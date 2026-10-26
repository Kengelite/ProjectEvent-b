"""Add a Rodin-proved batch to the dataset.

    python tools/generators/integrate_batch.py --batch all_197 --workspace <Rodin workspace folder>

<Rodin workspace folder> is the unzipped workspace that contains the imported
<Case>_Project directories after the auto-provers (Atelier B ML/PP) have run.

For every case found under batches/<batch>/ at any depth (cases may sit in topic
folders), in case-name order, this writes model.txt, features.json and meta.json, copies
the diagram and Rodin project to sources/, the Rodin results to rodin_raw/ml_pp/, then
rebuilds labels, dataset.jsonl, summary.csv and by_result/. A case whose meta.json carries
a model_id (a rebuilt first-round model) replaces that model in place; any other case gets
the next free model_XXX. Nothing is written unless every project has Rodin results.
"""
import argparse, filecmp, glob, json, os, re, shutil, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(DATASET))           # ChronoSeq-B (xml_parser)
sys.path.insert(0, os.path.dirname(HERE))              # tools/
from xml_parser import extract_detailed_sequence, extract_fragments_from_xml  # noqa: E402
import rebuild_labels, make_by_result                                           # noqa: E402

RAW_EXT = (".bps", ".bpo", ".bpr", ".bum", ".buc", ".bcm", ".bcc")


def text_features(txt):
    var_line = txt.split("VARIABLES\n")[1].split("\n")[0]
    events = re.findall(r"^ {4}(send|receive|checkloop)\S*$", txt, re.M)
    return {
        "n_variables": len([v for v in var_line.split(",") if v.strip()]),
        "n_invariants": len(re.findall(r"^ {4}inv\d+:", txt, re.M)),
        "n_axioms": len(re.findall(r"^ {4}axm\d+:", txt, re.M)),
        "n_enum_constants": len(re.findall(r"^ {4}axm\d+: \w+ = \d+$", txt, re.M)),
        "n_operations": len(events) + 1,
        "n_send_receive_events": sum(e in ("send", "receive") for e in events),
        "n_checkloop_events": events.count("checkloop"),
        "n_guards": len(re.findall(r"^\s+grd\d+:", txt, re.M)),
        "n_actions": len(re.findall(r"^\s+act\d+:", txt, re.M)),
    }


def diagram_features(xml_path):
    edges = extract_detailed_sequence(xml_path)
    frags = extract_fragments_from_xml(xml_path)

    def depth(f):
        return 1 + sum(1 for g in frags if g is not f
                       and g["y_start"] <= f["y_start"] and g["y_end"] >= f["y_end"])
    return {
        "n_objects": len({e["sender"] for e in edges} | {e["receiver"] for e in edges}),
        "n_messages": len(edges),
        "n_data": len({d.strip() for e in edges for d in (e["data"] or "").split(",") if d.strip()}),
        "fragments": dict(Counter(f["type"] for f in frags)),
        "n_fragments": len(frags),
        "max_nesting_depth": max((depth(f) for f in frags), default=0),
        "n_duration_constraints": sum(1 for e in edges if e.get("duration")),
        "n_delay_constraints": sum(1 for e in edges if e.get("delay")),
    }


def proved_before(bum, project):
    """An older .bps is still valid when the model and its result equal the copy already in
    rodin_raw/ml_pp/ (an unchanged model that Rodin did not need to prove again)."""
    raw = os.path.join(DATASET, "rodin_raw", "ml_pp", project, os.path.basename(bum))
    return (os.path.exists(raw) and filecmp.cmp(bum, raw, shallow=False)
            and filecmp.cmp(bum[:-4] + ".bps", raw[:-4] + ".bps", shallow=False))


