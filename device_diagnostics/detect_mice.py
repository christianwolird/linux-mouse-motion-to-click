#!/usr/bin/env python3
"""List mouse candidates. This standalone script never grabs or writes input."""

import argparse
from contextlib import closing
from pathlib import Path
import sys


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        from evdev import InputDevice, ecodes as e
    except ImportError:
        print("Install Python evdev first; see README.md.", file=sys.stderr)
        return 1

    # Do not use evdev.list_devices(): it silently omits inaccessible devices.
    try:
        paths = sorted(p for p in Path("/dev/input").iterdir()
                       if p.name.startswith("event"))
    except OSError as error:
        print(f"Cannot list /dev/input: {error}", file=sys.stderr)
        return 1

    found = inaccessible = 0
    for path in paths:
        try:
            with closing(InputDevice(str(path))) as device:
                caps = device.capabilities()
                if not ({e.REL_X, e.REL_Y} <= set(caps.get(e.EV_REL, []))
                        and e.BTN_LEFT in caps.get(e.EV_KEY, [])):
                    continue
                found += 1
                print(f"{path}: {device.name}")
                print(f"  bus={device.info.bustype:04x} "
                      f"vendor={device.info.vendor:04x} product={device.info.product:04x}")
                print(f"  physical path: {device.phys or 'unavailable'}")
                print(f"  unique identifier: {device.uniq or 'unavailable'}")
                axes = [e.REL.get(code, str(code)) for code in caps[e.EV_REL]]
                print(f"  relative axes: {', '.join(axes)}")
                for directory in ("by-id", "by-path"):
                    for link in sorted((Path("/dev/input") / directory).glob("*")):
                        if link.resolve() == path:
                            print(f"  device link: {link}")
        except OSError as error:
            print(f"Cannot inspect {path}: {error}", file=sys.stderr)
            inaccessible += 1

    print(f"Found {found} accessible mouse candidate(s).")
    if inaccessible:
        print(f"{inaccessible} device(s) could not be inspected; the list may be incomplete. "
              "For permission errors, retry with sudo.", file=sys.stderr)
    return int(found == 0 or inaccessible > 0)


if __name__ == "__main__":
    sys.exit(main())
