"""Curses front-end for L33T.

Rendering rules that keep it smooth:
  * terminal size is read once per frame, never once per character;
  * the rain groups runs of same-coloured cells into a single addstr;
  * every screen is a non-blocking fixed-timestep loop -- no time.sleep(),
    so input and resize stay responsive during transitions.
"""

from __future__ import annotations

import curses
import random
import time
import unicodedata

MIN_H, MIN_W = 22, 72
FRAME = 1.0 / 60.0

# Colour pair ids
P_DIM, P_GREEN, P_HI, P_WHITE, P_RED, P_AMBER, P_CYAN, P_SEL, P_ALERT, P_GREY = range(1, 11)


def display_width(text: str) -> int:
    """Columns a string occupies, not how many codepoints it has.

    Japanese characters are double-width: あかり is 3 codepoints but 6 columns.
    Measuring with len() would let text overrun its panel and corrupt the
    line, so every clip and centring goes through here.
    """
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def clip_to_width(text: str, columns: int) -> str:
    """Longest prefix of `text` that fits in `columns`, never splitting a
    wide character across the boundary."""
    if columns <= 0:
        return ""
    out, used = [], 0
    for ch in text:
        w = 0 if unicodedata.combining(ch) else (
            2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1)
        if used + w > columns:
            break
        out.append(ch)
        used += w
    return "".join(out)


class Glyphs:
    """Unicode where the terminal supports it, ASCII where it doesn't."""

    def __init__(self, unicode_ok: bool):
        self.unicode = unicode_ok
        if unicode_ok:
            self.full, self.empty = "█", "░"
            self.hline, self.vline = "─", "│"
            self.pip, self.heart = "▮", "♥"
            self.arrow = "▸"
            self.note = "↳"
            self.hidden = "·"
        else:
            self.full, self.empty = "#", "-"
            self.hline, self.vline = "-", "|"
            self.pip, self.heart = "!", "*"
            self.arrow = ">"
            self.note = "->"
            self.hidden = "_"

    LOGO_UNICODE = [
        "██╗     ██████╗ ██████╗ ████████╗",
        "██║     ╚════██╗╚════██╗╚══██╔══╝",
        "██║      █████╔╝ █████╔╝   ██║",
        "██║      ╚═══██╗ ╚═══██╗   ██║",
        "███████╗██████╔╝██████╔╝   ██║",
        "╚══════╝╚═════╝ ╚═════╝    ╚═╝",
    ]
    LOGO_ASCII = [
        " _     ____  ____  _____",
        "| |   |___ \\|___ \\|_   _|",
        "| |     __) | __) | | |",
        "| |    / __/ / __/  | |",
        "| |___| |___| |___  | |",
        "|_____|_____|_____| |_|",
    ]

    @property
    def logo(self):
        art = self.LOGO_UNICODE if self.unicode else self.LOGO_ASCII
        width = max(len(line) for line in art)
        return [line.ljust(width) for line in art]


def init_colors() -> None:
    curses.start_color()
    bg = curses.COLOR_BLACK
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        pass

    if curses.COLORS >= 256:
        dim, green, hi = 28, 40, 46
        white, red, amber, cyan, grey = 231, 196, 214, 51, 244
    else:
        dim = green = hi = curses.COLOR_GREEN
        white, red, amber = curses.COLOR_WHITE, curses.COLOR_RED, curses.COLOR_YELLOW
        cyan, grey = curses.COLOR_CYAN, curses.COLOR_WHITE

    for pair, fg in (
        (P_DIM, dim), (P_GREEN, green), (P_HI, hi), (P_WHITE, white),
        (P_RED, red), (P_AMBER, amber), (P_CYAN, cyan), (P_GREY, grey),
    ):
        curses.init_pair(pair, fg, bg)
    curses.init_pair(P_SEL, curses.COLOR_BLACK, hi)
    curses.init_pair(P_ALERT, white, red)