def main(batch, workspace):
    bdir = os.path.join(DATASET, "batches", batch)
    dirs = {os.path.basename(os.path.dirname(p)): os.path.dirname(p)
            for p in glob.glob(os.path.join(bdir, "**", "meta.json"), recursive=True)}
    cases = sorted(dirs, key=str.lower)
    metas = {c: json.load(open(os.path.join(dirs[c], "meta.json"))) for c in cases}
    existing = [json.load(open(p)) for p in glob.glob(os.path.join(DATASET, "models", "*", "meta.json"))]
    if any(m.get("integrated_from") == batch for m in existing):
        raise SystemExit(f"{batch} is already in the dataset")
    known = {m["case"] for m in existing}
    clash = [c for c in cases if c in known and "model_id" not in metas[c]]
    if clash:
        raise SystemExit("already in the dataset under another batch: " + ", ".join(clash))
    missing, stale, pending = [], [], []
    for c in cases:
        pdir = os.path.join(workspace, metas[c]["rodin_project"])
        for bum in glob.glob(os.path.join(pdir, "*.bum")) or [os.path.join(pdir, "?.bum")]:
            bps = bum[:-4] + ".bps"
            if not os.path.exists(bps):
                missing.append(c)
            elif os.path.getmtime(bps) < os.path.getmtime(bum) and not proved_before(bum, metas[c]["rodin_project"]):
                stale.append(c)                                       # proof of an older version of the model
            elif 'confidence="-99"' in open(bps, encoding="utf-8").read():   # not attempted yet
                pending.append(c)
    for what, names in (("no Rodin results (.bps)", missing), ("results older than the model", stale),
                        ("POs not attempted yet", pending)):
        if names:
            print(f"{what}: {len(names)} — " + ", ".join(sorted(set(names))[:12]) + (" …" if len(names) > 12 else ""))
    if missing or stale or pending:
        raise SystemExit("workspace is not fully proved — nothing written")

    last = max(int(os.path.basename(p)[6:]) for p in glob.glob(os.path.join(DATASET, "models", "model_*")))
    new = [c for c in cases if "model_id" not in metas[c]]
    ids = {c: metas[c]["model_id"] for c in cases if c not in new}
    ids.update({c: f"model_{k:03d}" for k, c in enumerate(new, start=last + 1)})
    for case in cases:
        mid, meta = ids[case], dict(metas[case])
        meta.pop("model_id", None)
        src, project = dirs[case], meta["rodin_project"]
        mdir, sdir = os.path.join(DATASET, "models", mid), os.path.join(DATASET, "sources", mid)
        rdir = os.path.join(DATASET, "rodin_raw", "ml_pp", project)
        for d in (mdir, sdir, rdir):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
        txt = open(os.path.join(src, f"{case}_EventB.txt")).read()
        open(os.path.join(mdir, "model.txt"), "w").write(txt)
        feats = {**diagram_features(os.path.join(src, f"{case}.drawio.xml")), **text_features(txt)}
        json.dump(feats, open(os.path.join(mdir, "features.json"), "w"), indent=2)
        meta = {"model_id": mid, **meta, "integrated_from": batch, "source_dir": f"sources/{mid}",
                "rodin_raw_dir": f"rodin_raw/ml_pp/{project}"}
        json.dump(meta, open(os.path.join(mdir, "meta.json"), "w"), indent=2, ensure_ascii=False)
        for f in (f"{case}.drawio.xml", f"{case}_Rodin.zip"):
            shutil.copy2(os.path.join(src, f), sdir)
        for f in os.listdir(os.path.join(workspace, project)):
            if f.endswith(RAW_EXT) or f == ".project":
                shutil.copy2(os.path.join(workspace, project, f), rdir)
    print(f"replaced {len(cases) - len(new)} models, added {len(new)}: "
          f"model_{last + 1:03d} .. model_{last + len(new):03d}")
    rebuild_labels.main("ml_pp", None)
    make_by_result.main()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--workspace", required=True)
    a = ap.parse_args()
    main(a.batch, os.path.expanduser(a.workspace))
