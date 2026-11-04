"""Backend programming problems (C++17, Java 13, Python 3.8, Node.js 12)."""

from __future__ import annotations

import random

from app.data.coding_bank import ProblemSpec, Test, python_oracle
from app.data.coding_bank.dsa import GENERAL, _java

# ---------------------------------------------------------------------------
# 13. Sliding-window rate limiter — API business logic
# ---------------------------------------------------------------------------

_LIMITER_PY = '''import sys
from collections import deque


def main():
    data = sys.stdin.buffer.read().split()
    limit, window, n = int(data[0]), int(data[1]), int(data[2])
    allowed = {}
    out = []
    for i in range(n):
        t = int(data[3 + 2 * i])
        client = data[4 + 2 * i]
        times = allowed.get(client)
        if times is None:
            times = allowed[client] = deque()
        while times and times[0] <= t - window:
            times.popleft()
        if len(times) < limit:
            times.append(t)
            out.append("ALLOW")
        else:
            out.append("DENY")
    print("\\n".join(out))


main()
'''


def _limiter_tests() -> tuple[Test, ...]:
    r = random.Random(1313)

    def case(limit: int, window: int, requests: list[tuple[int, str]]) -> str:
        return f"{limit} {window} {len(requests)}\n" + "".join(f"{t} {c}\n" for t, c in requests)

    def stream(n: int, clients: int, step: int) -> list[tuple[int, str]]:
        t, out = 0, []
        for _ in range(n):
            t += r.randint(0, step)
            out.append((t, f"c{r.randint(1, clients)}"))
        return out

    return (
        Test(case(2, 10, [(1, "alice"), (2, "alice"), (3, "alice"), (11, "alice"), (12, "alice")]), hidden=False,
             explanation="The third request is the 3rd within (−7, 3]; at t=11 the request from t=1 has left the window."),
        Test(case(1, 5, [(0, "a"), (0, "b"), (4, "a"), (5, "a")]), hidden=False,
             explanation="Clients are limited independently; a request exactly W seconds later is allowed."),
        Test(case(3, 1, [(7, "x")] * 5)),
        Test(case(2, 100, [(0, "k"), (50, "k"), (60, "k"), (99, "k"), (100, "k"), (150, "k")])),
        Test(case(5, 60, stream(500, 3, 10))),
        Test(case(10, 1000, stream(9000, 50, 30)), weight=2.0),
        Test(case(10000, 10**9, stream(9000, 2, 5)), weight=2.0),
    )


RATE_LIMITER = ProblemSpec(
    slug="be-sliding-window-rate-limiter",
    title="API Rate Limiter",
    category="backend",
    difficulty="MEDIUM",
    summary="Decide ALLOW/DENY for API requests with a per-client sliding window.",
    roles=("backend-developer", "full-stack-developer", "java-developer", "python-developer"),
    competencies=("rest-apis", "programming", "core-java", "core-python"),
    statement=(
        "An API gateway allows each client at most L requests in any W-second sliding window.\n\n"
        "Requests arrive in non-decreasing timestamp order. A request at time t from client c is "
        "ALLOWED if fewer than L earlier requests from c were allowed in the window (t − W, t] "
        "(that is, at times strictly greater than t − W). Otherwise it is DENIED. Denied requests do "
        "not count towards the limit. Each client is limited independently.\n\n"
        "Print ALLOW or DENY for each request."
    ),
    input_format="The first line contains L, W and N. Each of the next N lines contains a timestamp and a client id.",
    output_format="N lines, each ALLOW or DENY.",
    constraints="1 ≤ L ≤ 10 000\n1 ≤ W ≤ 10^9\n1 ≤ N ≤ 10 000\n0 ≤ timestamp ≤ 10^10, non-decreasing\nClient ids are 1–20 letters or digits",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys
from collections import deque


def main():
    data = sys.stdin.buffer.read().split()
    limit, window, n = int(data[0]), int(data[1]), int(data[2])
    out = []
    for i in range(n):
        t = int(data[3 + 2 * i])
        client = data[4 + 2 * i]
        # TODO: decide whether this request is allowed.
        out.append("ALLOW")
    print("\\n".join(out))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    long long limit, window;
    int n;
    cin >> limit >> window >> n;
    string out;
    for (int i = 0; i < n; i++) {
        long long t;
        string client;
        cin >> t >> client;
        // TODO: decide whether this request is allowed.
        out += "ALLOW\\n";
    }
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        long limit = in.nextLong(), window = in.nextLong();
        int n = in.nextInt();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < n; i++) {
            long t = in.nextLong();
            String client = in.next();
            // TODO: decide whether this request is allowed.
            out.append("ALLOW\\n");
        }
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);
const limit = Number(data[0]);
const window = Number(data[1]);
const n = Number(data[2]);
const out = [];
for (let i = 0; i < n; i++) {
  const t = Number(data[3 + 2 * i]);
  const client = data[4 + 2 * i];
  // TODO: decide whether this request is allowed.
  out.push('ALLOW');
}
console.log(out.join('\\n'));
''',
    },
    reference_solutions={
        "PYTHON": _LIMITER_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    long long limit, window;
    int n;
    cin >> limit >> window >> n;
    unordered_map<string, deque<long long>> allowed;
    string out;
    for (int i = 0; i < n; i++) {
        long long t;
        string client;
        cin >> t >> client;
        deque<long long>& times = allowed[client];
        while (!times.empty() && times.front() <= t - window) times.pop_front();
        if ((long long)times.size() < limit) {
            times.push_back(t);
            out += "ALLOW\\n";
        } else {
            out += "DENY\\n";
        }
    }
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        long limit = in.nextLong(), window = in.nextLong();
        int n = in.nextInt();
        HashMap<String, ArrayDeque<Long>> allowed = new HashMap<>();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < n; i++) {
            long t = in.nextLong();
            String client = in.next();
            ArrayDeque<Long> times = allowed.computeIfAbsent(client, k -> new ArrayDeque<>());
            while (!times.isEmpty() && times.peekFirst() <= t - window) times.pollFirst();
            if (times.size() < limit) {
                times.addLast(t);
                out.append("ALLOW\\n");
            } else {
                out.append("DENY\\n");
            }
        }
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);
const limit = Number(data[0]);
const window = Number(data[1]);
const n = Number(data[2]);
const allowed = new Map();
const out = [];
for (let i = 0; i < n; i++) {
  const t = Number(data[3 + 2 * i]);
  const client = data[4 + 2 * i];
  let q = allowed.get(client);
  if (!q) {
    q = { times: [], head: 0 };
    allowed.set(client, q);
  }
  while (q.head < q.times.length && q.times[q.head] <= t - window) q.head++;
  if (q.times.length - q.head < limit) {
    q.times.push(t);
    out.push('ALLOW');
  } else {
    out.push('DENY');
  }
}
console.log(out.join('\\n'));
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
limit, window, n = int(data[0]), int(data[1]), int(data[2])
buckets = {}
out = []
for i in range(n):
    t, c = int(data[3 + 2 * i]), data[4 + 2 * i]
    key = (c, t // window)
    if buckets.get(key, 0) < limit:
        buckets[key] = buckets.get(key, 0) + 1
        out.append("ALLOW")
    else:
        out.append("DENY")
print("\\n".join(out))
''', "Uses fixed windows instead of a sliding window."),
        ("PYTHON", _LIMITER_PY.replace("        if len(times) < limit:\n            times.append(t)", "        times.append(t)\n        if len(times) <= limit:"),
         "Counts denied requests towards the limit."),
    ),
    tests=_limiter_tests(),
    oracle=python_oracle(_LIMITER_PY),
    time_limit_seconds=1.0,
    estimated_minutes=20,
)


