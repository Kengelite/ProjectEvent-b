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
table.codes { font-size: 8.2pt; margin: 2px 0 4px; } table.codes td { padding: 1px 6px; }
table.codes td.k { font-family: Menlo, monospace; font-weight: bold; color: #2f5fa8; width: 34px; }
.ecodes { font-family: Menlo, monospace; font-size: 7.4pt; columns: 2; column-gap: 12px; line-height: 1.35; margin: 2px 0 4px; overflow-wrap: anywhere; }
.paths { font-family: Menlo, monospace; font-size: 7.6pt; line-height: 1.4; overflow-wrap: normal; word-break: normal; }
.none { color: #8a93a3; font-size: 8.6pt; }
.rule { border-left: 4px solid #2f5fa8; background: #eef3fb; padding: 6px 10px; margin: 6px 0; }
"""


def guard_block(t):
    gc = t["guard_codes"]
    if not gc:
        return "<div class='none'>ไม่มีเงื่อนไขจากแผนภาพ (ลำดับข้อความอย่างเดียว)</div>"
    rows = "".join(f"<tr><td class='k'>{c}</td><td>{esc(g)}</td></tr>" for c, g in gc.items())
    tree = "\n".join(["(root)"] + draw(t["guard_tree"], lambda c: f"{c}  {gc[c]}"))
    return (f"<table class='codes'>{rows}</table><pre class='tree'>{esc(tree)}</pre>"
            "<div class='lbl'>เส้นทาง</div><div class='paths'>" + "<br>".join(esc(p) for p in t["guard_paths"]) + "</div>")


def event_block(t):
    codes = "<br>".join(f"<b>{c}</b> {esc(n)}" + (f" (guard {' '.join(t['event_guards'][c])})" if t["event_guards"][c] else "")
                        for c, n in t["event_codes"].items())
    tree = "\n".join(["(root) INITIALISATION"] + draw_events_compact(t["event_tree"], width=8))
    return (f"<div class='ecodes'>{codes}</div><pre class='tree'>{esc(tree)}</pre><div class='lbl'>เส้นทาง</div>"
            "<div class='paths'>" + "<br>".join(esc(p) for p in t["event_paths"]) + "</div>")


def render(rows, trees):
    have = [r for r in rows if r["id"] in trees]
    n_guard = sum(bool(trees[r["id"]]["guard_codes"]) for r in have)
    gp = Counter(len(trees[r["id"]]["guard_paths"]) for r in have)
    h = ["<h1>Event tree และ Guard tree</h1>",
         f"<div class='sub'>สกัดจากแบบจำลอง Event-B {len(have)} ตัว (model.txt ที่ได้จาก ChronoSeq-B โดยไม่แก้ไข) · "
         f"มีเงื่อนไขจากแผนภาพ {n_guard} ตัว · ไม่มีเงื่อนไข {len(have) - n_guard} ตัว</div>"]

    h.append("<h2>1. หลักการ</h2>")
    h.append("<p>guard ในแบบจำลองแบ่งได้ 2 กลุ่ม</p><table><tr><th style='width:30%'>กลุ่ม</th><th>ตัวอย่าง</th><th style='width:18%'>ใช้ทำ</th></tr>"
             "<tr><td>guard ควบคุมลำดับข้อความ (สูตรแปลงสร้างให้ทุกข้อความ)</td><td><code>m ∉ sentMessages</code>, "
             "<code>p ∈ receivedMessages</code>, <code>currentMessage = ∅</code></td><td>Event tree</td></tr>"
             "<tr><td>guard เงื่อนไขจากแผนภาพ (loop / alt / opt)</td><td><code>cycleNo &lt; 8</code>, "
             "<code>mode = GOLD</code>, <code>cycleNo mod 3 = 0</code></td><td>Guard tree</td></tr></table>")
    h.append("<div class='rule'><b>การตั้งรหัส guard</b><br>"
             "• <b>ตัวอักษร</b> = จุดตัดสินใจ: guard ที่นิพจน์ด้านซ้ายเหมือนกันใช้ตัวอักษรเดียวกัน "
             "(<code>mode = GOLD</code> กับ <code>mode = SILVER</code> เป็นตัว b ทั้งคู่)<br>"
             "• <b>ตัวเลข</b> = ทางเลือกของจุดตัดสินใจนั้น เรียงตามลำดับที่พบในไฟล์ (b1, b2, b3)<br>"
             "• ตัวอักษรเรียงตามลำดับที่พบในไฟล์ (a, b, c …)</div>")
    h.append("<div class='rule'><b>การตั้งรหัส event</b> (ใช้หลักเดียวกับ guard · send และ receive เป็นคนละ event)<br>"
             "• <b>ตัวอักษร</b> = ลำดับขั้น: event ที่ต่อกันเป็นเส้นตรงได้ตัวอักษรใหม่ทีละขั้น (a1 → b1 → c1)<br>"
             "• <b>ตัวเลข</b> = ทางเลือกตรงจุดแยกกิ่ง: event ขั้นเดียวกันของแต่ละกิ่งใช้ตัวอักษรเดียวกัน "
             "(กิ่ง GOLD / SILVER / BRONZE → m1 / m2 / m3 แล้วขั้นถัดไป n1 / n2 / n3) · ท้าย loop แยกเป็น "
             "ทำต่อ (o1) กับวนรอบใหม่ (o2)<br>"
             "• event ที่หลายกิ่งมารวมกันได้ตัวอักษรใหม่ (q1) · ในวงเล็บ (guard …) คือรหัส guard ของ event นั้น</div>")
    h.append("<div class='rule'><b>การสร้าง tree</b><br>"
             "• <b>Event tree</b>: send m → receive m และ receive p → send m เมื่อ send m มี guard "
             "<code>p ∈ receivedMessages</code> · alt แตกเป็นหลายกิ่ง · หลัง alt ที่มี guard แบบ "
             "<code>p ∈ receivedMessages ∨ q ∈ receivedMessages</code> ทุกกิ่งต่อด้วย event เดียวกัน · "
             "event นับรอบ loop (checkloop) อยู่ท้าย loop และมีลูกศร ↺ กลับไปจุดเริ่ม loop<br>"
             "• ในเอกสารนี้ event tree แสดงแบบย่อ: event ที่ต่อกันเป็นเส้นตรงเขียนในบรรทัดเดียว (a1 → b1 → c1) "
             "และแตกบรรทัดเฉพาะจุดที่แยกกิ่ง · รูปเต็มอยู่ใน <code>models/&lt;id&gt;/tree.txt</code><br>"
             "• <b>Guard tree</b>: เดินตามแต่ละเส้นทางของ event tree แล้วเก็บรหัส guard ตามลำดับที่พบครั้งแรก "
             "จึงได้ทั้งเงื่อนไขซ้อนกัน (loop ที่มี alt ข้างใน) และเงื่อนไขที่มาต่อกัน (opt แล้วตามด้วย alt)</div>")

    h.append("<h2>2. ตัวอย่าง</h2>")
    h.append("<p><b>ตัวอย่างหลักการ</b>: guard แรกคือ <code>age &gt; 50</code> และจุดถัดไปมี 2 ทางเลือก "
             "<code>salary ≥ 500</code> กับ <code>salary &lt; 500</code></p>")
    h.append("<table class='codes'><tr><td class='k'>a1</td><td>age &gt; 50</td></tr>"
             "<tr><td class='k'>b1</td><td>salary ≥ 500</td></tr><tr><td class='k'>b2</td><td>salary &lt; 500</td></tr></table>"
             "<pre class='tree'>(root)\n└── a1  age &gt; 50\n    ├── b1  salary ≥ 500\n    └── b2  salary &lt; 500\n\n"
             "เส้นทาง:  a1 -&gt; b1\n           a1 -&gt; b2</pre>")
    for mid, why in (("model_141", "opt แล้วตามด้วย alt 3 ทาง (เงื่อนไขมาต่อกัน)"),
                     ("model_109", "loop ที่มี alt อยู่ข้างใน และมี loop ซ้อนในกิ่งแรก (เงื่อนไขซ้อนกัน)")):
        r = next(x for x in rows if x["id"] == mid)
        t = trees[mid]
        h.append(f"<div class='model'><h3>{mid} {esc(r['case'])} — {esc(why)}</h3>"
                 f"<div class='cols'><div><div class='lbl'>Guard tree</div>{guard_block(t)}</div>"
                 f"<div><div class='lbl'>Event tree</div>{event_block(t)}</div></div></div>")

    h.append("<h2>3. สรุปทั้งชุด</h2>")
    h.append("<table><tr><th>จำนวนเส้นทางใน guard tree</th>" + "".join(f"<th>{k}</th>" for k in sorted(gp)) + "</tr>"
             "<tr><td>จำนวนแบบจำลอง</td>" + "".join(f"<td class='n'>{gp[k]}</td>" for k in sorted(gp)) + "</tr></table>")
    h.append("<p>0 = ไม่มีเงื่อนไขจากแผนภาพ · ไฟล์ของแต่ละแบบจำลอง: <code>models/&lt;id&gt;/tree.txt</code> (รูป tree เต็ม) และ "
             "<code>tree.json</code> · รวมทุกแบบจำลอง: <code>data/trees.jsonl</code>, <code>trees/guard_codes.csv</code>, "
             "<code>trees/event_codes.csv</code> · "
             "<b>model_001</b>: model.txt มีเฉพาะชื่อ event จึงอ่าน event และ guard จากไฟล์ proof obligation ของ Rodin (.bpo) แทน · "
             "มี 1 event ที่ไฟล์ Rodin ไม่เก็บชื่อไว้ (แสดงเป็น unnamed_event_N, guard <code>retry &lt; 3</code>) · "
             "แบบจำลองนี้แปลงด้วยสูตรรุ่นแรก ส่วน loop และ par จึงไม่มี guard อ้างข้อความก่อนหน้า event tree จึงแยกเป็นหลายกิ่งจาก root</p>")

    h.append("<h2 style='break-before:page'>4. รหัสและเส้นทางของแต่ละแบบจำลอง</h2>")
    h.append("<p>ซ้าย: รหัส guard, guard tree และเส้นทาง · ขวา: รหัส event (ในวงเล็บคือ guard ของ event นั้น), "
             "event tree แบบย่อ และเส้นทาง · ↺ x = จบรอบ loop แล้วกลับไปที่ event x</p>")
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


CHECKS = [("C1", "ข้อความ", "ข้อความในแผนภาพตรงกับ event send / receive ใน Event-B ครบและเรียงลำดับเดียวกัน"),
          ("C2", "guard ราย event", "เงื่อนไขที่ครอบแต่ละข้อความในแผนภาพ ตรงกับ guard ของ event send และ receive ของข้อความนั้น"),
          ("C3", "รหัส guard", "มีรหัสครบทุกเงื่อนไขในแผนภาพ และไม่มีรหัสเกิน"),
          ("C4", "ลำดับ event", "event ก่อนหน้าของทุก event ตรงกับลำดับที่ได้จากแผนภาพ รวมจุดแยกกิ่งและจุดรวมของ alt"),
          ("C5", "loop", "event นับรอบ loop มีครบทุก loop มี guard ถูกต้อง อยู่ท้ายส่วนที่วน และย้อนกลับจุดเริ่มถูกต้อง"),
          ("C6", "รหัส event", "1 event มี 1 รหัส · ทางเลือกตรงจุดแยกกิ่งใช้ตัวอักษรเดียวกันและเลขไม่ซ้ำ · เส้นตรงไม่ใช้ตัวอักษรซ้ำ"),
          ("C7", "เส้นทาง guard", "เส้นทางใน guard tree ตรงกับทุกทางที่เป็นไปได้ในแผนภาพ"),
          ("C8", "ไฟล์", "ไฟล์ในชุดเทรน (models/, data/trees.jsonl, trees/guard_codes.csv) ตรงกับต้นฉบับทุกไฟล์")]


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
         f"<div class='sub'>{n} แบบจำลอง · ตรวจกับแผนภาพต้นฉบับ {len(diag)} แบบจำลอง และกับไฟล์ Rodin 1 แบบจำลอง (model_001)</div>",
         "<div class='kpi'>"
         f"<div><b>{n}</b><span>แบบจำลองที่มี tree</span></div>"
         f"<div><b>{ok} / {n}</b><span>ผ่านการตรวจทุกข้อ</span></div>"
         f"<div><b>{sum(s['guard_codes'] for s in stats):,}</b><span>รหัส guard รวม</span></div>"
         f"<div><b>{sum(s['events'] for s in stats):,}</b><span>รหัส event รวม</span></div></div>"]

    h.append("<h2>1. งานนี้ทำอะไร</h2>")
    h.append("<p>สกัด tree 2 แบบจากแบบจำลอง Event-B ทุกตัว โดยใช้ <code>model.txt</code> ที่ได้จาก ChronoSeq-B ตามเดิม ไม่แก้ไข "
             "(model_001 มีเฉพาะชื่อ event จึงอ่านจากไฟล์ proof obligation ของ Rodin แทน)</p>"
             "<table><tr><th style='width:18%'>tree</th><th>node คืออะไร</th><th style='width:34%'>ได้จาก</th></tr>"
             "<tr><td>Event tree</td><td>event ของ Event-B (send และ receive แยกกัน) เรียงตามลำดับที่ทำงานได้</td>"
             "<td>guard ควบคุมลำดับ เช่น <code>p ∈ receivedMessages</code></td></tr>"
             "<tr><td>Guard tree</td><td>เงื่อนไขจากแผนภาพ (loop / alt / opt) เรียงตามลำดับที่พบเมื่อระบบทำงาน</td>"
             "<td>guard เงื่อนไข เช่น <code>mode = GOLD</code></td></tr></table>")

    h.append("<h2>2. หลักการตั้งรหัส</h2>")
    h.append("<table><tr><th style='width:14%'></th><th>ตัวอักษร</th><th>ตัวเลข</th><th style='width:26%'>ตัวอย่าง</th></tr>"
             "<tr><td>guard</td><td>จุดตัดสินใจ: guard ที่นิพจน์ด้านซ้ายเหมือนกันใช้ตัวอักษรเดียวกัน</td>"
             "<td>ทางเลือกของจุดนั้น</td><td><code>mode = GOLD</code> b1<br><code>mode = SILVER</code> b2</td></tr>"
             "<tr><td>event</td><td>ลำดับขั้น: event ที่ต่อกันเป็นเส้นตรงได้ตัวอักษรใหม่ทีละขั้น</td>"
             "<td>ทางเลือกตรงจุดแยกกิ่ง (alt หรือ วนรอบใหม่ / ทำต่อ)</td><td>m1 / m2 / m3 = event แรกของแต่ละกิ่ง</td></tr></table>")
    h.append("<p>event ที่หลายกิ่งมารวมกันได้ตัวอักษรใหม่ · ถ้าทางเลือกหนึ่งเป็นจุดรวม ทางเลือกอื่นตรงจุดแยกนั้นใช้ตัวอักษรของจุดรวม "
             "(รหัสจึงไม่ขึ้นกับลำดับที่อ่านกิ่ง)</p>")
    from extract_trees import draw_events_compact
    t = trees["model_141"]
    gtree = "\n".join(["(root)"] + draw(t["guard_tree"], lambda c: f"{c}  {t['guard_codes'][c]}"))
    etree = "\n".join(["(root)"] + draw_events_compact(t["event_tree"], width=8))
    h.append("<h3>ตัวอย่าง model_141 PharmacyDelivery (opt แล้วตามด้วย alt 3 ทาง)</h3>"
             f"<div class='cols'><div><div class='lbl'>Guard tree</div><pre class='tree'>{esc(gtree)}</pre></div>"
             f"<div><div class='lbl'>Event tree</div><pre class='tree'>{esc(etree)}</pre></div></div>")

    h.append("<h2>3. การตรวจสอบความถูกต้อง</h2>")
    h.append("<p><b>วิธีตรวจ:</b> อ่านแผนภาพ draw.io ต้นฉบับของแต่ละแบบจำลองด้วยตัวอ่านที่เขียนแยก ไม่ใช้โค้ดของตัวแปลงหรือตัวสกัด "
             "(อ่านกรอบ alt / opt / loop / par เส้นแบ่งกิ่ง ข้อความเงื่อนไข และข้อความตามตำแหน่งบนแผนภาพ) "
             "แล้วคำนวณว่า tree ต้องเป็นอย่างไร เทียบกับ tree ที่สกัดได้ 8 ข้อ "
             "(<code>tools/verify_trees.py</code>)</p>")
    h.append("<table class='keep'><tr><th style='width:7%'>ข้อ</th><th style='width:16%'>เรื่อง</th><th>สิ่งที่ตรวจ</th>"
             "<th style='width:13%'>ผล</th></tr>")
    for code, name, what in CHECKS:
        if code == "C8":
            good = not check["file_errors"]
            cell = "ผ่านทุกไฟล์" if good else f"ผิด {len(check['file_errors'])} จุด"
        else:
            p_, tot = passed(code)
            good, cell = p_ == tot, f"ผ่าน {p_} / {tot}"
        h.append(f"<tr><td>{code}</td><td>{esc(name)}</td><td>{esc(what)}</td>"
                 f"<td class='{'ok' if good else 'bad'}'>{cell}</td></tr>")
    h.append("</table>")
    h.append("<p>C2, C4, C5, C7 ตรวจได้เฉพาะแบบจำลองที่มีแผนภาพ (197 ตัว) · model_001 ตรวจ C1, C3 กับไฟล์ Rodin (.bpo) "
             "· ผลรายแบบจำลองอยู่ใน <code>check.csv</code></p>")
    st = check["selftest"]
    h.append(f"<h3>ทดสอบตัวตรวจ</h3><p>เพื่อยืนยันว่าตัวตรวจจับข้อผิดพลาดได้จริง จงใจทำ tree ที่ถูกต้องให้ผิด {len(st)} แบบ "
             f"แล้วให้ตัวตรวจตรวจซ้ำ · จับได้ <b>{sum(x['caught'] for x in st)} / {len(st)}</b> แบบ</p>"
             "<table><tr><th>ทำให้ผิดแบบ</th><th style='width:16%'>แบบจำลอง</th><th style='width:16%'>จับได้ที่ข้อ</th></tr>"
             + "".join(f"<tr><td>{esc(x['case'])}</td><td>{x['model']}</td>"
                       f"<td class='{'ok' if x['caught'] else 'bad'}'>{x['by'] or 'จับไม่ได้'}</td></tr>" for x in st)
             + "</table>")
    h.append("<h3>ปัญหาที่พบระหว่างตรวจ และการแก้ไข</h3><table><tr><th style='width:30%'>ปัญหา</th><th>สาเหตุ</th>"
             "<th style='width:26%'>การแก้ไข</th></tr>"
             "<tr><td>รหัส event ตรงจุดแยกกิ่งใช้คนละตัวอักษร (model_015, model_036, model_038)</td>"
             "<td>ทางเลือกหนึ่งเป็นจุดรวมของ alt ก่อนหน้า (มีตัวอักษรของตัวเอง) อีกทางเลือกเป็น event นับรอบ loop จึงได้ตัวอักษรใหม่</td>"
             "<td>ปรับกฎ: ทางเลือกอื่นใช้ตัวอักษรของจุดรวม (k1 / k2) · ตรวจซ้ำผ่านทุกแบบจำลอง</td></tr>"
             "<tr><td>model_001 ไม่มี tree ในรอบแรก</td><td>model.txt มีเฉพาะชื่อ event</td>"
             "<td>อ่าน event และ guard จากไฟล์ Rodin (.bpo)</td></tr></table>")

    h.append("<h2>4. ข้อสังเกตจากการตรวจ (พฤติกรรมของสูตรแปลง)</h2><ul>"
             "<li><b>par</b> — สูตรแปลงเรียงข้อความใน par ตามลำดับบนลงล่าง ไม่มี guard ที่ทำให้ทำงานพร้อมกัน event tree จึงเป็นเส้นตรง</li>"
             "<li><b>opt</b> — ข้อความหลัง opt ต้องรอข้อความสุดท้ายใน opt ใน Event-B จึงข้าม opt ไม่ได้ tree ไม่มีกิ่ง “ไม่เข้า opt”</li>"
             "<li><b>loop</b> — ข้อความหลัง loop ต้องรอข้อความสุดท้ายใน loop จึงต้องทำอย่างน้อย 1 รอบ "
             "การวนรอบใหม่แสดงด้วย event นับรอบ (↺)</li>"
             "<li><b>model_001</b> — แปลงด้วยสูตรรุ่นแรก loop และ par ไม่มี guard อ้างข้อความก่อนหน้า tree จึงแยกเป็น 2 กิ่งจาก root "
             "และมี 1 event ที่ไฟล์ Rodin ไม่เก็บชื่อ (unnamed_event_N)</li></ul>"
             "<p>ข้อสังเกตเหล่านี้เป็นคุณสมบัติของแบบจำลองที่แปลงได้ tree แสดงตามแบบจำลองจริง ไม่ได้ปรับให้ต่างจาก Event-B</p>")

    h.append("<h2>5. สถิติ</h2>")
    h.append("<table><tr><th>จำนวนเส้นทางใน guard tree</th>" + "".join(f"<th>{k}</th>" for k in sorted(gp)) + "</tr>"
             "<tr><td>จำนวนแบบจำลอง</td>" + "".join(f"<td class='n'>{gp[k]}</td>" for k in sorted(gp)) + "</tr></table>")
    h.append("<table><tr><th>รายการ</th><th>ต่ำสุด</th><th>มัธยฐาน</th><th>สูงสุด</th><th>รวม</th></tr>"
             + "".join(f"<tr><td>{lbl}</td><td class='n'>{min(v)}</td><td class='n'>{sorted(v)[len(v) // 2]}</td>"
                       f"<td class='n'>{max(v)}</td><td class='n'>{sum(v):,}</td></tr>"
                       for lbl, v in (("event ต่อแบบจำลอง", ev),
                                      ("เส้นทางใน event tree", [s["event_paths"] for s in stats]),
                                      ("รหัส guard ต่อแบบจำลอง", [s["guard_codes"] for s in stats]),
                                      ("loop ต่อแบบจำลอง", [s["loops"] for s in stats])))
             + "</table>")
    h.append(f"<p>แบบจำลองที่ไม่มีเงื่อนไขจากแผนภาพ {gp[0]} ตัว มีเฉพาะ event tree (guard tree ว่าง)</p>")

    h.append("<h2>6. ไฟล์</h2>")
    tree = ["EventB_PO_Training/",
            "├── trees/",
            "│   ├── SUMMARY.pdf          ← เอกสารนี้",
            "│   ├── TREES.pdf            ← หลักการ ตัวอย่าง และรหัส + tree ของทุกแบบจำลอง",
            "│   ├── guard_codes.csv      ← รหัส guard ทุกแบบจำลอง (model_id, code, guard)",
            "│   ├── event_codes.csv      ← รหัส event ทุกแบบจำลอง (model_id, code, event, guards)",
            "│   ├── tree_summary.csv     ← ตัวเลขต่อแบบจำลอง + เส้นทาง guard + ผลตรวจ",
            "│   ├── check.csv            ← ผลตรวจรายแบบจำลอง",
            "│   └── by_topic/<หัวข้อ>/<pass|fail>/<model>.txt   ← tree ของแต่ละแบบจำลอง (รูปย่อ + รูปเต็ม)",
            "├── models/<id>/tree.txt · tree.json   ← ชุดเดียวกัน อยู่คู่กับ model.txt",
            "└── data/trees.jsonl                  ← ทุกแบบจำลองในไฟล์เดียว (สำหรับโปรแกรม)"]
    h.append("<pre>" + esc("\n".join(tree)) + "</pre>")
    h.append("<p>สร้างใหม่ทั้งหมดด้วย <code>python tools/make_release.py</code> (สกัด → ตรวจ → สร้างเอกสาร) · "
             "ตัวสกัด <code>tools/extract_trees.py</code> · ตัวตรวจ <code>tools/verify_trees.py</code></p>")

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
