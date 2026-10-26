"""Build by_result/pass and by_result/fail — a browsing view of models/ split by the
Rodin label (failed == 0 -> pass). For looking at the data only: the folder name is
the answer, so never feed by_result/ paths or names to a model being evaluated.

    python tools/make_by_result.py        (run after tools/rebuild_labels.py)
"""
import glob, json, os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "by_result")

README = """by_result/ — แยก model ตามผลจาก Rodin เพื่อเปิดดูเท่านั้น

pass/  = model ที่ PO discharge ครบ (failed = 0)
fail/  = model ที่มี PO พิสูจน์ไม่ได้อย่างน้อย 1 ข้อ (failed > 0)

ชื่อโฟลเดอร์ = <model_id>_<case>  ข้างในเป็นสำเนาของ models/<model_id>/
ผ่าน/ไม่ผ่านอ่านจาก models/<model_id>/label.json (prover: Rodin 3.9 + Atelier B ML/PP)

ห้ามใช้โฟลเดอร์นี้ (หรือชื่อโฟลเดอร์ pass/fail) เป็นข้อมูล train หรือ input ของ LLM
เพราะชื่อโฟลเดอร์คือเฉลย — สำหรับ train ให้ใช้ dataset.jsonl

สร้างใหม่ได้ด้วย: python tools/make_by_result.py
"""


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    counts = {"pass": 0, "fail": 0}
    lines = ["model_id,case,result,failed,total_po"]
    for mdir in sorted(glob.glob(os.path.join(ROOT, "models", "model_*"))):
        mid = os.path.basename(mdir)
        label = json.load(open(os.path.join(mdir, "label.json")))
        result = "pass" if label["failed"] == 0 else "fail"
        safe_case = re.sub(r"[^A-Za-z0-9]+", "_", label["case"]).strip("_")
        shutil.copytree(mdir, os.path.join(OUT, result, f"{mid}_{safe_case}"))
        counts[result] += 1
        lines.append(f"{mid},{label['case']},{result},{label['failed']},{label['total_po']}")
    with open(os.path.join(OUT, "README.txt"), "w", encoding="utf-8") as f:
        f.write(README)
    with open(os.path.join(OUT, "pass_fail_list.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"by_result/: pass {counts['pass']} | fail {counts['fail']}")


if __name__ == "__main__":
    main()
