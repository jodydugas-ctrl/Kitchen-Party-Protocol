"""Read-only filters over one graph. Metaphors never upgrade evidence."""
from collections import deque
from .common import ScanError
from .scanner import verify_report


def view(report, specification):
    verify_report(report)
    kinds = set(specification["kinds"])
    nodes = [n for n in report["graph"]["nodes"] if (not kinds or n["kind"] in kinds)
             and max(n["loop_depth"], n["attributes"].get("nested_depth", 0)) >= specification["min_loop_depth"]]
    ids = {n["id"] for n in nodes}
    return {"schema": "scan.view/1", "graph_digest": report["graph_digest"], "filter": specification,
            "nodes": nodes, "edges": [e for e in report["graph"]["edges"] if e["src"] in ids and e["dst"] in ids],
            "evidence_upgraded": False, "gaps": report["graph"]["gaps"]}


def query(report, start, direction="impact", limit=256):
    verify_report(report)
    if direction not in ("impact", "dependencies") or not 1 <= limit <= 4096:
        raise ScanError("Invalid direction or traversal limit")
    nodes = {n["id"]: n for n in report["graph"]["nodes"]}
    if start not in nodes: raise ScanError("Unknown node ID")
    links = {}
    for edge in report["graph"]["edges"]:
        if edge["kind"] not in ("possible_call", "possible_import"): continue
        src, dst = edge["src"], edge["dst"]
        if direction == "impact": src, dst = dst, src
        links.setdefault(src, []).append((dst, edge["id"]))
    pending, seen, paths = deque([start]), {start}, []
    truncated = False
    while pending:
        current = pending.popleft()
        for target, eid in sorted(links.get(current, [])):
            if target in seen: continue
            if len(seen) >= limit:
                truncated = True
                continue
            seen.add(target)
            pending.append(target)
            paths.append({"from": current, "to": target, "edge": eid})
    return {"graph_digest": report["graph_digest"], "direction": direction, "nodes": [nodes[i] for i in sorted(seen)],
            "paths": paths, "truncated": truncated, "scope": "Possible static dependencies only; dynamic and external paths can be absent"}
