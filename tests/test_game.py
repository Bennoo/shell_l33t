import random
import re
import string

import pytest

from l33t import shell
from l33t.engine import KeyStat, TypingSession
from l33t.modes import (
    DIFFICULTIES, LINES_PER_LESSON, MODIFIER_STEPS, MODIFIERS,
    build_path, step_payload,
)
from l33t.screens import LEARN_COMMANDS
from l33t.stats import MIN_ATTEMPTS, LessonState, Profile, profile_path

SEEDS = list(range(20))
TYPEABLE = set(string.printable) - set("\t\n\r\x0b\x0c")


# -- the command library ---------------------------------------------------


def test_every_command_is_typeable_and_fits():
    """A command you can't type, or that runs off the panel, is unplayable."""
    for cmd in shell.ALL_COMMANDS:
        assert cmd.text, "empty command"
        assert set(cmd.text) <= TYPEABLE, repr(cmd.text)
        assert len(cmd.text) <= shell.MAX_WIDTH, (len(cmd.text), cmd.text)
        assert cmd.text == cmd.text.strip()


def test_every_command_explains_itself():
    """The explanation is the teaching half; a command without one is filler."""
    for cmd in shell.ALL_COMMANDS:
        assert cmd.explain and len(cmd.explain) >= 10, cmd.text
        assert len(cmd.explain) <= 70, cmd.explain
        assert cmd.tool, cmd.text


# Command names that are also ordinary English words -- their appearance in a
# problem statement proves nothing either way.
ENGLISH_NAMES = {"file", "find", "sort", "split", "head", "tail", "cut",
                 "less", "kill", "touch", "command", "diff", "stat", "printf"}


def test_every_command_poses_a_real_problem():
    """The lesson opens with the problem, so it has to read as one."""
    for cmd in shell.ALL_COMMANDS:
        assert cmd.problem, cmd.text
        assert 25 <= len(cmd.problem) <= 140, (len(cmd.problem), cmd.text)
        name = cmd.text.split()[0]
        if name not in ENGLISH_NAMES:
            # A problem describes a situation; it must not give away the answer.
            assert name not in cmd.problem.split(), cmd.text


def test_decompositions_reassemble_into_their_command():
    """The strongest guard against a breakdown drifting away from what it
    describes: the parts must rebuild the command exactly."""
    for cmd in shell.ALL_COMMANDS:
        assert shell.reassemble(cmd) == cmd.text, cmd.text


def test_every_command_is_decomposed_meaningfully():
    for cmd in shell.ALL_COMMANDS:
        assert len(cmd.parts) >= 2, f"{cmd.text} is not broken down"
        for part in cmd.parts:
            assert part.text.strip(), cmd.text
            # Operands can be glossed in two words ("the file"); flags cannot.
            assert len(part.means) >= 4, (cmd.text, part.text)
            assert len(part.means) <= 70, part.means


def test_flags_are_actually_explained():
    """Naming a flag isn't teaching it. Anything starting with a dash has to
    say what it does -- that's the part nobody can guess."""
    for cmd in shell.ALL_COMMANDS:
        for part in cmd.parts:
            if part.text.startswith("-") and part.text != "--":
                assert len(part.means) >= 15, (cmd.text, part.text, part.means)


def test_part_fragments_appear_in_their_command():
    for cmd in shell.ALL_COMMANDS:
        for part in cmd.parts:
            assert part.text in cmd.text, (cmd.text, part.text)


def test_a_lesson_can_always_fill_a_learning_run():
    for lesson in shell.LESSONS:
        assert len(lesson.commands) >= LEARN_COMMANDS, lesson.key


def test_every_tool_has_a_codex_entry():
    """The codex must be able to describe anything the player types."""
    missing = [t for t in shell.ALL_TOOLS if t not in shell.TOOL_SUMMARY]
    assert missing == []


def test_commands_are_unique():
    texts = [c.text for c in shell.ALL_COMMANDS]
    assert len(texts) == len(set(texts))


def test_lesson_keys_are_unique_and_non_empty():
    keys = [l.key for l in shell.LESSONS]
    assert len(keys) == len(set(keys))
    for lesson in shell.LESSONS:
        assert lesson.name and lesson.blurb
        assert len(lesson.commands) >= LEARN_COMMANDS, lesson.key
        assert lesson.tools


