"""あかり (Akari) -- the operator whose shell you're learning.

She runs the WATCH session, and turns up through the lessons as a short line
of commentary. Terse and practical: she's been doing this a long time and
isn't impressed by speed on its own.

All her copy lives here so the persona stays consistent and is easy to edit
in one place.
"""

from __future__ import annotations

import random

NAME = "akari"          # her shell account -- ASCII, like any Unix account
KANA = "あかり"          # her name, for the chrome


def signature(unicode_ok: bool) -> str:
    """How she's labelled on screen."""
    return KANA if unicode_ok else NAME.capitalize()


def say(unicode_ok: bool, line: str) -> str:
    return f"{signature(unicode_ok)}  {line}"


# -- main menu -------------------------------------------------------------

MENU_UNSTARTED = [
    "eleven lessons. take them in order, they build.",
    "you'll type these until your hands know them.",
    "start at the top. the shell is small once you know it.",
]
MENU_PARTWAY = [
    "keep going. the middle lessons are the useful ones.",
    "go back over cleared ones. speed comes from repetition.",
    "you're past the easy part.",
]
MENU_DONE = [
    "all eleven. now make them fast.",
    "you know them. drill the keys you still fumble.",
    "nothing left to teach you. go and break something.",
]


def menu_line(cleared: int, total: int, rng: random.Random) -> str:
    if cleared == 0:
        pool = MENU_UNSTARTED
    elif cleared >= total:
        pool = MENU_DONE
    else:
        pool = MENU_PARTWAY
    return rng.choice(pool)


# -- one remark per lesson, shown on its card ------------------------------

LESSON_REMARKS = {
    "files": "know where you are before you touch anything.",
    "inspect": "read before you write. always, on someone else's box.",
    "find": "worth it on the day you can't remember the filename.",
    "text": "this is the lesson that turns a shell into a language.",
    "pipes": "stdout and stderr are different rivers. know which.",
    "perms": "the one everybody skips. permissions bite quietly.",
    "procs": "knowing what is running is half of knowing what is wrong.",
    "net": "if it's slow, suspect DNS. if it's dead, check the port.",
    "git": "--force-with-lease. never plain --force. that's the lesson.",
    "archive": "always dry-run a --delete. I learned that one expensively.",
    "script": "set -euo pipefail on line one. every time.",
}


def lesson_remark(key: str) -> str:
    return LESSON_REMARKS.get(key, "")


# -- reactions to how a challenge went -------------------------------------

CLEARED = [
    "clean. that's the one.",
    "good hands. next.",
    "you had that from the start.",
]
NOT_CLEAN = [
    "fast, but you left blood on the floor.",
    "speed without accuracy is just noise. again, slower.",
    "you finished it. you didn't land it.",
]
TRACED = [
    "again, slower. accuracy first -- speed follows on its own.",
    "no shame. the trace wins the first time, most times.",
    "you were reading while you typed. read first, then start.",
]


def result_remark(cleared: bool, finished: bool, rng: random.Random) -> str:
    if cleared:
        return rng.choice(CLEARED)
    if finished:
        return rng.choice(NOT_CLEAN)
    return rng.choice(TRACED)
