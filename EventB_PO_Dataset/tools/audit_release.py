"""Audit the whole release against the raw sources, independently of the scripts that built it.

    python tools/audit_release.py [--release ../EventB_PO_Training]

    A labels      recount every PO from the Rodin files (.bpo = POs, .bps = results; stale or unattempted
                  proofs count as failed) and compare with label.json, po_details.json, dataset.jsonl,
                  the assistant answers in upload/ and the csv tables
    B model text  model.txt = the machine and context Rodin proved (.bum / .buc): invariants, axioms,
                  every guard and action of every event
    C failures    every failed PO comes from a diagram error and every diagram error fails a PO:
                  inverted duration {a..b} (a > b) -> FIS of `t :∈ a..b`, `mod` condition -> WD of that guard;
                  no other PO fails
    D split       each model in exactly one split, ratios kept per result, model_001 in test, no two models
                  with the same text, and nothing from the answer in the input
    E files       release copies, by_topic folders and per-topic lists, csv tables match the dataset
Prints every problem and a summary; writes audit_report.json next to the dataset.
"""
import argparse, csv, glob, hashlib, json, os, re, sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from verify_trees import cells                                    # noqa: E402

problems = defaultdict(list)


def bad(section, msg):
    problems[section].append(msg)


# ── A: labels from Rodin ───────────────────────────────────────────────────
def rodin_results(rdir):
    pos, stamp = {}, {}
    for f in glob.glob(os.path.join(rdir, "*.bpo")):
        for s in ET.parse(f).getroot().iter("org.eventb.core.poSequent"):
            pos[s.get("name")] = os.path.basename(f)[:-4]
            stamp[s.get("name")] = s.get("org.eventb.core.poStamp")
    status = {}
    for f in glob.glob(os.path.join(rdir, "*.bps")):
        for s in ET.parse(f).getroot().iter("org.eventb.core.psStatus"):
            status[s.get("name")] = (int(s.get("org.eventb.core.confidence")),
                                     s.get("org.eventb.core.psBroken") == "true",
                                     s.get("org.eventb.core.poStamp"))
    out = {}
    for name in pos:
        conf, broken, st = status.get(name, (-99, False, None))
        stale = st is not None and stamp[name] is not None and st != stamp[name]
        out[name] = {"discharged": conf >= 1000 and not broken and not stale,
                     "missing": name not in status, "stale": stale}
    extra = set(status) - set(pos)
    return out, extra


# ── B: model text vs .bum / .buc ───────────────────────────────────────────
def squash(s):
    """Whitespace-free, with the ASCII and Unicode spellings of an assignment made equal."""
    return re.sub(r"\s+", "", s).replace(":=", "≔").replace("::", ":∈").replace("‥", "..")


def parse_model_txt(path):
    m = {"inv": {}, "axm": {}, "events": defaultdict(lambda: {"grd": {}, "act": {}})}
    ev, part = None, None
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if re.fullmatch(r"[A-Za-z_]\w*", s) and s not in ("WHEN", "THEN", "END", "SETS", "CONSTANTS", "AXIOMS",
                                                           "VARIABLES", "INVARIANTS", "EVENTS"):
            ev, part = s, None
            m["events"][ev]
        elif s.startswith("INITIALISATION"):
            ev, part = "INITIALISATION", "act"
            m["events"][ev]
        elif s == "WHEN":
            part = "grd"
        elif s == "THEN":
            part = "act"
        elif mm := re.match(r"(inv\d+|axm\d+|grd\d+|act\d+):\s*(.*)$", s):
            label, body = mm.groups()
            if label.startswith("inv"):
                m["inv"][label] = body
            elif label.startswith("axm"):
                m["axm"][label] = body
            elif ev:
                m["events"][ev][label[:3]][label] = body
    return m


