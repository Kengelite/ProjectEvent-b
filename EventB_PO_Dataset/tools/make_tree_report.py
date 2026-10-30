"""TREES.pdf: how the event tree and guard tree are extracted, and the codes of every model.

Called by make_release.py after extract_trees.py has written models/<id>/tree.json.
"""
import json, os, subprocess, sys, tempfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from categorize import TOPIC_NAMES                               # noqa: E402
from extract_trees import draw, draw_events_compact              # noqa: E402
from make_batch_report import CHROME, CSS, esc                   # noqa: E402

EXTRA_CSS = """
pre.tree { font-family: Menlo, monospace; font-size: 8pt; line-height: 1.35; background: #f6f8fb; border: 1px solid #dfe5ee;
           border-radius: 5px; padding: 6px 9px; margin: 4px 0; white-space: pre; overflow: hidden; }
.model { break-inside: avoid; border-top: 1.5px solid #cfd6e1; padding-top: 5px; margin-top: 10px; }
.model h4 { margin: 0 0 3px; font-size: 10.4pt; color: #12325c; }
.model h4 .res-pass { color: #2e7d5b; } .model h4 .res-fail { color: #c0392b; }
.cols { display: grid; grid-template-columns: minmax(0, 42fr) minmax(0, 58fr); gap: 10px; }
.cols .lbl { font-size: 8.4pt; color: #5a6475; font-weight: bold; margin-top: 2px; }
table.codes { font-size: 8.2pt; margin: 2px 0 4px; } table.codes td { padding: 1px 6px; line-height: 1.3; }
table.codes td.k { font-family: Menlo, monospace; font-weight: bold; color: #2f5fa8; width: 34px; }
table.ev { font-size: 7.6pt; } table.ev th { font-size: 7.6pt; padding: 1px 6px; }
table.ev td { font-family: Menlo, monospace; overflow-wrap: anywhere; padding: 0 6px; line-height: 1.3; } table.ev td.g { color: #5a6475; width: 22%; }
.paths { font-family: Menlo, monospace; font-size: 7.6pt; line-height: 1.4; overflow-wrap: normal; word-break: normal; }
.none { color: #8a93a3; font-size: 8.6pt; }
.rule { border-left: 4px solid #2f5fa8; background: #eef3fb; padding: 6px 10px; margin: 6px 0; }
.rule ul { margin: 3px 0 0; padding-left: 18px; } .rule li { margin: 1px 0; }
"""


def guard_block(t):
    gc = t["guard_codes"]
    if not gc:
        return "<div class='none'>ไม่มีเงื่อนไขจากแผนภาพ</div>"
    rows = "".join(f"<tr><td class='k'>{c}</td><td>{esc(g)}</td></tr>" for c, g in gc.items())
    tree = "\n".join(["(root)"] + draw(t["guard_tree"], lambda c: f"{c}  {gc[c]}"))
    return (f"<table class='codes'>{rows}</table><pre class='tree'>{esc(tree)}</pre>"
            "<div class='lbl'>เส้นทาง</div><div class='paths'>" + "<br>".join(path_html(p) for p in t["guard_paths"]) + "</div>")


def path_html(p):
    """A path that wraps only between steps, never inside an arrow."""
    return esc(p).replace("-&gt;", "-\u2060&gt;")


def event_block(t):
    rows = "".join(f"<tr><td class='k'>{c}</td><td>{esc(n)}</td><td class='g'>{' '.join(t['event_guards'][c])}</td></tr>"
                   for c, n in t["event_codes"].items())
    tree = "\n".join(["(root) INITIALISATION"] + draw_events_compact(t["event_tree"], width=8))
    return (f"<table class='codes ev'><tr><th>รหัส</th><th>event</th><th>guard</th></tr>{rows}</table>"
            f"<pre class='tree'>{esc(tree)}</pre><div class='lbl'>เส้นทาง</div>"
            "<div class='paths'>" + "<br>".join(path_html(p) for p in t["event_paths"]) + "</div>")


