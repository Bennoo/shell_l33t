import pytest

from l33t import shell
from l33t.effects import (
    FLASH, SCRAMBLE, SCRAMBLING, SETTLED, Decrypt, Typewriter,
)

TEXT = "du -sh * | sort -rh | head -10"


def render(effect, elapsed):
    return "".join(effect.state(i, elapsed)[0] for i in range(len(effect.text)))


def test_decrypt_resolves_to_the_exact_text():
    d = Decrypt(TEXT)
    assert render(d, d.duration) == TEXT
    assert render(d, d.duration + 100) == TEXT
    assert d.done(d.duration)


def test_decrypt_starts_as_noise():
    d = Decrypt(TEXT)
    assert render(d, 0.0) != TEXT
    assert not d.done(0.0)


def test_decrypt_never_scrambles_whitespace():
    """Keeping the spaces still preserves the word shapes, so the command is
    readable while it resolves instead of a wall of punctuation."""
    d = Decrypt(TEXT)
    for t in (0.0, 0.1, 0.3, 0.6, 1.0):
        shown = render(d, t)
        for i, ch in enumerate(TEXT):
            if ch == " ":
                assert shown[i] == " ", (t, i)


def test_decrypt_resolves_left_to_right_and_never_unresolves():
    """Once a character has landed it must stay landed; a settled character
    flickering back to noise reads as a glitch, not an effect."""
    d = Decrypt(TEXT)
    settled_at = {}
    t = 0.0
    while t <= d.duration + 0.1:
        for i, ch in enumerate(TEXT):
            _, tier = d.state(i, t)
            if tier == SETTLED and not ch.isspace():
                settled_at.setdefault(i, t)
            elif tier == SCRAMBLING:
                assert i not in settled_at, f"char {i} unresolved at {t}"
        t += 1 / 60
    order = [settled_at[i] for i in sorted(settled_at)]
    assert order == sorted(order), "characters did not resolve left to right"


def test_decrypt_flashes_as_each_character_lands():
    d = Decrypt(TEXT)
    i = 5
    settle = d.settle_at(i)
    assert d.state(i, settle - 0.01)[1] == SCRAMBLING
    assert d.state(i, settle + d.flash / 2)[1] == FLASH
    assert d.state(i, settle + d.flash + 0.01)[1] == SETTLED
    # The flash shows the real character, not noise.
    assert d.state(i, settle + d.flash / 2)[0] == TEXT[i]


def test_decrypt_noise_comes_from_the_scramble_set():
    d = Decrypt(TEXT)
    for t in (0.0, 0.05, 0.2):
        for i, ch in enumerate(TEXT):
            glyph, tier = d.state(i, t)
            if tier == SCRAMBLING:
                assert glyph in SCRAMBLE


def test_decrypt_is_deterministic():
    """A frame redrawn at the same time must look identical -- otherwise the
    text shimmers whenever the frame rate wobbles."""
    a, b = Decrypt(TEXT, seed=3), Decrypt(TEXT, seed=3)
    assert render(a, 0.17) == render(b, 0.17)


def test_decrypt_noise_actually_changes_over_time():
    d = Decrypt(TEXT)
    assert render(d, 0.0) != render(d, d.flicker * 3)


def test_decrypt_progress_is_bounded():
    d = Decrypt(TEXT)
    assert d.progress(-1) == 0.0
    assert d.progress(0.0) == 0.0
    assert d.progress(d.duration * 10) == 1.0


def test_empty_decrypt_is_harmless():
    d = Decrypt("")
    assert d.duration == 0.0 and d.done(0.0) and d.progress(0.0) == 1.0


def test_typewriter_reveals_then_completes():
    t = Typewriter("hello world", cps=10)
    assert t.visible(0.0) == ""
    assert t.visible(0.5) == "hello"
    assert t.visible(t.duration) == "hello world"
    assert t.visible(t.duration + 99) == "hello world"
    assert t.done(t.duration)


