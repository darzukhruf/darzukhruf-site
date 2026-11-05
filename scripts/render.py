"""HTML/SVG renderers (screenshotted with Playwright): material cards over photos, and the 2D plan slide.
Brand: dark green #14332E background, gold #C2A06B lines/text, sand #F3ECE1 accents."""
import base64, html, math
G, D, S = "#C2A06B", "#14332E", "#F3ECE1"
FONT_CSS = ("<link rel='preconnect' href='https://fonts.googleapis.com'>"
            "<link href='https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap' rel='stylesheet'>")
BASE_CSS = f"""*{{margin:0;padding:0;box-sizing:border-box}} html,body{{width:1080px;height:1440px;overflow:hidden;background:{D}}}
body{{font-family:'Tajawal','DejaVu Sans',sans-serif;direction:rtl}}"""
STAR = ("<svg viewBox='-100 -100 200 200' width='{s}' height='{s}'><g fill='none' stroke='{c}' stroke-width='9'>"
        "<rect x='-58' y='-58' width='116' height='116'/><rect x='-58' y='-58' width='116' height='116' transform='rotate(45)'/></g></svg>")
e = lambda t: html.escape(str(t or ""))

def card_html(photo_bytes, item, point=None, idx=1, total=5):
    b64 = base64.b64encode(photo_bytes).decode()
    sw = item.get("hex") or ""
    swatch = (f"<div class='sw' style='background:{e(sw)}'></div>" if sw else f"<div class='sw ico'>{STAR.format(s=54, c=G)}</div>")
    code = " · ".join(x for x in [item.get("code"), item.get("brand")] if x)
    marker = ""
    if point and 0 <= point[0] <= 1 and 0 <= point[1] <= 1:
        x, y = point[0] * 1080, point[1] * 1440
        y = min(y, 1440 - 420)  # keep marker above the card
        marker = (f"<svg class='mk' width='1080' height='1440'><line x1='{x}' y1='{y}' x2='{x}' y2='{1440-330}' stroke='{G}' stroke-width='2.5' stroke-dasharray='6 6'/>"
                  f"<circle cx='{x}' cy='{y}' r='17' fill='none' stroke='{G}' stroke-width='4'/><circle cx='{x}' cy='{y}' r='6' fill='{G}'/></svg>")
    return f"""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>{FONT_CSS}<style>{BASE_CSS}
.ph{{position:absolute;inset:0;background:url(data:image/jpeg;base64,{b64}) center/cover}}
.mk{{position:absolute;inset:0}}
.top{{position:absolute;top:34px;right:40px;display:flex;align-items:center;gap:12px;color:{S};font-size:30px;font-weight:700;text-shadow:0 2px 10px #0008}}
.pg{{position:absolute;top:40px;left:40px;color:{S};font-size:26px;background:#14332Ecc;border:1.5px solid {G};border-radius:30px;padding:6px 18px}}
.card{{position:absolute;left:40px;right:40px;bottom:44px;background:rgba(20,51,46,.92);border:2px solid {G};border-radius:26px;padding:30px 34px;display:flex;align-items:center;gap:28px}}
.sw{{width:120px;height:120px;border-radius:50%;flex:none;border:4px solid {G};box-shadow:0 0 0 6px rgba(194,160,107,.25)}}
.sw.ico{{display:flex;align-items:center;justify-content:center;background:{D}}}
.tx{{flex:1;min-width:0}} .k{{color:{G};font-size:28px;font-weight:700;letter-spacing:.5px}}
.n{{color:{S};font-size:44px;font-weight:700;line-height:1.25;margin:4px 0}} .c{{color:{S};opacity:.9;font-size:30px;direction:ltr;text-align:right}}
.w{{color:{G};font-size:26px;margin-top:8px}}
</style></head><body><div class='ph'></div>{marker}
<div class='top'>{STAR.format(s=40, c=G)}<span>دار زخرف</span></div><div class='pg'>{idx}/{total}</div>
<div class='card'>{swatch}<div class='tx'><div class='k'>{e(item.get('type_ar'))}</div><div class='n'>{e(item.get('name'))}</div>
<div class='c'>{e(code)}</div><div class='w'>{e(item.get('where_ar'))}</div></div></div></body></html>"""

