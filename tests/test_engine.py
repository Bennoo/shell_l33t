import random

import pytest

from l33t.engine import LATENCY_CAP, TypingSession


def type_out(session, text, *, start=0.0, interval=0.1, now=None):
    """Feed `text` one character at a time at a fixed cadence."""
    t = start
    for ch in text:
        t += interval
        session.press(ch, t)
    return t


def test_clock_starts_on_first_keypress_not_construction():
    s = TypingSession(["abcde"])
    s.press("a", 100.0)          # a long think before starting
    s.press("b", 100.1)
    m = s.metrics(100.1)
    assert m.elapsed == pytest.approx(0.1)


def test_perfect_run_wpm_and_accuracy():
    # 50 characters in exactly 60s = 10 "words" per minute.
    text = "a" * 50
    s = TypingSession([text])
    t = 0.0
    for ch in text:
        s.press(ch, t)
        t += 60.0 / 49          # first press starts the clock
    m = s.metrics()
    assert s.done
    assert m.net_wpm == pytest.approx(10.0, rel=1e-6)
    assert m.raw_wpm == pytest.approx(10.0, rel=1e-6)
    assert m.accuracy == 1.0
    assert m.errors == 0


def test_accuracy_counts_keystrokes_not_final_text():
    s = TypingSession(["ab"])
    s.press("x", 1.0)           # wrong
    s.backspace(1.1)
    s.press("a", 1.2)
    s.press("b", 1.3)
    m = s.metrics()
    assert s.done
    assert m.correct_chars == 2          # the text ends up perfect
    assert m.accuracy == pytest.approx(2 / 3)   # but 3 keys were pressed
    assert m.errors == 1


def test_net_wpm_ignores_wrong_characters_raw_does_not():
    s = TypingSession(["abcd"])
    type_out(s, "abXd")
    m = s.metrics()
    assert m.correct_chars == 3
    assert m.typed_chars == 4
    assert m.raw_wpm > m.net_wpm


def test_empty_session_is_inert():
    s = TypingSession([])
    assert s.press("a", 1.0) is False
    m = s.metrics()
    assert m.net_wpm == 0.0 and m.accuracy == 1.0


def test_lines_advance_and_session_finishes():
    s = TypingSession(["ab", "cd"])
    type_out(s, "ab")
    assert s.line == 1 and s.pos == 0 and not s.done
    type_out(s, "cd", start=1.0)
    assert s.done


def test_strict_mode_blocks_until_corrected():
    s = TypingSession(["abc"], strict=True)
    s.press("a", 1.0)
    for i in range(5):
        s.press("z", 2.0 + i)         # wrong, repeatedly
        assert s.pos == 1, "cursor moved past an uncorrected error"
    s.press("b", 8.0)
    assert s.pos == 2
    assert s.errors == 5


def test_backspace_can_be_disabled():
    s = TypingSession(["abc"], allow_backspace=False)
    s.press("x", 1.0)
    s.backspace(1.1)
    assert s.pos == 1                  # the mistake is permanent
    assert s.typed[0] == ["x"]


def test_backspace_crosses_line_boundaries():
    s = TypingSession(["ab", "cd"])
    type_out(s, "abc")
    assert s.line == 1 and s.pos == 1
    s.backspace(5.0)
    assert s.line == 1 and s.pos == 0
    s.backspace(5.1)
    assert s.line == 0 and s.pos == 1
    assert s.typed[0] == ["a"]


def test_backspace_at_the_very_start_is_a_no_op():
    s = TypingSession(["ab"])
    s.backspace(1.0)
    assert s.line == 0 and s.pos == 0


def test_backspace_after_finishing_does_nothing():
    s = TypingSession(["ab"])
    type_out(s, "ab")
    assert s.done
    s.backspace(9.0)
    assert s.typed[0] == ["a", "b"]


def test_progress_tracks_characters_typed():
    s = TypingSession(["abcd", "efgh"])
    assert s.progress() == 0.0
    type_out(s, "abcd")
    assert s.progress() == pytest.approx(0.5)
    type_out(s, "efgh", start=5.0)
    assert s.progress() == 1.0


