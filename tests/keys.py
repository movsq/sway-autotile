"""Moves from key bindings: one press of a `move <dir>` key moves the focused window, as without the daemon.

The sway config that `run` writes binds Mod4+Shift+h/j/k/l to move left/down/up/right; wtype presses them
through a virtual keyboard, so Sway sends binding events as for a real key.

  K1  a wrapped window moves right and back with one press each; the next opens need no repair
  K2  each press of left/up/down/right moves the window, also across levels of the tree
  K3  two presses sent at once move the window twice
  K4  swaymsg moves (no binding event) still move it on the second command, then keys again on the first
  K5  closing a sibling unwraps the ancestor above the focused wrapper, and one press still moves
  K6  a compound `move ..., mark ...` binding keeps unwrapped across window::mark and still rewraps
"""
import os
import subprocess
import time

from lib import EVENTS, by_title, check, check_open, cmd, finish, focused_window, rect, result, spawn, tree, wid

KEYS = {"left": "h", "down": "j", "up": "k", "right": "l"}


def press(*directions, settle=0.6):
    args = ["wtype", "-M", "logo", "-M", "shift"]
    for d in directions:
        args += ["-k", KEYS[d]]
    subprocess.run(args + ["-m", "shift", "-m", "logo"], check=True)
    time.sleep(settle)


def events():
    with open(EVENTS) as f:
        return [line.split() for line in f]


def since(start, change, node_id=None):
    return sum(1 for c, i in events()[start:] if c == change and (node_id is None or int(i) == node_id))


def order(*titles):
    t = tree()
    return sorted(titles, key=lambda n: by_title(t, n)["rect"]["x"])


def press_and_check(direction, label):
    before = tree()
    f = focused_window(before)
    start = len(events())
    press(direction)
    after = check(f"{label}: {direction}")
    moved = rect(by_title(after, f["name"])) != rect(f)
    result(moved, f"{label}: one press of move {direction} moves {f['name']}")
    focus, moves = since(start, "focus"), since(start, "move")
    result(focus == 0 and moves <= 2, f"{label}: move {direction} -> {focus} focus, {moves} move events")


def open_and_check(title, label):
    before = tree()
    start = len(events())
    spawn(title)
    check_open(before, check(f"{label}: open {title}"), title, label)
    new = wid(title)
    repaired = since(start, "move", new) + since(start, "mark")
    result(repaired == 0, f"{label}: {title} opens in place, no repair ({repaired} move/mark events)")


print("== K1 one press moves a wrapped window")
spawn("k1")
spawn("k2")                                  # splith[k1, k2]
cmd(f"[con_id={wid('k1')}] focus")           # k1 gets its splitv wrapper
start = len(events())
press("right")
check("K1 move right")
result(order("k1", "k2") == ["k2", "k1"], f"K1 one press of move right: k1 on the right ({order('k1', 'k2')})")
got = since(start, "move", wid("k1"))
result(got == 2, f"K1 move right -> {got} move events (Sway's unwrap + the repeated move)")
press("left")
check("K1 move left")
result(order("k1", "k2") == ["k1", "k2"], f"K1 one press of move left: k1 back on the left ({order('k1', 'k2')})")
open_and_check("k3", "K1 after key moves")
open_and_check("k4", "K1 next open")

print("== K2 every direction, one press each")
cmd("workspace 2")
spawn("v1")
spawn("v2")
spawn("v3")                                  # splith[v1, splitv[v2, v3]], v3 focused
for d in ("left", "up", "down", "right", "up", "left"):
    press_and_check(d, "K2")
open_and_check("v4", "K2 after key moves")

print("== K3 two presses at once move twice")
cmd("workspace 3")
spawn("x1")
spawn("x2")
cmd(f"[con_id={wid('x2')}] focus")
spawn("x3")                                  # x3 below x2
press("right")                               # x3 to the right of x2: splith[x1, x2, x3]
result(order("x1", "x2", "x3") == ["x1", "x2", "x3"], f"K3 setup: a row ({order('x1', 'x2', 'x3')})")
cmd(f"[con_id={wid('x1')}] focus")
press("right", "right", settle=1.0)
check("K3 after two presses")
result(order("x1", "x2", "x3") == ["x2", "x3", "x1"], f"K3 two presses: x1 moved twice ({order('x1', 'x2', 'x3')})")
open_and_check("x4", "K3 after the presses")

print("== K4 swaymsg moves keep today's behaviour, keys move on the first press again")
cmd("workspace 4")
spawn("s1")
spawn("s2")
cmd(f"[con_id={wid('s1')}] focus")
cmd("move right")                            # no binding event: Sway only takes s1 out of its wrapper
result(order("s1", "s2") == ["s1", "s2"], f"K4 first swaymsg move right only unwraps ({order('s1', 's2')})")
cmd("move right")
result(order("s1", "s2") == ["s2", "s1"], f"K4 second swaymsg move right moves ({order('s1', 's2')})")
press("left")                                # s1 not wrapped: Sway moves it, the daemon wraps it again
result(order("s1", "s2") == ["s1", "s2"], f"K4 key move left after swaymsg moves ({order('s1', 's2')})")
press("right")                               # wrapped again: the key's move is repeated
result(order("s1", "s2") == ["s2", "s1"], f"K4 next key move right ({order('s1', 's2')})")
check("K4")
open_and_check("s3", "K4 after key moves")

print("== K5 move key after closing sibling")
cmd("workspace 5")
spawn("c1")
spawn("c2")
cmd(f"[con_id={wid('c2')}] focus")
spawn("c3")                                  # splith[c1, splitv[c2, splith[c3]]]
cmd(f"[con_id={wid('c2')}] kill", settle=0.6)
check("K5 after closing sibling")
press("left")
check("K5 move left")
result(order("c1", "c3") == ["c3", "c1"],
       f"K5 one press of move left after close: c3 on the left ({order('c1', 'c3')})")
open_and_check("c4", "K5 after move")

print("== K6 compound move + mark binding preserves unwrapped across window::mark")
with open(os.environ["AUTOTILE_SWAY_CONFIG"], "a") as f:
    f.write("bindsym Mod4+Shift+u move right, mark k6\n")
cmd("reload", settle=1)
cmd("workspace 6")
spawn("u1")
spawn("u2")
cmd(f"[con_id={wid('u1')}] focus")
start = len(events())
subprocess.run(["wtype", "-M", "logo", "-M", "shift", "-k", "u", "-m", "shift", "-m", "logo"], check=True)
time.sleep(0.6)
marks = since(start, "mark", wid("u1"))
result(marks >= 1, f"K6 compound binding emitted window::mark ({marks})")
check("K6 after move+mark binding")
open_and_check("u3", "K6 after move+mark binding")

finish()
