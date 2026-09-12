"""The command library.

Every command carries three things beyond its text: the PROBLEM it solves,
a one-line summary, and a PART-BY-PART decomposition. The lesson flow poses
the problem first, explains the pieces, and only then asks you to type it --
so you learn a tool rather than memorising a string.

Invariant: " ".join(part.text for part in parts) == command.text. The tests
enforce it, which keeps a decomposition from drifting away from its command.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from .demos import DEMOS

MAX_WIDTH = 58
DEMO_WIDTH = 66


@dataclass(frozen=True)
class Part:
    text: str          # the fragment, exactly as it appears
    means: str         # what that fragment does
    glue: str = " "    # what separates it from the previous part
    # True for a fragment whose exact text is an arbitrary value -- a path,
    # filename, host, URL -- rather than something to learn. Recall shows
    # these already: the point is remembering the command and its flags,
    # not memorising a generated filename.
    given: bool = False


@dataclass(frozen=True)
class Command:
    text: str
    problem: str          # the task, posed before anything is shown
    explain: str          # one-line summary
    tool: str
    parts: tuple[Part, ...]
    # A sample run. Lines beginning "$ " are follow-up commands, used when
    # this command prints nothing of its own.
    demo: tuple[str, ...] = ()


@dataclass(frozen=True)
class Lesson:
    key: str
    name: str
    blurb: str
    commands: tuple[Command, ...]

    @property
    def tools(self) -> list[str]:
        return list(dict.fromkeys(c.tool for c in self.commands))


def _C(text, problem, explain, tool, parts):
    """parts entries are (fragment, meaning) or (fragment, meaning, glue)."""
    return Command(text, problem, explain, tool,
                   tuple(Part(*p) for p in parts))


def reassemble(command: "Command") -> str:
    """Rebuild a command from its parts. Must equal the original -- that's
    what stops a decomposition drifting away from what it describes."""
    if not command.parts:
        return ""
    out = [command.parts[0].text]
    for part in command.parts[1:]:
        out.append(part.glue + part.text)
    return "".join(out)


LESSONS: tuple[Lesson, ...] = (
    Lesson("files", "FILES & NAVIGATION",
           "Seeing what's there, and moving it without losing it.", (
        _C("ls -lah --group-directories-first",
           "You've landed in an unfamiliar directory. What's actually in it,"
           " hidden files included?",
           "long listing, human sizes, hidden files, folders first", "ls", [
            ("ls", "list directory contents"),
            ("-lah", "-l long form, -a include hidden, -h human sizes"),
            ("--group-directories-first", "folders at the top, files below"),
           ]),
        _C("du -sh * | sort -rh | head -10",
           "The disk is filling up. Which things in this folder are the"
           " biggest?",
           "the ten largest items here, biggest first", "du", [
            ("du -sh *", "total size of each item, -s summarised, -h readable"),
            ("|", "feed that list into the next command"),
            ("sort -rh", "-h understands '2.4G', -r puts the largest first"),
            ("|", "and pass the sorted list on again"),
            ("head -10", "keep only the first ten lines"),
           ]),
        _C("mkdir -p build/{bin,lib,include}",
           "You need a whole directory tree, several levels deep, in one go.",
           "create a nested tree with brace expansion", "mkdir", [
            ("mkdir", "make directories"),
            ("-p", "create missing parents, and don't complain if it exists"),
            ("build/{bin,lib,include}", "the shell expands this to three paths",
             " ", True),
           ]),
        _C("cp -av config.yaml config.yaml.bak",
           "Before editing a config, you want a backup that is genuinely"
           " identical -- permissions and timestamps too.",
           "copy preserving everything, and say what it did", "cp", [
            ("cp", "copy"),
            ("-av", "-a preserve mode/owner/timestamps, -v print each copy"),
            ("config.yaml", "the source", " ", True),
            ("config.yaml.bak", "the destination", " ", True),
           ]),
        _C("ln -sfn /opt/app/releases/v3 /opt/app/current",
           "A new release is unpacked. Switch 'current' to it without a gap"
           " where the path doesn't exist.",
           "atomically repoint a symlink -- the classic deploy trick", "ln", [
            ("ln", "create a link"),
            ("-sfn", "-s symbolic, -f replace, -n don't follow the old link"),
            ("/opt/app/releases/v3", "what it should point at", " ", True),
            ("/opt/app/current", "the link itself", " ", True),
           ]),
        _C("rm -i -- -weirdly-named-file",
           "A file's name begins with a dash, so every command thinks it's"
           " an option. How do you delete it?",
           "-- ends option parsing, making a leading dash safe", "rm", [
            ("rm", "remove"),
            ("-i", "ask before each deletion"),
            ("--", "everything after this is a filename, not an option"),
            ("-weirdly-named-file", "now treated as a name", " ", True),
           ]),
    )),

    Lesson("inspect", "READING FILES",
           "Looking inside a file without opening an editor.", (
        _C("tail -f -n 100 app.log",
           "A service is misbehaving right now. You want to watch its log"
           " live, with a bit of history for context.",
           "last 100 lines, then follow as it grows", "tail", [
            ("tail", "show the end of a file"),
            ("-f", "follow: keep printing as new lines arrive"),
            ("-n 100", "start with the last 100 lines"),
            ("app.log", "the file to watch", " ", True),
           ]),
        _C("head -n 20 /var/log/syslog",
           "A log is far too big to open. You just want to see how it"
           " starts.",
           "the first 20 lines", "head", [
            ("head", "show the beginning of a file"),
            ("-n 20", "how many lines to show from the top"),
            ("/var/log/syslog", "the file", " ", True),
           ]),
        _C("wc -l < access.log",
           "How many requests are in this log? You want the number alone,"
           " with no filename cluttering it.",
           "count lines; redirecting hides the filename", "wc", [
            ("wc", "count lines, words and bytes"),
            ("-l", "count lines only, not words or bytes"),
            ("<", "feed the file in on stdin, so wc never learns its name"),
            ("access.log", "the file", " ", True),
           ]),
        _C("stat -c '%s %Y %n' *.tar.gz",
           "You want size and modification time for a set of files, in a"
           " layout you can feed to another script.",
           "custom-formatted file metadata", "stat", [
            ("stat", "show file metadata"),
            ("-c", "use a custom output format"),
            ("'%s %Y %n'", "%s size, %Y mtime as a number, %n name"),
            ("*.tar.gz", "every matching file", " ", True),
           ]),
        _C("diff -u old.conf new.conf",
           "Two versions of a config behave differently. What actually"
           " changed?",
           "unified diff -- the format patches are written in", "diff", [
            ("diff", "compare two files line by line"),
            ("-u", "unified format, with context lines around each change"),
            ("old.conf", "the original", " ", True),
            ("new.conf", "the new version", " ", True),
           ]),
        _C("file -i unknown.bin",
           "Someone hands you a file with a meaningless name. What is it?",
           "identify a file by its contents, not its extension", "file", [
            ("file", "identify a file's type by inspecting its bytes"),
            ("-i", "report it as a MIME type and encoding"),
            ("unknown.bin", "the mystery file", " ", True),
           ]),
    )),

    Lesson("find", "FINDING THINGS",
           "Locating files by name, age or content -- then acting on them.", (
        _C("find . -type f -name '*.py' -newermt '-2 days'",
           "You were working on something on Friday and can't remember which"
           " files you touched.",
           "python files modified in the last two days", "find", [
            ("find", "walk a directory tree"),
            (".", "starting here", " ", True),
            ("-type f", "regular files only, not directories"),
            ("-name '*.py'", "quoted so find expands it, not the shell"),
            ("-newermt '-2 days'", "modified more recently than two days ago"),
           ]),
        _C("grep -rn --include='*.go' 'TODO' .",
           "How much unfinished work is hiding in the codebase, and where"
           " exactly?",
           "recursive search with line numbers, one file type", "grep", [
            ("grep", "search text for a pattern"),
            ("-rn", "-r recurse into directories, -n show line numbers"),
            ("--include='*.go'", "only look inside matching filenames"),
            ("'TODO'", "the pattern"),
            (".", "where to search", " ", True),
           ]),
        _C("find . -name '*.tmp' -print0 | xargs -0 rm -f",
           "You need to delete hundreds of scattered temp files -- and some"
           " of the paths contain spaces.",
           "-print0 and -0 pair up to survive spaces in names", "xargs", [
            ("find . -name '*.tmp'", "locate the files"),
            ("-print0", "separate results with a null byte, not a newline"),
            ("|", "pipe them along"),
            ("xargs -0", "read null-separated input and build arguments"),
            ("rm -f", "the command xargs runs on them"),
           ]),
        _C("grep -v '^#' /etc/ssh/sshd_config | grep .",
           "A config file is mostly commentary. What is it actually"
           " configuring?",
           "strip comments, then strip the blank lines left behind", "grep", [
            ("grep -v", "-v inverts the match: print lines that DON'T match"),
            ("'^#'", "^ anchors to line start, so: lines beginning with #"),
            ("/etc/ssh/sshd_config", "the file", " ", True),
            ("|", "pass what survived onward"),
            ("grep .", "'.' is any character, so this drops empty lines"),
           ]),
        _C("grep -c ERROR app.log",
           "Is this log getting worse? You want a number, not pages of"
           " output.",
           "count matching lines instead of printing them", "grep", [
            ("grep", "search"),
            ("-c", "print a count of matching lines"),
            ("ERROR", "the pattern"),
            ("app.log", "the file", " ", True),
           ]),
        _C("find /var -size +100M -exec ls -lh {} +",
           "Something under /var is huge. Find the offenders and show their"
           " details in one pass.",
           "big files, batched into as few ls calls as possible", "find", [
            ("find /var", "search under /var"),
            ("-size +100M", "larger than 100 megabytes"),
            ("-exec ls -lh", "run this command on the matches"),
            ("{} +", "{} is the matches; + batches many per call, not one"),
           ]),
    )),

    Lesson("text", "TEXT PROCESSING",
           "The classic filters. This is where the shell earns its keep.", (
        _C("sort access.log | uniq -c | sort -rn",
           "Which lines appear most often in this log? This is the single"
           " most reused pipeline in the shell.",
           "the canonical count-and-rank pipeline", "uniq", [
            ("sort access.log", "uniq only sees adjacent duplicates, so sort first"),
            ("|", "pipe"),
            ("uniq -c", "collapse duplicates, prefixing each with its count"),
            ("|", "pipe"),
            ("sort -rn", "-n sort those counts as numbers, -r highest first"),
           ]),
        _C("awk -F: '$3 >= 1000 {print $1}' /etc/passwd",
           "You want the real human accounts on a machine, not the dozens of"
           " system ones.",
           "colon-separated fields: names of users with uid >= 1000", "awk", [
            ("awk", "field-aware text processing"),
            ("-F:", "split each line on colons"),
            ("'$3 >= 1000", "a condition on the third field, the uid"),
            ("{print $1}'", "the action: print the first field, the name"),
            ("/etc/passwd", "the file", " ", True),
           ]),
        _C("sed -i.bak 's/localhost/0.0.0.0/g' config.yaml",
           "One value needs replacing throughout a config, and you want a"
           " safety copy in case you get it wrong.",
           "edit in place, keeping a .bak of the original", "sed", [
            ("sed", "stream editor"),
            ("-i.bak", "edit the file in place, saving the original as .bak"),
            ("'s/localhost/0.0.0.0/g'", "substitute, /g for every occurrence"),
            ("config.yaml", "the file", " ", True),
           ]),
        _C("cut -d, -f1,3 data.csv",
           "A CSV has twenty columns and you need two of them.",
           "keep the first and third comma-separated fields", "cut", [
            ("cut", "select parts of each line"),
            ("-d,", "the delimiter is a comma"),
            ("-f1,3", "keep fields 1 and 3"),
            ("data.csv", "the file", " ", True),
           ]),
        _C("awk '{sum += $2} END {print sum}' sizes.txt",
           "You need the total of a column of numbers.",
           "accumulate a column, print it once at the end", "awk", [
            ("awk", "process line by line"),
            ("'{sum += $2}", "runs for every line: add the 2nd field"),
            ("END {print sum}'", "runs once, after the last line"),
            ("sizes.txt", "the file", " ", True),
           ]),
        _C("jq -r '.items[] | .id' data.json",
           "An API returned JSON and you want one field from every item, as"
           " plain lines.",
           "extract a field from each element of an array", "jq", [
            ("jq", "query and reshape JSON"),
            ("-r", "raw output: no surrounding quotes"),
            ("'.items[]", "iterate over every element of the items array"),
            ("| .id'", "jq has its own pipe, inside the quotes"),
            ("data.json", "the file", " ", True),
           ]),
    )),

    Lesson("pipes", "PIPES & REDIRECTION",
           "Wiring commands together and steering their output.", (
        _C("make 2>&1 | tee build.log",
           "A build is failing. You want to watch it scroll AND keep the"
           " whole thing, error messages included.",
           "merge stderr into stdout, watch it and save it", "tee", [
            ("make", "the command producing output"),
            ("2>&1", "send stderr (2) to wherever stdout (1) currently goes"),
            ("|", "pipe carries stdout only -- hence the line above"),
            ("tee build.log", "write to the file AND pass it through to screen"),
           ]),
        _C("./run.sh > out.txt 2> err.txt",
           "You want a script's normal output and its errors in separate"
           " files.",
           "stdout and stderr to different destinations", "redirection", [
            ("./run.sh", "the command", " ", True),
            ("> out.txt", "redirect stdout; > truncates, >> would append"),
            ("2> err.txt", "redirect stderr, which is file descriptor 2"),
           ]),
        _C("diff <(sort a.txt) <(sort b.txt)",
           "Two files hold the same items in a different order. Compare their"
           " contents, not their ordering.",
           "process substitution: treat output as a file", "bash", [
            ("diff", "expects two filenames"),
            ("<(sort a.txt)", "run this and hand diff a file-like handle to it"),
            ("<(sort b.txt)", "and the same for the second file"),
           ]),
        _C("command -v rg >/dev/null 2>&1 || echo missing",
           "A script should use a faster tool if it's installed -- without"
           " printing anything while it checks.",
           "test for a tool silently, and react if it's absent", "command", [
            ("command -v rg", "print rg's path, and succeed only if it exists"),
            (">/dev/null", "throw the path away; we only want the exit status"),
            ("2>&1", "and silence any error message too"),
            ("||", "run what follows only if the left side FAILED"),
            ("echo missing", "the fallback"),
           ]),
        _C("grep -m5 FATAL huge.log",
           "You only need to know whether a huge file contains something --"
           " reading all of it is a waste.",
           "stop after the first five matches", "grep", [
            ("grep", "search"),
            ("-m5", "stop reading after 5 matches"),
            ("FATAL", "the pattern"),
            ("huge.log", "the file", " ", True),
           ]),
        _C("printf '%s\\n' one two three | nl",
           "You want a list of values turned into numbered lines.",
           "printf reuses its format; nl numbers the result", "printf", [
            ("printf", "formatted output, safer than echo"),
            ("'%s\\n'", "one string then a newline -- reused for each argument"),
            ("one two three", "three arguments, so the format runs three times"),
            ("| nl", "number the lines"),
           ]),
    )),

    Lesson("perms", "PERMISSIONS & OWNERSHIP",
           "Who can read, write and run what -- and how to fix it safely.", (
        _C("chmod 600 ~/.ssh/id_ed25519",
           "SSH refuses your key with 'permissions are too open'.",
           "a private key must be readable only by you", "chmod", [
            ("chmod", "change permission bits"),
            ("600", "owner read+write, group none, others none"),
            ("~/.ssh/id_ed25519", "the private key", " ", True),
           ]),
        _C("chmod u+x,go-w deploy.sh",
           "Make a script runnable by you, while making sure nobody else can"
           " edit what you're about to run.",
           "symbolic modes change bits without restating them all", "chmod", [
            ("chmod", "change permissions"),
            ("u+x,go-w", "u=user g=group o=others; + adds, - removes"),
            ("deploy.sh", "the script", " ", True),
           ]),
        _C("chown -R deploy:deploy /srv/www",
           "A directory tree was unpacked as root and the service account"
           " can't write to it.",
           "recursively set owner and group", "chown", [
            ("chown", "change ownership"),
            ("-R", "recurse into the whole tree"),
            ("deploy:deploy", "user:group"),
            ("/srv/www", "the tree", " ", True),
           ]),
        _C("find . -type f -perm /o+w -ls",
           "Audit a project for files anyone on the system could modify.",
           "list world-writable files -- usually a mistake", "find", [
            ("find .", "search here"),
            ("-type f", "regular files only, skip directories"),
            ("-perm /o+w", "/ means 'any of these bits'; o+w is other-writable"),
            ("-ls", "print full details for each match"),
           ]),
        _C("umask 027",
           "Everything you create is readable by the whole machine. Change"
           " the default.",
           "mask the bits new files must not have", "umask", [
            ("umask", "set default permissions for newly created files"),
            ("027", "subtracted: group loses write, others lose everything"),
           ]),
        _C("sudo -u postgres psql -c '\\l'",
           "Run one database command as the service account, without opening"
           " a shell as that user.",
           "run a single command as another user", "sudo", [
            ("sudo", "run as another user"),
            ("-u postgres", "which user -- not root"),
            ("psql", "the command"),
            ("-c '\\l'", "psql's own flag: run this and exit"),
           ]),
    )),

    Lesson("procs", "PROCESSES & JOBS",
           "Seeing what's running, and making it stop.", (
        _C("ps aux --sort=-%mem | head -5",
           "The machine is swapping. What's eating the memory?",
           "the five hungriest processes by memory", "ps", [
            ("ps aux", "every process, from every user, with details"),
            ("--sort=-%mem", "sort by memory; the minus means descending"),
            ("| head -5", "just the top five"),
           ]),
        _C("kill -9 $(lsof -t -i:8080)",
           "You restart your server and it says 'address already in use'.",
           "force-kill whatever still holds port 8080", "lsof", [
            ("kill -9", "SIGKILL: cannot be caught or ignored, so use it last"),
            ("$(", "command substitution: run this first, use its output here"),
            ("lsof -t -i:8080", "-i select by port, -t print only the pid", ""),
            (")", "closes the substitution", ""),
           ]),
        _C("nohup ./worker.sh > worker.log 2>&1 &",
           "Start a long job over SSH that must survive you closing the"
           " laptop.",
           "detach from the terminal and keep the output", "nohup", [
            ("nohup", "ignore the hangup signal sent when the terminal closes"),
            ("./worker.sh", "the job", " ", True),
            ("> worker.log", "capture its output, since you won't be watching"),
            ("2>&1", "errors too"),
            ("&", "run it in the background and give the prompt back"),
           ]),
        _C("pgrep -af nginx",
           "Is that service actually running, and with which arguments?",
           "find processes by name, showing the full command line", "pgrep", [
            ("pgrep", "find process ids by name"),
            ("-af", "-a show the full command line, -f match against all of it"),
            ("nginx", "the name to match"),
           ]),
        _C("timeout 30s ./flaky-check.sh",
           "A health check sometimes hangs forever and blocks your script.",
           "kill it if it hasn't finished in time", "timeout", [
            ("timeout", "run a command with a time limit"),
            ("30s", "the limit"),
            ("./flaky-check.sh", "the command", " ", True),
           ]),
        _C("journalctl -u nginx --since '1 hour ago' -f",
           "A service just started failing. What has it been saying?",
           "follow one service's recent logs", "journalctl", [
            ("journalctl", "query the systemd journal"),
            ("-u nginx", "restrict output to this systemd unit"),
            ("--since '1 hour ago'", "accepts plain English time expressions"),
            ("-f", "follow new entries as they arrive"),
           ]),
    )),

    Lesson("net", "NETWORKING",
           "Reaching other machines, and working out why you can't.", (
        _C("curl -sS -o /dev/null -w '%{http_code}\\n' https://x.io",
           "Is this endpoint healthy? You want the status code and nothing"
           " else -- no body, no progress bar.",
           "fetch quietly and print only the status code", "curl", [
            ("curl", "transfer data over HTTP"),
            ("-sS", "-s silence the progress meter, -S but still show errors"),
            ("-o /dev/null", "discard the response body"),
            ("-w '%{http_code}\\n'", "after the transfer, print just this"),
            ("https://x.io", "the URL", " ", True),
           ]),
        _C("ssh -i ~/.ssh/id_ed25519 -p 2222 deploy@10.0.42.7",
           "Connect to a host that uses a non-standard port and a key that"
           " isn't your default.",
           "connect with a specific key on a custom port", "ssh", [
            ("ssh", "secure shell"),
            ("-i ~/.ssh/id_ed25519", "which private key to offer"),
            ("-p 2222", "which port -- lowercase p on ssh"),
            ("deploy@10.0.42.7", "user@host", " ", True),
           ]),
        _C("ssh -L 5432:localhost:5432 bastion",
           "A database is only reachable from a jump host. You want to query"
           " it from your laptop.",
           "tunnel a remote port to your own machine", "ssh", [
            ("ssh", "secure shell"),
            ("-L", "local forward: open a port here, tunnel it there"),
            ("5432:localhost:5432", "myport:host-as-seen-by-bastion:itsport"),
            ("bastion", "the host you can actually reach", " ", True),
           ]),
        _C("ss -tulpn | grep LISTEN",
           "Something is bound to a port and you don't know what.",
           "every listening socket and the process behind it", "ss", [
            ("ss", "socket statistics, the modern netstat"),
            ("-tulpn", "t tcp, u udp, l listening, p process, n numeric ports"),
            ("| grep LISTEN", "keep only the listening sockets"),
           ]),
        _C("dig +short AAAA example.com",
           "You need a domain's IPv6 address, without a screenful of DNS"
           " ceremony.",
           "just the answer, nothing else", "dig", [
            ("dig", "DNS lookup tool"),
            ("+short", "print only the answer"),
            ("AAAA", "the IPv6 record type; A would be IPv4"),
            ("example.com", "the name to look up", " ", True),
           ]),
        _C("nc -zv db.internal 5432",
           "Before blaming the database, check whether you can even reach its"
           " port.",
           "test a port without sending any data", "nc", [
            ("nc", "netcat: raw TCP/UDP connections"),
            ("-zv", "-z just scan, send nothing; -v say what happened"),
            ("db.internal", "the host", " ", True),
            ("5432", "the port"),
           ]),
    )),

    Lesson("git", "GIT",
           "The commands you use daily, plus the ones that save you.", (
        _C("git switch -c feature/typing-modes",
           "Start work on something new without touching the branch you're"
           " on.",
           "create a branch and move to it", "git", [
            ("git switch", "change branches -- the modern, clearer checkout"),
            ("-c", "create the branch first"),
            ("feature/typing-modes", "the new branch name", " ", True),
           ]),
        _C("git add -p src/engine.py",
           "You fixed a bug and left some debug prints. Commit only the fix.",
           "stage selected hunks, not whole files", "git", [
            ("git add", "stage changes for the next commit"),
            ("-p", "patch mode: walk each hunk and choose y/n"),
            ("src/engine.py", "limit it to this file", " ", True),
           ]),
        _C("git commit --amend --no-edit",
           "You committed, then immediately spotted a typo. You don't want a"
           " second 'fix typo' commit.",
           "fold staged changes into the previous commit", "git", [
            ("git commit", "record staged changes"),
            ("--amend", "replace the last commit instead of adding one"),
            ("--no-edit", "keep the existing message"),
           ]),
        _C("git rebase -i HEAD~3",
           "Your branch has three messy commits. Tidy them before anyone"
           " sees.",
           "reorder, squash or reword recent commits", "git", [
            ("git rebase", "replay commits onto a new base"),
            ("-i", "interactive: choose what happens to each one"),
            ("HEAD~3", "the last three commits"),
           ]),
        _C("git push --force-with-lease origin HEAD",
           "You rebased, so a normal push is rejected -- but a plain --force"
           " could destroy a colleague's work.",
           "force push that refuses to clobber someone else's commits", "git", [
            ("git push", "send commits to the remote"),
            ("--force-with-lease", "refuse if the remote moved since you fetched"),
            ("origin", "the remote"),
            ("HEAD", "the current branch"),
           ]),
        _C("git bisect start HEAD v1.2.0",
           "Something broke somewhere in the last 200 commits and you have no"
           " idea where.",
           "binary-search history for the commit that broke it", "git", [
            ("git bisect start", "begin a binary search through history"),
            ("HEAD", "a commit known to be broken"),
            ("v1.2.0", "a commit known to be good"),
           ]),
    )),

    Lesson("archive", "ARCHIVES & TRANSFER",
           "Packing, unpacking and moving bytes around reliably.", (
        _C("tar -czf backup-$(date +%F).tar.gz /var/lib/node",
           "Take a compressed backup whose filename says when it was made.",
           "gzip archive stamped with today's date", "tar", [
            ("tar", "create and extract archives"),
            ("-czf", "c create, z gzip it, f the filename follows"),
            ("backup-$(date +%F).tar.gz", "$(...) inserts 2026-09-11"),
            ("/var/lib/node", "what to archive", " ", True),
           ]),
        _C("tar -xzf release.tar.gz -C /opt/app --strip-components=1",
           "A release tarball wraps everything in a top-level folder you"
           " don't want.",
           "extract elsewhere, dropping the wrapper directory", "tar", [
            ("tar", "archive tool"),
            ("-xzf", "x extract, z gunzip, f from this file"),
            ("release.tar.gz", "the archive", " ", True),
            ("-C /opt/app", "change to this directory before extracting"),
            ("--strip-components=1", "discard the first path component"),
           ]),
        _C("rsync -avz --delete --dry-run ./dist/ edge:/srv/www/",
           "You're about to sync a build to production with --delete. Check"
           " what it would remove first.",
           "always dry-run a --delete sync", "rsync", [
            ("rsync", "efficient file sync"),
            ("-avz", "a preserve everything, v verbose, z compress in transit"),
            ("--delete", "remove remote files that no longer exist locally"),
            ("--dry-run", "change nothing; just report what would happen"),
            ("./dist/", "the trailing slash means 'contents of', not the folder"),
            ("edge:/srv/www/", "host:path destination", " ", True),
           ]),
        _C("rsync -avzP --partial big.iso backup:/data/",
           "A huge transfer keeps dying halfway over a bad connection.",
           "resumable transfer with progress", "rsync", [
            ("rsync", "file sync"),
            ("-avzP", "P = --partial plus --progress"),
            ("--partial", "keep what transferred so a rerun resumes"),
            ("big.iso", "the file", " ", True),
            ("backup:/data/", "the destination", " ", True),
           ]),
        _C("zcat access.log.gz | grep -c 500",
           "Count errors in a rotated log without unpacking a gigabyte to"
           " disk.",
           "read a compressed file as a stream", "zcat", [
            ("zcat", "decompress to stdout, leaving the file alone"),
            ("access.log.gz", "the compressed log", " ", True),
            ("| grep -c 500", "count matching lines in the stream"),
           ]),
        _C("split -b 100M big.bin part-",
           "An upload limit is 100MB and your file is 2GB.",
           "chop a file into fixed-size pieces", "split", [
            ("split", "break a file into pieces"),
            ("-b 100M", "100 megabytes each"),
            ("big.bin", "the source", " ", True),
            ("part-", "prefix, giving part-aa, part-ab, ...", " ", True),
           ]),
    )),

    Lesson("script", "SHELL SCRIPTING",
           "The syntax that turns a command line into a program.", (
        _C("set -euo pipefail",
           "Your deploy script failed in the middle but exited 0 and carried"
           " on. Make that impossible.",
           "the first line of every serious bash script", "bash", [
            ("set", "change shell options"),
            ("-euo", "e exit on error, u error on unset vars, o sets the next"),
            ("pipefail", "a pipeline fails if ANY command in it fails"),
           ]),
        _C("for f in *.md; do echo \"${f%.md}\"; done",
           "Rename or process a set of files, using each name without its"
           " extension.",
           "loop over files, stripping the suffix", "bash", [
            ("for f in *.md;", "f takes each matching filename in turn"),
            ("do", "the body starts"),
            ("echo \"${f%.md}\";", "%.md removes that suffix from the end"),
            ("done", "the body ends"),
           ]),
        _C("while read -r line; do echo \"$line\"; done < in.txt",
           "Process a file one line at a time, safely -- including lines with"
           " backslashes.",
           "the correct way to read a file line by line", "bash", [
            ("while read -r line;", "-r stops backslashes being interpreted"),
            ("do echo \"$line\";", "quote it, or the shell splits the line up"),
            ("done", "end of loop"),
            ("< in.txt", "feed the file into the loop's stdin"),
           ]),
        _C("count=$(grep -c ERROR app.log)",
           "You need a command's output as a value you can test and print.",
           "capture command output into a variable", "bash", [
            ("count=", "assignment -- no spaces around the equals sign"),
            ("$(grep -c ERROR app.log)", "run this, substitute its output", ""),
           ]),
        _C("trap 'rm -f \"$tmp\"' EXIT",
           "Your script makes a temp file and sometimes dies before deleting"
           " it.",
           "clean up no matter how the script ends", "bash", [
            ("trap", "run something when a signal or event arrives"),
            ("'rm -f \"$tmp\"'", "the cleanup, quoted so it runs later, not now"),
            ("EXIT", "on any exit -- success, failure or interrupt"),
           ]),
        _C("echo \"${NAME:-anonymous}\"",
           "A variable might be unset, and you want a sensible default rather"
           " than an empty string.",
           "use a fallback when a variable is empty or unset", "bash", [
            ("echo", "print"),
            ("\"${NAME:-anonymous}\"", ":- supplies a default; := would also assign"),
           ]),
    )),
)

# Attach the sample runs, kept in their own module so the lesson definitions
# above stay readable.
LESSONS = tuple(
    replace(lesson, commands=tuple(
        replace(c, demo=DEMOS.get(c.text, ())) for c in lesson.commands))
    for lesson in LESSONS)

LESSON_BY_KEY = {lesson.key: lesson for lesson in LESSONS}
ALL_COMMANDS: tuple[Command, ...] = tuple(c for l in LESSONS for c in l.commands)
ALL_TOOLS: tuple[str, ...] = tuple(dict.fromkeys(c.tool for c in ALL_COMMANDS))

TOOL_SUMMARY = {
    "ls": "list directory contents",
    "du": "disk usage per file or directory",
    "mkdir": "create directories",
    "cp": "copy files and directories",
    "ln": "create links, usually symbolic",
    "rm": "delete files",
    "tail": "end of a file, optionally following",
    "head": "beginning of a file",
    "wc": "count lines, words and bytes",
    "stat": "detailed file metadata",
    "diff": "compare files line by line",
    "file": "identify a file's type by content",
    "find": "walk a tree, filtering and acting on matches",
    "grep": "search text with patterns",
    "xargs": "turn input into arguments for another command",
    "uniq": "collapse or count adjacent duplicates",
    "awk": "field-aware text processing language",
    "sed": "stream editor for substitutions and ranges",
    "cut": "select columns from delimited text",
    "jq": "query and reshape JSON",
    "tee": "write to a file and pass output along",
    "redirection": "steer stdin, stdout and stderr",
    "bash": "the shell's own syntax",
    "command": "run or test for a command, bypassing aliases",
    "printf": "formatted output, safer than echo",
    "chmod": "change permission bits",
    "chown": "change owner and group",
    "umask": "default permissions for new files",
    "sudo": "run as another user",
    "ps": "snapshot of running processes",
    "lsof": "list open files and sockets",
    "nohup": "run immune to terminal hangups",
    "pgrep": "find processes by name",
    "timeout": "run with a time limit",
    "journalctl": "query systemd logs",
    "curl": "transfer data over HTTP and friends",
    "ssh": "secure shell, and tunnels",
    "ss": "socket statistics",
    "dig": "DNS lookups",
    "nc": "raw TCP/UDP connections",
    "git": "version control",
    "tar": "create and extract archives",
    "rsync": "efficient, resumable sync",
    "zcat": "read a compressed file as a stream",
    "split": "break a file into pieces",
}

SYMBOLS = "!@#$%^&*()[]{}<>-_=+/\\|;:'\",.?~`"


def lesson_commands(lesson: Lesson, count: int,
                    rng: random.Random) -> list[Command]:
    pool = list(lesson.commands)
    rng.shuffle(pool)
    out = []
    while len(out) < count:
        if not pool:
            pool = list(lesson.commands)
            rng.shuffle(pool)
        out.append(pool.pop())
    return out


WEAK_SHARE = 0.6


def sample_commands(count: int, rng: random.Random,
                    weak: list[str] | None = None) -> list[Command]:
    """Commands from the whole library, with slots reserved for weak keys."""
    pool = list(ALL_COMMANDS)
    rng.shuffle(pool)
    picked: list[Command] = []
    seen: set[str] = set()

    if weak:
        hot = set(weak)
        quota = min(count, int(round(count * WEAK_SHARE)))
        for c in pool:
            if len(picked) >= quota:
                break
            if hot & set(c.text) and c.text not in seen:
                picked.append(c)
                seen.add(c.text)

    for c in pool:
        if len(picked) >= count:
            break
        if c.text not in seen:
            picked.append(c)
            seen.add(c.text)

    while len(picked) < count:
        picked.append(rng.choice(ALL_COMMANDS))
    rng.shuffle(picked)
    return picked


def symbol_drill(rng: random.Random, weak: list[str], width: int = 44) -> str:
    charset = SYMBOLS + "".join(c for c in weak if c in SYMBOLS) * 5
    groups, length = [], 0
    while length < width:
        group = "".join(rng.choice(charset) for _ in range(rng.randint(2, 4)))
        if length + len(group) + 1 > width:
            break
        groups.append(group)
        length += len(group) + 1
    return " ".join(groups) if groups else rng.choice(SYMBOLS) * 3


def given_spans(command: Command) -> list[tuple[int, int]]:
    """Character ranges of parts already given away during recall.

    These are the arbitrary values (paths, filenames, hosts...) a lesson
    generates rather than teaches -- shown up front so recall tests whether
    you remember the command, not whether you memorised a filename.
    """
    return [span for part, span in zip(command.parts, part_spans(command))
            if part.given]


def part_spans(command: Command) -> list[tuple[int, int]]:
    """Where each part sits inside the command text.

    Lets the UI highlight the exact characters an explanation refers to,
    instead of listing fragments beside a command and hoping you match them
    up by eye.
    """
    spans, pos = [], 0
    for i, part in enumerate(command.parts):
        if i:
            pos += len(part.glue)
        spans.append((pos, pos + len(part.text)))
        pos += len(part.text)
    return spans