# ---------------------------------------------------------------------------
# 14. Validate sign-up requests — validation and error handling
# ---------------------------------------------------------------------------

_SIGNUP_PY = '''import sys

LOWER = set("abcdefghijklmnopqrstuvwxyz")
UPPER = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
DIGITS = set("0123456789")


def email_ok(email):
    if email.count("@") != 1 or " " in email:
        return False
    local, domain = email.split("@")
    if not local or "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False
    return True


def validate(line):
    fields = line.split("|")
    if len(fields) != 4:
        return ["FIELD_COUNT"]
    username, email, age, password = fields
    errors = []
    if not 3 <= len(username) <= 20:
        errors.append("USERNAME_LENGTH")
    if not username or username[0] not in LOWER or any(ch not in LOWER and ch not in DIGITS and ch != "_" for ch in username):
        errors.append("USERNAME_CHARS")
    if not email_ok(email):
        errors.append("EMAIL_FORMAT")
    if not (1 <= len(age) <= 3 and all(ch in DIGITS for ch in age) and 13 <= int(age) <= 120):
        errors.append("AGE_INVALID")
    if not 8 <= len(password) <= 64:
        errors.append("PASSWORD_LENGTH")
    if not (any(c in LOWER for c in password) and any(c in UPPER for c in password) and any(c in DIGITS for c in password)):
        errors.append("PASSWORD_WEAK")
    return errors


def main():
    lines = sys.stdin.read().split("\\n")
    n = int(lines[0])
    out = []
    for line in lines[1:1 + n]:
        errors = validate(line.rstrip("\\r"))
        out.append("VALID" if not errors else "INVALID " + ",".join(errors))
    print("\\n".join(out))


main()
'''


def _signup_tests() -> tuple[Test, ...]:
    r = random.Random(1414)
    chars = "abcxyzABCXYZ019_.@- "

    def junk(k: int) -> str:
        return "".join(r.choice(chars) for _ in range(k))

    def case(lines: list[str]) -> str:
        return f"{len(lines)}\n" + "\n".join(lines) + "\n"

    random_lines = []
    for _ in range(600):
        parts = [junk(r.randint(0, 22)), junk(r.randint(0, 15)), str(r.randint(-5, 150)) if r.random() < 0.8 else junk(3), junk(r.randint(0, 70))]
        if r.random() < 0.05:
            parts = parts[: r.randint(1, 3)]
        random_lines.append("|".join(parts))
    return (
        Test(case(["maya_01|maya@example.com|29|Secur3Pass", "Al|al@site|9|short"]), hidden=False,
             explanation="The second line breaks five rules; codes appear in the fixed rule order."),
        Test(case(["dev|dev@mail.co|13|abcdefG1", "only|three|fields"]), hidden=False,
             explanation="Boundary values are valid; a line without exactly 4 fields reports only FIELD_COUNT."),
        Test(case(["user name|a@b.com|30|Passw0rdX"])),
        Test(case(["_lead|a@b.com|30|Passw0rdX", "9lives|a@b.com|30|Passw0rdX", "abcdefghijklmnopqrstu|a@b.com|30|Passw0rdX"])),
        Test(case(["okname|@b.com|30|Passw0rdX", "okname|a@@b.com|30|Passw0rdX", "okname|a@b..com|30|Passw0rdX",
                   "okname|a@.b.com|30|Passw0rdX", "okname|a@bcom|30|Passw0rdX", "okname|a b@c.com|30|Passw0rdX"])),
        Test(case(["okname|a@b.com|121|Passw0rdX", "okname|a@b.com|012|Passw0rdX", "okname|a@b.com|1e2|Passw0rdX",
                   "okname|a@b.com||Passw0rdX", "okname|a@b.com|-20|Passw0rdX"])),
        Test(case(["okname|a@b.com|40|ALLUPPER123", "okname|a@b.com|40|" + "Aa1" * 22, "okname|a@b.com|40|Aa1"])),
        Test(case(["a|b|c|d|e", "", "|||"])),
        Test(case(random_lines), weight=2.0),
    )


