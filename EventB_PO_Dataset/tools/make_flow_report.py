"""Build a Thai PDF that shows the dataset workflow as a flow chart.

    python tools/make_flow_report.py [--batch all_197]

Writes batches/<batch>/FLOW_<batch>.pdf in the same style as README_<batch>.pdf.
"""
import argparse, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_batch_report import CHROME, CSS, DATASET, collect, esc   # noqa: E402

# (phase, title, detail, where, command/output); "now" marks the step the batch is waiting at
STEPS = [
    ("gen", "1. สร้าง sequence diagram",
     "pass: diagram ถูก · fail: ใส่จุดผิดใน diagram (ช่วงเวลากลับด้าน หรือ mod กับตัวนับ loop)",
     "Mac", "gen_batch.py · redo_round1.py → .drawio.xml"),
    ("gen", "2. อ่าน diagram กลับมาตรวจ",
     "ผู้ส่ง ผู้รับ data เวลา เงื่อนไข ต้องตรงกับที่ตั้งใจ — ไม่ตรง → ทิ้งแล้วสุ่มใหม่ (กลับไปข้อ 1)",
     "Mac", "check_parse() ใน gen_batch.py"),
    ("gen", "3. แปลงด้วย ChronoSeq-B",
     "ใช้สูตรแปลงตามปกติ ไม่แก้ Event-B ภายหลัง แล้วคำนวณ PO ที่คาดว่าจะล้ม",
     "Mac", "→ _EventB.txt · _Rodin.zip · meta.json"),
    ("gen", "4. จัด folder",
     "แยกตามหัวข้อ และ pass / fail · รวม Rodin project เป็น zip เดียว · ทำ PDF อธิบาย",
     "Mac", "organize_batches.py → batches/all_197/"),
    ("rodin", "5. พิสูจน์ด้วย Rodin",
     "import zip → auto-prover (Atelier B ML/PP) รันจนครบ → zip workspace ส่งกลับ",
     "Windows", "Rodin 3.9 + Atelier B"),
    ("data", "6. รวมผลเข้า dataset",
     "อ่านผลจาก .bps ของแต่ละ PO · รอบแรกใช้ ID เดิม ชุดใหม่ได้ model_049–198",
     "Mac", "integrate_batch.py → models/ · sources/ · rodin_raw/"),
    ("data", "7. เทียบผล Rodin กับที่ออกแบบ",
     "ตรงกัน → ใช้ได้ · ไม่ตรง → ดูว่า PO ไหนต่าง แล้วตรวจ diagram / สูตรแปลง",
     "Mac", "rebuild_labels.py"),
    ("data", "8. ได้ dataset",
     "label ของทุกโมเดล (total / discharged / failed + ราย PO) · แยก folder ตามผลจริง · ตารางหัวข้อ",
     "Mac", "dataset.jsonl · by_result/ · model_categories.csv"),
    ("llm", "9. ใช้กับ LLM",
     "input = model.txt (+ features) · output = จำนวน PO ที่พิสูจน์ได้ · เทียบกับ label",
     "—", "ห้ามใช้ meta.json · sources/ · rodin_raw/ เป็น input"),
]
PHASE = {"gen": ("สร้างโมเดล", "#2b6cb0", "#e8f0fb"), "rodin": ("พิสูจน์", "#c26a00", "#fdf1e2"),
         "data": ("ทำ dataset", "#2e7d5b", "#e6f4ec"), "llm": ("ใช้งาน", "#6b46c1", "#efeafb")}
NOW = 5   # the batch is waiting for Rodin

EXTRA_CSS = """
.legend span { display: inline-block; margin-right: 14px; font-size: 9.4pt; }
.legend i { display: inline-block; width: 11px; height: 11px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
.flow { display: flex; flex-direction: column; align-items: center; margin: 8px 0 4px; }
.step { width: 100%; border: 1.5px solid; border-radius: 6px; padding: 3px 12px 4px; display: grid;
        grid-template-columns: 1fr auto; gap: 1px 12px; break-inside: avoid; position: relative; }
.step .t { font-weight: bold; font-size: 10.8pt; }
.step .w { font-size: 8.4pt; color: #5a6475; text-align: right; white-space: nowrap; }
.step .d { font-size: 9.2pt; grid-column: 1 / 3; line-height: 1.45; }
.step .c { font-family: "Menlo", monospace; font-size: 7.8pt; color: #3c4658; grid-column: 1 / 3; line-height: 1.4; }
.step.now { box-shadow: 0 0 0 3px #f2c94c; }
.now-tag { position: absolute; right: -2px; top: -11px; background: #f2c94c; color: #1d2433; font-size: 8pt;
           font-weight: bold; padding: 1px 7px; border-radius: 9px; }
.arrow { color: #8a93a3; font-size: 9pt; line-height: 1; margin: 1px 0; }
.lane { font-size: 8.4pt; color: #5a6475; margin: 0; line-height: 1.3; }
.pipe { display: grid; grid-template-columns: 1fr 18px 1fr 18px 1fr; align-items: center; gap: 0; margin: 6px 0 12px; }
.pipe .b { border: 1.5px solid #cfd6e1; border-radius: 6px; padding: 6px 8px; font-size: 9.2pt; min-height: 58px; }
.pipe .b .h { font-size: 8.4pt; color: #5a6475; }
.pipe .x { text-align: center; color: #8a93a3; font-size: 13pt; }
.pipe .bad { border-color: #c0392b; background: #fdecea; }
"""


