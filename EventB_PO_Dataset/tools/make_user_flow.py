"""Draw the workflow as a user-flow diagram (start, steps, yes/no decisions, end).

    python tools/make_user_flow.py [--release ../EventB_PO_Training]

Numbers come from <release>/data/dataset.jsonl. Writes FLOW.pdf and FLOW.png into the
release folder.
"""
import argparse, html, json, os, subprocess, tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1560, 1060
INK, MUTED, LINE = "#1f2a44", "#6b7489", "#8a93a3"
BOX, DIA, START, END, BADGE = "#8b8ff5", "#8de8cf", "#3b33a6", "#5fcf8e", "#2f5fa8"
FONT = "Thonburi, 'Sukhumvit Set', sans-serif"


def t(x, y, s, size=15, fill=INK, weight="normal", anchor="start"):
    return (f"<text x='{x}' y='{y}' font-size='{size}' fill='{fill}' font-weight='{weight}' "
            f"text-anchor='{anchor}' font-family=\"{FONT}\">{html.escape(s)}</text>")


def box(cx, cy, num, title, subs):
    out = [f"<rect x='{cx - 120}' y='{cy - 45}' width='240' height='90' rx='12' fill='{BOX}'/>",
           f"<rect x='{cx - 108}' y='{cy - 35}' width='40' height='24' rx='6' fill='#ffffff'/>",
           t(cx - 88, cy - 17, num, 14, BADGE, "bold", "middle")]
    lines = title.split("\n")
    y0 = cy + 18 if len(lines) == 1 else cy + 8
    out += [t(cx, y0 + 22 * k, line, 17, "#ffffff", "bold", "middle") for k, line in enumerate(lines)]
    out += [t(cx - 118, cy + 72 + 22 * k, "· " + s, 14, MUTED) for k, s in enumerate(subs)]
    return "".join(out)


def diamond(cx, cy, text):
    pts = f"{cx},{cy - 72} {cx + 92},{cy} {cx},{cy + 72} {cx - 92},{cy}"
    lines = text.split("\n")
    y0 = cy + 6 - 11 * (len(lines) - 1)
    return (f"<polygon points='{pts}' fill='{DIA}'/>"
            + "".join(t(cx, y0 + 22 * k, line, 16, "#134e3f", "bold", "middle") for k, line in enumerate(lines)))


def pill(cx, cy, text, fill):
    lines = text.split("\n")
    y0 = cy + 7 - 11 * (len(lines) - 1)
    return (f"<rect x='{cx - 95}' y='{cy - 34}' width='190' height='68' rx='34' fill='{fill}'/>"
            + "".join(t(cx, y0 + 22 * k, line, 18, "#ffffff", "bold", "middle") for k, line in enumerate(lines)))


def arrow(pts, label=None, at=None, yes=True):
    d = " ".join(f"{x},{y}" for x, y in pts)
    out = f"<polyline points='{d}' fill='none' stroke='{LINE}' stroke-width='2' marker-end='url(#head)'/>"
    if label:
        x, y = at
        fill, ink = ("#e3f6ea", "#2e7d5b") if yes else ("#fbe4e2", "#b23a2e")
        w = 22 + 15 * len(label)
        out += (f"<rect x='{x - w / 2}' y='{y - 15}' width='{w}' height='30' rx='15' fill='{fill}'/>"
                + t(x, y + 6, ("✓ " if yes else "✕ ") + label, 15, ink, "bold", "middle"))
    return out


def note(x, y, w, lines):
    h = 20 + 24 * len(lines)
    return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='10' fill='#eef2fb' stroke='#c9d5ee' stroke-width='1.5'/>"
            + "".join(t(x + 16, y + 32 + 24 * k, s, 15, "#2a3f6b") for k, s in enumerate(lines)))