SIGNUP_VALIDATION = ProblemSpec(
    slug="be-validate-signup-requests",
    title="Validate Sign-up Requests",
    category="backend",
    difficulty="EASY",
    summary="Validate sign-up fields and report every broken rule in a fixed order.",
    roles=("backend-developer", "full-stack-developer", "security-engineer", "application-security-engineer"),
    competencies=("rest-apis", "programming", "secure-coding"),
    statement=(
        "A sign-up endpoint must return every validation error at once, in a fixed order, so the "
        "client can highlight all invalid fields.\n\n"
        "Each request is one line: username|email|age|password. If the line does not split into "
        "exactly 4 fields on '|', the only error is FIELD_COUNT. Otherwise check, in this order:\n\n"
        "1. USERNAME_LENGTH — username length must be 3–20.\n"
        "2. USERNAME_CHARS — username must start with a lowercase letter and contain only a–z, 0–9 and '_'.\n"
        "3. EMAIL_FORMAT — exactly one '@'; no spaces; a non-empty part before '@'; the domain after '@' "
        "contains a '.', does not start or end with '.', and has no '..'.\n"
        "4. AGE_INVALID — age must be 1–3 digits (no sign) with a value from 13 to 120. Leading zeros are allowed.\n"
        "5. PASSWORD_LENGTH — password length must be 8–64.\n"
        "6. PASSWORD_WEAK — password needs at least one lowercase letter, one uppercase letter and one digit.\n\n"
        "Print VALID, or INVALID followed by a space and the comma-separated error codes. Fields are "
        "never trimmed: spaces are part of the value."
    ),
    input_format="The first line contains N. The next N lines are requests (a line may be empty).",
    output_format="N lines: VALID or INVALID CODE1,CODE2,…",
    constraints="1 ≤ N ≤ 600\nEach line has at most 200 printable ASCII characters",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def validate(line: str):
    # TODO: return the list of error codes for this request, in rule order.
    return []


def main():
    lines = sys.stdin.read().split("\\n")
    n = int(lines[0])
    out = []
    for line in lines[1:1 + n]:
        errors = validate(line.rstrip("\\r"))
        out.append("VALID" if not errors else "INVALID " + ",".join(errors))
    print("\\n".join(out))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

vector<string> validate(const string& line) {
    // TODO: return the error codes for this request, in rule order.
    return {};
}

int main() {
    string line;
    getline(cin, line);
    int n = stoi(line);
    string out;
    for (int i = 0; i < n; i++) {
        if (!getline(cin, line)) line = "";
        if (!line.empty() && line.back() == '\\r') line.pop_back();
        vector<string> errors = validate(line);
        if (errors.empty()) { out += "VALID\\n"; continue; }
        out += "INVALID ";
        for (size_t k = 0; k < errors.size(); k++) out += (k ? "," : "") + errors[k];
        out += "\\n";
    }
    cout << out;
    return 0;
}
''',
        "JAVA": '''import java.io.*;
import java.util.*;

public class Main {
    static List<String> validate(String line) {
        // TODO: return the error codes for this request, in rule order.
        return new ArrayList<>();
    }

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        int n = Integer.parseInt(br.readLine().trim());
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < n; i++) {
            String line = br.readLine();
            if (line == null) line = "";
            List<String> errors = validate(line);
            out.append(errors.isEmpty() ? "VALID" : "INVALID " + String.join(",", errors)).append('\\n');
        }
        System.out.print(out);
    }
}
''',
        "JAVASCRIPT": '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');

function validate(line) {
  // TODO: return the error codes for this request, in rule order.
  return [];
}

const n = parseInt(lines[0], 10);
const out = [];
for (let i = 1; i <= n; i++) {
  const errors = validate((lines[i] || '').replace(/\\r$/, ''));
  out.push(errors.length === 0 ? 'VALID' : 'INVALID ' + errors.join(','));
}
console.log(out.join('\\n'));
''',
    },
    reference_solutions={
        "PYTHON": _SIGNUP_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

static bool isLower(char c) { return c >= 'a' && c <= 'z'; }
static bool isUpper(char c) { return c >= 'A' && c <= 'Z'; }
static bool isDigit(char c) { return c >= '0' && c <= '9'; }

static vector<string> split(const string& s, char sep) {
    vector<string> parts;
    string cur;
    for (char c : s) {
        if (c == sep) { parts.push_back(cur); cur.clear(); }
        else cur += c;
    }
    parts.push_back(cur);
    return parts;
}

static bool emailOk(const string& email) {
    if (count(email.begin(), email.end(), '@') != 1 || email.find(' ') != string::npos) return false;
    size_t at = email.find('@');
    string local = email.substr(0, at), domain = email.substr(at + 1);
    if (local.empty() || domain.find('.') == string::npos) return false;
    if (domain.front() == '.' || domain.back() == '.' || domain.find("..") != string::npos) return false;
    return true;
}

vector<string> validate(const string& line) {
    vector<string> f = split(line, '|');
    if (f.size() != 4) return {"FIELD_COUNT"};
    const string &username = f[0], &email = f[1], &age = f[2], &password = f[3];
    vector<string> errors;
    if (username.size() < 3 || username.size() > 20) errors.push_back("USERNAME_LENGTH");
    bool charsOk = !username.empty() && isLower(username[0]);
    for (char c : username) if (!isLower(c) && !isDigit(c) && c != '_') charsOk = false;
    if (!charsOk) errors.push_back("USERNAME_CHARS");
    if (!emailOk(email)) errors.push_back("EMAIL_FORMAT");
    bool ageOk = !age.empty() && age.size() <= 3;
    for (char c : age) if (!isDigit(c)) ageOk = false;
    if (ageOk) { int v = stoi(age); ageOk = v >= 13 && v <= 120; }
    if (!ageOk) errors.push_back("AGE_INVALID");
    if (password.size() < 8 || password.size() > 64) errors.push_back("PASSWORD_LENGTH");
    bool lo = false, up = false, dg = false;
    for (char c : password) { lo = lo || isLower(c); up = up || isUpper(c); dg = dg || isDigit(c); }
    if (!(lo && up && dg)) errors.push_back("PASSWORD_WEAK");
    return errors;
}

int main() {
    string line;
    getline(cin, line);
    int n = stoi(line);
    string out;
    for (int i = 0; i < n; i++) {
        if (!getline(cin, line)) line = "";
        if (!line.empty() && line.back() == '\\r') line.pop_back();
        vector<string> errors = validate(line);
        if (errors.empty()) { out += "VALID\\n"; continue; }
        out += "INVALID ";
        for (size_t k = 0; k < errors.size(); k++) out += (k ? "," : "") + errors[k];
        out += "\\n";
    }
    cout << out;
    return 0;
}
''',
        "JAVA": '''import java.io.*;
import java.util.*;

public class Main {
    static boolean isLower(char c) { return c >= 'a' && c <= 'z'; }
    static boolean isUpper(char c) { return c >= 'A' && c <= 'Z'; }
    static boolean isDigit(char c) { return c >= '0' && c <= '9'; }

    static boolean emailOk(String email) {
        int ats = 0;
        for (char c : email.toCharArray()) if (c == '@') ats++;
        if (ats != 1 || email.indexOf(' ') >= 0) return false;
        int at = email.indexOf('@');
        String local = email.substring(0, at), domain = email.substring(at + 1);
        if (local.isEmpty() || domain.indexOf('.') < 0) return false;
        return !(domain.startsWith(".") || domain.endsWith(".") || domain.contains(".."));
    }

    static List<String> validate(String line) {
        String[] f = line.split("\\\\|", -1);
        List<String> errors = new ArrayList<>();
        if (f.length != 4) { errors.add("FIELD_COUNT"); return errors; }
        String username = f[0], email = f[1], age = f[2], password = f[3];
        if (username.length() < 3 || username.length() > 20) errors.add("USERNAME_LENGTH");
        boolean charsOk = !username.isEmpty() && isLower(username.charAt(0));
        for (char c : username.toCharArray()) if (!isLower(c) && !isDigit(c) && c != '_') charsOk = false;
        if (!charsOk) errors.add("USERNAME_CHARS");
        if (!emailOk(email)) errors.add("EMAIL_FORMAT");
        boolean ageOk = !age.isEmpty() && age.length() <= 3;
        for (char c : age.toCharArray()) if (!isDigit(c)) ageOk = false;
        if (ageOk) { int v = Integer.parseInt(age); ageOk = v >= 13 && v <= 120; }
        if (!ageOk) errors.add("AGE_INVALID");
        if (password.length() < 8 || password.length() > 64) errors.add("PASSWORD_LENGTH");
        boolean lo = false, up = false, dg = false;
        for (char c : password.toCharArray()) { lo |= isLower(c); up |= isUpper(c); dg |= isDigit(c); }
        if (!(lo && up && dg)) errors.add("PASSWORD_WEAK");
        return errors;
    }

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        int n = Integer.parseInt(br.readLine().trim());
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < n; i++) {
            String line = br.readLine();
            if (line == null) line = "";
            List<String> errors = validate(line);
            out.append(errors.isEmpty() ? "VALID" : "INVALID " + String.join(",", errors)).append('\\n');
        }
        System.out.print(out);
    }
}
''',
        "JAVASCRIPT": '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');

const isLower = (c) => c >= 'a' && c <= 'z';
const isUpper = (c) => c >= 'A' && c <= 'Z';
const isDigit = (c) => c >= '0' && c <= '9';

function emailOk(email) {
  if (email.split('@').length !== 2 || email.indexOf(' ') !== -1) return false;
  const [local, domain] = email.split('@');
  if (local === '' || domain.indexOf('.') === -1) return false;
  return !(domain.startsWith('.') || domain.endsWith('.') || domain.indexOf('..') !== -1);
}

function validate(line) {
  const f = line.split('|');
  if (f.length !== 4) return ['FIELD_COUNT'];
  const [username, email, age, password] = f;
  const errors = [];
  if (username.length < 3 || username.length > 20) errors.push('USERNAME_LENGTH');
  const chars = username.split('');
  if (username === '' || !isLower(username[0]) || chars.some((c) => !isLower(c) && !isDigit(c) && c !== '_')) errors.push('USERNAME_CHARS');
  if (!emailOk(email)) errors.push('EMAIL_FORMAT');
  const ageOk = age.length >= 1 && age.length <= 3 && age.split('').every(isDigit) && Number(age) >= 13 && Number(age) <= 120;
  if (!ageOk) errors.push('AGE_INVALID');
  if (password.length < 8 || password.length > 64) errors.push('PASSWORD_LENGTH');
  const p = password.split('');
  if (!(p.some(isLower) && p.some(isUpper) && p.some(isDigit))) errors.push('PASSWORD_WEAK');
  return errors;
}

const n = parseInt(lines[0], 10);
const out = [];
for (let i = 1; i <= n; i++) {
  const errors = validate((lines[i] || '').replace(/\\r$/, ''));
  out.push(errors.length === 0 ? 'VALID' : 'INVALID ' + errors.join(','));
}
console.log(out.join('\\n'));
''',
    },
    wrong_solutions=(
        ("PYTHON", _SIGNUP_PY.replace('    if email.count("@") != 1 or " " in email:\n        return False', '    return "@" in email'),
         "Accepts any email containing '@'."),
        ("JAVASCRIPT", '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');
const n = parseInt(lines[0], 10);
const out = [];
for (let i = 1; i <= n; i++) {
  const f = (lines[i] || '').trim().split('|');
  if (f.length !== 4) { out.push('INVALID FIELD_COUNT'); continue; }
  const errors = [];
  if (!/^[a-z][a-z0-9_]{2,19}$/.test(f[0])) errors.push('USERNAME_CHARS');
  if (!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(f[1])) errors.push('EMAIL_FORMAT');
  const age = parseInt(f[2], 10);
  if (!(age >= 13 && age <= 120)) errors.push('AGE_INVALID');
  if (!(/[a-z]/.test(f[3]) && /[A-Z]/.test(f[3]) && /[0-9]/.test(f[3]) && f[3].length >= 8)) errors.push('PASSWORD_WEAK');
  out.push(errors.length ? 'INVALID ' + errors.join(',') : 'VALID');
}
console.log(out.join('\\n'));
''', "Merges length and character errors, trims input and accepts ages like '1e2'."),
    ),
    tests=_signup_tests(),
    oracle=python_oracle(_SIGNUP_PY),
    time_limit_seconds=1.0,
    estimated_minutes=20,
)


# ---------------------------------------------------------------------------
# 15. Endpoint latency report — data processing
# ---------------------------------------------------------------------------

_LATENCY_PY = '''import sys


def normalise(path):
    path = path.split("?", 1)[0]
    parts = path.split("/")
    return "/".join(":id" if part.isdigit() else part for part in parts)


def main():
    lines = sys.stdin.read().split("\\n")
    n = int(lines[0])
    groups = {}
    for line in lines[1:1 + n]:
        method, path, status, latency = line.split()
        key = method + " " + normalise(path)
        entry = groups.setdefault(key, [0, 0, []])
        entry[0] += 1
        if int(status) >= 500:
            entry[1] += 1
        entry[2].append(int(latency))
    rows = []
    for key, (count, errors, latencies) in groups.items():
        latencies.sort()
        p95 = latencies[(95 * count + 99) // 100 - 1]
        rows.append((-count, key, "%s %d %d %d" % (key, count, errors, p95)))
    rows.sort()
    print("\\n".join(row[2] for row in rows))


main()
'''


def _latency_tests() -> tuple[Test, ...]:
    r = random.Random(1515)
    routes = [("GET", "/api/users/{id}"), ("GET", "/api/users"), ("POST", "/api/orders"), ("GET", "/api/orders/{id}/items"),
              ("DELETE", "/api/users/{id}"), ("GET", "/health"), ("PUT", "/api/orders/{id}")]

    def line() -> str:
        method, template = r.choice(routes)
        path = template.replace("{id}", str(r.randint(1, 99999)))
        if r.random() < 0.2:
            path += f"?page={r.randint(1, 9)}"
        status = r.choice([200, 200, 200, 201, 204, 400, 404, 500, 503])
        return f"{method} {path} {status} {r.randint(1, 3000)}"

    def case(lines: list[str]) -> str:
        return f"{len(lines)}\n" + "\n".join(lines) + "\n"

    return (
        Test(case(["GET /api/users/42 200 120", "GET /api/users/7 500 900", "GET /api/users?page=2 200 80", "GET /api/users/42 200 60"]),
             hidden=False, explanation="/api/users/42 and /api/users/7 group as /api/users/:id (3 requests, 1 error, p95 = 900)."),
        Test(case(["POST /login 401 30", "POST /login 200 45"]), hidden=False,
             explanation="4xx is not an error; with 2 latencies the p95 is the 2nd smallest."),
        Test(case(["GET /a 200 5"])),
        Test(case([f"GET /x {200 if i % 10 else 502} {i}" for i in range(1, 21)])),
        Test(case(["GET /v1/2024/report 200 10", "GET /v1/2025/report 200 20", "GET /v1/abc123/report 200 30"])),
        Test(case([line() for _ in range(300)])),
        Test(case([line() for _ in range(50000)]), weight=2.0),
    )


LATENCY_REPORT = ProblemSpec(
    slug="be-endpoint-latency-report",
    title="Endpoint Latency Report",
    category="backend",
    difficulty="MEDIUM",
    summary="Aggregate access logs per endpoint: counts, 5xx errors and p95 latency.",
    roles=("backend-developer", "full-stack-developer", "data-engineer", "python-developer"),
    competencies=("programming", "rest-apis", "etl-pipelines", "python-data", "core-python"),
    statement=(
        "An API team wants a daily report of its slowest and busiest endpoints.\n\n"
        "Each log line is 'METHOD PATH STATUS LATENCY_MS'. Group lines by endpoint: the method plus "
        "the normalised path, where the query string (from '?') is removed and every path segment that "
        "consists only of digits becomes ':id' (so /api/users/42?x=1 → /api/users/:id).\n\n"
        "For each endpoint print 'METHOD PATH count errors p95', where errors counts statuses ≥ 500 and "
        "p95 is the nearest-rank 95th percentile: the ⌈95·count/100⌉-th smallest latency. Sort by "
        "count descending, then by 'METHOD PATH' ascending (plain string order)."
    ),
    input_format="The first line contains N. Each of the next N lines is a log entry.",
    output_format="One line per endpoint: METHOD PATH count errors p95.",
    constraints="1 ≤ N ≤ 50 000\n1 ≤ latency ≤ 10^6\nPaths start with '/' and contain no spaces",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def normalise(path: str) -> str:
    # TODO: drop the query string and replace all-digit segments with ':id'.
    return path


def main():
    lines = sys.stdin.read().split("\\n")
    n = int(lines[0])
    for line in lines[1:1 + n]:
        method, path, status, latency = line.split()
        # TODO: aggregate per endpoint and print the report.


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

string normalise(const string& path) {
    // TODO: drop the query string and replace all-digit segments with ":id".
    return path;
}

int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        string method, path;
        int status, latency;
        cin >> method >> path >> status >> latency;
        // TODO: aggregate per endpoint and print the report.
    }
    return 0;
}
''',
        "JAVA": _java('''
    static String normalise(String path) {
        // TODO: drop the query string and replace all-digit segments with ":id".
        return path;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        for (int i = 0; i < n; i++) {
            String method = in.next(), path = in.next();
            int status = in.nextInt(), latency = in.nextInt();
            // TODO: aggregate per endpoint and print the report.
        }
    }
'''),
        "JAVASCRIPT": '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');

function normalise(path) {
  // TODO: drop the query string and replace all-digit segments with ':id'.
  return path;
}

const n = parseInt(lines[0], 10);
for (let i = 1; i <= n; i++) {
  const [method, path, status, latency] = lines[i].trim().split(/\\s+/);
  // TODO: aggregate per endpoint and print the report.
}
''',
    },
    reference_solutions={
        "PYTHON": _LATENCY_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

string normalise(const string& raw) {
    string path = raw.substr(0, raw.find('?'));
    string out, segment;
    auto flush = [&]() {
        bool digits = !segment.empty() && all_of(segment.begin(), segment.end(), [](char c) { return c >= '0' && c <= '9'; });
        out += digits ? ":id" : segment;
        segment.clear();
    };
    for (char c : path) {
        if (c == '/') { flush(); out += '/'; }
        else segment += c;
    }
    flush();
    return out;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    cin >> n;
    map<string, tuple<int, int, vector<int>>> groups;
    for (int i = 0; i < n; i++) {
        string method, path;
        int status, latency;
        cin >> method >> path >> status >> latency;
        auto& g = groups[method + " " + normalise(path)];
        get<0>(g)++;
        if (status >= 500) get<1>(g)++;
        get<2>(g).push_back(latency);
    }
    vector<pair<int, string>> rows;
    for (auto& kv : groups) {
        vector<int>& lat = get<2>(kv.second);
        sort(lat.begin(), lat.end());
        int count = get<0>(kv.second);
        int p95 = lat[(95 * count + 99) / 100 - 1];
        rows.push_back({-count, kv.first + " " + to_string(count) + " " + to_string(get<1>(kv.second)) + " " + to_string(p95)});
    }
    stable_sort(rows.begin(), rows.end(), [](const pair<int, string>& a, const pair<int, string>& b) { return a.first < b.first; });
    for (auto& row : rows) cout << row.second << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static String normalise(String raw) {
        int q = raw.indexOf('?');
        String path = q >= 0 ? raw.substring(0, q) : raw;
        String[] parts = path.split("/", -1);
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) out.append('/');
            String p = parts[i];
            boolean digits = !p.isEmpty();
            for (char c : p.toCharArray()) if (c < '0' || c > '9') digits = false;
            out.append(digits ? ":id" : p);
        }
        return out.toString();
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        TreeMap<String, int[]> counts = new TreeMap<>();
        HashMap<String, ArrayList<Integer>> latencies = new HashMap<>();
        for (int i = 0; i < n; i++) {
            String method = in.next(), path = in.next();
            int status = in.nextInt(), latency = in.nextInt();
            String key = method + " " + normalise(path);
            int[] c = counts.computeIfAbsent(key, k -> new int[2]);
            c[0]++;
            if (status >= 500) c[1]++;
            latencies.computeIfAbsent(key, k -> new ArrayList<>()).add(latency);
        }
        List<String> keys = new ArrayList<>(counts.keySet());
        keys.sort((a, b) -> counts.get(b)[0] != counts.get(a)[0] ? counts.get(b)[0] - counts.get(a)[0] : a.compareTo(b));
        StringBuilder out = new StringBuilder();
        for (String key : keys) {
            int[] c = counts.get(key);
            ArrayList<Integer> lat = latencies.get(key);
            Collections.sort(lat);
            out.append(key).append(' ').append(c[0]).append(' ').append(c[1]).append(' ')
               .append(lat.get((95 * c[0] + 99) / 100 - 1)).append('\\n');
        }
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');

function normalise(raw) {
  const path = raw.split('?')[0];
  return path.split('/').map((part) => (/^[0-9]+$/.test(part) ? ':id' : part)).join('/');
}

const n = parseInt(lines[0], 10);
const groups = new Map();
for (let i = 1; i <= n; i++) {
  const [method, path, status, latency] = lines[i].trim().split(/\\s+/);
  const key = method + ' ' + normalise(path);
  const g = groups.get(key) || { count: 0, errors: 0, latencies: [] };
  g.count++;
  if (Number(status) >= 500) g.errors++;
  g.latencies.push(Number(latency));
  groups.set(key, g);
}
const rows = Array.from(groups.entries()).sort((a, b) =>
  b[1].count - a[1].count || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
const out = rows.map(([key, g]) => {
  g.latencies.sort((x, y) => x - y);
  return key + ' ' + g.count + ' ' + g.errors + ' ' + g.latencies[Math.floor((95 * g.count + 99) / 100) - 1];
});
console.log(out.join('\\n'));
''',
    },
    wrong_solutions=(
        ("PYTHON", _LATENCY_PY.replace("latencies[(95 * count + 99) // 100 - 1]", "latencies[int(0.95 * (count - 1))]"),
         "Uses an interpolated index instead of the nearest-rank percentile."),
        ("PYTHON", _LATENCY_PY.replace('return "/".join(":id" if part.isdigit() else part for part in parts)', "return path"),
         "Does not normalise numeric path segments."),
    ),
    tests=_latency_tests(),
    oracle=python_oracle(_LATENCY_PY),
    time_limit_seconds=1.5,
    estimated_minutes=25,
)


