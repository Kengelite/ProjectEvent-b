"""Build a Thai PDF that explains a staged batch folder and the diagram error of every fail model.

    python tools/make_batch_report.py [--batch all_197]

Reads batches/<batch>/<NN_topic>/{pass,fail}/<Case>/ (meta.json, _EventB.txt, .drawio.xml) and
writes batches/<batch>/README_<batch>.pdf (HTML rendered by headless Chrome).
"""
import argparse, glob, html, json, os, re, subprocess, tempfile

DATASET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

FAMILY = {"inverted1": "A", "inverted2": "A", "inverted3": "A", "inverted_frame": "A",
          "mod_alt": "B", "mod_opt": "B", "mod_inverted": "A+B"}
FAMILY_TH = {"A": "A. ช่วงเวลากลับด้าน", "B": "B. mod กับตัวนับ loop", "A+B": "A + B"}
CATEGORY_TH = {"model_error": "โมเดลผิดจริง", "non_inductive": "ค่าจริงถูก แต่พิสูจน์ไม่ได้"}
# summary table: (what is wrong in the diagram, which PO fails and why)
TYPE_TH = {
    "inverted1": ("ช่วงเวลา {a..b} ของ message 1 ตัวเขียนกลับด้าน (a > b)",
                  "สูตรแปลงได้ t_time :∈ a..b ซึ่งไม่มีค่าให้เลือก → FIS ล้ม 1 ข้อ"),
    "inverted2": ("เหมือน inverted1 แต่กลับด้าน 2 message", "FIS ล้ม 2 ข้อ"),
    "inverted3": ("เหมือน inverted1 แต่กลับด้าน 3 message", "FIS ล้ม 3 ข้อ"),
    "inverted_frame": ("ช่วงเวลากลับด้านบน message ที่อยู่ใน fragment (loop / alt / opt / par)",
                       "FIS ล้ม 1 ข้อ — fragment ไม่ได้เปลี่ยนผล"),
    "mod_alt": ("alt ใช้เงื่อนไข [c mod k == 0] / [c mod k != 0] กับตัวนับ loop c",
                "c mod k ต้องมี c ≥ 0 แต่สูตรแปลงให้แค่ c ∈ ℤ → WD ล้มทุก guard ที่มี mod"),
    "mod_opt": ("opt ใช้เงื่อนไข [c mod k == 0] กับตัวนับ loop c", "เหตุผลเดียวกับ mod_alt"),
    "mod_inverted": ("มีทั้งช่วงเวลากลับด้าน 1 จุด และเงื่อนไข mod กับตัวนับ loop", "FIS ล้ม 1 ข้อ + WD ล้ม"),
}
SHOW = 4          # longest list of lines / POs printed in full on a card


def esc(s):
    return html.escape(str(s))


def c(s):
    return f"<code>{esc(s)}</code>"


def find_line(lines, pattern, start=0, end=None):
    for i in range(start, len(lines) if end is None else end):
        if pattern(lines[i]):
            return i
    return None


def block(lines, header):
    s = find_line(lines, lambda l: l.strip() == header)
    e = find_line(lines, lambda l: l.strip() == "END", s + 1)
    return s, e


def diagram_texts(xml):
    return [html.unescape(v) for v in re.findall(r'value="([^"]*)"', xml)]


def inverted_labels(xml):
    out = []
    for v in diagram_texts(xml):
        m = re.search(r"\{(\d+)\.\.(\d+)\}", v)
        if m and int(m.group(1)) > int(m.group(2)):
            out.append((v, m.group(1), m.group(2)))
    return out


def mod_frame(xml):
    """(mod condition boxes, enclosing loop condition box) as written in the diagram."""
    texts = diagram_texts(xml)
    mods = [t for t in texts if " mod " in t]
    if not mods:
        return [], None
    var = re.match(r"\[(\w+) mod", mods[0]).group(1)
    loop = next(t for t in texts if re.fullmatch(rf"\[{var} < \d+\]", t))
    return mods, loop


