"""Focus levels from key bindings: one press of `focus parent`/`focus child` changes what is focused on screen.

The daemon keeps the focused window in a one-child wrapper, which looks exactly like the window. A key's
`focus parent` that stops there shows no change, so the daemon goes on past it. The sway config that `run`
writes binds Mod4+a to focus parent, Mod4+Shift+a to focus child and Mod4+m to `move container to
workspace 9, workspace 9`; wtype presses them.

  F1  two windows: one press of focus parent selects both, one press of focus child the window again
  F2  back on a workspace left after focus parent: Sway gives the focus to the window's wrapper (checked with
      the daemon stopped), the daemon focuses the window, and a new window halves it
  F3  one window beside two stacked ones: the stacked pair, then all; focus child goes back down the same way
  F4  swaymsg focus parent (no binding event) keeps Sway's behaviour and stops on the wrapper
  F5  two presses of focus parent sent at once go up two levels on screen, two of focus child back down;
      the daemon is stopped during the presses, so its tree reads already show both
  F6  a key moves the focused window to another workspace and follows it: a new window halves it there
      (covers handling workspace events first; on sway 1.12 no workspace event comes between a key's
      move and binding events, so it can't catch that regression there)
  F7  a workspace passed through on the way to another (`workspace 6; workspace 2`) doesn't take the focus back
  F8  swaymsg focus parent onto a window's wrapper, after a key's focus parent and focus child there: back
      on the workspace, the focus stays on the wrapper
  F9  focus parent, then focus child, sent at once with the daemon stopped: the window is focused again
  F10 focus parent once more on the workspace (a no-op): back on the workspace, the window is focused and
      a new window halves it
  F11 two presses of focus parent at once (daemon stopped) that Sway itself takes to the workspace: back on
      the workspace, the window is focused and a new window halves it
  F12 focus parent from the left of two windows selects the workspace: a new window opens right of both,
      as it does from the right one (Sway alone puts it after the window focused last, between them)
  F13 the same with a split group last on the workspace: the new window opens right of the group
  `tests/run focus` runs this file once per workspace_open value. With half, F12 and F13 check that the new
  window takes the workspace's right half and the old windows keep their layout in the left half; with
  sway, Sway's placement: the new window opens right after the window focused last.
"""
import json
import os
import signal
import subprocess
import time

from lib import GAP, by_title, check, check_open, check_still, cmd, finish, geom_by_title, halves, msg, nodes, option, parents, result, spawn, tree, wid


DAEMON = int(os.environ.get("AUTOTILE_DAEMON_PID") or 0)  # the daemon `run` started for this case


def press(key, shift=False, settle=0.6, times=1, hold=False):
    """hold: stop the daemon while Sway runs the presses, so it reads each binding event late."""
    mods = ["logo", "shift"] if shift else ["logo"]
    args = ["wtype"]
    for m in mods:
        args += ["-M", m]
    args += ["-k", key] * times
    for m in reversed(mods):
        args += ["-m", m]
    wtype(args, settle, hold)


def wtype(args, settle, hold):
    """Run a wtype command line, then wait `settle` seconds. hold: as for press()."""
    if hold and DAEMON:
        os.kill(DAEMON, signal.SIGSTOP)
    try:
        subprocess.run(args, check=True)
        if hold:
            time.sleep(0.3)
    finally:
        if hold and DAEMON:
            os.kill(DAEMON, signal.SIGCONT)
    time.sleep(settle)


def focused(t):
    """Window names under the focused node (all of a workspace's windows for a workspace)."""
    for output in t["nodes"]:
        for ws in output["nodes"]:
            for n in [ws] + [c for c, _ in nodes(ws)]:
                if n["focused"]:
                    leaves = [c for c, _ in nodes(n) if not c["nodes"] and c.get("app_id") is not None]
                    return sorted(c["name"] for c in leaves) if n["nodes"] else [n["name"]]
    return []


def on_wrapper_of(t, title):
    """The focused con is the wrapper of window `title`: its parent, a con with that one child."""
    wrapper = parents(t).get(by_title(t, title)["id"])
    return bool(wrapper) and wrapper["focused"] and wrapper["type"] == "con" and len(wrapper["nodes"]) == 1


def press_and_check(label, want, shift=False, times=1, hold=False):
    before = tree()
    press("a", shift, settle=0.6 * times, times=times, hold=hold)
    after = tree()
    got = focused(after)
    what = f"{times} x " * (times > 1) + f"focus {'child' if shift else 'parent'}"
    result(got == want, f"{label}: {what} -> {got}" + ("" if got == want else f", expected {want}"))
    check_still(before, after, label)


print("== F1 two windows")
spawn("a1")
spawn("a2")                                  # splith[a1, splitv[a2]], a2 focused in its wrapper
press_and_check("F1 first press", ["a1", "a2"])
press_and_check("F1 child", ["a2"], shift=True)
press_and_check("F1 again", ["a1", "a2"])

