# Click interval variance at 250 Hz

## Why this matters for Cookie Clicker

This project was created for speedrunning Cookie Clicker. The target is the
older game's 4 ms click threshold, documented in the
[version and CPS findings](versions_and_cps_limit_findings.md#v10466-every-attempt-restarts-the-wait).
The game compares integer-millisecond clock readings: a difference of 0, 1, 2,
or 3 ms rejects the current click; 4 ms or more accepts it. Rejected attempts
also reset the previous-click timer.

Perfectly spaced 4 ms clicks give a theoretical ceiling of 250 accepted clicks
per second, assuming negligible handler time and preserved delivery spacing.
A 4 ms average alone is insufficient: variation can place individual attempts
below the threshold.

The source uses `new Date().getTime()` rather than explicitly rounding timestamps
to the nearest millisecond. It compares the current handler's clock reading with
one taken at the end of the previous handler. These are browser processing times,
so the probe's intervals cannot directly determine which game clicks succeed.

## Trial results

User-provided output from [`variance_probe.py`](../diagonstics/variance_probe.py),
testing the intended 4 ms spacing of a remapped 250 Hz mouse stream:

```text
10-second trial complete (timed from the first completed click).
Total clicks: 2500
Intervals:    2499
Average delay: 4.000074 ms
Median delay:  3.999684 ms
Minimum delay: 3.223455 ms
Maximum delay: 4.757232 ms
Std. deviation (population): 0.027488 ms

Intervals rounded to 0.01 ms:
  Delay (ms)     Count   Percent
      <=3.85         1     0.04%
        3.86         0     0.00%
        3.87         2     0.08%
        3.88         5     0.20%
        3.89         1     0.04%
        3.90         1     0.04%
        3.91         2     0.08%
        3.92         3     0.12%
        3.93         2     0.08%
        3.94         3     0.12%
        3.95         5     0.20%
        3.96        19     0.76%
        3.97        32     1.28%
        3.98        94     3.76%
        3.99       412    16.49%
        4.00      1353    54.14%
        4.01       366    14.65%
        4.02       116     4.64%
        4.03        34     1.36%
        4.04        17     0.68%
        4.05        10     0.40%
        4.06         3     0.12%
        4.07         3     0.12%
        4.08         0     0.00%
        4.09         1     0.04%
        4.10         4     0.16%
        4.11         3     0.12%
        4.12         0     0.00%
        4.13         5     0.20%
        4.14         0     0.00%
      >=4.15         2     0.08%
```

## Interpretation

The mean is very close to the intended 4 ms interval. The 3.99, 4.00, and 4.01 ms
buckets contain 2,131 of 2,499 intervals (85.27%). The standard deviation is
about 27.5 microseconds, with extremes of 3.223455 and 4.757232 ms.

The probe timestamps completed left-click releases as Python observes them,
before libinput and browser filtering. These measurements include Python
scheduling and input read batching. They show variation at this observation
point, not necessarily variation produced by the mouse itself.

An interval below 4 ms does not automatically imply rejection: the game compares
two integer-millisecond timestamps, not a rounded interval. Acceptance depends
on where those readings fall relative to millisecond boundaries, as well as
browser delivery and handler time. This histogram does not retain that timing
information, and no in-game accepted-click count was supplied for this trial.