def step_html(k, phase, title, detail, where, cmd):
    _, line, fill = PHASE[phase]
    now = k == NOW
    return (f"<div class='step{' now' if now else ''}' style='border-color:{line};background:{fill}'>"
            + ("<span class='now-tag'>ตอนนี้อยู่ตรงนี้</span>" if now else "")
            + f"<span class='t' style='color:{line}'>{esc(title)}</span><span class='w'>ทำที่: {esc(where)}</span>"
            f"<span class='d'>{esc(detail)}</span><span class='c'>{esc(cmd)}</span></div>")


def render(batch, rows):
    n_pass = sum(r["result"] == "pass" for r in rows)
    h = [f"<h1>ขั้นตอนการทำ dataset</h1>",
         f"<div class='sub'>{esc(batch)} · {len(rows)} โมเดล · pass {n_pass} / fail {len(rows) - n_pass} "
         "· ตอนนี้รอผลจาก Rodin</div>"]
    h.append("<div class='legend'>" + "".join(
        f"<span><i style='background:{line}'></i>{esc(name)}</span>" for name, line, _ in PHASE.values()) + "</div>")

    h.append("<h2 style='margin-top:12px'>1. ภาพรวม</h2><div class='flow'>")
    for k, s in enumerate(STEPS, start=1):
        if k > 1:
            h.append("<div class='arrow'>▼</div>")
        if k == 5:
            h.append("<div class='lane'>— ส่ง Rodin_Import_all_197.zip ไปเครื่อง Windows —</div>")
        if k == 6:
            h.append("<div class='lane'>— ส่ง workspace ที่พิสูจน์แล้วกลับมา —</div>")
        h.append(step_html(k, *s))
    h.append("</div>")

    h.append("<h2 style='break-before:page'>2. โมเดล fail เกิดขึ้นอย่างไร</h2>")
    h.append("<p>จุดผิดอยู่ใน <b>diagram</b> เท่านั้น สูตรแปลงทำงานตามปกติ แล้ว PO ข้อที่เกี่ยวข้องจะพิสูจน์ไม่ได้</p>")
    for diagram, eventb, po in [
        ("<code>notify() {5..3}</code><br>ช่วงเวลากลับด้าน (5 &gt; 3)",
         "<code>t_time_i :∈ 5..3</code><br>ไม่มีค่าให้เลือก", "<b>FIS ล้ม</b><br><code>INITIALISATION/actN/FIS</code>"),
        ("loop <code>[retryNo &lt; 5]</code><br>+ alt/opt <code>[retryNo mod 2 == 0]</code>",
         "guard <code>retryNo mod 2 = 0</code><br>แต่ invariant มีแค่ <code>retryNo ∈ ℤ</code>",
         "<b>WD ล้ม</b> (ต้องรู้ว่า retryNo ≥ 0)<br><code>sendX/grdN/WD</code>"),
    ]:
        h.append("<div class='pipe'>"
                 f"<div class='b'><div class='h'>ใน diagram</div>{diagram}</div><div class='x'>▶</div>"
                 f"<div class='b'><div class='h'>สูตรแปลงได้</div>{eventb}</div><div class='x'>▶</div>"
                 f"<div class='b bad'><div class='h'>Rodin</div>{po}</div></div>")
    h.append("<p>INV ไม่ล้มจาก diagram เพราะสูตรแปลงสร้างแค่ invariant บอกชนิดข้อมูลกับ "
             "<code>inv5: receivedMessages ⊆ sentMessages</code> และใส่ guard รองรับ inv5 ให้เองเสมอ</p>")

    h.append("<h2>3. แต่ละขั้นใช้อะไร ได้อะไร</h2>")
    h.append("<table><tr><th style='width:22%'>ขั้น</th><th style='width:10%'>ทำที่</th><th>เครื่องมือ / ไฟล์ที่ได้</th></tr>")
    for phase, title, _, where, cmd in STEPS:
        h.append(f"<tr><td>{esc(title)}</td><td>{esc(where)}</td><td class='mono'>{esc(cmd)}</td></tr>")
    h.append("</table>")
    h.append("<p>script ทั้งหมดอยู่ใน <code>EventB_PO_Dataset/tools/</code> (ตัวสร้างโมเดลอยู่ใน <code>tools/generators/</code>)</p>")
    return (f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{CSS}{EXTRA_CSS}</style></head>"
            f"<body>{''.join(h)}</body></html>")


def main(batch):
    bdir = os.path.join(DATASET, "batches", batch)
    out = os.path.join(bdir, f"FLOW_{batch}.pdf")
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "flow.html")
        open(page, "w").write(render(batch, collect(bdir)))
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", f"file://{page}"], check=True, capture_output=True)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="all_197")
    main(ap.parse_args().batch)
