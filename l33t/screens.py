"""Menus, run wrappers, results and the stats screen."""

from __future__ import annotations

import curses
import random
import time

from . import akari
from . import shell
from .effects import FLASH, SCRAMBLING, Decrypt, Typewriter
from .engine import KeyStat, TypingSession
from .modes import (
    CLEAR_ACCURACY, DIFFICULTIES, LINE_WIDTH, build_path, phases_from,
    step_payload,
)
from .play import RunContext, run_typing
from .stats import Profile
from . import watch
from .watch import stream as shell_stream
from . import tte
from .ui import (
    FRAME, P_ALERT, P_AMBER, P_CYAN, P_DIM, P_GREEN, P_GREY, P_HI, P_RED,
    P_SEL, P_WHITE, Clock, Rain, Screen, bar, clear_box, ensure_size,
    clip_to_width, display_width, too_small_notice, wait_screen, wrap,
)

ENTER_KEYS = (10, 13, curses.KEY_ENTER)
UP_KEYS = (curses.KEY_UP, ord("k"), ord("K"), ord("w"), ord("W"))
DOWN_KEYS = (curses.KEY_DOWN, ord("j"), ord("J"), ord("s"), ord("S"))
QUIT_KEYS = (ord("q"), ord("Q"), 27)

SPARK = "▁▂▃▄▅▆▇█"

# Results screens open while the player's hands are still moving; ignore input
# briefly so a trailing keystroke can't dismiss a score before it's read.
DISMISS_LOCKOUT = 0.7

# How fast the sample-run output streams in.
DEMO_LINE = 0.13


# --------------------------------------------------------------------------
# Boot
# --------------------------------------------------------------------------

BOOT_LINES = [
    ("BIOS ROM v4.02 -- L33T SYSTEMS INC.", P_GREY),
    ("KEYBOARD CONTROLLER: 8042", P_GREY),
    ("CALIBRATING INPUT LATENCY", P_GREEN),
    ("LOADING PAYLOAD CORPUS", P_GREEN),
    ("ARMING ICEBREAKER", P_AMBER),
    ("", P_GREEN),
    ("TYPE FAST. TYPE CLEAN.", P_HI),
]
# Readable, but it's a splash screen -- nobody wants to sit through it twice.
# Each line lands, its check completes, then the next one starts.
CPS = 95.0
OK_DELAY = 0.10         # line finishes -> its "OK" appears
LINE_PAUSE = 0.17       # gap before the next line starts
FINAL_HOLD = 0.7        # linger on the last line


def boot_schedule() -> tuple[list[tuple[float, str, int, Typewriter]], float]:
    """When each boot line starts typing, and how long the whole thing runs."""
    schedule, at = [], 0.0
    for line, pair in BOOT_LINES:
        typer = Typewriter(line, cps=CPS)
        schedule.append((at, line, pair, typer))
        at += typer.duration + LINE_PAUSE
        if line and pair != P_HI:
            at += OK_DELAY
    return schedule, at + FINAL_HOLD


