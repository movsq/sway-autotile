"""Windows whose longer side already matches their parent's layout, the case where autotiling-rs would
let the next window join the parent (an equal share of it). Here it must halve the focused window.

  H  a wide window in a splith parent, after its wrapper was cleaned up (workspace 1)
  N  a wide window in a splith parent that never had a wrapper (workspace 2)
  V  a tall window in a splitv parent, after its wrapper was cleaned up (workspace 3)
  F  a focused window resized from tall to wide before opening another (workspace 4)
  M  a focused window moved and resized before opening another (workspace 5)
  W  a lone window on a workspace turned across its longer side without a window event (workspace 6)
"""
from lib import by_title, check, check_open, cmd, finish, parents, result, show, spawn, tree, wid

# H: a was wrapped once, focus left it, cleanup removed the wrapper, then it was made wide
spawn("a")
spawn("b")
cmd(f"[con_id={wid('a')}] focus")
cmd(f"[con_id={wid('b')}] focus")
cmd(f"[con_id={wid('a')}] resize set width 1800 px")
cmd(f"[con_id={wid('a')}] focus")
before = tree()
spawn("c")
check_open(before, check("H"), "c", "H")

# N: a2 opened alone, b2 next to it; a2 is made wide without ever having had focus with a sibling
cmd("workspace 2")
spawn("a2")
spawn("b2")
cmd(f"[con_id={wid('a2')}] resize set width 1800 px")
cmd(f"[con_id={wid('a2')}] focus")
before = tree()
spawn("c2")
check_open(before, check("N"), "c2", "N")

# V: q tall in a splitv parent after its wrapper was cleaned up
cmd("workspace 3")
spawn("p")
spawn("q")                                   # splith[p, q]
cmd(f"[con_id={wid('q')}] focus")
spawn("r")                                   # q tall -> splitv[q, r]
cmd(f"[con_id={wid('q')}] focus")
cmd(f"[con_id={wid('p')}] focus")            # q wrapped while focused, cleaned up once focus left
cmd(f"[con_id={wid('q')}] resize set height 1330 px")
cmd(f"[con_id={wid('q')}] focus")
before = tree()
spawn("s")
t = check("V")
check_open(before, t, "s", "V")
show(t)
# F: resizing the currently focused window can leave its wrapper pointing the old way.
cmd("workspace 4")
spawn("a3")
spawn("b3")
cmd(f"[con_id={wid('a3')}] focus")
cmd(f"[con_id={wid('a3')}] resize set width 1800 px")
before = tree()
spawn("c3")
check_open(before, check("F"), "c3", "F")

# M: recheck the direction using the restored rectangle if the tile was resized after the move.
cmd("workspace 5")
spawn("a4")
spawn("b4")
cmd(f"[con_id={wid('a4')}] focus")
cmd("move right")
cmd("move right")
cmd(f"[con_id={wid('a4')}] resize set width 1800 px")
before = tree()
spawn("c4")
check_open(before, check("M"), "c4", "M")
before = tree()
spawn("d4")
check_open(before, check("M next open"), "d4", "M next open")

# W: a lone window on a workspace whose layout was turned across without a window event
cmd("workspace 6")
spawn("w1")
cmd("split v")
before = tree()
ws_before = parents(before)[by_title(before, "w1")["id"]]
result(ws_before["type"] == "workspace" and ws_before["layout"] == "splitv",
       f"W setup: w1 alone on splitv workspace ({ws_before['type']} {ws_before['layout']})")
spawn("w2")
after = check("W")
check_open(before, after, "w2", "W")
par = parents(after)
w1_parent = par[by_title(after, "w1")["id"]]
w2_top = par[by_title(after, "w2")["id"]]
result(w1_parent["type"] == "workspace" and w1_parent["layout"] == "splith"
       and par[w2_top["id"]]["id"] == w1_parent["id"] and len(w1_parent["nodes"]) == 2,
       f"W no extra container around [w1, w2] ({w1_parent['type']} {w1_parent['layout']}, {len(w1_parent['nodes'])} children)")

finish()