GUARD_RULE = ("<div class='rule'><b>รหัส guard</b><ul>"
              "<li><b>ตัวอักษร</b> คือจุดตัดสินใจ เงื่อนไขที่นิพจน์ด้านซ้ายเหมือนกันใช้ตัวอักษรเดียวกัน "
              "เช่น <code>mode = GOLD</code> และ <code>mode = SILVER</code> เป็นตัว b ทั้งคู่</li>"
              "<li><b>ตัวเลข</b> คือทางเลือกของจุดตัดสินใจนั้น เช่น b1, b2, b3</li>"
              "<li>ตัวอักษรและตัวเลขเรียงตามลำดับที่พบในแบบจำลอง</li></ul></div>")
EVENT_RULE = ("<div class='rule'><b>รหัส event</b> (send และ receive นับเป็นคนละ event)<ul>"
              "<li><b>ตัวอักษร</b> คือลำดับขั้น event ที่ต่อกันเป็นเส้นตรงได้ตัวอักษรใหม่ทุกขั้น (a1 → b1 → c1)</li>"
              "<li><b>ตัวเลข</b> คือทางเลือกที่จุดแยก event ขั้นเดียวกันของแต่ละกิ่งใช้ตัวอักษรเดียวกัน "
              "เช่น กิ่ง GOLD, SILVER, BRONZE ได้ m1, m2, m3 และขั้นถัดไปได้ n1, n2, n3</li>"
              "<li>ท้าย loop เป็นจุดแยกเช่นกัน คือทำต่อ (o1) หรือวนรอบใหม่ (o2)</li>"
              "<li>event ที่กิ่งมารวมกันได้ตัวอักษรใหม่ (q1)</li></ul></div>")


