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
  F14 the first window resized to 500 px, a window, a splith group last; focus parent from the first
  F15 the same with a splitv group
  F16 a marked one-child container first (holding a splitv group), a window: mark, group and order survive
  F17 a splitv workspace (the windows after the new one move up)
  F18 a workspace with only a floating window: focus parent from it, then a tiled window opens normally
  F19 two no_focus windows (`no_focus [title="^nf"]` in the sway config): the workspace stays selected
  F20 a splitv workspace around one splith container: the new window gets no extra container level
  F21 a marked one-child splitv around a splith group first, the window from which the workspace is
      selected last: mark, group and order survive, and the new window opens last in every mode (half
      needs a move after which Sway would dissolve that pair, so it only puts the window at the end)
  `tests/run focus` runs this file once per workspace_open value and names it in
  AUTOTILE_EXPECT_WORKSPACE_OPEN. With end, F14-F17, F19 and F20 check that the new window is last and
  (F14, F15, F17, F19) that every window's rect equals Sway's own end placement, built on another workspace
  from the last child. With half, F12-F20 check that the new window takes the workspace's right half and
  the old windows keep their layout in the left half (F14-F17, F19, F20: in their old proportions); with
  sway, Sway's placement: the new window opens right after the window focused last.
"""
import json
import os
import signal
import subprocess
import time

from lib import GAP, by_title, check, check_open, check_still, cmd, finish, geom_by_title, halves, msg, nodes, parents, result, spawn, tree, wid, windows, workspace_windows


DAEMON = int(os.environ.get("AUTOTILE_DAEMON_PID") or 0)  # the daemon `run` started for this case
# The daemon's workspace_open, as `run` configured it: not read through the program's own loader.
MODE = os.environ.get("AUTOTILE_EXPECT_WORKSPACE_OPEN")
if MODE not in ("end", "half", "sway"):
    raise SystemExit(f"focus.py: AUTOTILE_EXPECT_WORKSPACE_OPEN must be end, half or sway (tests/run sets it), got {MODE!r}")


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


def top_of(t, title):
    """(the workspace child that holds window `title`, the workspace)."""
    parent_of, node = parents(t), by_title(t, title)
    while parent_of[node["id"]]["type"] != "workspace":
        node = parent_of[node["id"]]
    return node, parent_of[node["id"]]


def slot_of(t, title):
    """Index of the workspace child that holds window `title`."""
    node, ws = top_of(t, title)
    return [c["id"] for c in ws["nodes"]].index(node["id"])


LEFT, RIGHT = halves([GAP, GAP, 2560 - 2 * GAP, 1440 - 2 * GAP])  # the workspace's halves (output 2560x1440)


def check_half(t, old, new, label, before=None):
    """half: `new` takes the workspace's right half, the windows in `old` fill the left half. With
    `before` (the tree before the open): each keeps its place there, scaled into the left half."""
    g = geom_by_title(t)
    xs = [g[w][0] for w in old] + [g[w][0] + g[w][2] for w in old]
    ok = g[new] == RIGHT and min(xs) == LEFT[0] and max(xs) == LEFT[0] + LEFT[2]
    off = []
    if before:
        g0, scale = geom_by_title(before), LEFT[2] / (2560 - 2 * GAP)
        for w in old:
            want = [LEFT[0] + (g0[w][0] - GAP) * scale, g0[w][1], g0[w][2] * scale, g0[w][3]]
            if any(abs(a - b) > 2 * GAP for a, b in zip(g[w], want)):
                off.append(f"{w} {g[w]} (was {g0[w]})")
    result(ok and not off, f"{label}: {new} {g[new]} takes the right half {RIGHT}, {', '.join(old)} the left half {LEFT}"
           + (" in their old proportions" if before else "") + (f"  off: {off}" if off else ""))


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


def workspace_focused(t, name, label):
    ws = next(w for w in json.loads(msg("-t", "get_workspaces")) if w["name"] == name)
    node = next((n for n, _ in nodes(t) if n["type"] == "workspace" and n["name"] == name), None)
    result(bool(node) and node["focused"] and ws["focused"], f"{label}: workspace {name} focused ({focused(t)})")


def select_and_open(ws, start, titles, label):
    """Focus window `start`, select workspace `ws` with one focus parent press, open the windows `titles`.
    Returns (tree before, tree after) for each open."""
    cmd(f"[con_id={wid(start)}] focus")
    press("a")
    workspace_focused(tree(), str(ws), f"{label} focus parent")
    out = []
    for title in titles:
        before = tree()
        spawn(title)
        out.append((before, tree()))
    return out


def check_mode(label, before, t, start, new, ref=None):
    """`new` opened on the workspace a focus parent press selected from window `start`; `before`: the tree
    before. end: `new` is last and, with `ref` = (titles, the same windows on a reference workspace where
    Sway put the window at the end itself), every window's rect equals its reference's. half: see
    check_half. sway: right after `start`."""
    there = workspace_windows(before, by_title(before, start)["id"])
    old = sorted(w["name"] for i, w in windows(before).items() if i in there)
    slot, last = slot_of(t, new), len(top_of(t, new)[1]["nodes"]) - 1
    if MODE == "half":
        check_half(t, old, new, label, before)
    elif MODE == "sway":
        result(slot == slot_of(t, start) + 1, f"{label}: {new} opens right after {start}, Sway's placement: slot {slot}")
    else:
        got, want = (rects(t, ref[0] + [new]), rects(t, ref[1])) if ref else (None, None)
        result(slot == last and got == want, f"{label}: {new} opens at the end, slot {slot}"
               + (f", like Sway puts it there: {got}" if ref else "") + ("" if got == want else f", expected {want}"))


def group_last(ws, p, layout):
    """Workspace `ws`: splith[p1 500 px wide, p4, group[p2, p3] with layout `layout`]. Returns the group's id."""
    cmd(f"workspace {ws}")
    for i in range(1, 5):
        spawn(f"{p}{i}")                         # splith[p1, splitv[p2, splith[p3, splitv[p4]]]]
    cmd(f"[con_id={wid(p + '4')}] move right")   # out of its wrapper
    cmd(f"[con_id={wid(p + '4')}] move right")   # out of the group: splith[p1, splitv[p2, p3], p4]
    group = top_of(tree(), p + "3")[0]["id"]
    cmd(f"[con_id={group}] move right")          # it swaps places with p4
    cmd(f"[con_id={wid(p + '2')}] layout {layout}")
    cmd(f"[con_id={wid(p + '1')}] resize set width 500 px")
    return group


