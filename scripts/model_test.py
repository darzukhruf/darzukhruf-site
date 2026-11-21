"""Model comparison test (owner request 21-11): same 3 rooms, same prompt, several image models, ONE raw image each
(no retries, no retouch) so we compare the models' own error rate. Judged by the same vision checks the generator uses.
Output: media/model-test/<run>/ (images + results.json). Never published."""
import os, sys, json, re, time, datetime as dt, glob, requests
SRC = open(os.path.join(os.path.dirname(__file__), "gen.py"), encoding="utf-8").read()
SRC = SRC[:SRC.index("\ndef main():")]          # definitions only, gen.py's main() is not run
g = {"__name__": "gen_defs", "__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen.py")}; sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "media"]
exec(compile(SRC, "gen.py", "exec"), g)
fal, vision, QA, ACCURACY, openings_text, layout_text, STYLE, log = (g[k] for k in
    ("fal", "vision", "QA", "ACCURACY", "openings_text", "layout_text", "STYLE", "log"))
OUT = sys.argv[1]; H = g["H"]
# candidate endpoints per family (first one that answers wins); search API fills gaps
FAMILIES = {
  "Nano Banana Pro (Google)": ["fal-ai/nano-banana-pro"],
  "GPT Image (OpenAI)": ["fal-ai/gpt-image-2.5", "fal-ai/gpt-image-2", "fal-ai/gpt-image-1.5", "openai/gpt-image-2"],
  "Seedream 5 Pro (ByteDance)": ["fal-ai/bytedance/seedream/v5/pro/text-to-image", "fal-ai/bytedance/seedream/v5/text-to-image",
                                  "fal-ai/bytedance/seedream/v4.5/text-to-image"],
}
SEARCH = {"GPT Image (OpenAI)": "gpt-image", "Seedream 5 Pro (ByteDance)": "seedream"}
def search(q):
    try:
        r = requests.get("https://api.fal.ai/v1/models", params={"q": q, "limit": 20}, headers={"Authorization": H["Authorization"]}, timeout=30)
        ids = [m.get("endpoint_id") for m in r.json().get("models", []) if m.get("endpoint_id")]
        return sorted([i for i in ids if "edit" not in i and ("text-to-image" in i or i.count("/") <= 2)], reverse=True)
    except Exception as ex: log("search failed", q, ex); return []
PAYLOADS = lambda p: [{"prompt": p, "num_images": 1, "aspect_ratio": "3:4", "output_format": "jpeg"},
                      {"prompt": p, "num_images": 1, "image_size": "portrait_4_3"},
                      {"prompt": p, "num_images": 1, "image_size": {"width": 1080, "height": 1440}},
                      {"prompt": p}]
def generate(ep, p):
    for pl in PAYLOADS(p):
        t = time.time(); j = fal(ep, pl, timeout=400)
        u = (((j or {}).get("images") or [{}])[0]).get("url") if j else None
        if u: return u, round(time.time() - t)
        if g["BLOCK"]: return None, 0
    return None, 0
LAYOUT_CHECK = ("You check an interior photo against the planned layout below. Judge ONLY what is visible. Reply ONLY JSON "
                '{"matches":true|false,"problems":["short", ...]}. matches=false if a listed piece stands on a different wall, '
                "a piece that is clearly in view is missing, furniture NOT in the layout appears, or floor/wall colours clearly differ. Layout: ")
rooms = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "specs", "model-test", "rooms", "*.json")))
run = dt.datetime.now(g["RIY"]).strftime("%Y%m%d-%H%M"); od = os.path.join(OUT, "model-test", run); os.makedirs(od, exist_ok=True)
res = {"run": run, "note": "صورة واحدة خام لكل موديل بلا إعادة ولا ترميم", "models": {}, "rooms": []}
eps = {}
for fam, cands in FAMILIES.items():
    eps[fam] = cands + [c for c in search(SEARCH[fam]) if c not in cands][:3] if fam in SEARCH else cands
for f in rooms:
    sp = json.load(open(f, encoding="utf-8")); rid = os.path.basename(f)[:-5]
    lay = layout_text(sp) + openings_text(sp)
    prompt = "Photorealistic photograph of " + sp["scene_en"].strip() + lay + " View: " + sp.get("view_en", "wide shot from the entrance") + "." + STYLE
    room = {"id": rid, "name": sp.get("space_ar"), "size": f"{sp['room']['w']}×{sp['room']['l']}", "results": {}}
    for fam in FAMILIES:
        r = {"endpoint": None}
        for ep in eps[fam]:
            u, sec = generate(ep, prompt)
            if u: r.update(endpoint=ep, seconds=sec, url=u); break
            if g["BLOCK"]: break
        if g["BLOCK"]: log("fal blocked - stopping"); break
        if r.get("url"):
            fn = f"{rid}__{re.sub(r'[^a-z0-9]+', '-', fam.lower()).strip('-')}.jpg"
            open(os.path.join(od, fn), "wb").write(g["to_jpg"](g["fetch"](r["url"]))); r["file"] = fn
            q, _ = vision(QA + "the main furniture piece", r["url"]); a, _ = vision(ACCURACY + (openings_text(sp) or "not given"), r["url"])
            l, _ = vision(LAYOUT_CHECK + lay, r["url"])
            r["qa"], r["openings"], r["layout"] = q, a, l
            errs = (len((q or {}).get("issues") or []) if (q or {}).get("major_artifacts") else 0) \
                 + (len((a or {}).get("problems") or []) if (a or {}).get("ok") is False else 0) \
                 + (len((l or {}).get("problems") or []) if (l or {}).get("matches") is False else 0)
            r["errors"] = errs; r["photoreal"] = (q or {}).get("photoreal")
        room["results"][fam] = r; log("TEST", rid, fam, json.dumps({k: r.get(k) for k in ("endpoint", "errors", "photoreal", "seconds")}))
    res["rooms"].append(room)
    if g["BLOCK"]: break
for fam in FAMILIES:
    rs = [rm["results"].get(fam, {}) for rm in res["rooms"]]; ok = [x for x in rs if x.get("file")]
    res["models"][fam] = {"images": len(ok), "errors_total": sum(x.get("errors", 0) for x in ok),
                          "photoreal_avg": round(sum(x.get("photoreal") or 0 for x in ok) / len(ok), 1) if ok else None,
                          "endpoint": next((x.get("endpoint") for x in ok), None)}
res["blocked"] = bool(g["BLOCK"]); res["log"] = g["LOG"][-80:]
json.dump(res, open(os.path.join(od, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res["models"], ensure_ascii=False, indent=1))
if g["BLOCK"]: print("::error::fal blocked"); sys.exit(1)
