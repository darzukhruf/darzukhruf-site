"""Dar Zukhruf design generator (the "hands" of the design agent).
Runs ~1h before each posting slot (00:00, 06:00, 12:00, 18:00 Riyadh).
1) Reads the design agent's plan (public CSV of Google Sheet "خطة التصاميم") for the next slot.
2) Generates 1 master + 3 angles with Gemini, QA-checks each image (realism, artifacts, decency), retries.
3) Saves gen/YYYY-MM-DD_HHMM_<space>_N.jpg + manifest.json on the `media` branch; prunes files > 7 days."""
import base64, csv, io, json, os, re, sys, time, datetime as dt, requests
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "media"
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("IMAGE_MODEL", "").strip() or "gemini-2.5-flash-image"
QA_MODEL = os.environ.get("QA_MODEL", "").strip() or "gemini-2.5-flash"
REPO = os.environ.get("REPO", "darzukhruf/darzukhruf-site")
PLAN_CSV = "https://docs.google.com/spreadsheets/d/14RmR325nkLONa_PhRXNLEbjbQoZdrlOTTxM1CIm9XrQ/export?format=csv"
FALLBACK_FROM = dt.datetime(2026, 11, 9, 6, 0)  # before this, only generate planned slots (library covers earlier slots)
RIY = dt.timezone(dt.timedelta(hours=3))
if not KEY:
    print("GEMINI_API_KEY not set; skipping."); sys.exit(0)

# ---- target slot ----
now = dt.datetime.now(RIY).replace(tzinfo=None)
slot = None
for add in range(0, 30):
    c = (now + dt.timedelta(hours=add)).replace(minute=0, second=0, microsecond=0)
    if c.hour % 6 == 0 and c - now >= dt.timedelta(minutes=20):
        slot = c; break
slot_key = slot.strftime("%Y-%m-%d %H:%M")
man_path = os.path.join(OUT, "manifest.json")
manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else []
if any(m.get("slot") == slot_key for m in manifest):
    print("already generated for", slot_key); sys.exit(0)

# ---- plan from design agent ----
plan = None
try:
    r = requests.get(PLAN_CSV, timeout=30); r.encoding = "utf-8"
    for row in csv.DictReader(io.StringIO(r.text)):
        if (row.get("slot") or "").strip() == slot_key and (row.get("prompt_en") or "").strip():
            plan = row
except Exception as e:
    print("plan read failed:", e)

SPACES = [("men's majlis", "مجلس رجال"), ("women's majlis", "مجلس نساء"), ("family living room", "صالة عائلية"),
  ("master bedroom", "غرفة نوم رئيسية"), ("open kitchen with island", "مطبخ مفتوح"), ("villa entrance foyer", "مدخل فيلا"),
  ("guest powder room", "حمام ضيوف"), ("home office", "مكتب منزلي"), ("dining room", "غرفة طعام"),
  ("dressing room", "غرفة ملابس"), ("outdoor courtyard seating", "جلسة الحوش"), ("coffee corner", "ركن القهوة")]
STYLES = [("Japandi", "ياباندي"), ("warm minimalism", "مينيمال دافئ"), ("quiet luxury", "فخامة هادئة"),
  ("modern Najdi", "نجدي عصري"), ("contemporary classic", "كلاسيك معاصر"), ("organic modern", "عضوي عصري"),
  ("modern Hejazi", "حجازي عصري")]
PALETTES = [("sand beige and olive green", "رملي وزيتي"), ("ivory and sage", "عاجي ومريمية"),
  ("terracotta and cream", "تراكوتا وكريمي"), ("walnut and charcoal", "جوزي وفحمي"),
  ("greige and brushed brass", "رمادي بيج ونحاسي"), ("deep emerald and gold", "زمردي وذهبي"),
  ("mocha brown and off-white", "موكا وأوف وايت")]
if plan:
    meta = {k: plan.get(k, "") for k in ("space_ar", "style_ar", "palette_ar", "detail_ar", "notes")}
    base = plan["prompt_en"].strip()
    angles = [a.strip() for a in (plan.get("angles_en") or "").split("|") if a.strip()]
else:
    if slot < FALLBACK_FROM:
        print("no plan for", slot_key, "and before fallback date; skipping."); sys.exit(0)
    n = len(manifest)
    sp, st, pa = SPACES[n % len(SPACES)], STYLES[(n * 3) % len(STYLES)], PALETTES[(n * 5) % len(PALETTES)]
    meta = {"space_ar": sp[1], "style_ar": st[1], "palette_ar": pa[1], "detail_ar": "", "notes": "fallback"}
    base = (f"{sp[0]} in a Saudi Arabian home, {st[0]} interior style, colour palette of {pa[0]}, "
            "subtle Saudi heritage details")
    angles = []
