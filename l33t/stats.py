"""Your typing profile, accumulated across sessions.

Per-key accuracy and latency are the whole point: they're what DRILL mode
uses to build practice that targets the keys you actually fumble, and what
the stats screen shows you.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .engine import KeyStat, Metrics
from .modes import DIFFICULTIES

HISTORY_LIMIT = 200
# Below this many attempts, an error rate is noise rather than a weakness.
MIN_ATTEMPTS = 12
DEFAULT_DIFFICULTY = "normal"


def profile_path() -> Path:
    root = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(root) / "l33t" / "profile.json"


@dataclass
class Run:
    when: str
    mode: str
    wpm: float
    accuracy: float
    consistency: float
    seconds: float

    @classmethod
    def from_dict(cls, d: dict) -> "Run | None":
        try:
            return cls(str(d["when"]), str(d["mode"]), float(d["wpm"]),
                       float(d["accuracy"]), float(d.get("consistency", 0.0)),
                       float(d.get("seconds", 0.0)))
        except (KeyError, TypeError, ValueError):
            return None


@dataclass
class LessonState:
    cleared: bool = False
    attempts: int = 0
    best_wpm: float = 0.0
    best_accuracy: float = 0.0


class Profile:
    def __init__(self, keys: dict[str, KeyStat] | None = None,
                 runs: list[Run] | None = None,
                 tools: dict[str, KeyStat] | None = None,
                 lessons: dict[str, dict[str, LessonState]] | None = None,
                 difficulty: str = DEFAULT_DIFFICULTY):
        self.keys: dict[str, KeyStat] = keys or {}
        self.runs: list[Run] = runs or []
        # Per-tool accuracy: attempts/errors counted in characters typed.
        self.tools: dict[str, KeyStat] = tools or {}
        # lesson key -> difficulty -> state. Kept separate per difficulty
        # because the time budget (and so the wpm needed to clear) scales
        # with DIFFICULTIES, which makes an easy-mode best incomparable to
        # a hard-mode one.
        self.lessons: dict[str, dict[str, LessonState]] = lessons or {}
        self.difficulty: str = difficulty if difficulty in DIFFICULTIES else DEFAULT_DIFFICULTY

    # -- persistence ------------------------------------------------------

    @classmethod
    def load(cls) -> "Profile":
        try:
            raw = json.loads(profile_path().read_text())
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()

        keys = {}
        for ch, d in (raw.get("keys") or {}).items():
            if not isinstance(d, dict) or len(ch) != 1:
                continue
            try:
                keys[ch] = KeyStat(int(d.get("attempts", 0)),
                                   int(d.get("errors", 0)),
                                   float(d.get("latency_total", 0.0)),
                                   int(d.get("latency_n", 0)))
            except (TypeError, ValueError):
                continue

        runs = [r for r in (Run.from_dict(d) for d in (raw.get("runs") or [])
                            if isinstance(d, dict)) if r]

        tools = {}
        for name, d in (raw.get("tools") or {}).items():
            if not isinstance(d, dict) or not isinstance(name, str):
                continue
            try:
                tools[name] = KeyStat(int(d.get("attempts", 0)),
                                      int(d.get("errors", 0)))
            except (TypeError, ValueError):
                continue

        lessons: dict[str, dict[str, LessonState]] = {}
        for name, d in (raw.get("lessons") or {}).items():
            if not isinstance(d, dict) or not isinstance(name, str):
                continue
            # Pre-difficulty profiles stored one flat state per lesson;
            # treat that as the "normal" bucket instead of losing it.
            if "cleared" in d or "attempts" in d:
                d = {DEFAULT_DIFFICULTY: d}
            by_difficulty: dict[str, LessonState] = {}
            for diff, sd in d.items():
                if diff not in DIFFICULTIES or not isinstance(sd, dict):
                    continue
                try:
                    by_difficulty[diff] = LessonState(
                        bool(sd.get("cleared", False)), int(sd.get("attempts", 0)),
                        float(sd.get("best_wpm", 0.0)),
                        float(sd.get("best_accuracy", 0.0)))
                except (TypeError, ValueError):
                    continue
            if by_difficulty:
                lessons[name] = by_difficulty

        difficulty = raw.get("difficulty")
        if difficulty not in DIFFICULTIES:
            difficulty = DEFAULT_DIFFICULTY

        return cls(keys, runs, tools, lessons, difficulty)

    def save(self) -> None:
        data = {
            "keys": {ch: {"attempts": s.attempts, "errors": s.errors,
                          "latency_total": round(s.latency_total, 4),
                          "latency_n": s.latency_n}
                     for ch, s in self.keys.items()},
            "runs": [{"when": r.when, "mode": r.mode, "wpm": round(r.wpm, 2),
                      "accuracy": round(r.accuracy, 4),
                      "consistency": round(r.consistency, 4),
                      "seconds": round(r.seconds, 1)}
                     for r in self.runs[-HISTORY_LIMIT:]],
            "tools": {n: {"attempts": s.attempts, "errors": s.errors}
                      for n, s in self.tools.items()},
            "lessons": {n: {diff: {"cleared": s.cleared, "attempts": s.attempts,
                                   "best_wpm": round(s.best_wpm, 2),
                                   "best_accuracy": round(s.best_accuracy, 4)}
                            for diff, s in by_difficulty.items()}
                        for n, by_difficulty in self.lessons.items()},
            "difficulty": self.difficulty,
        }
        try:
            path = profile_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1))
            tmp.replace(path)      # never leave a half-written profile behind
        except OSError:
            pass

    # -- updates ----------------------------------------------------------

    def record(self, mode: str, metrics: Metrics,
               key_stats: dict[str, KeyStat]) -> None:
        for ch, s in key_stats.items():
            acc = self.keys.setdefault(ch, KeyStat())
            acc.attempts += s.attempts
            acc.errors += s.errors
            acc.latency_total += s.latency_total
            acc.latency_n += s.latency_n
        self.runs.append(Run(
            when=time.strftime("%Y-%m-%d %H:%M"), mode=mode,
            wpm=metrics.net_wpm, accuracy=metrics.accuracy,
            consistency=metrics.consistency, seconds=metrics.elapsed))
        del self.runs[:-HISTORY_LIMIT]

    def record_tools(self, per_tool: dict[str, tuple[int, int]]) -> None:
        """per_tool: {tool: (characters typed, characters wrong)}"""
        for name, (typed, wrong) in per_tool.items():
            stat = self.tools.setdefault(name, KeyStat())
            stat.attempts += typed
            stat.errors += wrong

    def record_lesson(self, key: str, difficulty: str, wpm: float,
                      accuracy: float, cleared: bool) -> None:
        state = self.lessons.setdefault(key, {}).setdefault(
            difficulty, LessonState())
        state.attempts += 1
        state.best_wpm = max(state.best_wpm, wpm)
        state.best_accuracy = max(state.best_accuracy, accuracy)
        # Clearing sticks: a bad run later doesn't un-teach the lesson.
        state.cleared = state.cleared or cleared

    def lesson(self, key: str, difficulty: str) -> LessonState:
        return self.lessons.get(key, {}).get(difficulty, LessonState())

    def cleared_count(self, difficulty: str | None = None) -> int:
        """How many lessons are cleared.

        With a difficulty given, only clears at that difficulty count --
        matching what the path screen shows while browsing it. With none,
        a lesson counts if it's been cleared at any difficulty, for the
        difficulty-agnostic overview on the title screen.
        """
        if difficulty is None:
            return sum(1 for by_difficulty in self.lessons.values()
                       if any(s.cleared for s in by_difficulty.values()))
        return sum(1 for by_difficulty in self.lessons.values()
                   if by_difficulty.get(difficulty, LessonState()).cleared)

    # -- queries ----------------------------------------------------------

    # A key this much slower than your average is worth drilling even if you
    # never actually miss it.
    SLOW_FACTOR = 1.25

    def mean_latency(self) -> float:
        total = sum(s.latency_total for s in self.keys.values())
        n = sum(s.latency_n for s in self.keys.values())
        return total / n if n else 0.0

    def weak_keys(self, limit: int = 10) -> list[str]:
        """The keys actually worth drilling.

        A key qualifies by missing the target (any error rate) or by being
        markedly slower than your average. Keys you've barely touched are
        excluded -- one miss out of two isn't a weakness, it's a coin flip.
        And a key you never miss at normal speed isn't practice, it's filler.
        """
        baseline = self.mean_latency()
        ranked = []
        for ch, s in self.keys.items():
            if s.attempts < MIN_ATTEMPTS or ch.isspace():
                continue
            slow = baseline > 0 and s.mean_latency > baseline * self.SLOW_FACTOR
            if s.errors or slow:
                ranked.append((ch, s))
        ranked.sort(key=lambda cs: (-cs[1].error_rate, -cs[1].mean_latency))
        return [c for c, _ in ranked[:limit]]

    def best_wpm(self, mode: str | None = None) -> float:
        runs = [r for r in self.runs if mode is None or r.mode == mode]
        return max((r.wpm for r in runs), default=0.0)

    def recent(self, n: int = 10, mode: str | None = None) -> list[Run]:
        runs = [r for r in self.runs if mode is None or r.mode == mode]
        return runs[-n:]

    def average_wpm(self, n: int = 10) -> float:
        runs = self.recent(n)
        return sum(r.wpm for r in runs) / len(runs) if runs else 0.0
