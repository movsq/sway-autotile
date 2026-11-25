# sway-autotile

One Python daemon for sway: autotiling (the focused window is split along its longer side, so a new
window always takes half of it and windows form a spiral — the direction rule of
[autotiling-rs](https://github.com/ammgws/autotiling-rs)) plus cleanup of the one-child split containers
those splits leave behind once focus moves on.

## Layout

```
sway-autotile           # the program: Python 3 stdlib only, raw sway IPC, executable, no extension
PKGBUILD                # Arch package built from this checkout (makepkg); bump pkgver/pkgrel on release
tests/run               # the only entry point for tests
tests/scenarios.py      # invariants in normal use, no event loops, tab groups intact
tests/sequences.py      # 9 seeded open/focus/close sequences (SEEDS table), placement checked every step
tests/resize.py         # windows whose longer side already matches their parent's layout
tests/lib.py, events.py # helpers and the placement checks; event logger (counts focus events)
```

## Commands

```bash
./sway-autotile --once --dry-run   # safe in a live session: prints what it would do, changes nothing
./sway-autotile --debug            # logs every command to stderr — run it in a test sway, not a live session
tests/run                          # all tests, ~4.5 min; or: scenarios | sequences | resize
SEEDS="1 2" tests/run sequences    # a subset
```

## Testing

- Needs sway, python3 and kitty (`AUTOTILE_TEST_TERMINAL` picks another terminal with a `--title`
  option). Each case starts its own headless, software-rendered sway (`WLR_BACKENDS=headless`,
  `WLR_RENDERER=pixman`) with a fixed 2560x1440 output and config, detached from the session it runs in.
  Never point the program or the tests at a live session — windows would move under the user.
- Every change to `sway-autotile` must pass `tests/run` (all). The placement rule is checked directly
  (`lib.check_open`): after an open, the new window and the window focused before fill that window's old
  rectangle, half each along its longer side, and no other window moves; a focus moves nothing; a close
  shrinks nothing. A change meant to alter placement changes those checks — say so first.
- `lib.GAP` must equal `gaps inner` in the sway config `tests/run` writes. Keep a seed's action sequence
  in `sequences.py` unchanged, so failures stay comparable between runs.
- `shellcheck tests/run` for the runner; run Python with `python3 -B` (no `__pycache__`).

## Design constraints (each one was found by a failing test)

- `split none` flattens *every* one-child ancestor of its target, not one level → only send it when the
  whole run is splith/splitv; tabbed/stacked, focused or marked containers end a run.
- A focused window with siblings is split even when its parent already has the wanted layout
  (autotiling-rs skips that split, and the next window then gets an equal share of the parent instead of
  half). Only a window alone in its container needs no split, at most a `layout` change of that
  container. `tests/run resize` covers the windows this matters for.
- One process, one pass per event, all commands of a pass in one RUN_COMMAND: a separate autotiler +
  cleaner raced (a cleanup could remove a wrapper made for a window focused in the meantime).
- Cleanup runs on every focus/close/move/floating event, splits on focus/close/floating (not on focus
  only like autotiling-rs): sway sends the focus event for the next window *before* the close event, so a
  window that grows when its neighbour closes kept a split for its old shape (seeds 1, 4, 5 in
  `tests/run sequences`). Never split on `move`: sway's `move` first takes the window out of its
  one-child wrapper without moving it, so re-wrapping after each move kept the window in place for good
  (`tests/scenarios.py` section 12).
- `split`, `layout` and `split none` aimed at a con with `[con_id=]` emit no window event and don't move
  focus → no loop. `tests/scenarios.py` section 10: 30 focus commands → exactly 30 focus events.
- No dependencies beyond the Python standard library (no i3ipc): keep it that way.
