"""Package the labelled dataset into a clean training folder.

    python tools/make_release.py [--out ../EventB_PO_Training] [--seed 20261026]

Output (rebuilt from scratch each run):
    README.pdf                  Thai summary: numbers, what to upload, structure, caveats
    upload/train.jsonl          chat-format records to fine-tune on
    upload/val.jsonl            chat-format records for validation during training
    upload/test.jsonl           chat-format records kept out of training (evaluation only)
    data/dataset.jsonl          one row per model: model text, features, labels, topic, split
    data/po_details.jsonl       one row per proof obligation
    data/split.csv              model_id -> train / val / test
    csv/summary.csv             per-model numbers (features + labels + topic + split)
    csv/pass_fail_list.csv      per-model pass / fail
    csv/model_categories.csv    topic, diagram error, expected vs Rodin (analysis only)
    models/model_XXX/           model.txt, label.json, po_details.json, features.json
    by_topic/<NN_Topic>/<pass|fail>/<model_XXX_Case>/   the same models grouped by topic and
                                Rodin result, with a list.csv per topic
    FLOW.pdf, FLOW.png          workflow diagram (tools/make_user_flow.py)
    SOURCES.md                  provenance (tools, versions, dates) and references

Nothing that reveals the answer (meta.json, diagrams, Rodin files) is copied into the
inputs. The split is stratified by result and by kind of failing PO; model_001 (the
reconstructed Payment case kept for testing) always goes to test.
"""
import argparse, csv, glob, hashlib, html, json, os, shutil, statistics, subprocess, sys, tempfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from categorize import TOPIC, TOPIC_NAMES                       # noqa: E402
from make_batch_report import CHROME, CSS, esc                  # noqa: E402
import make_user_flow                                           # noqa: E402

SPLIT = (("train", 0.70), ("val", 0.15), ("test", 0.15))
PROJECT = os.path.dirname(DATASET)
CONVERTER_REPO = "https://github.com/Kengelite/ProjectEvent-b"
# (provenance item, detail) — Thai, shown in README.pdf and SOURCES.md
PROVENANCE = [
    ("แผนภาพต้นทาง", "Sequence Diagram 197 แบบจำลอง สร้างด้วย draw.io (ไฟล์ .drawio.xml) ครอบคลุม 11 หัวข้อ "
                    "และ model_001 Payment & Notification ซึ่งเป็นกรณีทดสอบจากงานเดิม"),
    ("การแปลง", "ChronoSeq-B ({repo}) commit {commit} — แปลงแผนภาพเป็น Event-B และ Rodin project "
                "โดยไม่แก้ไขผลลัพธ์ภายหลัง"),
    ("การพิสูจน์", "Rodin Platform บน Windows (Eclipse platform 4.23) ร่วมกับ Atelier B provers plugin — "
                   "ใน proof file พบ reasoner com.clearsy.atelierb.provers.core.externalML และ externalPP"),
    ("ช่วงเวลาพิสูจน์", "รอบแรก 1–2 ตุลาคม 2026 (26 แบบจำลองที่ไม่เปลี่ยน ใช้ผลรอบนี้) · รอบหลัก 26 ตุลาคม 2026"),
    ("การอ่านผล", "อ่านสถานะจากไฟล์ .bps: PO ผ่านเมื่อ confidence = 1000 และ proof ไม่อยู่ในสถานะ broken"),
    ("เครื่องมือประมวลผล", "Python {python} · script ใน EventB_PO_Dataset/tools/ ({repo})"),
]
REFERENCES = [
    "Abrial, J.-R. (2010). <i>Modeling in Event-B: System and Software Engineering</i>. Cambridge University Press.",
    "Abrial, J.-R., Butler, M., Hallerstede, S., Hoang, T. S., Mehta, F., & Voisin, L. (2010). Rodin: An open toolset "
    "for modelling and reasoning in Event-B. <i>International Journal on Software Tools for Technology Transfer, 12</i>(6), "
    "447–466. https://doi.org/10.1007/s10009-010-0145-y",
    "Event-B and the Rodin Platform. https://www.event-b.org/",
    "CLEARSY. Atelier B (provers ML and PP, Rodin plugin). https://www.atelierb.eu/",
    "Object Management Group. (2017). <i>OMG Unified Modeling Language (UML), Version 2.5.1</i>. https://www.omg.org/spec/UML/2.5.1",
    "draw.io (diagrams.net). https://www.drawio.com/",
    "ChronoSeq-B — Sequence Diagram to Event-B converter. " + CONVERTER_REPO,
    "OpenAI. Fine-tuning guide (chat-format training data). https://platform.openai.com/docs/guides/fine-tuning",
    "Hugging Face. TRL — SFTTrainer. https://huggingface.co/docs/trl/sft_trainer",
]


