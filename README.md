# L33T

**Learn the shell by solving problems with it, then drill the typing.**

Knowing shell commands cold, and typing them without looking at your hands,
used to just be what it meant to be good at this job. These days an agent
will write the command faster and more reliably than you will, and that's
genuinely fine — it's a good trade, most days.

But there's still something worth keeping in doing it yourself, the same way
there's still something worth keeping in building your own mechanical
keyboard or restoring an old motorcycle when a new one would just work. Not
because it's the efficient way to get the job done, but because the craft is
satisfying on its own terms — the fluency, the muscle memory, the small
pleasure of a command landing clean on the first try. L33T exists to keep
that alive a little, for whoever still wants it.

Not a typing test with shell-flavoured filler. Each lesson teaches you *which
problem is solved by which command, in which composition* — and only then
asks you to type it fast.

```bash
uv sync
uv run l33t
```

(or `python3 game.py` — needs a real terminal, at least 72x22)

## How a lesson works

Five phases. **Only the last one is timed.**

**1. The problem.** Posed on its own, before you see any answer:

> *The disk is filling up. Which things in this folder are the biggest?*
>
> How would you do that? *Have a think — nothing is timed here.*

**2. The breakdown.** The command decrypts into place out of shell noise:

```
DECRYPTING PAYLOAD  [██████░░░░░░░░░░░░]
cp 'A] ^~F/9[`%'E> )~$:9<3%?E;8)2$
             ↓
cp -av config.yaml config.yaml.bak
```

Then each explanation types in while its fragment **lights up inside the
command**, so you can see exactly which characters it's talking about:

```
du -sh * | sort -rh | head -10
the ten largest items here, biggest first
────────────────────────────────────────────────────────────
du -sh *    total size of each item, -s summarised, -h readable
|           feed that list into the next command
sort -rh    -h understands '2.4G', -r puts the largest first
|           and pass the sorted list on again
head -10    keep only the first ten lines
```

Then a sample run, so you know what success actually looks like:

```
IF YOU RUN IT
$ ln -sfn /opt/app/releases/v3 /opt/app/current
$ ls -l /opt/app/current
  lrwxrwxrwx 1 root root 21 Sep 11 09:31 current -> releases/v3
```

Commands that print nothing show the follow-up that proves they worked —
because "silence means success" is itself a shell lesson, and so is knowing
how to check. Sample output has to match the flags the breakdown just
explained: `head -10` never shows eleven lines, `grep -c` shows one integer,
a pipeline ending `sort -rn` comes back descending. All enforced by tests.

Any key skips straight to the fully revealed version — the effect never
stands between you and the content.

**3. Type it.** Untimed, no speed readout, and you can't move past a character
until it's right — the point is to learn it correctly.

**4. Recall.** The part that proves you learned it. You get the *problem
only*; the command is hidden behind `·· ··· ···········` and appears as you
type it from memory. Paths, filenames and hosts stay visible throughout --
they're generated per run, so recall is testing whether you remember the
command and its flags, not whether you memorised `config.yaml`. Still no
clock. `TAB` reveals it if you're stuck, and the result screen tells you how
often you needed that.

**5. Challenge.** Now speed. The same four commands, back to back, against the
trace. Clear the lesson at the target speed with 90% accuracy.

### Skipping

Already know a lesson, or did it once and it didn't get recorded? You don't
have to sit through the teaching again. Picking a lesson asks where to begin:

```
▸ FROM THE START          problem, breakdown, type, recall, challenge
  SKIP TO RECALL          you know these -- prove it, then race
  STRAIGHT TO CHALLENGE   the timed run, nothing else
```

And `ctrl-N` (or PageDown) skips whatever step you're on, so you can bail out
of a command you already know without leaving the lesson.

The one thing you can never skip is the **challenge** — it's the only thing
that clears a lesson, so skipping past it would let you tick off a lesson
without doing it. Skipped steps aren't folded into your key statistics
either, since you didn't type them.

あかり turns up throughout — a line on each lesson card, and a verdict on how
the challenge went:

```
あかり  the one everybody skips. permissions bite quietly.
あかり  speed without accuracy is just noise. again, slower.
```

The clock never runs while you're trying to understand something. Even in the
challenge it starts on your **first keypress**, not when the screen appears —
reading is always free.

## The path

11 lessons, 66 commands, 45 tools, each command with its own problem and
decomposition:

files & navigation · reading files · finding things · text processing · pipes
& redirection · permissions · processes & jobs · networking · git · archives &
transfer · shell scripting

Lessons 4, 6, 8 and 10 add pressure **to the challenge only**: `PURGE` (errors
cost double), `NO BACKSPACE`, `SURGE` (the trace accelerates), `LOCKDOWN` (fix
an error before you can continue). Clearing sticks — a bad run later doesn't
un-teach a lesson.

Difficulty is set on the learning path screen (left/right arrows) and sticks
across sessions per lesson: `easy` gives the challenge 35% more time, `hard`
gives 18% less. `--difficulty` seeds it from the command line on launch.
Results are tracked separately per difficulty, since the wpm needed to clear
a lesson isn't comparable across them.

## WATCH

Nothing to do but admire. **あかり (Akari)** works a real shell, endlessly:

```
OBSERVING :: あかり / akari :: session 2d73cb

