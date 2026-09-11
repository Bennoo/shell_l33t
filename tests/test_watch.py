import random
import re

import pytest

from l33t import watch
from l33t.watch import MAX_WIDTH, SCENES, Beat, make_scene, stream

SEEDS = list(range(60))

# Every command a scene runs must be a real tool, not invented flavour.
KNOWN = {
    "df", "du", "find", "ls", "cat", "head", "tail", "wc", "stat", "grep",
    "awk", "sed", "cut", "sort", "uniq", "curl", "ss", "journalctl", "ps",
    "kill", "systemctl", "lsof", "make", "git", "rsync", "ssh", "scp", "dig",
    "nc", "openssl", "chmod", "chown", "zcat", "nginx", "echo", "sleep",
    "tar", "split", "xargs", "jq", "printf", "nohup", "timeout", "pgrep",
}


def all_beats(seeds=SEEDS):
    for seed in seeds:
        yield from make_scene(random.Random(seed))


def test_every_scene_produces_a_coherent_run():
    for seed in SEEDS:
        beats = make_scene(random.Random(seed))
        assert len(beats) >= 3, "a scene should read as an investigation"
        assert all(isinstance(b, Beat) for b in beats)
        assert all(b.command.strip() for b in beats)
        # One prompt per scene unless the operator changes directory.
        assert len({b.prompt for b in beats}) <= 2


def test_every_command_starts_with_a_real_tool():
    for beat in all_beats():
        first = beat.command.split()[0]
        first = first.split("=")[0] if "=" in first else first
        assert first in KNOWN, (first, beat.command)


def test_nothing_overflows_the_terminal():
    for beat in all_beats():
        assert len(beat.command) <= MAX_WIDTH, beat.command
        for line in beat.output:
            assert len(line) <= MAX_WIDTH, line


# Braces are legitimate shell ({} for find -exec, %{http_code} for curl), so
# look for the actual tells of a Python f-string that didn't get formatted.
LEAKS = re.compile(r"\{(rng|ctx|self|_|beat)\b|\bNone\b|\{\w+!r\}")


def test_no_unformatted_placeholders_leak_through():
    for beat in all_beats():
        for line in (beat.command, *beat.output):
            assert not LEAKS.search(line), line


def test_prompts_look_like_prompts():
    for beat in all_beats():
        assert re.fullmatch(r"[\w.-]+@[\w.-]+:\S+", beat.prompt), beat.prompt


# -- output has to actually match the command ------------------------------


def test_head_never_returns_more_lines_than_asked_for():
    for beat in all_beats():
        m = re.search(r"\|\s*head -(\d+)\s*$", beat.command)
        if m:
            assert len(beat.output) <= int(m.group(1)), beat.command


def test_counting_commands_return_a_single_number():
    """wc -l and grep -c print one integer. Anything else is a tell."""
    for beat in all_beats():
        cmd = beat.command
        if re.search(r"(wc -l|grep -c|\| wc -l)\s*$", cmd) and beat.output:
            assert len(beat.output) == 1, cmd
            assert beat.output[0].strip().isdigit(), (cmd, beat.output)


def test_status_code_probes_print_a_status_code():
    for beat in all_beats():
        if "%{http_code}" in beat.command and beat.output:
            assert len(beat.output) == 1
            code = beat.output[0].strip()
            assert code.isdigit() and len(code) == 3, code
            # 000 is curl's "no response", and must be marked as a failure.
            assert beat.failed == (code == "000"), (code, beat.failed)


def test_uniq_c_output_is_count_then_value_descending():
    for beat in all_beats():
        if "uniq -c | sort -rn" in beat.command and beat.output:
            counts = []
            for line in beat.output:
                parts = line.split()
                assert parts[0].isdigit(), line
                counts.append(int(parts[0]))
            assert counts == sorted(counts, reverse=True), beat.command


def test_du_sort_rh_output_is_largest_first():
    for beat in all_beats():
        if beat.command.startswith("du -sh"):
            def as_bytes(line):
                size = line.split("\t")[0]
                mult = {"K": 1e3, "M": 1e6, "G": 1e9}[size[-1]]
                return float(size[:-1]) * mult
            sizes = [as_bytes(l) for l in beat.output]
            assert sizes == sorted(sizes, reverse=True), beat.output


def test_successful_commands_are_not_marked_failed():
    for beat in all_beats():
        if beat.output and any("succeeded" in o or "successful" in o
                               for o in beat.output):
            assert not beat.failed, beat.command


# -- variety ---------------------------------------------------------------


