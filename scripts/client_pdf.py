"""Client delivery PDF (Arabic, A4 landscape) for paid-client designs — never published.
Pages: cover (hero) · extra views · 2D plan · colour & material board · shopping list (dated prices, 30-day validity,
total vs budget, cheaper alternative) · contractor notes (walls, lighting, electrical points) · closing page
(proposed design disclaimer, revisions left, how to ask for a revision).
Every section is optional except the cover: missing spec fields are skipped, never invented."""
import base64, html, os, datetime as dt
from render import FONT_CSS

G, D, S = "#C2A06B", "#14332E", "#F4EFE6"
e = lambda s: html.escape(str(s if s is not None else ""))

def _img(path):
    return "data:image/jpeg;base64," + base64.b64encode(open(path, "rb").read()).decode()

def _num(v):
    try: return float(str(v).replace(",", "").replace("ريال", "").strip())
    except Exception: return None

CSS = f"""@page{{size:A4 landscape;margin:0}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Tajawal','Noto Naskh Arabic','Noto Sans Arabic','DejaVu Sans',sans-serif;direction:rtl;color:{D};background:#fff}}
.pg{{width:297mm;height:210mm;padding:12mm 14mm;position:relative;page-break-after:always;overflow:hidden}}
.pg:last-child{{page-break-after:auto}}
h1{{font-size:30pt;color:{D}}} h2{{font-size:20pt;color:{D};border-bottom:2px solid {G};padding-bottom:3mm;margin-bottom:5mm}}
.sub{{color:{G};font-size:13pt;margin-top:2mm}}
.ft{{position:absolute;bottom:6mm;right:14mm;left:14mm;display:flex;justify-content:space-between;font-size:9pt;color:#777}}
.cover{{background:{D};color:{S};display:flex;gap:10mm;align-items:center}}
.cover h1{{color:{S}}} .cover .ph{{height:180mm;border:2px solid {G}}}
.cover .tx{{flex:1}} .cover .lb{{color:{G};font-size:12pt;margin-top:8mm;line-height:1.8}}
.full{{display:flex;justify-content:center;align-items:center;height:165mm}} .full img{{max-height:165mm;max-width:100%;border:1px solid #ddd}}
.two{{display:flex;gap:6mm;justify-content:center}} .two img{{max-height:160mm;max-width:49%;border:1px solid #ddd}}
table{{width:100%;border-collapse:collapse;font-size:10.5pt}} th{{background:{D};color:{S};padding:2.2mm;text-align:right}}
td{{border-bottom:1px solid #e3dccf;padding:2mm;vertical-align:top}} tr:nth-child(even) td{{background:#faf7f1}}
.c{{direction:ltr;unicode-bidi:isolate}} .tot td{{font-weight:700;background:#f3ead9!important}}
.note{{font-size:10pt;color:#555;margin-top:3mm;line-height:1.7}}
.cols{{display:flex;gap:8mm}} .cols>div{{flex:1}} ul{{padding-right:6mm;line-height:1.9;font-size:11pt}}
.box{{border:1.5px solid {G};border-radius:3mm;padding:6mm;margin-top:5mm;line-height:2;font-size:12.5pt}}"""

def _foot(title, n):
    return f"<div class='ft'><span>دار زخرف · Dar Zukhruf — تصميم مقترح · وثيقة العمل الحر FL-271313510</span><span>{e(title)}</span><span>{n}</span></div>"

