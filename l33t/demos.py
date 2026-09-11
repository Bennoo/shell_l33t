"""Sample runs: what each command actually prints.

A line starting with "$ " is a follow-up command, used when the command
itself is silent -- because "no output means it worked" is a real shell
lesson, and the way you check is worth teaching alongside it.

Output has to match the flags the breakdown just explained: `head -10` shows
at most ten lines, `grep -c` shows one integer, a pipeline ending `sort -rn`
comes back descending. The tests enforce it.
"""

from __future__ import annotations

DEMOS: dict[str, tuple[str, ...]] = {

    # -- files & navigation -------------------------------------------
    "ls -lah --group-directories-first": (
        "total 48K",
        "drwxr-xr-x 4 user user 4.0K Sep 11 09:14 src",
        "drwxr-xr-x 2 user user 4.0K Sep 10 17:02 tests",
        "-rw-r--r-- 1 user user  18K Sep 11 09:20 README.md",
        "-rw-r--r-- 1 user user  220 Aug 30 11:48 .gitignore",
    ),
    "du -sh * | sort -rh | head -10": (
        "1.4G\tnode_modules",
        "612M\t.git",
        "48M\tdist",
        "2.1M\tsrc",
        "16K\tREADME.md",
    ),
    "mkdir -p build/{bin,lib,include}": (
        "$ find build -type d",
        "build",
        "build/bin",
        "build/include",
        "build/lib",
    ),
    "cp -av config.yaml config.yaml.bak": (
        "'config.yaml' -> 'config.yaml.bak'",
    ),
    "ln -sfn /opt/app/releases/v3 /opt/app/current": (
        "$ ls -l /opt/app/current",
        "lrwxrwxrwx 1 root root 21 Sep 11 09:31 current -> releases/v3",
    ),
    "rm -i -- -weirdly-named-file": (
        "rm: remove regular file '-weirdly-named-file'? y",
    ),

    # -- reading files -------------------------------------------------
    "tail -f -n 100 app.log": (
        "09:31:02 INFO  worker 3 picked up job 8814",
        "09:31:02 INFO  job 8814 finished in 412ms",
        "09:31:05 WARN  queue depth 1204 above threshold",
        "^C",
    ),
    "head -n 20 /var/log/syslog": (
        "Sep 11 08:00:01 host CRON[2841]: (root) CMD (/usr/bin/backup)",
        "Sep 11 08:00:07 host systemd[1]: Started Daily backup.",
        "Sep 11 08:01:22 host kernel: usb 1-2: new high-speed device",
    ),
    "wc -l < access.log": ("48213",),
    "stat -c '%s %Y %n' *.tar.gz": (
        "10485760 1757577600 backup-2026-09-10.tar.gz",
        "10321992 1757491200 backup-2026-09-09.tar.gz",
    ),
    "diff -u old.conf new.conf": (
        "--- old.conf",
        "+++ new.conf",
        "@@ -3,5 +3,5 @@",
        "-listen 127.0.0.1:8080",
        "+listen 0.0.0.0:8080",
    ),
    "file -i unknown.bin": (
        "unknown.bin: application/gzip; charset=binary",
    ),

    # -- finding things ------------------------------------------------
    "find . -type f -name '*.py' -newermt '-2 days'": (
        "./l33t/engine.py",
        "./l33t/screens.py",
        "./tests/test_engine.py",
    ),
    "grep -rn --include='*.go' 'TODO' .": (
        "./cmd/server/main.go:42:// TODO: drain conns on shutdown",
        "./internal/store/cache.go:118:// TODO: evict by weight",
    ),
    "find . -name '*.tmp' -print0 | xargs -0 rm -f": (
        "$ find . -name '*.tmp' | wc -l",
        "0",
    ),
    "grep -v '^#' /etc/ssh/sshd_config | grep .": (
        "Port 22",
        "PermitRootLogin no",
        "PasswordAuthentication no",
    ),
    "grep -c ERROR app.log": ("147",),
    "find /var -size +100M -exec ls -lh {} +": (
        "-rw-r----- 1 root adm 240M /var/log/journal/system.journal",
        "-rw-r--r-- 1 mysql mysql 1.1G /var/lib/mysql/ibdata1",
    ),

    # -- text processing -----------------------------------------------
    "sort access.log | uniq -c | sort -rn": (
        "   4412 GET /api/health",
        "   1183 GET /assets/app.js",
        "     97 POST /api/login",
    ),
    "awk -F: '$3 >= 1000 {print $1}' /etc/passwd": (
        "user",
        "deploy",
        "jenkins",
    ),
    "sed -i.bak 's/localhost/0.0.0.0/g' config.yaml": (
        "$ grep listen config.yaml",
        "listen: 0.0.0.0:8080",
    ),
    "cut -d, -f1,3 data.csv": (
        "id,action",
        "1042,login",
        "1043,search",
    ),
    "awk '{sum += $2} END {print sum}' sizes.txt": ("184320",),
    "jq -r '.items[] | .id' data.json": (
        "itm_8f21",
        "itm_9a03",
        "itm_1c77",
    ),

    # -- pipes & redirection -------------------------------------------
    "make 2>&1 | tee build.log": (
        "cc -c src/main.c -o build/main.o",
        "src/main.c:88:5: warning: unused variable 'tmp'",
        "make: *** [build/app] Error 1",
    ),
    "./run.sh > out.txt 2> err.txt": (
        "$ wc -l out.txt err.txt",
        "  128 out.txt",
        "    3 err.txt",
    ),
    "diff <(sort a.txt) <(sort b.txt)": (
        "3d2",
        "< banana",
    ),
    "command -v rg >/dev/null 2>&1 || echo missing": ("missing",),
    "grep -m5 FATAL huge.log": (
        "09:12:44 FATAL cannot bind :8080",
        "09:14:01 FATAL cannot bind :8080",
    ),
    "printf '%s\\n' one two three | nl": (
        "     1\tone",
        "     2\ttwo",
        "     3\tthree",
    ),

    # -- permissions ----------------------------------------------------
    "chmod 600 ~/.ssh/id_ed25519": (
        "$ stat -c '%A' ~/.ssh/id_ed25519",
        "-rw-------",
    ),
    "chmod u+x,go-w deploy.sh": (
        "$ stat -c '%A' deploy.sh",
        "-rwxr--r--",
    ),
    "chown -R deploy:deploy /srv/www": (
        "$ stat -c '%U:%G' /srv/www",
        "deploy:deploy",
    ),
    "find . -type f -perm /o+w -ls": (
        "2621 4 -rw-rw-rw- 1 user user 1204 Sep 10 14:02 ./notes.txt",
    ),
    "umask 027": (
        "$ touch new.txt && stat -c '%A' new.txt",
        "-rw-r-----",
    ),
    "sudo -u postgres psql -c '\\l'": (
        "   Name    |  Owner   | Encoding",
        "-----------+----------+----------",
        " orders    | postgres | UTF8",
        " postgres  | postgres | UTF8",
    ),

    # -- processes & jobs ------------------------------------------------
    "ps aux --sort=-%mem | head -5": (
        "USER  PID %CPU %MEM   RSS COMMAND",
        "user 4821  2.1 18.4  2.9G /usr/bin/firefox",
        "user 5102  0.8  6.2  988M node server.js",
    ),
    "kill -9 $(lsof -t -i:8080)": (
        "$ lsof -i:8080 | wc -l",
        "0",
    ),
    "nohup ./worker.sh > worker.log 2>&1 &": (
        "[1] 20314",
    ),
    "pgrep -af nginx": (
        "1204 nginx: master process /usr/sbin/nginx",
        "1205 nginx: worker process",
    ),
    "timeout 30s ./flaky-check.sh": (
        "checking upstream... ok",
        "checking database... ok",
    ),
    "journalctl -u nginx --since '1 hour ago' -f": (
        "09:14:02 host nginx[1204]: reloading configuration",
        "09:15:41 host nginx[1204]: 502 upstream timed out",
    ),

    # -- networking -------------------------------------------------------
    "curl -sS -o /dev/null -w '%{http_code}\\n' https://x.io": ("200",),
    "ssh -i ~/.ssh/id_ed25519 -p 2222 deploy@10.0.42.7": (
        "Linux edge-07 6.8.0 x86_64",
        "Last login: Wed Sep 10 22:14:03 2026 from 10.0.42.1",
        "deploy@edge-07:~$",
    ),
    "ssh -L 5432:localhost:5432 bastion": (
        "$ psql -h localhost -p 5432 -c 'select 1'",
        " ?column?",
        "----------",
        "        1",
    ),
    "ss -tulpn | grep LISTEN": (
        "tcp LISTEN 0.0.0.0:22     users:((\"sshd\",pid=821))",
        "tcp LISTEN 127.0.0.1:5432 users:((\"postgres\",pid=1442))",
    ),
    "dig +short AAAA example.com": (
        "2606:2800:21f:cb07:6820:80da:af6b:8b2c",
    ),
    "nc -zv db.internal 5432": (
        "Connection to db.internal 5432 port [tcp/postgresql] succeeded!",
    ),

    # -- git ---------------------------------------------------------------
    "git switch -c feature/typing-modes": (
        "Switched to a new branch 'feature/typing-modes'",
    ),
    "git add -p src/engine.py": (
        "@@ -142,6 +142,7 @@ def metrics(self):",
        "+        if self.started is None:",
        "(1/3) Stage this hunk [y,n,q,a,d,s,e,?]?",
    ),
    "git commit --amend --no-edit": (
        "[main 8f3c21a] cap keystroke latency outliers",
        " 1 file changed, 6 insertions(+), 2 deletions(-)",
    ),
    "git rebase -i HEAD~3": (
        "Successfully rebased and updated refs/heads/main.",
    ),
    "git push --force-with-lease origin HEAD": (
        "To github.com:you/project.git",
        " + 9a1f0c3...8f3c21a HEAD -> main (forced update)",
    ),
    "git bisect start HEAD v1.2.0": (
        "Bisecting: 9 revisions left to test after this (~3 steps)",
        "[4c2f8ab] bump client timeout to 5s",
    ),

    # -- archives & transfer ------------------------------------------------
    "tar -czf backup-$(date +%F).tar.gz /var/lib/node": (
        "$ ls -lh backup-2026-09-11.tar.gz",
        "-rw-r--r-- 1 user user 412M Sep 11 09:40 backup-2026-09-11.tar.gz",
    ),
    "tar -xzf release.tar.gz -C /opt/app --strip-components=1": (
        "$ ls /opt/app",
        "bin  config  lib  VERSION",
    ),
    "rsync -avz --delete --dry-run ./dist/ edge:/srv/www/": (
        "sending incremental file list",
        "deleting old/legacy.js",
        "dist/index.html",
        "sent 1,204 bytes  received 38 bytes",
    ),
    "rsync -avzP --partial big.iso backup:/data/": (
        "big.iso",
        "  1,073,741,824 100%   38.2MB/s    0:00:26 (xfr#1)",
    ),
    "zcat access.log.gz | grep -c 500": ("312",),
    "split -b 100M big.bin part-": (
        "$ ls part-*",
        "part-aa  part-ab  part-ac",
    ),

    # -- shell scripting -----------------------------------------------------
    "set -euo pipefail": (
        "$ false | true; echo \"exit $?\"",
        "exit 1",
    ),
    "for f in *.md; do echo \"${f%.md}\"; done": (
        "CHANGELOG",
        "README",
    ),
    "while read -r line; do echo \"$line\"; done < in.txt": (
        "first line",
        "second line",
    ),
    "count=$(grep -c ERROR app.log)": (
        "$ echo \"$count\"",
        "147",
    ),
    "trap 'rm -f \"$tmp\"' EXIT": (
        "$ ls /tmp/tmp.* 2>/dev/null | wc -l",
        "0",
    ),
    "echo \"${NAME:-anonymous}\"": ("anonymous",),
}