def test_scenes_differ_between_runs():
    """Two viewings must not look the same."""
    a = [b.command for b in make_scene(random.Random(1))]
    b = [b.command for b in make_scene(random.Random(2))]
    c = [b.command for b in make_scene(random.Random(1))]
    assert a == c, "same seed should reproduce"
    assert a != b


def test_the_same_scene_twice_still_varies_in_detail():
    """Even replaying one scene, the values must be freshly generated."""
    from l33t.watch import make_context, scene_disk_full
    one = scene_disk_full(make_context(random.Random(11)))
    two = scene_disk_full(make_context(random.Random(12)))
    assert [b.command for b in one] != [b.command for b in two] or \
           [b.output for b in one] != [b.output for b in two]


def test_stream_is_endless_and_marks_scene_boundaries():
    rng = random.Random(5)
    got = [next(s) for s in [stream(rng)] * 1 for _ in range(400)]
    assert len(got) == 400
    assert any(b is None for b in got), "no scene boundary emitted"
    assert all(b is None or b.command for b in got)


def test_stream_never_repeats_a_scene_back_to_back():
    """Back-to-back repeats are exactly what makes a screensaver feel canned."""
    rng = random.Random(9)
    gen = stream(rng)
    scenes, current = [], []
    for _ in range(600):
        beat = next(gen)
        if beat is None:
            if current:
                scenes.append(tuple(current))
            current = []
        else:
            current.append(beat.command.split()[0])
    assert len(scenes) >= 4
    for a, b in zip(scenes, scenes[1:]):
        assert a != b, "the same scene ran twice in a row"


def test_all_scenes_are_reachable():
    rng = random.Random(3)
    gen = stream(rng)
    seen = set()
    for _ in range(4000):
        beat = next(gen)
        if beat is not None:
            seen.add(beat.command.split()[0])
    assert len(seen) >= 15, seen


# -- the typist ------------------------------------------------------------


def test_typist_always_ends_on_the_exact_command():
    """A simulated typo must always get corrected. Leaving a wrong character
    in the final command would be showing the viewer a broken command."""
    from l33t.screens import _Typist
    for seed in range(200):
        rng = random.Random(seed)
        cmd = rng.choice([b.command for b in make_scene(random.Random(seed))])
        t = _Typist(cmd, rng)
        assert t.visible(t.duration) == cmd, cmd
        assert t.visible(t.duration + 60) == cmd


def test_typist_only_ever_shows_a_prefix_or_a_single_slip():
    from l33t.screens import _Typist
    rng = random.Random(7)
    cmd = "grep -rn --include='*.go' 'TODO' ."
    t = _Typist(cmd, rng)
    e = 0.0
    while e <= t.duration:
        shown = t.visible(e)
        if not cmd.startswith(shown):
            # the only allowed deviation is one wrong trailing character
            assert cmd.startswith(shown[:-1]), shown
            assert len(shown) <= len(cmd), shown
        e += 1 / 60


def test_typist_starts_empty_and_pauses_before_typing():
    from l33t.screens import _Typist
    t = _Typist("ls -lah", random.Random(1))
    assert t.visible(0.0) == ""
    assert t.think > 0

def test_typist_is_not_instantaneous():
    """It should read as someone typing, not as text appearing."""
    from l33t.screens import _Typist
    cmd = "du -sh * | sort -rh | head -10"
    t = _Typist(cmd, random.Random(3))
    typing = t.duration - t.think
    cps = len(cmd) / typing
    assert 8 < cps < 40, cps


def test_wrap_row_splits_long_lines_and_marks_continuations():
    from l33t.screens import _wrap_row
    from l33t.ui import P_WHITE
    long = "x" * 50
    rows = _wrap_row((f"me@host:~$ {long}", P_WHITE, "cmd"), 20)
    assert len("".join(r[0] for r in rows)) == len(f"me@host:~$ {long}")
    assert rows[0][2] is False, "first row carries the prompt"
    assert all(r[2] for r in rows[1:]), "continuations must not re-colour"


def test_wrap_row_leaves_short_lines_alone():
    from l33t.screens import _wrap_row
    from l33t.ui import P_DIM
    rows = _wrap_row(("total 4", P_DIM, "out"), 40)
    assert rows == [("total 4", P_DIM, True)]


# -- Akari -----------------------------------------------------------------


def test_the_operator_is_always_akari():
    for beat in all_beats():
        user = beat.prompt.split("@")[0]
        assert user == watch.OPERATOR == "akari", beat.prompt


def test_her_shell_account_stays_ascii():
    """Unix usernames are ASCII; the kana belongs in the chrome, not in a
    prompt or a stat(1) line."""
    assert watch.OPERATOR.isascii()
    for beat in all_beats():
        assert beat.prompt.isascii(), beat.prompt
        assert beat.command.isascii(), beat.command
        for line in beat.output:
            assert line.isascii(), line


