"""Build the B-model dataset (same format as model_001) for every generated case.

    python build_dataset.py                      # model.txt + features, labels pending
    python build_dataset.py --workspace <path>   # also fill labels from Rodin's .bps

Per case  dataset/model_XXX/
    model.txt        Event-B model given to the LLM (no hint of any mutation)
    features.json    structural metrics (diagram + Event-B)
    label.json       Rodin ground truth: total / discharged / failed PO
    po_details.json  per-PO result (only once Rodin results exist)
    meta.json        provenance: source diagram, pass/fail intent, mutation, expected
                     failures — for analysis only, never an LLM input
Plus dataset/dataset.jsonl (training rows) and dataset/summary.csv (analysis).
model_001 (Payment, proven earlier) is kept as is.
"""
import argparse, csv, glob, json, os, re, sys
import xml.etree.ElementTree as ET
from collections import Counter

sys.path.insert(0, "/Users/elite/Documents/ปโท/projectcode")
from xml_parser import extract_detailed_sequence, extract_fragments_from_xml

HERE = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS = os.path.dirname(HERE)
OUT = os.path.join(HERE, "dataset")
SOURCES = [("Drawio_Models", "expected_pass"), ("Drawio_Models_Fail", "expected_fail")]
DISCHARGED = 1000
NS = "org.eventb.core."


def text_features(txt):
    var_line = txt.split("VARIABLES\n")[1].split("\n")[0]
    events = re.findall(r"^ {4}(send|receive|checkloop)\S*$", txt, re.M)
    return {
        "n_variables": len([v for v in var_line.split(",") if v.strip()]),
        "n_invariants": len(re.findall(r"^ {4}inv\d+:", txt, re.M)),
        "n_axioms": len(re.findall(r"^ {4}axm\d+:", txt, re.M)),
        "n_enum_constants": len(re.findall(r"^ {4}axm\d+: \w+ = \d+$", txt, re.M)),
        "n_operations": len(events) + 1,                       # + INITIALISATION
        "n_send_receive_events": sum(e in ("send", "receive") for e in events),
        "n_checkloop_events": events.count("checkloop"),
        "n_guards": len(re.findall(r"^\s+grd\d+:", txt, re.M)),
        "n_actions": len(re.findall(r"^\s+act\d+:", txt, re.M)),
    }


def diagram_features(xml_path):
    edges = extract_detailed_sequence(xml_path)
    frags = extract_fragments_from_xml(xml_path)

    def depth(f):          # 1 + number of other fragments whose band encloses f
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


def read_bps(path):
    per = []
    for el in ET.parse(path).getroot().iter():
        if el.tag.endswith("psStatus"):
            name = el.get("name") or el.get(f"{NS}name")      # .bps uses plain "name"
            conf = int(el.get(f"{NS}confidence") or 0)
            per.append({"po": name, "confidence": conf, "discharged": conf >= DISCHARGED,
                        "manual": el.get(f"{NS}psManual") == "true",
                        "type": name.split("/")[-1]})
    return per


def rodin_label(workspace, project):
    """Machine + context POs of one project, or None if Rodin has not built it."""
    pdir = os.path.join(workspace, project)
    bps = sorted(glob.glob(os.path.join(pdir, "*.bps")))
    if not bps:
        return None
    per = []
    for p in bps:
        comp = os.path.splitext(os.path.basename(p))[0]
        per += [{**x, "component": comp} for x in read_bps(p)]
    return per


def collect_cases():
    cases = []
    for folder, intent in SOURCES:
        for d in sorted(glob.glob(os.path.join(DOWNLOADS, folder, "*/"))):
            name = os.path.basename(d.rstrip("/"))
            meta = {"case": name, "design_intent": intent, "variant": "plain",
                    "source_diagram": f"{folder}/{name}/{name}.drawio.xml",
                    "rodin_project": f"{name}_Project"}
            for extra in ("mutation.json", "augmentation.json"):
                p = os.path.join(d, extra)
                if os.path.exists(p):
                    info = json.load(open(p))
                    info.pop("model", None)
                    meta.update(info)
            if intent == "expected_fail":
                meta["variant"] = "mutated" if meta.get("operations") else "diagram_error"
            elif "added_invariants" in meta:
                meta["variant"] = "augmented"
            cases.append((name, d, meta))
    # IDs follow the case name, not pass/fail grouping, so the ID carries no label signal
    return sorted(cases, key=lambda c: c[0].lower())


