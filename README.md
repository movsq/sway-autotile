# sway-autotile

Autotiling for [sway](https://swaywm.org) that also removes the invisible one-window containers its
splits leave behind. New windows split the focused one along its longer side, so windows form a spiral,
and each leftover container is removed once you move on.

It is one Python file that uses only the standard library and reacts to sway's IPC events instead of
polling.

## Why

Autotilers such as [autotiling-rs](https://github.com/ammgws/autotiling-rs) leave one-window containers
in the tree. They pick the direction of the next window by running `split v` or `split h` on the focused
window, and sway does that by wrapping the window in a new container with just that window inside. If
no window opens there, the wrapper stays. You can't see it, but `layout tabbed` then turns it into a tab
group with a single tab, and `move` and `resize` work on a level of the tree you didn't know was there.
Closing windows leaves the same kind of one-window containers behind, sometimes nested.

sway-autotile places windows exactly like autotiling-rs, which its tests check step by step, and removes
those containers as soon as they stop doing anything.

## What it does

- Splits the focused window along its longer side, `splitv` if it's taller than wide, else `splith`.
  It follows the same rules as autotiling-rs: no splits for floating or fullscreen windows, inside tabbed
  or stacked containers, or when the parent already has that layout.
- Removes one-window split containers with `split none` after every focus change, close, move or
  floating toggle. It keeps:
  - the focused window's own container, which decides where the next window goes;
  - tabbed and stacked containers (a tab group with one tab stays a tab group);
  - containers that are marked or focused.
- When it removed the container of a window whose longer side matches its parent's layout, it splits that
  window again on its next focus, so the next window still halves it instead of sharing the parent.
- Does both in one process, one event at a time, so a cleanup can't undo a split made a moment earlier.

Example: a sway tree where `two` was left inside its own `splitv` container and `one` has focus.

```
workspace splith
  one   (focused)   [con_id=5]
  splitv   [con_id=8]
    two   [con_id=6]
  three   [con_id=7]
```

```console
$ sway-autotile --once --dry-run
[con_id=6] split none; [con_id=5] splitv
```

`split none` removes the container around `two`, and `splitv` prepares `one`, which is taller than wide,
so the next window opens below it.

## Requirements

- sway (tested with 1.12)
- Python 3, standard library only (tested with 3.14)

## Install

```bash
git clone https://github.com/movsq/sway-autotile.git
install -Dm755 sway-autotile/sway-autotile ~/.local/bin/sway-autotile
```

Remove any other autotiler, such as `autotiling` or `autotiling-rs`, because two autotilers would split
the same windows. Then add it to your sway config:

```
exec ~/.local/bin/sway-autotile
```

To start it without logging out:

```bash
swaymsg exec ~/.local/bin/sway-autotile
```

`swaymsg reload` neither starts it again nor stops it, because sway runs `exec` lines only at startup.

## Usage

Without options it runs as a daemon, started from the sway config as above. It exits when sway does.

| Option | What it does |
| --- | --- |
| `--once` | one pass over the current tree, then exit |
| `--dry-run` | print the sway commands instead of running them |
| `--debug` | log every command it sends to stderr |

`--once --dry-run` only reads the tree, so it's safe to run in your session to see what the daemon would do.
It needs `SWAYSOCK`, which sway sets for everything it starts, including your terminal inside sway.

## Tests

```bash
tests/run              # everything, about 4.5 minutes
tests/run scenarios    # invariants in normal use: no leftover containers, no event loops, tab groups intact
tests/run sequences    # 9 seeded open/focus/close sequences; window geometry must match the baseline at every step
tests/run resize       # the case where cleaning up could change where windows open
```

Each case starts its own headless, software-rendered sway, so nothing happens in your session. The tests
need sway, python3 and kitty. To use another terminal with a `--title` option, set
`AUTOTILE_TEST_TERMINAL`. `SEEDS="1 2" tests/run sequences` runs a subset, and `KEEP=1` keeps the output
directory.

`tests/baseline/` holds the geometry autotiling-rs produces for the same sequences. `tests/run baseline`
records it again and needs `autotiling-rs`.

## Development

Issues and pull requests are welcome. Changes to `sway-autotile` should pass `tests/run`. The design
constraints in [AGENTS.md](AGENTS.md) explain the non-obvious parts: why `split none` is only sent for
whole runs of split containers, why windows are split again, and why it's one process.

## Acknowledgements

The split rules come from [autotiling-rs](https://github.com/ammgws/autotiling-rs) (MIT), which is also
the reference for window placement in the tests.

## License

MIT. See [LICENSE](LICENSE).
