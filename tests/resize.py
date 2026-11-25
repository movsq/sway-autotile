"""The case where cleaning up wrappers could change placement: a window whose longer side matches its
parent's layout. Under autotiling-rs it still sits in its old wrapper and the next window halves it.
Writes the geometry to OUT as JSON; `run` compares it with baseline/resize.json (autotiling-rs).

Usage: resize.py OUT
"""
import json
import sys

from lib import by_title, cmd, show, spawn, tree, wid


def rect(t, title):
    r = by_title(t, title)["rect"]
    return [r["x"], r["y"], r["width"], r["height"]]


out = {}
# H: a wide window in a splith parent
spawn("a")
spawn("b")
cmd(f"[con_id={wid('a')}] focus")
cmd(f"[con_id={wid('b')}] focus")          # a got a wrapper, focus left it
cmd(f"[con_id={wid('a')}] resize set width 1800 px")
cmd(f"[con_id={wid('a')}] focus")
out["H_before_a"] = rect(tree(), "a")
spawn("c")
t = tree()
out["H_after"] = {n: rect(t, n) for n in "abc"}

# V (workspace 2): a tall window in a splitv parent
cmd("workspace 2")
spawn("p")
spawn("q")                                   # splith[p, q]
cmd(f"[con_id={wid('q')}] focus")
spawn("r")                                   # q tall -> splitv[q, r]
cmd(f"[con_id={wid('q')}] focus")
cmd(f"[con_id={wid('p')}] focus")            # q wide -> wrapped in splith, focus left it
cmd(f"[con_id={wid('q')}] resize set height 1330 px")
cmd(f"[con_id={wid('q')}] focus")
out["V_before_q"] = rect(tree(), "q")
spawn("s")
t = tree()
out["V_after"] = {n: rect(t, n) for n in "pqrs"}
show(t)

with open(sys.argv[1], "w") as f:
    json.dump(out, f)