def changed_lines(txt):
    """[(line number, text)] in _EventB.txt produced by the diagram error."""
    lines, out = txt.split("\n"), []
    s, e = block(lines, "INITIALISATION BEGIN")
    for i in range(s, e):
        m = re.search(r":∈ (\d+)\.\.(\d+)", lines[i])
        if m and int(m.group(1)) > int(m.group(2)):
            out.append(i)
    out += [i for i, l in enumerate(lines) if re.match(r"^\s+grd\d+: .* mod \d+", l)]
    return [(i + 1, lines[i].strip()) for i in out]


def po_detail(txt, po):
    """Formula behind a PO: the invariant for INV, the action for FIS, the guard for WD."""
    ev, label, kind = po.split("/")
    lines = txt.split("\n")
    if kind == "INV":
        i = find_line(lines, lambda l: l.strip().startswith(f"{label}: ") and re.match(r"^ {4}inv", l))
        return lines[i].strip() if i is not None else ""
    s, e = block(lines, "INITIALISATION BEGIN" if ev == "INITIALISATION" else ev)
    i = find_line(lines, lambda l: l.strip().startswith(f"{label}: "), s, e)
    return lines[i].strip() if i is not None else ""


def explain(r):
    """(what is wrong in the diagram, why the PO fails) for one fail model."""
    xml = r["xml"]
    what, why = [], []
    labs = inverted_labels(xml)
    if labs:
        what.append("ช่วงเวลากลับด้าน: " + ", ".join(c(l[0]) for l in labs))
        why.append("; ".join(f"สูตรแปลงได้ {c(f':∈ {l[1]}..{l[2]}')} ซึ่งไม่มีค่าให้เลือก ({l[1]} > {l[2]})" for l in labs)
                   + " → FIS ล้ม")
    mods, loop = mod_frame(xml)
    if mods:
        var, k = re.match(r"\[(\w+) mod (\d+)", mods[0]).groups()
        kind = "alt" if len(mods) == 2 else "opt"
        what.append(f"{kind} ใช้เงื่อนไข " + " / ".join(c(t) for t in mods) + f" กับตัวนับของ loop {c(loop)}")
        why.append(f"สูตรแปลงใส่เงื่อนไขนี้เป็น guard ของทุก event ใน {kind} "
                   f"แต่ {c(f'{var} mod {k}')} คำนวณได้เมื่อ {c(f'{var} ≥ 0')} เท่านั้น (WD) "
                   f"สูตรแปลงสร้างแค่ {c(f'{var} ∈ ℤ')} — ค่าจริงเริ่มที่ 0 และเพิ่มทีละ 1 จึงไม่ติดลบ "
                   "แต่ไม่มี invariant บอก prover → WD ล้มทุก guard ที่มี mod")
    return "<br>".join(what), "<br>".join(why)


def shorten(items, extra):
    if len(items) <= SHOW:
        return "<br>".join(items)
    return "<br>".join(items[:SHOW - 1]) + f"<br><span class='ln'>… และอีก {len(items) - SHOW + 1} {extra}</span>"


def collect(bdir):
    rows = []
    for p in sorted(glob.glob(os.path.join(bdir, "*", "*", "*", "meta.json"))):
        d = os.path.dirname(p)
        topic_dir, result = d.split(os.sep)[-3:-1]
        meta = json.load(open(p))
        case = meta["case"]
        rows.append({"topic_dir": topic_dir, "result": result, "meta": meta,
                     "txt": open(os.path.join(d, f"{case}_EventB.txt")).read(),
                     "xml": open(os.path.join(d, f"{case}.drawio.xml")).read(),
                     "rel": os.path.relpath(d, bdir)})
    return rows


