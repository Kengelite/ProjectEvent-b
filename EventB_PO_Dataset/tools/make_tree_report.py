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
.paths { font-family: Menlo, monospace; font-size: 7.6pt; line-height: 1.4; overflow-wrap: anywhere; }
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
    codes = "<br>".join(f"<b>{c}</b> {esc(n)}" + (f" [{' '.join(t['event_guards'][c])}]" if t["event_guards"][c] else "")
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
    h.append("<div class='rule'><b>การสร้าง tree</b><br>"
             "• <b>Event tree</b>: send m → receive m และ receive p → send m เมื่อ send m มี guard "
             "<code>p ∈ receivedMessages</code> · alt แตกเป็นหลายกิ่ง · หลัง alt ที่มี guard แบบ "
             "<code>p ∈ receivedMessages ∨ q ∈ receivedMessages</code> ทุกกิ่งต่อด้วย event เดียวกัน · "
             "event นับรอบ loop (checkloop) อยู่ท้าย loop และมีลูกศร ↺ กลับไปจุดเริ่ม loop · event ใช้รหัส e1, e2 … ตามลำดับในไฟล์<br>"
             "• ในเอกสารนี้ event tree แสดงแบบย่อ: event ที่ต่อกันเป็นเส้นตรงเขียนในบรรทัดเดียว (e1 → e2 → e3) "
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
             "<code>tree.json</code> · รวมทุกแบบจำลอง: <code>data/trees.jsonl</code>, <code>csv/guard_codes.csv</code> · "
             "<b>model_001</b>: model.txt มีเฉพาะชื่อ event จึงอ่าน event และ guard จากไฟล์ proof obligation ของ Rodin (.bpo) แทน · "
             "มี 1 event ที่ไฟล์ Rodin ไม่เก็บชื่อไว้ (แสดงเป็น unnamed_event_N, guard <code>retry &lt; 3</code>) · "
             "แบบจำลองนี้แปลงด้วยสูตรรุ่นแรก ส่วน loop และ par จึงไม่มี guard อ้างข้อความก่อนหน้า event tree จึงแยกเป็นหลายกิ่งจาก root</p>")

    h.append("<h2 style='break-before:page'>4. รหัสและเส้นทางของแต่ละแบบจำลอง</h2>")
    h.append("<p>ซ้าย: รหัส guard, guard tree และเส้นทาง · ขวา: รหัส event (ในวงเล็บคือ guard ของ event นั้น), "
             "event tree แบบย่อ และเส้นทาง · ↺ eN = จบรอบ loop แล้วกลับไปที่ eN</p>")
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