@pytest.mark.parametrize("seed", SEEDS)
def test_lesson_sampling_avoids_repeats_until_exhausted(seed):
    lesson = shell.LESSONS[0]
    n = len(lesson.commands)
    picked = shell.lesson_commands(lesson, n, random.Random(seed))
    assert len({c.text for c in picked}) == n


@pytest.mark.parametrize("seed", SEEDS)
def test_sampling_more_than_the_lesson_holds_still_works(seed):
    lesson = shell.LESSONS[0]
    picked = shell.lesson_commands(lesson, len(lesson.commands) + 5,
                                   random.Random(seed))
    assert len(picked) == len(lesson.commands) + 5


@pytest.mark.parametrize("seed", SEEDS)
def test_library_sampling_is_distinct(seed):
    picked = shell.sample_commands(12, random.Random(seed))
    assert len({c.text for c in picked}) == 12


@pytest.mark.parametrize("seed", SEEDS)
def test_targeted_drill_really_hits_the_weak_keys(seed):
    """A targeted drill must reliably contain the keys it claims to target --
    on this run, not on average over many."""
    rng = random.Random(seed)
    weak = ["{", "}"]
    picked = shell.sample_commands(10, rng, weak=weak)
    hits = sum(1 for c in picked if set(weak) & set(c.text))
    quota = int(round(10 * shell.WEAK_SHARE))
    available = sum(1 for c in shell.ALL_COMMANDS if set(weak) & set(c.text))
    assert hits >= min(quota, available)


def test_untargeted_sampling_is_unconstrained():
    picked = shell.sample_commands(10, random.Random(0))
    assert len({c.text for c in picked}) == 10


@pytest.mark.parametrize("seed", SEEDS)
def test_symbol_drill_is_typeable(seed):
    line = shell.symbol_drill(random.Random(seed), ["|", "&"])
    assert line and set(line) <= TYPEABLE
    assert line == line.strip()


# -- the learning path -----------------------------------------------------


def test_path_is_a_stable_syllabus():
    """It's a syllabus, not a shuffle: later lessons build on earlier ones."""
    first = [s.key for s in build_path()]
    assert first == [s.key for s in build_path()]
    assert first == [l.key for l in shell.LESSONS]


def test_path_indices_and_modifiers():
    steps = build_path()
    assert [s.index for s in steps] == list(range(1, len(shell.LESSONS) + 1))
    for step in steps:
        if step.index in MODIFIER_STEPS:
            assert step.modifier is not None
            assert step.modifier.key == MODIFIER_STEPS[step.index]
        else:
            assert step.modifier is None
    mods = [s.modifier for s in steps if s.modifier]
    assert len({m.key for m in mods}) == len(mods)
    assert all(m in MODIFIERS for m in mods)


def test_early_lessons_stay_clean():
    """You can't learn a tool while fighting LOCKDOWN on lesson one."""
    for step in build_path()[:3]:
        assert step.modifier is None


def test_target_speed_increases_along_the_path():
    speeds = [s.target_wpm for s in build_path()]
    assert speeds == sorted(speeds)
    assert speeds[0] < speeds[-1]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("difficulty", sorted(DIFFICULTIES))
def test_step_budget_matches_its_target_speed(seed, difficulty):
    rng = random.Random(seed)
    for step in build_path():
        commands, seconds = step_payload(step, rng, difficulty)
        assert len(commands) == LINES_PER_LESSON
        chars = sum(len(c.text) for c in commands)
        implied = (chars / 5.0) / (seconds / 60.0)
        assert implied == pytest.approx(step.target_wpm / DIFFICULTIES[difficulty],
                                        rel=1e-6)
        assert seconds > 5.0


def test_easy_gives_more_time_than_hard():
    step = build_path()[0]
    times = {d: step_payload(step, random.Random(0), d)[1] for d in DIFFICULTIES}
    assert times["easy"] > times["normal"] > times["hard"]


@pytest.mark.parametrize("seed", SEEDS)
def test_challenge_times_exactly_what_was_taught(seed):
    """The timed challenge must test the commands the lesson just taught,
    not a fresh draw the player has never seen."""
    rng = random.Random(seed)
    for step in build_path():
        taught = shell.lesson_commands(step.lesson, LEARN_COMMANDS, rng)
        commands, seconds = step_payload(step, rng, "normal", taught)
        assert [c.text for c in commands] == [c.text for c in taught]
        chars = sum(len(c.text) for c in taught)
        assert (chars / 5.0) / (seconds / 60.0) == pytest.approx(
            step.target_wpm, rel=1e-6)


