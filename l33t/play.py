"""The typing view: per-character feedback and the live run loop."""

from __future__ import annotations

import curses
import time
from dataclasses import dataclass, field

from .engine import TypingSession
from .ui import (
    FRAME, P_ALERT, P_AMBER, P_CYAN, P_DIM, P_GREEN, P_GREY, P_HI, P_RED,
    P_SEL, P_WHITE, Clock, Screen, bar, too_small_notice,
)

TEXT_X = 4
VISIBLE_BEFORE = 2      # completed lines kept on screen for review
VISIBLE_AFTER = 3       # lines of lookahead

ABORT_KEYS = (27, 4)    # ESC, Ctrl-D -- 'q' is a character you have to type
BACKSPACE_KEYS = (curses.KEY_BACKSPACE, 127, 8)
# Skip the current step. Must not be a printable key -- every one of those is
# a character you might have to type.
SKIP_KEYS = (14, curses.KEY_NPAGE)      # Ctrl-N, PageDown

# Input is polled far faster than the screen is redrawn: keystroke latency is
# a statistic here, so 60Hz quantisation would visibly blur it.
POLL_MS = 4


@dataclass
class RunContext:
    """Per-mode rules layered over the same typing view."""

    mode: str                       # "path" | "practice" | "drill"
    title: str
    subtitle: str = ""
    # One explanation per target line. This is the teaching half of the game:
    # you read what the command does while your hands learn to type it.
    notes: tuple[str, ...] = ()
    lives: int = 0
    node: tuple[int, int] | None = None
    modifier_name: str = ""
    blind: bool = False
    trace_seconds: float | None = None
    time_limit: float | None = None
    error_penalty: float = 0.8
    surge: bool = False
    # Recall mode: the target is hidden and only appears as you type it
    # correctly. This is what tests whether you know the command, rather
    # than whether you can copy one.
    masked: bool = False
    revealed: set = field(default_factory=set)
    hints: int = 0
    # Learning phases run calm: no clock, no speed readout, nothing counting
    # down while you're still working out what a command means. Pressure is
    # for the challenge at the end, once you already understand it.
    calm: bool = False
    phase: str = ""
    # Whether this step can be skipped. The teaching phases can; the timed
    # challenge cannot, or a lesson could be "cleared" without being done.
    skippable: bool = False

    trace: float = 0.0
    outcome: str | None = None      # "done" | "traced" | "timeup" | "abort"

    @property
    def trace_pct(self) -> float:
        if not self.trace_seconds:
            return 0.0
        return min(1.0, self.trace / self.trace_seconds)

    def penalise(self) -> None:
        if self.trace_seconds:
            self.trace += self.error_penalty

    def update(self, dt: float, session: TypingSession) -> None:
        # Nothing starts counting until the first keypress. Reading the
        # commands, or just getting your hands settled, is free -- and the
        # challenge card promises exactly this.
        if session.started is None:
            return

        if self.trace_seconds:
            rate = 1.0
            if self.surge:
                # The longer they're onto you, the faster it closes.
                rate += self.trace_pct
            self.trace += dt * rate
            if self.trace >= self.trace_seconds:
                self.outcome = "traced"
        if self.time_limit and session.started is not None:
            if time.monotonic() - session.started >= self.time_limit:
                self.outcome = "timeup"


def run_typing(screen: Screen, session: TypingSession, ctx: RunContext) -> RunContext:
    """Drive one typing run to completion, abort, or failure."""
    clock = Clock()
    screen.win.timeout(POLL_MS)
    last_draw = 0.0
    dirty = True

    while True:
        dt = clock.tick()
        screen.sync()

        if screen.too_small:
            too_small_notice(screen)
            if any(k in ABORT_KEYS for k in screen.keys()):
                ctx.outcome = "abort"
                return ctx
            clock.tick()
            continue

        now = time.monotonic()
        for key in screen.keys():
            if key in ABORT_KEYS:
                ctx.outcome = "abort"
                return ctx
            if key in SKIP_KEYS and ctx.skippable:
                ctx.outcome = "skipped"
                return ctx
            if key == 9 and ctx.masked:          # TAB: give up, show it
                if session.line not in ctx.revealed:
                    ctx.revealed.add(session.line)
                    ctx.hints += 1
                dirty = True
            elif key in BACKSPACE_KEYS:
                session.backspace(now)
                dirty = True
            elif 32 <= key <= 126:
                if session.press(chr(key), now):
                    ctx.penalise()
                dirty = True

        if session.done and ctx.outcome is None:
            ctx.outcome = "done"
        if ctx.outcome is None:
            ctx.update(dt, session)
        if ctx.outcome:
            draw_run(screen, session, ctx)
            screen.present()
            return ctx

        # Poll fast, draw at frame rate.
        if dirty or now - last_draw >= FRAME:
            draw_run(screen, session, ctx)
            screen.present()
            last_draw = now
            dirty = False


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


