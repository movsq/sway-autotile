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
tests/keys.py           # one press of a `move` key binding moves the window (wtype presses the keys)
tests/focus.py          # one press of a `focus parent`/`focus child` key changes the focus on screen
tests/cli.py            # every documented way to run it: --help, --once, --dry-run, plain daemon, errors
tests/lib.py, events.py # helpers and the placement checks; event logger (counts focus events)
```

## Commands

```bash
./sway-autotile --once --dry-run   # safe in a live session: prints what it would do, changes nothing
./sway-autotile --debug            # logs every command to stderr — run it in a test sway, not a live session
tests/run                          # all tests, ~5 min; or: scenarios | sequences | resize | keys | focus | cli
SEEDS="1 2" tests/run sequences    # a subset
```

## Testing

- Needs sway, python3 and kitty (`AUTOTILE_TEST_TERMINAL` picks another terminal with a `--title`
  option); `tests/run keys` and `tests/run focus` also need wtype and are skipped without it. Each
  case starts its own headless, software-rendered sway (`WLR_BACKENDS=headless`,
  `WLR_RENDERER=pixman`) with a fixed 2560x1440 output and config, detached from the session it runs in.
  Never point the program or the tests at a live session — windows would move under the user.
- Every change to `sway-autotile` must pass `tests/run` (all). The placement rule is checked directly
  (`lib.check_open`): after an open, the new window and the window focused before fill that window's old
  rectangle, half each along its longer side, and no other window moves; a focus moves nothing; a close
  shrinks nothing. A change meant to alter placement changes those checks — say so first.
- Every documented option, combination and exit path (README "Usage") has a section in `tests/cli.py`, and
  `tests/run` checks that the daemon exits when sway does. A new option or exit path gets a section there.
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
  cleaner raced (a cleanup could remove a wrapper made for a window focused in the meantime). The one
  exception is the open repair below: its follow-up pass runs on the daemon's own tagged tick.
- The daemon prepares the focused split at startup and after focus/close/floating events. Sway can
  send a focus event before a close changes the next window's shape (seeds 1, 4, 5).
- Cleanup also runs on move. Never split on a `move` event: sway's directional move of a wrapped
  tile only takes it out of its wrapper, into the wrapper's slot (and resets the siblings' sizes, so
  the tile's rect can change). Rewrapping on every move would keep it in place for good. A key
  binding is the exception: its `binding` event follows its move event, so if that move only
  unwrapped the tile, the daemon sends the same `move` again and then wraps the tile. swaymsg,
  scripts and mouse drags send no binding event and keep the old rule.
- Whether a move only unwrapped is decided from the event stream, not from a tree read alone: a
  tree read after a key press can already show the next press. After each split the daemon sends a
  tick naming the tile and its wrapper's slot; the tile's next move event consumes it and only
  unwrapped if the tile is now in that slot. `tests/run keys` K3 sends two presses at once.
- If an opening joins the focused tile's siblings, wrap the old tile and move the new tile into the
  wrapper. A tagged IPC tick then rechecks the restored rectangle and prepares the next split,
  including when Sway keeps focus on the old tile. Scenarios 12–14 cover moves, manual `split none`,
  and opens that keep focus on the old tile.
- Sway can resize the focused tile without sending a window event. On `new`, recheck the direction
  using the rectangle occupied by the pair if it already shares a split. The F and M cases in
  `tests/run resize` check an open after a resize without refocusing, including after a move.
- `split`, `layout` and `split none` aimed at a con with `[con_id=]` emit no window event and don't move
  focus → no loop. `tests/scenarios.py` section 10: 30 focus commands → exactly 30 focus events. The open
  repair is the exception: its `mark` and `move container to mark` emit window events, so the daemon
  skips the new window's focus and move events until its tick arrives. The repeated key move emits
  a move event but no binding event, and only binding events repeat moves.
- A key's `focus parent` can stop on the focused window's wrapper, which looks like the window: on
  its binding event the daemon moves the focus one level on screen, past one-child split cons
  (`[con_id=]` matches no workspace: for one it focuses the con below and sends `focus parent`).
  As with moves, the press's start comes from the event stream, not from a tree read, which can
  already show the next press: the con focused last per window and workspace focus events and the
  daemon's own focus commands. If later presses already took the focus beyond the target, it stays.
  If a press finds the focus still on the window a focus event put it on, a later press of the other
  key undid it (that window's focus event comes between their binding events): nothing is sent (F9).
  `swaymsg focus parent` sends no event, so that con is only used while the focus lies in the press's
  direction from it. Known limit: after `swaymsg focus parent`, a key press that finds the focus past
  its target can't be told from a burst, so the next key press starts from that target (a `focus
  child` key can then go two levels). `tests/run focus` F5 stops the daemon while Sway runs two presses.
- A workspace focus event can restore focus to such a wrapper, and a window opened then lands beside it
  (a third, not a half), so the daemon focuses the window inside (F2), read from a fresh tree and only
  while the focus is still on that workspace: `workspace 6; workspace 2` runs both before the daemon
  reads the first event (F7). Only a wrapper a focus key went past (or focused on the way to the
  workspace) is left: one picked with `swaymsg focus parent` stays (F8). Known limit: `swaymsg focus
  child` onto a wrapper a key went past sends no event either, so on return the daemon still moves the
  focus off that one. The daemon keeps one such wrapper per workspace, set by a focus key there and
  dropped by the next window focus there; a key press that changes nothing keeps it (F10). Sway reports
  `fullscreen_mode` 1 for every workspace, so only a con counts as fullscreen: two presses that Sway
  itself takes to the workspace still record the wrapper (F11). Workspace events are handled before a
  move event's result is passed on, so one can't drop a key move's rewrap (on sway 1.12 none came
  between them in tests).
- No dependencies beyond the Python standard library (no i3ipc): keep it that way.
