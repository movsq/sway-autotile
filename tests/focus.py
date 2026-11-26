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
"""
import json
import os
import signal
import subprocess
import time

from lib import by_title, check, check_open, check_still, cmd, finish, msg, nodes, parents, result, spawn, tree, wid


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

finish()