WINDOW = VISIBLE_BEFORE + VISIBLE_AFTER + 1
# Rows below the text block that must always survive: explanation, spacer,
# rule, footer. The explanation is the teaching half of the game, so a short
# terminal drops lookahead lines rather than dropping it.
FOOTER_ROWS = 4
TEXT_TOP = 7


def window_size(height: int) -> int:
    return max(1, min(WINDOW, (height - TEXT_TOP - FOOTER_ROWS) // 2))


def visible_range(line: int, total: int, cap: int = WINDOW) -> tuple[int, int]:
    """The half-open range of lines to show around the active one."""
    cap = max(1, min(cap, WINDOW))
    before = min(VISIBLE_BEFORE, (cap - 1) // 2)
    first = max(0, line - before)
    last = min(total, first + cap)
    first = max(0, min(first, last - cap))
    return first, last


def draw_run(screen: Screen, session: TypingSession, ctx: RunContext) -> None:
    screen.erase()
    draw_hud(screen, session, ctx)

    top = TEXT_TOP
    first, last = visible_range(session.line, len(session.lines),
                                window_size(screen.h))

    for i in range(first, last):
        y = top + (i - first) * 2
        active = i == session.line
        if active:
            screen.text(y, TEXT_X - 2, screen.g.arrow,
                        curses.color_pair(P_HI) | curses.A_BOLD)
        draw_text_line(screen, y, TEXT_X, session.lines[i],
                       session.typed[i], session.ok[i],
                       cursor=session.pos if active else None,
                       active=active, blind=ctx.blind,
                       mask=ctx.masked and i not in ctx.revealed,
                       hidden=screen.g.hidden)

    y = top + (last - first) * 2
    if ctx.notes:
        note = ctx.notes[session.line] if session.line < len(ctx.notes) else ""
        if note:
            screen.text(y, TEXT_X, screen.g.note + " " + note,
                        curses.color_pair(P_CYAN))
        y += 2

    draw_footer(screen, session, ctx, y)


def draw_text_line(screen: Screen, y: int, x: int, target: str,
                   typed: list[str], ok: list[bool], cursor: int | None,
                   active: bool, blind: bool, mask: bool = False,
                   hidden: str = "·") -> None:
    """One target line, coloured per character.

    A mistyped character shows the character you *should* have hit, on red --
    seeing the right answer at the point of failure is what teaches the hand.
    """
    attrs: list[int] = []
    for i, ch in enumerate(target):
        if i < len(typed):
            if blind:
                attr = curses.color_pair(P_DIM)
            elif ok[i]:
                attr = (curses.color_pair(P_HI) | curses.A_BOLD if active
                        else curses.color_pair(P_GREEN))
            else:
                attr = curses.color_pair(P_ALERT) | curses.A_BOLD
        elif active:
            attr = curses.color_pair(P_WHITE)
        else:
            attr = curses.color_pair(P_DIM)
        attrs.append(attr)

    if cursor is not None and cursor < len(target):
        attrs[cursor] = curses.color_pair(P_SEL) | curses.A_BOLD

    # In recall mode, characters you haven't reached yet are placeholders:
    # you can see the shape of the answer, not the answer.
    shown = list(target)
    if mask:
        for i in range(len(target)):
            if i >= len(typed):
                shown[i] = " " if target[i] == " " else hidden

    i = 0
    while i < len(target):
        attr = attrs[i]
        start = i
        run = []
        while i < len(target) and attrs[i] == attr:
            run.append(shown[i])
            i += 1
        screen.text(y, x + start, "".join(run), attr)

    # Cursor parked past the end of the line (everything typed, line about to
    # roll over) still needs to be visible.
    if cursor is not None and cursor >= len(target):
        screen.text(y, x + len(target), " ",
                    curses.color_pair(P_SEL) | curses.A_BOLD)


def draw_hud(screen: Screen, session: TypingSession, ctx: RunContext) -> None:
    m = session.metrics(time.monotonic())

    title = ctx.title
    screen.text(0, 2, title, curses.color_pair(P_WHITE) | curses.A_BOLD)
    if ctx.modifier_name:
        screen.text(0, 2 + len(title) + 2, f"[{ctx.modifier_name}]",
                    curses.color_pair(P_RED) | curses.A_BOLD)

    if ctx.calm:
        # Deliberately no speed, no accuracy, no clock.
        if ctx.phase:
            screen.text(0, max(0, screen.w - len(ctx.phase) - 2), ctx.phase,
                        curses.color_pair(P_CYAN) | curses.A_BOLD)
    else:
        right = f"{m.net_wpm:5.1f} WPM   {m.accuracy:5.1%} ACC"
        screen.text(0, max(0, screen.w - len(right) - 2), right,
                    curses.color_pair(P_AMBER))

    if ctx.subtitle:
        from .ui import wrap
        for i, line in enumerate(wrap(ctx.subtitle, max(20, screen.w - 6))[:2]):
            screen.text(1 + i, 2, line, curses.color_pair(P_CYAN))

    if ctx.calm:
        pass
    elif ctx.trace_seconds:
        pct = ctx.trace_pct
        attr = (curses.color_pair(P_HI) if pct < 0.5
                else curses.color_pair(P_AMBER) | curses.A_BOLD if pct < 0.8
                else curses.color_pair(P_RED) | curses.A_BOLD)
        screen.text(3, 2, "TRACE", curses.color_pair(P_GREY))
        bar(screen, 3, 8, 28, pct, attr, f"{int(pct * 100):3d}%")
        if pct >= 0.8:
            screen.text(3, 44, "!! TRACE IMMINENT !!",
                        curses.color_pair(P_ALERT) | curses.A_BOLD)
    elif ctx.time_limit:
        left = ctx.time_limit
        if session.started is not None:
            left = max(0.0, ctx.time_limit - (time.monotonic() - session.started))
        attr = (curses.color_pair(P_RED) | curses.A_BOLD if left <= 5
                else curses.color_pair(P_CYAN))
        screen.text(3, 2, "TIME", curses.color_pair(P_GREY))
        bar(screen, 3, 8, 28, 1.0 - left / ctx.time_limit, attr, f"{left:4.1f}s")

    screen.text(4, 2, "PROGRESS", curses.color_pair(P_GREY))
    bar(screen, 4, 11, 25, session.progress(), curses.color_pair(P_GREEN))
    if not ctx.calm:
        screen.text(4, 44, f"ERRORS {m.errors}",
                    curses.color_pair(P_RED if m.errors else P_GREY))

    screen.rule(5, 2, min(screen.w - 4, 72), curses.color_pair(P_DIM))


def draw_footer(screen: Screen, session: TypingSession, ctx: RunContext,
                y: int) -> None:
    y = min(y, screen.h - 2)
    screen.rule(y - 1, 2, min(screen.w - 4, 72), curses.color_pair(P_DIM))
    hints = ["ESC abort"]
    if ctx.skippable:
        hints.insert(0, "ctrl-N skip this step")
    if ctx.masked:
        hints.insert(0, "TAB reveal")
    if not session.allow_backspace:
        hints.insert(0, "BACKSPACE DISABLED")
    if session.strict:
        hints.insert(0, "must fix errors to advance")
    if ctx.blind:
        hints.insert(0, "blind: no feedback")
    screen.text(y, 2, "   ".join(hints), curses.color_pair(P_GREY))
