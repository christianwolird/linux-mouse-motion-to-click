"""Check click timing and histogram boundaries without opening input devices."""

import contextlib
import io
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from evdev import InputEvent, ecodes as e

from diagonstics import variance_probe as probe


def event(kind, code, value=0):
    return InputEvent(0, 0, kind, code, value)


def click(stamp):
    return [(stamp, event(e.EV_KEY, e.BTN_LEFT, 1)),
            (stamp, event(e.EV_SYN, e.SYN_REPORT)),
            (stamp, event(e.EV_KEY, e.BTN_LEFT, 0)),
            (stamp, event(e.EV_SYN, e.SYN_REPORT))]


class FakeSelector:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.now = 0
        self.timeouts = []
        self.key = SimpleNamespace(fileobj=self, data=probe.ClickObserver())

    def select(self, timeout):
        self.timeouts.append(timeout)
        self.batch = next(self.batches, None)
        if self.batch is None:
            assert timeout is not None, 'Unexpected indefinite wait'
            self.now += round(timeout * 1_000_000_000)
            return []
        return [(self.key, selectors_event_read)]

    def read(self):
        for stamp, record in self.batch:
            self.now = stamp
            yield record


selectors_event_read = 1


class VarianceProbeTests(unittest.TestCase):
    def collect(self, batches):
        selector = FakeSelector(batches)
        with patch.object(probe.time, 'monotonic_ns', side_effect=lambda: selector.now):
            timestamps = probe.collect_trial(selector, e)
        return timestamps, selector

    def test_250_hz_trial_starts_on_first_click_and_excludes_deadline(self):
        start = 20_000_000_000
        batch = [record for i in range(2501) for record in click(start + i * 4_000_000)]
        timestamps, selector = self.collect([batch])
        self.assertEqual(timestamps, [start + i * 4_000_000 for i in range(2500)])
        self.assertIsNone(selector.timeouts[0])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            probe.print_results(timestamps)
        self.assertIn('Total clicks: 2500', output.getvalue())
        self.assertIn('Intervals:    2499', output.getvalue())
        self.assertIn('Average delay: 4.000000 ms', output.getvalue())
        self.assertRegex(output.getvalue(), r'4\.00\s+2499\s+100\.00%')

    def test_trial_finishes_after_one_click_even_if_input_stops(self):
        start = 20_000_000_000
        timestamps, selector = self.collect([click(start)])
        self.assertEqual(timestamps, [start])
        self.assertEqual(selector.timeouts, [None, 10.0])
        self.assertEqual(selector.now, start + probe.DURATION_NS)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            probe.print_results(timestamps)
        self.assertIn('At least two clicks', output.getvalue())

    def test_release_timestamp_survives_split_report_and_ignores_noise(self):
        observer = probe.ClickObserver()
        for record in [event(e.EV_KEY, e.BTN_LEFT, 0),
                       event(e.EV_KEY, e.BTN_RIGHT, 1),
                       event(e.EV_REL, e.REL_X, 3),
                       event(e.EV_SYN, e.SYN_REPORT)]:
            self.assertEqual(observer.feed(record, 1, e), [])
        for value in [1, 2, 1]:
            self.assertEqual(observer.feed(event(e.EV_KEY, e.BTN_LEFT, value), 10, e), [])
        self.assertEqual(observer.feed(event(e.EV_KEY, e.BTN_LEFT, 0), 123456789, e), [])
        self.assertEqual(observer.feed(event(e.EV_SYN, e.SYN_REPORT), 123500000, e), [123456789])
        self.assertEqual(observer.feed(event(e.EV_SYN, e.SYN_REPORT), 123600000, e), [])

    def test_lost_input_invalidates_trial(self):
        with self.assertRaisesRegex(RuntimeError, 'SYN_DROPPED'):
            probe.ClickObserver().feed(event(e.EV_SYN, e.SYN_DROPPED), 0, e)

    def test_rounding_boundaries_and_tails_use_integer_precision(self):
        intervals = [0, 3_854_999, 3_855_000, 3_865_000, 3_985_000,
                     3_994_999, 3_995_000, 4_144_999, 4_145_000, 100_000_000]
        bins = probe.interval_histogram(intervals)
        self.assertEqual(list(bins), [i * 10_000 for i in range(385, 416)])
        self.assertEqual({key: count for key, count in bins.items() if count},
                         {3_850_000: 2, 3_860_000: 1, 3_870_000: 1,
                          3_990_000: 2, 4_000_000: 1, 4_140_000: 1, 4_150_000: 2})


if __name__ == '__main__':
    unittest.main()