print("== F2 back on the workspace")
cmd("workspace 2")
if DAEMON:
    os.kill(DAEMON, signal.SIGSTOP)              # Sway's own restore, before the daemon reacts
try:
    cmd("workspace 1")
    t = tree()
    result(on_wrapper_of(t, "a2"), f"F2 Sway focuses a2's wrapper on workspace 1 ({focused(t)})")
finally:
    if DAEMON:
        os.kill(DAEMON, signal.SIGCONT)
time.sleep(0.35)
got = focused(tree())
result(got == ["a2"], f"F2 back on workspace 1: {got} focused")
before = check("F2 back")
spawn("a3")
check_open(before, check("F2 open a3"), "a3", "F2")

print("== F3 one window beside two stacked ones")
cmd("workspace 3")
spawn("b1")
spawn("b2")
cmd(f"[con_id={wid('b2')}] focus")
spawn("b3")                                  # splith[b1, splitv[b2, splith[b3]]], b3 focused
press_and_check("F3 first press", ["b2", "b3"])
press_and_check("F3 second press", ["b1", "b2", "b3"])
press_and_check("F3 child", ["b2", "b3"], shift=True)
press_and_check("F3 child again", ["b3"], shift=True)
check("F3")

print("== F4 swaymsg focus parent")
cmd(f"[con_id={wid('b1')}] focus")
cmd("focus parent")
t = tree()
result(on_wrapper_of(t, "b1"), f"F4 swaymsg focus parent stops on b1's wrapper ({focused(t)})")

print("== F5 two presses at once")
cmd("workspace 4")
spawn("c1")
spawn("c2")
cmd(f"[con_id={wid('c2')}] focus")
spawn("c3")                                  # splith[c1, splitv[c2, splith[c3]]], c3 focused
result(DAEMON != 0, "F5 the daemon's pid is known")
press_and_check("F5 two presses", ["c1", "c2", "c3"], times=2, hold=True)
press_and_check("F5 two child presses", ["c3"], shift=True, times=2, hold=True)
check("F5")

print("== F6 a key moves the window to another workspace and follows it")
cmd("workspace 9")
spawn("d1")
cmd("workspace 5")
spawn("e1")
spawn("e2")                                  # e2 focused, wrapped
press("m")                                   # e2 to workspace 9 beside d1, focus follows it
t = check("F6 moved")
got = focused(t)
result(got == ["e2"], f"F6 e2 focused on workspace 9: {got} focused")
spawn("e3")
check_open(t, check("F6 open e3"), "e3", "F6")

print("== F7 passing through a workspace")
cmd("workspace 6")
spawn("g1")
spawn("g2")
press_and_check("F7 focus parent", ["g1", "g2"])  # workspace 6 focused, g2's wrapper below it
cmd("workspace 2")
cmd("workspace 6; workspace 2", settle=0.8)
ws = [w["name"] for w in json.loads(msg("-t", "get_workspaces")) if w["focused"]]
result(ws == ["2"], f"F7 workspace 6; workspace 2 -> workspace {ws} focused")

print("== F8 swaymsg focus parent, then back on the workspace")
cmd("workspace 7")
spawn("h1")
spawn("h2")                                  # h2 focused, wrapped
press_and_check("F8 focus parent", ["h1", "h2"])
press_and_check("F8 child", ["h2"], shift=True)
cmd("focus parent")
t = tree()
result(on_wrapper_of(t, "h2"), f"F8 swaymsg focus parent stops on h2's wrapper ({focused(t)})")
cmd("workspace 2")
cmd("workspace 7", settle=0.8)
t = tree()
result(on_wrapper_of(t, "h2"), f"F8 back on workspace 7: focus stays on h2's wrapper ({focused(t)})")

print("== F9 focus parent, then focus child, at once")
cmd("workspace 8")
spawn("i1")
spawn("i2")                                  # splith[i1, splitv[i2]], i2 focused in its wrapper
before = tree()
wtype(["wtype", "-M", "logo", "-k", "a", "-M", "shift", "-k", "a", "-m", "shift", "-m", "logo"], 1.2, True)
t = tree()
result(by_title(t, "i2")["focused"], f"F9 focus parent + focus child -> i2 focused ({focused(t)})")
check_still(before, t, "F9")

print("== F10 focus parent on the workspace, then back on it")
cmd("workspace 10")
spawn("j1")
spawn("j2")
press_and_check("F10 focus parent", ["j1", "j2"])  # workspace 10 focused, j2's wrapper below it
press_and_check("F10 focus parent again", ["j1", "j2"])
cmd("workspace 2")
cmd("workspace 10", settle=0.8)
t = check("F10 back")
result(by_title(t, "j2")["focused"], f"F10 back on workspace 10: j2 focused ({focused(t)})")
spawn("j3")
check_open(t, check("F10 open j3"), "j3", "F10")

