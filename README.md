
# Mouse motion to left click (remapper for linux)
## Overview

The script [`remap_mouse.py`](remap_mouse.py) turns movement events from a chosen mouse into left
clicks. You'll need another mouse to move the cursor. Run this with:
```bash
sudo python3 remap_mouse.py
```

The file [`target_mouse.txt`](target_mouse.txt) contains your chosen mouse's device path. For example:
```
/dev/input/by-id/usb-Logitech_Gaming_Mouse_G402_6D9241915253-event-mouse
```



## Compatibility

This should work on any Linux desktop using Wayland or X11.

However, this was only tested on **Ubuntu with Wayland**.
The script uses Linux's `evdev` and `uinput` interfaces. It doesn't run on Windows
or macOS as written.

You'll need Python with `evdev` installed. You might also need to turn off
`libinput`'s debouncing feature.

## Remapping script details

All remapping behavior is in [`remap_mouse.py`](remap_mouse.py). It has no
configurable minimum delay or click-rate limit.

- `remap_events` reads one mouse event report at a time. Each report creates at most one click.
- Lines 40-43 actually generate the click by sending a press and release event to a virtual mouse.
- Any button presses or scrolling on the remapped mouse are not affected.
- `main` opens both the remapped mouse and the virtual output mouse, waits for the user to hit Enter, and then calls `remap_events`.
- `Ctrl+C` stops the script. A `with` block releases the remapped mouse's intercept and deletes the virtual mouse.

[`remap_mouse.py`](remap_mouse.py) imports Python's `contextlib` and `pathlib`, plus `evdev` for Linux input
and output. Other than that, the script is standalone. It does not import anything from `diagonstics/` or `tests/`. The only other file this script interacts with is [`target_mouse.txt`](target_mouse.txt).

## Setup and usage

Install evdev and find your target mouse:

```bash
sudo apt install python3-evdev
sudo python3 diagonstics/detect_mice.py
```

Put device path of your chosen mouse in `target_mouse.txt`, on one line with **no comments
or quotes**. Use the path that looks like `/dev/input/by-id/...-event-mouse` preferably. The event numbers in the other paths can change after rebooting.

Then run:

```bash
sudo python3 remap_mouse.py
```

Press Enter to start remapping. **Ctrl+C in that terminal
stops the script.** The script has no error handling so beware.

## Turn off debouncing if needed

If this tool only produces clicks when you move the remapped mouse very slowly, then `libinput` might be blocking the click events with its debouncing feature.

If this is happening, add the following to `/etc/libinput/local-overrides.quirks`:

```ini
[mouse_move_click intentional rapid clicks]
MatchName=mouse_move_click
ModelBouncingKeys=1
```

Keep `MatchName` as written: it matches the script's virtual mouse. **Reboot, then
start the remapper again.** This worked on the author's computer. It doesn't remove the game's
own click limit though, which depends on the version. See our
[version and CPS findings](docs/versions_and_cps_limit_findings.md).

## Optional device diagnostic tools

There's also a few tools that just observe inputs. Run them
from the top directory; Ctrl+C stops them.

This first script detects all mice connected to your computer and print their details:
```bash
sudo python3 diagonstics/detect_mice.py
```

The following prints all mouse events from all mice to the terminal:
```bash
sudo python3 diagonstics/print_mice_events.py
```

 And a script for measuring your clicks per second (cps) rate across all mice:
```bash
sudo python3 diagonstics/show_cps.py
```

Importantly, **this measures cps before libinput does any debouncing**, so if you're getting low cps in a game or application, you can use this script to check whether the problem is with debouncing or with the raw mouse events.

### Click interval distribution

To measure variation in the spacing of clicks, start the remapper first, then run:

```bash
sudo python3 diagonstics/variance_probe.py
```

The probe waits for the first completed left click, prints `Started!`, records
for 10 seconds, then exits. Like `show_cps.py`, it watches all mice and counts a press followed by a
release, confirmed at the end of the input report. To watch only one mouse, pass
`--device /dev/input/eventN` using its path from `detect_mice.py`. For remapped
clicks, choose the virtual `mouse_move_click` device.

It stores each release's observation time in memory as integer monotonic
nanoseconds and prints no further output until recording finishes. This preserves finer than
0.01 ms timestamp resolution on typical Linux systems; the reported clock
resolution is not a guarantee of observation accuracy. Python scheduling and
evdev read batching affect these times. The probe measures delivery to Python,
before libinput/browser filtering, rather than hardware timestamps.

The results show total clicks, the number of intervals (one fewer than clicks),
average, median, minimum and maximum delay, and population standard deviation.
A column of counts and percentages groups intervals rounded to the nearest
0.01 ms: `<=3.85`, `3.86`, `3.87`, through `4.14`, and `>=4.15` ms. Statistics
use unrounded intervals. Ctrl+C cancels; lost input stops the trial with an error.

## Development checks

The [`tests/`](tests/) check the remapper using fake devices and the variance
probe using simulated events and clock times:

```bash
python3 -m unittest discover -s tests -v
python3 diagonstics/show_cps.py --self-test
```
