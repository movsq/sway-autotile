"""Seeded random open/focus/close sequence; checks the placement rules after every step.

Usage: sequences.py SEED
  open   the new window and the window focused before split that window's old place in half
         along its longer side; no other window moves
  focus  no window moves
  close  no window gets smaller
plus the invariant from lib.check (no leftover one-child split containers) after every step.
Keep the action sequence of a seed unchanged, so a failure can be compared with older runs.
"""
import random
import sys

from lib import check, check_close, check_open, check_still, cmd, finish, spawn, tree, wid

# seed: (steps, probability boundary for focus vs close)
SEEDS = {1: (30, 0.85), 2: (30, 0.85), 3: (30, 0.85),
         4: (35, 0.7), 5: (35, 0.7), 6: (35, 0.7), 7: (35, 0.7), 8: (35, 0.7), 9: (35, 0.7)}

seed = int(sys.argv[1])
steps, focus_p = SEEDS[seed]
rng = random.Random(seed)
opened, alive = 0, []
for step in range(steps):
    before = tree()
    r = rng.random()
    if not alive or (r < 0.4 and len(alive) < 9):
        opened += 1
        title = f"w{opened}"
        spawn(title, settle=0.7)
        alive.append(title)
        act = f"open {title}"
    elif r < focus_p:
        title = rng.choice(alive)
        cmd(f"[con_id={wid(title)}] focus", settle=0.5)
        act = f"focus {title}"
    else:
        title = rng.choice(alive)
        closed = wid(title)
        cmd(f"[con_id={closed}] kill", settle=0.7)
        alive.remove(title)
        act = f"close {title}"
    label = f"seed {seed} step {step} {act}"
    t = check(label)
    if act.startswith("open"):
        if len(alive) > 1:
            check_open(before, t, title, label)
    elif act.startswith("focus"):
        check_still(before, t, label)
    else:
        check_close(before, t, closed, label)
finish()
