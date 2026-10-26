"""Rebuild labels, dataset.jsonl and summary.csv from the raw Rodin results.

Self-contained (Python standard library only). Run from the dataset root:

    python tools/rebuild_labels.py
        -> models/*/label.json, models/*/po_details.json, dataset.jsonl, summary.csv
           from rodin_raw/ml_pp (Rodin 3.9 + Atelier B ML/PP — the official labels)

    python tools/rebuild_labels.py --config basic_prover --out labels_basic_prover
        -> labels.jsonl + summary.csv in labels_basic_prover/ (built-in reasoners only);
           models/ is left untouched

A PO counts as discharged when its Rodin confidence is 1000 and its proof is not broken
(psBroken: a proof kept from an older version of the model that no longer applies).
"""
import argparse, csv, glob, json, os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISCHARGED = 1000
NS = "org.eventb.core."
FEATURES = ["n_objects", "n_messages", "n_data", "n_variables", "n_invariants", "n_axioms",
            "n_enum_constants", "n_operations", "n_send_receive_events", "n_checkloop_events",
            "n_guards", "n_actions", "fragments", "n_fragments", "max_nesting_depth",
            "n_duration_constraints", "n_delay_constraints"]
CSV_FEATURES = [f for f in FEATURES if f != "fragments"]


def read_raw(raw_dir):
    """Every PO status in the component .bps files of one Rodin project."""
    per = []
    for path in sorted(glob.glob(os.path.join(ROOT, raw_dir, "*.bps"))):
        comp = os.path.splitext(os.path.basename(path))[0]
        for el in ET.parse(path).getroot().iter():
            if el.tag.endswith("psStatus"):
                name = el.get("name") or el.get(f"{NS}name")
                conf = int(el.get(f"{NS}confidence") or 0)
                broken = el.get(f"{NS}psBroken") == "true"
                per.append({"po": name, "component": comp, "type": name.split("/")[-1],
                            "confidence": conf, "discharged": conf >= DISCHARGED and not broken,
                            "broken": broken, "manual": el.get(f"{NS}psManual") == "true"})
    return per


def label_of(mid, case, per, config):
    disc = sum(p["discharged"] for p in per)
    return {"model_id": mid, "case": case, "prover_config": config, "total_po": len(per),
            "discharged": disc, "failed": len(per) - disc,
            "discharge_rate": round(disc / len(per), 4) if per else None}


def main(config, out):
    rows, mismatches = [], []
    for mdir in sorted(glob.glob(os.path.join(ROOT, "models", "model_*"))):
        mid = os.path.basename(mdir)
        meta = json.load(open(os.path.join(mdir, "meta.json")))
        raw_dir = meta["rodin_raw_dir"].replace("rodin_raw/ml_pp/", f"rodin_raw/{config}/")
        per = read_raw(raw_dir)
        if not per:
            if config != "ml_pp":          # comparison runs exist only for older batches
                continue
            raise SystemExit(f"{mid}: no .bps found in {raw_dir}")
        label = label_of(mid, meta["case"], per, config)
        feats = json.load(open(os.path.join(mdir, "features.json")))
        rows.append((mid, meta, feats, label, per))
        exp = meta.get("expected_failed_pos",
                       [] if meta["design_intent"] == "expected_pass" else None)
        if exp is not None:
            got = sorted(p["po"] for p in per if not p["discharged"])
            if sorted(exp) != got:
                mismatches.append((mid, meta["case"], sorted(set(exp) - set(got)),
                                   sorted(set(got) - set(exp))))

    official = out is None
    out_dir = ROOT if official else os.path.join(ROOT, out)
    os.makedirs(out_dir, exist_ok=True)

    if official:
        for mid, meta, feats, label, per in rows:
            json.dump(label, open(os.path.join(ROOT, "models", mid, "label.json"), "w"), indent=2)
            json.dump(per, open(os.path.join(ROOT, "models", mid, "po_details.json"), "w"),
                      indent=2, ensure_ascii=False)
        with open(os.path.join(out_dir, "dataset.jsonl"), "w") as f:
            for mid, meta, feats, label, _ in rows:
                text = open(os.path.join(ROOT, "models", mid, "model.txt")).read()
                f.write(json.dumps({"id": mid, "case": meta["case"], "model": text,
                                    **{k: feats.get(k) for k in FEATURES},
                                    "total_po": label["total_po"], "discharged": label["discharged"],
                                    "failed": label["failed"],
                                    "discharge_rate": label["discharge_rate"]},
                                   ensure_ascii=False) + "\n")
    else:
        with open(os.path.join(out_dir, "labels.jsonl"), "w") as f:
            for *_, label, _ in rows:
                f.write(json.dumps(label, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "case", "design_intent", "variant", *CSV_FEATURES, "expected_failed",
                    "total_po", "discharged", "failed", "discharge_rate"])
        for mid, meta, feats, label, _ in rows:
            w.writerow([mid, meta["case"], meta["design_intent"], meta["variant"],
                        *[feats.get(k, "") for k in CSV_FEATURES],
                        meta.get("expected_failed_count",
                                 0 if meta["design_intent"] == "expected_pass" else ""),
                        label["total_po"],
                        label["discharged"], label["failed"], label["discharge_rate"]])

    n_fail = sum(1 for r in rows if r[3]["failed"] > 0)
    print(f"[{config}] {len(rows)} models | pass {len(rows) - n_fail} / fail {n_fail} | "
          f"POs {sum(r[3]['total_po'] for r in rows)}, failed {sum(r[3]['failed'] for r in rows)}")
    print(f"expected-vs-Rodin mismatches: {len(mismatches)}")
    for m in mismatches:
        print(f"  {m[0]} {m[1]}: expected-but-discharged={m[2]} unexpected-failures={m[3]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml_pp", choices=["ml_pp", "basic_prover"])
    ap.add_argument("--out", help="write labels.jsonl + summary.csv here instead of models/")
    a = ap.parse_args()
    main(a.config, a.out)
