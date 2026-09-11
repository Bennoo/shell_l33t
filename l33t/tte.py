"""Optional bridge to terminaltexteffects.

TTE owns stdout and runs its own frame loop, so it can't be composited into a
curses window or interrupted by a keypress -- which rules it out for the
interactive teaching screens, where the effect has to share the layout with a
parts list and be skippable.

It IS a good fit for a one-shot, non-interactive flourish: suspend curses, let
TTE have the terminal, take it back. That's what this module does, with the
native effects as the fallback when the package isn't installed.

    uv sync --extra effects
"""

from __future__ import annotations

import curses
import random

# Effects that suit a single line of shell text. TTE ships 37; these are the
# ones that read as "decrypting" rather than as confetti.
LINE_EFFECTS = (
    "decrypt", "binarypath", "matrix", "errorcorrect", "scattered",
    "slide", "wipe", "expand", "middleout", "sweep", "laseretch",
    "unstable", "blackhole", "beams", "vhstape", "crumble", "spray",
)


def available() -> bool:
    try:
        import terminaltexteffects  # noqa: F401
    except Exception:
        return False
    return True


def _load(name: str):
    """Import one effect class by its module name."""
    module = __import__(
        f"terminaltexteffects.effects.effect_{name}", fromlist=["*"])
    for attr in dir(module):
        obj = getattr(module, attr)
        if isinstance(obj, type) and attr.lower() == name.replace("_", ""):
            return obj
    # Fall back to whichever public class the module defines.
    for attr in dir(module):
        obj = getattr(module, attr)
        if isinstance(obj, type) and not attr.startswith("_") \
                and obj.__module__ == module.__name__:
            return obj
    raise ImportError(name)


def play(stdscr, text: str, effect: str | None = None,
         rng: random.Random | None = None) -> bool:
    """Hand the terminal to TTE for one effect, then take it back.

    Returns False if TTE isn't installed or the effect failed, so the caller
    can fall back. Curses is always restored, including on failure.
    """
    if not available():
        return False
    rng = rng or random
    name = effect or rng.choice(LINE_EFFECTS)

    curses.def_prog_mode()
    curses.endwin()
    try:
        cls = _load(name)
        eff = cls(text)
        with eff.terminal_output() as terminal:
            for frame in eff:
                terminal.print(frame)
        return True
    except Exception:
        # A decorative effect must never take the game down.
        return False
    finally:
        curses.reset_prog_mode()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.clear()
        stdscr.refresh()