def test_typewriter_respects_its_delay():
    t = Typewriter("abc", cps=10, delay=1.0)
    assert t.visible(0.9) == ""
    assert t.visible(1.3) == "abc"[:3]
    assert t.duration == pytest.approx(1.3)


def test_typewriter_caret_only_while_typing():
    t = Typewriter("abc", cps=10, delay=0.5)
    assert not t.caret(0.2)               # before it starts
    assert t.caret(0.6)                   # mid-type
    assert not t.caret(t.duration + 0.1)  # finished


def test_typewriter_output_is_always_a_prefix():
    t = Typewriter("some explanation text", cps=30)
    e = 0.0
    while e <= t.duration + 0.2:
        assert t.text.startswith(t.visible(e))
        e += 1 / 60


# -- the part highlighting the animation drives ----------------------------


def test_part_spans_point_at_the_right_characters():
    for cmd in shell.ALL_COMMANDS:
        spans = shell.part_spans(cmd)
        assert len(spans) == len(cmd.parts)
        for (start, end), part in zip(spans, cmd.parts):
            assert cmd.text[start:end] == part.text, cmd.text


def test_part_spans_are_ordered_and_non_overlapping():
    for cmd in shell.ALL_COMMANDS:
        spans = shell.part_spans(cmd)
        for (_, prev_end), (start, _) in zip(spans, spans[1:]):
            assert prev_end <= start, cmd.text
        assert spans[-1][1] <= len(cmd.text)


def test_part_spans_cover_everything_but_the_joiners():
    for cmd in shell.ALL_COMMANDS:
        covered = sum(e - s for s, e in shell.part_spans(cmd))
        joiners = sum(len(p.glue) for p in cmd.parts[1:])
        assert covered + joiners == len(cmd.text), cmd.text


# -- east asian width ------------------------------------------------------


def test_display_width_counts_columns_not_codepoints():
    from l33t.ui import display_width
    assert display_width("akari") == 5
    assert display_width("あかり") == 6          # 3 codepoints, 6 columns
    assert display_width("あかり / akari") == 14
    assert display_width("") == 0


def test_clip_never_splits_a_wide_character():
    """Half a kana is a corrupted cell, and it desynchronises the whole line."""
    from l33t.ui import clip_to_width, display_width
    for columns in range(0, 10):
        clipped = clip_to_width("あかり", columns)
        assert display_width(clipped) <= columns
        assert "あかり".startswith(clipped)
    assert clip_to_width("あかり", 5) == "あか"   # 5 cols can't hold the third


def test_clip_handles_mixed_width_text():
    from l33t.ui import clip_to_width, display_width
    text = "OBSERVING :: あかり / akari"
    for columns in range(0, 30):
        clipped = clip_to_width(text, columns)
        assert display_width(clipped) <= columns
        assert text.startswith(clipped)


def test_wrap_measures_columns():
    from l33t.ui import display_width, wrap
    lines = wrap("あかり あかり あかり あかり", 14)
    assert len(lines) > 1
    for line in lines:
        assert display_width(line) <= 14, line


# -- boot pacing -----------------------------------------------------------


def test_boot_is_readable_but_not_tedious():
    """A boot sequence nobody can read is just a delay -- and one that
    outstays its welcome is worse, because you see it every launch."""
    from l33t.screens import BOOT_LINES, boot_schedule
    schedule, total = boot_schedule()
    assert len(schedule) == len(BOOT_LINES)
    assert 2.5 <= total <= 5.0, total
    starts = [start for start, *_ in schedule]
    assert starts == sorted(starts)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(g >= 0.15 for g in gaps), gaps


def test_boot_lines_finish_typing_before_the_next_one_starts():
    """Overlapping lines would read as a jumble rather than a sequence."""
    from l33t.screens import boot_schedule
    schedule, _ = boot_schedule()
    for (start, _, _, typer), (next_start, *_) in zip(schedule, schedule[1:]):
        assert start + typer.duration <= next_start, start


def test_boot_lines_are_fully_revealed_at_their_own_end():
    from l33t.screens import boot_schedule
    for start, line, _, typer in boot_schedule()[0]:
        assert typer.visible(typer.duration) == line