def render(rows, trees):
    have = [r for r in rows if r["id"] in trees]
    n_guard = sum(bool(trees[r["id"]]["guard_codes"]) for r in have)
    gp = Counter(len(trees[r["id"]]["guard_paths"]) for r in have)
    h = ["<h1>Event tree และ Guard tree</h1>",
         f"<div class='sub'>แบบจำลอง {len(have)} ตัว · มีเงื่อนไขจากแผนภาพ {n_guard} ตัว · "
         f"ไม่มีเงื่อนไข {len(have) - n_guard} ตัว</div>"]

    h.append("<h2>1. ที่มาของ tree</h2>")
    h.append("<p>tree ทั้งสองแบบสร้างจาก guard ในแบบจำลอง Event-B ที่ได้จาก ChronoSeq-B โดยไม่แก้ไขแบบจำลอง</p>"
             "<p>guard ในแบบจำลองแบ่งเป็น 2 กลุ่ม ดังนี้</p>"
             "<table><tr><th style='width:34%'>กลุ่ม</th><th>ตัวอย่าง</th><th style='width:16%'>ใช้สร้าง</th></tr>"
             "<tr><td>guard ลำดับข้อความ (สูตรแปลงสร้างให้ทุกข้อความ)</td><td><code>m ∉ sentMessages</code>, "
             "<code>p ∈ receivedMessages</code>, <code>currentMessage = ∅</code></td><td>Event tree</td></tr>"
             "<tr><td>guard เงื่อนไขจากแผนภาพ (loop, alt, opt)</td><td><code>cycleNo &lt; 8</code>, "
             "<code>mode = GOLD</code>, <code>cycleNo mod 3 = 0</code></td><td>Guard tree</td></tr></table>")

    h.append("<h2>2. การตั้งรหัส</h2>" + GUARD_RULE + EVENT_RULE)

    h.append("<h2>3. การสร้าง tree</h2><ul>"
             "<li><b>Event tree</b> — receive ตามหลัง send ของข้อความเดียวกัน และ send ของข้อความ m ตามหลัง receive "
             "ของข้อความ p เมื่อ send m มี guard <code>p ∈ receivedMessages</code></li>"
             "<li>alt ทำให้ tree แยกกิ่ง และกิ่งกลับมารวมที่ event ที่มี guard "
             "<code>p ∈ receivedMessages ∨ q ∈ receivedMessages</code></li>"
             "<li>event นับรอบ loop อยู่ท้าย loop เครื่องหมาย ↺ ชี้กลับไปยัง event แรกของ loop</li>"
             "<li><b>Guard tree</b> — ไล่ตามแต่ละเส้นทางของ event tree แล้วบันทึกรหัส guard ตามลำดับที่พบครั้งแรก "
             "จึงแสดงได้ทั้งเงื่อนไขที่ซ้อนกัน (alt ใน loop) และเงื่อนไขที่ต่อกัน (opt ตามด้วย alt)</li>"
             "<li>เอกสารนี้แสดง event tree แบบย่อ คือ event ที่ต่อกันเป็นเส้นตรงเขียนในบรรทัดเดียว "
             "และขึ้นบรรทัดใหม่เฉพาะที่จุดแยก รูปเต็มอยู่ใน <code>models/&lt;id&gt;/tree.txt</code></li></ul>")

    h.append("<h2>4. ตัวอย่าง</h2>")
    h.append("<p><b>ตัวอย่างพื้นฐาน</b> เงื่อนไขแรกคือ <code>age &gt; 50</code> จากนั้นมี 2 ทางเลือก คือ "
             "<code>salary ≥ 500</code> และ <code>salary &lt; 500</code></p>")
    h.append("<table class='codes'><tr><td class='k'>a1</td><td>age &gt; 50</td></tr>"
             "<tr><td class='k'>b1</td><td>salary ≥ 500</td></tr><tr><td class='k'>b2</td><td>salary &lt; 500</td></tr></table>"
             "<pre class='tree'>(root)\n└── a1  age &gt; 50\n    ├── b1  salary ≥ 500\n    └── b2  salary &lt; 500\n\n"
             "เส้นทาง:  a1 -&gt; b1\n           a1 -&gt; b2</pre>")
    for mid, why in (("model_141", "opt ตามด้วย alt 3 ทาง (เงื่อนไขต่อกัน)"),
                     ("model_109", "alt ใน loop และกิ่งแรกมี loop ซ้อน (เงื่อนไขซ้อนกัน)")):
        r = next(x for x in rows if x["id"] == mid)
        t = trees[mid]
        h.append(f"<div class='model'><h3>{mid} {esc(r['case'])} — {esc(why)}</h3>"
                 f"<div class='cols'><div><div class='lbl'>Guard tree</div>{guard_block(t)}</div>"
                 f"<div><div class='lbl'>Event tree</div>{event_block(t)}</div></div></div>")

    h.append("<h2>5. ภาพรวมทั้งชุด</h2>")
    h.append("<table><tr><th>จำนวนเส้นทางใน guard tree</th>" + "".join(f"<th>{k}</th>" for k in sorted(gp)) + "</tr>"
             "<tr><td>จำนวนแบบจำลอง</td>" + "".join(f"<td class='n'>{gp[k]}</td>" for k in sorted(gp)) + "</tr></table>")
    h.append("<ul><li>0 คือแบบจำลองที่ไม่มีเงื่อนไขจากแผนภาพ จึงมีเฉพาะ event tree</li>"
             "<li>tree ของแต่ละแบบจำลองอยู่ใน <code>models/&lt;id&gt;/tree.txt</code> และ <code>tree.json</code> "
             "ส่วนข้อมูลรวมทุกแบบจำลองอยู่ใน <code>data/trees.jsonl</code>, <code>trees/guard_codes.csv</code> "
             "และ <code>trees/event_codes.csv</code></li>"
             "<li><b>model_001</b> — model.txt มีเพียงชื่อ event จึงใช้ event และ guard จากไฟล์ .bpo ของ Rodin แทน "
             "มี 1 event ที่ไม่มีชื่อในไฟล์ (unnamed_event_N, guard <code>retry &lt; 3</code>) "
             "และเนื่องจากแปลงด้วยสูตรรุ่นแรก event tree จึงแยกเป็นหลายกิ่งจาก root</li></ul>")

    h.append("<h2 style='break-before:page'>6. tree ของแต่ละแบบจำลอง</h2>")
    h.append("<p>แต่ละแบบจำลองแสดง 2 ส่วน ด้านซ้ายคือ guard (รหัส, tree, เส้นทาง) ด้านขวาคือ event "
             "(รหัส, tree แบบย่อ, เส้นทาง) คอลัมน์ guard ในตาราง event คือรหัส guard ของ event นั้น "
             "และ ↺ x หมายถึงวนกลับไปที่ event x</p>")
    for code, (en, th) in TOPIC_NAMES.items():
        group = [r for r in have if r["topic"] == en]
        h.append(f"<h3>{esc(th)} · {esc(en)} ({len(group)})</h3>")
        for r in group:
            t = trees[r["id"]]
            h.append(f"<div class='model'><h4>{r['id']} {esc(r['case'])} · <span class='res-{r['result']}'>{r['result']}</span></h4>"
                     f"<div class='cols'><div><div class='lbl'>Guard</div>{guard_block(t)}</div>"
                     f"<div><div class='lbl'>Event</div>{event_block(t)}</div></div></div>")
    return (f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{CSS}{EXTRA_CSS}</style></head>"
            f"<body>{''.join(h)}</body></html>")


