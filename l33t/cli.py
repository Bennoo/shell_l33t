"""Entry point: locale, curses bootstrap, top-level menu loop."""

from __future__ import annotations

import argparse
import curses
import locale
import os
import random
import sys

from .modes import DIFFICULTIES
from .screens import (
    boot, briefing, codex, drill, path_screen, practice, stats_screen,
    title, watch_screen,
)
from .stats import Profile
from .ui import Glyphs, Screen, ensure_size, init_colors


def unicode_supported() -> bool:
    enc = (locale.getpreferredencoding(False) or "").lower()
    return "utf" in enc


def run(stdscr, seed: int | None, skip_boot: bool, difficulty: str) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    init_colors()
    stdscr.nodelay(True)

    screen = Screen(stdscr, Glyphs(unicode_supported()))
    if not ensure_size(screen):
        return
    rng = random.Random(seed)
    if not skip_boot:
        boot(screen, rng)

    while True:
        profile = Profile.load()
        choice = title(screen, profile, rng)
        if choice == "quit":
            return
        if not ensure_size(screen):
            return
        if choice == "path":
            path_screen(screen, profile, rng, difficulty)
        elif choice == "practice":
            practice(screen, profile, rng)
        elif choice == "codex":
            codex(screen, profile)
        elif choice == "watch":
            watch_screen(screen, rng)
        elif choice == "drill":
            drill(screen, profile, rng)
        elif choice == "stats":
            stats_screen(screen, profile)
        elif choice == "briefing":
            briefing(screen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="l33t", description="Learn the shell by typing it.")
    parser.add_argument("--seed", type=int, default=None,
                        help="fixed seed, for reproducible text")
    parser.add_argument("--no-boot", action="store_true",
                        help="skip the boot sequence")
    parser.add_argument("--difficulty", choices=sorted(DIFFICULTIES),
                        default="normal",
                        help="challenge time budget (default: normal)")
    args = parser.parse_args(argv)

    locale.setlocale(locale.LC_ALL, "")
    # Default is 1000ms, which makes ESC-to-abort feel broken. Kept under the
    # input poll interval so a real ESC resolves within a single frame.
    os.environ.setdefault("ESCDELAY", "10")

    if not sys.stdout.isatty():
        print("l33t needs a real terminal.", file=sys.stderr)
        return 1
    try:
        curses.wrapper(run, args.seed, args.no_boot, args.difficulty)
    except KeyboardInterrupt:
        pass
    print("Connection terminated. Stay l33t.")
    return 0
