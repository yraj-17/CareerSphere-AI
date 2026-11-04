"""
Bash and Linux problems (Judge0 "Bash (5.0.0)").

The Judge0 sandbox provides bash 5.0, coreutils, GNU sed 4.7 and mawk (not gawk; no
bc). Problems only require those tools. Each problem has an independent Python oracle.
File-operation problems use the bash_workspace harness: the test's files are created
in an empty directory, the script runs there, and the final directory listing is part
of the checked output — so the script must really move the files.
"""

from __future__ import annotations

import json
import random

from app.data.coding_bank import ProblemSpec, Test

BASH_ONLY = ("BASH",)
OPS_ROLES = ("devops-engineer", "site-reliability-engineer", "linux-administrator", "system-administrator")
OPS_COMPS = ("scripting-automation", "linux-scripting", "sysadmin-scripting")
BASH_NOTE = "Runtime: Bash 5.0 with coreutils, GNU sed 4.7 and mawk (gawk-only features and bc are not available)."


def _lines(text: str) -> list[str]:
    return [line for line in text.split("\n") if line != ""]


# ---------------------------------------------------------------------------
# 21. Log analysis — top offending IPs
# ---------------------------------------------------------------------------


def _top_ips_oracle(stdin: str) -> str:
    counts: dict[str, int] = {}
    for line in _lines(stdin):
        fields = line.split()
        if int(fields[-2]) >= 400:
            counts[fields[0]] = counts.get(fields[0], 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return "".join(f"{count} {ip}\n" for ip, count in ranked)


def _access_log(r: random.Random, n: int, ips: list[str]) -> str:
    paths = ["/", "/login", "/api/items", "/admin", "/static/app.js", "/wp-login.php"]
    out = []
    for i in range(n):
        status = r.choice([200, 200, 200, 301, 304, 401, 403, 404, 500, 502])
        out.append(f'{r.choice(ips)} - - [04/Nov/2026:10:{i % 60:02d}:{(i * 7) % 60:02d} +0530] '
                   f'"{r.choice(["GET", "POST"])} {r.choice(paths)} HTTP/1.1" {status} {r.randint(0, 9000)}')
    return "\n".join(out) + "\n"


def _top_ips_tests() -> tuple[Test, ...]:
    r = random.Random(2121)
    sample = (
        '10.0.0.5 - - [04/Nov/2026:10:00:01 +0530] "GET /login HTTP/1.1" 401 120\n'
        '10.0.0.5 - - [04/Nov/2026:10:00:02 +0530] "GET /login HTTP/1.1" 401 120\n'
        '192.168.1.9 - - [04/Nov/2026:10:00:03 +0530] "GET / HTTP/1.1" 200 5120\n'
        '172.16.0.2 - - [04/Nov/2026:10:00:04 +0530] "GET /admin HTTP/1.1" 403 98\n'
        '192.168.1.9 - - [04/Nov/2026:10:00:05 +0530] "POST /api/items HTTP/1.1" 500 0\n'
        '10.0.0.5 - - [04/Nov/2026:10:00:06 +0530] "GET /login HTTP/1.1" 200 640\n'
    )
    ties = (
        '10.0.0.10 - - [04/Nov/2026:11:00:00 +0530] "GET /x HTTP/1.1" 404 1\n'
        '10.0.0.2 - - [04/Nov/2026:11:00:01 +0530] "GET /x HTTP/1.1" 404 1\n'
        '10.0.0.3 - - [04/Nov/2026:11:00:02 +0530] "GET /x HTTP/1.1" 404 1\n'
        '10.0.0.4 - - [04/Nov/2026:11:00:03 +0530] "GET /x HTTP/1.1" 404 1\n'
    )
    many_ips = [f"203.0.{r.randint(0, 9)}.{r.randint(1, 254)}" for _ in range(40)]
    return (
        Test(sample, hidden=False, explanation="10.0.0.5 has two 401s; its 200 response does not count."),
        Test(ties, hidden=False, explanation="Equal counts are ordered by IP as plain text ('10.0.0.10' < '10.0.0.2')."),
        Test('8.8.8.8 - - [04/Nov/2026:12:00:00 +0530] "GET / HTTP/1.1" 200 10\n'),
        Test('1.1.1.1 - - [04/Nov/2026:12:00:00 +0530] "GET / HTTP/1.1" 399 10\n'
             '1.1.1.2 - - [04/Nov/2026:12:00:01 +0530] "GET / HTTP/1.1" 400 10\n'),
        Test(_access_log(r, 300, many_ips[:6])),
        Test(_access_log(r, 20000, many_ips), weight=2.0),
    )


TOP_IPS = ProblemSpec(
    slug="bash-top-offending-ips",
    title="Top Offending IPs",
    category="bash",
    difficulty="EASY",
    summary="Find the client IPs with the most error responses in an access log (Bash).",
    roles=OPS_ROLES,
    competencies=OPS_COMPS,
    statement=(
        "A web server is being probed. Write a Bash script that reads an access log on stdin and "
        "prints the three client IPs with the most error responses (HTTP status 400 or higher).\n\n"
        "Each line has the format: IP - - [timestamp] \"METHOD PATH PROTOCOL\" STATUS BYTES. The status "
        "is always the second-to-last field.\n\n"
        "Print 'count ip' for at most three IPs, ordered by count descending, then by IP ascending as "
        "plain text (byte order, as `LC_ALL=C sort` does). IPs with no error responses are not printed."
    ),
    input_format="Access log lines on stdin.",
    output_format="Up to three lines: count ip.",
    constraints="Up to 20 000 log lines",
    languages=BASH_ONLY,
    starter_code={
        "BASH": "#!/bin/bash\n# Read the access log from stdin and print the top 3 IPs by error responses.\n\n"
                "while IFS= read -r line; do\n  : # TODO\ndone\n",
    },
    reference_solutions={
        "BASH": """#!/bin/bash
export LC_ALL=C
awk '$(NF-1) >= 400 { count[$1]++ } END { for (ip in count) print count[ip], ip }' \\
  | sort -k1,1nr -k2,2 \\
  | head -n 3
""",
    },
    wrong_solutions=(
        ("BASH", """#!/bin/bash
export LC_ALL=C
awk '{ count[$1]++ } END { for (ip in count) print count[ip], ip }' | sort -k1,1nr -k2,2 | head -n 3
""", "Counts every request, not only error responses."),
        ("BASH", """#!/bin/bash
export LC_ALL=C
awk '$(NF-1) > 400 { count[$1]++ } END { for (ip in count) print count[ip], ip }' | sort -k1,1nr -k2,2 | head -n 3
""", "Off by one: status 400 is not counted as an error."),
    ),
    tests=_top_ips_tests(),
    oracle=_top_ips_oracle,
    instructions=BASH_NOTE,
    time_limit_seconds=2.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 22. Text processing — CSV totals with bad rows
# ---------------------------------------------------------------------------


def _csv_oracle(stdin: str) -> str:
    rows = _lines(stdin)[1:]
    totals: dict[str, int] = {}
    skipped = 0
    for row in rows:
        fields = row.split(",")
        if len(fields) == 4 and fields[3].isdigit() and fields[3].isascii():
            totals[fields[1]] = totals.get(fields[1], 0) + int(fields[3])
        else:
            skipped += 1
    out = [f"{region} {total}" for region, total in sorted(totals.items())]
    out.append(f"TOTAL {sum(totals.values())}")
    out.append(f"SKIPPED {skipped}")
    return "\n".join(out) + "\n"


def _csv_tests() -> tuple[Test, ...]:
    r = random.Random(2222)
    regions = ["north", "south", "east", "west", "central"]

    def csv(n: int, bad_rate: float) -> str:
        rows = ["date,region,product,amount"]
        for i in range(n):
            amount = str(r.randint(0, 10000))
            if r.random() < bad_rate:
                amount = r.choice(["", "N/A", "-5", "12.5", "1e3", "abc"])
            rows.append(f"2026-10-{1 + i % 28:02d},{r.choice(regions)},sku{r.randint(1, 30)},{amount}")
        return "\n".join(rows) + "\n"

    return (
        Test("date,region,product,amount\n2026-10-01,north,pen,120\n2026-10-01,south,ink,80\n2026-10-02,north,pad,30\n",
             hidden=False, explanation="north = 120 + 30; regions are listed alphabetically."),
        Test("date,region,product,amount\n2026-10-03,east,pen,N/A\n2026-10-03,east,pen,15\n2026-10-04,west,cap,-4\n",
             hidden=False, explanation="'N/A' and '-4' are not non-negative integers, so those rows are skipped."),
        Test("date,region,product,amount\n"),
        Test("date,region,product,amount\n2026-10-05,north,a,0\n2026-10-05,north,b,007\n2026-10-06,south,c,5,extra\n"),
        Test(csv(200, 0.1)),
        Test(csv(2000, 0.05), weight=2.0),
    )


CSV_TOTALS = ProblemSpec(
    slug="bash-csv-region-totals",
    title="Regional Sales Totals from CSV",
    category="bash",
    difficulty="EASY",
    summary="Total a CSV column per region and count malformed rows (Bash).",
    roles=OPS_ROLES,
    competencies=OPS_COMPS,
    statement=(
        "A nightly job exports sales as CSV and an operations script must summarise it.\n\n"
        "stdin starts with the header 'date,region,product,amount', followed by data rows. A row is "
        "valid when it has exactly 4 comma-separated fields and amount is a non-negative integer "
        "written with digits only (leading zeros allowed). Fields never contain commas or quotes.\n\n"
        "Print one line 'region total' per region that has valid rows, sorted by region name; then "
        "'TOTAL x' (sum of all valid amounts) and 'SKIPPED k' (number of invalid data rows)."
    ),
    input_format="CSV on stdin: a header line, then zero or more data rows.",
    output_format="region total lines, then TOTAL and SKIPPED lines.",
    constraints="Up to 2 000 data rows\n0 ≤ amount ≤ 10 000",
    languages=BASH_ONLY,
    starter_code={
        "BASH": "#!/bin/bash\n# Read the CSV from stdin and print per-region totals, TOTAL and SKIPPED.\n\n"
                "read -r header\nwhile IFS=, read -r date region product amount; do\n  : # TODO\ndone\n",
    },
    reference_solutions={
        "BASH": """#!/bin/bash
export LC_ALL=C
awk -F, '
  NR == 1 { next }
  NF == 4 && $4 ~ /^[0-9]+$/ { total[$2] += $4; all += $4; next }
  { skipped++ }
  END {
    for (region in total) printf "%s %d\\n", region, total[region] | "sort"
    close("sort")
    printf "TOTAL %d\\n", all
    printf "SKIPPED %d\\n", skipped
  }'
""",
    },
    wrong_solutions=(
        ("BASH", """#!/bin/bash
export LC_ALL=C
awk -F, '
  NR == 1 { next }
  { total[$2] += $4; all += $4 }
  END {
    for (region in total) printf "%s %d\\n", region, total[region] | "sort"
    close("sort")
    printf "TOTAL %d\\nSKIPPED 0\\n", all
  }'
""", "Adds malformed amounts instead of skipping them."),
    ),
    tests=_csv_tests(),
    oracle=_csv_oracle,
    instructions=BASH_NOTE,
    time_limit_seconds=2.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 23. File operations — organise a downloads folder (workspace harness)
# ---------------------------------------------------------------------------


def _extension(name: str) -> str:
    if "." not in name:
        return "other"
    ext = name.rsplit(".", 1)[1]
    return ext.lower() if ext else "other"


def _organise_oracle(test_input: str) -> str:
    files = json.loads(test_input)["files"]
    moved: dict[str, int] = {}
    listing = []
    for name, content in files.items():
        ext = _extension(name)
        moved[ext] = moved.get(ext, 0) + 1
        listing.append(f"{ext}/{name} {len(content.encode('utf-8'))}")
    out = [f"{ext} {count}" for ext, count in sorted(moved.items())]
    out.append("== workspace ==")
    out.extend(sorted(listing, key=lambda line: line.rsplit(" ", 1)[0].encode()))
    return "\n".join(out) + "\n"


def _workspace(files: dict[str, str]) -> str:
    return json.dumps({"files": files, "stdin": ""}, sort_keys=True)


def _organise_tests() -> tuple[Test, ...]:
    r = random.Random(2323)
    exts = ["pdf", "PDF", "jpg", "png", "txt", "csv", "zip", "Mp4", "gz"]
    random_files = {}
    while len(random_files) < 60:
        stem = r.choice(["report", "photo", "invoice", "notes", "backup", "clip", "data"]) + str(r.randint(1, 500))
        if r.random() < 0.15:
            stem += " copy"
        name = stem if r.random() < 0.1 else f"{stem}.{r.choice(exts)}"
        random_files[name] = "x" * r.randint(0, 40) + "\n"
    return (
        Test(_workspace({"report.pdf": "pdf-bytes\n", "photo.JPG": "jpeg\n", "notes.txt": "hi\n", "README": "read me\n"}),
             hidden=False, explanation="Extensions are lower-cased for the folder name; README has no extension so it goes to other/."),
        Test(_workspace({"my resume.docx": "cv\n", "backup.tar.gz": "tgz\n", "trailing.": "dot\n"}), hidden=False,
             explanation="Names may contain spaces; the extension is the text after the last dot; 'trailing.' has an empty extension."),
        Test(_workspace({"a.TXT": "1\n", "b.txt": "22\n", "c.Txt": "333\n"})),
        Test(_workspace({"x.other": "o\n", "y": "plain\n"})),
        Test(_workspace({"weird name with  spaces.log": "log\n", "q.LOG": "\n"})),
        Test(_workspace(random_files), weight=2.0),
    )


ORGANISE_FILES = ProblemSpec(
    slug="bash-organise-downloads",
    title="Organise a Downloads Folder",
    category="bash",
    difficulty="MEDIUM",
    summary="Move files into folders by extension and report counts (Bash file operations).",
    roles=OPS_ROLES,
    competencies=OPS_COMPS,
    statement=(
        "A shared downloads directory has become unmanageable. Write a Bash script that organises the "
        "current directory.\n\n"
        "The current directory contains only regular files (no sub-directories; no names start with "
        "'.'). Move every file into a sub-directory named after its extension in lower case — the text "
        "after the last '.' in the name (photo.JPG → jpg/, backup.tar.gz → gz/). Files without an "
        "extension, or whose name ends with '.', go into other/. File names may contain spaces and must "
        "not be renamed.\n\n"
        "Then print one line 'extension count' per directory you created, sorted by extension name.\n\n"
        "The checker also inspects the directory afterwards: after your output it prints a line "
        "'== workspace ==' followed by every file's path and size, so the files must really be moved."
    ),
    input_format="No stdin. The files to organise are in the current working directory.",
    output_format="'extension count' lines, sorted by extension; the checker then appends the workspace listing.",
    constraints="Up to 60 files\nNo file without an extension has the same name as an extension folder\n"
                "Sample and custom inputs are JSON: {\"files\": {\"name\": \"content\"}, \"stdin\": \"\"}",
    languages=BASH_ONLY,
    starter_code={
        "BASH": "#!/bin/bash\n# Organise the files in the current directory by extension.\n\n"
                "for f in *; do\n  [ -f \"$f\" ] || continue\n  : # TODO: work out the extension and move the file\ndone\n",
    },
    reference_solutions={
        "BASH": """#!/bin/bash
export LC_ALL=C
for f in *; do
  [ -f "$f" ] || continue
  case "$f" in
    *.*) ext="${f##*.}" ;;
    *) ext="" ;;
  esac
  if [ -z "$ext" ]; then
    ext=other
  else
    ext=$(printf '%s' "$ext" | tr 'A-Z' 'a-z')
  fi
  mkdir -p -- "$ext"
  mv -- "$f" "$ext/"
done
for d in */; do
  d="${d%/}"
  printf '%s %s\\n' "$d" "$(find "$d" -type f | wc -l | tr -d ' ')"
done
""",
    },
    wrong_solutions=(
        ("BASH", """#!/bin/bash
for f in $(ls); do
  ext="${f##*.}"
  [ "$ext" = "$f" ] && ext=other
  mkdir -p "$ext"
  mv "$f" "$ext/"
done
for d in */; do d="${d%/}"; echo "$d $(ls "$d" | wc -l)"; done
""", "Word-splits names with spaces and keeps upper-case extensions."),
        ("BASH", """#!/bin/bash
export LC_ALL=C
for f in *; do
  case "$f" in *.*) ext="${f##*.}" ;; *) ext="" ;; esac
  [ -z "$ext" ] && ext=other
  ext=$(printf '%s' "$ext" | tr 'A-Z' 'a-z')
  echo "$ext"
done | sort | uniq -c | awk '{ print $2, $1 }'
""", "Prints the right summary without actually moving any files."),
    ),
    tests=_organise_tests(),
    oracle=_organise_oracle,
    harness={"type": "bash_workspace"},
    instructions=BASH_NOTE,
    time_limit_seconds=3.0,
    estimated_minutes=20,
)


# ---------------------------------------------------------------------------
# 24. Process analysis — memory report from ps output
# ---------------------------------------------------------------------------


def _ps_oracle(stdin: str) -> str:
    rows = _lines(stdin)[1:]
    per_user: dict[str, list[int]] = {}
    top = None
    for row in rows:
        fields = row.split()
        user, pid, cpu, rss = fields[0], int(fields[1]), float(fields[3]), int(fields[4])
        command = " ".join(fields[5:])
        entry = per_user.setdefault(user, [0, 0])
        entry[0] += 1
        entry[1] += rss
        if top is None or cpu > top[0] or (cpu == top[0] and pid < top[1]):
            top = (cpu, pid, command)
    ranked = sorted(per_user.items(), key=lambda kv: (-kv[1][1], kv[0]))
    out = [f"{user} {count} {rss}" for user, (count, rss) in ranked]
    out.append(f"TOP_CPU {top[1]} {top[2]}")
    return "\n".join(out) + "\n"


def _ps_listing(r: random.Random, n: int) -> str:
    users = ["root", "www-data", "postgres", "deploy", "redis", "app"]
    commands = ["/usr/sbin/nginx -g daemon off;", "postgres: checkpointer", "python3 worker.py --queue high",
                "node server.js", "redis-server *:6379", "/usr/lib/systemd/systemd-journald", "bash", "sleep 3600"]
    lines = ["USER PID PPID %CPU RSS COMMAND"]
    pids = r.sample(range(2, 60000), n)
    for pid in pids:
        lines.append(f"{r.choice(users)} {pid} {r.randint(1, 2000)} {r.randint(0, 999) / 10:.1f} {r.randint(100, 900000)} {r.choice(commands)}")
    return "\n".join(lines) + "\n"


def _ps_tests() -> tuple[Test, ...]:
    r = random.Random(2424)
    return (
        Test("USER PID PPID %CPU RSS COMMAND\n"
             "root 1 0 0.1 9000 /sbin/init\n"
             "app 210 1 35.5 250000 node server.js --port 3000\n"
             "app 211 1 2.0 120000 node worker.js\n"
             "postgres 300 1 12.0 400000 postgres: writer process\n",
             hidden=False, explanation="app uses 370000 KB across 2 processes; node server.js has the highest %CPU."),
        Test("USER PID PPID %CPU RSS COMMAND\n"
             "zed 50 1 5.0 1000 sleep 10\n"
             "amy 40 1 5.0 1000 sleep 20\n",
             hidden=False, explanation="Equal memory is ordered by user name; equal %CPU picks the lower PID."),
        Test("USER PID PPID %CPU RSS COMMAND\nroot 1 0 0.0 4096 /sbin/init splash\n"),
        Test("USER PID PPID %CPU RSS COMMAND\n"
             "a 9 1 9.9 10 x\n"
             "b 10 1 10.0 10 y   with   spaces\n"
             "c 11 1 100.0 10 z\n"),
        Test(_ps_listing(r, 80)),
        Test(_ps_listing(r, 300), weight=2.0),
    )


PROCESS_REPORT = ProblemSpec(
    slug="bash-process-memory-report",
    title="Process Memory Report",
    category="bash",
    difficulty="MEDIUM",
    summary="Summarise process memory per user and find the busiest process (Bash).",
    roles=OPS_ROLES,
    competencies=OPS_COMPS,
    statement=(
        "During an incident you capture a process listing and need a quick summary.\n\n"
        "stdin is a header line 'USER PID PPID %CPU RSS COMMAND' followed by one line per process. "
        "Fields are separated by spaces; COMMAND is everything after RSS and may itself contain "
        "spaces. RSS is in kilobytes and %CPU has one decimal place.\n\n"
        "Print 'user processes total_rss' for every user, sorted by total_rss descending, then by user "
        "ascending. Finally print 'TOP_CPU pid command' for the process with the highest %CPU (lowest "
        "PID on ties), where command is the COMMAND fields joined by single spaces."
    ),
    input_format="A ps-style listing on stdin (header line first).",
    output_format="Per-user lines, then the TOP_CPU line.",
    constraints="1 ≤ processes ≤ 300\n0.0 ≤ %CPU ≤ 100.0\nRSS ≤ 1 000 000",
    languages=BASH_ONLY,
    starter_code={
        "BASH": "#!/bin/bash\n# Summarise the ps listing on stdin.\n\n"
                "read -r header\nwhile read -r user pid ppid cpu rss command; do\n  : # TODO\ndone\n",
    },
    reference_solutions={
        "BASH": """#!/bin/bash
export LC_ALL=C
awk '
  NR == 1 { next }
  {
    count[$1]++
    rss[$1] += $5
    cmd = $6
    for (i = 7; i <= NF; i++) cmd = cmd " " $i
    if (!found || $4 + 0 > best + 0 || ($4 + 0 == best + 0 && $2 + 0 < bestpid + 0)) {
      found = 1; best = $4; bestpid = $2; bestcmd = cmd
    }
  }
  END {
    for (u in count) printf "%s %d %d\\n", u, count[u], rss[u] | "sort -k3,3nr -k1,1"
    close("sort -k3,3nr -k1,1")
    printf "TOP_CPU %d %s\\n", bestpid, bestcmd
  }'
""",
    },
    wrong_solutions=(
        ("BASH", """#!/bin/bash
export LC_ALL=C
awk 'NR == 1 { next }
  { count[$1]++; rss[$1] += $5; if ($4 + 0 > best + 0) { best = $4; pid = $2; cmd = $6 } }
  END {
    for (u in count) printf "%s %d %d\\n", u, count[u], rss[u] | "sort -k3,3nr -k1,1"
    close("sort -k3,3nr -k1,1")
    printf "TOP_CPU %d %s\\n", pid, cmd
  }'
""", "Keeps only the first word of the command."),
        ("BASH", """#!/bin/bash
export LC_ALL=C
awk 'NR == 1 { next }
  { count[$1]++; rss[$1] += $5; cmd = $6; for (i = 7; i <= NF; i++) cmd = cmd " " $i
    if ($4 > best) { best = $4; pid = $2; bc = cmd } }
  END {
    for (u in count) printf "%s %d %d\\n", u, count[u], rss[u] | "sort -k2,2nr -k1,1"
    close("sort -k2,2nr -k1,1")
    printf "TOP_CPU %d %s\\n", pid, bc
  }'
""", "Sorts by process count and breaks %CPU ties by input order."),
    ),
    tests=_ps_tests(),
    oracle=_ps_oracle,
    instructions=BASH_NOTE,
    time_limit_seconds=2.0,
    estimated_minutes=20,
)


PROBLEMS = (TOP_IPS, CSV_TOTALS, ORGANISE_FILES, PROCESS_REPORT)
