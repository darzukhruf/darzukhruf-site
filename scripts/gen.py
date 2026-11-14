"""Dar Zukhruf design generator v3 (fal.ai) — the "hands" of the design agent.
Modes:
  * specs in specs/run/*.json not yet in manifest  -> generate them (opening batches / manual runs)
  * otherwise: next slot (00/06/12/18 Riyadh); spec_json from the design agent's sheet for that slot
Per set: N photoreal slides (same room, different views) each with a real material card, + a final 2D plan slide.
Output: gen/<id>_<n>.jpg + manifest.json on the `media` branch; log.txt with diagnostics."""
import base64, csv, glob, io, json, os, re, subprocess, sys, time, datetime as dt, requests
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from render import card_html, plan_html, board_html, story_html, hero_html, end_card_html

OUT = sys.argv[1] if len(sys.argv) > 1 else "media"
SPEC_DIR = sys.argv[2] if len(sys.argv) > 2 else "site/specs/run"
KEY = os.environ.get("FAL_KEY", "").strip()
T2I = os.environ.get("T2I_MODEL", "").strip() or "fal-ai/nano-banana"
EDIT = os.environ.get("EDIT_MODEL", "").strip() or "fal-ai/nano-banana/edit"
REPO = os.environ.get("REPO", "darzukhruf/darzukhruf-site")
PLAN_CSV = "https://docs.google.com/spreadsheets/d/14RmR325nkLONa_PhRXNLEbjbQoZdrlOTTxM1CIm9XrQ/export?format=csv"
RIY = dt.timezone(dt.timedelta(hours=3))
LOG = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.append(s)
if not KEY:
    print("FAL_KEY not set; skipping."); sys.exit(0)
H = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}

def fal(model, payload, timeout=300):
    for attempt in range(2):
        try:
            r = requests.post(f"https://fal.run/{model}", headers=H, json=payload, timeout=timeout)
            if r.ok: return r.json()
            log("fal", model, r.status_code, r.text[:300])
        except Exception as ex:
            log("fal err", model, ex)
        time.sleep(4)
    return None

def fetch(url):
    r = requests.get(url, timeout=120); r.raise_for_status(); return r.content

VISION = [("openrouter/router/vision", {"model": "google/gemini-2.5-flash"}),
          ("fal-ai/any-llm/vision", {"model": "google/gemini-2.5-flash"}),
          ("fal-ai/any-llm/vision", {"model": "google/gemini-flash-1.5"})]
def vision(prompt, url):
    for ep, extra in VISION:
        j = fal(ep, {**extra, "prompt": prompt, "image_url": url, "image_urls": [url]}, timeout=120)
        txt = (j or {}).get("output") or ""
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try: return json.loads(m.group(0)), ep
            except Exception: pass
    return None, None

QA = ("You are a senior QA inspector for AI-generated interior photos of a Saudi design studio. You know the typical failures of "
  "image models. Inspect the image very carefully and reply ONLY JSON: "
  '{"photoreal":0-10,"artifacts":true|false,"major_artifacts":true|false,"issues":["short fixable problem", ...],"inappropriate":true|false,'
  '"item_visible":true|false,"point":[x,y],"reason":"short"}. '
  "Check this list of AI-generation errors: (1) bent, wavy or non-parallel lines in walls, ceilings, door/window frames, tiles, shelves; "
  "(2) inconsistent perspective / multiple vanishing points; (3) furniture with missing, extra, floating or merged legs, sofas/cushions "
  "melting into each other, objects fused into walls; (4) duplicated or cloned objects (two identical lamps/vases where one is expected), "
  "illogical symmetry; (5) impossible geometry: doors or windows that lead nowhere, stairs to nowhere, cabinets without space, "
  "unrealistic scale (tiny chairs, giant lamps); (6) wrong lighting: shadows in different directions, light with no source, glowing "
  "edges, reflections that do not match the room (mirrors, glossy floors); (7) garbled text, fake letters, random symbols, watermarks; "
  "(8) smeared, blurry, plastic/CGI or over-smooth textures, repeating texture tiles, tiles not aligned; (9) curtains, rugs or fabrics "
  "clipping through furniture; (10) electrical oddities (cables to nowhere, switches in impossible places); (11) over-saturation, HDR halos, "
  "noise. artifacts=true if ANY of these is visible. major_artifacts=true ONLY for obvious errors an ordinary viewer would notice "
  "on a phone screen without zooming: missing/extra/merged/floating furniture legs, duplicated or fused objects, garbled text, impossible "
  "doors/windows/geometry, clearly bent or wavy walls/frames, absurd scale, or melted/clipping fabric; slight imperfections (small line "
  "deviations, subtle shadow or reflection inconsistencies, slightly smooth textures, minor halos) are NOT major. issues = each problem found, written as a precise retouch instruction "
  "(e.g. 'straighten the left window frame', 'remove the duplicated vase on the right'). inappropriate: anything against Saudi public "
  "decency or culture (people, revealing clothing, nudity incl. art/statues, alcohol, crosses/idols, offensive symbols). "
  "photoreal: 10 = indistinguishable from a real professional photo. item_visible: whether this element is clearly visible. "
  "point: normalized [x,y] (0..1 from top-left) of the centre of: ")

