#!/usr/bin/env python3
"""Show combined rolling one-second CPS for all mice, before desktop filtering.

This standalone observer never grabs a device or injects input. A click means
an observed BTN_LEFT press followed by release, committed at SYN_REPORT.
"""

import argparse
from collections import deque
from contextlib import ExitStack
from pathlib import Path
import selectors
import signal
import sys
import time


WINDOW_SECONDS = 1.0
REFRESH_SECONDS = 0.1


class ClickCounter:
    def __init__(self):
        self.pressed = False
        self.pending = []
        self.clicks = deque()
        self.total = 0

    def feed(self, event, now, e):
        if event.type == e.EV_SYN:
            if event.code == e.SYN_DROPPED:
                raise RuntimeError("SYN_DROPPED: the monitor lost input; CPS is unreliable. Stopped.")
            if event.code == e.SYN_REPORT:
                self.clicks.extend(self.pending)
                self.total += len(self.pending)
                self.pending.clear()
        elif event.type == e.EV_KEY and event.code == e.BTN_LEFT:
            if event.value == 1:
                self.pressed = True
            elif event.value == 0 and self.pressed:
                self.pending.append(now)
                self.pressed = False

    def cps(self, now):
        while self.clicks and self.clicks[0] <= now - WINDOW_SECONDS:
            self.clicks.popleft()
        return len(self.clicks) / WINDOW_SECONDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="test counting without opening devices")
    args = parser.parse_args()
    try:
        from evdev import InputDevice, ecodes as e
    except ImportError:
        raise ValueError("Install Python evdev first; see README.md.") from None
    if args.self_test:
        return self_test(e)

    paths = sorted(path for path in Path("/dev/input").iterdir() if path.name.startswith("event"))
    with ExitStack() as devices, selectors.DefaultSelector() as selector:
        counters = []
        for path in paths:
            try:
                device = InputDevice(str(path))
                devices.callback(device.close)
                caps = device.capabilities()
            except OSError as error:
                print(f"Skipping {path}: {error}", file=sys.stderr)
                continue
            if not (e.BTN_LEFT in caps.get(e.EV_KEY, []) and
                    {e.REL_X, e.REL_Y} <= set(caps.get(e.EV_REL, []))):
                device.close()
                continue
            # Each mouse needs its own press/release and report state.
            counter = ClickCounter()
            counters.append(counter)
            selector.register(device, selectors.EVENT_READ, counter)
            print(f"Watching {device.path}: {device.name}")
        if not counters:
            raise ValueError("No accessible mice found. Start the clicker first and run this monitor with sudo.")
        print("Combined CPS for the devices above. Restart after adding mice or restarting the clicker.")
        print("Before libinput/browser filtering; completed left clicks received in the last 1.0 s.")
        print("No grab or input injection. Ctrl+C stops. First second fills the window.")
        next_refresh = time.monotonic()
        try:
            while True:
                for key, _ in selector.select(max(0.0, next_refresh - time.monotonic())):
                    try:
                        # One read per readiness check keeps rendering responsive
                        # even with continuous input. Evdev reads records in batches.
                        for event in key.fileobj.read():
                            key.data.feed(event, time.monotonic(), e)
                    except BlockingIOError:
                        pass
                now = time.monotonic()
                if now >= next_refresh:
                    cps = sum(counter.cps(now) for counter in counters)
                    total = sum(counter.total for counter in counters)
                    status = f"CPS: {cps:8.1f} | Total: {total}"
                    print("\r" + status.ljust(60) if sys.stdout.isatty() else status,
                          end="" if sys.stdout.isatty() else "\n", flush=True)
                    next_refresh = now + REFRESH_SECONDS
        finally:
            if sys.stdout.isatty():
                print()


def self_test(e):
    """In-memory events only: these tests neither open nor create input devices."""
    import unittest
    from evdev import InputEvent

    class Tests(unittest.TestCase):
        def setUp(self):
            self.counter = ClickCounter()

        def feed(self, kind, code, value, now):
            self.counter.feed(InputEvent(0, 0, kind, code, value), now, e)

        def click(self, now):
            self.feed(e.EV_KEY, e.BTN_LEFT, 1, now)
            self.feed(e.EV_SYN, e.SYN_REPORT, 0, now)
            self.feed(e.EV_KEY, e.BTN_LEFT, 0, now)
            self.feed(e.EV_SYN, e.SYN_REPORT, 0, now)

        def test_one_pair_counts_once_and_hold_does_not_repeat(self):
            self.feed(e.EV_KEY, e.BTN_LEFT, 1, 1.0)
            self.feed(e.EV_KEY, e.BTN_LEFT, 2, 1.1)
            self.feed(e.EV_KEY, e.BTN_LEFT, 1, 1.2)
            self.feed(e.EV_SYN, e.SYN_REPORT, 0, 1.2)
            self.assertEqual(self.counter.cps(1.2), 0.0)
            self.feed(e.EV_KEY, e.BTN_LEFT, 0, 1.3)
            self.assertEqual(self.counter.cps(1.3), 0.0)
            self.feed(e.EV_SYN, e.SYN_REPORT, 0, 1.3)
            self.assertEqual(self.counter.cps(1.3), 1.0)

        def test_rolling_window_expires_without_new_events(self):
            self.click(1.0)
            self.click(1.5)
            self.assertEqual(self.counter.cps(1.75), 2.0)
            self.assertEqual(self.counter.cps(2.0), 1.0)
            self.assertEqual(self.counter.cps(2.5), 0.0)
            self.assertEqual(self.counter.total, 2)

        def test_500_clicks_are_not_1000_button_edges(self):
            for i in range(500):
                self.click(1.0 + i / 1000)
            self.assertEqual(f"{self.counter.cps(1.5):.1f}", "500.0")

        def test_unmatched_release_other_buttons_and_motion_are_ignored(self):
            for kind, code, value in [(e.EV_KEY, e.BTN_LEFT, 0),
                                      (e.EV_KEY, e.BTN_RIGHT, 1),
                                      (e.EV_KEY, e.BTN_RIGHT, 0),
                                      (e.EV_REL, e.REL_X, 10),
                                      (e.EV_REL, e.REL_WHEEL, 1)]:
                self.feed(kind, code, value, 1.0)
            self.feed(e.EV_SYN, e.SYN_REPORT, 0, 1.0)
            self.assertEqual(self.counter.cps(1.0), 0.0)

        def test_lost_input_fails_instead_of_showing_a_plausible_wrong_rate(self):
            self.feed(e.EV_KEY, e.BTN_LEFT, 1, 1.0)
            with self.assertRaisesRegex(RuntimeError, "SYN_DROPPED"):
                self.feed(e.EV_SYN, e.SYN_DROPPED, 0, 1.0)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, RuntimeError) as error:
        print(f"show_cps: {error}", file=sys.stderr)
        sys.exit(1)
