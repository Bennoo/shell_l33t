"""WATCH mode: an expert working a real shell, endlessly.

Scenes are coherent investigations, not a shuffled command list -- output from
one command motivates the next, the way it does when someone actually knows
what they're doing. Every value (hosts, sizes, pids, addresses, timestamps) is
generated per run, so two viewings never look the same.

Pure data generation: no curses here, so the scenes are testable and the
renderer stays dumb.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from . import akari

MAX_WIDTH = 74


@dataclass(frozen=True)
class Beat:
    """One command and what it printed."""
    prompt: str
    command: str
    output: tuple[str, ...] = ()
    pause: float = 0.85         # beat before the next command is typed
    failed: bool = False
    comment: str = ""           # shown dim above the command, as intent
    mutter: tuple[str, str] = ()  # (japanese, english) note after the output


# --------------------------------------------------------------------------
# Random furniture
# --------------------------------------------------------------------------

# The operator you're watching. Her copy lives in l33t/akari.py so the
# persona stays consistent between WATCH and the lessons.
OPERATOR = akari.NAME
OPERATOR_KANA = akari.KANA

HOSTS = ["shibuya-edge", "kyoto-db01", "akiba-relay", "tokyo-gw",
         "osaka-worker", "sapporo-ci", "nerima-bastion", "shinjuku-node",
         "yokohama-02", "sendai-cache"]

# Short notes she leaves herself. Kept simple and unambiguous, each with an
# English gloss for the renderer to fall back on when the terminal can't do
# Japanese.
# Reactions to something she just read on screen.
DISCOVERY = [
    ("なるほど", "I see"),
    ("見つけた", "found it"),
    ("これだ", "this is it"),
    ("ビンゴ", "bingo"),
]
# Reactions to a command that failed.
SURPRISE = [
    ("おかしい", "that's odd"),
    ("やっぱり", "just as I thought"),
    ("なるほど", "I see"),
]
# Said at the end, once the problem is solved.
CLOSING = [
    ("完了", "done"),
    ("よし", "right then"),
]
# Asked of herself partway through, before she's actually found anything --
# the hypothesis she's chasing with the next command.
QUESTIONS = [
    ("なぜだ", "why though"),
    ("怪しいな", "that's suspicious"),
    ("原因は", "what's the cause"),
    ("さてと", "let's see"),
    ("次は何だ", "what's next"),
]

MUTTERINGS = DISCOVERY + SURPRISE + CLOSING + QUESTIONS
PROJECTS = ["atlas", "helios", "orbit", "vertex", "lumen", "quarry", "pylon"]
SERVICES = ["nginx", "postgres", "redis", "api-gateway", "worker", "ingest"]
BRANCHES = ["main", "develop", "feature/cache-layer", "fix/timeout-retry",
            "release/2.4"]


def _size(rng, lo=1, hi=900, unit=None):
    unit = unit or rng.choice(["K", "M", "M", "G"])
    if unit == "G":
        return f"{rng.uniform(1.0, 9.9):.1f}G"
    return f"{rng.randint(lo, hi)}{unit}"


def _pid(rng):
    return rng.randint(300, 32000)


def _ipv4(rng):
    return f"10.{rng.randint(0,40)}.{rng.randint(0,255)}.{rng.randint(2,254)}"


def _ipv6(rng):
    return "2606:{:x}:{:x}::{:x}".format(rng.randint(0x1000, 0xffff),
                                         rng.randint(0x100, 0xfff),
                                         rng.randint(1, 0xffff))
def _hexid(rng, n=7):
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _clock(rng):
    return f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"


def _date(rng):
    return f"2026-{rng.randint(1,9):02d}-{rng.randint(10,28)}"


@dataclass
class Context:
    """Who we're watching, and where."""
    user: str
    host: str
    cwd: str
    project: str
    rng: random.Random = field(repr=False, default=None)

    @property
    def prompt(self) -> str:
        return f"{self.user}@{self.host}:{self.cwd}"

    def at(self, cwd: str) -> str:
        self.cwd = cwd
        return self.prompt


def make_context(rng: random.Random) -> Context:
    project = rng.choice(PROJECTS)
    return Context(user=OPERATOR, host=rng.choice(HOSTS),
                   cwd=rng.choice([f"~/{project}", "/srv/www", "/var/log",
                                   f"/opt/{project}", "~"]),
                   project=project, rng=rng)


