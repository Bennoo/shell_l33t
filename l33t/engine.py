"""The typing engine: what you typed, how fast, and how accurately.

Pure logic -- no curses, no clock of its own. The caller passes `now` into
every input method, so a test can replay a whole session at exact timings.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class Keystroke:
    t: float          # seconds since the first keypress
    expected: str
    typed: str
    correct: bool
    latency: float    # seconds since the previous keypress


@dataclass
class Metrics:
    elapsed: float = 0.0
    raw_wpm: float = 0.0      # everything you typed
    net_wpm: float = 0.0      # only what stands correct
    accuracy: float = 1.0     # correct keystrokes / all keystrokes
    consistency: float = 1.0  # 1 - coefficient of variation of per-second wpm
    keystrokes: int = 0
    errors: int = 0
    correct_chars: int = 0
    typed_chars: int = 0


@dataclass
class KeyStat:
    attempts: int = 0
    errors: int = 0
    latency_total: float = 0.0
    latency_n: int = 0

    @property
    def error_rate(self) -> float:
        return self.errors / self.attempts if self.attempts else 0.0

    @property
    def mean_latency(self) -> float:
        return self.latency_total / self.latency_n if self.latency_n else 0.0


# A keystroke slower than this is a pause for thought, not a typing latency;
# folding it into the mean would slander the key.
LATENCY_CAP = 1.5


class TypingSession:
    """One run over a list of target lines.

    The clock starts on the first keypress, not on construction -- otherwise
    the time spent reading the first line counts against your WPM.
    """

    def __init__(self, lines: list[str], *, strict: bool = False,
                 allow_backspace: bool = True):
        self.lines = [ln for ln in lines if ln]
        self.strict = strict
        self.allow_backspace = allow_backspace

        self.line = 0
        self.pos = 0
        self.typed: list[list[str]] = [[] for _ in self.lines]
        self.ok: list[list[bool]] = [[] for _ in self.lines]

        self.keystrokes: list[Keystroke] = []
        self.started: float | None = None
        self.finished: float | None = None
        self.errors = 0
        self._last_t: float | None = None
        # Errors the player typed but has not yet backspaced away.
        self.pending_error = False

    # -- state -----------------------------------------------------------

    @property
    def done(self) -> bool:
        return self.finished is not None

    @property
    def target(self) -> str:
        return self.lines[self.line] if self.line < len(self.lines) else ""

    @property
    def total_chars(self) -> int:
        return sum(len(ln) for ln in self.lines)

    def progress(self) -> float:
        if not self.lines:
            return 1.0
        done = sum(len(t) for t in self.typed)
        return min(1.0, done / self.total_chars)

    # -- input -----------------------------------------------------------

    def press(self, ch: str, now: float) -> bool:
        """Feed one character. Returns True if it was a mistake."""
        if self.done or not self.lines:
            return False
        if self.started is None:
            self.started = now
            self._last_t = now

        expected = self.target[self.pos]
        correct = ch == expected
        self._log(now, expected, ch, correct)
        if not correct:
            self.errors += 1

        if self.strict and not correct:
            # LOCKDOWN: the cursor does not move until you get it right.
            return True

        self.typed[self.line].append(ch)
        self.ok[self.line].append(correct)
        self.pos += 1

        if self.pos >= len(self.target):
            self.line += 1
            self.pos = 0
            if self.line >= len(self.lines):
                self.finished = now
        return not correct

    def backspace(self, now: float) -> None:
        if self.done or not self.allow_backspace:
            return
        if self.pos == 0:
            if self.line == 0:
                return
            self.line -= 1
            self.pos = len(self.typed[self.line])
        if self.pos > 0:
            self.pos -= 1
            self.typed[self.line].pop()
            self.ok[self.line].pop()

    def _log(self, now: float, expected: str, typed: str, correct: bool) -> None:
        latency = now - (self._last_t if self._last_t is not None else now)
        self._last_t = now
        self.keystrokes.append(
            Keystroke(now - self.started, expected, typed, correct, latency))

    # -- measurement ------------------------------------------------------

    def metrics(self, now: float | None = None) -> Metrics:
        if self.started is None:
            return Metrics()
        end = self.finished if self.finished is not None else (now or self.started)
        elapsed = max(end - self.started, 1e-6)
        minutes = elapsed / 60.0

        typed_chars = sum(len(t) for t in self.typed)
        correct_chars = sum(1 for flags in self.ok for f in flags if f)
        total_ks = len(self.keystrokes)
        correct_ks = sum(1 for k in self.keystrokes if k.correct)

        return Metrics(
            elapsed=elapsed,
            # A "word" is 5 characters -- the standard WPM convention.
            raw_wpm=(typed_chars / 5.0) / minutes,
            net_wpm=(correct_chars / 5.0) / minutes,
            accuracy=correct_ks / total_ks if total_ks else 1.0,
            consistency=self.consistency(),
            keystrokes=total_ks,
            errors=self.errors,
            correct_chars=correct_chars,
            typed_chars=typed_chars,
        )

    def consistency(self) -> float:
        """How even your pace was: 1.0 is metronomic, 0.0 is wildly erratic.

        Per-second WPM buckets, scored by coefficient of variation -- the same
        shape of measure typing sites use.
        """
        if len(self.keystrokes) < 10:
            return 1.0
        buckets: dict[int, int] = {}
        for k in self.keystrokes:
            buckets[int(k.t)] = buckets.get(int(k.t), 0) + 1
        if len(buckets) < 2:
            return 1.0
        span = max(buckets) + 1
        samples = [buckets.get(i, 0) * 60.0 / 5.0 for i in range(span)]
        mean = statistics.fmean(samples)
        if mean <= 0:
            return 0.0
        cv = statistics.pstdev(samples) / mean
        return max(0.0, min(1.0, 1.0 - cv))

    def key_stats(self) -> dict[str, KeyStat]:
        """Per-character attempts, errors and mean latency.

        Keyed by the character you were *supposed* to hit, which is what makes
        it useful for building drills.
        """
        out: dict[str, KeyStat] = {}
        for k in self.keystrokes:
            stat = out.setdefault(k.expected, KeyStat())
            stat.attempts += 1
            if not k.correct:
                stat.errors += 1
            if 0 < k.latency <= LATENCY_CAP:
                stat.latency_total += k.latency
                stat.latency_n += 1
        return out

    def line_results(self) -> list[tuple[int, int]]:
        """(typed, correct) per target line -- lets the caller attribute a
        line's accuracy to whatever it was teaching."""
        return [(len(t), sum(1 for f in flags if f))
                for t, flags in zip(self.typed, self.ok)]

    def worst_keys(self, limit: int = 8, min_attempts: int = 3) -> list[str]:
        """Keys you actually got wrong this run, worst first.

        Only keys with real mistakes: reporting a key you hit perfectly as a
        "weakness" is noise, and a clean run should say so by returning [].
        """
        stats = self.key_stats()
        ranked = [(c, s) for c, s in stats.items()
                  if s.attempts >= min_attempts and s.errors]
        ranked.sort(key=lambda cs: (-cs[1].error_rate, -cs[1].mean_latency))
        return [c for c, _ in ranked[:limit]]
