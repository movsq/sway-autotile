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

sway-autotile removes those containers as soon as they stop doing anything, and a new window takes
half of the focused one, also where autotiling-rs would give it a smaller share.

## What it does

- Splits the focused tile along its longer side so the next window takes half of it. Floating,
  fullscreen, tabbed, and stacked windows keep Sway's native layout behavior.
- Prepares the focused tile at startup and after focus, close, and floating changes. When a window
  opens, it checks the split direction again in case the focused tile was resized. Sway's
  directional move of a prepared tile only takes it out of its split. When a key binding ran the
  move, sway-autotile sends it again and prepares the tile, so one press moves it. A move from
  `swaymsg` or a script sends no binding event: the first one only takes the tile out of its split,
  and the tile is prepared again when another window opens or focus changes.
- Removes one-window split containers with `split none` after every focus change, close, move or
  floating toggle. It keeps:
  - the focused window's own container, which decides where the next window goes;
  - tabbed and stacked containers, so a tab group with one tab stays a tab group;
  - containers that are marked or focused.
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

Copy the script into your `PATH`:

```bash
git clone https://github.com/movsq/sway-autotile.git
install -Dm755 sway-autotile/sway-autotile ~/.local/bin/sway-autotile
```

Or, on Arch Linux, build a package from the checkout with the `PKGBUILD` in the repository. It installs
to `/usr/bin/sway-autotile`:

```bash
cd sway-autotile
makepkg -si
```

## Configuration

Remove any other autotiler, such as `autotiling` or `autotiling-rs`, because two autotilers would split
the same windows. Then add this line to your sway config, or `exec sway-autotile` if you installed the
package:

```
exec ~/.local/bin/sway-autotile
```

To start it without logging out, run the command for your installation.

```bash
swaymsg exec ~/.local/bin/sway-autotile   # script installed manually
swaymsg exec sway-autotile               # Arch package
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
tests/run              # everything, about 5 minutes
tests/run scenarios    # invariants in normal use: no leftover containers, no event loops, tab groups intact
tests/run sequences    # 9 seeded open/focus/close sequences; placement checked after every step
tests/run resize       # windows whose longer side already matches their parent's layout
tests/run keys         # one press of a move key binding moves the window (needs wtype)
tests/run cli          # every option and error exit: --help, --once, --dry-run, no SWAYSOCK
```

Each case starts its own headless, software-rendered sway, so nothing happens in your session. The tests
need sway, python3 and kitty, and `tests/run keys` needs wtype. To use another terminal with a
`--title` option, set `AUTOTILE_TEST_TERMINAL`. `SEEDS="1 2" tests/run sequences` runs a subset, and
`KEEP=1` keeps the output directory.

After each window opens, the tests check that the new window and the window focused before it fill the
old rectangle of the focused window, half each along its longer side, and that no other window moved. A
focus change must move no window, and a close must make none smaller.

## Development

Issues and pull requests are welcome. Changes to `sway-autotile` should pass `tests/run`. The design
constraints in [AGENTS.md](AGENTS.md) explain the non-obvious parts: why `split none` is only sent for
whole runs of split containers, why windows are split even when their parent already has the right
layout, and why it's one process.

## Acknowledgements

The split direction rule comes from [autotiling-rs](https://github.com/ammgws/autotiling-rs) (MIT).

## License

MIT. See [LICENSE](LICENSE).