def parse_rodin_model(rdir):
    m = {"inv": {}, "axm": {}, "events": defaultdict(lambda: {"grd": {}, "act": {}})}
    for f in glob.glob(os.path.join(rdir, "*.buc")):
        for a in ET.parse(f).getroot().iter("org.eventb.core.axiom"):
            m["axm"][a.get("org.eventb.core.label")] = a.get("org.eventb.core.predicate")
    for f in glob.glob(os.path.join(rdir, "*.bum")):
        root = ET.parse(f).getroot()
        for i in root.iter("org.eventb.core.invariant"):
            m["inv"][i.get("org.eventb.core.label")] = i.get("org.eventb.core.predicate")
        for e in root.iter("org.eventb.core.event"):
            ev = m["events"][e.get("org.eventb.core.label")]
            for g in e.iter("org.eventb.core.guard"):
                ev["grd"][g.get("org.eventb.core.label")] = g.get("org.eventb.core.predicate")
            for a in e.iter("org.eventb.core.action"):
                ev["act"][a.get("org.eventb.core.label")] = a.get("org.eventb.core.assignment")
    return m


def compare_models(mid, txt, rod):
    for kind in ("inv", "axm"):
        a = {k: squash(v) for k, v in txt[kind].items()}
        b = {k: squash(v) for k, v in rod[kind].items()}
        if a != b:
            bad("B", f"{mid}: {kind} differ ({sorted(set(a.items()) ^ set(b.items()))[:2]})")
    if set(txt["events"]) != set(rod["events"]):
        bad("B", f"{mid}: events differ {sorted(set(txt['events']) ^ set(rod['events']))}")
    for e in set(txt["events"]) & set(rod["events"]):
        for part in ("grd", "act"):
            a = {k: squash(v) for k, v in txt["events"][e][part].items()}
            b = {k: squash(v) for k, v in rod["events"][e][part].items()}
            if a != b:
                bad("B", f"{mid}: {e} {part} differ ({sorted(set(a.items()) ^ set(b.items()))[:2]})")


# ── C: why POs fail ────────────────────────────────────────────────────────
def predicted_failures(model):
    pred = set()
    for label, body in model["events"]["INITIALISATION"]["act"].items():
        if mm := re.search(r":∈\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*$", body):
            if int(mm.group(1)) > int(mm.group(2)):
                pred.add(f"INITIALISATION/{label}/FIS")
    for e, parts in model["events"].items():
        for label, body in parts["grd"].items():
            if re.search(r"\bmod\b", body):
                pred.add(f"{e}/{label}/WD")
    return pred


def diagram_errors(path):
    inverted, mods = 0, 0
    for c in cells(path):
        for a, b in re.findall(r"\{\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*\}", c["value"]):
            inverted += int(a) > int(b)
        v = c["value"].strip()
        if v.startswith("[") and re.search(r"\bmod\b", v):
            mods += 1
    return inverted, mods


