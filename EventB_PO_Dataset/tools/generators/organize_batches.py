"""Merge staged batches into one browsing folder grouped by topic and pass/fail.

    python tools/generators/organize_batches.py --into all_197 new_150 round1

A source is any folder under batches/ holding Rodin_Import_<source>.zip and case folders
(flat, as gen_batch.py writes them, or already grouped by a previous run of this script).

Result: batches/<into>/<NN_topic_th>/{pass,fail}/<Case>/ plus one Rodin_Import_<into>.zip
holding every project. pass/fail is the design intent from meta.json (not yet Rodin-proved).
The source folders are removed once every case has been moved out of them.
"""
import argparse, glob, json, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from categorize import TOPIC, TOPIC_NAMES  # noqa: E402

FOLDER = {"expected_pass": "pass", "expected_fail": "fail"}


def main(into, batches):
    root = os.path.join(DATASET, "batches")
    out = os.path.join(root, into)
    if os.path.exists(out):
        raise SystemExit(f"{out} already exists")
    topic_dir = {code: f"{k:02d}_{th}" for k, (code, (_, th)) in enumerate(TOPIC_NAMES.items(), start=1)}
    cases = []
    for b in batches:
        for p in sorted(glob.glob(os.path.join(root, b, "**", "meta.json"), recursive=True)):
            m = json.load(open(p))
            if m["case"] not in TOPIC:
                raise SystemExit(f"no topic for {m['case']} — add it to TOPIC in tools/categorize.py")
            cases.append((os.path.dirname(p), m))

    os.makedirs(out)
    seen = set()
    with zipfile.ZipFile(os.path.join(out, f"Rodin_Import_{into}.zip"), "w", zipfile.ZIP_DEFLATED) as zout:
        for b in batches:
            with zipfile.ZipFile(os.path.join(root, b, f"Rodin_Import_{b}.zip")) as zin:
                for info in zin.infolist():
                    if info.filename in seen:
                        raise SystemExit(f"{info.filename} is in two batches")
                    seen.add(info.filename)
                    zout.writestr(info, zin.read(info))
    for src, m in cases:
        dst = os.path.join(out, topic_dir[TOPIC[m["case"]]], FOLDER[m["design_intent"]])
        os.makedirs(dst, exist_ok=True)
        shutil.move(src, os.path.join(dst, m["case"]))
    for b in batches:
        if glob.glob(os.path.join(root, b, "**", "meta.json"), recursive=True):
            raise SystemExit(f"{b} still holds cases")
        shutil.rmtree(os.path.join(root, b))

    print(f"{len(cases)} models, {len({n.split('/')[0] for n in seen})} Rodin projects -> {out}")
    for d in sorted(os.listdir(out)):
        if os.path.isdir(os.path.join(out, d)):
            n = {s: len(os.listdir(os.path.join(out, d, s))) if os.path.isdir(os.path.join(out, d, s)) else 0
                 for s in ("pass", "fail")}
            print(f"  {d}: pass {n['pass']} / fail {n['fail']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--into", required=True)
    ap.add_argument("batches", nargs="+")
    a = ap.parse_args()
    main(a.into, a.batches)