def svg(stats):
    s = stats
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
             "<defs><marker id='head' markerWidth='10' markerHeight='10' refX='9' refY='5' orient='auto'>"
             f"<path d='M0,0 L10,5 L0,10 z' fill='{LINE}'/></marker></defs>",
             f"<rect width='{W}' height='{H}' fill='#ffffff'/>",
             t(40, 46, "ขั้นตอนการดำเนินงาน", 15, "#3b33a6", "bold"),
             t(40, 84, "การจัดทำชุดข้อมูล Proof Obligation จาก Sequence Diagram", 26, INK, "bold")]

    # row 1: left to right
    y1 = 240
    parts += [pill(130, y1, "เริ่มต้น", START),
              box(400, y1, "1", "สร้าง\nSequence Diagram", ["สร้างอัตโนมัติ (ไฟล์ draw.io) 11 หัวข้อ", "กรณีไม่ผ่าน: กำหนดจุดผิดในแผนภาพ"]),
              box(720, y1, "2", "ตรวจสอบแผนภาพ", ["ผู้ส่ง ผู้รับ และข้อมูล", "เงื่อนไขเวลาและเงื่อนไขควบคุม"]),
              diamond(1010, y1, "โครงสร้าง\nถูกต้อง?"),
              box(1290, y1, "3", "แปลงเป็น\nแบบจำลอง Event-B", ["ใช้เครื่องมือ ChronoSeq-B", "ไม่แก้ไขผลลัพธ์ภายหลัง"])]
    parts += [arrow([(225, y1), (276, y1)]), arrow([(520, y1), (596, y1)]), arrow([(840, y1), (914, y1)]),
              arrow([(1010, y1 - 72), (1010, y1 - 105), (400, y1 - 105), (400, y1 - 49)], "ไม่ใช่", (705, y1 - 105), yes=False),
              arrow([(1102, y1), (1166, y1)], "ใช่", (1134, y1 - 40))]

    # row 2: right to left
    y2 = 520
    parts += [box(1290, y2, "4", "จัดกลุ่มแบบจำลอง", ["แยกตามหัวข้อและผลที่คาดหวัง", "รวมโปรเจกต์เป็นไฟล์เดียว"]),
              box(960, y2, "5", "พิสูจน์ด้วย Rodin", ["ตัวพิสูจน์ Atelier B (ML/PP)", f"รวม {s['po']:,} Proof Obligation"]),
              diamond(630, y2, "พิสูจน์ครบ\nทุกโปรเจกต์?"),
              box(290, y2, "6", "สรุปผลราย PO", ["จำนวนทั้งหมด / ผ่าน / ไม่ผ่าน", "ระบุ PO ที่พิสูจน์ไม่ได้"])]
    parts += [arrow([(1410, y1), (1470, y1), (1470, y2), (1414, y2)]),
              arrow([(1170, y2), (1084, y2)]), arrow([(840, y2), (726, y2)]),
              arrow([(630, y2 - 72), (630, y2 - 120), (960, y2 - 120), (960, y2 - 49)], "ไม่ใช่ · ดำเนินการต่อ", (795, y2 - 120), yes=False),
              arrow([(538, y2), (414, y2)], "ใช่", (476, y2 - 38))]

    # row 3: left to right
    y3 = 840
    parts += [diamond(290, y3, "ผลตรงตาม\nที่ออกแบบ?"),
              box(620, y3, "7", "จัดทำชุดข้อมูล", [f"{s['models']} แบบจำลอง", "แบบจำลอง Event-B พร้อม label"]),
              box(950, y3, "8", "แบ่งชุดข้อมูล", [f"train / val / test = {s['train']} / {s['val']} / {s['test']}",
                                                   "คงสัดส่วนผ่าน / ไม่ผ่าน"]),
              pill(1290, y3, "ฝึกและประเมิน\nโมเดล AI", END)]
    parts += [arrow([(170, y2), (110, y2), (110, y3), (194, y3)]),
              arrow([(382, y3), (496, y3)], "ใช่", (440, y3 - 38)),
              arrow([(740, y3), (826, y3)]), arrow([(1070, y3), (1191, y3)]),
              arrow([(290, y3 + 72), (290, y3 + 118)], "ไม่ใช่", (348, y3 + 96), yes=False),
              note(150, y3 + 122, 490, ["ตรวจสอบแผนภาพและกฎการแปลง แล้วเริ่มขั้นตอนที่ 1 ใหม่"])]

    # notes
    parts += [note(150, y1 + 112, 470, ["จุดผิดในแผนภาพที่ทำให้ PO พิสูจน์ไม่ได้",
                                   "· ช่วงเวลากลับด้าน เช่น {5..3}  →  FIS",
                                   "· ใช้ mod กับตัวนับ loop  →  WD"]),
              note(810, y2 + 122, 650, ["PO ประเภท INV พิสูจน์ผ่านเสมอ เนื่องจากกฎการแปลงสร้าง guard รองรับไว้",
                                   "ทุกแบบจำลองใช้ตัวพิสูจน์ชุดเดียวกัน (Atelier B ML/PP)"]),
              note(1060, y3 + 92, 470, [f"ผลลัพธ์: ผ่าน {s['pass']} / ไม่ผ่าน {s['fail']} แบบจำลอง",
                                    f"PO ไม่ผ่าน {s['failed']} จาก {s['po']:,} ข้อ ตรงตามที่ออกแบบทั้งหมด"])]
    parts.append("</svg>")
    return "".join(parts)


def stats(release):
    rows = [json.loads(l) for l in open(os.path.join(release, "data", "dataset.jsonl"))]
    sp = Counter(r["split"] for r in rows)
    return {"models": len(rows), "po": sum(r["total_po"] for r in rows), "failed": sum(r["failed"] for r in rows),
            "pass": sum(r["failed"] == 0 for r in rows), "fail": sum(r["failed"] > 0 for r in rows),
            "train": sp["train"], "val": sp["val"], "test": sp["test"]}


def main(release):
    page = (f"<!doctype html><html><head><meta charset='utf-8'><style>@page {{ size: {W}px {H}px; margin: 0 }} "
            f"html, body {{ margin: 0; background: #fff }} svg {{ display: block }}</style></head>"
            f"<body>{svg(stats(release))}</body></html>")
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "flow.html")
        open(p, "w").write(page)
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.join(release, 'FLOW.pdf')}", f"file://{p}"], check=True, capture_output=True)
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                        "--force-device-scale-factor=2", f"--screenshot={os.path.join(release, 'FLOW.png')}",
                        f"file://{p}"], check=True, capture_output=True)
    print(os.path.join(release, "FLOW.pdf"), os.path.join(release, "FLOW.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default=os.path.join(os.path.dirname(DATASET), "EventB_PO_Training"))
    main(os.path.abspath(ap.parse_args().release))