# ---------------------------------------------------------------------------
# 16. LRU cache service — data structures
# ---------------------------------------------------------------------------

_LRU_PY = '''import sys
from collections import OrderedDict


def main():
    data = sys.stdin.buffer.read().split()
    capacity, q = int(data[0]), int(data[1])
    cache = OrderedDict()
    out = []
    i = 2
    for _ in range(q):
        op = data[i]
        if op == b"GET":
            key = data[i + 1]
            i += 2
            if key in cache:
                cache.move_to_end(key)
                out.append(cache[key].decode())
            else:
                out.append("-1")
        else:
            key, value = data[i + 1], data[i + 2]
            i += 3
            cache[key] = value
            cache.move_to_end(key)
            if len(cache) > capacity:
                cache.popitem(last=False)
    print("\\n".join(out))


main()
'''


def _lru_tests() -> tuple[Test, ...]:
    r = random.Random(1616)

    def case(capacity: int, ops: list[str]) -> str:
        return f"{capacity} {len(ops)}\n" + "\n".join(ops) + "\n"

    def random_ops(n: int, keys: int, get_ratio: float = 0.5, max_value: int = 10**9) -> list[str]:
        ops = []
        for _ in range(n):
            key = f"k{r.randint(1, keys)}"
            ops.append(f"GET {key}" if r.random() < get_ratio else f"PUT {key} {r.randint(0, max_value)}")
        return ops

    return (
        Test(case(2, ["PUT a 1", "PUT b 2", "GET a", "PUT c 3", "GET b", "GET c"]), hidden=False,
             explanation="Reading 'a' makes 'b' the least recently used, so PUT c evicts b."),
        Test(case(1, ["PUT x 5", "PUT x 6", "GET x", "PUT y 7", "GET x"]), hidden=False,
             explanation="Updating a key replaces its value; capacity 1 keeps only the latest key."),
        Test(case(3, ["GET missing"])),
        Test(case(2, ["PUT a 1", "PUT b 2", "PUT a 10", "PUT c 3", "GET a", "GET b", "GET c"])),
        Test(case(5, random_ops(1000, 12))),
        Test(case(1000, random_ops(200000, 3000, get_ratio=0.05, max_value=999)), weight=2.0),
        Test(case(100000, random_ops(200000, 150000, get_ratio=0.05, max_value=999)), weight=2.0),
    )