def main(workspace=None):
    rows, report = [], []
    first = os.path.join(OUT, "dataset.jsonl")
    keep = [json.loads(l) for l in open(first)][:1] if os.path.exists(first) else []

    for k, (name, d, meta) in enumerate(collect_cases(), start=2):
        mid = f"model_{k:03d}"
        mdir = os.path.join(OUT, mid)
        os.makedirs(mdir, exist_ok=True)
        txt = open(os.path.join(d, f"{name}_EventB.txt")).read()
        feats = {**diagram_features(os.path.join(d, f"{name}.drawio.xml")), **text_features(txt)}

        per = rodin_label(workspace, meta["rodin_project"]) if workspace else None
        if per is None:
            label = {"model_id": mid, "case": name, "status": "pending_rodin",
                     "total_po": None, "discharged": None, "failed": None, "discharge_rate": None}
        else:
            disc = sum(p["discharged"] for p in per)
            label = {"model_id": mid, "case": name, "status": "rodin",
                     "total_po": len(per), "discharged": disc, "failed": len(per) - disc,
                     "discharge_rate": round(disc / len(per), 4) if per else None}
            json.dump(per, open(os.path.join(mdir, "po_details.json"), "w"), indent=2, ensure_ascii=False)
            exp = set(meta.get("expected_failed_pos", []))
            got = {f"{p['po']}" for p in per if not p["discharged"]}
            if exp != got:
                report.append((mid, name, sorted(exp - got), sorted(got - exp)))

        open(os.path.join(mdir, "model.txt"), "w").write(txt)
        json.dump(feats, open(os.path.join(mdir, "features.json"), "w"), indent=2)
        json.dump(label, open(os.path.join(mdir, "label.json"), "w"), indent=2)
        json.dump({"model_id": mid, **meta}, open(os.path.join(mdir, "meta.json"), "w"),
                  indent=2, ensure_ascii=False)
        rows.append((mid, name, meta, feats, label, txt))

    # dataset.jsonl — training rows (model text + features + label; no meta)
    with open(first, "w") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for mid, name, meta, feats, label, txt in rows:
            f.write(json.dumps({"id": mid, "case": name, "model": txt, **feats,
                                "total_po": label["total_po"], "discharged": label["discharged"],
                                "failed": label["failed"]}, ensure_ascii=False) + "\n")

    # summary.csv — analysis table (includes meta)
    cols = ["id", "case", "design_intent", "variant", "n_obj", "n_msg", "n_data", "n_var", "n_inv",
            "n_op", "n_guard", "n_action", "n_frag", "max_depth", "n_dur", "n_delay",
            "expected_failed", "total_po", "discharged", "failed", "rate", "status"]
    with open(os.path.join(OUT, "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in keep:
            w.writerow([r["id"], r["case"], "real_proof", "original", r["n_objects"], r["n_messages"],
                        r["n_data"], r["n_variables"], "", r["n_operations"], "", "", "", "", "", "",
                        "", r["total_po"], r["discharged"], r["failed"],
                        round(r["discharged"] / r["total_po"], 2), "rodin"])
        for mid, name, meta, x, lb, _ in rows:
            w.writerow([mid, name, meta["design_intent"], meta["variant"], x["n_objects"],
                        x["n_messages"], x["n_data"], x["n_variables"], x["n_invariants"],
                        x["n_operations"], x["n_guards"], x["n_actions"], x["n_fragments"],
                        x["max_nesting_depth"], x["n_duration_constraints"], x["n_delay_constraints"],
                        meta.get("expected_failed_count", 0), lb["total_po"], lb["discharged"],
                        lb["failed"], lb["discharge_rate"], lb["status"]])

    done = sum(1 for r in rows if r[4]["status"] == "rodin")
    print(f"built {len(rows)} models (model_002..model_{len(rows) + 1:03d}) + model_001 kept")
    print(f"labels from Rodin: {done}/{len(rows)}")
    if workspace:
        missing = [r[1] for r in rows if r[4]["status"] != "rodin"]
        if missing:
            print("no .bps found for:", ", ".join(missing))
        print(f"expected vs Rodin mismatches: {len(report)}")
        for mid, name, not_failed, extra_failed in report:
            print(f"  {mid} {name}: expected-but-discharged={not_failed} unexpected-failures={extra_failed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", help="Rodin workspace folder containing the imported *_Project dirs")
    main(ap.parse_args().workspace)