angles = (angles + ["a wide view from the opposite corner of the same room",
                    "a close-up detail shot of the main materials and decor of the same room",
                    "a side view of the same room toward the window"])[:3]
STYLE_SUFFIX = (" Shot as a real professional architectural interior photograph (full-frame camera, 24mm tilt-shift, "
  "natural daylight, true-to-life materials, straight vertical lines, realistic scale and proportions, subtle imperfections). "
  "Modest and family-friendly: no people, no statues or nude art, no alcohol, no religious symbols other than Arabic calligraphy patterns, "
  "no text, no logos, no watermark.")

def api(model, parts, gen_cfg):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = requests.post(url, headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                      json={"contents": [{"parts": parts}], "generationConfig": gen_cfg}, timeout=180)
    if not r.ok: print(model, r.status_code, r.text[:300]); return None
    return r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])

def img_part(b): return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b).decode()}}

def generate(prompt, ref=None):
    parts = [{"text": prompt}] + ([img_part(ref)] if ref else [])
    for p in api(MODEL, parts, {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "3:4"}}) or []:
        d = p.get("inlineData") or p.get("inline_data")
        if d: return to_jpg(base64.b64decode(d["data"]))
    return None

QA_PROMPT = ("You are a strict quality inspector for a Saudi interior design studio's social media. Inspect this image and reply JSON only: "
  '{"photoreal": 0-10, "artifacts": true/false, "inappropriate": true/false, "reason": "short"}. '
  "artifacts = any warped/melted furniture, impossible geometry, bent straight lines, garbled text or letters, extra/merged objects, "
  "plastic CGI look, wrong shadows or reflections. inappropriate = anything against Saudi public decency or culture: people in revealing "
  "clothing, nudity in art/statues, alcohol, crosses or idols, gambling, offensive symbols.")

def qa(b):
    parts = api(QA_MODEL, [{"text": QA_PROMPT}, img_part(b)], {"responseMimeType": "application/json"})
    try:
        j = json.loads(parts[0]["text"])
        ok = j.get("photoreal", 0) >= 8 and not j.get("artifacts") and not j.get("inappropriate")
        return ok, j
    except Exception as e:
        return False, {"reason": f"qa error {e}"}

def to_jpg(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB"); w, h = im.size; t = 3 / 4
    if w / h > t: nw = int(h * t); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else: nh = int(w / t); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    b = io.BytesIO(); im.resize((1080, 1440), Image.LANCZOS).save(b, "JPEG", quality=90, optimize=True)
    return b.getvalue()

def good(prompt, ref=None, tries=3):
    last = None
    for _ in range(tries):
        b = generate(prompt, ref)
        if not b: time.sleep(5); continue
        ok, rep = qa(b); last = rep
        if ok: return b, rep
        print("QA rejected:", rep)
    return None, last

master, rep0 = good("Photorealistic photograph of a " + base + "." + STYLE_SUFFIX)
if not master:
    print("master failed QA; no design for", slot_key, rep0); sys.exit(0)
imgs, reps = [master], [rep0]
for a in angles:
    b, rep = good("Using the reference photo, show the exact same room with identical furniture, materials, colours and lighting, "
                  f"but as {a}." + STYLE_SUFFIX, master)
    if b: imgs.append(b); reps.append(rep)
if len(imgs) < 2:
    print("not enough approved angles; skipping", slot_key); sys.exit(0)

space_slug = re.sub(r"[^a-z0-9]+", "-", base.split(" in ")[0].lower()).strip("-")[:24] or "design"
os.makedirs(os.path.join(OUT, "gen"), exist_ok=True)
urls = []
for i, b in enumerate(imgs, 1):
    fn = f"gen/{slot.strftime('%Y-%m-%d_%H%M')}_{space_slug}_{i}.jpg"
    open(os.path.join(OUT, fn), "wb").write(b)
    urls.append(f"https://raw.githubusercontent.com/{REPO}/media/{fn}")
manifest.append({"id": slot.strftime("%Y-%m-%d_%H%M"), "slot": slot_key, "planned": bool(plan), **meta,
                 "prompt": base, "qa": reps, "images": urls,
                 "created_riyadh": now.strftime("%Y-%m-%d %H:%M")})

# prune image files older than 7 days (Metricool keeps its own copy after scheduling)
cut = now - dt.timedelta(days=7)
for m in manifest:
    try:
        if dt.datetime.strptime(m["slot"], "%Y-%m-%d %H:%M") < cut and not m.get("pruned"):
            for u in m.get("images", []):
                p = os.path.join(OUT, u.split("/media/", 1)[1])
                if os.path.exists(p): os.remove(p)
            m["pruned"] = True
    except Exception:
        pass
json.dump(manifest[-200:], open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("generated", slot_key, len(imgs), "images", meta.get("space_ar"))