@pytest.mark.parametrize("seed", SEEDS)
def test_step_commands_come_from_their_own_lesson(seed):
    rng = random.Random(seed)
    for step in build_path():
        commands, _ = step_payload(step, rng, "normal")
        allowed = {c.text for c in step.lesson.commands}
        assert {c.text for c in commands} <= allowed


# -- profile ---------------------------------------------------------------


@pytest.fixture
def profile_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    return tmp_path


def make_run(text="grep -rn TODO .", errors_at=()):
    s = TypingSession([text])
    t = 0.0
    for i, ch in enumerate(text):
        t += 0.1
        s.press("Z" if i in errors_at else ch, t)
    return s


def test_profile_round_trips(profile_home):
    p = Profile.load()
    assert p.runs == [] and p.keys == {}
    s = make_run(errors_at=(2, 5))
    p.record("path", s.metrics(), s.key_stats())
    p.record_tools({"grep": (40, 3)})
    p.record_lesson("find", "normal", 24.0, 0.95, True)
    p.save()

    again = Profile.load()
    assert len(again.runs) == 1 and again.runs[0].mode == "path"
    assert again.best_wpm() == pytest.approx(p.runs[0].wpm, abs=0.01)
    assert again.tools["grep"].attempts == 40
    assert again.lesson("find", "normal").cleared is True
    assert again.cleared_count() == 1
    assert again.cleared_count("normal") == 1
    assert again.cleared_count("hard") == 0


def test_clearing_a_lesson_sticks(profile_home):
    """A bad run later must not un-teach a lesson you already cleared."""
    p = Profile.load()
    p.record_lesson("files", "normal", 30.0, 0.96, True)
    p.record_lesson("files", "normal", 12.0, 0.70, False)
    state = p.lesson("files", "normal")
    assert state.cleared is True
    assert state.attempts == 2
    assert state.best_wpm == 30.0
    assert state.best_accuracy == pytest.approx(0.96)


def test_lesson_results_are_kept_separate_per_difficulty(profile_home):
    """Easy and hard runs of the same lesson must not blend their bests --
    the time budget (and so the wpm needed to clear) differs per difficulty."""
    p = Profile.load()
    p.record_lesson("files", "easy", 20.0, 0.95, True)
    p.record_lesson("files", "hard", 40.0, 0.92, False)
    assert p.lesson("files", "easy").best_wpm == 20.0
    assert p.lesson("files", "easy").cleared is True
    assert p.lesson("files", "hard").best_wpm == 40.0
    assert p.lesson("files", "hard").cleared is False
    assert p.lesson("files", "normal") == LessonState()
    p.save()

    again = Profile.load()
    assert again.lesson("files", "easy").best_wpm == 20.0
    assert again.lesson("files", "hard").best_wpm == 40.0
    assert again.cleared_count("easy") == 1
    assert again.cleared_count("hard") == 0
    assert again.cleared_count() == 1     # cleared at any difficulty


def test_unknown_lesson_is_safe(profile_home):
    assert Profile.load().lesson("nope", "normal") == LessonState()


def test_old_flat_lesson_state_migrates_to_normal(profile_home):
    """Profiles saved before difficulty was tracked stored one flat state
    per lesson; that history must land in the 'normal' bucket, not vanish."""
    import json

    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "lessons": {"files": {"cleared": True, "attempts": 3,
                              "best_wpm": 28.0, "best_accuracy": 0.94}},
    }))
    p = Profile.load()
    assert p.lesson("files", "normal").cleared is True
    assert p.lesson("files", "normal").best_wpm == 28.0
    assert p.lesson("files", "easy") == LessonState()


def test_difficulty_defaults_to_normal_and_round_trips(profile_home):
    p = Profile.load()
    assert p.difficulty == "normal"
    p.difficulty = "hard"
    p.save()
    assert Profile.load().difficulty == "hard"


def test_bogus_stored_difficulty_falls_back_to_normal(profile_home):
    import json

    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"difficulty": "nightmare"}))
    assert Profile.load().difficulty == "normal"


def test_tool_stats_accumulate(profile_home):
    p = Profile.load()
    p.record_tools({"awk": (10, 1)})
    p.record_tools({"awk": (10, 3), "sed": (5, 0)})
    assert (p.tools["awk"].attempts, p.tools["awk"].errors) == (20, 4)
    assert p.tools["sed"].error_rate == 0.0