# key rejected after restoring from backup
akari@sendai-cache:~$ ssh -i ~/.ssh/id_ed25519 akari@akiba-relay
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
Permissions 0644 for '~/.ssh/id_ed25519' are too open.
akari@akiba-relay: Permission denied (publickey).
akari@sendai-cache:~$ stat -c '%A %U:%G %n' ~/.ssh/id_ed25519
-rw-r--r-- akari:akari /home/akari/.ssh/id_ed25519
# ビンゴ   bingo
akari@sendai-cache:~$ chmod 600 ~/.ssh/id_ed25519
```

She leaves herself short notes as she works — なるほど, 見つけた, 完了 — placed
where they make sense: a reaction only lands on a command that actually
printed something, a failure gets a failure-shaped reaction, and a scene
closes on a closing note. Her shell account is ASCII (`akari@tokyo-gw`), as
Unix accounts are; the kana is in the chrome and her notes.

Terminal width is measured in **columns, not codepoints** — あかり is three
characters but six cells — so nothing overruns its panel and a clip never
splits a kana in half. Terminals that can't do UTF-8 get the English gloss.

Nine scenes — disk filling up, service down, deploy, log forensics, a
rejected SSH key, a squatted port, tidying a branch, probing the network,
crunching a CSV. Each is a **coherent investigation**: output from one command
motivates the next, the way it does when someone knows what they're doing.

- **The output is correct.** `head -10` never returns eleven lines, `wc -l`
  returns one integer, a pipeline ending in `sort -rn` comes back descending,
  and `%{http_code}` returns three digits (`000` only when the command is
  marked failed). All enforced by tests.
- **Every value is generated per run** — hosts, users, paths, sizes, pids,
  addresses, commit hashes, timestamps — so two viewings never match, and the
  same scene never runs twice in a row.
- **The typing is human.** Variable speed, a beat at pipes and quotes, and the
  occasional slip instantly backspaced away. It always ends on the exact
  command.

When a scene finishes it stays on screen for seven seconds with a countdown,
so you can read the whole investigation before it's wiped for the next one.

`q` leaves, any other key pauses.

## The other modes

- **PRACTICE** — a free run across the whole library, no trace.
- **DRILL** — built from *your* per-key error history, plus raw punctuation
  lines, which is the part of shell typing that really hurts. Targeting is
  guaranteed, not a weighted coin flip.
- **CODEX** — every tool, what it does, and how cleanly you type it.
- **STATS** — WPM over time, and per-key accuracy and reaction time.

## Feedback while you type

Correct characters turn green. A mistake shows **the character you should have
hit**, on red, at the moment you get it wrong.

Metrics are the standard ones: a "word" is 5 characters, net WPM counts only
what stands correct, accuracy counts keystrokes (backspacing a typo fixes the
text but not your accuracy), consistency is the coefficient of variation of
your per-second speed.

### Controls

| key | action |
| --- | --- |
| type | the command shown |
| `TAB` | reveal the answer during recall |
| `BACKSPACE` | correct a mistake (unless the lesson says otherwise) |
| `ctrl-N` / `PageDown` | skip the current teaching step |
| `ESC` | leave a lesson — `q` is a character you have to type |

Profile: `$XDG_DATA_HOME/l33t/profile.json` (`~/.local/share/l33t/`).

## Layout

Game logic is free of curses and of I/O, so it's testable headlessly:

| file | role |
| --- | --- |
| `l33t/engine.py` | typing session, WPM/accuracy/consistency, per-key stats |
| `l33t/shell.py` | the library: problem, command, explanation, decomposition |
| `l33t/modes.py` | the path, its modifiers, challenge budgets |
| `l33t/stats.py` | profile: keys, tools, lessons, history |
| `l33t/play.py` | the typing view, calm/timed run loop |
| `l33t/screens.py` | the five lesson phases, path browser, codex |
| `l33t/demos.py` | sample runs: what each command prints |
| `l33t/akari.py` | あかり's copy, in one place so the persona stays consistent |
| `l33t/effects.py` | decrypt / typewriter effects, as pure timing functions |
| `l33t/ui.py` | curses primitives |

Every decomposition is checked to reassemble into its exact command, so a
breakdown can't drift away from what it describes.

The text effects are implemented natively against the curses frame loop rather
than taken from a terminal-effects library: those own stdout and run their own
frame loop, so they can't be composited into a curses window or interrupted by
a keypress. Writing them as pure `state(i, elapsed)` functions keeps them
skippable, deterministic (a frame redrawn at the same time looks identical),
and testable without a terminal.

### Optional: terminaltexteffects

For the one place a library effect *does* fit — the boot flourish, which is a
single non-interactive moment — L33T will use
[terminaltexteffects](https://github.com/ChrisBuilds/terminaltexteffects) if
it's installed, picking at random from 17 of its effects each launch:

```bash
uv sync --extra effects
```

It works by suspending curses (`def_prog_mode` / `endwin`), handing TTE the
terminal, then restoring. Entirely optional — without it the native typewriter
runs instead, and a missing or failing effect can never take the game down.

```bash
uv run pytest
```
