"""Build a Thai PDF listing every model of a staged folder by topic.

    python tools/make_topic_report.py [--batch all_197]

Writes batches/<batch>/TOPICS_<batch>.pdf in the same style as README_<batch>.pdf.
"""
import argparse, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from categorize import TOPIC_NAMES                                     # noqa: E402
from make_batch_report import CHROME, CSS, DATASET, collect, esc       # noqa: E402

ABOUT = {
    "FIN": "ชำระเงิน โอนเงิน บัตร บัญชี และการยืนยันตัวตนทางการเงิน",
    "HEA": "โรงพยาบาล นัดหมาย จ่ายยา ห้องแล็บ และการแพทย์ทางไกล",
    "TRA": "รถโดยสาร แท็กซี่ สนามบิน ที่จอดรถ และระบบจราจร",
    "LOG": "พัสดุ คลังสินค้า การติดตามสินค้า และห่วงโซ่อุปทาน",
    "HOME": "อุปกรณ์ในบ้าน ประตู ไฟ ลิฟต์ และระบบอาคาร",
    "IND": "โรงงาน หุ่นยนต์ พลังงาน เซนเซอร์ และโครงสร้างพื้นฐาน",
    "RET": "ร้านค้า สั่งอาหาร ตู้ขายของ และการซื้อของออนไลน์",
    "BOOK": "จองห้อง ตั๋ว โรงแรม ร้านอาหาร และงานกิจกรรม",
    "EDU": "การเรียน การสอบ ห้องสมุด และบริการภาครัฐ",
    "IT": "การล็อกอิน เซิร์ฟเวอร์ แชท และบริการออนไลน์",
    "AGR": "ฟาร์ม การให้น้ำ ปศุสัตว์ และการเฝ้าระวังสิ่งแวดล้อม",
}
TYPE_TH = {"inverted1": "ช่วงเวลากลับด้าน 1 จุด", "inverted2": "ช่วงเวลากลับด้าน 2 จุด",
           "inverted3": "ช่วงเวลากลับด้าน 3 จุด", "inverted_frame": "ช่วงเวลากลับด้านใน fragment",
           "mod_alt": "mod กับตัวนับ loop (alt)", "mod_opt": "mod กับตัวนับ loop (opt)",
           "mod_inverted": "ช่วงเวลากลับด้าน + mod"}

EXTRA_CSS = """
.bar { display: inline-block; height: 9px; vertical-align: middle; }
.bar.p { background: #2e7d5b; } .bar.f { background: #c0392b; }
td.res-pass { color: #2e7d5b; font-weight: bold; } td.res-fail { color: #c0392b; font-weight: bold; }
.about { color: #5a6475; margin: 0 0 6px; break-after: avoid; }
"""


def render(batch, rows):
    codes = list(TOPIC_NAMES)
    dirs = sorted({r["topic_dir"] for r in rows})
    n_pass = sum(r["result"] == "pass" for r in rows)
    h = [f"<h1>หัวข้อของโมเดล ({esc(batch)})</h1>",
         f"<div class='sub'>{len(rows)} โมเดล · {len(dirs)} หัวข้อ · pass {n_pass} / fail {len(rows) - n_pass} "
         "· pass/fail คือผลที่ออกแบบไว้ ยังไม่ได้รัน Rodin</div>"]

    h.append("<h2>1. สรุปทุกหัวข้อ</h2>")
    h.append("<table><tr><th>#</th><th>หัวข้อ</th><th>English</th><th>pass</th><th>fail</th><th>รวม</th>"
             "<th style='width:22%'>สัดส่วน</th></tr>")
    for k, d in enumerate(dirs):
        en, th = TOPIC_NAMES[codes[k]]
        p = sum(r["topic_dir"] == d and r["result"] == "pass" for r in rows)
        f = sum(r["topic_dir"] == d and r["result"] == "fail" for r in rows)
        bar = (f"<span class='bar p' style='width:{p * 4}px'></span>"
               f"<span class='bar f' style='width:{f * 4}px'></span>")
        h.append(f"<tr><td>{k + 1:02d}</td><td>{esc(th)}</td><td>{esc(en)}</td><td class='n'>{p}</td>"
                 f"<td class='n'>{f}</td><td class='n'>{p + f}</td><td>{bar}</td></tr>")
    h.append(f"<tr><th></th><th>รวม</th><th></th><th class='n'>{n_pass}</th><th class='n'>{len(rows) - n_pass}</th>"
             f"<th class='n'>{len(rows)}</th><th></th></tr></table>")
    h.append("<p><span class='bar p' style='width:12px'></span> pass &nbsp; "
             "<span class='bar f' style='width:12px'></span> fail — "
             "สัดส่วนรวมเป็น 60:40 แต่บางหัวข้อไม่ถึง เพราะตอนสร้างสุ่มว่าตัวไหนเป็น fail โดยไม่ได้ดูหัวข้อ</p>")
    h.append("<p>หัวข้อของแต่ละโมเดลอยู่ใน <code>model_categories.csv</code> (คอลัมน์ topic / topic_th) "
             "แก้ได้ที่ <code>TOPIC</code> ใน <code>tools/categorize.py</code></p>")

    h.append("<h2>2. รายชื่อโมเดลในแต่ละหัวข้อ</h2>")
    h.append("<p>ID มีเฉพาะโมเดลรอบแรก (model_002–048) — ชุดใหม่จะได้ ID หลังรวมผล Rodin</p>")
    for k, d in enumerate(dirs):
        en, th = TOPIC_NAMES[codes[k]]
        group = sorted((r for r in rows if r["topic_dir"] == d),
                       key=lambda r: (r["result"] != "pass", r["meta"]["case"].lower()))
        h.append(f"<h3>{k + 1:02d} {esc(th)} · {esc(en)} ({len(group)})</h3>")
        h.append(f"<p class='about'>{esc(ABOUT[codes[k]])}</p>")
        h.append("<table><tr><th style='width:13%'>ID</th><th style='width:32%'>โมเดล</th><th style='width:9%'>ผล</th>"
                 "<th>จุดผิดใน diagram</th><th style='width:11%'>PO ที่ล้ม</th></tr>")
        for r in group:
            m = r["meta"]
            res = r["result"]
            h.append(f"<tr><td>{esc(m.get('model_id', '–'))}</td><td>{esc(m['case'])}</td>"
                     f"<td class='res-{res}'>{res}</td><td>{esc(TYPE_TH.get(m.get('mutation_type'), '–'))}</td>"
                     f"<td class='n'>{m['expected_failed_count'] or '–'}</td></tr>")
        h.append("</table>")
    return (f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{CSS}{EXTRA_CSS}</style></head>"
            f"<body>{''.join(h)}</body></html>")


def main(batch):
    bdir = os.path.join(DATASET, "batches", batch)
    out = os.path.join(bdir, f"TOPICS_{batch}.pdf")
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "topics.html")
        open(page, "w").write(render(batch, collect(bdir)))
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", f"file://{page}"], check=True, capture_output=True)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="all_197")
    main(ap.parse_args().batch)