def test_her_name_renders_as_kana():
    assert watch.OPERATOR_KANA == "あかり"
    assert not watch.OPERATOR_KANA.isascii()


def test_mutterings_are_short_and_glossed():
    from l33t.ui import display_width
    for kana, gloss in watch.MUTTERINGS:
        assert kana and gloss
        assert not kana.isascii(), kana
        assert gloss.isascii(), gloss
        assert display_width(kana) <= 10, kana      # a note, not a speech


def test_a_reaction_only_lands_where_there_is_something_to_react_to():
    """"found it" above a command that printed nothing breaks the illusion."""
    for seed in SEEDS:
        beats = make_scene(random.Random(seed))
        for i, beat in enumerate(beats):
            if beat.mutter and i != len(beats) - 1:
                assert beat.output, beat.command


def test_failures_get_a_failure_shaped_reaction():
    for beat in all_beats():
        if beat.mutter and beat.failed and beat is not None:
            assert beat.mutter in watch.SURPRISE, (beat.command, beat.mutter)


def test_a_scene_closes_on_a_closing_note():
    for seed in SEEDS:
        beats = make_scene(random.Random(seed))
        assert beats[-1].mutter in watch.CLOSING, beats[-1].command


def test_the_first_beat_never_reacts():
    """She has nothing to react to before running anything."""
    for seed in SEEDS:
        assert not make_scene(random.Random(seed))[0].mutter


def test_hosts_have_japanese_flavour():
    assert any("shibuya" in h or "kyoto" in h or "tokyo" in h
               for h in watch.HOSTS)
    assert all(h.isascii() for h in watch.HOSTS)


def test_rendered_mutter_fits_a_narrow_terminal():
    from l33t.ui import display_width
    for kana, gloss in watch.MUTTERINGS:
        line = f"# {kana}   {gloss}"
        assert display_width(line) <= 40, line


# -- Akari's presence in the lessons ---------------------------------------


def test_every_lesson_has_a_remark_from_her():
    from l33t import akari
    from l33t import shell as sh
    for lesson in sh.LESSONS:
        assert akari.lesson_remark(lesson.key), lesson.key


def test_no_remark_is_keyed_to_a_lesson_that_does_not_exist():
    from l33t import akari
    from l33t import shell as sh
    keys = {l.key for l in sh.LESSONS}
    assert set(akari.LESSON_REMARKS) - keys == set()


def test_her_lines_fit_a_narrow_panel():
    from l33t import akari
    from l33t.ui import display_width
    lines = (list(akari.LESSON_REMARKS.values()) + akari.MENU_UNSTARTED
             + akari.MENU_PARTWAY + akari.MENU_DONE + akari.CLEARED
             + akari.NOT_CLEAN + akari.TRACED)
    for line in lines:
        assert display_width(akari.say(True, line)) <= 68, line
        assert display_width(akari.say(False, line)) <= 68, line


def test_menu_line_matches_progress():
    from l33t import akari
    rng = random.Random(0)
    assert akari.menu_line(0, 11, rng) in akari.MENU_UNSTARTED
    assert akari.menu_line(5, 11, rng) in akari.MENU_PARTWAY
    assert akari.menu_line(11, 11, rng) in akari.MENU_DONE
    assert akari.menu_line(99, 11, rng) in akari.MENU_DONE


def test_result_remark_matches_the_outcome():
    from l33t import akari
    rng = random.Random(0)
    assert akari.result_remark(True, True, rng) in akari.CLEARED
    assert akari.result_remark(False, True, rng) in akari.NOT_CLEAN
    assert akari.result_remark(False, False, rng) in akari.TRACED


def test_she_is_labelled_consistently_everywhere():
    from l33t import akari
    assert akari.signature(True) == "あかり"
    assert akari.signature(False) == "Akari"
    assert akari.say(True, "x").startswith("あかり")
    assert akari.say(False, "x").isascii()


def test_watch_and_lessons_share_one_persona():
    """Two sources of truth for her name is how she ends up called something
    different on two screens."""
    from l33t import akari
    assert watch.OPERATOR is akari.NAME
    assert watch.OPERATOR_KANA is akari.KANA


def test_a_finished_scene_is_held_long_enough_to_read():
    """The last command's output has to stay up long enough to actually read
    before the screen is wiped for the next scene."""
    from l33t.screens import SCENE_HOLD
    longest_pause = max(b.pause for b in all_beats())
    assert SCENE_HOLD >= 5.0
    assert SCENE_HOLD > longest_pause * 3
