#!/usr/bin/env python3
"""Observe all or selected mice without grabbing, remapping, or injecting input."""

import argparse
from contextlib import ExitStack
from pathlib import Path
import selectors
import signal
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", action="append", type=Path, help="device path; repeat for multiple mice")
    parser.add_argument("--raw", action="store_true", help="print individual records instead of whole reports")
    args = parser.parse_args()
    try:
        from evdev import InputDevice, ecodes as e
    except ImportError:
        print("Install Python evdev first; see README.md.", file=sys.stderr)
        return 1

    def describe(event):
        names = e.bytype.get(event.type, {}).get(event.code, str(event.code))
        if isinstance(names, (list, tuple)):
            names = "/".join(names)
        return f"{names}={event.value:+d}"

    with ExitStack() as cleanup:
        selector = cleanup.enter_context(selectors.DefaultSelector())
        paths = args.device or sorted(p for p in Path("/dev/input").iterdir()
                                      if p.name.startswith("event"))
        seen = set()
        for path in paths:
            try:
                path = path.resolve(strict=True)
                if path in seen:
                    continue
                seen.add(path)
                device = InputDevice(str(path))
                cleanup.callback(device.close)
                caps = device.capabilities()
            except OSError as error:
                if args.device:
                    raise
                print(f"Cannot inspect {path}: {error}. The device list may be incomplete; "
                      "retry with sudo for permission errors.", file=sys.stderr)
                continue
            if not ({e.REL_X, e.REL_Y} <= set(caps.get(e.EV_REL, []))
                    and e.BTN_LEFT in caps.get(e.EV_KEY, [])):
                device.close()
                if args.device:
                    raise ValueError(f"{path} is not a relative-pointer mouse")
                continue
            # Each reader retains its own incomplete report across read() calls.
            selector.register(device, selectors.EVENT_READ,
                              {"fields": [], "dropping": False})
            print(f"Watching {path}: {device.name}", file=sys.stderr)

        if not selector.get_map():
            raise ValueError("No accessible relative-pointer mice found. Run detect_mice.py first.")
        print("Observing only; Ctrl+C stops. Restart after connecting a mouse. "
              "Printing is not a throughput benchmark.", file=sys.stderr)

        while True:
            for key, _ in selector.select():
                device, report = key.fileobj, key.data
                try:
                    events = device.read()
                    for event in events:
                        stamp = f"{event.sec}.{event.usec:06d} {Path(device.path).name}"
                        if event.type == e.EV_SYN and event.code == e.SYN_DROPPED:
                            print(f"{device.path}: SYN_DROPPED: input was lost.", file=sys.stderr)
                            report["fields"].clear()
                            report["dropping"] = True
                        if args.raw:
                            print(f"{stamp} type={event.type} code={event.code} "
                                  f"value={event.value} ({describe(event)})", flush=True)
                        elif event.type == e.EV_SYN and event.code == e.SYN_REPORT:
                            if report["fields"] and not report["dropping"]:
                                print(f"{stamp} {' '.join(report['fields'])}", flush=True)
                            report["fields"].clear()
                            report["dropping"] = False
                        elif event.type != e.EV_SYN and not report["dropping"]:
                            report["fields"].append(describe(event))
                except BlockingIOError:
                    continue
                except OSError as error:
                    raise OSError(f"{device.path}: stopped reading: {error}") from error


if __name__ == "__main__":
    # Closing a pipe (e.g. piping to head) exits without a Python traceback.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as error:
        print(f"print_mice_events: {error}", file=sys.stderr)
        sys.exit(1)