def test_key_stats_are_keyed_by_the_expected_character():
    s = TypingSession(["aaa"])
    s.press("a", 1.0)
    s.press("z", 1.1)          # wrong key, but 'a' was expected
    s.press("a", 1.2)
    stats = s.key_stats()
    assert set(stats) == {"a"}
    assert stats["a"].attempts == 3
    assert stats["a"].errors == 1
    assert stats["a"].error_rate == pytest.approx(1 / 3)


def test_long_pauses_do_not_pollute_latency():
    """A pause for thought is not a measure of how fast a key is."""
    s = TypingSession(["ab"])
    s.press("a", 0.0)
    s.press("b", 10.0)         # a 10s think
    stats = s.key_stats()
    assert stats["b"].latency_n == 0
    assert stats["b"].mean_latency == 0.0

    s2 = TypingSession(["ab"])
    s2.press("a", 0.0)
    s2.press("b", LATENCY_CAP - 0.01)
    assert s2.key_stats()["b"].latency_n == 1


def test_worst_keys_ranks_by_error_rate_and_respects_min_attempts():
    s = TypingSession(["aaaaz"])
    for i, ch in enumerate("xxxa"):    # 'a' expected 4x, 3 errors
        s.press(ch, 1.0 + i * 0.1)
    s.press("q", 2.0)                  # 'z' expected once, 1 error
    assert s.worst_keys(min_attempts=3) == ["a"]
    assert set(s.worst_keys(min_attempts=1)) == {"a", "z"}


def test_a_clean_run_reports_no_weak_keys():
    """A perfect run must not list keys you never missed."""
    s = TypingSession(["the quick brown fox jumps"])
    type_out(s, "the quick brown fox jumps")
    assert s.metrics().accuracy == 1.0
    assert s.worst_keys() == []


def test_consistency_is_high_for_metronomic_typing():
    s = TypingSession(["a" * 120])
    t = 0.0
    for ch in s.lines[0]:
        s.press(ch, t)
        t += 0.1                       # exactly 10 keys/sec
    assert s.consistency() > 0.85


def test_consistency_drops_for_bursty_typing():
    s = TypingSession(["a" * 120])
    t = 0.0
    for i, ch in enumerate(s.lines[0]):
        s.press(ch, t)
        t += 0.01 if (i // 20) % 2 == 0 else 0.3   # sprint, stall, sprint
    steady = TypingSession(["a" * 120])
    t = 0.0
    for ch in steady.lines[0]:
        steady.press(ch, t)
        t += 0.1
    assert s.consistency() < steady.consistency()


def test_consistency_is_neutral_without_enough_data():
    s = TypingSession(["abc"])
    s.press("a", 1.0)
    assert s.consistency() == 1.0


def test_metrics_are_stable_after_finishing():
    """Once done, the clock stops -- idling on the results screen must not
    erode the score."""
    s = TypingSession(["abcde"])
    type_out(s, "abcde")
    first = s.metrics(now=1000.0)
    later = s.metrics(now=99999.0)
    assert first.net_wpm == later.net_wpm
    assert first.elapsed == later.elapsed


@pytest.mark.parametrize("seed", range(30))
def test_random_input_never_corrupts_state(seed):
    rng = random.Random(seed)
    lines = ["".join(rng.choice("abc ") for _ in range(rng.randint(1, 12)))
             for _ in range(3)]
    s = TypingSession(lines, strict=rng.random() < 0.5,
                      allow_backspace=rng.random() < 0.5)
    t = 0.0
    for _ in range(400):
        t += rng.random() * 0.2
        if rng.random() < 0.2:
            s.backspace(t)
        else:
            s.press(rng.choice("abcxyz "), t)
        assert 0 <= s.line <= len(s.lines)
        if s.line < len(s.lines):
            assert 0 <= s.pos <= len(s.lines[s.line])
        for i in range(len(s.lines)):
            assert len(s.typed[i]) == len(s.ok[i])
        m = s.metrics(t)
        assert 0.0 <= m.accuracy <= 1.0
        assert 0.0 <= m.consistency <= 1.0
        assert m.net_wpm <= m.raw_wpm + 1e-9