def main(out, rows, trees):
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "trees.html")
        open(page, "w").write(render(rows, trees))
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.join(out, 'TREES.pdf')}", f"file://{page}"],
                       check=True, capture_output=True)


CHECKS = [("C1", "ข้อความ", "ทุกข้อความในแผนภาพมี event send และ receive ครบ และเรียงลำดับตรงกัน"),
          ("C2", "guard ของ event", "เงื่อนไขที่ครอบข้อความในแผนภาพตรงกับ guard ของ event send และ receive ของข้อความนั้น"),
          ("C3", "รหัส guard", "ทุกเงื่อนไขในแผนภาพมีรหัส และไม่มีรหัสเกิน"),
          ("C4", "ลำดับ event", "event ก่อนหน้าของทุก event ตรงกับแผนภาพ รวมถึงจุดแยกและจุดรวมของ alt"),
          ("C5", "loop", "ทุก loop มี event นับรอบ มี guard ถูกต้อง อยู่ท้าย loop และวนกลับไปยัง event แรกของ loop"),
          ("C6", "รหัส event", "event หนึ่งมีรหัสเดียว ทางเลือกที่จุดแยกใช้ตัวอักษรเดียวกันโดยตัวเลขไม่ซ้ำ "
                              "และเส้นตรงไม่ใช้ตัวอักษรซ้ำ"),
          ("C7", "เส้นทาง guard", "เส้นทางใน guard tree ครบทุกทางที่เป็นไปได้ในแผนภาพ"),
          ("C8", "ไฟล์", "ไฟล์ในชุดเทรน (models/, data/trees.jsonl, trees/guard_codes.csv) ตรงกับต้นฉบับ")]


