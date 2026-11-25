"""Windows whose longer side already matches their parent's layout, the case where autotiling-rs would
let the next window join the parent (an equal share of it). Here it must halve the focused window.

  H  a wide window in a splith parent, after its wrapper was cleaned up (workspace 1)
  N  a wide window in a splith parent that never had a wrapper (workspace 2)
  V  a tall window in a splitv parent, after its wrapper was cleaned up (workspace 3)
"""
from lib import check, check_open, cmd, finish, show, spawn, tree, wid

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
finish()
