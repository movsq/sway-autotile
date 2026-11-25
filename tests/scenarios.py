"""Scenario suite: invariants after every step of normal use, no event loops, tab groups intact."""
import time

from lib import (by_title, check, check_open, cmd, finish, focus_events, geom, msg, parents, result, show,
                 spawn, tree, wid, windows)


def focus_and_check(title, label):
    t0 = tree()
    g0, e0 = geom(t0), focus_events()
    cmd(f"[con_id={by_title(t0, title)['id']}] focus")
    t = check(f"{label}: focus {title} -> invariant")
    result(geom(t) == g0, f"{label}: focus {title} -> geometry unchanged")
    got = focus_events() - e0
    result(got == 1, f"{label}: focus {title} -> exactly 1 focus event (got {got})")


print("== 1 open 4 windows")
for x in "abcd":
    spawn(x)
    check(f"1 open {x}")
show(tree())

print("== 2 focus cycling")
for x in "abcdacbd":
    focus_and_check(x, "2")

print("== 3 a new window halves the focused one along its longer side")
for target in "ab":
    cmd(f"[con_id={wid(target)}] focus")
    before = tree()
    spawn("n" + target)
    check_open(before, check(f"3 after opening n{target}"), "n" + target, "3")

print("== 4 tab groups survive")
cmd(f"[con_id={wid('c')}] focus")
cmd("layout tabbed")
spawn("tab2")
cmd(f"[con_id={wid('a')}] focus")
t = check("4 two tabs, focus elsewhere")
group = parents(t)[by_title(t, "c")["id"]]
result(group["layout"] == "tabbed" and len(group["nodes"]) == 2, "4 tab group [c, tab2] intact")
cmd(f"[con_id={wid('d')}] focus")
cmd("split v")
cmd("layout tabbed")
cmd(f"[con_id={wid('a')}] focus")
t = check("4 one-tab group, focus elsewhere")
group = parents(t)[by_title(t, "d")["id"]]
result(group["layout"] == "tabbed" and len(group["nodes"]) == 1,
       f"4 one-tab group [d] intact (parent {group['layout']}, {len(group['nodes'])} children)")

print("== 5 split chains")
cmd(f"[con_id={wid('b')}] focus")
for s in ("split h", "split v", "split h"):
    cmd(s)
cmd(f"[con_id={wid('a')}] focus")
check("5 chain on b removed once focus leaves")
cmd(f"[con_id={wid('b')}] focus")
for s in ("split v", "split h"):
    cmd(s)
cmd(f"[con_id={wid('nb')}] focus")
cmd(f"[con_id={wid('b')}] focus")
check("5 focused b keeps only its own wrapper")

print("== 6 marked containers are left alone")
t = tree()
wrapper = parents(t)[by_title(t, "b")["id"]]
if wrapper["type"] == "con" and len(wrapper["nodes"]) == 1:
    cmd(f"[con_id={wrapper['id']}] mark --add keepme")
    cmd(f"[con_id={wid('a')}] focus")
    result(wrapper["id"] in parents(tree()), "6 marked wrapper kept")
    cmd("unmark keepme")
else:
    result(False, "6 setup: b should have a wrapper while focused")

print("== 7 moves")
for m in ("move left", "move up", "move right", "move down", "move right", "move up"):
    cmd(m)
    check(f"7 {m}")
cmd("move container to workspace 2")
check("7 move to workspace 2")
cmd("workspace 2")
check("7 on workspace 2")
spawn("w2a")
spawn("w2b")
cmd(f"[con_id={wid('w2a')}] focus")
cmd("move container to workspace 1")
check("7 w2a back to workspace 1")
cmd("workspace 1")
check("7 on workspace 1")

print("== 8 floating / fullscreen")
for c in ("floating enable", "floating disable", "fullscreen enable", "fullscreen disable"):
    cmd(c)
    check(f"8 {c}")

print("== 9 closing windows")
for x in ("nb", "tab2", "a"):
    cmd(f"[con_id={wid(x)}] kill", settle=0.6)
    check(f"9 close {x}")
cmd("kill", settle=0.6)
check("9 close the focused window")

print("== 10 burst of 30 focus commands")
ids = list(windows(tree()))
e0 = focus_events()
for i in range(30):
    msg(f"[con_id={ids[i % len(ids)]}] focus")
time.sleep(1.5)
check("10 after the burst")
got = focus_events() - e0
result(got == 30, f"10 30 focus commands -> {got} focus events (more = a loop)")

print("== 11 a new window still halves the focused one")
cmd(f"[con_id={ids[0]}] focus")
before = tree()
spawn("last")
t = check("11 final")
check_open(before, t, "last", "11")
show(t)

finish()
