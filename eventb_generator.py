from xml_parser import (
    extract_base_name_from_xml,
    extract_fragments_from_xml,
    extract_detailed_sequence,
    build_time_model,
    build_loop_model,
    build_frag_vars,
    edge_guard_conditions,
    sanitize_conditions,
)


def _data_items(data):
    return [d.strip() for d in (data or '').split(',') if d.strip()]


def _data_map(m, data):
    return ", ".join(f"{m} ↦ {d}" for d in _data_items(data))


def _partition(set_name, elements):
    """Enumerated-set axiom that also asserts every element is distinct.
    Empty element list degrades to `set_name = ∅` (matches rodin_exporter)."""
    if not elements:
        return f"{set_name} = ∅"
    parts = ", ".join(f"{{{e}}}" for e in elements)
    return f"partition({set_name}, {parts})"


def generate_step_events(edges, time_model=None):
    events = []
    for i, edge in enumerate(edges, 1):
        m = f"{edge['msg']}_{i}"
        snd, rcv, data = edge['sender'], edge['receiver'], edge['data']
        suffix = edge.get('opt_suffix', "")
        conds = edge_guard_conditions(edge)

        send = f"""
    send{m}{suffix}
    WHEN
        grd1: {m} ∉ sentMessages
        grd2: currentMessage = ∅"""
        grd_idx = 3
        preds = edge.get('pred_idxs', [])
        if preds:
            pred_g = " ∨ ".join(f"{edges[p]['msg']}_{p + 1} ∈ receivedMessages" for p in preds)
            send += f"\n        grd{grd_idx}: {pred_g}"
            grd_idx += 1
        for cond_clean in conds:
            send += f"\n        grd{grd_idx}: {cond_clean}"
            grd_idx += 1
        send += f"""
    THEN
        act1: sentMessages := sentMessages ∪ {{{m}}}
        act2: sender := sender ∪ {{{m} ↦ {snd}}}
        act3: receiver := receiver ∪ {{{m} ↦ {rcv}}}
        act4: receivedMessages := ∅"""
        act_idx = 5
        dmap = _data_map(m, data)
        if dmap:
            send += f"\n        act{act_idx}: senderdataMessages := senderdataMessages ∪ {{{dmap}}}"
            act_idx += 1
            send += f"\n        act{act_idx}: currentMessage := {{{m}}}"
        else:
            send += f"\n        act{act_idx}: currentMessage := {{{m}}}"
        send += "\n    END"

        receive = f"""
    receive{m}{suffix}
    WHEN
        grd1: {m} ∈ sentMessages
        grd2: {m} ↦ {snd} ∈ sender
        grd3: {m} ↦ {rcv} ∈ receiver
        grd4: {m} ∉ receivedMessages
        grd5: currentMessage = {{{m}}}"""
        grd_idx = 6
        for cond_clean in conds:
            receive += f"\n        grd{grd_idx}: {cond_clean}"
            grd_idx += 1
        receive += f"""
    THEN
        act1: receivedMessages := receivedMessages ∪ {{{m}}}"""
        r_idx = 2
        dmap = _data_map(m, data)
        if dmap:
            receive += f"\n        act{r_idx}: receiverdataMessages := receiverdataMessages ∪ {{{dmap}}}"
            r_idx += 1
        receive += f"\n        act{r_idx}: currentMessage := ∅"
        r_idx += 1
        if time_model and i in time_model["success"]:
            ts, tt, td = time_model["success"][i]
            receive += f"\n        act{r_idx}: {ts} := {tt} + {td}"
        receive += "\n    END"

        events.extend([send, receive])
    return "\n".join(events)


