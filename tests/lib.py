"""Shared helpers for the tests. They run inside sway-sandbox (SWAYSOCK points at the sandbox)."""
import json
import os
import subprocess
import time

FAILS = []
EVENTS = os.environ.get("AUTOTILE_EVENTS", "")  # file written by events.py, one "change id" per line
TERMINAL = os.environ.get("AUTOTILE_TEST_TERMINAL", "kitty")


def msg(*args):
    return subprocess.run(["swaymsg", *args], capture_output=True, text=True).stdout


def cmd(command, settle=0.35):
    results = json.loads(msg(command))
    if not all(r.get("success") for r in results):
        print("   command failed:", command, results)
    time.sleep(settle)


def tree():
    return json.loads(msg("-t", "get_tree"))


def nodes(node, out=None):
    """(node, parent) for every node below `node`, floating ones included."""
    out = [] if out is None else out
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        out.append((child, node))
        nodes(child, out)
    return out


def windows(t):
    return {c["id"]: c for c, _ in nodes(t)
            if c["type"] in ("con", "floating_con") and not c["nodes"] and c.get("app_id") is not None}


def by_title(t, title):
    for w in windows(t).values():
        if w["name"] == title:
            return w
    return None


def wid(title):
    return by_title(tree(), title)["id"]


def geom(t):
    return {w["id"]: (w["rect"]["x"], w["rect"]["y"], w["rect"]["width"], w["rect"]["height"])
            for w in windows(t).values()}


def geom_by_title(t):
    return {w["name"]: [w["rect"][k] for k in ("x", "y", "width", "height")] for w in windows(t).values()}


def parents(t):
    return {c["id"]: p for c, p in nodes(t)}


def show(t):
    def walk(n, depth=0):
        if n["type"] == "workspace" and n["name"].startswith("__"):
            return
        if n["type"] in ("con", "workspace", "floating_con"):
            r = n["rect"]
            print("      " + "  " * depth, n["id"], n["type"] if n["type"] != "con" else "", n["layout"],
                  n.get("name") if n.get("app_id") else "", f'{r["width"]}x{r["height"]}',
                  "*F*" if n["focused"] else "", n["marks"] or "")
        for c in n["nodes"] + n.get("floating_nodes", []):
            walk(c, depth + 1)
    for output in t["nodes"]:
        for ws in output["nodes"]:
            walk(ws)


def check(label):
    """Invariant: the only one-child split containers left are the focused window's own wrapper and
    ones in a run that holds a tabbed/stacked or marked container."""
    t = tree()
    parent_of = parents(t)
    bad = []
    for c, _ in nodes(t):
        if c["type"] != "con" or len(c["nodes"]) != 1 or c["layout"] not in ("splith", "splitv"):
            continue
        child = c["nodes"][0]
        if child["focused"] and not child["nodes"]:
            continue
        run, x = [c], c
        while len(x["nodes"]) == 1 and len(x["nodes"][0]["nodes"]) == 1:
            x = x["nodes"][0]
            run.append(x)
        y = parent_of.get(c["id"])
        while y and y["type"] == "con" and len(y["nodes"]) == 1:
            run.append(y)
            y = parent_of.get(y["id"])
        if any(r["layout"] in ("tabbed", "stacked") or r["marks"] for r in run):
            continue
        bad.append(c["id"])
    result(not bad, label + ("" if not bad else f"  leftover one-child splits: {bad}"))
    if bad:
        show(t)
    return t


def result(ok, label):
    print(("PASS " if ok else "FAIL ") + label, flush=True)
    if not ok:
        FAILS.append(label)


def focus_events():
    with open(EVENTS) as f:
        return sum(1 for line in f if line.startswith("focus "))


def spawn(title, settle=0.8):
    before = len(windows(tree()))
    msg(f"exec {TERMINAL} --title {title}")
    for _ in range(50):
        time.sleep(0.1)
        if len(windows(tree())) > before:
            break
    time.sleep(settle)


def halved(before, after, layout, tol=12):
    if layout == "splitv":
        return after["width"] == before["width"] and abs(after["height"] - before["height"] / 2) <= tol
    return after["height"] == before["height"] and abs(after["width"] - before["width"] / 2) <= tol


def finish():
    print("FAILURES:", FAILS if FAILS else "none", flush=True)
    raise SystemExit(1 if FAILS else 0)
