"""Rebuild the first-round models (model_002..048) under the diagram-only rule.

    python tools/generators/redo_round1.py

The first round had 17 fail models whose Event-B was edited after conversion and 4
"augmented" pass models with invariants added by hand. Under the rule that every model
is the converter's output of its diagram, those 21 are redone:
  * fail  -> the error is written into the model's own diagram (a duration interval
             written backwards, or a "c mod k" condition inside a loop), then converted
  * augmented -> the unchanged diagram is converted (plain pass model)
The other 26 already follow the rule and are converted again unchanged (same text).

Output (staging, before Rodin), same layout as gen_batch.py:  batches/round1/
The 21 old versions (models/, sources/, rodin_raw/) are copied to
archive/round1_post_conversion_edits/ first. model_001 (Payment test case) is left out.
"""
import glob, io, json, os, random, re, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(DATASET))
sys.path.insert(0, HERE)
import rodin_exporter                                       # noqa: E402
from eventb_generator import apply_rules_1_and_2            # noqa: E402
from xml_parser import extract_detailed_sequence            # noqa: E402
from gen_batch import plan_ops, CATEGORY                     # noqa: E402

BATCH = "round1"
# diagram error per redone fail model: messages whose {0..n} is written backwards, or the
# condition box replaced by a mod condition on the enclosing loop counter
FIXES = {
    "AirportBaggage": {"invert": ["loadBag"]},
    "BankTransfer": {"invert": ["checkFraud", "postTransfer"]},
    "BatteryChargeCycle": {"invert": ["chargePulse"]},
    "ChatMessaging": {"invert": ["deliverText", "replyText", "deliverReply"]},
    "ColdChainMonitor": {"invert": ["uploadLog"]},
    "ConferenceRoomBooking": {"invert": ["updatePanel"]},
    "CourseEnrollment": {"invert": ["checkPrereq", "requestApproval"]},
    "GymCheckIn": {"invert": ["scanQR"]},
    "LoginRateLimiter": {"mod": ("[locked == 1]", "[failCount mod 2 == 0]")},
    "MedicationDispenser": {"invert": ["doseAlert"]},
    "OnlineAuction": {"invert": ["raiseBid"]},
    "PrinterQueue": {"invert": ["pagePrinted"]},
    "SmartMeterBilling": {"invert": ["sendUsage", "generateBill"]},
    "SmartPlugControl": {"invert": ["plugState"]},
    "TaxiDispatch": {"invert": ["findDriver", "tripComplete"]},
    "ToolRentalLocker": {"invert": ["reserveTool"]},
    "TrafficLightController": {"invert": ["setGreen", "setRed"]},
}


def write_error(xml, fix, rng):
    """Return (xml with the diagram error, mtype)."""
    if "mod" in fix:
        old, new = fix["mod"]
        assert xml.count(f'value="{old}"') == 1, old
        return xml.replace(f'value="{old}"', f'value="{new}"'), "mod_opt"
    for name in fix["invert"]:
        pat = re.compile(rf'value="({re.escape(name)}\([^"]*\)) \{{0\.\.(\d+)\}}"')
        m = pat.search(xml)
        hi = int(m.group(2))
        xml = xml[:m.start()] + f'value="{m.group(1)} {{{hi}..{rng.randint(0, hi - 1)}}}"' + xml[m.end():]
    return xml, None


def main():
    out = os.path.join(DATASET, "batches", BATCH)
    if os.path.exists(out):
        raise SystemExit(f"{out} already exists")
    archive = os.path.join(DATASET, "archive", "round1_post_conversion_edits")
    os.makedirs(out)
    zall = zipfile.ZipFile(os.path.join(out, f"Rodin_Import_{BATCH}.zip"), "w", zipfile.ZIP_DEFLATED)
    for p in sorted(glob.glob(os.path.join(DATASET, "models", "model_*", "meta.json"))):
        old = json.load(open(p))
        mid, case = old["model_id"], old["case"]
        if mid == "model_001":
            continue
        redo = old["variant"] in ("mutated", "augmented")
        if redo and not os.path.exists(os.path.join(archive, "models", mid)):
            for sub, name in (("models", mid), ("sources", mid), (os.path.join("rodin_raw", "ml_pp"), old["rodin_project"])):
                shutil.copytree(os.path.join(DATASET, sub, name), os.path.join(archive, sub, name))

        xml = open(glob.glob(os.path.join(DATASET, "sources", mid, "*.drawio.xml"))[0]).read()
        mtype = old.get("mutation_type") if old["variant"] == "diagram_error" else None
        if old["variant"] == "mutated":
            xml, mtype = write_error(xml, FIXES[case], random.Random(int(mid[6:])))
        d = os.path.join(out, case)
        os.makedirs(d)
        xml_path = os.path.join(d, f"{case}.drawio.xml")
        open(xml_path, "w").write(xml)

        edges = extract_detailed_sequence(xml_path)
        if mtype is None and old["design_intent"] == "expected_fail":
            n = sum(1 for e in edges if e.get("duration")
                    and int(e["duration"].split("..")[0]) > int(e["duration"].split("..")[1]))
            framed = any(e.get("fragments") for e in edges if e.get("duration")
                         and int(e["duration"].split("..")[0]) > int(e["duration"].split("..")[1]))
            mtype = "inverted_frame" if n == 1 and framed else f"inverted{n}"
        rodin_exporter._next_export_name = lambda p, n=case: n
        txt = apply_rules_1_and_2(xml_path, 1)
        zbytes = rodin_exporter.generate_rodin_zip(xml_path, 1)
        zin = zipfile.ZipFile(io.BytesIO(zbytes))
        bum = zin.read(next(x for x in zin.namelist() if x.endswith(".bum"))).decode("utf-8")
        open(os.path.join(d, f"{case}_EventB.txt"), "w").write(txt)
        open(os.path.join(d, f"{case}_Rodin.zip"), "wb").write(zbytes)
        for name in zin.namelist():
            zall.writestr(name, zin.read(name))

        meta = {"case": case, "model_id": mid, "rodin_project": old["rodin_project"], "batch": BATCH,
                "operations": {}}
        if old["design_intent"] == "expected_fail":
            _, expected, desc = plan_ops(None, mtype, "diagram_error", edges, None, txt, bum)
            exp = expected([])
            meta.update({"design_intent": "expected_fail", "variant": "diagram_error", "mutation": desc,
                         "category": CATEGORY.get(mtype, "model_error"), "mutation_type": mtype,
                         "expected_failed_pos": exp, "expected_failed_count": len(exp)})
        else:
            meta.update({"design_intent": "expected_pass", "variant": "plain",
                         "mutation": "converter output, unchanged",
                         "expected_failed_pos": [], "expected_failed_count": 0})
        if redo:
            what = old.get("mutation") or "added " + "; ".join(old["added_invariants"].values())
            meta["round1_version"] = f"{old['variant']}: {what} (archived)"
        json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=2, ensure_ascii=False)
        status = "redone" if redo else "same" if txt == open(os.path.join(DATASET, "models", mid, "model.txt")).read() else "CHANGED"
        print(f"{mid} {case:24} {status:7} {meta['variant']:13} {meta.get('mutation_type', ''):15} "
              f"expected_failed={meta['expected_failed_count']}")
    zall.close()


if __name__ == "__main__":
    main()