def provenance():
    commit = subprocess.run(["git", "-C", PROJECT, "log", "-1", "--format=%h (%ad)", "--date=short", "main", "--",
                             "eventb_generator.py", "xml_parser.py", "rodin_exporter.py"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    py = sys.version.split()[0]
    return [(k, v.format(repo=CONVERTER_REPO, commit=commit, python=py)) for k, v in PROVENANCE]


def write_sources(out):
    import re
    md = ["# แหล่งที่มา (Sources)", "", "## ที่มาของข้อมูล", "", "| รายการ | รายละเอียด |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in provenance()]
    md += ["", "## เอกสารอ้างอิง", ""]
    md += [f"{k}. " + re.sub(r"</?i>", "*", r) for k, r in enumerate(REFERENCES, start=1)]
    open(os.path.join(out, "SOURCES.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
SYSTEM = ("You are an Event-B proof-obligation analyst. Given an Event-B model (context and machine) "
          "generated by ChronoSeq-B from a sequence diagram, predict the proof obligations that Rodin "
          "(auto-provers with Atelier B ML/PP) generates for the machine and context, and which of them "
          "it cannot discharge. Answer with JSON only.")
QUESTION = ("How many proof obligations does this model have, how many are discharged, how many fail, "
            "and which ones fail?\n\nEvent-B model:\n```\n{model}\n```")


def kind(failed_pos):
    kinds = sorted({p.split("/")[-1] for p in failed_pos})
    return "+".join(kinds) if kinds else "none"


def assign_splits(rows, seed):
    groups = defaultdict(list)
    for r in rows:
        if r["id"] != "model_001":
            groups[(r["result"], r["fail_kind"])].append(r["id"])
    split = {"model_001": "test"}
    for key in sorted(groups):
        ids = sorted(groups[key], key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
        n = len(ids)
        n_val = round(n * SPLIT[1][1])
        n_test = round(n * SPLIT[2][1])
        for k, i in enumerate(ids):
            split[i] = "val" if k < n_val else "test" if k < n_val + n_test else "train"
    return split


def chat(r):
    answer = {"total_po": r["total_po"], "discharged": r["discharged"], "failed": r["failed"],
              "failed_pos": r["failed_pos"]}
    return {"id": r["id"], "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": QUESTION.format(model=r["model"])},
        {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}]}


def load():
    rows, po_rows = [], []
    cats = {r["model_id"]: r for r in csv.DictReader(open(os.path.join(DATASET, "model_categories.csv")))}
    for line in open(os.path.join(DATASET, "dataset.jsonl")):
        d = json.loads(line)
        mdir = os.path.join(DATASET, "models", d["id"])
        pos = json.load(open(os.path.join(mdir, "po_details.json")))
        failed_pos = sorted(p["po"] for p in pos if not p["discharged"])
        assert len(failed_pos) == d["failed"] and len(pos) == d["total_po"], d["id"]
        code = TOPIC[d["case"]]
        rows.append({**d, "topic": TOPIC_NAMES[code][0], "topic_th": TOPIC_NAMES[code][1],
                     "result": "fail" if d["failed"] else "pass", "failed_pos": failed_pos,
                     "fail_kind": kind(failed_pos), "category": cats[d["id"]]})
        po_rows += [{"id": d["id"], **p} for p in pos]
    return rows, po_rows


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def build(out, seed):
    rows, po_rows = load()
    split = assign_splits(rows, seed)
    for r in rows:
        r["split"] = split[r["id"]]
    if os.path.exists(out):
        shutil.rmtree(out)
    for sub in ("upload", "data", "csv", "models", "by_topic"):
        os.makedirs(os.path.join(out, sub))

    for name, _ in SPLIT:
        with open(os.path.join(out, "upload", f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                if r["split"] == name:
                    f.write(json.dumps(chat(r), ensure_ascii=False) + "\n")
    feats = [k for k in rows[1] if k.startswith("n_") or k in ("fragments", "max_nesting_depth")]
    with open(os.path.join(out, "data", "dataset.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            keep = {k: r.get(k) for k in ["id", "case", "topic", "topic_th", "split", "model"] + feats
                    + ["total_po", "discharged", "failed", "discharge_rate", "failed_pos"]}
            f.write(json.dumps(keep, ensure_ascii=False) + "\n")
    with open(os.path.join(out, "data", "po_details.jsonl"), "w", encoding="utf-8") as f:
        for p in po_rows:
            f.write(json.dumps({k: p[k] for k in ("id", "po", "component", "type", "discharged")},
                               ensure_ascii=False) + "\n")
    write_csv(os.path.join(out, "data", "split.csv"), rows, ["id", "split"])

    num = [k for k in feats if k != "fragments"]
    write_csv(os.path.join(out, "csv", "summary.csv"), rows,
              ["id", "case", "topic", "topic_th", "split", "result"] + num
              + ["total_po", "discharged", "failed", "discharge_rate", "fail_kind"])
    write_csv(os.path.join(out, "csv", "pass_fail_list.csv"), rows,
              ["id", "case", "topic_th", "split", "result", "total_po", "failed", "fail_kind"])
    cat_rows = [{**r["category"], "split": r["split"]} for r in rows]
    write_csv(os.path.join(out, "csv", "model_categories.csv"), cat_rows,
              list(rows[0]["category"]) + ["split"])

    for r in rows:
        src, dst = os.path.join(DATASET, "models", r["id"]), os.path.join(out, "models", r["id"])
        os.makedirs(dst)
        for f in ("model.txt", "label.json", "po_details.json", "features.json"):
            if os.path.exists(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), dst)

    by_topic(out, rows)
    write_sources(out)
    pdf(out, rows, po_rows)
    make_user_flow.main(out)
    return rows


def by_topic(out, rows):
    """by_topic/<NN_Topic>/<pass|fail>/<model_XXX_Case>/ + list.csv per topic (Rodin results)."""
    for k, (code, (en, th)) in enumerate(TOPIC_NAMES.items(), start=1):
        group = sorted((r for r in rows if r["topic"] == en), key=lambda r: r["id"])
        name = en.replace(" & ", "_and_").replace(", ", "_").replace(" ", "_")
        tdir = os.path.join(out, "by_topic", f"{k:02d}_{name}")
        for r in group:
            res = "fail" if r["failed"] else "pass"
            dst = os.path.join(tdir, res, f"{r['id']}_{r['case'].replace(' ', '').replace('&', 'And')}")
            shutil.copytree(os.path.join(out, "models", r["id"]), dst)
        with open(os.path.join(tdir, "list.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["model_id", "case", "result", "total_po", "discharged", "failed", "failed_pos", "split"])
            for r in group:
                w.writerow([r["id"], r["case"], "fail" if r["failed"] else "pass", r["total_po"],
                            r["discharged"], r["failed"], "; ".join(r["failed_pos"]), r["split"]])


EXTRA_CSS = """
.upload { border: 2px solid #2e7d5b; background: #e6f4ec; border-radius: 6px; padding: 8px 12px; margin: 8px 0; }
.warn { border-left: 4px solid #c0392b; background: #fdecea; padding: 6px 10px; margin: 8px 0; }
.kpi { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 8px 0 4px; }
.kpi div { border: 1px solid #cfd6e1; border-radius: 6px; padding: 6px 10px; }
.kpi b { display: block; font-size: 17pt; color: #12325c; font-variant-numeric: tabular-nums; }
.kpi span { font-size: 8.8pt; color: #5a6475; }
pre.wrap { white-space: pre-wrap; word-break: break-all; }
ol.refs li { margin-bottom: 4px; font-size: 9.6pt; overflow-wrap: anywhere; }
"""


def pdf(out, rows, po_rows):
    n = len(rows)
    n_fail = sum(r["result"] == "fail" for r in rows)
    tot = sum(r["total_po"] for r in rows)
    bad = sum(r["failed"] for r in rows)
    po_total = sorted(r["total_po"] for r in rows)
    h = ["<h1>EventB PO Dataset — ชุดสำหรับเทรน AI</h1>",
         f"<div class='sub'>{n} โมเดล · label จาก Rodin + Atelier B (ML/PP) · ทุกโมเดลเป็นผลของสูตรแปลง ChronoSeq-B</div>",
         "<div class='kpi'>"
         f"<div><b>{n}</b><span>โมเดล</span></div>"
         f"<div><b>{n - n_fail} / {n_fail}</b><span>pass / fail</span></div>"
         f"<div><b>{tot:,}</b><span>PO ทั้งหมด</span></div>"
         f"<div><b>{bad}</b><span>PO ที่พิสูจน์ไม่ได้</span></div></div>"]

    h.append("<h2>1. ต้องอัปอะไรไปเทรน</h2>")
    counts = Counter(r["split"] for r in rows)
    h.append("<div class='upload'><b>อัป 2 ไฟล์นี้ไปเทรน (fine-tune)</b><br>"
             f"<code>upload/train.jsonl</code> ({counts['train']} โมเดล) — ใช้เทรน<br>"
             f"<code>upload/val.jsonl</code> ({counts['val']} โมเดล) — ใช้ตรวจระหว่างเทรน (validation file)<br><br>"
             f"<b>ห้ามอัป</b> <code>upload/test.jsonl</code> ({counts['test']} โมเดล) — เก็บไว้วัดผลหลังเทรนเท่านั้น</div>")
    h.append("<p>ไฟล์ทั้ง 3 เป็นรูปแบบ chat (<code>messages</code>: system / user / assistant) "
             "ใช้กับ OpenAI fine-tuning, Hugging Face (TRL / SFTTrainer) และเครื่องมือส่วนใหญ่ได้ตรง ๆ "
             "ถ้าเครื่องมือที่ใช้ต้องการรูปแบบอื่น ใช้ <code>data/dataset.jsonl</code> แปลงต่อได้</p>")
    h.append("<table><tr><th>ถ้าจะทำ</th><th>ใช้ไฟล์</th></tr>"
             "<tr><td>Fine-tune LLM</td><td><code>upload/train.jsonl</code> + <code>upload/val.jsonl</code></td></tr>"
             "<tr><td>วัดผลหลังเทรน</td><td><code>upload/test.jsonl</code> — ให้โมเดลตอบจากข้อความ user แล้วเทียบกับคำตอบ assistant</td></tr>"
             "<tr><td>RAG (ค้นโมเดลที่คล้ายมาเป็นตัวอย่าง)</td><td>ทำดัชนีจาก train ใน <code>data/dataset.jsonl</code> "
             "(คอลัมน์ <code>model</code> + label) แล้วทดสอบกับ test</td></tr>"
             "<tr><td>ML ทั่วไปจาก feature (ไม่ใช้ LLM)</td><td><code>csv/summary.csv</code> (คอลัมน์ n_* = input, total_po / failed = เป้าหมาย)</td></tr></table>")

    h.append("<h2>2. ตัวอย่างข้อมูล 1 รายการ</h2>")
    ex = next(r for r in rows if r["split"] == "train" and r["result"] == "fail" and r["failed"] == 2)
    c = chat(ex)
    short = c["messages"][1]["content"]
    short = short[:short.index("```") + 380] + "\n... (ต่อจนจบโมเดล) ...\n```"
    h.append("<pre class='wrap'>" + esc(json.dumps({"id": c["id"], "messages": [
        {"role": "system", "content": "You are an Event-B proof-obligation analyst. ... Answer with JSON only."},
        {"role": "user", "content": short},
        c["messages"][2]]}, ensure_ascii=False, indent=1)) + "</pre>")
    h.append("<p>คำตอบ (assistant) = จำนวน PO ทั้งหมด, ที่พิสูจน์ได้, ที่ล้ม และชื่อ PO ที่ล้ม — "
             "ชื่อ PO อ่านแบบ <code>&lt;event&gt;/&lt;label&gt;/&lt;ชนิด&gt;</code> เช่น <code>INITIALISATION/act12/FIS</code></p>")

    h.append("<h2>3. โครงสร้าง folder</h2>")
    tree = ["EventB_PO_Training/",
            "├── README.pdf                ← ไฟล์นี้",
            "├── upload/                   ← ไฟล์สำหรับเทรน",
            "│   ├── train.jsonl",
            "│   ├── val.jsonl",
            "│   └── test.jsonl            ← ห้ามใช้เทรน",
            "├── data/",
            "│   ├── dataset.jsonl         ← ทุกโมเดล: ข้อความ Event-B + feature + label + topic + split",
            "│   ├── po_details.jsonl      ← ผลราย PO (ผ่าน / ไม่ผ่าน)",
            "│   └── split.csv             ← โมเดลไหนอยู่ train / val / test",
            "├── csv/",
            "│   ├── summary.csv           ← ตัวเลขต่อโมเดล (feature + label)",
            "│   ├── pass_fail_list.csv    ← pass / fail ต่อโมเดล",
            "│   └── model_categories.csv  ← หัวข้อ + จุดผิดใน diagram (ใช้วิเคราะห์ ห้ามเป็น input)",
            "├── models/model_001 … model_198/",
            "│   ├── model.txt             ← Event-B (input)",
            "│   ├── label.json            ← total / discharged / failed",
            "│   ├── po_details.json       ← ผลราย PO",
            "│   └── features.json",
            "├── by_topic/                 ← โมเดลชุดเดียวกัน แยกตามหัวข้อ และผล Rodin",
            "│   ├── 01_Finance_and_Payment/",
            "│   │   ├── list.csv          ← รายชื่อ + ผล ของหัวข้อนี้",
            "│   │   ├── pass/model_003_ATMWithdrawal/ …",
            "│   │   └── fail/model_004_BankTransfer/ …",
            "│   └── … (11 หัวข้อ)",
            "├── FLOW.pdf · FLOW.png       ← แผนภาพขั้นตอนการดำเนินงาน",
            "└── SOURCES.md                ← แหล่งที่มาและเอกสารอ้างอิง"]
    h.append("<pre>" + esc("\n".join(tree)) + "</pre>")

    h.append("<h2>4. การแบ่ง train / val / test</h2>")
    h.append("<p>แบ่ง 70 / 15 / 15 แบบรักษาสัดส่วน pass/fail และชนิดของ PO ที่ล้มให้เท่ากันทุกชุด "
             "(ใช้ seed คงที่ — สร้างใหม่ได้ผลเดิม) · model_001 (Payment) อยู่ใน test เสมอ</p>")
    kinds = ["none", "FIS", "WD", "FIS+WD"]
    h.append("<table><tr><th>ชุด</th><th>โมเดล</th><th>pass</th><th>fail: FIS</th><th>fail: WD</th><th>fail: FIS+WD</th><th>PO</th></tr>")
    for name, _ in SPLIT:
        g = [r for r in rows if r["split"] == name]
        kc = Counter(r["fail_kind"] for r in g)
        h.append(f"<tr><td>{name}</td><td class='n'>{len(g)}</td>" + "".join(f"<td class='n'>{kc[k]}</td>" for k in kinds)
                 + f"<td class='n'>{sum(r['total_po'] for r in g):,}</td></tr>")
    h.append("</table>")

    h.append("<h2>5. สถิติ</h2>")
    h.append(f"<p>PO ต่อโมเดล: ต่ำสุด {po_total[0]} · มัธยฐาน {statistics.median(po_total):g} · สูงสุด {po_total[-1]} "
             f"· ความยาวข้อความ Event-B เฉลี่ย {sum(len(r['model']) for r in rows) // n:,} ตัวอักษร</p>")
    tc = Counter(p["type"] for p in po_rows)
    fc = Counter(p["type"] for p in po_rows if not p["discharged"])
    h.append("<table><tr><th>ชนิด PO</th><th>ความหมาย</th><th>ทั้งหมด</th><th>ล้ม</th></tr>")
    mean = {"INV": "invariant ยังจริงหลัง event", "FIS": "action :∈ มีค่าให้เลือก", "WD": "สูตรคำนวณได้ (เช่น mod)",
            "THM": "theorem", "GRD": "guard refinement"}
    for t, k in tc.most_common():
        h.append(f"<tr><td><code>{esc(t)}</code></td><td>{esc(mean.get(t, ''))}</td><td class='n'>{k:,}</td><td class='n'>{fc[t]}</td></tr>")
    h.append("</table>")
    h.append("<table style='break-inside:avoid'><tr><th>หัวข้อ</th><th>pass</th><th>fail</th><th>รวม</th><th>train / val / test</th></tr>")
    for code, (en, th) in TOPIC_NAMES.items():
        g = [r for r in rows if r["topic"] == en]
        sc = Counter(r["split"] for r in g)
        h.append(f"<tr><td>{esc(th)}</td><td class='n'>{sum(r['result'] == 'pass' for r in g)}</td>"
                 f"<td class='n'>{sum(r['result'] == 'fail' for r in g)}</td><td class='n'>{len(g)}</td>"
                 f"<td class='n'>{sc['train']} / {sc['val']} / {sc['test']}</td></tr>")
    h.append("</table>")

    h.append("<h2>6. ข้อควรรู้ก่อนเทรน</h2><ul>")
    h.append("<li><b>input มีแค่ข้อความ Event-B</b> (<code>model.txt</code>) — "
             "ห้ามใส่คอลัมน์ใน <code>model_categories.csv</code> เช่น ชนิดจุดผิด หรือ expected เพราะเป็นเฉลย</li>")
    h.append("<li><b>PO ที่ล้มมีแค่ FIS กับ WD</b> — สูตรแปลงทำให้ INV ไม่ล้มจาก diagram "
             "โมเดลที่เทรนจะเรียนรู้รูปแบบ <code>:∈ a..b</code> ที่ a &gt; b และ <code>mod</code> กับตัวนับ loop "
             "ซึ่งตรงกับพฤติกรรมจริงของสูตรแปลง แต่ไม่ครอบคลุมความผิดแบบอื่น</li>")
    h.append("<li><b>label ขึ้นกับ prover</b> — ทั้งชุดใช้ Rodin + Atelier B (ML/PP) ค่าเดียวกัน "
             "ถ้ารันด้วย prover อื่นจำนวนที่พิสูจน์ได้อาจต่าง</li>")
    h.append(f"<li><b>ข้อความยาว</b> — เฉลี่ยราว {sum(len(r['model']) for r in rows) // n // 3:,} token ต่อโมเดล "
             f"(ยาวสุดราว {max(len(r['model']) for r in rows) // 3:,} token) ควรเลือก LLM ที่รับ context ได้อย่างน้อย 8k</li>")
    h.append("<li>สร้าง folder นี้ใหม่ได้ด้วย <code>python tools/make_release.py</code> ใน EventB_PO_Dataset</li></ul>")

    h.append("<h2>7. แหล่งที่มา</h2><h3>ที่มาของข้อมูล</h3><table><tr><th style='width:20%'>รายการ</th><th>รายละเอียด</th></tr>")
    h += [f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in provenance()]
    h.append("</table><h3>เอกสารอ้างอิง</h3><ol class='refs'>")
    h += [f"<li>{r}</li>" for r in REFERENCES]
    h.append("</ol>")

    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "readme.html")
        open(page, "w").write(f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{CSS}{EXTRA_CSS}"
                              f"</style></head><body>{''.join(h)}</body></html>")
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.join(out, 'README.pdf')}", f"file://{page}"],
                       check=True, capture_output=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(DATASET), "EventB_PO_Training"))
    ap.add_argument("--seed", type=int, default=20261026)
    a = ap.parse_args()
    rows = build(os.path.abspath(a.out), a.seed)
    print(os.path.abspath(a.out), Counter(r["split"] for r in rows))
