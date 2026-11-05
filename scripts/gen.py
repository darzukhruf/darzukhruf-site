"""Dar Zukhruf design generator: one new design (4 angles) per run.
Writes JPGs + manifest.json into the given folder (the `media` branch checkout)."""
import base64, io, json, os, sys, time, datetime, requests
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "media"
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("IMAGE_MODEL", "").strip() or "gemini-2.5-flash-image"
REPO = os.environ.get("REPO", "darzukhruf/darzukhruf-site")
if not KEY:
    print("GEMINI_API_KEY not set; skipping."); sys.exit(0)

SPACES = [("men's majlis with floor and sofa seating", "مجلس رجال"), ("women's majlis", "مجلس نساء"),
  ("family living room with TV wall", "صالة عائلية"), ("master bedroom", "غرفة نوم رئيسية"),
  ("open kitchen with island", "مطبخ مفتوح"), ("villa entrance foyer", "مدخل فيلا"),
  ("guest powder room", "حمام ضيوف"), ("home office", "مكتب منزلي"), ("dining room", "غرفة طعام"),
  ("dressing room / walk-in closet", "غرفة ملابس"), ("outdoor courtyard seating (hosh)", "جلسة الحوش"),
  ("staircase and corridor", "الدرج والممر"), ("coffee corner with dallah display", "ركن القهوة")]
STYLES = [("Japandi", "ياباندي"), ("warm minimalism", "مينيمال دافئ"), ("quiet luxury", "فخامة هادئة"),
  ("modern Najdi", "نجدي عصري"), ("contemporary classic", "كلاسيك معاصر"), ("organic modern", "عضوي عصري"),
  ("wabi-sabi", "وابي سابي"), ("modern Hejazi with roshan wood lattice", "حجازي عصري"),
  ("mid-century modern", "منتصف القرن"), ("Mediterranean Saudi", "متوسطي بروح سعودية")]
PALETTES = [("sand beige and olive green", "رملي وزيتي"), ("ivory and sage", "عاجي ومريمية"),
  ("terracotta and cream", "تراكوتا وكريمي"), ("walnut and charcoal", "جوزي وفحمي"),
  ("greige and brushed brass", "رمادي بيج ونحاسي"), ("deep emerald and gold", "زمردي وذهبي"),
  ("mocha brown and off-white", "موكا وأوف وايت"), ("navy and camel", "كحلي وجملي"),
  ("dusty rose and taupe", "وردي مطفي وتوبي"), ("butter yellow and linen", "أصفر زبدي وكتاني")]
DETAILS = [("a Sadu-pattern rug", "سجادة سدو"), ("a carved mashrabiya screen", "مشربية"),
  ("Najdi triangular niches", "نيشات نجدية"), ("a palm-frond (khoos) ceiling detail", "سقف خوص"),
  ("framed Arabic calligraphy art", "لوحة خط عربي"), ("an eight-pointed star inlay", "نجمة ثمانية"),
  ("handmade pottery and brass dallah", "فخار ودلة نحاس"), ("lime plaster walls", "جدران بلاستر"),
  ("arched openings", "أقواس"), ("hidden cove lighting", "إضاءة مخفية")]
ANGLES = ["a wide view from the opposite corner of the same room",
          "a close-up detail shot of the main materials, textures and decor of the same room",
          "a side view of the same room looking toward the window"]

man_path = os.path.join(OUT, "manifest.json")
manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else []
n = len(manifest)
sp, st, pa, de = SPACES[n % 13], STYLES[(n * 3) % 10], PALETTES[(n * 7) % 10], DETAILS[(n * 3 + 1) % 10]

base = (f"Photorealistic interior design photograph of a {sp[0]} in a Saudi Arabian home, {st[0]} style, "
        f"colour palette of {pa[0]}, featuring {de[0]}, soft natural daylight with warm accent lighting, "
        "high-end architectural photography, 35mm lens, styled and tidy, no people, no text, no logos, no watermark.")

def gen(prompt, ref=None):
    parts = [{"text": prompt}]
    if ref:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(ref).decode()}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "3:4"}}}
    for attempt in range(3):
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
                          headers={"x-goog-api-key": KEY, "Content-Type": "application/json"}, json=body, timeout=180)
        if r.ok:
            for p in r.json().get("candidates", [{}])[0].get("content", {}).get("parts", []):
                d = p.get("inlineData") or p.get("inline_data")
                if d: return base64.b64decode(d["data"])
        print("attempt", attempt + 1, r.status_code, r.text[:300]); time.sleep(10)
    raise SystemExit("image generation failed")

def to_jpg(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size; t = 3 / 4
    if w / h > t: nw = int(h * t); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else: nh = int(w / t); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    b = io.BytesIO(); im.resize((1080, 1440), Image.LANCZOS).save(b, "JPEG", quality=88, optimize=True)
    return b.getvalue()

now = datetime.datetime.utcnow()
did = now.strftime("%Y%m%d-%H%M")
os.makedirs(os.path.join(OUT, "gen"), exist_ok=True)
master = to_jpg(gen(base))
imgs = [master] + [to_jpg(gen("Using the reference image, show the exact same room with the same furniture, "
                               f"materials, colours and lighting, but as {a}. Photorealistic, no people, no text.", master))
                   for a in ANGLES]
urls = []
for i, b in enumerate(imgs, 1):
    fn = f"gen/{did}-{i}.jpg"; open(os.path.join(OUT, fn), "wb").write(b)
    urls.append(f"https://raw.githubusercontent.com/{REPO}/media/{fn}")
manifest.append({"id": did, "created_utc": now.isoformat(timespec="minutes"), "space": sp[1], "style": st[1],
                 "palette": pa[1], "detail": de[1], "prompt": base, "images": urls})
json.dump(manifest, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("generated", did, sp[1], st[1], pa[1])