def test_corrupt_profile_does_not_crash(profile_home):
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json at all")
    assert Profile.load().runs == []

    path.write_text('{"keys": {"ab": {"attempts": 1}}, "runs": [7], '
                    '"tools": {"x": "nope"}, "lessons": {"y": 5}}')
    p = Profile.load()
    assert p.keys == {} and p.runs == [] and p.tools == {} and p.lessons == {}


def test_unwritable_profile_is_survivable(profile_home, monkeypatch):
    p = Profile.load()
    p.record_lesson("files", "normal", 20.0, 0.9, True)
    monkeypatch.setattr("pathlib.Path.mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    p.save()      # must not raise


def test_weak_keys_ignores_keys_with_too_little_data(profile_home):
    p = Profile.load()
    p.keys["z"] = KeyStat(attempts=2, errors=2)                    # noise
    p.keys["e"] = KeyStat(attempts=MIN_ATTEMPTS * 2, errors=MIN_ATTEMPTS)
    p.keys["a"] = KeyStat(attempts=MIN_ATTEMPTS * 2, errors=0)     # fine
    assert p.weak_keys() == ["e"]


def test_weak_keys_includes_accurate_but_slow_keys(profile_home):
    p = Profile.load()
    for ch in "abcdef":
        p.keys[ch] = KeyStat(attempts=100, errors=0, latency_total=10.0,
                             latency_n=100)
    p.keys["z"] = KeyStat(attempts=100, errors=0, latency_total=40.0,
                          latency_n=100)
    assert p.weak_keys() == ["z"]


def test_history_is_capped(profile_home):
    from l33t.stats import HISTORY_LIMIT
    p = Profile.load()
    s = make_run()
    for _ in range(HISTORY_LIMIT + 25):
        p.record("drill", s.metrics(), s.key_stats())
    p.save()
    assert len(Profile.load().runs) == HISTORY_LIMIT


# -- view window -----------------------------------------------------------


@pytest.mark.parametrize("line,total", [(0, 1), (0, 10), (3, 10), (9, 10),
                                        (10, 10), (5, 3), (0, 0)])
@pytest.mark.parametrize("cap", [1, 2, 3, 6, 99])
def test_visible_range_stays_in_bounds(line, total, cap):
    from l33t.play import WINDOW, visible_range
    first, last = visible_range(line, total, cap)
    assert 0 <= first <= last <= total
    assert last - first <= min(max(cap, 1), WINDOW)


@pytest.mark.parametrize("cap", [1, 2, 3, 6])
def test_visible_range_keeps_the_active_line_in_view(cap):
    from l33t.play import visible_range
    for line in range(10):
        first, last = visible_range(line, 10, cap)
        assert first <= line < last, (line, cap, first, last)


@pytest.mark.parametrize("height", range(18, 60))
def test_layout_always_leaves_room_for_the_explanation(height):
    """Regression: at minimum height the footer rule overwrote the command
    explanation -- which is the half of the game that teaches you anything."""
    from l33t.play import FOOTER_ROWS, TEXT_TOP, window_size
    n = window_size(height)
    note_y = TEXT_TOP + n * 2
    rule_y = note_y + 2 - 1
    footer_y = min(height - 2, note_y + 2)
    assert n >= 1
    assert note_y < rule_y, "explanation overwritten by the separator"
    assert rule_y < height
    assert footer_y <= height - 2


# -- tool attribution ------------------------------------------------------


def _cmd(text, tool):
    return shell.Command(text, "a problem statement", "does a thing", tool,
                         (shell.Part(text, "the whole thing"),))


def test_tool_breakdown_attributes_errors_to_the_right_tool():
    from l33t.screens import _tool_breakdown
    cmds = [_cmd("abcd", "grep"), _cmd("efgh", "awk")]
    s = TypingSession([c.text for c in cmds])
    t = 0.0
    for ch in "abZd" "efgh":          # one error, in the grep line
        t += 0.1
        s.press(ch, t)
    out = _tool_breakdown(s, cmds)
    assert out["grep"] == (4, 1)
    assert out["awk"] == (4, 0)


def test_tool_breakdown_skips_untouched_lines():
    from l33t.screens import _tool_breakdown
    cmds = [_cmd("abcd", "grep"), _cmd("efgh", "awk")]
    s = TypingSession([c.text for c in cmds])
    for i, ch in enumerate("abcd"):
        s.press(ch, i * 0.1)
    out = _tool_breakdown(s, cmds)
    assert "awk" not in out           # never reached
    assert out["grep"] == (4, 0)


# -- timing --------------------------------------------------------------


def test_nothing_counts_down_before_the_first_keypress():
    """Reading the screen must be free. The trace starts when you do."""
    from l33t.play import RunContext
    from l33t.engine import TypingSession

    session = TypingSession(["ls -lah"])
    ctx = RunContext(mode="path", title="t", trace_seconds=10.0)
    for _ in range(600):            # ten seconds of frames, untouched
        ctx.update(1 / 60, session)
    assert ctx.trace == 0.0
    assert ctx.outcome is None

    session.press("l", 0.0)
    for _ in range(60):
        ctx.update(1 / 60, session)
    assert ctx.trace > 0.9


def test_learning_phases_carry_no_clock_at_all():
    """The calm phases must have no trace and no time limit -- a countdown
    while you're still understanding the command is the opposite of the job."""
    from l33t.play import RunContext
    from l33t.engine import TypingSession

    session = TypingSession(["ls -lah"])
    ctx = RunContext(mode="learn", title="t", calm=True)
    session.press("l", 0.0)
    for _ in range(6000):           # a hundred seconds of thinking
        ctx.update(1 / 60, session)
    assert ctx.trace == 0.0
    assert ctx.outcome is None
    assert ctx.trace_seconds is None and ctx.time_limit is None


def test_a_timed_run_still_ends_once_started():
    from l33t.play import RunContext
    from l33t.engine import TypingSession

    session = TypingSession(["ls -lah"])
    ctx = RunContext(mode="path", title="t", trace_seconds=2.0)
    session.press("l", 0.0)
    for _ in range(300):
        ctx.update(1 / 60, session)
    assert ctx.outcome == "traced"


def test_an_error_costs_trace_only_after_you_start():
    from l33t.play import RunContext
    from l33t.engine import TypingSession

    ctx = RunContext(mode="path", title="t", trace_seconds=10.0,
                     error_penalty=0.8)
    ctx.penalise()
    assert ctx.trace == pytest.approx(0.8)   # penalties are keypress-driven


# -- sample runs -----------------------------------------------------------


def test_every_command_shows_what_it_prints():
    """The demo is half the teaching -- a command with no sample run leaves
    you guessing what success even looks like."""
    for cmd in shell.ALL_COMMANDS:
        assert cmd.demo, cmd.text


def test_demo_lines_fit_the_panel():
    for cmd in shell.ALL_COMMANDS:
        for line in cmd.demo:
            assert len(line.expandtabs(8)) <= shell.DEMO_WIDTH, (cmd.text, line)


def test_demos_are_short_enough_to_read():
    for cmd in shell.ALL_COMMANDS:
        assert len(cmd.demo) <= 6, (cmd.text, len(cmd.demo))


def test_demo_keys_all_match_a_real_command():
    """A demo keyed to a command that no longer exists is dead content that
    silently stops being shown."""
    from l33t.demos import DEMOS
    known = {c.text for c in shell.ALL_COMMANDS}
    assert set(DEMOS) - known == set()


def test_head_demos_respect_their_line_limit():
    for cmd in shell.ALL_COMMANDS:
        m = re.search(r"head -(\d+)\s*$", cmd.text)
        if m:
            body = [l for l in cmd.demo if not l.startswith("$ ")]
            assert len(body) <= int(m.group(1)), (cmd.text, body)


def test_counting_demos_print_exactly_one_integer():
    for cmd in shell.ALL_COMMANDS:
        if re.search(r"(wc -l|grep -c \S+)( \S+)?$", cmd.text):
            body = [l for l in cmd.demo if not l.startswith("$ ")]
            assert len(body) == 1, (cmd.text, cmd.demo)
            assert body[0].strip().isdigit(), (cmd.text, body)


def test_status_code_demo_is_a_status_code():
    for cmd in shell.ALL_COMMANDS:
        if "%{http_code}" in cmd.text:
            body = [l for l in cmd.demo if not l.startswith("$ ")]
            assert len(body) == 1 and body[0].strip().isdigit()
            assert len(body[0].strip()) == 3, body


def test_uniq_c_demo_is_descending():
    for cmd in shell.ALL_COMMANDS:
        if cmd.text.endswith("uniq -c | sort -rn"):
            counts = [int(l.split()[0]) for l in cmd.demo]
            assert counts == sorted(counts, reverse=True), cmd.demo


def test_silent_commands_demo_how_to_verify_them():
    """Commands that print nothing must show the follow-up that proves they
    worked -- otherwise the demo would just be blank."""
    silent = ["mkdir -p build/{bin,lib,include}", "chmod 600 ~/.ssh/id_ed25519",
              "umask 027", "set -euo pipefail", "chown -R deploy:deploy /srv/www"]
    for text in silent:
        cmd = next(c for c in shell.ALL_COMMANDS if c.text == text)
        assert cmd.demo[0].startswith("$ "), (text, cmd.demo)
        assert len(cmd.demo) >= 2, text


def test_follow_up_commands_come_before_their_output():
    """A '$ ' line is a command; output below it belongs to it. An output
    line before any command would be orphaned."""
    for cmd in shell.ALL_COMMANDS:
        if any(l.startswith("$ ") for l in cmd.demo):
            assert cmd.demo[0].startswith("$ "), (cmd.text, cmd.demo)


def test_demo_does_not_just_repeat_the_command():
    for cmd in shell.ALL_COMMANDS:
        for line in cmd.demo:
            assert line.strip() != cmd.text, cmd.text


# -- skipping --------------------------------------------------------------


def test_phases_from_each_start_point():
    from l33t.modes import PHASES, phases_from
    assert phases_from("full") == ("learn", "recall", "challenge")
    assert phases_from("recall") == ("recall", "challenge")
    assert phases_from("challenge") == ("challenge",)
    for start in ("full", "recall", "challenge"):
        got = phases_from(start)
        # always a suffix of the full sequence, never reordered
        assert got == PHASES[len(PHASES) - len(got):]


def test_an_unknown_start_point_runs_everything():
    """A bad value must teach more, not less."""
    from l33t.modes import phases_from
    assert phases_from("nonsense") == ("learn", "recall", "challenge")
    assert phases_from("") == ("learn", "recall", "challenge")


def test_you_can_never_skip_the_challenge():
    """The challenge is the only thing that clears a lesson, so no start
    point may skip past it."""
    from l33t.modes import START_POINTS, phases_from
    for start in START_POINTS:
        assert "challenge" in phases_from(start), start


def test_skip_keys_are_not_typeable():
    """Every printable key is a character you might have to type, so a skip
    bound to one would fire mid-command."""
    from l33t.play import ABORT_KEYS, SKIP_KEYS
    for key in SKIP_KEYS + ABORT_KEYS:
        assert not (32 <= key <= 126), key


def test_skip_is_refused_when_a_step_is_not_skippable():
    """The timed challenge must ignore the skip key entirely."""
    from l33t.play import RunContext
    ctx = RunContext(mode="path", title="challenge", trace_seconds=30.0)
    assert ctx.skippable is False


def test_teaching_steps_are_skippable_and_the_challenge_is_not():
    import inspect

    from l33t import screens
    src = inspect.getsource(screens.type_single)
    assert "skippable=True" in src, "teaching steps must be skippable"
    challenge = inspect.getsource(screens.play_lesson)
    challenge = challenge[challenge.index("phase 5"):]
    assert "skippable" not in challenge, "the challenge must not be skippable"


def test_menu_labels_are_never_truncated():
    """A hard-coded label column silently clips the longest option -- which
    is usually the most important one."""
    import inspect

    from l33t import screens
    src = inspect.getsource(screens.menu)
    assert "label_w = max(" in src, "label column must size itself"
    assert ".ljust(20)" not in src


# -- regression: drill's synthetic Command entries --------------------------


def test_symbol_drills_build_valid_commands():
    """Regression: _symbol_drills used to call shell.Command with the old
    3-positional-argument shape, which crashed the moment DRILL was opened
    from the menu -- and nothing in the suite exercised that call site."""
    from l33t.screens import _symbol_drills

    for seed in range(20):
        rng = random.Random(seed)
        drills = _symbol_drills(rng, ["|", "&"], 2)
        assert len(drills) == 2
        for cmd in drills:
            assert isinstance(cmd, shell.Command)
            assert cmd.text and cmd.problem and cmd.explain and cmd.tool
            assert cmd.parts and all(isinstance(p, shell.Part) for p in cmd.parts)
            # reassemble() is the general invariant every Command must satisfy
            assert shell.reassemble(cmd) == cmd.text


def test_symbol_drills_work_with_no_weak_keys_yet():
    """A fresh profile has no weak keys -- must not crash on an empty list."""
    from l33t.screens import _symbol_drills
    drills = _symbol_drills(random.Random(1), [], 2)
    assert len(drills) == 2