def apply_rules_1_and_2(xml_path: str, version: int = 1) -> str:
    base_name = extract_base_name_from_xml(xml_path)
    fragments = extract_fragments_from_xml(xml_path)
    edges = extract_detailed_sequence(xml_path)

    objects = sorted(list(set([e['sender'] for e in edges] + [e['receiver'] for e in edges])))
    msg_instances = [f"{e['msg']}_{i}" for i, e in enumerate(edges, 1)]
    raw_messages = sorted(list(set([e['msg'] for e in edges])))
    data_messages = sorted({d for e in edges for d in _data_items(e['data'])})

    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"

    sanitize_conditions(edges, set(objects) | set(msg_instances)
                        | set(raw_messages) | set(data_messages))
    conditions = [c for e in edges for c in e.get('conditions', [])]
    frag_vars, enum_consts = build_frag_vars(conditions, fragments)
    time_model = build_time_model(edges)
    loop_model = build_loop_model(edges, fragments)
    for v in loop_model["counters"]:            # loop counters start at 0
        frag_vars[v] = {'op': '=', 'val': '0', 'kind': 'counter'}

    base_vars = ["sentMessages", "sender", "receiver", "receivedMessages",
                 "senderdataMessages", "currentMessage", "receiverdataMessages"]
    all_vars = base_vars + list(frag_vars.keys()) + time_model["vars"]

    invs = [
        "inv1: sentMessages ⊆ Messages",
        "inv2: currentMessage ⊆ Messages",
        "inv3: sender ⊆ Messages × Objects",
        "inv4: receiver ⊆ Messages × Objects",
        "inv5: receivedMessages ⊆ sentMessages",
        "inv6: senderdataMessages ⊆ Messages × DataMessages",
        "inv7: receiverdataMessages ⊆ Messages × DataMessages"
    ]
    inv_idx = 8
    for v in frag_vars.keys():
        invs.append(f"inv{inv_idx}: {v} ∈ ℤ")
        inv_idx += 1
    for pred in time_model["invs"]:
        invs.append(f"inv{inv_idx}: {pred}")
        inv_idx += 1

    inits = [
        "act1: sentMessages := ∅",
        "act2: sender := ∅",
        "act3: receiver := ∅",
        "act4: receivedMessages := ∅",
        "act5: senderdataMessages := ∅",
        "act6: receiverdataMessages := ∅",
        "act7: currentMessage := ∅"
    ]
    act_idx = 8
    for v, details in frag_vars.items():
        val, kind = details['val'], details.get('kind', 'int')
        if kind == 'counter':
            inits.append(f"act{act_idx}: {v} := 0")
        elif kind == 'free':
            inits.append(f"act{act_idx}: {v} :∈ ℤ")
        elif kind == 'range':
            inits.append(f"act{act_idx}: {v} :∈ 0..{val}")
        else:
            inits.append(f"act{act_idx}: {v} := {val}")
        act_idx += 1
    for var, kind, val in time_model["inits"]:
        if kind == "range":
            inits.append(f"act{act_idx}: {var} :∈ {val}")
        else:
            inits.append(f"act{act_idx}: {var} := {val}")
        act_idx += 1

    enum_const_line = f"\n    {', '.join(enum_consts)}" if enum_consts else ""
    enum_axioms = "".join(f"\n    axm{4 + j}: {ev} = {j}" for j, ev in enumerate(enum_consts))

    # Only message instances are declared as constants — raw message names are
    # unused by the machine (kept out to match the exported .buc).
    return f"""CONTEXT {context_name}
SETS
    Objects; Messages; DataMessages
CONSTANTS
    {", ".join(objects)}
    {", ".join(msg_instances)}
    {", ".join(data_messages) if data_messages else "/* No Data */"}{enum_const_line}
AXIOMS
    axm1: {_partition("Objects", objects)}
    axm2: {_partition("Messages", msg_instances)}
    axm3: {_partition("DataMessages", data_messages)}{enum_axioms}
END

MACHINE {machine_name}
SEES {context_name}
VARIABLES
    {", ".join(all_vars)}
INVARIANTS
    {"\n    ".join(invs)}
EVENTS
    INITIALISATION BEGIN
        {"\n        ".join(inits)}
    END

{generate_step_events(edges, time_model)}
{_checkloop_events(loop_model)}
END"""


def _checkloop_events(loop_model):
    """Extra events that count loop rounds (grd retry < N, act retry := retry + 1)."""
    out = ""
    for chk in loop_model["checks"]:
        v, n = chk["var"], chk["bound"]
        guards = chk.get("guards", [])
        guard_lines = "".join(f"        grd{i + 1}: {g}\n" for i, g in enumerate(guards))
        bound_idx = len(guards) + 1
        out += (f"\n    {chk['name']}\n"
                f"    WHEN\n"
                f"{guard_lines}"
                f"        grd{bound_idx}: {v} < {n}\n"
                f"    THEN\n"
                f"        act1: {v} := {v} + 1\n"
                f"    END\n")
    return out