def qa_ok(q):
    major = q.get("major_artifacts", q.get("artifacts"))  # minor nitpicks are retouched but do not block publishing
    return q.get("photoreal", 0) >= 8 and not major and not q.get("inappropriate") and q.get("item_visible", True)

def to_jpg(raw, size=(1080, 1440)):
    im = Image.open(io.BytesIO(raw)).convert("RGB"); w, h = im.size; t = size[0] / size[1]
    if w / h > t: nw = int(h * t); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else: nh = int(w / t); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    b = io.BytesIO(); im.resize(size, Image.LANCZOS).save(b, "JPEG", quality=92); return b.getvalue()

STYLE = (" Shot as a real professional architectural interior photograph: full-frame camera, 24mm tilt-shift lens, natural "
         "daylight with warm practical lights, true-to-life materials and textures, straight verticals, realistic scale. "
         "Modest and family-friendly: no people, no statues or nude art, no alcohol, no religious symbols except Arabic "
         "geometric patterns, no text, no logos, no watermark.")

WALLS = dict(N="north", S="south", E="east", W="west")
FURN_EN = {"خزانة": "wardrobe", "زينة": "vanity", "كرسي": "chair", "شيزلونغ": "chaise longue", "جزيرة": "island",
           "كنبة": "sofa", "جلسة": "floor seating", "طاولة": "table", "تلفاز": "TV unit", "خزائن": "cabinets", "بنش": "bench",
           "إضاءة": "floor lamp", "مغسلة": "sink", "ثلاجة": "fridge", "قهوة": "coffee", "بار": "bar stools", "سرير": "bed"}

def furn_name(lb):
    hits = [en for ar, en in FURN_EN.items() if ar in lb]
    return (" ".join(dict.fromkeys(hits)) or "furniture piece") + f" ({lb})"

def wall_map(sp):
    """Which wall each piece stands against (nearest wall within 0.6 m), else centre. Same text goes into every photo prompt."""
    r = sp["room"]; W, L = float(r["w"]), float(r["l"]); walls = {k: [] for k in "NSEW"}; centre = []
    for o in sp.get("openings", []): walls[o["wall"]].append(o["type"])
    for f in sp.get("furniture", []):
        x, y, w, d = (float(f[k]) for k in ("x", "y", "w", "d"))
        dist = {"W": x, "E": W - (x + w), "S": y, "N": L - (y + d)}; k = min(dist, key=dist.get)
        (walls[k] if dist[k] <= 0.6 else centre).append(furn_name(f.get("label_ar", "")))
    parts = [f"{WALLS[k]} wall: " + ", ".join(v) for k, v in walls.items() if v]
    if centre: parts.append("centre of the room: " + ", ".join(centre))
    return "; ".join(parts)

def materials_text(sp):
    m = [f"{s.get('locate_en','element')} = {s['item'].get('name','')} by {s['item'].get('brand','')}" for s in sp.get("slides", []) if s.get("item")]
    return "; ".join(m)

def layout_text(sp):
    r = sp["room"]; s = f" The room is {r['w']} m wide, {r['l']} m long, ceiling height {r.get('h',3)} m."
    s += " FIXED LAYOUT (identical in every photo of this room, nothing added or moved): " + wall_map(sp) + "."
    mt = materials_text(sp)
    if mt: s += " FIXED MATERIALS AND COLOURS (identical in every photo): " + mt + "."
    return s

