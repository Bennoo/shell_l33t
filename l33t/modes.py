"""The learning path: lessons in teaching order, with typing pressure on top."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .shell import LESSONS, Command, Lesson, lesson_commands

LINE_WIDTH = 58
LINES_PER_LESSON = 6

# Accuracy below this means you typed it but didn't learn it.
CLEAR_ACCURACY = 0.90


@dataclass(frozen=True)
class Modifier:
    key: str
    name: str
    tag: str      # short form, for list views
    blurb: str


MODIFIERS = [
    Modifier("lockdown", "LOCKDOWN", "LOCK", "errors must be corrected to advance"),
    Modifier("blind", "BLIND", "BLIND", "no correctness feedback while you type"),
    Modifier("nobackspace", "NO BACKSPACE", "NOBS", "mistakes are permanent"),
    Modifier("surge", "SURGE", "SURGE", "the trace accelerates as it closes"),
    Modifier("purge", "PURGE", "PURGE", "every error costs double"),
]

# Which steps of the path add pressure. The early ones stay clean so you can
# read the commands and actually learn them.
MODIFIER_STEPS = {4: "purge", 6: "nobackspace", 8: "surge", 10: "lockdown"}

DIFFICULTIES = {"easy": 1.35, "normal": 1.0, "hard": 0.82}


@dataclass(frozen=True)
class Step:
    index: int              # 1-based position on the path
    lesson: Lesson
    target_wpm: float
    modifier: Modifier | None

    @property
    def key(self) -> str:
        return self.lesson.key

    @property
    def name(self) -> str:
        return self.lesson.name

    def has(self, key: str) -> bool:
        return self.modifier is not None and self.modifier.key == key


_BY_KEY = {m.key: m for m in MODIFIERS}


def build_path() -> list[Step]:
    """The path is fixed, not shuffled -- it's a syllabus, and later lessons
    lean on earlier ones."""
    steps = []
    for i, lesson in enumerate(LESSONS, start=1):
        mod = _BY_KEY.get(MODIFIER_STEPS.get(i, ""))
        # Shell text is punctuation-heavy; nobody types it at prose speed.
        steps.append(Step(index=i, lesson=lesson,
                          target_wpm=17.0 + i * 0.8, modifier=mod))
    return steps


def step_payload(step: Step, rng: random.Random, difficulty: str,
                 commands: list[Command] | None = None
                 ) -> tuple[list[Command], float]:
    """The commands for one step, and the trace budget they're worth.

    Pass `commands` to time exactly the set already taught in this lesson --
    the challenge must test what you just learned, not fresh material.
    """
    if commands is None:
        commands = lesson_commands(step.lesson, LINES_PER_LESSON, rng)
    chars = sum(len(c.text) for c in commands)
    seconds = chars / (step.target_wpm * 5.0) * 60.0
    return commands, seconds * DIFFICULTIES.get(difficulty, 1.0)


# --------------------------------------------------------------------------
# Where to start a lesson
# --------------------------------------------------------------------------

# In teaching order. A start point runs its own phase and everything after it.
PHASES = ("learn", "recall", "challenge")

START_POINTS = {
    "full": "learn",
    "recall": "recall",
    "challenge": "challenge",
}


def phases_from(start: str) -> tuple[str, ...]:
    """Which phases run, given where the player chose to start.

    Skipping ahead never skips the challenge: that's the graded part, and the
    only thing that can clear a lesson.
    """
    first = START_POINTS.get(start, "learn")
    return PHASES[PHASES.index(first):]