for label, layout, ws, p, q in (("F14", "splith", 16, "r", "s"), ("F15", "splitv", 18, "t", "u")):
    print(f"== {label} the first window resized, a {layout} group last, focus parent from the first")
    group_last(ws, p, layout)
    [(before, after)] = select_and_open(ws, p + "1", [p + "5"], label)
    check(f"{label} open {p}5")
    if MODE == "end":                            # the reference: the group focused, Sway puts q5 after it
        cmd(f"[con_id={group_last(ws + 1, q, layout)}] focus")
        spawn(q + "5")
    ref = ([p + str(i) for i in range(1, 5)], [q + str(i) for i in range(1, 6)])
    check_mode(label, before, tree(), p + "1", p + "5", ref)

print("== F16 a marked container first: mark, group and order survive")
cmd("workspace 20")
for w in ("w1", "w2", "w3"):
    spawn(w)                                     # splith[w1, splitv[w2, splith[w3]]]
group = top_of(tree(), "w2")[0]["id"]
cmd(f"[con_id={group}] move left")               # splith[splitv[w2, w3], w1]
cmd(f"[con_id={group}] split h")
marked = parents(tree())[group]["id"]
cmd(f"[con_id={marked}] mark keep")              # splith[splith keep[splitv[w2, w3]], w1]
[(before, after)] = select_and_open(20, "w1", ["w4"], "F16")
t = check("F16 open w4")
m = next((n for n, _ in nodes(t) if n["id"] == marked), {"marks": None, "nodes": []})
kids = [[c["name"] for c in n["nodes"]] for n in m["nodes"]]
result(m["marks"] == ["keep"] and [n["id"] for n in m["nodes"]] == [group] and kids == [["w2", "w3"]],
       f"F16 the marked con {marked} {m['marks']} still holds the group {[n['id'] for n in m['nodes']]} with {kids}")
check_mode("F16", before, t, "w1", "w4")

print("== F17 a splitv workspace: focus parent from the top window")
opened = {}
for ws, p, start in ((21, "y", "y1"), (22, "z", "z2")):  # 22, the reference: from the last child, Sway's end
    if ws == 22 and MODE != "end":
        break
    cmd(f"workspace {ws}")
    spawn(p + "1")
    spawn(p + "2")
    cmd(f"[con_id={wid(p + '1')}] focus parent; layout splitv")  # splitv[p1, splitv[p2]]
    opened[ws] = select_and_open(ws, start, [p + "3"], f"F17 {ws}")