def summary(out, rows, trees, stats, check):
    """SUMMARY.pdf: what was built, the coding rules, how it was checked and the result."""
    res = check["results"]
    n = len(rows)
    ok = sum(not r["errors"] for r in res.values())
    diag = [m for m, r in res.items() if "messages" in r]
    def passed(code):
        scope = list(res) if code in ("C1", "C3", "C6") else diag
        return sum(not any(e.startswith(code) for e in res[m]["errors"]) for m in scope), len(scope)
    gp = Counter(s["guard_paths"] for s in stats)
    ev = sorted(s["events"] for s in stats)
    h = ["<h1>สรุปงาน Event tree และ Guard tree</h1>",
         f"<div class='sub'>แบบจำลอง {n} ตัว · ตรวจกับแผนภาพต้นฉบับ {len(diag)} ตัว "
         f"และกับไฟล์ Rodin {n - len(diag)} ตัว (model_001)</div>",
         "<div class='kpi'>"
         f"<div><b>{n}</b><span>แบบจำลอง</span></div>"
         f"<div><b>{ok} / {n}</b><span>ผ่านการตรวจครบทุกข้อ</span></div>"
         f"<div><b>{sum(s['guard_codes'] for s in stats):,}</b><span>รหัส guard</span></div>"
         f"<div><b>{sum(s['events'] for s in stats):,}</b><span>รหัส event</span></div></div>"]

    h.append("<h2>1. ภาพรวม</h2>")
    h.append("<p>สร้าง tree 2 แบบให้แบบจำลอง Event-B ทุกตัวที่ได้จาก ChronoSeq-B โดยใช้ guard ในแบบจำลองตามเดิม ไม่แก้ไข</p>"
             "<table><tr><th style='width:16%'>tree</th><th>node</th><th style='width:38%'>สร้างจาก</th></tr>"
             "<tr><td>Event tree</td><td>event ของ Event-B (send และ receive แยกกัน)</td>"
             "<td>guard ลำดับข้อความ เช่น <code>p ∈ receivedMessages</code></td></tr>"
             "<tr><td>Guard tree</td><td>เงื่อนไขจากแผนภาพ (loop, alt, opt)</td>"
             "<td>guard เงื่อนไข เช่น <code>mode = GOLD</code></td></tr></table>")

    h.append("<h2>2. การตั้งรหัส</h2>")
    h.append("<table><tr><th style='width:11%'></th><th>ตัวอักษร</th><th>ตัวเลข</th><th style='width:27%'>ตัวอย่าง</th></tr>"
             "<tr><td>guard</td><td>จุดตัดสินใจ (เงื่อนไขที่นิพจน์ด้านซ้ายเหมือนกันใช้ตัวอักษรเดียวกัน)</td>"
             "<td>ทางเลือกของจุดตัดสินใจ</td><td><code>mode = GOLD</code> → b1<br><code>mode = SILVER</code> → b2</td></tr>"
             "<tr><td>event</td><td>ลำดับขั้น (event ที่ต่อกันเป็นเส้นตรงได้ตัวอักษรใหม่ทุกขั้น)</td>"
             "<td>ทางเลือกที่จุดแยก (alt หรือท้าย loop)</td><td>event แรกของ 3 กิ่ง → m1, m2, m3</td></tr></table>")
    h.append("<p>event ที่กิ่งมารวมกันได้ตัวอักษรใหม่ ถ้าทางเลือกใดเป็นจุดรวม ทางเลือกอื่นที่จุดแยกเดียวกันใช้ตัวอักษรนั้นด้วย "
             "รหัสจึงเหมือนเดิมไม่ว่าจะไล่กิ่งใดก่อน</p>")
    t = trees["model_141"]
    gtree = "\n".join(["(root)"] + draw(t["guard_tree"], lambda c: f"{c}  {t['guard_codes'][c]}"))
    etree = "\n".join(["(root)"] + draw_events_compact(t["event_tree"], width=8))
    h.append("<h3>ตัวอย่าง: model_141 PharmacyDelivery (opt ตามด้วย alt 3 ทาง)</h3>"
             f"<div class='cols'><div><div class='lbl'>Guard tree</div><pre class='tree'>{esc(gtree)}</pre></div>"
             f"<div><div class='lbl'>Event tree</div><pre class='tree'>{esc(etree)}</pre></div></div>")

    h.append("<h2>3. การตรวจสอบความถูกต้อง</h2>")
    h.append("<p>เขียนโปรแกรมตรวจแยกต่างหาก (<code>tools/verify_trees.py</code>) ให้อ่านแผนภาพ draw.io ต้นฉบับโดยตรง "
             "ได้แก่ กรอบ alt, opt, loop, par เส้นแบ่งกิ่ง เงื่อนไข และข้อความ แล้วคำนวณ tree ที่ควรได้ "
             "เทียบกับ tree ที่สร้างไว้ 8 ข้อ โปรแกรมนี้ไม่ใช้โค้ดของสูตรแปลงหรือของตัวสร้าง tree "
             "การตรวจจึงเป็นอิสระจากงานที่ถูกตรวจ</p>")
    h.append("<table class='keep'><tr><th style='width:7%'>ข้อ</th><th style='width:17%'>เรื่อง</th><th>สิ่งที่ตรวจ</th>"
             "<th style='width:12%'>ผ่าน</th></tr>")
    for code, name, what in CHECKS:
        if code == "C8":
            good = not check["file_errors"]
            cell = "ทุกไฟล์" if good else f"ไม่ตรง {len(check['file_errors'])} จุด"
        else:
            p_, tot = passed(code)
            good, cell = p_ == tot, f"{p_} / {tot}"
        h.append(f"<tr><td>{code}</td><td>{esc(name)}</td><td>{esc(what)}</td>"
                 f"<td class='{'ok' if good else 'bad'}'>{cell}</td></tr>")
    h.append("</table>")
    h.append(f"<p>C2, C4, C5 และ C7 ต้องใช้แผนภาพ จึงตรวจ {len(diag)} ตัว ส่วน model_001 ไม่มีแผนภาพ "
             "จึงตรวจ C1 และ C3 กับไฟล์ .bpo ของ Rodin แทน ผลรายแบบจำลองอยู่ใน <code>check.csv</code></p>")
    st = check["selftest"]
    h.append(f"<h3>ทดสอบโปรแกรมตรวจ</h3><p>เพื่อยืนยันว่าโปรแกรมตรวจพบข้อผิดพลาดได้จริง ได้แก้ tree ที่ถูกต้องให้ผิดโดยเจตนา "
             f"{len(st)} แบบ โปรแกรมตรวจพบ <b>{sum(x['caught'] for x in st)} จาก {len(st)}</b> แบบ</p>"
             "<table><tr><th>ข้อผิดที่ใส่</th><th style='width:16%'>แบบจำลอง</th><th style='width:16%'>ตรวจพบในข้อ</th></tr>"
             + "".join(f"<tr><td>{esc(x['case'])}</td><td>{x['model']}</td>"
                       f"<td class='{'ok' if x['caught'] else 'bad'}'>{x['by'] or 'ตรวจไม่พบ'}</td></tr>" for x in st)
             + "</table>")
    h.append("<h3>ปัญหาที่พบและการแก้ไข</h3><table><tr><th style='width:30%'>ปัญหา</th><th>สาเหตุ</th>"
             "<th style='width:28%'>การแก้ไข</th></tr>"
             "<tr><td>รหัส event ที่จุดแยกเดียวกันใช้คนละตัวอักษร (model_015, model_036, model_038)</td>"
             "<td>ทางเลือกหนึ่งเป็นจุดรวมของ alt ก่อนหน้า ซึ่งมีตัวอักษรของตัวเองอยู่แล้ว "
             "อีกทางเลือกคือ event นับรอบ loop จึงได้ตัวอักษรใหม่</td>"
             "<td>ให้ทางเลือกอื่นใช้ตัวอักษรของจุดรวม (k1, k2) ตรวจซ้ำแล้วผ่านทุกแบบจำลอง</td></tr>"
             "<tr><td>model_001 ไม่มี tree ในรอบแรก</td><td>model.txt มีเพียงชื่อ event ไม่มี guard</td>"
             "<td>ใช้ event และ guard จากไฟล์ .bpo ของ Rodin</td></tr></table>")

    h.append("<h2>4. ข้อสังเกตเกี่ยวกับสูตรแปลง</h2>"
             "<p>การตรวจพบลักษณะต่อไปนี้ของแบบจำลองที่ได้จากสูตรแปลง tree แสดงตามแบบจำลองจริงโดยไม่ปรับแก้</p><ul>"
             "<li><b>par</b> — ข้อความใน par ถูกเรียงตามลำดับบนลงล่าง ไม่มี guard ที่ให้ทำงานพร้อมกัน "
             "event tree จึงเป็นเส้นตรง</li>"
             "<li><b>opt</b> — ข้อความหลัง opt ต้องรอข้อความสุดท้ายใน opt จึงข้าม opt ไม่ได้ "
             "tree จึงไม่มีกิ่งที่ไม่เข้า opt</li>"
             "<li><b>loop</b> — ข้อความหลัง loop ต้องรอข้อความสุดท้ายใน loop จึงต้องทำอย่างน้อย 1 รอบ "
             "รอบถัดไปแสดงด้วย ↺</li>"
             "<li><b>model_001</b> — แปลงด้วยสูตรรุ่นแรก loop และ par ไม่มี guard ที่อ้างข้อความก่อนหน้า "
             "event tree จึงแยกเป็น 2 กิ่งจาก root และมี 1 event ที่ไม่มีชื่อในไฟล์ Rodin (unnamed_event_N)</li></ul>")

    h.append("<h2>5. สถิติ</h2>")
    h.append("<table><tr><th>จำนวนเส้นทางใน guard tree</th>" + "".join(f"<th>{k}</th>" for k in sorted(gp)) + "</tr>"
             "<tr><td>จำนวนแบบจำลอง</td>" + "".join(f"<td class='n'>{gp[k]}</td>" for k in sorted(gp)) + "</tr></table>")
    h.append("<table><tr><th>ต่อแบบจำลอง</th><th>ต่ำสุด</th><th>มัธยฐาน</th><th>สูงสุด</th><th>รวมทั้งชุด</th></tr>"
             + "".join(f"<tr><td>{lbl}</td><td class='n'>{min(v)}</td><td class='n'>{sorted(v)[len(v) // 2]}</td>"
                       f"<td class='n'>{max(v)}</td><td class='n'>{sum(v):,}</td></tr>"
                       for lbl, v in (("event", ev),
                                      ("เส้นทางใน event tree", [s["event_paths"] for s in stats]),
                                      ("รหัส guard", [s["guard_codes"] for s in stats]),
                                      ("loop", [s["loops"] for s in stats])))
             + "</table>")
    h.append(f"<p>แบบจำลอง {gp[0]} ตัวไม่มีเงื่อนไขจากแผนภาพ จึงมีเฉพาะ event tree</p>")

    h.append("<h2>6. ไฟล์</h2>")
    tree = ["EventB_PO_Training/",
            "├── trees/",
            "│   ├── SUMMARY.pdf          ← เอกสารนี้",
            "│   ├── TREES.pdf            ← หลักการ ตัวอย่าง และ tree ของทุกแบบจำลอง",
            "│   ├── guard_codes.csv      ← รหัส guard ของทุกแบบจำลอง",
            "│   ├── event_codes.csv      ← รหัส event ของทุกแบบจำลอง",
            "│   ├── tree_summary.csv     ← ตัวเลขสรุปรายแบบจำลอง",
            "│   ├── check.csv            ← ผลตรวจรายแบบจำลอง",
            "│   └── by_topic/<หัวข้อ>/<pass|fail>/<แบบจำลอง>.txt   ← tree ของแต่ละแบบจำลอง",
            "├── models/<id>/tree.txt, tree.json   ← ชุดเดียวกัน เก็บคู่กับ model.txt",
            "└── data/trees.jsonl                 ← ทุกแบบจำลองในไฟล์เดียว สำหรับใช้กับโปรแกรม"]
    h.append("<pre>" + esc("\n".join(tree)) + "</pre>")
    h.append("<p>สร้างใหม่ทั้งหมดได้ด้วยคำสั่ง <code>python tools/make_release.py</code> "
             "ซึ่งจะสร้าง tree ตรวจความถูกต้อง และทำเอกสารตามลำดับ</p>")

    css = (CSS + EXTRA_CSS + ".kpi { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 8px 0 4px; }"
           ".kpi div { border: 1px solid #cfd6e1; border-radius: 6px; padding: 6px 10px; }"
           ".kpi b { display: block; font-size: 17pt; color: #12325c; } .kpi span { font-size: 8.8pt; color: #5a6475; }"
           "table.keep { break-inside: avoid; } td.ok { color: #2e7d5b; font-weight: bold; } td.bad { color: #c0392b; font-weight: bold; }")
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "summary.html")
        open(page, "w").write(f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{css}</style></head>"
                              f"<body>{''.join(h)}</body></html>")
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.join(out, 'SUMMARY.pdf')}", f"file://{page}"],
                       check=True, capture_output=True)