# --------------------------------------------------------------------------
# Scenes
# --------------------------------------------------------------------------


def scene_disk_full(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    p = ctx.at(f"/var/lib/{ctx.project}")
    dirs = rng.sample(["uploads", "cache", "postgres", "artifacts", "tmp",
                       "index", "snapshots", "media"], 5)
    sizes = sorted([rng.uniform(0.4, 18.0) for _ in dirs], reverse=True)
    listing = [f"{s:.1f}G\t{d}" if s >= 1 else f"{int(s*1024)}M\t{d}"
               for s, d in zip(sizes, dirs)]
    pct = rng.randint(91, 99)
    big = dirs[0]
    logs = [f"{big}/{_hexid(rng,6)}.log" for _ in range(3)]
    return [
        Beat(p, "df -h --output=source,pcent,target",
             ("Filesystem     Use% Mounted on",
              f"/dev/nvme0n1p2  {pct}% /",
              "/dev/nvme0n1p1   12% /boot"),
             comment="disk alert on this box -- find out what grew"),
        Beat(p, "du -sh * | sort -rh | head -10", tuple(listing), pause=1.0),
        Beat(p, f"find {big} -size +100M -exec ls -lh {{}} +",
             tuple(f"-rw-r--r-- 1 {ctx.user} {ctx.user} {_size(rng, unit='G')} "
                   f"{_date(rng)} {f}" for f in logs)),
        Beat(p, f"find {big} -name '*.log' -mtime +7 -print0 | xargs -0 rm -f",
             ()),
        Beat(p, "df -h --output=source,pcent,target",
             ("Filesystem     Use% Mounted on",
              f"/dev/nvme0n1p2  {pct - rng.randint(18, 40)}% /",
              "/dev/nvme0n1p1   12% /boot"), pause=1.4),
    ]


def scene_service_down(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    svc = rng.choice(SERVICES)
    port = rng.choice([80, 443, 5432, 6379, 8080, 9090])
    pid = _pid(rng)
    p = ctx.at("~")
    return [
        Beat(p, f"curl -sS -o /dev/null -w '%{{http_code}}\\n' "
                f"http://localhost:{port}/health",
             ("000",), failed=True,
             comment=f"{svc} is not answering -- work out why"),
        Beat(p, "ss -tulpn | grep LISTEN",
             ("Netid State  Local Address:Port   Process",
              f"tcp   LISTEN 0.0.0.0:22           users:((\"sshd\",pid=821))",
              f"tcp   LISTEN 127.0.0.1:{port}        "
              f"users:((\"{svc}\",pid={pid}))")),
        Beat(p, f"journalctl -u {svc} --since '15 min ago' | tail -n 5",
             (f"{_clock(rng)} {ctx.host} {svc}[{pid}]: worker pool exhausted",
              f"{_clock(rng)} {ctx.host} {svc}[{pid}]: upstream timed out",
              f"{_clock(rng)} {ctx.host} {svc}[{pid}]: refusing connections"),
             pause=1.1),
        Beat(p, f"ps aux --sort=-%mem | head -3",
             ("USER   PID  %CPU %MEM    RSS COMMAND",
              f"{ctx.user:<6} {pid} {rng.uniform(80,99):4.1f} "
              f"{rng.uniform(40,78):4.1f} {rng.randint(2,9)}.{rng.randint(0,9)}G {svc}",
              f"root   821  0.0  0.1  12M sshd")),
        Beat(p, f"kill -TERM {pid}", ()),
        Beat(p, f"systemctl start {svc} && sleep 2", ()),
        Beat(p, f"curl -sS -o /dev/null -w '%{{http_code}}\\n' "
                f"http://localhost:{port}/health", ("200",), pause=1.5),
    ]


def scene_deploy(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    rel = f"v{rng.randint(2,5)}.{rng.randint(0,9)}.{rng.randint(0,9)}"
    p = ctx.at(f"~/{ctx.project}")
    files = rng.randint(6, 40)
    return [
        Beat(p, "git log --oneline --graph --decorate -5",
             (f"* {_hexid(rng)} (HEAD -> main, origin/main) cache negative lookups",
              f"* {_hexid(rng)} drop retry on 4xx",
              f"* {_hexid(rng)} bump client timeout to 5s",
              f"* {_hexid(rng)} fix flaky integration test",
              f"* {_hexid(rng)} chore: pin toolchain"),
             comment=f"shipping {rel} to {ctx.host}"),
        Beat(p, "rsync -avz --delete --dry-run ./dist/ edge:/srv/www/",
             ("sending incremental file list",
              *[f"deleting stale/{_hexid(rng,5)}.js" for _ in range(2)],
              f"dist/index.html", f"dist/assets/app.{_hexid(rng,8)}.js",
              f"sent {rng.randint(2,9)},{rng.randint(100,999)} bytes  "
              f"received {rng.randint(20,99)} bytes"),
             pause=1.2),
        Beat(p, "rsync -avz --delete ./dist/ edge:/srv/www/",
             (f"sent {files*1024 + rng.randint(0,999):,} bytes  "
              f"speed {rng.uniform(2,40):.1f}MB/s",
              f"total size is {rng.randint(10,90)}.{rng.randint(0,9)}M")),
        Beat(p, f"ssh edge 'ln -sfn /opt/app/releases/{rel} /opt/app/current'", ()),
        Beat(p, "curl -sS -o /dev/null -w '%{http_code}\\n' https://"
                f"{ctx.project}.io", ("200",), pause=1.5),
    ]


def scene_log_forensics(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    p = ctx.at("/var/log/nginx")
    total = rng.randint(400, 9000)
    codes = [(500, rng.randint(20, 400)), (404, rng.randint(50, 900)),
             (200, rng.randint(4000, 90000))]
    ips = [(_ipv4(rng), rng.randint(40, 4000)) for _ in range(4)]
    ips.sort(key=lambda t: -t[1])
    return [
        Beat(p, "zcat access.log.gz | grep -c ' 500 '", (str(total),),
             comment="spike in 5xx overnight -- find the source"),
        Beat(p, "zcat access.log.gz | awk '{print $9}' | sort | uniq -c | sort -rn",
             tuple(f"{count:>8} {code}" for code, count in
                   sorted(codes, key=lambda c: -c[1])), pause=1.1),
        Beat(p, "awk '$9==500 {print $1}' access.log | sort | uniq -c "
                "| sort -rn | head -4",
             tuple(f"{count:>8} {ip}" for ip, count in ips)),
        Beat(p, f"grep -c '{ips[0][0]}' /etc/nginx/blocklist.conf", ("0",)),
        Beat(p, f"echo 'deny {ips[0][0]};' >> /etc/nginx/blocklist.conf", ()),
        Beat(p, "nginx -t && systemctl reload nginx",
             ("nginx: configuration file /etc/nginx/nginx.conf test is successful",),
             pause=1.4),
    ]


def scene_permissions(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    host = rng.choice(HOSTS)
    p = ctx.at("~")
    return [
        Beat(p, f"ssh -i ~/.ssh/id_ed25519 {ctx.user}@{host}",
             ("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@",
              "@    WARNING: UNPROTECTED PRIVATE KEY FILE!          @",
              "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@",
              "Permissions 0644 for '~/.ssh/id_ed25519' are too open.",
              f"{ctx.user}@{host}: Permission denied (publickey)."),
             failed=True, comment="key rejected after restoring from backup"),
        Beat(p, "stat -c '%A %U:%G %n' ~/.ssh/id_ed25519",
             (f"-rw-r--r-- {ctx.user}:{ctx.user} /home/{ctx.user}/.ssh/id_ed25519",)),
        Beat(p, "chmod 600 ~/.ssh/id_ed25519", ()),
        Beat(p, "stat -c '%A %U:%G %n' ~/.ssh/id_ed25519",
             (f"-rw------- {ctx.user}:{ctx.user} /home/{ctx.user}/.ssh/id_ed25519",)),
        Beat(p, f"ssh -i ~/.ssh/id_ed25519 {ctx.user}@{host} 'uptime'",
             (f" {_clock(rng)} up {rng.randint(1,300)} days, "
              f"{rng.randint(1,40)} users,  load average: "
              f"{rng.uniform(0,3):.2f}, {rng.uniform(0,3):.2f}, "
              f"{rng.uniform(0,3):.2f}",), pause=1.5),
    ]


def scene_port_hunt(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    port = rng.choice([3000, 5432, 8080, 8000, 9000])
    pid = _pid(rng)
    svc = rng.choice(["node", "python3", "java", "ruby", "gunicorn"])
    p = ctx.at(f"~/{ctx.project}")
    return [
        Beat(p, "make serve",
             (f"Error: listen EADDRINUSE: address already in use :::{port}",),
             failed=True, comment="port already bound -- find the squatter"),
        Beat(p, f"lsof -i:{port}",
             ("COMMAND   PID  USER   FD  TYPE  NODE NAME",
              f"{svc:<9} {pid} {ctx.user:<5} 23u  IPv6   TCP *:{port} (LISTEN)")),
        Beat(p, f"ps -p {pid} -o pid,etime,cmd --no-headers",
             (f"{pid}  {rng.randint(1,9)}-{rng.randint(10,23)}:{rng.randint(10,59):02d}"
              f"  {svc} server.js --port {port}",)),
        Beat(p, f"kill -9 $(lsof -t -i:{port})", ()),
        Beat(p, f"lsof -i:{port}", (), failed=True, pause=0.9),
        Beat(p, "make serve",
             (f"listening on http://0.0.0.0:{port}",), pause=1.5),
    ]


def scene_git_tidy(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    branch = rng.choice(BRANCHES[2:])
    n = rng.randint(3, 5)
    p = ctx.at(f"~/{ctx.project}")
    return [
        Beat(p, "git status --short --branch",
             (f"## {branch}...origin/{branch} [ahead {n}]",
              " M src/engine.py", " M tests/test_engine.py"),
             comment="tidy the branch before opening the PR"),
        Beat(p, "git add -p src/engine.py",
             (f"{n} hunks staged, {rng.randint(1,3)} skipped",)),
        Beat(p, "git commit --amend --no-edit",
             (f"[{branch} {_hexid(rng)}] cap keystroke latency outliers",
              f" {rng.randint(1,4)} files changed, "
              f"{rng.randint(10,90)} insertions(+), {rng.randint(1,40)} deletions(-)")),
        Beat(p, f"git rebase -i HEAD~{n}",
             (f"Successfully rebased and updated refs/heads/{branch}.",),
             pause=1.1),
        Beat(p, "git push --force-with-lease origin HEAD",
             (f"To github.com:{ctx.project}/{ctx.project}.git",
              f" + {_hexid(rng)}...{_hexid(rng)} HEAD -> {branch} (forced update)"),
             pause=1.5),
    ]


def scene_net_probe(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    host = f"{rng.choice(['api','db','cache','queue'])}.internal"
    port = rng.choice([443, 5432, 6379, 5672])
    p = ctx.at("~")
    return [
        Beat(p, f"dig +short AAAA {host}", (_ipv6(rng),),
             comment=f"can this box reach {host}?"),
        Beat(p, f"nc -zv {host} {port}",
             (f"Connection to {host} ({_ipv4(rng)}) {port} port [tcp] succeeded!",)),
        Beat(p, f"ss -tulpn | grep :{port}",
             (f"tcp   ESTAB  0  0  {_ipv4(rng)}:{rng.randint(40000,60000)}  "
              f"{_ipv4(rng)}:{port}",)),
        Beat(p, f"openssl s_client -brief -connect {host}:443 </dev/null",
             ("CONNECTION ESTABLISHED",
              "Protocol version: TLSv1.3",
              "Ciphersuite: TLS_AES_256_GCM_SHA384",
              f"Verification: OK",
              f"Peer certificate: CN = {host}"), pause=1.3),
        Beat(p, f"ssh -L {port}:{host}:{port} bastion -N -f", (), pause=1.4),
    ]


def scene_text_crunch(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    p = ctx.at(f"~/{ctx.project}/data")
    rows = rng.randint(1200, 98000)
    users = rng.randint(3, 40)
    return [
        Beat(p, "wc -l < events.csv", (f"{rows}",),
             comment="summarise yesterday's export"),
        Beat(p, "head -n 2 events.csv",
             ("ts,user_id,action,duration_ms",
              f"2026-09-10T{_clock(rng)},{rng.randint(1000,9999)},login,"
              f"{rng.randint(20,900)}")),
        Beat(p, "cut -d, -f3 events.csv | sort | uniq -c | sort -rn | head -4",
             # The command sorts descending, so the output has to be.
             tuple(f"{count:>8} {action}" for count, action in zip(
                 sorted((rng.randint(100, 9000) for _ in range(4)), reverse=True),
                 rng.sample(["view", "login", "search", "export"], 4)))),
        Beat(p, "awk -F, 'NR>1 {sum += $4} END {print sum/NR \" ms avg\"}' events.csv",
             (f"{rng.uniform(40, 900):.2f} ms avg",)),
        Beat(p, f"awk -F: '$3 >= 1000 {{print $1}}' /etc/passwd | wc -l",
             (str(users),), pause=1.4),
    ]


def scene_backup_check(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    p = ctx.at(f"/var/backups/{ctx.project}")
    host = rng.choice(HOSTS)
    fname = f"{ctx.project}-{_date(rng)}.tar.gz"
    size = _size(rng, unit=rng.choice(["M", "G"]))
    return [
        Beat(p, "ls -lh | tail -3",
             (f"-rw-r--r-- 1 {ctx.user} {ctx.user} {_size(rng,unit='M')} "
              f"{_date(rng)} {ctx.project}-{_date(rng)}.tar.gz",
              f"-rw-r--r-- 1 {ctx.user} {ctx.user} {_size(rng,unit='M')} "
              f"{_date(rng)} {ctx.project}-{_date(rng)}.tar.gz",
              f"-rw-r--r-- 1 {ctx.user} {ctx.user} {size} {_date(rng)} {fname}"),
             comment="nightly backup landed -- make sure it isn't empty air"),
        Beat(p, f"tar -tzf {fname} | wc -l", (str(rng.randint(400, 50000)),)),
        Beat(p, f"tar -tzf {fname} | head -3",
             (f"{ctx.project}/config/settings.yml",
              f"{ctx.project}/db/schema.sql",
              f"{ctx.project}/db/dump.sql"), pause=1.0),
        Beat(p, f"scp {fname} {host}:/mnt/offsite/",
             (f"{fname}   100%  {size}  {rng.uniform(2,40):.1f}MB/s   "
              f"00:0{rng.randint(1,9)}",)),
        Beat(p, f"ssh {host} 'ls -la /mnt/offsite/{fname}'",
             (f"-rw-r--r-- 1 root root {size} {_date(rng)} {fname}",),
             pause=1.4),
    ]


def scene_stuck_job(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    job = rng.choice(["nightly-export", "report-builder", "index-rebuild",
                       "cache-warm"])
    pid = _pid(rng)
    hours = rng.randint(3, 14)
    p = ctx.at(f"~/{ctx.project}")
    return [
        Beat(p, f"pgrep -fa {job}",
             (f"{pid} python3 scripts/{job}.py --full",),
             comment=f"{job} should be minutes, not sitting like this"),
        Beat(p, f"ps -p {pid} -o pid,etime,stat --no-headers",
             (f"{pid}   {hours:02d}:{rng.randint(10,59):02d}:00 D",)),
        Beat(p, f"cat /proc/{pid}/wchan", ("pipe_wait",)),
        Beat(p, f"lsof -p {pid} | grep -i pipe | head -2",
             (f"python3 {pid} {ctx.user:<5} 10w  FIFO  0,13   0t0  pipe",
              f"python3 {pid} {ctx.user:<5} 11r  FIFO  0,13   0t0  pipe"),
             pause=1.0),
        Beat(p, f"kill -9 {pid}", ()),
        Beat(p, f"pgrep -fa {job}", (), failed=True, pause=0.9),
        Beat(p, f"nohup timeout 30m python3 scripts/{job}.py "
                "&>/tmp/job.log &",
             (f"[1] {_pid(rng)}",), pause=1.4),
    ]


def scene_api_probe(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    svc = rng.choice(["orders", "billing", "search", "accounts"])
    p = ctx.at("~")
    latency = rng.randint(180, 950)
    err_count = rng.randint(3, 40)
    return [
        Beat(p, f"curl -s {ctx.project}.io/{svc}/health | jq .",
             ("{", '  "status": "degraded",',
              f'  "latency_ms": {latency}', "}"),
             comment=f"{svc} dashboard is flashing amber -- see for herself"),
        Beat(p, f"journalctl -u {svc}-api --since '10 min ago' "
                "| grep -c ERROR", (str(err_count),), pause=1.0),
        Beat(p, f"journalctl -u {svc}-api --since '10 min ago' "
                "| grep ERROR | tail -2",
             (f"{_clock(rng)} {ctx.host} {svc}-api: pool timeout at 5000ms",
              f"{_clock(rng)} {ctx.host} {svc}-api: connection reset by peer")),
        Beat(p, f"ssh {ctx.host} 'systemctl restart {svc}-api'", (), pause=1.2),
        Beat(p, f"curl -s {ctx.project}.io/{svc}/health | jq -r .status",
             ("ok",), pause=1.5),
    ]


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _cert_date(rng):
    return (f"{rng.choice(_MONTHS)} {rng.randint(1,28)} "
            f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:00 2026 GMT")


def scene_cert_watch(ctx: Context) -> list[Beat]:
    rng = ctx.rng
    host = f"{ctx.project}.io"
    p = ctx.at("~")
    days = rng.randint(2, 9)
    return [
        Beat(p, f"openssl s_client -connect {host}:443 > /tmp/cert.pem",
             (), comment="renewal alerts have gone quiet -- check herself"),
        Beat(p, "openssl x509 -in /tmp/cert.pem -noout -enddate",
             (f"notAfter={_cert_date(rng)}",)),
        Beat(p, f"grep -c {host} /var/log/certbot-renew.log", ("0",)),
        Beat(p, "systemctl status certbot-renew.timer",
             ("certbot-renew.timer - dead",
              "   Active: inactive (dead)",
              "  Trigger: n/a"), pause=1.0),
        Beat(p, "systemctl enable --now certbot-renew.timer", ()),
        Beat(p, "systemctl list-timers certbot-renew.timer --no-pager",
             ("NEXT                 LEFT     UNIT",
              f"tomorrow 03:00:00    {days}h left  certbot-renew.timer")),
        Beat(p, "journalctl -u certbot-renew --since '2 min ago' "
                "| tail -n 2",
             (f"{_clock(rng)} {ctx.host} certbot: renewing {host}",
              f"{_clock(rng)} {ctx.host} certbot: certificate renewed"),
             pause=1.5),
    ]


SCENES = (scene_disk_full, scene_service_down, scene_deploy,
          scene_log_forensics, scene_permissions, scene_port_hunt,
          scene_git_tidy, scene_net_probe, scene_text_crunch,
          scene_backup_check, scene_stuck_job, scene_api_probe,
          scene_cert_watch)


def _with_mutterings(beats: list[Beat], rng: random.Random) -> list[Beat]:
    """Drop two or three of her notes onto beats inside the scene.

    Placement is contextual, not random: a reaction only lands on a beat that
    actually printed something for her to react to, a failure gets a
    failure-shaped reaction, and the closing note goes on the last beat where
    the problem is resolved. A mismatched mutter ("that's odd" after a clean
    delete) breaks the illusion faster than having none at all.

    Where there's room for it, an earlier beat also gets a question -- the
    hypothesis she's chasing before the reaction beat answers it. That's what
    makes her read as thinking it through rather than just narrating what
    already happened.
    """
    beats = [b for b in beats if b.command]
    if len(beats) < 3:
        return beats
    out = list(beats)

    candidates = [i for i in range(1, len(out) - 1) if out[i].output]
    if candidates:
        i = rng.choice(candidates)
        pool = SURPRISE if out[i].failed else DISCOVERY
        out[i] = replace(out[i], mutter=rng.choice(pool))

        earlier = [j for j in candidates if j < i and not out[j].failed]
        if earlier:
            q = rng.choice(earlier)
            out[q] = replace(out[q], mutter=rng.choice(QUESTIONS))

    out[-1] = replace(out[-1], mutter=rng.choice(CLOSING))
    return out


def make_scene(rng: random.Random) -> list[Beat]:
    """One coherent investigation, with fresh values."""
    ctx = make_context(rng)
    return _with_mutterings(rng.choice(SCENES)(ctx), rng)


def stream(rng: random.Random):
    """Endless beats, never repeating the same scene twice in a row."""
    last = None
    while True:
        ctx = make_context(rng)
        choices = [s for s in SCENES if s is not last] or list(SCENES)
        chosen = rng.choice(choices)
        last = chosen
        for beat in _with_mutterings(chosen(ctx), rng):
            yield beat
        yield None      # scene boundary: the renderer clears the screen