CSS = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: "Thonburi", "Sukhumvit Set", sans-serif; font-size: 10.5pt; color: #1d2433; line-height: 1.55; margin: 0; }
h1 { font-size: 21pt; margin: 0 0 4px; color: #12325c; }
h2 { font-size: 14.5pt; color: #12325c; border-bottom: 2px solid #12325c; padding-bottom: 3px; margin: 22px 0 10px; break-after: avoid; }
h3 { font-size: 12pt; margin: 16px 0 6px; color: #12325c; break-after: avoid; }
p { margin: 6px 0; }
.sub { color: #5a6475; margin-bottom: 14px; }
code, .mono { font-family: "Menlo", monospace; font-size: 8.6pt; }
pre { font-family: "Menlo", monospace; font-size: 8.4pt; background: #f4f6fa; border: 1px solid #dde3ec; border-radius: 4px; padding: 8px 10px; margin: 6px 0; white-space: pre; line-height: 1.45; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 9.4pt; }
th, td { border: 1px solid #cfd6e1; padding: 3px 6px; text-align: left; vertical-align: top; }
th { background: #e8edf5; }
td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr { break-inside: avoid; }
.note { background: #fff7e0; border-left: 4px solid #e0a800; padding: 6px 10px; margin: 8px 0; }
.card { border: 1px solid #cfd6e1; border-left: 4px solid #c0392b; border-radius: 4px; padding: 7px 10px; margin: 8px 0; break-inside: avoid; }
.card .hd { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.card .name { font-weight: bold; font-size: 11pt; }
.card .tag { font-size: 8.6pt; color: #5a6475; white-space: nowrap; }
.card .path { font-family: "Menlo", monospace; font-size: 7.8pt; color: #5a6475; }
.card dl { display: grid; grid-template-columns: 82px 1fr; gap: 3px 8px; margin: 5px 0 0; }
.card dt { color: #5a6475; }
.card dd { margin: 0; }
.ln { color: #8a93a3; }
.po { color: #a8281c; }
.names { columns: 3; column-gap: 18px; font-size: 9.6pt; margin: 4px 0 8px; }
"""


def render(batch, rows):
    n_pass = sum(r["result"] == "pass" for r in rows)
    n_fail = len(rows) - n_pass
    topics = sorted({r["topic_dir"] for r in rows})
    fails = [r for r in rows if r["result"] == "fail"]
    h = [f"<h1>ชุดโมเดล {esc(batch)}</h1>",
         f"<div class='sub'>{len(rows)} โมเดล · pass {n_pass} / fail {n_fail} · {len(topics)} หัวข้อ · ยังไม่ได้รัน Rodin</div>"]

    old = [r for r in rows if "model_id" in r["meta"]]
    redone = [r for r in old if "round1_version" in r["meta"]]
    h.append("<h2>1. ภาพรวม</h2>")
    if old:
        h.append(f"<p>รวมทุกโมเดลไว้ที่เดียว: <b>รอบแรก {len(old)} ตัว</b> (model_002–048, ใช้ ID เดิม; "
                 f"แก้ใหม่ {len(redone)} ตัว ดูข้อ 6) + <b>ชุดใหม่ {len(rows) - len(old)} ตัว</b> (batch_02–04) "
                 "— model_001 (Payment) เก็บไว้ทดสอบ ไม่ได้อยู่ในชุดนี้</p>")
    h.append(f"<p>แต่ละตัวเริ่มจาก sequence diagram "
             "แล้วแปลงเป็น Event-B ด้วย ChronoSeq-B <b>โดยไม่แก้ Event-B ภายหลัง</b> "
             "(เอา diagram ไปแปลงใหม่จะได้ไฟล์เดิมทุกตัวอักษร)</p>")
    h.append("<ul><li><b>pass</b> — diagram ถูก</li>"
             "<li><b>fail</b> — diagram มีจุดผิดที่ตั้งใจใส่ไว้ ทำให้ Event-B ที่แปลงออกมามี PO ที่พิสูจน์ไม่ได้</li></ul>")
    h.append("<div class='note'><b>pass / fail ในชุดนี้คือผลที่ออกแบบไว้ ยังไม่ใช่ผลจาก Rodin</b><br>"
             "ผลจริงได้หลังรัน Rodin (ML/PP) และจะอยู่ใน <code>by_result/</code></div>")

    h.append("<h2>2. โครงสร้าง folder</h2>")
    tree = [f"batches/{batch}/",
            f"├── README_{batch}.pdf            ← ไฟล์นี้",
            f"├── Rodin_Import_{batch}.zip      ← import เข้า Rodin ครั้งเดียว ครบ {len(rows)} project",
            "├── 01_การเงินและการชำระเงิน/       ← หัวข้อ",
            "│   ├── pass/",
            "│   │   └── <ชื่อโมเดล>/",
            "│   │       ├── <ชื่อโมเดล>.drawio.xml",
            "│   │       ├── <ชื่อโมเดล>_EventB.txt",
            "│   │       ├── <ชื่อโมเดล>_Rodin.zip",
            "│   │       └── meta.json",
            "│   └── fail/",
            "├── 02_สุขภาพและการแพทย์/",
            f"└── ... (รวม {len(topics)} หัวข้อ)"]
    h.append("<pre>" + esc("\n".join(tree)) + "</pre>")
    h.append("<table><tr><th>ไฟล์</th><th>คืออะไร</th></tr>"
             "<tr><td><code>.drawio.xml</code></td><td>sequence diagram (ของ fail มีจุดผิดอยู่ในนี้)</td></tr>"
             "<tr><td><code>_EventB.txt</code></td><td>Event-B ที่ได้จากสูตรแปลง = input ของ LLM</td></tr>"
             "<tr><td><code>_Rodin.zip</code></td><td>Rodin project ของโมเดลนี้</td></tr>"
             "<tr><td><code>meta.json</code></td><td>pass/fail ที่ออกแบบ, จุดผิด, PO ที่คาดว่าจะล้ม — "
             "<b>ห้ามใช้เป็น input ของ LLM</b> เพราะมีเฉลย</td></tr>"
             f"<tr><td><code>Rodin_Import_{esc(batch)}.zip</code></td><td>ทุก project ในไฟล์เดียว "
             "(Rodin: File → Import → Existing Projects into Workspace → Select archive file)</td></tr></table>")
    h.append("<h3>ขั้นตอนต่อไป</h3><ol>"
             f"<li>import <code>Rodin_Import_{esc(batch)}.zip</code> ในเครื่องที่มี Rodin + Atelier B (ML/PP)</li>"
             "<li>รอ auto-prover จนครบ แล้ว zip workspace ส่งกลับ</li>"
             f"<li>รัน <code>python tools/generators/integrate_batch.py --batch {esc(batch)} --workspace &lt;workspace&gt;</code> "
             f"→ รอบแรกแทนที่ ID เดิม ชุดใหม่ได้ model_049–model_{48 + len(rows) - len(old):03d} "
             "พร้อม label และ by_result/</li></ol>")

    h.append("<h2>3. จำนวนตามหัวข้อ</h2><table><tr><th>หัวข้อ</th><th>pass</th><th>fail</th><th>รวม</th></tr>")
    for t in topics:
        p = sum(r["topic_dir"] == t and r["result"] == "pass" for r in rows)
        f = sum(r["topic_dir"] == t and r["result"] == "fail" for r in rows)
        h.append(f"<tr><td>{esc(t)}</td><td class='n'>{p}</td><td class='n'>{f}</td><td class='n'>{p + f}</td></tr>")
    h.append(f"<tr><th>รวม</th><th class='n'>{n_pass}</th><th class='n'>{n_fail}</th><th class='n'>{len(rows)}</th></tr></table>")

    h.append("<h2>4. อ่านชื่อ PO</h2>")
    h.append("<p>รูปแบบ <code>&lt;event&gt;/&lt;label&gt;/&lt;ชนิด&gt;</code></p><table>"
             "<tr><th>ชนิด</th><th>ต้องพิสูจน์ว่า</th><th>ตัวอย่าง</th></tr>"
             "<tr><td><code>INV</code></td><td>หลัง event ทำงาน invariant ยังจริง</td><td><code>receiveX_3/inv5/INV</code></td></tr>"
             "<tr><td><code>FIS</code></td><td>action <code>:∈</code> มีค่าให้เลือกอย่างน้อย 1 ค่า</td><td><code>INITIALISATION/act10/FIS</code></td></tr>"
             "<tr><td><code>WD</code></td><td>สูตรใน guard คำนวณได้ เช่น <code>a mod b</code> ต้องมี a ≥ 0 และ b &gt; 0</td><td><code>sendX_4/grd5/WD</code></td></tr></table>")

    h.append("<h2>5. diagram ผิดแบบไหนทำให้ PO ล้ม</h2>")
    h.append("<p>สูตรแปลงสร้าง invariant แค่ 2 แบบ คือ ชนิดข้อมูล (<code>x ∈ ℤ</code>, <code>⊆</code>) และ "
             "<code>inv5: receivedMessages ⊆ sentMessages</code> ซึ่งสูตรใส่ guard รองรับให้เองเสมอ "
             "<b>INV จึงไม่ล้มไม่ว่าวาด diagram แบบไหน</b> จุดใน diagram ที่ทำให้ PO ล้มได้มี 2 แบบ:</p>")
    h.append("<table><tr><th style='width:16%'>กลุ่ม</th><th>เขียนใน diagram</th><th>สูตรแปลงได้</th><th>PO ที่ล้ม</th></tr>"
             "<tr><td>A. ช่วงเวลากลับด้าน</td><td><code>notify() {5..3}</code></td><td><code>t_time_i :∈ 5..3</code></td>"
             "<td><b>FIS</b> — ไม่มีค่าให้เลือก (โมเดลผิดจริง)</td></tr>"
             "<tr><td>B. mod กับตัวนับ loop</td><td>loop <code>[retryNo &lt; 5]</code> + alt/opt <code>[retryNo mod 2 == 0]</code></td>"
             "<td>guard <code>retryNo mod 2 = 0</code> + invariant แค่ <code>retryNo ∈ ℤ</code></td>"
             "<td><b>WD</b> — ต้องรู้ว่า retryNo ≥ 0 (ค่าจริงถูก แต่พิสูจน์ไม่ได้)</td></tr></table>")
    h.append("<table><tr><th>ชนิด</th><th>กลุ่ม</th><th>จุดผิดใน diagram</th><th>ผล</th><th>จำนวน</th></tr>")
    for t, (what, why) in TYPE_TH.items():
        n = sum(r["meta"].get("mutation_type") == t for r in fails)
        if n:
            h.append(f"<tr><td><code>{t}</code></td><td>{FAMILY[t]}</td><td>{esc(what)}</td><td>{esc(why)}</td><td class='n'>{n}</td></tr>")
    h.append("</table>")

    if redone:
        h.append("<h2>6. รอบแรก: ตัวที่แก้ใหม่</h2>")
        h.append("<p>รอบแรกมี 21 ตัวที่ Event-B ไม่ได้มาจาก diagram ตรง ๆ (แก้ Event-B หลังแปลง หรือเติม invariant เอง) "
                 "ตอนนี้แก้ให้ทุกตัวเป็นผลของสูตรแปลงแล้ว ของเดิมเก็บไว้ที่ "
                 "<code>archive/round1_post_conversion_edits/</code></p>")
        h.append("<table><tr><th>ID</th><th>โมเดล</th><th>เดิม</th><th>ตอนนี้</th></tr>")
        for r in sorted(redone, key=lambda r: r["meta"]["model_id"]):
            m = r["meta"]
            before = m["round1_version"].replace(" (archived)", "")
            now = (f"fail: <code>{esc(m['mutation_type'])}</code> (จุดผิดใน diagram)"
                   if m["design_intent"] == "expected_fail" else "pass: แปลงจาก diagram ตรง ๆ")
            h.append(f"<tr><td>{esc(m['model_id'])}</td><td>{esc(m['case'])}</td>"
                     f"<td class='mono'>{esc(before)}</td><td>{now}</td></tr>")
        h.append("</table>")
    n_sec = 7 if redone else 6
    h.append(f"<h2>{n_sec}. จุดผิดของโมเดล fail ทีละตัว</h2>")
    h.append("<p><b>ใน diagram</b> = ข้อความที่ผิดใน .drawio.xml · <b>ใน Event-B</b> = บรรทัดที่ได้จากจุดนั้นใน _EventB.txt</p>")
    for t in topics:
        group = sorted((r for r in fails if r["topic_dir"] == t), key=lambda r: r["meta"]["case"].lower())
        if not group:
            continue
        h.append(f"<h3>{esc(t)} ({len(group)})</h3>")
        for r in group:
            m = r["meta"]
            mt = m["mutation_type"]
            what, why = explain(r)
            lines = shorten([f"<span class='ln'>บรรทัด {n}</span> <span class='mono'>{esc(s)}</span>"
                             for n, s in changed_lines(r["txt"])], "บรรทัด")
            pos = shorten([f"<span class='mono po'>{esc(po)}</span> <span class='mono'>— {esc(po_detail(r['txt'], po))}</span>"
                           for po in m["expected_failed_pos"]], "ข้อ")
            h.append(
                "<div class='card'><div class='hd'>"
                f"<span class='name'>{esc(m['case'])}"
                + (f" <span class='ln'>{esc(m['model_id'])}</span>" if "model_id" in m else "") + "</span>"
                f"<span class='tag'>{esc(CATEGORY_TH[m['category']])} · {esc(FAMILY_TH[FAMILY[mt]])} · <code>{esc(mt)}</code></span></div>"
                f"<div class='path'>{esc(r['rel'])}/</div><dl>"
                f"<dt>ใน diagram</dt><dd>{what}</dd>"
                f"<dt>ใน Event-B</dt><dd>{lines}</dd>"
                f"<dt>PO ที่ล้ม ({m['expected_failed_count']})</dt><dd>{pos}</dd>"
                f"<dt>ทำไม</dt><dd>{why}</dd></dl></div>")

    h.append(f"<h2>{n_sec + 1}. โมเดล pass</h2>")
    h.append("<p>diagram ถูก ไม่มีช่วงเวลากลับด้าน และไม่มี mod — Event-B คือผลของสูตรแปลงตรง ๆ</p>")
    for t in topics:
        names = sorted((r["meta"]["case"] for r in rows if r["topic_dir"] == t and r["result"] == "pass"), key=str.lower)
        h.append(f"<h3>{esc(t)} ({len(names)})</h3><div class='names'>" + "<br>".join(esc(n) for n in names) + "</div>")
    return f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(h)}</body></html>"


def main(batch):
    bdir = os.path.join(DATASET, "batches", batch)
    rows = collect(bdir)
    for r in rows:
        m = r["meta"]
        if r["result"] == "fail":
            assert changed_lines(r["txt"]) and all(explain(r)), m["case"]
            assert all(po_detail(r["txt"], po) for po in m["expected_failed_pos"]), m["case"]
        else:
            assert not changed_lines(r["txt"]) and not inverted_labels(r["xml"]), m["case"]
    out = os.path.join(bdir, f"README_{batch}.pdf")
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "report.html")
        open(page, "w").write(render(batch, rows))
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", f"file://{page}"], check=True, capture_output=True)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="all_197")
    main(ap.parse_args().batch)
