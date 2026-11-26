"""Shared helpers for the tests. They run inside the headless sway that `run` starts (SWAYSOCK points at it)."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import time

FAILS = []
EVENTS = os.environ.get("AUTOTILE_EVENTS", "")  # file written by events.py, one "change id" per line
TERMINAL = os.environ.get("AUTOTILE_TEST_TERMINAL", "kitty")
PROGRAM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sway-autotile")
GAP = 8  # "gaps inner" in the sway config that `run` writes; with smart_gaps a lone window has none


def load_program():
    """The program as a module, for its functions (load_options reads os.environ)."""
    loader = importlib.machinery.SourceFileLoader("sway_autotile", PROGRAM)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("sway_autotile", loader))
    loader.exec_module(module)
    return module


def option(key):
    """The value of a config option as the daemon of this case reads it (tests/run's CONFIG)."""
    return load_program().load_options(None)[key]


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


def rect(w):
    return [w["rect"][k] for k in ("x", "y", "width", "height")]


def focused_window(t):
    for c, _ in nodes(t):
        if c["focused"] and not c["nodes"]:
            return c
    return None


def workspace_windows(t, window_id):
    """Ids of the windows on the workspace that holds `window_id`."""
    for output in t["nodes"]:
        for ws in output["nodes"]:
            ids = {c["id"] for c, _ in nodes(ws) if not c["nodes"] and c.get("app_id") is not None}
            if window_id in ids:
                return ids
    return set()


def halves(r):
    """Where the focused window (rect r) and the new window go: r split along its longer side, the new
    window second, GAP between them, the first half rounded like sway does."""
    x, y, w, h = r
    if h > w:  # splitv
        a = int((h - GAP) / 2 + 0.5)
        return [x, y, w, a], [x, y + a + GAP, w, h - a - GAP]
    a = int((w - GAP) / 2 + 0.5)
    return [x, y, a, h], [x + a + GAP, y, w - a - GAP, h]


def check_open(before, after, title, label):
    """The window `title` just opened: it and the window focused before share that window's old place,
    half each along its longer side, and no other window moved."""
    f = focused_window(before)
    if f is None:
        result(False, f"{label}: no focused window before the open")
        return
    r = rect(f)
    if workspace_windows(before, f["id"]) == {f["id"]}:  # alone: smart_gaps gave it the whole workspace
        r = [r[0] + GAP, r[1] + GAP, r[2] - 2 * GAP, r[3] - 2 * GAP]
    want_f, want_new = halves(r)
    g0, g = geom(before), geom(after)
    new = by_title(after, title)
    got_f, got_new = list(g.get(f["id"], ())), rect(new) if new else None
    moved = [i for i in g0 if i != f["id"] and g.get(i) != g0[i]]
    ok = got_f == want_f and got_new == want_new and not moved
    result(ok, f"{label}: {title} halves {f['name']} {r[2]}x{r[3]}"
           + ("" if ok else f"  expected {want_f} + {want_new}, got {got_f} + {got_new}, others moved: {moved}"))


def check_still(before, after, label):
    """Nothing opened or closed: no window moved."""
    g0, g = geom(before), geom(after)
    moved = [i for i in g0 if g.get(i) != g0[i]]
    result(not moved, label + ": no window moved" + ("" if not moved else f"  moved: {moved}"))


def check_close(before, after, closed, label):
    """A window closed: the others only take over its space, none gets smaller."""
    g0, g = geom(before), geom(after)
    shrunk = [i for i in g0 if i != closed and (i not in g or g[i][2] < g0[i][2] or g[i][3] < g0[i][3])]
    result(not shrunk, label + ": no window got smaller" + ("" if not shrunk else f"  shrunk: {shrunk}"))


def finish():
    print("FAILURES:", FAILS if FAILS else "none", flush=True)
    raise SystemExit(1 if FAILS else 0)