print("== F11 two presses at once up to the workspace, then back on it")
cmd("workspace 11")
spawn("x1")
spawn("x2")                                  # splith[x1, splitv[x2]], x2 focused in its wrapper
press_and_check("F11 two presses", ["x1", "x2"], times=2, hold=True)  # Sway: x2, its wrapper, workspace
cmd("workspace 2")
cmd("workspace 11", settle=0.8)
t = check("F11 back")
result(by_title(t, "x2")["focused"], f"F11 back on workspace 11: x2 focused ({focused(t)})")
spawn("x3")
check_open(t, check("F11 open x3"), "x3", "F11")


def rects(t, titles):
    g = geom_by_title(t)
    return [g.get(title) for title in titles]


def slot_of(t, title):
    """Index of the workspace child that holds window `title`."""
    parent_of, node = parents(t), by_title(t, title)
    while parent_of[node["id"]]["type"] != "workspace":
        node = parent_of[node["id"]]
    return [c["id"] for c in parent_of[node["id"]]["nodes"]].index(node["id"])


MODE = option("workspace_open")  # sway: Sway's placement, right after the window focused last
LEFT, RIGHT = halves([GAP, GAP, 2560 - 2 * GAP, 1440 - 2 * GAP])  # the workspace's halves (output 2560x1440)


def check_half(t, old, new, label):
    """half: `new` takes the workspace's right half, the windows in `old` fill the left half."""
    g = geom_by_title(t)
    xs = [g[w][0] for w in old] + [g[w][0] + g[w][2] for w in old]
    ok = g[new] == RIGHT and min(xs) == LEFT[0] and max(xs) == LEFT[0] + LEFT[2]
    result(ok, f"{label}: {new} {g[new]} takes the right half {RIGHT}, {', '.join(old)} the left half {LEFT}")


print(f"== F12 focus parent on the workspace from the left window, then open (workspace_open {MODE})")
# Sway puts a window opened on a focused workspace after the child focused last there; the daemon
# moves it to the end, as with the last child focused (workspace 13: Sway's own result), or gives it
# half the workspace.
for ws, start in ((12, "k1"), (13, "l2")):
    cmd(f"workspace {ws}")
    p = "k" if ws == 12 else "l"
    spawn(p + "1")
    spawn(p + "2")                               # splith[p1, splitv[p2]]
    cmd(f"[con_id={wid(start)}] focus")          # 12: splith[splitv[k1], k2], k1 focused
    press_and_check(f"F12 focus parent on {ws}", [p + "1", p + "2"])
    spawn(p + "3")
    t = check(f"F12 open {p}3")
    result(by_title(t, p + "3")["focused"], f"F12 {p}3 focused")
got, want = rects(t, ["k1", "k3", "k2"] if MODE == "sway" else ["k1", "k2", "k3"]), rects(t, ["l1", "l2", "l3"])
where = {"end": "right of k1 and k2 like l3 does", "half": "in the right half like l3 does",
         "sway": "between k1 and k2, Sway's placement"}[MODE]
slot = {"end": 2, "half": 1, "sway": 1}[MODE]
result(slot_of(t, "k3") == slot and got == want,
       f"F12 k3 opens {where}: {got}, slot {slot_of(t, 'k3')}" + ("" if got == want else f", expected {want}"))
if MODE == "half":
    check_half(t, ["k1", "k2"], "k3", "F12")

print("== F13 the same with a split group last on the workspace")
for ws, presses in ((14, 1), (15, 2)):
    cmd(f"workspace {ws}")
    p = "m" if ws == 14 else "n"
    spawn(p + "1")
    spawn(p + "2")
    cmd(f"[con_id={wid(p + '2')}] focus")
    spawn(p + "3")                               # splith[p1, splitv[p2, splith[p3]]], p3 focused
    if ws == 14:
        cmd(f"[con_id={wid('m1')}] focus")       # m1 wrapped, the group last
    for i in range(presses):
        press_and_check(f"F13 focus parent on {ws} ({i + 1})", [p + "1", p + "2", p + "3"] if ws == 14 or i else ["n2", "n3"])
    spawn(p + "4")
    t = check(f"F13 open {p}4")
if MODE == "sway":
    got = [slot_of(t, w) for w in ("m1", "m4", "m2", "m3")]
    result(got == [0, 1, 2, 2], f"F13 m4 opens between m1 and the group, Sway's placement: slots {got}")
else:
    got, want = rects(t, ["m1", "m2", "m3", "m4"]), rects(t, ["n1", "n2", "n3", "n4"])
    slot = 2 if MODE == "end" else 1
    result(slot_of(t, "m4") == slot and got == want,
           f"F13 m4 opens right of the group like n4 does: {got}, slot {slot_of(t, 'm4')}"
           + ("" if got == want else f", expected {want}"))
    if MODE == "half":
        check_half(t, ["m1", "m2", "m3"], "m4", "F13")

finish()