class Screen:
    """Clipped drawing against a size read once per frame."""

    def __init__(self, stdscr, glyphs: Glyphs):
        self.win = stdscr
        self.g = glyphs
        self.h, self.w = stdscr.getmaxyx()

    def sync(self) -> bool:
        h, w = self.win.getmaxyx()
        if (h, w) != (self.h, self.w):
            self.h, self.w = h, w
            return True
        return False

    @property
    def too_small(self) -> bool:
        return self.h < MIN_H or self.w < MIN_W

    def erase(self) -> None:
        self.win.erase()

    def present(self) -> None:
        self.win.noutrefresh()
        curses.doupdate()

    def text(self, y: int, x: int, s: str, attr: int = 0) -> None:
        if y < 0 or y >= self.h or not s:
            return
        if x < 0:
            s = s[-x:]
            x = 0
        if x >= self.w:
            return
        limit = self.w - x - (1 if y == self.h - 1 else 0)
        if limit <= 0:
            return
        try:
            self.win.addstr(y, x, clip_to_width(s, limit), attr)
        except curses.error:
            pass

    def center(self, y: int, s: str, attr: int = 0) -> None:
        self.text(y, max(0, (self.w - display_width(s)) // 2), s, attr)

    def rule(self, y: int, x: int, width: int, attr: int = 0) -> None:
        self.text(y, x, self.g.hline * width, attr)

    def keys(self) -> list[int]:
        """Drain the input queue so input never lags behind the frame rate."""
        out = []
        while True:
            ch = self.win.getch()
            if ch == -1:
                break
            out.append(ch)
            if len(out) > 32:
                break
        return out


class Clock:
    def __init__(self):
        self.last = time.monotonic()

    def tick(self) -> float:
        now = time.monotonic()
        dt = now - self.last
        self.last = now
        # A suspended process or a slow redraw must not teleport the trace.
        return min(dt, 0.1)


class Rain:
    CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*<>/\\|+-=?"

    def __init__(self, h: int, w: int, density: float = 1.0):
        self.density = density
        self.resize(h, w)

    def resize(self, h: int, w: int) -> None:
        self.h, self.w = max(h, 1), max(w, 1)
        self.cells = [[0] * self.w for _ in range(self.h)]
        self.chars = [[" "] * self.w for _ in range(self.h)]
        self.head = [random.randint(-self.h, 0) for _ in range(self.w)]
        self.rate = [random.uniform(14.0, 45.0) * self.density for _ in range(self.w)]
        self.accum = [random.random() for _ in range(self.w)]

    def update(self, dt: float) -> None:
        for row in self.cells:
            for x in range(self.w):
                if row[x]:
                    row[x] -= 1
        for x in range(self.w):
            self.accum[x] += self.rate[x] * dt
            steps = int(self.accum[x])
            if not steps:
                continue
            self.accum[x] -= steps
            for _ in range(min(steps, 4)):
                self.head[x] += 1
                y = self.head[x]
                if y >= self.h:
                    self.head[x] = -random.randint(0, self.h)
                    self.rate[x] = random.uniform(14.0, 45.0) * self.density
                    break
                if y >= 0:
                    self.chars[y][x] = random.choice(self.CHARS)
                    self.cells[y][x] = random.randint(8, 16)

    def draw(self, screen: Screen, x0: int = 0, x1: int | None = None) -> None:
        """Draw the band [x0, x1), grouping same-attribute runs into one
        addstr each instead of one call per cell."""
        x1 = self.w if x1 is None else min(x1, self.w)
        for y in range(min(self.h, screen.h)):
            cells, chars = self.cells[y], self.chars[y]
            x = x0
            while x < x1:
                level = cells[x]
                if level <= 0:
                    x += 1
                    continue
                attr = self._attr(level)
                start = x
                run = []
                while x < x1 and cells[x] > 0 and self._attr(cells[x]) == attr:
                    run.append(chars[x])
                    x += 1
                screen.text(y, start, "".join(run), attr)

    @staticmethod
    def _attr(level: int) -> int:
        if level >= 13:
            return curses.color_pair(P_WHITE) | curses.A_BOLD
        if level >= 7:
            return curses.color_pair(P_HI) | curses.A_BOLD
        return curses.color_pair(P_DIM)


# --------------------------------------------------------------------------
# Shared widgets
# --------------------------------------------------------------------------


def bar(screen: Screen, y: int, x: int, width: int, pct: float, attr: int,
        label: str = "", empty_attr: int | None = None) -> None:
    filled = max(0, min(width, round(width * pct)))
    g = screen.g
    screen.text(y, x, "[", curses.color_pair(P_GREY))
    screen.text(y, x + 1, g.full * filled, attr)
    # P_DIM reads as a dark green, so it doubles as the default track colour
    # -- but a bar whose fill colour carries meaning (like difficulty) needs
    # an empty_attr that won't itself read as "still green" at 0%.
    screen.text(y, x + 1 + filled, g.empty * (width - filled),
                empty_attr if empty_attr is not None else curses.color_pair(P_DIM))
    screen.text(y, x + 1 + width, "]", curses.color_pair(P_GREY))
    if label:
        screen.text(y, x + width + 3, label, attr)


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap. Long problem statements have to fit narrow panels."""
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if display_width(candidate) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def clear_box(screen: Screen, y0: int, y1: int, width: int) -> None:
    """Blank a centred region so rain doesn't crowd the text drawn over it."""
    width = min(width, screen.w)
    x = max(0, (screen.w - width) // 2)
    blank = " " * width
    for y in range(max(0, y0), min(screen.h, y1 + 1)):
        screen.text(y, x, blank)


def wait_screen(screen: Screen, draw, duration: float | None = None,
                skippable: bool = True, lockout: float = 0.0) -> None:
    """Run `draw(screen, elapsed)` at frame rate until a key or timeout.

    `lockout` ignores input for its first seconds. Typing screens hand over to
    results screens while the player's hands are still moving, and without it
    the trailing keystroke of the last word dismisses the score unread.
    """
    clock = Clock()
    elapsed = 0.0
    screen.win.timeout(int(FRAME * 1000))
    while True:
        elapsed += clock.tick()
        screen.sync()
        keys = screen.keys()
        if skippable and keys and elapsed >= lockout:
            return
        screen.erase()
        draw(screen, elapsed)
        screen.present()
        if duration is not None and elapsed >= duration:
            return


def too_small_notice(screen: Screen) -> None:
    screen.erase()
    screen.text(0, 0, "TERMINAL TOO SMALL", curses.color_pair(P_RED) | curses.A_BOLD)
    screen.text(1, 0, f"{screen.w}x{screen.h} -- need {MIN_W}x{MIN_H}",
                curses.color_pair(P_AMBER))
    screen.text(2, 0, "resize, or Q to quit", curses.color_pair(P_GREY))
    screen.present()


def ensure_size(screen: Screen) -> bool:
    """Block until the terminal is big enough. False if the player quits."""
    if not screen.too_small:
        return True
    screen.win.timeout(120)
    while screen.too_small:
        screen.sync()
        too_small_notice(screen)
        if any(k in (ord("q"), ord("Q")) for k in screen.keys()):
            return False
    return True