LRU_CACHE = ProblemSpec(
    slug="be-lru-cache-service",
    title="LRU Cache Service",
    category="backend",
    difficulty="MEDIUM",
    summary="Implement a fixed-capacity least-recently-used cache.",
    roles=("backend-developer", "java-developer", "python-developer", "android-developer", "software-development-engineer", "software-engineer"),
    competencies=("programming", "core-java", "core-python", "kotlin-java", "data-structures"),
    statement=(
        "A service caches user profiles in memory with a fixed capacity and evicts the least recently "
        "used entry when it is full.\n\n"
        "Process Q operations:\n"
        "* GET key — print the cached value, or -1 if the key is not cached. A successful GET makes the "
        "key the most recently used.\n"
        "* PUT key value — insert or update the key (making it the most recently used). If the cache now "
        "holds more than capacity keys, evict the least recently used key.\n\n"
        "Both operations should run in O(1) average time."
    ),
    input_format="The first line contains capacity and Q. Each of the next Q lines is 'GET key' or 'PUT key value'.",
    output_format="One line per GET: the value or -1.",
    constraints="1 ≤ capacity ≤ 100 000\n1 ≤ Q ≤ 200 000, with at most 12 000 GET operations\nKeys are 1–20 letters or digits; values are integers 0 … 10^9",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        # TODO: choose a data structure with O(1) get and put.

    def get(self, key):
        # TODO
        return "-1"

    def put(self, key, value):
        # TODO
        pass


def main():
    data = sys.stdin.read().split()
    cache = LRUCache(int(data[0]))
    q, i, out = int(data[1]), 2, []
    for _ in range(q):
        if data[i] == "GET":
            out.append(cache.get(data[i + 1]))
            i += 2
        else:
            cache.put(data[i + 1], data[i + 2])
            i += 3
    print("\\n".join(out))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

class LRUCache {
public:
    explicit LRUCache(int capacity) : capacity_(capacity) {}
    string get(const string& key) {
        // TODO
        return "-1";
    }
    void put(const string& key, const string& value) {
        // TODO
    }
private:
    int capacity_;
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int capacity, q;
    cin >> capacity >> q;
    LRUCache cache(capacity);
    string op, key, value, out;
    while (q--) {
        cin >> op >> key;
        if (op == "GET") out += cache.get(key) + "\\n";
        else { cin >> value; cache.put(key, value); }
    }
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    static final class LRUCache {
        final int capacity;
        LRUCache(int capacity) { this.capacity = capacity; }
        String get(String key) {
            // TODO
            return "-1";
        }
        void put(String key, String value) {
            // TODO
        }
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        LRUCache cache = new LRUCache(in.nextInt());
        int q = in.nextInt();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < q; i++) {
            String op = in.next(), key = in.next();
            if (op.equals("GET")) out.append(cache.get(key)).append('\\n');
            else cache.put(key, in.next());
        }
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);

class LRUCache {
  constructor(capacity) {
    this.capacity = capacity;
    // TODO: choose a data structure with O(1) get and put.
  }
  get(key) {
    // TODO
    return '-1';
  }
  put(key, value) {
    // TODO
  }
}

const cache = new LRUCache(Number(data[0]));
const q = Number(data[1]);
const out = [];
let i = 2;
for (let k = 0; k < q; k++) {
  if (data[i] === 'GET') { out.push(cache.get(data[i + 1])); i += 2; }
  else { cache.put(data[i + 1], data[i + 2]); i += 3; }
}
console.log(out.join('\\n'));
''',
    },
    reference_solutions={
        "PYTHON": _LRU_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

class LRUCache {
public:
    explicit LRUCache(int capacity) : capacity_(capacity) {}
    string get(const string& key) {
        auto it = index_.find(key);
        if (it == index_.end()) return "-1";
        order_.splice(order_.begin(), order_, it->second);
        return it->second->second;
    }
    void put(const string& key, const string& value) {
        auto it = index_.find(key);
        if (it != index_.end()) {
            it->second->second = value;
            order_.splice(order_.begin(), order_, it->second);
            return;
        }
        order_.push_front({key, value});
        index_[key] = order_.begin();
        if ((int)index_.size() > capacity_) {
            index_.erase(order_.back().first);
            order_.pop_back();
        }
    }
private:
    int capacity_;
    list<pair<string, string>> order_;
    unordered_map<string, list<pair<string, string>>::iterator> index_;
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int capacity, q;
    cin >> capacity >> q;
    LRUCache cache(capacity);
    string op, key, value, out;
    while (q--) {
        cin >> op >> key;
        if (op == "GET") out += cache.get(key) + "\\n";
        else { cin >> value; cache.put(key, value); }
    }
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    static final class LRUCache extends LinkedHashMap<String, String> {
        final int capacity;
        LRUCache(int capacity) { super(16, 0.75f, true); this.capacity = capacity; }
        String read(String key) { String v = super.get(key); return v == null ? "-1" : v; }
        void write(String key, String value) { super.put(key, value); }
        @Override protected boolean removeEldestEntry(Map.Entry<String, String> eldest) { return size() > capacity; }
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        LRUCache cache = new LRUCache(in.nextInt());
        int q = in.nextInt();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < q; i++) {
            String op = in.next(), key = in.next();
            if (op.equals("GET")) out.append(cache.read(key)).append('\\n');
            else cache.write(key, in.next());
        }
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);

class LRUCache {
  constructor(capacity) {
    this.capacity = capacity;
    this.map = new Map();
  }
  get(key) {
    if (!this.map.has(key)) return '-1';
    const value = this.map.get(key);
    this.map.delete(key);
    this.map.set(key, value);
    return value;
  }
  put(key, value) {
    this.map.delete(key);
    this.map.set(key, value);
    if (this.map.size > this.capacity) this.map.delete(this.map.keys().next().value);
  }
}

const cache = new LRUCache(Number(data[0]));
const q = Number(data[1]);
const out = [];
let i = 2;
for (let k = 0; k < q; k++) {
  if (data[i] === 'GET') { out.push(cache.get(data[i + 1])); i += 2; }
  else { cache.put(data[i + 1], data[i + 2]); i += 3; }
}
console.log(out.join('\\n'));
''',
    },
    wrong_solutions=(
        ("PYTHON", _LRU_PY.replace("            if key in cache:\n                cache.move_to_end(key)\n", "            if key in cache:\n"),
         "Evicts in insertion order (GET does not refresh recency)."),
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
capacity, q = int(data[0]), int(data[1])
keys, values, out, i = [], {}, [], 2
for _ in range(q):
    if data[i] == "GET":
        k = data[i + 1]; i += 2
        if k in values:
            keys.remove(k); keys.append(k); out.append(values[k])
        else:
            out.append("-1")
    else:
        k, v = data[i + 1], data[i + 2]; i += 3
        if k in values:
            keys.remove(k)
        keys.append(k); values[k] = v
        if len(keys) > capacity:
            del values[keys.pop(0)]
print("\\n".join(out))
''', "Correct but O(capacity) per operation; must exceed the time limit on large inputs."),
    ),
    tests=_lru_tests(),
    oracle=python_oracle(_LRU_PY),
    time_limit_seconds=1.0,
    memory_limit_kb=256_000,
    estimated_minutes=25,
)


PROBLEMS = (RATE_LIMITER, SIGNUP_VALIDATION, LATENCY_REPORT, LRU_CACHE)