PRO_EDIT = os.environ.get("PRO_EDIT_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
DIFF = ("Compare IMAGE 1 (reference) and IMAGE 2 of an interior. Reply ONLY JSON: "
        '{"same_room":true|false,"same_viewpoint":true|false,"angle_change_deg":0-180,"reason":"short"}. '
        "same_room = same space, furniture, materials and colours. same_viewpoint = the camera position/direction/framing is "
        "nearly the same (a crop, zoom or tiny shift of the same shot counts as same_viewpoint). Close-up detail shots of a "
        "different element count as a different viewpoint. same_room must be FALSE if, compared with the layout below, the floor "
        "material/colour or wall colour differs, any piece stands on a different wall, a piece is missing that should be in view, "
        "or furniture that is not in the layout appears (e.g. an extra sofa). Layout: ")

def different_view(ref_url, url, layout=""):
    j = None
    for ep, extra in VISION:
        r = fal(ep, {**extra, "prompt": DIFF + (layout or "not given"), "image_urls": [ref_url, url], "image_url": ref_url}, timeout=120)
        txt = (r or {}).get("output") or ""; m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try: j = json.loads(m.group(0)); break
            except Exception: pass
    if j is None: return True, {"diff": "unchecked"}
    log("DIFF", json.dumps(j, ensure_ascii=False))
    return (j.get("same_room", True) and not j.get("same_viewpoint")), j

def gen_image(prompt, ref_url=None, locate="the main element", layout="", t2i=None):
    """Generate -> QA -> (repair -> QA) up to 2 times -> viewpoint check. Every generated or edited image passes QA."""
    for attempt in range(3):
        if ref_url:
            model = PRO_EDIT if attempt == 2 else EDIT
            j = fal(model, {"prompt": prompt, "image_urls": [ref_url], "num_images": 1, "aspect_ratio": "3:4", "output_format": "jpeg"})
        else: j = fal(t2i or T2I, {"prompt": prompt, "num_images": 1, "aspect_ratio": "3:4", "output_format": "jpeg"})
        url = (((j or {}).get("images") or [{}])[0]).get("url")
        if not url: continue
        q, ep = vision(QA + locate, url)
        if q is None:
            log("QA unavailable -> rejecting (never publish unchecked)"); continue
        log("QA", json.dumps(q, ensure_ascii=False))
        repairs = 0
        while not qa_ok(q) and not q.get("inappropriate") and q.get("issues") and repairs < 2:
            repairs += 1
            fix = "; ".join(i if isinstance(i, str) else json.dumps(i, ensure_ascii=False) for i in q["issues"][:5])
            r = fal(EDIT, {"prompt": "Retouch this interior photograph. Fix ONLY these problems: " + fix + ". Keep the composition, "
                           "camera, furniture, materials, colours and lighting identical. Result must look like a real professional photo, "
                           "no text, no people.", "image_urls": [url], "num_images": 1, "aspect_ratio": "3:4", "output_format": "jpeg"})
            u2 = (((r or {}).get("images") or [{}])[0]).get("url")
            if not u2: break
            q2, _ = vision(QA + locate, u2)
            if q2 is None: break
            log("REPAIR", repairs, fix, "->", json.dumps(q2, ensure_ascii=False))
            url, q = u2, q2
        if not qa_ok(q): log("rejected after repairs:", q.get("reason")); continue
        if ref_url:
            dv, dj = different_view(ref_url, url, layout); q["diff"] = dj
            if not dv: log("rejected: same viewpoint or different room"); continue
        q["raw"] = url
        return url, q
    return None, None

def to_vertical(path_in, path_out):
    """3:4 card slide -> 9:16 story frame (1080x1920): blurred, darkened fill behind the full slide."""
    from PIL import ImageFilter, ImageEnhance
    im = Image.open(path_in).convert("RGB")
    bg = im.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(40)); bg = ImageEnhance.Brightness(bg).enhance(0.55)
    fg = im.resize((1080, int(im.height * 1080 / im.width)))
    bg.paste(fg, (0, (1920 - fg.height) // 2)); bg.save(path_out, "JPEG", quality=90)

def make_vertical(ident, files):
    """Stories (first 3 photos) + one reel (all photos + plan, crossfades). Reuses the same images: no new generation."""
    stories, frames = [], []
    for i, f in enumerate(files):
        out = f"gen/{ident}_v{i+1}.jpg"; to_vertical(os.path.join(OUT, f), os.path.join(OUT, out)); frames.append(out)
        if i < 3 and not f.endswith("_plan.jpg"): stories.append(out)
    reel = f"gen/{ident}_reel.mp4"; d, x = 3.2, 0.6
    try:
        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for fr in frames: args += ["-loop", "1", "-t", str(d), "-i", os.path.join(OUT, fr)]
        chain, last = [], "[0:v]"
        for i in range(1, len(frames)):
            chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={x}:offset={i*(d-x):.2f}[x{i}]"); last = f"[x{i}]"
        args += ["-filter_complex", ";".join(chain) + f";{last}format=yuv420p,fps=30[v]" if chain else f"[0:v]format=yuv420p,fps=30[v]",
                 "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", os.path.join(OUT, reel)]
        subprocess.run(args, check=True, timeout=300)
    except Exception as ex:
        log("reel failed", ex); reel = None
    return stories, reel

def build_multi(spec, browser, ident, slot=None):
    slides = spec["slides"]; total = len(slides) + 1
    base = spec["scene_en"].strip() + layout_text(spec)
    master_url, q0 = gen_image("Photorealistic photograph of " + base + " View: " + slides[0]["view_en"] + "." + STYLE,
                               locate=slides[0].get("locate_en", "the main wall"))
    if not master_url: log("master failed", ident); return None
    shots = [(master_url, q0)]
    for s in slides[1:]:
        u, q = gen_image("NEW CAMERA POSITION. This is the same room as the reference photo (identical layout, furniture, materials, "
                         "colours and lighting), but photographed from a COMPLETELY DIFFERENT viewpoint — do NOT reuse the reference "
                         f"framing or direction. New shot: {s['view_en']}." + layout_text(spec) + " Show the parts of the room "
                         "that are not visible in the reference EXACTLY as described in the fixed layout, and keep at least one element "
                         "that is also visible in the reference photo in frame so it reads as the same room. Do not invent extra furniture."
                         + STYLE, master_url, s.get("locate_en", "the main element"), wall_map(spec) + " | materials: " + materials_text(spec))
        shots.append((u, q) if u else (None, None))
    os.makedirs(os.path.join(OUT, "gen"), exist_ok=True)
    page = browser.new_page(viewport={"width": 1080, "height": 1440})
    files, qas, materials, n = [], [], [], 0
    for s, (u, q) in zip(slides, shots):
        if not u: continue
        n += 1; photo = to_jpg(fetch(u))
        pt = (q or {}).get("point")
        if not s["item"].get("hex") and pt and s["item"].get("sample_color", True):
            try:  # swatch = colour sampled from the image at the marked point ("أقرب درجة")
                im = Image.open(io.BytesIO(photo)).convert("RGB"); x, y = int(pt[0] * 1080), int(pt[1] * 1440)
                c = im.crop((max(0, x - 20), max(0, y - 20), min(1080, x + 20), min(1440, y + 20))).resize((1, 1), Image.BOX).getpixel((0, 0))
                s["item"]["hex"] = "#%02X%02X%02X" % c
            except Exception: pass
        page.set_content(card_html(photo, s["item"], (q or {}).get("point"), n, total), wait_until="networkidle")
        page.wait_for_timeout(300)
        fn = f"gen/{ident}_{n}.jpg"; page.screenshot(path=os.path.join(OUT, fn), type="jpeg", quality=90)
        files.append(fn); qas.append(q); materials.append(s["item"])
    if n < 2: log("too few slides", ident); page.close(); return None
    n += 1; page.set_content(plan_html(spec, n, n), wait_until="networkidle"); page.wait_for_timeout(300)
    fn = f"gen/{ident}_{n}_plan.jpg"; page.screenshot(path=os.path.join(OUT, fn), type="jpeg", quality=92); files.append(fn)
    page.close()
    if n != total:  # renumber badge mismatch is cosmetic; keep as is
        log("note: some slides dropped", ident)
    try: stories, reel = make_vertical(ident, files)
    except Exception as ex: log("vertical failed", ex); stories, reel = [], None
    raw = f"https://raw.githubusercontent.com/{REPO}/media/"
    return {"id": ident, "slot": slot or spec.get("slot") or "opening", "title_ar": spec.get("title_ar"),
            "space_ar": spec.get("space_ar"), "style_ar": spec.get("style_ar"), "palette_ar": spec.get("palette_ar"),
            "room": spec["room"], "materials": materials, "qa": qas, "notes": spec.get("notes_ar", ""),
            "images": [f"https://raw.githubusercontent.com/{REPO}/media/{f}" for f in files],
            "stories": [raw + f for f in stories], "reel": (raw + reel) if reel else None,
            "created_riyadh": dt.datetime.now(RIY).strftime("%Y-%m-%d %H:%M")}

HERO_T2I = os.environ.get("HERO_MODEL", "").strip() or "fal-ai/nano-banana-pro"
LOCATE = ("Reply ONLY JSON {\"items\":[{\"point\":[x,y],\"hex\":\"#RRGGBB\"},...]} — one item per element below, same order: "
          "point = normalized (0..1 from top-left) centre of a clean, evenly lit patch of that element (not a shadow, highlight, window or "
          "another object); hex = the element's true base colour as it appears in the photo (null if not visible). Elements: ")

def _hex(c): return "#%02X%02X%02X" % tuple(int(v) for v in c[:3])
def _rgb(h):
    h = (h or "").lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) if len(h) == 6 else None

def shoot(page, html, path, w=1080, h=1440):
    page.set_viewport_size({"width": w, "height": h}); page.set_content(html, wait_until="networkidle")
    page.wait_for_timeout(500); page.screenshot(path=path, type="jpeg", quality=91)

def reel_from(frames, out, kb=True):
    """Reel with crossfades. kb=True adds a slow Ken Burns zoom/pan to every photo frame (E-26, T-20261114-04);
    the WhatsApp end card (_rend.jpg) stays static so its text is readable. Any ffmpeg error -> static fallback."""
    d, x, fps = 3.4, 0.6, 30
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for fr in frames: args += ["-framerate", str(fps), "-loop", "1", "-t", str(d), "-i", fr]
    pre, src = [], []
    for i, fr in enumerate(frames):
        if kb and not fr.endswith("_rend.jpg"):
            n = int(d * fps); zin = i % 2 == 0  # alternate zoom-in / zoom-out, drift direction alternates too
            z = f"1+0.07*on/{n}" if zin else f"1.07-0.07*on/{n}"
            px = "(iw-iw/zoom)/2" if i % 4 < 2 else f"(iw-iw/zoom)*on/{n}"
            pre.append(f"[{i}:v]scale=2160:3840,zoompan=z='{z}':x='{px}':y='(ih-ih/zoom)/2':d=1:s=1080x1920:fps={fps},setsar=1[k{i}]")
        else:
            pre.append(f"[{i}:v]scale=1080:1920,setsar=1,fps={fps}[k{i}]")
        src.append(f"[k{i}]")
    chain, last = [], src[0]
    for i in range(1, len(frames)):
        chain.append(f"{last}{src[i]}xfade=transition=fade:duration={x}:offset={i*(d-x):.2f}[x{i}]"); last = f"[x{i}]"
    fc = ";".join(pre + chain + [f"{last}format=yuv420p[v]"])
    enc = ["-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", out]
    try:
        subprocess.run(args + ["-filter_complex", fc] + enc, check=True, timeout=300)
    except Exception as ex:
        if not kb: raise
        log("ken burns failed, static reel", ex); reel_from(frames, out, kb=False)

def build_single(spec, browser, ident, slot=None):
    """One strong hero photo + material board + (optional) 2D plan; stories and a reel from the same three images."""
    mats = [dict(m) for m in spec.get("materials", [])][:4]
    prompt = ("Photorealistic photograph of " + spec["scene_en"].strip() + layout_text({**spec, "slides": [
              {"locate_en": m.get("locate_en", "element"), "item": m} for m in mats]}) + " View: " + spec.get("view_en", "wide shot from the entrance") + "." + STYLE)
    url, q = gen_image(prompt, locate=(mats[0].get("locate_en") if mats else "the main element"), t2i=HERO_T2I)
    if not url: log("hero failed", ident); return None
    photo = to_jpg(fetch(url))
    try:  # swatches: median colour of a patch at the located point, cross-checked with the vision model's colour reading
        res, _ = vision(LOCATE + "; ".join(m.get("locate_en", "element") for m in mats), url)
        items = (res or {}).get("items") or []
        im = Image.open(io.BytesIO(photo)).convert("RGB")
        for m, it in zip(mats, items):
            if m.get("hex") or not isinstance(it, dict): continue
            vh, pt, samp = _rgb(it.get("hex")), it.get("point"), None
            if pt and len(pt) == 2 and pt[0] is not None:
                x, y = int(pt[0] * 1080), int(pt[1] * 1440)
                patch = im.crop((max(0, x - 30), max(0, y - 30), min(1080, x + 30), min(1440, y + 30)))
                px = sorted(patch.getdata(), key=lambda c: sum(c)); mid = px[len(px) // 4: 3 * len(px) // 4] or px
                samp = tuple(sum(c[i] for c in mid) / len(mid) for i in range(3))
            if samp and vh and sum((a - b) ** 2 for a, b in zip(samp, vh)) ** 0.5 > 70: m["hex"] = _hex(vh)  # sample hit the wrong thing
            elif samp: m["hex"] = _hex(samp)
            elif vh: m["hex"] = _hex(vh)
    except Exception as ex: log("swatch sampling failed", ex)
    os.makedirs(os.path.join(OUT, "gen"), exist_ok=True)
    page = browser.new_page(); files = []
    with_plan = spec.get("include_plan", True) and spec.get("room"); total = 3 if with_plan else 2
    f1 = f"gen/{ident}_1.jpg"; shoot(page, hero_html(photo), os.path.join(OUT, f1)); files.append(f1)
    f2 = f"gen/{ident}_2_board.jpg"; shoot(page, board_html(spec, photo, mats, 2, total), os.path.join(OUT, f2)); files.append(f2)
    if with_plan:
        f3 = f"gen/{ident}_3_plan.jpg"; shoot(page, plan_html(spec, 3, 3), os.path.join(OUT, f3)); files.append(f3)
    stories, frames = [], []
    for i, f in enumerate(files):
        b = open(os.path.join(OUT, f), "rb").read()
        sv = f"gen/{ident}_s{i+1}.jpg"; shoot(page, story_html(b), os.path.join(OUT, sv), 1080, 1920)
        if i < 2: stories.append(sv)
        rv = f"gen/{ident}_r{i+1}.jpg"; shoot(page, story_html(b, spec.get("reel_hook_ar") if i == 0 else None), os.path.join(OUT, rv), 1080, 1920)
        frames.append(os.path.join(OUT, rv))
    try:  # E-22: WhatsApp end card as the last reel frame (never blocks the reel if it fails)
        ec = os.path.join(OUT, f"gen/{ident}_rend.jpg"); shoot(page, end_card_html(), ec, 1080, 1920); frames.append(ec)
    except Exception as ex: log("end card failed", ex)
    page.close()
    reel = f"gen/{ident}_reel.mp4"
    try: reel_from(frames, os.path.join(OUT, reel))
    except Exception as ex: log("reel failed", ex); reel = None
    for fr in frames:
        try: os.remove(fr)
        except Exception: pass
    raw = f"https://raw.githubusercontent.com/{REPO}/media/"
    return {"id": ident, "format": "single", "category": spec.get("category", "residential"), "slot": slot or spec.get("slot") or "manual",
            "title_ar": spec.get("title_ar"), "space_ar": spec.get("space_ar"), "style_ar": spec.get("style_ar"),
            "palette_ar": spec.get("palette_ar"), "reel_hook_ar": spec.get("reel_hook_ar"), "room": spec.get("room"),
            "materials": mats, "qa": [q], "notes": spec.get("notes_ar", ""), "images": [raw + f for f in files],
            "stories": [raw + f for f in stories], "reel": (raw + reel) if reel else None,
            "created_riyadh": dt.datetime.now(RIY).strftime("%Y-%m-%d %H:%M")}

def build(spec, browser, ident, slot=None):
    if spec.get("format") == "single" or ("materials" in spec and "slides" not in spec):
        return build_single(spec, browser, ident, slot)
    return build_multi(spec, browser, ident, slot)

def norm_slot(v):
    """Google Sheets turns "2026-11-07 00:00" into a date and exports it as "2026-11-07 0:00" — normalise to YYYY-MM-DD HH:MM."""
    v = (v or "").strip()
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
        try: return dt.datetime.strptime(v, f).strftime("%Y-%m-%d %H:%M")
        except ValueError: pass
    return v

def main():
    from playwright.sync_api import sync_playwright
    man_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else []
    done = {m["id"] for m in manifest}
    jobs = []
    for p in sorted(glob.glob(os.path.join(SPEC_DIR, "*.json"))):
        sp = json.load(open(p, encoding="utf-8")); ident = sp.get("id") or os.path.splitext(os.path.basename(p))[0]
        if ident not in done: jobs.append((sp, ident, sp.get("slot")))
    # backfill stories + reel for upcoming slot entries made before this feature (reuses their images)
    now0 = dt.datetime.now(RIY).replace(tzinfo=None); changed = False
    for m in manifest:
        try: st = dt.datetime.strptime(m.get("slot", ""), "%Y-%m-%d %H:%M")
        except Exception: continue
        if st > now0 and ("stories" not in m or not m.get("reel")):
            files = [u.split("/media/", 1)[1] for u in m.get("images", [])]
            if files and all(os.path.exists(os.path.join(OUT, f)) for f in files):
                try:
                    stories, reel = make_vertical(m["id"], files); raw = f"https://raw.githubusercontent.com/{REPO}/media/"
                    m["stories"] = [raw + f for f in stories]; m["reel"] = (raw + reel) if reel else None; changed = True
                    log("backfilled vertical", m["id"])
                except Exception as ex: log("backfill failed", m.get("id"), ex)
    if changed: json.dump(manifest, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not jobs:  # buffer: build up to MAX_SETS upcoming slots (next 36h) that have a spec and no design yet
        now = dt.datetime.now(RIY).replace(tzinfo=None); max_sets = int(os.environ.get("MAX_SETS", "3"))
        done_slots = {m.get("slot") for m in manifest}
        try:
            r = requests.get(PLAN_CSV, timeout=30); r.encoding = "utf-8"
            plan = {}
            for row in csv.DictReader(io.StringIO(r.text)):
                if not (row.get("spec_json") or "").strip(): continue
                k = norm_slot(row.get("slot"))
                if k: plan[k] = row
            log("plan", r.status_code, len(plan), "rows", (sorted(plan)[-1] if plan else repr(r.text[:120])))
        except Exception as ex:
            log("plan read failed", ex); plan = {}
        for key in sorted(plan):  # flexible publishing times chosen by the design/market agents
            try: slot = dt.datetime.strptime(key, "%Y-%m-%d %H:%M")
            except ValueError: log("bad slot", key); continue
            if not (dt.timedelta(minutes=20) <= slot - now <= dt.timedelta(hours=36)) or key in done_slots:
                if slot > now: log("skip", key, "in", slot - now, "done" if key in done_slots else "")
                continue
            try: sp = json.loads(plan[key]["spec_json"])
            except Exception as ex: log("bad spec", key, ex); continue
            ident = slot.strftime("%Y-%m-%d_%H%M") + "_" + re.sub(r"[^a-z0-9]+", "-", sp.get("space_en", "design").lower())[:20]
            jobs.append((sp, ident, key))
            if len(jobs) >= max_sets: break
        if not jobs: log("buffer full or no specs"); return
    with sync_playwright() as p:
        br = p.chromium.launch()
        for sp, ident, slot in jobs:
            try:
                m = build(sp, br, ident, slot)
                if m: manifest.append(m); log("OK", ident, len(m["images"]), "images")
            except Exception as ex:
                log("build error", ident, repr(ex))
            json.dump(manifest[-300:], open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        br.close()
    # prune images older than 7 days (Metricool keeps its own copy once scheduled)
    cut = dt.datetime.now(RIY).replace(tzinfo=None) - dt.timedelta(days=7)
    for m in manifest:
        try:
            c = dt.datetime.strptime(m["created_riyadh"], "%Y-%m-%d %H:%M")
            if c < cut and not m.get("pruned") and not str(m.get("id", "")).startswith("client-"):  # client deliveries are kept
                for u in m["images"]:
                    f = os.path.join(OUT, u.split("/media/", 1)[1])
                    if os.path.exists(f): os.remove(f)
                m["pruned"] = True
        except Exception: pass
    json.dump(manifest[-300:], open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

try:
    main()
finally:
    with open(os.path.join(OUT, "log.txt"), "w", encoding="utf-8") as f:
        f.write(dt.datetime.now(RIY).isoformat() + "\n" + "\n".join(LOG) + "\n")