def plan_html(spec, idx=5, total=5):
    r = spec["room"]; W, L, H = float(r["w"]), float(r["l"]), float(r.get("h", 3.0))
    box = 820; sc = box / max(W, L); ox = (1080 - W * sc) / 2; oy = 330 + (box - L * sc) / 2
    X = lambda m: ox + m * sc; Y = lambda m: oy + (L - m) * sc  # y up in plan meters
    t = 0.2 * sc; parts = []
    parts.append(f"<rect x='{X(0)-t}' y='{Y(L)-t}' width='{W*sc+2*t}' height='{L*sc+2*t}' fill='none' stroke='{G}' stroke-width='4'/>")
    parts.append(f"<rect x='{X(0)}' y='{Y(L)}' width='{W*sc}' height='{L*sc}' fill='none' stroke='{G}' stroke-width='3'/>")
    for o in spec.get("openings", []):
        wall, pos, wd = o.get("wall", "S"), float(o.get("pos", 0)), float(o.get("width", 1))
        if wall in "SN":
            yy = Y(0) if wall == "S" else Y(L); x1, x2 = X(pos), X(pos + wd)
            yo = yy + (t / 2 if wall == "S" else -t / 2)
            parts.append(f"<line x1='{x1}' y1='{yo}' x2='{x2}' y2='{yo}' stroke='{D}' stroke-width='{t+8}'/>")
            if o.get("type") == "door":
                sgn = -1 if wall == "S" else 1
                parts.append(f"<path d='M{x1},{yy} L{x1},{yy+sgn*wd*sc} A{wd*sc},{wd*sc} 0 0 {1 if wall=='S' else 0} {x2},{yy}' fill='none' stroke='{G}' stroke-width='2.5'/>")
            else:
                for d_ in (-t / 3, t / 3):
                    parts.append(f"<line x1='{x1}' y1='{yo+d_}' x2='{x2}' y2='{yo+d_}' stroke='{G}' stroke-width='2.5'/>")
        else:
            xx = X(0) if wall == "W" else X(W); y1, y2 = Y(pos), Y(pos + wd)
            xo = xx + (-t / 2 if wall == "W" else t / 2)
            parts.append(f"<line x1='{xo}' y1='{y1}' x2='{xo}' y2='{y2}' stroke='{D}' stroke-width='{t+8}'/>")
            if o.get("type") == "door":
                sgn = 1 if wall == "W" else -1
                parts.append(f"<path d='M{xx},{y1} L{xx+sgn*wd*sc},{y1} A{wd*sc},{wd*sc} 0 0 {0 if wall=='W' else 1} {xx},{y2}' fill='none' stroke='{G}' stroke-width='2.5'/>")
            else:
                for d_ in (-t / 3, t / 3):
                    parts.append(f"<line x1='{xo+d_}' y1='{y1}' x2='{xo+d_}' y2='{y2}' stroke='{G}' stroke-width='2.5'/>")
    used = []
    for f in spec.get("furniture", []):
        x, y, w, d = (float(f[k]) for k in ("x", "y", "w", "d"))
        rx = 10 if f.get("round") else 4
        parts.append(f"<rect x='{X(x)}' y='{Y(y+d)}' width='{w*sc}' height='{d*sc}' rx='{rx}' fill='none' stroke='{G}' stroke-width='2' opacity='.95'/>")
        if f.get("label_ar") and min(w, d) * sc > 34:
            fs = max(16, min(24, int(min(w, d) * sc / 3.2)))
            rot = " transform='rotate(-90 {cx} {cy})'" if d > w * 1.6 and w * sc < 140 else ""
            cx, cy = X(x + w / 2), Y(y + d / 2)
            if any(abs(cx - a) < 90 and abs(cy - b) < 40 for a, b in used):
                cy = Y(y + d) + fs + 8  # move label to the top edge inside the shape
            used.append((cx, cy))
            parts.append(f"<text x='{cx}' y='{cy}' font-size='{fs}' fill='{G}' text-anchor='middle' dominant-baseline='middle'{rot.format(cx=cx, cy=cy)}>{e(f['label_ar'])}</text>")
    # dimension lines
    dy = Y(0) + t + 46
    parts.append(f"<line x1='{X(0)}' y1='{dy}' x2='{X(W)}' y2='{dy}' stroke='{G}' stroke-width='2'/>")
    for xx in (X(0), X(W)): parts.append(f"<line x1='{xx}' y1='{dy-12}' x2='{xx}' y2='{dy+12}' stroke='{G}' stroke-width='2'/>")
    parts.append(f"<text x='{(X(0)+X(W))/2}' y='{dy-14}' font-size='28' fill='{G}' text-anchor='middle'>{W:.2f} م</text>")
    dx = X(W) + t + 46
    parts.append(f"<line x1='{dx}' y1='{Y(0)}' x2='{dx}' y2='{Y(L)}' stroke='{G}' stroke-width='2'/>")
    for yy in (Y(0), Y(L)): parts.append(f"<line x1='{dx-12}' y1='{yy}' x2='{dx+12}' y2='{yy}' stroke='{G}' stroke-width='2'/>")
    parts.append(f"<text x='{dx+18}' y='{(Y(0)+Y(L))/2}' font-size='28' fill='{G}' text-anchor='middle' transform='rotate(-90 {dx+18} {(Y(0)+Y(L))/2})'>{L:.2f} م</text>")
    # north arrow
    parts.append(f"<g transform='translate(110,1190)'><circle r='34' fill='none' stroke='{G}' stroke-width='2'/><path d='M0,-26 L12,12 L0,4 L-12,12 Z' fill='{G}'/><text y='-44' font-size='22' fill='{G}' text-anchor='middle'>ش</text></g>")
    svg = "<svg class='pl' width='1080' height='1440'>" + "".join(parts) + "</svg>"
    area = W * L
    legend = " · ".join(e(x) for x in spec.get("plan_notes_ar", [])[:3])
    return f"""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>{FONT_CSS}<style>{BASE_CSS}
.pl{{position:absolute;inset:0}} .hd{{position:absolute;top:70px;right:0;left:0;text-align:center;color:{G}}}
.hd .t{{font-size:58px;font-weight:700}} .hd .s{{font-size:28px;margin-top:10px;opacity:.9}}
.ft{{position:absolute;bottom:150px;right:0;left:0;display:flex;justify-content:center;gap:26px;color:{G};font-size:32px;font-weight:500}}
.ft span{{border:2px solid {G};border-radius:40px;padding:10px 26px}}
.lg{{position:absolute;bottom:96px;right:60px;left:60px;text-align:center;color:{G};font-size:24px;opacity:.85}}
.br{{position:absolute;bottom:34px;left:0;right:0;display:flex;justify-content:center;align-items:center;gap:12px;color:{G};font-size:26px}}
.pg{{position:absolute;top:40px;left:40px;color:{G};font-size:26px;border:1.5px solid {G};border-radius:30px;padding:6px 18px}}
</style></head><body>{svg}<div class='pg'>{idx}/{total}</div>
<div class='hd'><div class='t'>{e(spec.get('title_ar'))}</div><div class='s'>مخطط توضيحي · الأبعاد بالمتر</div></div>
<div class='ft'><span>المساحة {area:.1f} م²</span><span>الارتفاع {H:.2f} م</span></div>
<div class='lg'>{legend}</div><div class='br'>{STAR.format(s=30, c=G)}<span>دار زخرف · تصميم مقترح</span></div></body></html>"""