check_mode("F17", opened[21][0][0], check("F17 open"), "y1", "y3", (["y1", "y2"], ["z1", "z2", "z3"]))

print("== F18 a workspace with only a floating window: focus parent from it, then open")
cmd("workspace 23")
spawn("fl1")
cmd("floating enable")
press("a")
workspace_focused(tree(), "23", "F18 focus parent")
spawn("fl2")
node = by_title(check("F18 open fl2"), "fl2")
result(node["type"] == "con" and node["focused"] and node["rect"]["width"] == 2560,
       f"F18 fl2 opens tiled over the whole workspace, focused: {node['type']}, {node['rect']['width']} wide")

print("== F19 two no_focus windows opened on the selected workspace")
for ws, p, start in ((24, "q", "q1"), (25, "o", "o2")):  # 25, the reference: from the last child, Sway's end
    if ws == 25 and MODE != "end":
        break
    cmd(f"workspace {ws}")
    spawn(p + "1")
    spawn(p + "2")                               # splith[p1, splitv[p2]]
    opened[ws] = select_and_open(ws, start, [f"nf{p}1", f"nf{p}2"], f"F19 {ws}")
    workspace_focused(tree(), str(ws), f"F19 {ws} after two no_focus opens")
(before1, after1), (before2, _) = opened[24]
check_mode("F19 nfq1", before1, after1, "q1", "nfq1")
# sway: no event since the key press runs a cleanup, so q1's wrapper it went past is left, as after any press
t = tree() if MODE == "sway" else check("F19 open")
check_mode("F19 nfq2", before2, t, "q1", "nfq2", (["q1", "q2", "nfq1"], ["o1", "o2", "nfo1", "nfo2"]))

print("== F20 one splith container on a splitv workspace: no new level")
cmd("workspace 26")
spawn("v1")
spawn("v2")
press("a")
cmd("split v")                                   # splitv[splith[v1, splitv[v2]]], that splith focused
press("a")
workspace_focused(tree(), "26", "F20 focus parent")
group = top_of(tree(), "v1")[0]["id"]
before = tree()
spawn("v3")
t = check("F20 open v3")
ws = top_of(t, "v3")[1]
kids, layout = [c["id"] for c in ws["nodes"]], "splith" if MODE == "half" else "splitv"
result(kids == [group, top_of(t, "v3")[0]["id"]] and ws["layout"] == layout,
       f"F20 the workspace ({ws['layout']}, expected {layout}) holds the container and v3, no level between: {kids}")
if MODE == "half":
    check_half(t, ["v1", "v2"], "v3", "F20", before)

print("== F21 a marked one-child splitv around a splith group first: Sway's squash would dissolve both")
cmd("workspace 27")
for w in ("sq1", "sq2", "sq3"):
    spawn(w)                                     # splith[sq1, splitv[sq2, splith[sq3]]]
group = top_of(tree(), "sq2")[0]["id"]
cmd(f"[con_id={group}] move left")               # splith[splitv[sq2, sq3], sq1]
cmd(f"[con_id={wid('sq2')}] layout splith")      # the group across its parent's way: splith[sq2, sq3]
cmd(f"[con_id={group}] split v")
marked = parents(tree())[group]["id"]
cmd(f"[con_id={marked}] mark sq")                # splith[splitv sq[splith[sq2, sq3]], sq1]
[(before, after)] = select_and_open(27, "sq1", ["sq4"], "F21")
t = check("F21 open sq4")
m = next((n for n, _ in nodes(t) if n["id"] == marked), {"marks": None, "nodes": []})
kids = [[c["name"] for c in n["nodes"]] for n in m["nodes"]]
result(m["marks"] == ["sq"] and [n["id"] for n in m["nodes"]] == [group] and kids == [["sq2", "sq3"]],
       f"F21 the marked con {marked} {m['marks']} still holds the group {[n['id'] for n in m['nodes']]} with {kids}")
# sq1 is last, so every mode leaves sq4 after it. half would need the move that squashes: it only goes
# to the end, sizes as Sway gives them.
slots = [slot_of(t, w) for w in ("sq2", "sq1", "sq4")]
widths = [top_of(t, w)[0]["rect"]["width"] for w in ("sq2", "sq1", "sq4")]
result(slots == [0, 1, 2] and max(widths) - min(widths) <= 1,
       f"F21 sq4 opens last, in thirds like Sway's end placement: slots {slots}, widths {widths}")

finish()