def build_pdf(page, spec, out_dir, files, views, mats, pdf_path):
    """files = [hero, board, plan?] relative to out_dir; views = extra view files. Returns pdf_path or None."""
    t = spec.get("title_ar") or "تصميم مقترح"; today = dt.date.today()
    P = lambda f: os.path.join(out_dir, f); pages = []; n = 0
    def add(body, cls=""):
        nonlocal n; n += 1; pages.append(f"<section class='pg {cls}'>{body}{_foot(t, n)}</section>")
    client = spec.get("client_name_ar", "")
    po = bool(spec.get("plan_only"))
    cover_img = "" if po else f"<img class='ph' src='{_img(P(files[0]))}'>"
    add(f"{cover_img}<div class='tx'><div class='sub'>دار زخرف · ملف التصميم</div><h1>{e(t)}</h1>"
        f"<div class='lb'>{('للعميل: ' + e(client) + '<br>') if client else ''}المساحة: {e(spec.get('space_ar'))} · "
        f"{e(spec['room']['w'])}×{e(spec['room']['l'])} م · ارتفاع {e(spec['room'].get('h', 3))} م<br>"
        f"النمط: {e(spec.get('style_ar'))}<br>الألوان: {e(spec.get('palette_ar'))}<br>تاريخ الإصدار: {today:%Y-%m-%d}"
        f"{'<br>المحتوى: مخطط توزيع بالمقاسات · لوحة ألوان وخامات بأكوادها · قائمة مشتريات · ملاحظات المقاول' if po else ''}</div></div>", "cover")
    for i in range(0, len(views), 2):
        imgs = "".join(f"<img src='{_img(P(v))}'>" for v in views[i:i + 2])
        add(f"<h2>زوايا إضافية لنفس التصميم</h2><div class='two'>{imgs}</div>")
    plan = next((f for f in files if f.endswith("_plan.jpg")), None)
    if plan:
        notes = "".join(f"<li>{e(x)}</li>" for x in spec.get("plan_notes_ar", []))
        add(f"<h2>المخطط 2D وتوزيع الأثاث</h2><div class='cols'><div class='full' style='flex:1.4'><img src='{_img(P(plan))}'></div>"
            f"<div><ul>{notes}</ul><div class='note'>المقاسات بالمتر. الشمال حسب السهم في المخطط. راجع المقاسات في الموقع قبل التصنيع.</div></div></div>")
    board = next((f for f in files if "_board" in f), None)
    rows = "".join(f"<tr><td>{e(m.get('type_ar'))}</td><td>{e(m.get('name'))}</td><td class='c'>{e(m.get('code'))}</td>"
                   f"<td>{e(m.get('brand'))}</td><td>{e(m.get('where_ar'))}</td></tr>" for m in mats)
    add(f"<h2>لوحة الألوان والخامات</h2><div class='cols'><div class='full' style='flex:1'>"
        f"{('<img src=' + chr(39) + _img(P(board)) + chr(39) + '>') if board else ''}</div><div style='flex:1.2'>"
        f"<table><tr><th>العنصر</th><th>الاسم</th><th>الكود</th><th>الماركة</th><th>وين تلقاه</th></tr>{rows}</table>"
        f"<div class='note'>الألوان تقريبية وتختلف حسب الإضاءة والشاشة — اطلب عينة من الوكيل قبل الدهان.</div></div></div>")
    shop = spec.get("shopping") or []
    if shop:
        tot, body, chunks = 0.0, "", []
        for k, it in enumerate(shop):
            if k and k % 10 == 0: chunks.append(body); body = ""
            q = _num(it.get("qty")) or 1; p = _num(it.get("price"))
            line = (p * q) if p is not None else None
            if line: tot += line
            body += (f"<tr><td>{e(it.get('item_ar'))}</td><td class='c'>{e(it.get('size'))}</td><td>{e(it.get('qty', 1))}</td>"
                     f"<td>{e(it.get('supplier_ar'))}</td><td>{('{:,.0f}'.format(line)) if line else 'عند المورد'}</td><td>{e(it.get('alt_ar', ''))}</td></tr>")
        budget = spec.get("budget_ar", "")
        body += f"<tr class='tot'><td colspan='4'>الإجمالي التقريبي للبنود المسعّرة</td><td>{tot:,.0f} ريال</td><td>{('ميزانيتك: ' + e(budget)) if budget else ''}</td></tr>"
        chunks.append(body); hdr = "<tr><th>القطعة</th><th>المقاس</th><th>الكمية</th><th>المورد المقترح</th><th>السعر التقريبي</th><th>بديل أوفر</th></tr>"
        for k, ch in enumerate(chunks[:-1]):
            add(f"<h2>قائمة المشتريات ({k + 1}/{len(chunks)})</h2><table>{hdr}{ch}</table><div class='note'>يتبع في الصفحة التالية.</div>")
        ttl = "قائمة المشتريات" + (f" ({len(chunks)}/{len(chunks)})" if len(chunks) > 1 else "")
        add(f"<h2>{ttl}</h2><table>{hdr}{chunks[-1]}</table>"
            f"<div class='note'>الأسعار تقريبية بتاريخ {today:%Y-%m-%d} وصالحة كمرجع 30 يوماً (حتى {today + dt.timedelta(days=30):%Y-%m-%d})؛ "
            f"تأكد من السعر والتوفر عند المورد. لا نبيع ولا نستلم أي مبلغ عن المشتريات — الاختيار لك.</div>")
    walls, light, elec, cn = spec.get("walls_ar") or {}, spec.get("lighting_ar") or [], spec.get("electrical_ar") or [], spec.get("contractor_notes_ar") or []
    if walls or light or elec or cn:
        WN = {"N": "الجدار الشمالي", "S": "الجدار الجنوبي", "E": "الجدار الشرقي", "W": "الجدار الغربي"}
        wr = "".join(f"<tr><td>{WN.get(k, e(k))}</td><td>{e(v)}</td></tr>" for k, v in walls.items())
        add("<h2>ملاحظات المقاول</h2><div class='cols'><div>"
            + (f"<table><tr><th>الجدار</th><th>المطلوب عليه (بالمقاسات)</th></tr>{wr}</table>" if wr else "")
            + ("<ul>" + "".join(f"<li>{e(x)}</li>" for x in cn) + "</ul>" if cn else "") + "</div><div>"
            + ("<b>الإضاءة</b><ul>" + "".join(f"<li>{e(x)}</li>" for x in light) + "</ul>" if light else "")
            + ("<b>نقاط الكهرباء</b><ul>" + "".join(f"<li>{e(x)}</li>" for x in elec) + "</ul>" if elec else "")
            + "</div></div><div class='note'>تصميم فقط: التنفيذ والقياس النهائي والتمديدات مسؤولية المقاول المرخّص.</div>")
    rev = spec.get("revisions_left", 2)
    add(f"<h2>قبل لا تبدأ</h2><div class='box'>• هذا <b>تصميم مقترح</b>، "
        + ("والمخطط ولوحة الألوان توضيحية للفكرة، وكل المقاسات تُراجع في الموقع قبل التنفيذ." if po else "والصور توضيحية للفكرة وليست صور مشروع منفّذ.")
        + "<br>"
        f"• الألوان تقريبية وتختلف حسب الإضاءة والشاشة.<br>• التعديلات المتبقية لك: <b>{e(rev)}</b>.<br>"
        f"• لطلب تعديل: أرسل لنا واتساب ملاحظاتك في رسالة وحدة (وش تغيّر ووين)، ويوصلك التعديل خلال يومي عمل تقريباً.<br>"
        f"• واتساب: <span class='c'>0578771717</span></div>")
    doc = f"<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>{FONT_CSS}<style>{CSS}</style></head><body>{''.join(pages)}</body></html>"
    page.set_content(doc, wait_until="networkidle", timeout=60000)
    try: page.evaluate("document.fonts && document.fonts.ready")
    except Exception: pass
    page.pdf(path=pdf_path, format="A4", landscape=True, print_background=True)
    return pdf_path