def boot(screen: Screen, rng: random.Random | None = None) -> None:
    # If terminaltexteffects is installed, let it do the title flourish: it's
    # a one-shot, non-interactive moment, which is the one place TTE fits.
    if tte.available():
        if tte.play(screen.win, "L33T  //  TYPE FAST. TYPE CLEAN.", rng=rng):
            return
    schedule, duration = boot_schedule()

    def draw(scr: Screen, elapsed: float) -> None:
        y = max(0, scr.h // 2 - len(BOOT_LINES) // 2)
        for i, (start, line, pair, typer) in enumerate(schedule):
            if elapsed < start:
                break
            local = elapsed - start
            shown = typer.visible(local)
            attr = curses.color_pair(pair)
            if pair == P_HI:
                attr |= curses.A_BOLD
            scr.text(y + i, 4, shown, attr)
            if typer.caret(local):
                scr.text(y + i, 4 + len(shown), " ",
                         curses.color_pair(P_SEL) | curses.A_BOLD)
            elif line and pair != P_HI and local >= typer.duration + OK_DELAY:
                scr.text(y + i, 4 + len(line) + 2, "OK",
                         curses.color_pair(P_HI) | curses.A_BOLD)
        scr.text(scr.h - 2, 4, "any key to skip", curses.color_pair(P_DIM))

    wait_screen(screen, draw, duration=duration)


# --------------------------------------------------------------------------
# Generic menu
# --------------------------------------------------------------------------


def menu(screen: Screen, options: list[tuple[str, str, str]], *,
         rain: Rain | None = None, heading: list[str] | None = None,
         footnote: str = "", aside: str = "") -> str:
    """options: (key, label, hint). Returns the chosen key, or "quit"."""
    idx = 0
    own_rain = rain is None
    if own_rain:
        rain = Rain(screen.h, screen.w)
    clock = Clock()
    screen.win.timeout(int(FRAME * 1000))

    while True:
        dt = clock.tick()
        if screen.sync():
            rain.resize(screen.h, screen.w)
        for key in screen.keys():
            if key in UP_KEYS:
                idx = (idx - 1) % len(options)
            elif key in DOWN_KEYS:
                idx = (idx + 1) % len(options)
            elif key in ENTER_KEYS:
                return options[idx][0]
            elif key in QUIT_KEYS:
                return "quit"

        rain.update(dt)
        screen.erase()
        rain.draw(screen)

        head = heading if heading is not None else screen.g.logo
        top = max(0, screen.h // 2 - (len(head) + len(options)) // 2 - 3)
        width = max(max(len(h) for h in head) if head else 0, 46)
        clear_box(screen, top - 1, top + len(head) + len(options) + 5, width + 10)

        for i, line in enumerate(head):
            screen.center(top + i, line, curses.color_pair(P_HI) | curses.A_BOLD)

        base = top + len(head) + 2
        # Size the label column to the longest label, or a long one overflows
        # into the hint column and gets clipped.
        label_w = max(len(label) for _, label, _ in options) + 3
        hint_w = max((len(hint) for *_, hint in options), default=0)
        x = max(0, (screen.w - (label_w + 2 + hint_w)) // 2)
        for i, (_, label, hint) in enumerate(options):
            selected = i == idx
            text = f"{screen.g.arrow} {label}" if selected else f"  {label}"
            attr = (curses.color_pair(P_SEL) | curses.A_BOLD if selected
                    else curses.color_pair(P_GREEN))
            screen.text(base + i, x, text.ljust(label_w), attr)
            screen.text(base + i, x + label_w + 2, hint,
                        curses.color_pair(P_AMBER if selected else P_DIM))

        if footnote:
            screen.center(base + len(options) + 2, footnote,
                          curses.color_pair(P_CYAN))
        if aside:
            screen.center(base + len(options) + 3, aside,
                          curses.color_pair(P_AMBER))
        screen.center(screen.h - 2, "arrows move   enter select   q back",
                      curses.color_pair(P_GREY))
        screen.present()


def title(screen: Screen, profile: Profile, rng: random.Random | None = None) -> str:
    best = profile.best_wpm()
    cleared = profile.cleared_count()
    total = len(shell.LESSONS)
    note = f"path {cleared}/{total} cleared"
    if best:
        note += f"   ·   best {best:.0f} wpm"
    # She greets you differently depending on how far along you are.
    line = akari.say(screen.g.unicode,
                     akari.menu_line(cleared, total, rng or random))
    return menu(screen, [
        ("path", "LEARNING PATH", f"{total} lessons, real commands"),
        ("practice", "PRACTICE", "free run, whole library"),
        ("drill", "DRILL", "target your worst keys"),
        ("codex", "CODEX", "the tools you've met"),
        ("watch", "WATCH", "look over an expert's shoulder"),
        ("stats", "STATS", "your progress"),
        ("briefing", "BRIEFING", "how it works"),
        ("quit", "DISCONNECT", ""),
    ], footnote=note, aside=line)


# --------------------------------------------------------------------------
# Briefing
# --------------------------------------------------------------------------

BRIEFING = [
    ("L33T teaches you the shell by making you type it.", P_WHITE),
    ("", P_GREEN),
    ("Every line is a real command. While you type it, the line below", P_GREEN),
    ("tells you what it does -- so you finish a lesson having learned", P_GREEN),
    ("the tool, not just the muscle memory.", P_GREEN),
    ("", P_GREEN),
    ("Correct characters turn green; a mistake shows the character you", P_GREEN),
    ("SHOULD have hit, on red, at the moment you get it wrong.", P_GREEN),
    ("", P_GREEN),
    ("LEARNING PATH  11 lessons, in teaching order: files, reading,", P_AMBER),
    ("      finding, text processing, pipes, permissions, processes,", P_AMBER),
    ("      networking, git, archives, scripting. Clear a lesson by", P_AMBER),
    ("      finishing it before the trace fills, at 90% accuracy.", P_AMBER),
    ("      Later lessons add pressure: LOCKDOWN, NO BACKSPACE,", P_AMBER),
    ("      SURGE, PURGE.", P_AMBER),
    ("", P_GREEN),
    ("PRACTICE   free run across the whole command library.", P_CYAN),
    ("DRILL      built from the keys you actually fumble.", P_CYAN),
    ("CODEX      every tool you've typed, what it does, how clean.", P_CYAN),
    ("", P_GREEN),
    ("ESC aborts a run ('q' is a character you have to type).", P_GREY),
]


def briefing(screen: Screen) -> None:
    def draw(scr: Screen, _e: float) -> None:
        top = max(1, (scr.h - len(BRIEFING)) // 2)
        x = max(2, (scr.w - 64) // 2)
        for i, (line, pair) in enumerate(BRIEFING):
            attr = curses.color_pair(pair)
            if i == 0:
                attr |= curses.A_BOLD
            scr.text(top + i, x, line, attr)
        scr.center(scr.h - 2, "any key to return", curses.color_pair(P_GREY))

    wait_screen(screen, draw)


# --------------------------------------------------------------------------
# Run wrappers
# --------------------------------------------------------------------------


def _tool_breakdown(session: TypingSession,
                    commands: list) -> dict[str, tuple[int, int]]:
    """Attribute each line's characters to the tool it was teaching."""
    out: dict[str, tuple[int, int]] = {}
    for (typed, correct), cmd in zip(session.line_results(), commands):
        if not typed:
            continue
        had, bad = out.get(cmd.tool, (0, 0))
        out[cmd.tool] = (had + typed, bad + (typed - correct))
    return out


def run_commands(screen: Screen, profile: Profile, commands: list,
                 ctx_kwargs: dict, mode: str) -> tuple[TypingSession, RunContext]:
    """Shared path for every mode: type these commands, then record."""
    session = TypingSession(
        [c.text for c in commands],
        strict=ctx_kwargs.pop("strict", False),
        allow_backspace=ctx_kwargs.pop("allow_backspace", True))
    ctx = RunContext(mode=mode, notes=tuple(c.explain for c in commands),
                     **ctx_kwargs)
    ctx = run_typing(screen, session, ctx)
    if session.started is not None and len(session.keystrokes) >= 10:
        profile.record_tools(_tool_breakdown(session, commands))
    return session, ctx


def practice(screen: Screen, profile: Profile, rng: random.Random) -> None:
    commands = shell.sample_commands(10, rng, profile.weak_keys(6))
    session, ctx = run_commands(screen, profile, commands, dict(
        title="PRACTICE", subtitle="whole library -- no timer, no trace"),
        "practice")
    finish(screen, profile, session, ctx, "practice")


def drill(screen: Screen, profile: Profile, rng: random.Random) -> None:
    weak = profile.weak_keys(8)
    if weak:
        subtitle = "targeting: " + " ".join(_display(c) for c in weak)
    else:
        subtitle = "no history yet -- this run builds your key profile"
    commands = shell.sample_commands(8, rng, weak)
    # Two pure punctuation lines: the part of shell typing that actually hurts.
    drills = [shell.Command(shell.symbol_drill(rng, weak),
                            "raw punctuation -- no meaning, just accuracy",
                            "symbols") for _ in range(2)]
    commands = commands[:6] + drills
    rng.shuffle(commands)
    session, ctx = run_commands(screen, profile, commands, dict(
        title="DRILL", subtitle=subtitle), "drill")
    finish(screen, profile, session, ctx, "drill")


def path_screen(screen: Screen, profile: Profile, rng: random.Random,
                difficulty: str = "normal") -> None:
    """Browse the syllabus and pick a lesson."""
    steps = build_path()
    idx = 0
    rain = Rain(screen.h, screen.w, density=0.35)
    clock = Clock()
    screen.win.timeout(int(FRAME * 1000))

    while True:
        dt = clock.tick()
        if screen.sync():
            rain.resize(screen.h, screen.w)
        for k in screen.keys():
            if k in UP_KEYS:
                idx = (idx - 1) % len(steps)
            elif k in DOWN_KEYS:
                idx = (idx + 1) % len(steps)
            elif k in ENTER_KEYS:
                play_lesson(screen, profile, steps[idx], rng, difficulty)
                screen.win.timeout(int(FRAME * 1000))
            elif k in QUIT_KEYS:
                return

        rain.update(dt)
        screen.erase()
        rain.draw(screen)

        panel_w = 68
        x = max(2, (screen.w - panel_w) // 2)
        cleared = profile.cleared_count()

        # Everything below is one block, vertically centred, instead of the
        # list anchored to the top and the detail panel pinned to the
        # bottom -- which used to leave a dead gap for any list shorter
        # than the terminal.
        list_rows = len(steps)
        detail_rows = 6
        block_h = 2 + list_rows + 1 + detail_rows
        top = max(1, (screen.h - block_h) // 2)

        clear_box(screen, top - 1, top + block_h + 1, panel_w + 6)

        screen.text(top, x, "LEARNING PATH",
                    curses.color_pair(P_WHITE) | curses.A_BOLD)
        count = f"{cleared}/{len(steps)} cleared"
        screen.text(top, x + panel_w - len(count), count,
                    curses.color_pair(P_AMBER))
        bar(screen, top + 1, x, panel_w - 2, cleared / len(steps),
            curses.color_pair(P_HI))

        list_top = top + 3
        for i, step in enumerate(steps):
            y = list_top + i
            state = profile.lesson(step.key)
            sel = i == idx
            mark = ("✓" if screen.g.unicode else "*") if state.cleared else " "
            label = f"{mark} {step.index:2}. {step.name}"
            attr = (curses.color_pair(P_SEL) | curses.A_BOLD if sel
                    else curses.color_pair(P_HI if state.cleared else P_GREEN))
            screen.text(y, x, label.ljust(30), attr)

            detail = f"{len(step.lesson.commands):2} cmds"
            if state.best_wpm:
                detail += f"   best {state.best_wpm:4.1f} wpm  {state.best_accuracy:5.1%}"
            screen.text(y, x + 31, detail, curses.color_pair(P_DIM))

            if step.modifier:
                screen.text(y, x + 62, step.modifier.tag,
                            curses.color_pair(P_RED))

        step = steps[idx]
        state = profile.lesson(step.key)
        by = list_top + list_rows + 1
        screen.rule(by - 1, x, panel_w - 2, curses.color_pair(P_DIM))
        screen.text(by, x, step.lesson.blurb, curses.color_pair(P_CYAN))
        screen.text(by + 1, x, "tools: " + "  ".join(step.lesson.tools),
                    curses.color_pair(P_DIM))

        remark_y = by + 2
        if step.modifier:
            screen.text(remark_y, x,
                        f"{step.modifier.name}: {step.modifier.blurb}",
                        curses.color_pair(P_RED))
            remark_y += 1

        remark = akari.lesson_remark(step.key)
        if remark:
            _akari_line(screen, remark_y, x, remark)
        elif state.attempts:
            screen.text(remark_y, x,
                        f"{state.attempts} attempt(s) so far",
                        curses.color_pair(P_DIM))

        screen.center(screen.h - 2,
                      f"enter to start   q back   ·   difficulty: {difficulty}",
                      curses.color_pair(P_GREY))
        screen.present()


# Commands taught per run. Four learned properly beats six skimmed.
LEARN_COMMANDS = 4


def play_lesson(screen: Screen, profile: Profile, step, rng: random.Random,
                difficulty: str = "normal", start: str | None = None) -> None:
    """A lesson is five phases:

        problem  ->  breakdown  ->  type it  ->  recall  ->  challenge

    Everything up to the challenge is untimed and self-paced. Nothing counts
    down while you're still working out what a command does; the clock only
    appears once you already know it.

    Any teaching step can be skipped with ctrl-N, and you can start partway
    through -- but never past the challenge, which is the only thing that
    clears a lesson.
    """
    if not ensure_size(screen):
        return
    if start is None:
        start = start_point(screen, step)
        if start == "quit":
            return
    phases = phases_from(start)

    commands = shell.lesson_commands(step.lesson, LEARN_COMMANDS, rng)
    total = len(commands)

    if lesson_card(screen, step) == "abort":
        return

    # -- phases 1-3: meet each command one at a time ---------------------
    if "learn" in phases:
        for i, cmd in enumerate(commands, 1):
            if problem_screen(screen, cmd, i, total) == "abort":
                return
            if breakdown_screen(screen, cmd, i, total) == "abort":
                return
            session, ctx = type_single(
                screen, cmd, title=f"{step.name} :: TYPE IT",
                phase=f"LEARN {i}/{total}", subtitle=cmd.problem, masked=False)
            if ctx.outcome == "abort":
                return
            if ctx.outcome != "skipped":
                _bank(profile, session, [cmd])

    # -- phase 4: recall -- problem only, command hidden ------------------
    hinted = 0
    if "recall" in phases:
        if phase_card(screen, "RECALL",
                      "Now without the answer in front of you.",
                      ["You'll see only the problem. Type the command that solves",
                       "it. Characters appear as you get them right.",
                       "",
                       "Still no clock -- take as long as you need.",
                       "TAB reveals the command, ctrl-N skips it."]) == "abort":
            return
        for i, cmd in enumerate(commands, 1):
            session, ctx = type_single(
                screen, cmd, title=f"{step.name} :: RECALL",
                phase=f"RECALL {i}/{total}", subtitle=cmd.problem, masked=True)
            if ctx.outcome == "abort":
                return
            if ctx.outcome != "skipped":
                hinted += ctx.hints
                _bank(profile, session, [cmd])

    # -- phase 5: challenge, the only timed part -------------------------
    commands, trace = step_payload(step, rng, difficulty, commands)
    if phase_card(screen, "CHALLENGE",
                  "You know them. Now type them fast.",
                  [f"All {total} commands, back to back, against the trace.",
                   f"Target {step.target_wpm / DIFFICULTIES[difficulty]:.0f} wpm"
                   f" at {CLEAR_ACCURACY:.0%} accuracy.",
                   "",
                   "This is the only timed phase. The clock starts on your",
                   "first keypress, not now."]) == "abort":
        return

    session, ctx = run_commands(screen, profile, commands, dict(
        title=f"{step.name} :: CHALLENGE",
        subtitle="type them quickly and cleanly",
        modifier_name=step.modifier.name if step.modifier else "",
        blind=step.has("blind"),
        trace_seconds=trace,
        error_penalty=1.6 if step.has("purge") else 0.8,
        surge=step.has("surge"),
        strict=step.has("lockdown"),
        allow_backspace=not step.has("nobackspace")), "path")

    if session.started is None:
        return
    m = session.metrics(time.monotonic())
    cleared = ctx.outcome == "done" and m.accuracy >= CLEAR_ACCURACY
    profile.record_lesson(step.key, m.net_wpm, m.accuracy, cleared)
    record(profile, session, "path")
    lesson_result(screen, session, step, ctx.outcome, cleared, hinted, rng)


def _bank(profile: Profile, session: TypingSession, commands: list) -> None:
    """Fold a learning-phase run into the profile, without logging it as a
    timed result -- these runs are deliberately slow."""
    if session.started is None or len(session.keystrokes) < 5:
        return
    profile.record_tools(_tool_breakdown(session, commands))
    for ch, stat in session.key_stats().items():
        acc = profile.keys.setdefault(ch, KeyStat())
        acc.attempts += stat.attempts
        acc.errors += stat.errors
        acc.latency_total += stat.latency_total
        acc.latency_n += stat.latency_n
    profile.save()


def type_single(screen: Screen, cmd, *, title: str, phase: str,
                subtitle: str, masked: bool):
    """One command, untimed, no speed readout. Strict: you cannot move past a
    character until it's right, because the point is to learn it correctly."""
    session = TypingSession([cmd.text], strict=True)
    ctx = RunContext(mode="learn", title=title, phase=phase, calm=True,
                     masked=masked, notes=() if masked else (cmd.explain,),
                     subtitle=subtitle, skippable=True)
    return session, run_typing(screen, session, ctx)


# --------------------------------------------------------------------------
# Teaching screens -- all self-paced, none auto-advance
# --------------------------------------------------------------------------


def _await_key_animated(screen: Screen, draw, duration: float) -> str:
    """Draw an animation, then wait for a keypress.

    The first key completes the animation rather than dismissing the screen,
    so an impatient player skips the effect without ever losing the content
    behind it. ESC leaves the lesson."""
    clock = Clock()
    screen.win.timeout(int(FRAME * 1000))
    elapsed = 0.0
    while True:
        elapsed += clock.tick()
        screen.sync()
        if screen.too_small:
            too_small_notice(screen)
            continue
        for key in screen.keys():
            if key == 27:
                return "abort"
            if elapsed < duration:
                elapsed = duration          # first key: skip to the end
            else:
                return "ok"
        screen.erase()
        draw(screen, elapsed)
        screen.present()


def problem_screen(screen: Screen, cmd, i: int, total: int) -> str:
    width = 58
    lines = wrap(cmd.problem, width)
    typers, at = [], 0.35
    for line in lines:
        typers.append((at, Typewriter(line, cps=260)))
        at += Typewriter(line, cps=260).duration + 0.05
    duration = at + 0.4

    def draw(scr: Screen, elapsed: float) -> None:
        w = min(width, scr.w - 8)
        top = max(2, scr.h // 2 - (len(lines) + 6) // 2)
        x = max(2, (scr.w - w) // 2)
        scr.text(top, x, f"INCOMING TASK  {i}/{total}",
                 curses.color_pair(P_AMBER) | curses.A_BOLD)
        for k, (start, typer) in enumerate(typers):
            shown = typer.visible(elapsed - start)
            scr.text(top + 2 + k, x, shown,
                     curses.color_pair(P_WHITE) | curses.A_BOLD)
            if typer.caret(elapsed - start):
                scr.text(top + 2 + k, x + len(shown), " ",
                         curses.color_pair(P_SEL) | curses.A_BOLD)
        if elapsed >= duration - 0.4:
            y = top + 3 + len(lines)
            scr.text(y, x, "How would you do that?",
                     curses.color_pair(P_HI) | curses.A_BOLD)
            scr.text(y + 2, x, "Have a think -- nothing is timed here.",
                     curses.color_pair(P_DIM))
        scr.center(scr.h - 2, "any key for the answer   ·   esc to leave",
                   curses.color_pair(P_GREY))

    return _await_key_animated(screen, draw, duration)


def breakdown_screen(screen: Screen, cmd, i: int, total: int) -> str:
    """The command decrypts into place, then each part lights up *inside the
    command* while its explanation types in -- so you see which characters an
    explanation is talking about, not just a list beside it. Then a sample run,
    so you know what it actually prints."""
    decrypt = Decrypt(cmd.text, seed=i * 7)
    spans = shell.part_spans(cmd)
    label_w = max(len(part.text) for part in cmd.parts)

    summary_at = decrypt.duration + 0.15
    summary = Typewriter(cmd.explain, cps=240)

    schedule, at = [], summary_at + summary.duration + 0.35
    for part in cmd.parts:
        typer = Typewriter(part.means, cps=210)
        schedule.append((at, typer))
        at += typer.duration + 0.22

    demo_at = at + 0.45
    duration = demo_at + len(cmd.demo) * DEMO_LINE + 0.2

    def active_part(elapsed: float) -> int | None:
        for k, (start, typer) in enumerate(schedule):
            if start <= elapsed < start + typer.duration:
                return k
        return None

    def draw(scr: Screen, elapsed: float) -> None:
        width = min(70, scr.w - 6)
        x = max(2, (scr.w - width) // 2)
        part_rows = sum(max(1, len(wrap(p.means, width - label_w - 4)))
                        for p in cmd.parts)
        # The sample run is the first thing sacrificed on a short terminal.
        room = scr.h - 4 - (5 + part_rows + 3)
        demo_lines = cmd.demo[:max(0, room)]
        total_rows = 5 + part_rows + (2 + len(demo_lines) + 1 if demo_lines else 0)
        top = max(1, (scr.h - total_rows - 2) // 2)

        decrypting = not decrypt.done(elapsed)
        if decrypting:
            scr.text(top, x, "DECRYPTING PAYLOAD",
                     curses.color_pair(P_AMBER) | curses.A_BOLD)
            bar(scr, top, x + 20, 18, decrypt.progress(elapsed),
                curses.color_pair(P_HI))
        else:
            scr.text(top, x, f"THE COMMAND  {i}/{total}",
                     curses.color_pair(P_GREY))

        current = active_part(elapsed)
        done_through = sum(1 for start, _ in schedule if elapsed >= start)
        chars, attrs = [], []
        for k, ch in enumerate(cmd.text):
            glyph, tier = decrypt.state(k, elapsed)
            chars.append(glyph)
            if decrypting:
                attrs.append(curses.color_pair(P_DIM) if tier == SCRAMBLING
                             else curses.color_pair(P_WHITE) | curses.A_BOLD
                             if tier == FLASH
                             else curses.color_pair(P_HI) | curses.A_BOLD)
                continue
            if current is not None and spans[current][0] <= k < spans[current][1]:
                attrs.append(curses.color_pair(P_SEL) | curses.A_BOLD)
            elif any(s <= k < e for s, e in spans[:done_through]):
                attrs.append(curses.color_pair(P_HI) | curses.A_BOLD)
            else:
                attrs.append(curses.color_pair(P_GREEN))
        _runs(scr, top + 2, x, chars, attrs)

        scr.text(top + 3, x, summary.visible(elapsed - summary_at),
                 curses.color_pair(P_CYAN))
        if elapsed >= summary_at:
            scr.rule(top + 4, x, width, curses.color_pair(P_DIM))

        y = top + 5
        for k, (start, typer) in enumerate(schedule):
            if elapsed < start:
                break
            part = cmd.parts[k]
            live = k == current
            scr.text(y, x, screen.g.note if live else " ",
                     curses.color_pair(P_AMBER) | curses.A_BOLD)
            scr.text(y, x + 2, part.text.ljust(label_w),
                     curses.color_pair(P_SEL if live else P_GREEN)
                     | curses.A_BOLD)
            shown = typer.visible(elapsed - start)
            rows = wrap(shown, width - label_w - 4) or [""]
            for n, line in enumerate(rows):
                scr.text(y + n, x + label_w + 4, line,
                         curses.color_pair(P_WHITE if n == 0 else P_DIM))
            y += len(rows)

        # --- the sample run ------------------------------------------
        if demo_lines and elapsed >= demo_at:
            scr.text(y + 1, x, "IF YOU RUN IT",
                     curses.color_pair(P_AMBER) | curses.A_BOLD)
            scr.text(y + 2, x, "$ ", curses.color_pair(P_GREY))
            scr.text(y + 2, x + 2, cmd.text,
                     curses.color_pair(P_HI) | curses.A_BOLD)
            shown = min(len(demo_lines), int((elapsed - demo_at) / DEMO_LINE) + 1)
            for n, line in enumerate(demo_lines[:shown]):
                row = y + 3 + n
                if line.startswith("$ "):
                    # A follow-up command, for when this one prints nothing.
                    scr.text(row, x, "$ ", curses.color_pair(P_GREY))
                    scr.text(row, x + 2, line[2:],
                             curses.color_pair(P_HI) | curses.A_BOLD)
                else:
                    scr.text(row, x + 2, line.expandtabs(8),
                             curses.color_pair(P_DIM))

        if elapsed >= duration:
            scr.center(scr.h - 2, "any key to type it   ·   esc to leave",
                       curses.color_pair(P_GREY))
        else:
            scr.center(scr.h - 2, "any key to skip ahead",
                       curses.color_pair(P_DIM))

    return _await_key_animated(screen, draw, duration)


def _runs(screen: Screen, y: int, x: int, chars: list[str],
          attrs: list[int]) -> None:
    """Draw a per-character-coloured line, batching equal attributes."""
    i = 0
    while i < len(chars):
        attr = attrs[i]
        start = i
        run = []
        while i < len(chars) and attrs[i] == attr:
            run.append(chars[i])
            i += 1
        screen.text(y, x + start, "".join(run), attr)


def phase_card(screen: Screen, name: str, tagline: str,
               body: list[str]) -> str:
    title = Decrypt(f"-- {name} --", stagger=0.03, churn=0.25)
    typer = Typewriter(tagline, cps=200)
    body_at = title.duration + typer.duration + 0.15
    duration = body_at + 0.25

    def draw(scr: Screen, elapsed: float) -> None:
        width = min(62, scr.w - 6)
        x = max(2, (scr.w - width) // 2)
        top = max(2, scr.h // 2 - (len(body) + 6) // 2)
        _decrypted(scr, top, x, title, elapsed, P_AMBER)
        scr.text(top + 2, x, typer.visible(elapsed - title.duration),
                 curses.color_pair(P_WHITE) | curses.A_BOLD)
        if elapsed >= body_at:
            for k, line in enumerate(body):
                scr.text(top + 4 + k, x, line, curses.color_pair(P_GREY))
        scr.center(scr.h - 2, "any key to begin   ·   esc to leave",
                   curses.color_pair(P_GREY))

    return _await_key_animated(screen, draw, duration)


def _decrypted(screen: Screen, y: int, x: int, effect: Decrypt, elapsed: float,
               pair: int) -> None:
    """Draw a Decrypt effect on one line, in the given colour once settled."""
    chars, attrs = [], []
    for i in range(len(effect.text)):
        glyph, tier = effect.state(i, elapsed)
        chars.append(glyph)
        attrs.append(curses.color_pair(P_DIM) if tier == SCRAMBLING
                     else curses.color_pair(P_WHITE) | curses.A_BOLD
                     if tier == FLASH
                     else curses.color_pair(pair) | curses.A_BOLD)
    _runs(screen, y, x, chars, attrs)


def lesson_card(screen: Screen, step) -> str:
    lesson = step.lesson
    title = Decrypt(lesson.name, stagger=0.035, churn=0.3)
    rest_at = title.duration + 0.1
    duration = rest_at + 0.3

    def draw(scr: Screen, elapsed: float) -> None:
        width = min(62, scr.w - 6)
        x = max(2, (scr.w - width) // 2)
        top = max(2, scr.h // 2 - 8)
        scr.text(top, x, f"LESSON {step.index} / {len(shell.LESSONS)}",
                 curses.color_pair(P_GREY))
        _decrypted(scr, top + 2, x, title, elapsed, P_HI)
        if elapsed < rest_at:
            scr.center(scr.h - 2, "any key to skip ahead",
                       curses.color_pair(P_DIM))
            return
        for k, line in enumerate(wrap(lesson.blurb, width)):
            scr.text(top + 3 + k, x, line, curses.color_pair(P_CYAN))
        y = top + 5
        scr.text(y, x, "tools: " + "  ".join(lesson.tools),
                 curses.color_pair(P_GREEN))
        scr.text(y + 2, x, "problem  ->  breakdown  ->  type it  ->  recall",
                 curses.color_pair(P_WHITE))
        scr.text(y + 3, x, "then one timed challenge at the end",
                 curses.color_pair(P_WHITE))
        scr.text(y + 5, x, "Only the challenge is timed.",
                 curses.color_pair(P_DIM))
        remark = akari.lesson_remark(step.key)
        if remark:
            _akari_line(scr, y + 6, x, remark)
        if step.modifier:
            scr.text(y + 8, x, f"challenge modifier: {step.modifier.name} -- "
                               f"{step.modifier.blurb}",
                     curses.color_pair(P_RED))
        scr.center(scr.h - 2, "any key to begin   ·   esc to leave",
                   curses.color_pair(P_GREY))

    return _await_key_animated(screen, draw, duration)


def lesson_result(screen: Screen, session: TypingSession, step, outcome: str,
                  cleared: bool, hinted: int = 0,
                  rng: random.Random | None = None) -> None:
    m = session.metrics(time.monotonic())
    remark_body = akari.result_remark(cleared, outcome == "done", rng or random)
    remark = akari.say(screen.g.unicode, remark_body)

    def draw(scr: Screen, _e: float) -> None:
        y = max(1, scr.h // 2 - 5)
        clear_box(scr, y - 1, y + 10, 62)
        if cleared:
            scr.center(y, "  LESSON CLEARED  ",
                       curses.color_pair(P_SEL) | curses.A_BOLD)
        elif outcome == "done":
            scr.center(y, "  FINISHED -- BUT NOT CLEAN ENOUGH  ",
                       curses.color_pair(P_AMBER) | curses.A_BOLD)
        else:
            scr.center(y, "  TRACE COMPLETE -- CONNECTION SEVERED  ",
                       curses.color_pair(P_ALERT) | curses.A_BOLD)
        scr.center(y + 2, f"{m.net_wpm:.1f} wpm   {m.accuracy:.1%} accuracy"
                          f"   {m.errors} errors",
                   curses.color_pair(P_WHITE) | curses.A_BOLD)
        if not cleared:
            if outcome == "done":
                scr.center(y + 3,
                           f"clearing needs {CLEAR_ACCURACY:.0%} accuracy",
                           curses.color_pair(P_AMBER))
            else:
                scr.center(y + 3, f"you needed {step.target_wpm:.0f} wpm clean",
                           curses.color_pair(P_AMBER))
        _akari_line(scr, y + 5, max(2, (scr.w - display_width(remark)) // 2),
                    remark_body)
        if hinted:
            scr.center(y + 7, f"{hinted} command(s) revealed during recall",
                       curses.color_pair(P_DIM))
        scr.center(y + 8, "tools: " + "  ".join(step.lesson.tools[:6]),
                   curses.color_pair(P_DIM))
        scr.center(scr.h - 2, "any key to continue", curses.color_pair(P_GREY))

    wait_screen(screen, draw, lockout=DISMISS_LOCKOUT)


def codex(screen: Screen, profile: Profile) -> None:
    """Every tool in the library, what it does, and how cleanly you type it."""
    rows = []
    for tool in shell.ALL_TOOLS:
        stat = profile.tools.get(tool)
        rows.append((tool, shell.TOOL_SUMMARY.get(tool, ""), stat))
    # Tools you've met come first, worst accuracy at the top.
    rows.sort(key=lambda r: (r[2] is None,
                             r[2].error_rate * -1 if r[2] else 0, r[0]))

    idx = 0
    clock = Clock()
    screen.win.timeout(int(FRAME * 1000))
    while True:
        clock.tick()
        screen.sync()
        room = max(3, screen.h - 7)
        for k in screen.keys():
            if k in UP_KEYS:
                idx = max(0, idx - 1)
            elif k in DOWN_KEYS:
                idx = min(len(rows) - 1, idx + 1)
            elif k == curses.KEY_NPAGE:
                idx = min(len(rows) - 1, idx + room)
            elif k == curses.KEY_PPAGE:
                idx = max(0, idx - room)
            elif k in ENTER_KEYS or k in QUIT_KEYS:
                return

        screen.erase()
        x = max(2, (screen.w - 70) // 2)
        met = sum(1 for _, _, st in rows if st)
        screen.text(1, x, "CODEX", curses.color_pair(P_WHITE) | curses.A_BOLD)
        screen.text(1, x + 8, f"{met}/{len(rows)} tools practised",
                    curses.color_pair(P_AMBER))
        first = max(0, min(idx - room // 2, len(rows) - room))
        for r, (tool, summary, stat) in enumerate(rows[first:first + room]):
            y = 3 + r
            sel = first + r == idx
            attr = (curses.color_pair(P_SEL) | curses.A_BOLD if sel
                    else curses.color_pair(P_HI if stat else P_DIM))
            screen.text(y, x, tool.ljust(11), attr)
            screen.text(y, x + 12, summary[:44],
                        curses.color_pair(P_GREEN if stat else P_DIM))
            if stat and stat.attempts:
                acc = 1.0 - stat.error_rate
                pair = P_HI if acc >= 0.97 else P_AMBER if acc >= 0.92 else P_RED
                screen.text(y, x + 58, f"{acc:5.1%}", curses.color_pair(pair))
        screen.center(screen.h - 2,
                      "arrows scroll   pgup/pgdn page   q back",
                      curses.color_pair(P_GREY))
        screen.present()


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


def record(profile: Profile, session: TypingSession, mode: str) -> bool:
    """Fold a run into the profile. Runs where nothing was typed are noise."""
    if session.started is None or len(session.keystrokes) < 10:
        return False
    profile.record(mode, session.metrics(time.monotonic()), session.key_stats())
    profile.save()
    return True


def finish(screen: Screen, profile: Profile, session: TypingSession,
           ctx: RunContext, mode: str) -> None:
    if ctx.outcome == "abort" and session.started is None:
        return
    previous_best = profile.best_wpm(mode)
    previous_avg = profile.average_wpm()
    if not record(profile, session, mode):
        return
    results(screen, session, mode, previous_best, previous_avg)


def results(screen: Screen, session: TypingSession, mode: str,
            previous_best: float, previous_avg: float) -> None:
    m = session.metrics(time.monotonic())
    worst = session.worst_keys(6)
    stats = session.key_stats()
    is_best = m.net_wpm > previous_best

    def draw(scr: Screen, _e: float) -> None:
        top = max(1, scr.h // 2 - 9)
        x = max(2, (scr.w - 56) // 2)

        scr.center(top, f"-- {mode.upper()} COMPLETE --", curses.color_pair(P_GREY))
        big = f"{m.net_wpm:.1f}"
        scr.center(top + 2, big + " WPM",
                   curses.color_pair(P_HI) | curses.A_BOLD)
        if is_best:
            scr.center(top + 3, "NEW PERSONAL BEST",
                       curses.color_pair(P_AMBER) | curses.A_BOLD)
        elif previous_best:
            delta = m.net_wpm - previous_best
            scr.center(top + 3, f"personal best {previous_best:.1f} "
                                f"({delta:+.1f})", curses.color_pair(P_DIM))

        rows = [
            ("accuracy", f"{m.accuracy:.1%}",
             P_HI if m.accuracy >= 0.97 else P_AMBER if m.accuracy >= 0.93 else P_RED),
            ("raw wpm", f"{m.raw_wpm:.1f}", P_GREEN),
            ("consistency", f"{m.consistency:.0%}", P_GREEN),
            ("errors", str(m.errors), P_RED if m.errors else P_GREEN),
            ("keystrokes", str(m.keystrokes), P_GREY),
            ("time", f"{m.elapsed:.1f}s", P_GREY),
        ]
        for i, (label, value, pair) in enumerate(rows):
            y = top + 5 + i
            scr.text(y, x, label.rjust(12), curses.color_pair(P_GREY))
            scr.text(y, x + 14, value, curses.color_pair(pair) | curses.A_BOLD)

        if previous_avg:
            scr.text(top + 5 + len(rows) + 1, x,
                     f"recent average {previous_avg:.1f} wpm",
                     curses.color_pair(P_DIM))

        y = top + 5 + len(rows) + 3
        if worst:
            scr.text(y, x, "weakest keys this run",
                     curses.color_pair(P_AMBER) | curses.A_BOLD)
            parts = [f"{_display(ch)} {stats[ch].error_rate:.0%}" for ch in worst]
            scr.text(y + 1, x, "   ".join(parts), curses.color_pair(P_RED))
        elif m.keystrokes:
            scr.text(y, x, "clean run -- no mistakes",
                     curses.color_pair(P_HI) | curses.A_BOLD)

        scr.center(scr.h - 2, "any key to continue", curses.color_pair(P_GREY))

    wait_screen(screen, draw, lockout=DISMISS_LOCKOUT)


def _display(ch: str) -> str:
    return "space" if ch == " " else ch


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------


def stats_screen(screen: Screen, profile: Profile) -> None:
    runs = profile.recent(40)
    keys = [(c, s) for c, s in profile.keys.items()
            if s.attempts >= 8 and not c.isspace()]
    keys.sort(key=lambda cs: (-cs[1].error_rate, -cs[1].mean_latency))
    total_ks = sum(s.attempts for s in profile.keys.values())

    def draw(scr: Screen, _e: float) -> None:
        x = max(2, (scr.w - 62) // 2)
        y = 2
        scr.text(y, x, "YOUR PROFILE", curses.color_pair(P_WHITE) | curses.A_BOLD)

        if not runs:
            scr.text(y + 2, x, "No runs recorded yet. Go type something.",
                     curses.color_pair(P_AMBER))
            scr.center(scr.h - 2, "any key to return", curses.color_pair(P_GREY))
            return

        best = profile.best_wpm()
        avg = profile.average_wpm(10)
        scr.text(y + 2, x, f"best {best:5.1f} wpm     "
                           f"last-10 average {avg:5.1f} wpm     "
                           f"{total_ks} keystrokes logged",
                 curses.color_pair(P_GREEN))

        # WPM sparkline over recent runs
        scr.text(y + 4, x, "wpm over last {} runs".format(len(runs)),
                 curses.color_pair(P_GREY))
        scr.text(y + 5, x, sparkline(scr, [r.wpm for r in runs]),
                 curses.color_pair(P_HI) | curses.A_BOLD)
        lo = min(r.wpm for r in runs)
        hi = max(r.wpm for r in runs)
        scr.text(y + 6, x, f"{lo:.0f}".ljust(len(runs)) , curses.color_pair(P_DIM))
        scr.text(y + 6, x + max(0, len(runs) - 4), f"{hi:.0f}",
                 curses.color_pair(P_DIM))

        scr.text(y + 8, x, "WEAKEST KEYS", curses.color_pair(P_AMBER) | curses.A_BOLD)
        scr.text(y + 9, x, "key   accuracy            errors  avg delay",
                 curses.color_pair(P_GREY))
        room = max(0, scr.h - (y + 11) - 3)
        for i, (ch, s) in enumerate(keys[:min(10, room)]):
            row = y + 10 + i
            acc = 1.0 - s.error_rate
            pair = P_HI if acc >= 0.98 else P_AMBER if acc >= 0.94 else P_RED
            scr.text(row, x, _display(ch).ljust(6),
                     curses.color_pair(P_WHITE) | curses.A_BOLD)
            bar(scr, row, x + 6, 12, acc, curses.color_pair(pair))
            scr.text(row, x + 22, f"{acc:5.1%}", curses.color_pair(pair))
            scr.text(row, x + 30, f"{s.errors}/{s.attempts}".rjust(8),
                     curses.color_pair(P_GREY))
            scr.text(row, x + 40, f"{s.mean_latency * 1000:5.0f} ms",
                     curses.color_pair(P_CYAN))

        if not keys:
            scr.text(y + 10, x, "not enough data per key yet -- keep typing",
                     curses.color_pair(P_DIM))
        scr.center(scr.h - 2, "any key to return", curses.color_pair(P_GREY))

    wait_screen(screen, draw)


def sparkline(screen: Screen, values: list[float]) -> str:
    if not values:
        return ""
    if not screen.g.unicode:
        return "".join("#" if v >= sum(values) / len(values) else "." for v in values)
    lo, hi = min(values), max(values)
    span = hi - lo
    if span <= 0:
        return SPARK[len(SPARK) // 2] * len(values)
    return "".join(SPARK[min(len(SPARK) - 1,
                             int((v - lo) / span * (len(SPARK) - 1)))]
                   for v in values)


# --------------------------------------------------------------------------
# WATCH -- observe an expert working a shell
# --------------------------------------------------------------------------

# A skilled typist, not a machine: fast, but with rhythm.
WATCH_CPS = (17.0, 26.0)        # characters per second, per command
THINK_BEFORE = (0.35, 1.3)      # pause before starting to type
RUN_DELAY = (0.12, 0.5)         # command submitted -> output appears
OUTPUT_LINE = 0.035             # output streams in rather than snapping on
TYPO_CHANCE = 0.05              # even experts fumble, and fix it instantly
# How long the finished scene stays on screen before it's cleared. The last
# command lands, its output arrives, and then you need time to actually read
# the whole thing -- so this is deliberately much longer than any beat pause.
SCENE_HOLD = 7.0


class _Typist:
    """Types one command, with human timing: variable speed, a beat at pipes
    and quotes, and the occasional instantly-corrected slip."""

    def __init__(self, text: str, rng: random.Random):
        self.text = text
        self.rng = rng
        self.cps = rng.uniform(*WATCH_CPS)
        self.think = rng.uniform(*THINK_BEFORE)
        # (elapsed, text-on-screen) keyframes, precomputed so rendering is a
        # lookup rather than a simulation that could drift between frames.
        self.frames: list[tuple[float, str]] = []
        t = self.think
        shown = ""
        for ch in text:
            step = 1.0 / self.cps * rng.uniform(0.55, 1.5)
            if ch in "|'\"$(":          # a beat at the tricky bits
                step += rng.uniform(0.04, 0.16)
            if ch == " ":
                step *= 0.7
            t += step
            if rng.random() < TYPO_CHANCE and ch.isalnum():
                wrong = rng.choice("asdfghjkl")
                self.frames.append((t, shown + wrong))
                t += rng.uniform(0.10, 0.22)
                self.frames.append((t, shown))      # backspace
                t += rng.uniform(0.05, 0.12)
            shown += ch
            self.frames.append((t, shown))
        self.duration = t + rng.uniform(0.10, 0.35)   # beat before Enter

    def visible(self, elapsed: float) -> str:
        shown = ""
        for at, text in self.frames:
            if elapsed < at:
                break
            shown = text
        return shown


def watch_screen(screen: Screen, rng: random.Random) -> None:
    """An endless, self-driving shell session. Nothing to do but watch."""
    beats = shell_stream(rng)
    lines: list[tuple[str, int, str]] = []   # (text, colour, kind)
    clock = Clock()
    screen.win.timeout(int(FRAME * 1000))

    beat = next(beats)
    typist = _Typist(beat.command, rng)
    state, elapsed, shown_lines = "type", 0.0, 0
    paused = False
    session = _hex_session(rng)
    if beat.comment:
        lines.append((f"# {beat.comment}", P_CYAN, "note"))

    while True:
        dt = clock.tick()
        screen.sync()
        for key in screen.keys():
            if key in QUIT_KEYS:
                return
            paused = not paused
        if not paused:
            elapsed += dt

        body = max(4, screen.h - 4)
        width = max(20, screen.w - 4)

        if state == "type" and elapsed >= typist.duration:
            lines.append((f"{beat.prompt}$ {beat.command}", P_WHITE, "cmd"))
            state, elapsed, shown_lines = "run", 0.0, 0
        elif state == "run" and elapsed >= rng.uniform(*RUN_DELAY):
            state, elapsed = "output", 0.0
        elif state == "output":
            want = min(len(beat.output), int(elapsed / OUTPUT_LINE) + 1)
            while shown_lines < want:
                pair = P_RED if beat.failed else P_DIM
                lines.append((beat.output[shown_lines], pair, "out"))
                shown_lines += 1
            if shown_lines >= len(beat.output):
                if beat.mutter:
                    lines.append((_mutter_text(screen, beat.mutter),
                                  P_AMBER, "note"))
                state, elapsed = "settle", 0.0
        elif state == "settle" and elapsed >= beat.pause:
            upcoming = next(beats)
            if upcoming is None:
                # Scene boundary. Hold the finished session on screen long
                # enough to read it before wiping it.
                state, elapsed = "hold", 0.0
            else:
                beat = upcoming
                if beat.comment:
                    lines.append(("", P_DIM, "out"))
                    lines.append((f"# {beat.comment}", P_CYAN, "note"))
                typist = _Typist(beat.command, rng)
                state, elapsed, shown_lines = "type", 0.0, 0
        elif state == "hold" and elapsed >= SCENE_HOLD:
            lines.clear()
            session = _hex_session(rng)
            beat = next(beats)
            if beat.comment:
                lines.append((f"# {beat.comment}", P_CYAN, "note"))
            typist = _Typist(beat.command, rng)
            state, elapsed, shown_lines = "type", 0.0, 0

        del lines[:-body]

        # The line currently being typed is part of the scrollback for layout
        # purposes, so a long command pushes history up exactly as it would
        # in a real terminal.
        live = None
        if state == "type":
            live = (f"{beat.prompt}$ {typist.visible(elapsed)}", P_WHITE, "cmd")

        rows: list[tuple[str, int, bool]] = []
        for entry in lines + ([live] if live else []):
            rows.extend(_wrap_row(entry, width))
        rows = rows[-body:]

        remaining = SCENE_HOLD - elapsed if state == "hold" else None
        screen.erase()
        _watch_chrome(screen, session, paused, remaining)
        for i, (text, pair, cont) in enumerate(rows):
            _watch_line(screen, 2 + i, text, pair, cont)
        if live and rows:
            y = 2 + len(rows) - 1
            if y < screen.h - 2:
                screen.text(y, 2 + len(rows[-1][0]), " ",
                            curses.color_pair(P_SEL) | curses.A_BOLD)
        screen.present()


def _wrap_row(entry, width: int) -> list[tuple[str, int, bool]]:
    """Split one logical line into physical rows, flagging continuations so
    only the first one gets prompt colouring. Measured in columns, so a line
    containing kana wraps where it actually reaches the edge."""
    text, pair, kind = entry
    colour = pair if kind != "cmd" else P_WHITE
    if display_width(text) <= width:
        return [(text, colour, kind != "cmd")]
    out, rest, first = [], text, True
    while rest:
        chunk = clip_to_width(rest, width)
        if not chunk:
            break
        out.append((chunk, colour, kind != "cmd" or not first))
        rest, first = rest[len(chunk):], False
    return out


def _hex_session(rng: random.Random) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(6))


def _akari_line(screen: Screen, y: int, x: int, remark: str) -> None:
    """Her name in bold, then what she said -- drawn separately so the gap
    survives (word-wrapping would collapse it) and the name can carry weight."""
    sig = akari.signature(screen.g.unicode)
    screen.text(y, x, sig, curses.color_pair(P_AMBER) | curses.A_BOLD)
    screen.text(y, x + display_width(sig) + 2, remark,
                curses.color_pair(P_AMBER))


def _mutter_text(screen: Screen, mutter: tuple[str, str]) -> str:
    """Her note, in Japanese where the terminal can render it."""
    kana, gloss = mutter
    if screen.g.unicode:
        return f"# {kana}   {gloss}"
    return f"# {gloss}"


def _watch_line(screen: Screen, y: int, text: str, pair: int,
                plain: bool = False) -> None:
    """Draw one terminal line, colouring the prompt separately from what was
    typed -- which is what makes it read as a shell rather than a log."""
    if not plain and "$ " in text:
        prompt, _, rest = text.partition("$ ")
        screen.text(y, 2, prompt, curses.color_pair(P_HI))
        screen.text(y, 2 + len(prompt), "$ ", curses.color_pair(P_GREY))
        screen.text(y, 2 + len(prompt) + 2, rest,
                    curses.color_pair(P_WHITE) | curses.A_BOLD)
    else:
        attr = curses.color_pair(pair)
        if pair == P_CYAN:
            attr |= curses.A_BOLD
        screen.text(y, 2, text, attr)


def _watch_chrome(screen: Screen, session: str, paused: bool,
                  remaining: float | None = None) -> None:
    who = (f"{watch.OPERATOR_KANA} / {watch.OPERATOR}" if screen.g.unicode
           else watch.OPERATOR.capitalize())
    head = f"OBSERVING :: {who} :: session {session}"
    screen.text(0, 2, head, curses.color_pair(P_GREY))
    # Width, not length: her name is double-width.
    tail = 2 + display_width(head) + 3
    if paused:
        screen.text(0, tail, "[PAUSED]",
                    curses.color_pair(P_AMBER) | curses.A_BOLD)
    elif remaining is not None:
        screen.text(0, tail, f"[session closed -- next in {remaining:.0f}s]",
                    curses.color_pair(P_CYAN))
    hint = "q to leave   ·   any other key pauses"
    screen.text(screen.h - 1, 2, hint, curses.color_pair(P_DIM))
