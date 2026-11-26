"""Focus levels from key bindings: one press of `focus parent`/`focus child` changes what is focused on screen.

The daemon keeps the focused window in a one-child wrapper, which looks exactly like the window. A key's
`focus parent` that stops there shows no change, so the daemon goes on past it. The sway config that `run`
writes binds Mod4+a to focus parent and Mod4+Shift+a to focus child; wtype presses them.

  F1  two windows: one press of focus parent selects both, one press of focus child the window again
  F2  back on a workspace left after focus parent: the window is focused, and a new window halves it
  F3  one window beside two stacked ones: the stacked pair, then all; focus child goes back down the same way
  F4  swaymsg focus parent (no binding event) keeps Sway's behaviour and stops on the wrapper
"""
import subprocess
import time

from lib import check, check_open, check_still, cmd, finish, nodes, result, spawn, tree, wid


def press(key, shift=False, settle=0.6):
    mods = ["logo", "shift"] if shift else ["logo"]
    args = ["wtype"]
    for m in mods:
        args += ["-M", m]
    args += ["-k", key]
    for m in reversed(mods):
        args += ["-m", m]
    subprocess.run(args, check=True)
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


def press_and_check(label, want, shift=False):
    before = tree()
    press("a", shift)
    after = tree()
    got = focused(after)
    result(got == want, f"{label}: focus {'child' if shift else 'parent'} -> {got}" + ("" if got == want else f", expected {want}"))
    check_still(before, after, label)


print("== F1 two windows")
spawn("a1")
spawn("a2")                                  # splith[a1, splitv[a2]], a2 focused in its wrapper
press_and_check("F1 first press", ["a1", "a2"])
press_and_check("F1 child", ["a2"], shift=True)
press_and_check("F1 again", ["a1", "a2"])

print("== F2 back on the workspace")
cmd("workspace 2")
cmd("workspace 1")
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
on_wrapper = any(c["focused"] and len(c["nodes"]) == 1 for c, _ in nodes(t))
result(on_wrapper, f"F4 swaymsg focus parent stops on b1's wrapper ({focused(t)})")

finish()