# ── main ───────────────────────────────────────────────────────────────────
def main(release):
    rel = lambda *p: os.path.join(release, *p)
    data = {json.loads(l)["id"]: json.loads(l) for l in open(rel("data", "dataset.jsonl"))}
    split = {r["id"]: r["split"] for r in csv.DictReader(open(rel("data", "split.csv")))}
    uploads = {}
    for name in ("train", "val", "test"):
        for l in open(rel("upload", f"{name}.jsonl")):
            r = json.loads(l)
            if r["id"] in uploads:
                bad("D", f"{r['id']} appears in more than one upload file")
            uploads[r["id"]] = (name, r)
    stats = Counter()
    texts = {}
    for d in sorted(glob.glob(os.path.join(DATASET, "models", "model_*"))):
        mid = os.path.basename(d)
        meta = json.load(open(os.path.join(d, "meta.json")))
        label = json.load(open(os.path.join(d, "label.json")))
        pod = {p["po"]: p for p in json.load(open(os.path.join(d, "po_details.json")))}
        text = open(os.path.join(d, "model.txt"), encoding="utf-8").read()
        rdir = os.path.join(DATASET, meta["rodin_raw_dir"])
        # A
        res, extra = rodin_results(rdir)
        if extra:
            bad("A", f"{mid}: {len(extra)} proof results without a PO (stale .bps)")
        if any(r["stale"] for r in res.values()):
            bad("A", f"{mid}: {sum(r['stale'] for r in res.values())} stale proofs")
        if any(r["missing"] for r in res.values()):
            bad("A", f"{mid}: {sum(r['missing'] for r in res.values())} POs never attempted")
        failed = sorted(n for n, r in res.items() if not r["discharged"])
        want = {"total_po": len(res), "discharged": len(res) - len(failed), "failed": len(failed)}
        stats["po"] += len(res)
        stats["failed_po"] += len(failed)
        stats["fail_models"] += bool(failed)
        if {k: label[k] for k in want} != want:
            bad("A", f"{mid}: label.json {[label[k] for k in want]} vs Rodin {list(want.values())}")
        if set(pod) != set(res) or any(pod[n]["discharged"] != res[n]["discharged"] for n in res):
            bad("A", f"{mid}: po_details.json differs from Rodin")
        row = data.get(mid)
        if not row or {k: row[k] for k in want} != want or sorted(row["failed_pos"]) != failed:
            bad("A", f"{mid}: dataset.jsonl differs from Rodin")
        if row and row["model"] != text:
            bad("E", f"{mid}: dataset.jsonl model text differs from models/{mid}/model.txt")
        if mid not in uploads:
            bad("D", f"{mid}: missing from upload/")
        else:
            name, u = uploads[mid]
            ans = json.loads(u["messages"][2]["content"])
            if (ans.get("total_po"), ans.get("discharged"), ans.get("failed")) != tuple(want.values()) or \
                    sorted(ans.get("failed_pos", [])) != failed:
                bad("A", f"{mid}: answer in upload/{name}.jsonl differs from Rodin")
            if name != split.get(mid) or name != row.get("split"):
                bad("D", f"{mid}: split differs between upload/, split.csv and dataset.jsonl")
            user = u["messages"][1]["content"]
            if text.strip() not in user:
                bad("D", f"{mid}: input does not contain model.txt exactly")
            leak = [w for w in ["/FIS", "/WD", "/INV", "mutation", "expected", "diagram_error", "inverted", "discharged\":"]
                    if w in user.replace(text, "")]
            if leak:
                bad("D", f"{mid}: input may reveal the answer ({leak})")
        # B
        txt_model = parse_model_txt(os.path.join(d, "model.txt"))
        if mid == "model_001":
            names = {n.split("/")[0] for n in res}
            if not names <= set(txt_model["events"]) | {"INITIALISATION"}:
                bad("B", f"{mid}: PO events not in model.txt {sorted(names - set(txt_model['events']))}")
        else:
            compare_models(mid, txt_model, parse_rodin_model(rdir))
        # C
        if mid != "model_001":
            pred = predicted_failures(txt_model)
            if pred != set(failed):
                bad("C", f"{mid}: failed {sorted(set(failed) - pred)} not predicted, predicted {sorted(pred - set(failed))} not failed")
            diag = glob.glob(os.path.join(DATASET, meta["source_dir"], "*.drawio.xml"))
            inv, mods = diagram_errors(diag[0])
            n_fis = sum(p.endswith("/FIS") for p in pred)
            if inv != n_fis:
                bad("C", f"{mid}: {inv} inverted durations in diagram, {n_fis} inverted ranges in model")
            if bool(mods) != any(p.endswith("/WD") for p in pred):
                bad("C", f"{mid}: mod in diagram {mods}, WD failures {sum(p.endswith('/WD') for p in pred)}")
            if bool(inv or mods) != bool(failed):
                bad("C", f"{mid}: diagram errors {inv + mods} but failed POs {len(failed)}")
            stats["diagram_errors_fis"] += inv
            stats["models_with_mod"] += bool(mods)
        if any(p.endswith("/INV") for p in failed):
            bad("C", f"{mid}: an INV PO failed")
        # D duplicates
        h = hashlib.sha1(squash(re.sub(r"\b[A-Z]\w*Context\b|\b\w+InteractionMachine_1\b", "", text)).encode()).hexdigest()
        if h in texts:
            bad("D", f"{mid}: same model text as {texts[h]} ({split.get(mid)} / {split.get(texts[h])})")
        texts[h] = mid
        # E copies
        for f in ("model.txt", "label.json", "po_details.json", "features.json", "tree.txt", "tree.json"):
            if open(os.path.join(d, f), "rb").read() != open(rel("models", mid, f), "rb").read():
                bad("E", f"{mid}: release models/{mid}/{f} differs")
    ids = sorted(data)
    if len(ids) != len(uploads) or set(ids) != set(uploads):
        bad("D", "upload/ and dataset.jsonl hold different models")
    if split.get("model_001") != "test":
        bad("D", "model_001 is not in test")
    # D ratios
    by = Counter((split[i], "fail" if data[i]["failed"] else "pass") for i in ids)
    for name in ("train", "val", "test"):
        n = by[(name, "pass")] + by[(name, "fail")]
        stats[f"{name}"] = n
        stats[f"{name}_fail_pct"] = round(100 * by[(name, "fail")] / n, 1)
    if max(stats[f"{n}_fail_pct"] for n in ("train", "val", "test")) - \
            min(stats[f"{n}_fail_pct"] for n in ("train", "val", "test")) > 5:
        bad("D", "fail ratio differs by more than 5 points between splits")
    # E tables and folders
    summ = {r["id"]: r for r in csv.DictReader(open(rel("csv", "summary.csv"), encoding="utf-8"))}
    pf = {r["id"]: r for r in csv.DictReader(open(rel("csv", "pass_fail_list.csv"), encoding="utf-8"))}
    for i in ids:
        res_ = "fail" if data[i]["failed"] else "pass"
        if summ[i]["result"] != res_ or int(summ[i]["failed"]) != data[i]["failed"] or \
                int(summ[i]["total_po"]) != data[i]["total_po"]:
            bad("E", f"{i}: csv/summary.csv differs")
        if pf[i]["result"] != res_ or int(pf[i]["failed"]) != data[i]["failed"]:
            bad("E", f"{i}: csv/pass_fail_list.csv differs")
    seen = Counter()
    for f in glob.glob(rel("by_topic", "*", "*", "model_*")):
        mid = os.path.basename(f)[:9]
        seen[mid] += 1
        res_ = "fail" if data[mid]["failed"] else "pass"
        if f.split(os.sep)[-2] != res_:
            bad("E", f"{mid}: by_topic folder says {f.split(os.sep)[-2]}, Rodin says {res_}")
        for g in os.listdir(f):
            if open(os.path.join(f, g), "rb").read() != open(rel("models", mid, g), "rb").read():
                bad("E", f"{mid}: by_topic copy of {g} differs")
    for f in glob.glob(rel("trees", "by_topic", "*", "*", "model_*.txt")):
        mid = os.path.basename(f)[:9]
        seen["tree:" + mid] += 1
        if f.split(os.sep)[-2] != ("fail" if data[mid]["failed"] else "pass"):
            bad("E", f"{mid}: trees/by_topic folder has the wrong result")
    for i in ids:
        if seen[i] != 1 or seen["tree:" + i] != 1:
            bad("E", f"{i}: appears {seen[i]}x in by_topic, {seen['tree:' + i]}x in trees/by_topic")
    for f in glob.glob(rel("by_topic", "*", "list.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            d_ = data[r["model_id"]]
            if (r["result"], int(r["failed"]), int(r["total_po"])) != \
                    ("fail" if d_["failed"] else "pass", d_["failed"], d_["total_po"]):
                bad("E", f"{r['model_id']}: {os.path.basename(os.path.dirname(f))}/list.csv differs")
    for name in ("provenance.csv", "similar_work.csv", "model_categories.csv"):
        got = [r for r in csv.DictReader(open(rel("csv", name), encoding="utf-8-sig"))]
        key = "model_id" if "model_id" in got[0] else "id"
        if sorted(r[key] for r in got) != ids:
            bad("E", f"csv/{name} does not list every model exactly once")
    stats["models"] = len(ids)
    stats["pass_models"] = len(ids) - stats["fail_models"]
    report = {"stats": dict(stats), "problems": {k: v for k, v in problems.items()}}
    json.dump(report, open(os.path.join(DATASET, "audit_report.json"), "w"), ensure_ascii=False, indent=1)
    for sec in "ABCDE":
        print(f"{sec}: {len(problems[sec])} problems")
        for p in problems[sec][:15]:
            print("   ", p)
    print(dict(stats))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default=os.path.join(os.path.dirname(DATASET), "EventB_PO_Training"))
    main(os.path.abspath(ap.parse_args().release))
