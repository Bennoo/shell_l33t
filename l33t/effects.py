"""Text effects for the teaching screens.

Implemented natively against the curses frame loop rather than pulled in from
a library: a terminal-effects package owns stdout and runs its own frame loop,
which can't be composited into a curses window or interrupted by a keypress.
These are pure timing functions -- `state(i, elapsed)` -- so the renderer stays
dumb, every effect is skippable, and the timing is testable without a screen.
"""

from __future__ import annotations

from dataclasses import dataclass

# Deliberately shell-flavoured: the noise should look like the thing it's
# resolving into.
SCRAMBLE = "!@#$%^&*()[]{}<>/\\|;:'\",.?~`0123456789ABCDEF"

SCRAMBLING = "scrambling"
FLASH = "flash"
SETTLED = "settled"


def _noise(i: int, tick: int, seed: int) -> str:
    """Deterministic pseudo-random glyph. Deterministic so a frame redrawn at
    the same elapsed time looks identical, and so tests can assert on it."""
    h = (i * 2654435761 + tick * 40503 + seed * 97) & 0xFFFFFFFF
    return SCRAMBLE[h % len(SCRAMBLE)]


@dataclass
class Decrypt:
    """Characters churn through noise, then resolve left to right.

    Whitespace is never scrambled -- keeping the word shapes intact makes the
    command readable as it resolves instead of a wall of punctuation.
    """

    text: str
    stagger: float = 0.022     # delay added per character
    churn: float = 0.40        # how long a character scrambles before settling
    flash: float = 0.16        # bright moment as it lands
    flicker: float = 0.045     # how fast the noise changes
    seed: int = 0

    def settle_at(self, i: int) -> float:
        return self.churn + i * self.stagger

    @property
    def duration(self) -> float:
        if not self.text:
            return 0.0
        return self.settle_at(len(self.text) - 1) + self.flash

    def done(self, elapsed: float) -> bool:
        return elapsed >= self.duration

    def state(self, i: int, elapsed: float) -> tuple[str, str]:
        """(character to draw, tier) for position `i` at `elapsed`."""
        ch = self.text[i]
        if ch.isspace():
            return ch, SETTLED
        settle = self.settle_at(i)
        if elapsed >= settle + self.flash:
            return ch, SETTLED
        if elapsed >= settle:
            return ch, FLASH
        return _noise(i, int(elapsed / self.flicker), self.seed), SCRAMBLING

    def progress(self, elapsed: float) -> float:
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, elapsed / self.duration))


@dataclass
class Typewriter:
    """Reveal text left to right at a fixed rate."""

    text: str
    cps: float = 220.0
    delay: float = 0.0

    @property
    def duration(self) -> float:
        return self.delay + len(self.text) / self.cps

    def done(self, elapsed: float) -> bool:
        return elapsed >= self.duration

    def visible(self, elapsed: float) -> str:
        # Clamp at the end: len/cps * cps can land a hair under len in
        # floating point, which would drop the final character.
        if elapsed >= self.duration:
            return self.text
        if elapsed <= self.delay:
            return ""
        return self.text[:int((elapsed - self.delay) * self.cps)]

    def caret(self, elapsed: float) -> bool:
        """Whether to show a trailing cursor block."""
        return not self.done(elapsed) and elapsed > self.delay
