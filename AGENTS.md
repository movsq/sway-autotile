# sway-autotile

One Python daemon for sway: autotiling (the focused window is split along its longer side, so new
windows form a spiral — the rules and placement of [autotiling-rs](https://github.com/ammgws/autotiling-rs))
plus cleanup of the one-child split containers those splits leave behind once focus moves on.

## Layout

```
sway-autotile           # the program: Python 3 stdlib only, raw sway IPC, executable, no extension
tests/run               # the only entry point for tests
tests/scenarios.py      # invariants in normal use, no event loops, tab groups intact
tests/sequences.py      # 9 seeded open/focus/close sequences (SEEDS table)
tests/resize.py         # the case where cleanup could change placement
tests/compare.py        # geometry vs baseline
tests/lib.py, events.py # helpers; event logger (counts focus events)
tests/baseline/         # geometry recorded with autotiling-rs alone (package 0.2.1; the binary says 0.2.0)
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
- Every change to `sway-autotile` must pass `tests/run` (all). A placement difference against
  `tests/baseline/` is a bug unless the change is meant to alter placement — then say so before
  re-recording.
- `tests/run baseline` re-records the baseline with autotiling-rs (needs it installed). The baseline
  depends on the test sway's config in `tests/run` (gaps, borders, output size): change that config and the
  baseline has to be re-recorded. Never change `sequences.py` in a way that alters the action sequence of
  a seed.
- `shellcheck tests/run` for the runner; run Python with `python3 -B` (no `__pycache__`).

## Design constraints (each one was found by a failing test)

- `split none` flattens *every* one-child ancestor of its target, not one level → only send it when the
  whole run is splith/splitv; tabbed/stacked, focused or marked containers end a run.
- autotiling-rs skips the split when the window's preferred direction equals its parent's layout. A window
  this program unwrapped would then get 1/n of the parent instead of half → `unwrapped` set + re-split on
  its next focus. Remove that and `tests/run resize` fails.
- One process, one pass per event, all commands of a pass in one RUN_COMMAND: a separate autotiler +
  cleaner raced (a cleanup could remove a wrapper made for a window focused in the meantime).
- Splits happen on focus events only (like autotiling-rs); cleanup also on close/move/floating.
- `split`, `layout` and `split none` aimed at a con with `[con_id=]` emit no window event and don't move
  focus → no loop. `tests/scenarios.py` section 10: 30 focus commands → exactly 30 focus events.
- No dependencies beyond the Python standard library (no i3ipc): keep it that way.
