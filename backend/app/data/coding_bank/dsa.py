"""DSA and algorithms problems (C++17, Java 13, Python 3.8, Node.js 12)."""

from __future__ import annotations

import random

from app.data.coding_bank import ProblemSpec, Test, python_oracle

GENERAL = ("CPP", "JAVA", "PYTHON", "JAVASCRIPT")
SDE = ("software-development-engineer", "software-engineer")
LANG_DEVS = ("java-developer", "python-developer")
LANG_COMPS = ("dsa-java", "problem-solving-python")

# Shared fast input reader for Java solutions (Scanner is too slow for 10^5 tokens).
JAVA_READER = """    static final class FastReader {
        private final DataInputStream in = new DataInputStream(new BufferedInputStream(System.in, 1 << 16));
        private int read() throws IOException { return in.read(); }
        long nextLong() throws IOException {
            int c = read();
            while (c != '-' && (c < '0' || c > '9')) { if (c == -1) throw new EOFException(); c = read(); }
            boolean negative = c == '-';
            if (negative) c = read();
            long value = 0;
            while (c >= '0' && c <= '9') { value = value * 10 + (c - '0'); c = read(); }
            return negative ? -value : value;
        }
        int nextInt() throws IOException { return (int) nextLong(); }
        String next() throws IOException {
            int c = read();
            while (c != -1 && c <= ' ') c = read();
            StringBuilder sb = new StringBuilder();
            while (c != -1 && c > ' ') { sb.append((char) c); c = read(); }
            return sb.toString();
        }
    }
"""


def _java(body: str) -> str:
    return "import java.io.*;\nimport java.util.*;\n\npublic class Main {\n" + JAVA_READER + body + "}\n"


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# 1. Bracket validator — stack
# ---------------------------------------------------------------------------

_BRACKETS_PY = '''import sys


def is_balanced(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in s:
        if ch in pairs:
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
        else:
            stack.append(ch)
    return not stack


def main():
    data = sys.stdin.read().split()
    t = int(data[0])
    print("\\n".join("YES" if is_balanced(data[i]) else "NO" for i in range(1, t + 1)))


main()
'''


def _brackets_tests() -> tuple[Test, ...]:
    r = _rng(101)

    def balanced(n: int) -> str:
        out, stack = [], []
        opens, closes = "([{", ")]}"
        while len(out) < n:
            remaining = n - len(out)
            if stack and (remaining <= len(stack) or r.random() < 0.45):
                out.append(closes[opens.index(stack.pop())])
            else:
                ch = r.choice(opens)
                stack.append(ch)
                out.append(ch)
        return "".join(out)

    def corrupt(s: str) -> str:
        i = r.randrange(len(s))
        return s[:i] + r.choice("()[]{}".replace(s[i], "")) + s[i + 1:]

    mixed = []
    for _ in range(300):
        s = balanced(r.randrange(1, 40) * 2)
        mixed.append(s if r.random() < 0.5 else corrupt(s))
    deep = "(" * 50000 + ")" * 50000
    return (
        Test("3\n()[]{}\n([)]\n{[()()]}\n", hidden=False, explanation="'([)]' closes '(' before the inner '['."),
        Test("2\n((\n}{\n", hidden=False, explanation="Unclosed brackets and a closer with nothing open are both unbalanced."),
        Test("4\n(\n)\n[]\n{}\n"),
        Test("3\n([]{[]})\n(((])))\n{[]}(\n"),
        Test(f"{len(mixed)}\n" + "\n".join(mixed) + "\n"),
        Test(f"2\n{deep}\n{deep[:-1]}]\n", weight=2.0),
        Test("1\n" + balanced(100000) + "\n", weight=2.0),
    )


BALANCED_BRACKETS = ProblemSpec(
    slug="dsa-bracket-validator",
    title="Bracket Validator",
    category="dsa",
    difficulty="EASY",
    summary="Decide whether each bracket sequence is correctly nested (stack).",
    roles=(*SDE, *LANG_DEVS),
    competencies=("data-structures", *LANG_COMPS),
    statement=(
        "A configuration linter needs to reject files whose brackets are not properly nested.\n\n"
        "You are given several strings made only of the characters ( ) [ ] { }. A string is balanced "
        "when every opening bracket is closed by the matching bracket type, and brackets close in the "
        "reverse order in which they were opened.\n\n"
        "For each string, print YES if it is balanced and NO otherwise."
    ),
    input_format="The first line contains T. Each of the next T lines contains one non-empty bracket string.",
    output_format="T lines, each YES or NO.",
    constraints="1 ≤ T ≤ 1000\nEach string has length 1 … 100 000\nThe total length of all strings is at most 200 000",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def is_balanced(s: str) -> bool:
    # TODO: return True if every bracket in s is closed in the correct order.
    return False


def main():
    data = sys.stdin.read().split()
    t = int(data[0])
    print("\\n".join("YES" if is_balanced(data[i]) else "NO" for i in range(1, t + 1)))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

bool isBalanced(const string& s) {
    // TODO: return true if every bracket in s is closed in the correct order.
    return false;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int t;
    cin >> t;
    string s;
    while (t--) {
        cin >> s;
        cout << (isBalanced(s) ? "YES" : "NO") << '\\n';
    }
    return 0;
}
''',
        "JAVA": _java('''
    static boolean isBalanced(String s) {
        // TODO: return true if every bracket in s is closed in the correct order.
        return false;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int t = in.nextInt();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < t; i++) out.append(isBalanced(in.next()) ? "YES" : "NO").append('\\n');
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);

function isBalanced(s) {
  // TODO: return true if every bracket in s is closed in the correct order.
  return false;
}

const t = parseInt(data[0], 10);
const out = [];
for (let i = 1; i <= t; i++) out.push(isBalanced(data[i]) ? 'YES' : 'NO');
console.log(out.join('\\n'));
''',
    },
    reference_solutions={
        "PYTHON": _BRACKETS_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

bool isBalanced(const string& s) {
    vector<char> stack;
    stack.reserve(s.size());
    for (char c : s) {
        if (c == '(' || c == '[' || c == '{') {
            stack.push_back(c);
        } else {
            char open = c == ')' ? '(' : (c == ']' ? '[' : '{');
            if (stack.empty() || stack.back() != open) return false;
            stack.pop_back();
        }
    }
    return stack.empty();
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int t;
    cin >> t;
    string s, out;
    while (t--) {
        cin >> s;
        out += isBalanced(s) ? "YES\\n" : "NO\\n";
    }
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    static boolean isBalanced(String s) {
        char[] stack = new char[s.length()];
        int top = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '(' || c == '[' || c == '{') {
                stack[top++] = c;
            } else {
                char open = c == ')' ? '(' : (c == ']' ? '[' : '{');
                if (top == 0 || stack[top - 1] != open) return false;
                top--;
            }
        }
        return top == 0;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int t = in.nextInt();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < t; i++) out.append(isBalanced(in.next()) ? "YES" : "NO").append('\\n');
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);

function isBalanced(s) {
  const match = { ')': '(', ']': '[', '}': '{' };
  const stack = [];
  for (const c of s) {
    if (c in match) {
      if (stack.length === 0 || stack[stack.length - 1] !== match[c]) return false;
      stack.pop();
    } else {
      stack.push(c);
    }
  }
  return stack.length === 0;
}

const t = parseInt(data[0], 10);
const out = [];
for (let i = 1; i <= t; i++) out.push(isBalanced(data[i]) ? 'YES' : 'NO');
console.log(out.join('\\n'));
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
for s in data[1:int(data[0]) + 1]:
    ok = s.count("(") == s.count(")") and s.count("[") == s.count("]") and s.count("{") == s.count("}")
    print("YES" if ok else "NO")
''', "Only compares bracket counts and ignores nesting order."),
    ),
    tests=_brackets_tests(),
    oracle=python_oracle(_BRACKETS_PY),
    time_limit_seconds=1.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 2. Count pairs with a target sum — hash map
# ---------------------------------------------------------------------------

_PAIRS_PY = '''import sys


def count_pairs(values, target):
    seen = {}
    pairs = 0
    for v in values:
        pairs += seen.get(target - v, 0)
        seen[v] = seen.get(v, 0) + 1
    return pairs


def main():
    data = sys.stdin.buffer.read().split()
    n, target = int(data[0]), int(data[1])
    values = list(map(int, data[2:2 + n]))
    print(count_pairs(values, target))


main()
'''


def _pairs_tests() -> tuple[Test, ...]:
    r = _rng(202)

    def case(values: list[int], target: int) -> str:
        return f"{len(values)} {target}\n{' '.join(map(str, values))}\n"

    random_small = [r.randint(-20, 20) for _ in range(2000)]
    random_big = [r.randint(-10**9, 10**9) for _ in range(20000)]
    random_big += [10**9 - v for v in random_big[:5000]]
    r.shuffle(random_big)
    return (
        Test(case([1, 5, 3, 3, 7], 6), hidden=False, explanation="(1, 5) and (3, 3) sum to 6."),
        Test(case([-2, 2, 0, 0], 0), hidden=False, explanation="(-2, 2) and (0, 0)."),
        Test(case([5], 10)),
        Test(case([4, 4, 4, 4], 8)),
        Test(case([1, 2, 3], 100)),
        Test(case(random_small, 0)),
        Test(case(random_big, 10**9), weight=2.0),
        Test(case([7] * 100000, 14), weight=2.0),  # answer needs 64-bit integers
    )


PAIR_SUM_COUNT = ProblemSpec(
    slug="dsa-pair-sum-count",
    title="Matching Transaction Pairs",
    category="dsa",
    difficulty="EASY",
    summary="Count index pairs whose values add up to a target (hash map).",
    roles=(*SDE, *LANG_DEVS, "backend-developer"),
    competencies=("data-structures", "arrays-strings", "programming", *LANG_COMPS),
    statement=(
        "A reconciliation job looks for pairs of ledger entries that cancel out to a target amount.\n\n"
        "Given n integers a[0..n-1] and an integer K, count the pairs of indices (i, j) with i < j and "
        "a[i] + a[j] = K. Equal values at different indices form distinct pairs."
    ),
    input_format="The first line contains n and K. The second line contains n integers.",
    output_format="A single integer: the number of pairs.",
    constraints="1 ≤ n ≤ 100 000\n-10^9 ≤ a[i] ≤ 10^9\n-2·10^9 ≤ K ≤ 2·10^9\nThe answer may exceed 32-bit range.",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def count_pairs(values, target):
    # TODO: count pairs i < j with values[i] + values[j] == target.
    return 0


def main():
    data = sys.stdin.buffer.read().split()
    n, target = int(data[0]), int(data[1])
    values = list(map(int, data[2:2 + n]))
    print(count_pairs(values, target))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

long long countPairs(const vector<long long>& values, long long target) {
    // TODO: count pairs i < j with values[i] + values[j] == target.
    return 0;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    long long target;
    cin >> n >> target;
    vector<long long> values(n);
    for (auto& v : values) cin >> v;
    cout << countPairs(values, target) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static long countPairs(long[] values, long target) {
        // TODO: count pairs i < j with values[i] + values[j] == target.
        return 0;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        long target = in.nextLong();
        long[] values = new long[n];
        for (int i = 0; i < n; i++) values[i] = in.nextLong();
        System.out.println(countPairs(values, target));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function countPairs(values, target) {
  // TODO: count pairs i < j with values[i] + values[j] === target.
  return 0;
}

const n = data[0];
const target = data[1];
console.log(String(countPairs(data.slice(2, 2 + n), target)));
''',
    },
    reference_solutions={
        "PYTHON": _PAIRS_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

long long countPairs(const vector<long long>& values, long long target) {
    unordered_map<long long, long long> seen;
    seen.reserve(values.size() * 2 + 1);
    long long pairs = 0;
    for (long long v : values) {
        auto it = seen.find(target - v);
        if (it != seen.end()) pairs += it->second;
        seen[v]++;
    }
    return pairs;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    long long target;
    cin >> n >> target;
    vector<long long> values(n);
    for (auto& v : values) cin >> v;
    cout << countPairs(values, target) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static long countPairs(long[] values, long target) {
        HashMap<Long, Integer> seen = new HashMap<>(values.length * 2);
        long pairs = 0;
        for (long v : values) {
            Integer c = seen.get(target - v);
            if (c != null) pairs += c;
            seen.merge(v, 1, Integer::sum);
        }
        return pairs;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        long target = in.nextLong();
        long[] values = new long[n];
        for (int i = 0; i < n; i++) values[i] = in.nextLong();
        System.out.println(countPairs(values, target));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function countPairs(values, target) {
  const seen = new Map();
  let pairs = 0;
  for (const v of values) {
    pairs += seen.get(target - v) || 0;
    seen.set(v, (seen.get(v) || 0) + 1);
  }
  return pairs;
}

const n = data[0];
const target = data[1];
console.log(String(countPairs(data.slice(2, 2 + n), target)));
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
n, k = int(data[0]), int(data[1])
values = set(map(int, data[2:2 + n]))
print(sum(1 for v in values if k - v in values and v < k - v))
''', "Uses a set of distinct values, so duplicate entries are not counted."),
        ("CPP", '''#include <bits/stdc++.h>
using namespace std;
int main() {
    int n; long long k; cin >> n >> k;
    vector<long long> a(n); for (auto& v : a) cin >> v;
    long long pairs = 0;
    for (int i = 0; i < n; i++) for (int j = i + 1; j < n; j++) if (a[i] + a[j] == k) pairs++;
    cout << pairs << endl;
}
''', "Correct but O(n^2); must exceed the time limit on large inputs."),
    ),
    tests=_pairs_tests(),
    oracle=python_oracle(_PAIRS_PY),
    time_limit_seconds=1.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 3. Longest window of distinct characters — sliding window / two pointers
# ---------------------------------------------------------------------------

_UNIQUE_PY = '''import sys


def longest_unique(s):
    last = {}
    best_len, best_start, left = 0, 0, 0
    for i, ch in enumerate(s):
        if ch in last and last[ch] >= left:
            left = last[ch] + 1
        last[ch] = i
        if i - left + 1 > best_len:
            best_len, best_start = i - left + 1, left
    return best_len, best_start


def main():
    s = sys.stdin.readline().strip()
    length, start = longest_unique(s)
    print(length, start)


main()
'''


def _unique_tests() -> tuple[Test, ...]:
    r = _rng(303)
    letters = "abcdefghijklmnopqrstuvwxyz"
    return (
        Test("abcabcbb\n", hidden=False, explanation="'abc' (length 3) first appears at index 0."),
        Test("pwwkew\n", hidden=False, explanation="'wke' has length 3 and starts at index 2."),
        Test("a\n"),
        Test("abba\n"),
        Test("zzzzzz\n"),
        Test(letters + "\n"),
        Test("".join(r.choice("abcde") for _ in range(5000)) + "\n"),
        Test("".join(r.choice(letters) for _ in range(100000)) + "\n", weight=2.0),
        Test((letters * 4000)[:100000] + "\n", weight=2.0),
    )


LONGEST_UNIQUE = ProblemSpec(
    slug="dsa-longest-distinct-window",
    title="Longest Distinct-Character Window",
    category="dsa",
    difficulty="MEDIUM",
    summary="Find the longest substring without repeated characters (sliding window).",
    roles=(*SDE, *LANG_DEVS),
    competencies=("arrays-strings", "algorithms", *LANG_COMPS),
    statement=(
        "A session-token generator must avoid repeated characters inside any window it emits.\n\n"
        "Given a string s of lowercase letters, find the length of the longest contiguous substring in "
        "which no character repeats. Also report the 0-based start index of that substring; if several "
        "substrings have the maximum length, report the leftmost one."
    ),
    input_format="One line containing s.",
    output_format="Two integers separated by a space: the maximum length and its leftmost start index.",
    constraints="1 ≤ |s| ≤ 100 000\ns contains only 'a'–'z'",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def longest_unique(s: str):
    # TODO: return (length, start) of the leftmost longest substring with no repeated character.
    return 0, 0


def main():
    s = sys.stdin.readline().strip()
    length, start = longest_unique(s)
    print(length, start)


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

pair<int, int> longestUnique(const string& s) {
    // TODO: return {length, start} of the leftmost longest substring with no repeated character.
    return {0, 0};
}

int main() {
    string s;
    cin >> s;
    pair<int, int> answer = longestUnique(s);
    cout << answer.first << ' ' << answer.second << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static int[] longestUnique(String s) {
        // TODO: return {length, start} of the leftmost longest substring with no repeated character.
        return new int[] {0, 0};
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int[] answer = longestUnique(in.next());
        System.out.println(answer[0] + " " + answer[1]);
    }
'''),
        "JAVASCRIPT": '''const s = require('fs').readFileSync(0, 'utf8').trim();

function longestUnique(str) {
  // TODO: return [length, start] of the leftmost longest substring with no repeated character.
  return [0, 0];
}

const [length, start] = longestUnique(s);
console.log(length + ' ' + start);
''',
    },
    reference_solutions={
        "PYTHON": _UNIQUE_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

pair<int, int> longestUnique(const string& s) {
    int last[26];
    fill(last, last + 26, -1);
    int bestLen = 0, bestStart = 0, left = 0;
    for (int i = 0; i < (int)s.size(); i++) {
        int c = s[i] - 'a';
        if (last[c] >= left) left = last[c] + 1;
        last[c] = i;
        if (i - left + 1 > bestLen) {
            bestLen = i - left + 1;
            bestStart = left;
        }
    }
    return {bestLen, bestStart};
}

int main() {
    string s;
    cin >> s;
    pair<int, int> answer = longestUnique(s);
    cout << answer.first << ' ' << answer.second << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static int[] longestUnique(String s) {
        int[] last = new int[26];
        Arrays.fill(last, -1);
        int bestLen = 0, bestStart = 0, left = 0;
        for (int i = 0; i < s.length(); i++) {
            int c = s.charAt(i) - 'a';
            if (last[c] >= left) left = last[c] + 1;
            last[c] = i;
            if (i - left + 1 > bestLen) {
                bestLen = i - left + 1;
                bestStart = left;
            }
        }
        return new int[] {bestLen, bestStart};
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int[] answer = longestUnique(in.next());
        System.out.println(answer[0] + " " + answer[1]);
    }
'''),
        "JAVASCRIPT": '''const s = require('fs').readFileSync(0, 'utf8').trim();

function longestUnique(str) {
  const last = new Map();
  let bestLen = 0;
  let bestStart = 0;
  let left = 0;
  for (let i = 0; i < str.length; i++) {
    const c = str[i];
    if (last.has(c) && last.get(c) >= left) left = last.get(c) + 1;
    last.set(c, i);
    if (i - left + 1 > bestLen) {
      bestLen = i - left + 1;
      bestStart = left;
    }
  }
  return [bestLen, bestStart];
}

const [length, start] = longestUnique(s);
console.log(length + ' ' + start);
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
s = sys.stdin.readline().strip()
last, best, best_start, left = {}, 0, 0, 0
for i, ch in enumerate(s):
    if ch in last:
        left = last[ch] + 1
    last[ch] = i
    if i - left + 1 > best:
        best, best_start = i - left + 1, left
print(best, best_start)
''', "Moves the window start backwards (fails on 'abba')."),
    ),
    tests=_unique_tests(),
    oracle=python_oracle(_UNIQUE_PY),
    time_limit_seconds=1.0,
    estimated_minutes=20,
)


# ---------------------------------------------------------------------------
# 4. Merge booking intervals — sorting
# ---------------------------------------------------------------------------

_MERGE_PY = '''import sys


def merge(intervals):
    intervals.sort()
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return merged


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    intervals = [[int(data[1 + 2 * i]), int(data[2 + 2 * i])] for i in range(n)]
    merged = merge(intervals)
    out = [str(len(merged))]
    out.extend("%d %d" % (s, e) for s, e in merged)
    print("\\n".join(out))


main()
'''


def _merge_tests() -> tuple[Test, ...]:
    r = _rng(404)

    def case(intervals) -> str:
        return f"{len(intervals)}\n" + "".join(f"{s} {e}\n" for s, e in intervals)

    def rand(n: int, span: int, width: int):
        out = []
        for _ in range(n):
            s = r.randint(0, span)
            out.append((s, min(10**9, s + r.randint(0, width))))
        return out

    return (
        Test(case([(1, 3), (8, 10), (2, 6), (15, 18)]), hidden=False, explanation="[1,3] and [2,6] overlap and merge into [1,6]."),
        Test(case([(1, 4), (4, 5)]), hidden=False, explanation="Intervals that share an endpoint are merged."),
        Test(case([(5, 5)])),
        Test(case([(1, 10), (2, 3), (4, 5)])),
        Test(case([(6, 8), (1, 2), (3, 4)])),
        Test(case(rand(1000, 5000, 20))),
        Test(case([(3 * i, 3 * i + 1) for i in r.sample(range(3000), 3000)])),
        Test(case(rand(100000, 10**9, 200000)), weight=2.0),
        Test(case([(i, i + 1) for i in range(100000, 0, -1)]), weight=2.0),
    )


MERGE_INTERVALS = ProblemSpec(
    slug="dsa-merge-booking-intervals",
    title="Merge Booking Intervals",
    category="dsa",
    difficulty="MEDIUM",
    summary="Merge overlapping time intervals after sorting them.",
    roles=(*SDE, *LANG_DEVS, "backend-developer"),
    competencies=("algorithms", "programming", *LANG_COMPS),
    statement=(
        "A room-booking service stores reservations as closed intervals [start, end]. To show a room's "
        "busy periods, overlapping reservations must be combined.\n\n"
        "Two intervals overlap when they share at least one point (so [1,4] and [4,5] overlap). Merge "
        "all overlapping intervals and print the result in increasing order of start."
    ),
    input_format="The first line contains n. Each of the next n lines contains start and end.",
    output_format="First the number of merged intervals m, then m lines 'start end' in increasing order.",
    constraints="1 ≤ n ≤ 100 000\n0 ≤ start ≤ end ≤ 10^9\nThe input is not sorted.\nThe merged result has at most 3 000 intervals.",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def merge(intervals):
    # TODO: return the merged intervals as a list of [start, end], sorted by start.
    return intervals


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    intervals = [[int(data[1 + 2 * i]), int(data[2 + 2 * i])] for i in range(n)]
    merged = merge(intervals)
    print(len(merged))
    print("\\n".join("%d %d" % (s, e) for s, e in merged))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

vector<pair<long long, long long>> mergeIntervals(vector<pair<long long, long long>> intervals) {
    // TODO: return the merged intervals sorted by start.
    return intervals;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    cin >> n;
    vector<pair<long long, long long>> intervals(n);
    for (auto& it : intervals) cin >> it.first >> it.second;
    vector<pair<long long, long long>> merged = mergeIntervals(intervals);
    cout << merged.size() << '\\n';
    for (auto& it : merged) cout << it.first << ' ' << it.second << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static List<long[]> merge(long[][] intervals) {
        // TODO: return the merged intervals sorted by start.
        return new ArrayList<>(Arrays.asList(intervals));
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        long[][] intervals = new long[n][2];
        for (int i = 0; i < n; i++) { intervals[i][0] = in.nextLong(); intervals[i][1] = in.nextLong(); }
        List<long[]> merged = merge(intervals);
        StringBuilder out = new StringBuilder().append(merged.size()).append('\\n');
        for (long[] it : merged) out.append(it[0]).append(' ').append(it[1]).append('\\n');
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function merge(intervals) {
  // TODO: return the merged intervals as [[start, end], ...] sorted by start.
  return intervals;
}

const n = data[0];
const intervals = [];
for (let i = 0; i < n; i++) intervals.push([data[1 + 2 * i], data[2 + 2 * i]]);
const merged = merge(intervals);
console.log([String(merged.length)].concat(merged.map((it) => it[0] + ' ' + it[1])).join('\\n'));
''',
    },
    reference_solutions={
        "PYTHON": _MERGE_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

vector<pair<long long, long long>> mergeIntervals(vector<pair<long long, long long>> intervals) {
    sort(intervals.begin(), intervals.end());
    vector<pair<long long, long long>> merged;
    for (auto& it : intervals) {
        if (!merged.empty() && it.first <= merged.back().second) {
            merged.back().second = max(merged.back().second, it.second);
        } else {
            merged.push_back(it);
        }
    }
    return merged;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    cin >> n;
    vector<pair<long long, long long>> intervals(n);
    for (auto& it : intervals) cin >> it.first >> it.second;
    vector<pair<long long, long long>> merged = mergeIntervals(intervals);
    string out = to_string(merged.size()) + "\\n";
    for (auto& it : merged) out += to_string(it.first) + " " + to_string(it.second) + "\\n";
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    static List<long[]> merge(long[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] != b[0] ? Long.compare(a[0], b[0]) : Long.compare(a[1], b[1]));
        List<long[]> merged = new ArrayList<>();
        for (long[] it : intervals) {
            if (!merged.isEmpty() && it[0] <= merged.get(merged.size() - 1)[1]) {
                long[] last = merged.get(merged.size() - 1);
                last[1] = Math.max(last[1], it[1]);
            } else {
                merged.add(new long[] {it[0], it[1]});
            }
        }
        return merged;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        long[][] intervals = new long[n][2];
        for (int i = 0; i < n; i++) { intervals[i][0] = in.nextLong(); intervals[i][1] = in.nextLong(); }
        List<long[]> merged = merge(intervals);
        StringBuilder out = new StringBuilder().append(merged.size()).append('\\n');
        for (long[] it : merged) out.append(it[0]).append(' ').append(it[1]).append('\\n');
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function merge(intervals) {
  intervals.sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
  const merged = [];
  for (const it of intervals) {
    const last = merged[merged.length - 1];
    if (last && it[0] <= last[1]) {
      last[1] = Math.max(last[1], it[1]);
    } else {
      merged.push([it[0], it[1]]);
    }
  }
  return merged;
}

const n = data[0];
const intervals = [];
for (let i = 0; i < n; i++) intervals.push([data[1 + 2 * i], data[2 + 2 * i]]);
const merged = merge(intervals);
console.log([String(merged.length)].concat(merged.map((it) => it[0] + ' ' + it[1])).join('\\n'));
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
n = int(data[0])
iv = [[int(data[1 + 2 * i]), int(data[2 + 2 * i])] for i in range(n)]
merged = []
for s, e in iv:
    if merged and s <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], e)
    else:
        merged.append([s, e])
merged.sort()
print(len(merged))
for s, e in merged:
    print(s, e)
''', "Merges in input order without sorting first."),
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
n = int(data[0])
iv = sorted([int(data[1 + 2 * i]), int(data[2 + 2 * i])] for i in range(n))
merged = []
for s, e in iv:
    if merged and s < merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], e)
    else:
        merged.append([s, e])
print(len(merged))
for s, e in merged:
    print(s, e)
''', "Treats touching intervals ([1,4] and [4,5]) as separate."),
    ),
    tests=_merge_tests(),
    oracle=python_oracle(_MERGE_PY),
    time_limit_seconds=1.5,
    estimated_minutes=20,
)


# ---------------------------------------------------------------------------
# 5. First position in a sorted list — binary search
# ---------------------------------------------------------------------------

_FIRST_PY = '''import sys
from bisect import bisect_left


def first_index(values, x):
    i = bisect_left(values, x)
    return i if i < len(values) and values[i] == x else -1


def main():
    data = sys.stdin.buffer.read().split()
    n, q = int(data[0]), int(data[1])
    values = list(map(int, data[2:2 + n]))
    queries = data[2 + n:2 + n + q]
    print("\\n".join(str(first_index(values, int(x))) for x in queries))


main()
'''


def _first_tests() -> tuple[Test, ...]:
    r = _rng(505)

    def case(values, queries) -> str:
        return f"{len(values)} {len(queries)}\n{' '.join(map(str, values))}\n{' '.join(map(str, queries))}\n"

    dup = sorted(r.randint(-50, 50) for _ in range(1000))
    big = sorted(r.randint(-10**9, 10**9) for _ in range(100000))
    big_queries = [r.choice(big) if r.random() < 0.7 else r.randint(-10**9, 10**9) for _ in range(8000)]
    return (
        Test(case([1, 3, 3, 3, 8, 10], [3, 8, 5]), hidden=False, explanation="The first 3 is at index 1; 5 is missing."),
        Test(case([2, 2, 2], [2, 1, 3]), hidden=False),
        Test(case([7], [7, -7])),
        Test(case([-5, -5, 0, 0, 0, 9], [-5, 0, 9, 10, -6])),
        Test(case(dup, [r.randint(-60, 60) for _ in range(500)])),
        Test(case(big, big_queries), weight=2.0),
        Test(case([4] * 100000, [5, 3, 4] * 6000), weight=2.0),
    )


FIRST_OCCURRENCE = ProblemSpec(
    slug="dsa-first-position-sorted",
    title="First Position in a Sorted List",
    category="dsa",
    difficulty="EASY",
    summary="Answer first-occurrence queries on a sorted array (binary search).",
    roles=(*SDE, *LANG_DEVS),
    competencies=("algorithms", "arrays-strings", *LANG_COMPS),
    statement=(
        "An audit log is stored as a list of event timestamps in non-decreasing order. Investigators "
        "repeatedly ask: where does timestamp x first appear?\n\n"
        "For each query x, print the smallest 0-based index i with values[i] = x, or -1 if x does not appear."
    ),
    input_format="The first line contains n and q. The second line has n sorted integers. The third line has q query values.",
    output_format="q lines, one index (or -1) per query.",
    constraints="1 ≤ n ≤ 100 000\n1 ≤ q ≤ 20 000\n-10^9 ≤ values, x ≤ 10^9\nvalues is sorted in non-decreasing order",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def first_index(values, x):
    # TODO: return the first index of x in the sorted list, or -1.
    return -1


def main():
    data = sys.stdin.buffer.read().split()
    n, q = int(data[0]), int(data[1])
    values = list(map(int, data[2:2 + n]))
    queries = data[2 + n:2 + n + q]
    print("\\n".join(str(first_index(values, int(x))) for x in queries))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

int firstIndex(const vector<long long>& values, long long x) {
    // TODO: return the first index of x in the sorted vector, or -1.
    return -1;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, q;
    cin >> n >> q;
    vector<long long> values(n);
    for (auto& v : values) cin >> v;
    string out;
    while (q--) {
        long long x;
        cin >> x;
        out += to_string(firstIndex(values, x)) + "\\n";
    }
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    static int firstIndex(long[] values, long x) {
        // TODO: return the first index of x in the sorted array, or -1.
        return -1;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt(), q = in.nextInt();
        long[] values = new long[n];
        for (int i = 0; i < n; i++) values[i] = in.nextLong();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < q; i++) out.append(firstIndex(values, in.nextLong())).append('\\n');
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function firstIndex(values, x) {
  // TODO: return the first index of x in the sorted array, or -1.
  return -1;
}

const n = data[0];
const q = data[1];
const values = data.slice(2, 2 + n);
const out = [];
for (let i = 0; i < q; i++) out.push(firstIndex(values, data[2 + n + i]));
console.log(out.join('\\n'));
''',
    },
    reference_solutions={
        "PYTHON": _FIRST_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

int firstIndex(const vector<long long>& values, long long x) {
    auto it = lower_bound(values.begin(), values.end(), x);
    if (it == values.end() || *it != x) return -1;
    return (int)(it - values.begin());
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, q;
    cin >> n >> q;
    vector<long long> values(n);
    for (auto& v : values) cin >> v;
    string out;
    while (q--) {
        long long x;
        cin >> x;
        out += to_string(firstIndex(values, x)) + "\\n";
    }
    cout << out;
    return 0;
}
''',
        "JAVA": _java('''
    static int firstIndex(long[] values, long x) {
        int lo = 0, hi = values.length;
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (values[mid] < x) lo = mid + 1; else hi = mid;
        }
        return lo < values.length && values[lo] == x ? lo : -1;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt(), q = in.nextInt();
        long[] values = new long[n];
        for (int i = 0; i < n; i++) values[i] = in.nextLong();
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < q; i++) out.append(firstIndex(values, in.nextLong())).append('\\n');
        System.out.print(out);
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function firstIndex(values, x) {
  let lo = 0;
  let hi = values.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (values[mid] < x) lo = mid + 1; else hi = mid;
  }
  return lo < values.length && values[lo] === x ? lo : -1;
}

const n = data[0];
const q = data[1];
const values = data.slice(2, 2 + n);
const out = [];
for (let i = 0; i < q; i++) out.push(firstIndex(values, data[2 + n + i]));
console.log(out.join('\\n'));
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
n, q = int(data[0]), int(data[1])
a = list(map(int, data[2:2 + n]))
out = []
for x in map(int, data[2 + n:2 + n + q]):
    lo, hi, found = 0, n - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == x:
            found = mid
            break
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid - 1
    out.append(str(found))
print("\\n".join(out))
''', "Returns any matching index rather than the first one."),
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
n, q = int(data[0]), int(data[1])
a = list(map(int, data[2:2 + n]))
out = []
for x in map(int, data[2 + n:2 + n + q]):
    try:
        out.append(str(a.index(x)))
    except ValueError:
        out.append("-1")
print("\\n".join(out))
''', "Linear scan per query; must exceed the time limit on large inputs."),
    ),
    tests=_first_tests(),
    oracle=python_oracle(_FIRST_PY),
    time_limit_seconds=1.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 6. Warehouse robot route — BFS on a grid graph
# ---------------------------------------------------------------------------

_GRID_PY = '''import sys
from collections import deque


def shortest_path(grid):
    rows, cols = len(grid), len(grid[0])
    start = end = None
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == "S":
                start = (r, c)
            elif grid[r][c] == "E":
                end = (r, c)
    dist = [[-1] * cols for _ in range(rows)]
    dist[start[0]][start[1]] = 0
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        if (r, c) == end:
            return dist[r][c]
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] != "#" and dist[nr][nc] == -1:
                dist[nr][nc] = dist[r][c] + 1
                queue.append((nr, nc))
    return -1


def main():
    data = sys.stdin.read().split()
    rows, cols = int(data[0]), int(data[1])
    grid = data[2:2 + rows]
    print(shortest_path(grid))


main()
'''


def _grid_tests() -> tuple[Test, ...]:
    r = _rng(606)

    def case(grid: list[str]) -> str:
        return f"{len(grid)} {len(grid[0])}\n" + "\n".join(grid) + "\n"

    def random_grid(rows: int, cols: int, wall: float) -> list[str]:
        cells = [["#" if r.random() < wall else "." for _ in range(cols)] for _ in range(rows)]
        cells[0][0], cells[rows - 1][cols - 1] = "S", "E"
        return ["".join(row) for row in cells]

    def serpentine(rows: int, cols: int) -> list[str]:
        grid = [["."] * cols for _ in range(rows)]
        for row in range(1, rows, 2):
            for c in range(cols):
                grid[row][c] = "#"
            grid[row][cols - 1 if (row // 2) % 2 == 0 else 0] = "."
        grid[0][0], grid[rows - 1][cols - 1] = "S", "E"
        return ["".join(g) for g in grid]

    return (
        Test(case(["S.#", "..#", "#.E"]), hidden=False, explanation="S → down → right → down → right: 4 moves."),
        Test(case(["S#E"]), hidden=False, explanation="The wall blocks the only route."),
        Test(case(["SE"])),
        Test(case(["S", ".", ".", "E"])),
        Test(case(["S.....", "#####.", "......", ".#####", ".....E"])),
        Test(case(["S.#", ".##", "##E"])),
        Test(case(random_grid(60, 80, 0.25))),
        Test(case(random_grid(300, 300, 0.3)), weight=2.0),
        Test(case(serpentine(299, 300)), weight=2.0),
    )


GRID_PATH = ProblemSpec(
    slug="dsa-warehouse-robot-route",
    title="Warehouse Robot Route",
    category="dsa",
    difficulty="MEDIUM",
    summary="Shortest path for a robot on a grid with obstacles (BFS).",
    roles=(*SDE, *LANG_DEVS),
    competencies=("data-structures", "algorithms", *LANG_COMPS),
    statement=(
        "A warehouse floor is a grid. A robot starts at S and must reach the packing station E. Each "
        "move goes one cell up, down, left or right (no diagonal moves) and cannot enter shelves (#) "
        "or leave the grid.\n\nPrint the minimum number of moves, or -1 if E cannot be reached."
    ),
    input_format="The first line contains R and C. The next R lines each contain C characters from '.', '#', 'S', 'E'.",
    output_format="A single integer: the minimum number of moves, or -1.",
    constraints="1 ≤ R, C ≤ 300\nExactly one S and exactly one E",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys
from collections import deque


def shortest_path(grid):
    # TODO: return the minimum number of moves from S to E, or -1.
    return -1


def main():
    data = sys.stdin.read().split()
    rows = int(data[0])
    print(shortest_path(data[2:2 + rows]))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

int shortestPath(const vector<string>& grid) {
    // TODO: return the minimum number of moves from S to E, or -1.
    return -1;
}

int main() {
    int rows, cols;
    cin >> rows >> cols;
    vector<string> grid(rows);
    for (auto& row : grid) cin >> row;
    cout << shortestPath(grid) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static int shortestPath(String[] grid) {
        // TODO: return the minimum number of moves from S to E, or -1.
        return -1;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int rows = in.nextInt();
        in.nextInt();
        String[] grid = new String[rows];
        for (int i = 0; i < rows; i++) grid[i] = in.next();
        System.out.println(shortestPath(grid));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);

function shortestPath(grid) {
  // TODO: return the minimum number of moves from S to E, or -1.
  return -1;
}

const rows = parseInt(data[0], 10);
console.log(String(shortestPath(data.slice(2, 2 + rows))));
''',
    },
    reference_solutions={
        "PYTHON": _GRID_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

int shortestPath(const vector<string>& grid) {
    int rows = grid.size(), cols = grid[0].size();
    int sr = 0, sc = 0, er = 0, ec = 0;
    for (int r = 0; r < rows; r++)
        for (int c = 0; c < cols; c++) {
            if (grid[r][c] == 'S') { sr = r; sc = c; }
            if (grid[r][c] == 'E') { er = r; ec = c; }
        }
    vector<int> dist(rows * cols, -1);
    deque<int> q;
    dist[sr * cols + sc] = 0;
    q.push_back(sr * cols + sc);
    const int dr[4] = {1, -1, 0, 0}, dc[4] = {0, 0, 1, -1};
    while (!q.empty()) {
        int cur = q.front();
        q.pop_front();
        int r = cur / cols, c = cur % cols;
        if (r == er && c == ec) return dist[cur];
        for (int k = 0; k < 4; k++) {
            int nr = r + dr[k], nc = c + dc[k];
            if (nr < 0 || nc < 0 || nr >= rows || nc >= cols || grid[nr][nc] == '#') continue;
            int nxt = nr * cols + nc;
            if (dist[nxt] != -1) continue;
            dist[nxt] = dist[cur] + 1;
            q.push_back(nxt);
        }
    }
    return -1;
}

int main() {
    int rows, cols;
    cin >> rows >> cols;
    vector<string> grid(rows);
    for (auto& row : grid) cin >> row;
    cout << shortestPath(grid) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static int shortestPath(String[] grid) {
        int rows = grid.length, cols = grid[0].length();
        int start = 0, end = 0;
        for (int r = 0; r < rows; r++)
            for (int c = 0; c < cols; c++) {
                if (grid[r].charAt(c) == 'S') start = r * cols + c;
                if (grid[r].charAt(c) == 'E') end = r * cols + c;
            }
        int[] dist = new int[rows * cols];
        Arrays.fill(dist, -1);
        int[] queue = new int[rows * cols];
        int head = 0, tail = 0;
        dist[start] = 0;
        queue[tail++] = start;
        int[] dr = {1, -1, 0, 0}, dc = {0, 0, 1, -1};
        while (head < tail) {
            int cur = queue[head++];
            if (cur == end) return dist[cur];
            int r = cur / cols, c = cur % cols;
            for (int k = 0; k < 4; k++) {
                int nr = r + dr[k], nc = c + dc[k];
                if (nr < 0 || nc < 0 || nr >= rows || nc >= cols || grid[nr].charAt(nc) == '#') continue;
                int nxt = nr * cols + nc;
                if (dist[nxt] != -1) continue;
                dist[nxt] = dist[cur] + 1;
                queue[tail++] = nxt;
            }
        }
        return -1;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int rows = in.nextInt();
        in.nextInt();
        String[] grid = new String[rows];
        for (int i = 0; i < rows; i++) grid[i] = in.next();
        System.out.println(shortestPath(grid));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);

function shortestPath(grid) {
  const rows = grid.length;
  const cols = grid[0].length;
  let start = 0;
  let end = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (grid[r][c] === 'S') start = r * cols + c;
      if (grid[r][c] === 'E') end = r * cols + c;
    }
  }
  const dist = new Int32Array(rows * cols).fill(-1);
  const queue = new Int32Array(rows * cols);
  let head = 0;
  let tail = 0;
  dist[start] = 0;
  queue[tail++] = start;
  const moves = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  while (head < tail) {
    const cur = queue[head++];
    if (cur === end) return dist[cur];
    const r = Math.floor(cur / cols);
    const c = cur % cols;
    for (const [dr, dc] of moves) {
      const nr = r + dr;
      const nc = c + dc;
      if (nr < 0 || nc < 0 || nr >= rows || nc >= cols || grid[nr][nc] === '#') continue;
      const next = nr * cols + nc;
      if (dist[next] !== -1) continue;
      dist[next] = dist[cur] + 1;
      queue[tail++] = next;
    }
  }
  return -1;
}

const rows = parseInt(data[0], 10);
console.log(String(shortestPath(data.slice(2, 2 + rows))));
''',
    },
    wrong_solutions=(
        ("PYTHON", _GRID_PY.replace("((1, 0), (-1, 0), (0, 1), (0, -1))", "((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))"),
         "Allows diagonal moves."),
    ),
    tests=_grid_tests(),
    oracle=python_oracle(_GRID_PY),
    time_limit_seconds=1.0,
    memory_limit_kb=256_000,
    estimated_minutes=25,
)


# ---------------------------------------------------------------------------
# 7. Ways to make change — dynamic programming
# ---------------------------------------------------------------------------

_COINS_PY = '''import sys

MOD = 1000000007


def count_ways(coins, amount):
    ways = [0] * (amount + 1)
    ways[0] = 1
    for coin in coins:
        for value in range(coin, amount + 1):
            ways[value] = (ways[value] + ways[value - coin]) % MOD
    return ways[amount]


def main():
    data = sys.stdin.read().split()
    n, amount = int(data[0]), int(data[1])
    coins = list(map(int, data[2:2 + n]))
    print(count_ways(coins, amount))


main()
'''


def _coin_tests() -> tuple[Test, ...]:
    r = _rng(707)

    def case(coins, amount) -> str:
        return f"{len(coins)} {amount}\n{' '.join(map(str, coins))}\n"

    return (
        Test(case([1, 2, 5], 5), hidden=False, explanation="5, 2+2+1, 2+1+1+1, 1+1+1+1+1 — order does not matter."),
        Test(case([2], 3), hidden=False, explanation="An odd amount cannot be made from 2s."),
        Test(case([7], 0)),
        Test(case([3, 5, 7], 1)),
        Test(case([1], 10000)),
        Test(case([2, 3, 5, 6], 10)),
        Test(case(r.sample(range(1, 200), 30), 5000)),
        Test(case(list(range(1, 51)), 10000), weight=2.0),
    )


COIN_CHANGE = ProblemSpec(
    slug="dsa-ways-to-make-change",
    title="Ways to Make Change",
    category="dsa",
    difficulty="MEDIUM",
    summary="Count coin combinations for an amount (dynamic programming).",
    roles=(*SDE, *LANG_DEVS),
    competencies=("algorithms", *LANG_COMPS),
    statement=(
        "A vending machine can return change using an unlimited supply of each of n distinct coin "
        "denominations. Count how many different combinations of coins add up to exactly the given "
        "amount. Combinations are unordered: 2+1 and 1+2 are the same combination.\n\n"
        "Because the count can be very large, print it modulo 1 000 000 007. There is exactly one way "
        "to make an amount of 0 (use no coins)."
    ),
    input_format="The first line contains n and amount. The second line contains n distinct denominations.",
    output_format="The number of combinations modulo 1 000 000 007.",
    constraints="1 ≤ n ≤ 50\n0 ≤ amount ≤ 10 000\n1 ≤ denomination ≤ 10 000",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys

MOD = 1000000007


def count_ways(coins, amount):
    # TODO: number of unordered coin combinations summing to amount, modulo MOD.
    return 0


def main():
    data = sys.stdin.read().split()
    n, amount = int(data[0]), int(data[1])
    print(count_ways(list(map(int, data[2:2 + n])), amount))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

const long long MOD = 1000000007LL;

long long countWays(const vector<int>& coins, int amount) {
    // TODO: number of unordered coin combinations summing to amount, modulo MOD.
    return 0;
}

int main() {
    int n, amount;
    cin >> n >> amount;
    vector<int> coins(n);
    for (auto& c : coins) cin >> c;
    cout << countWays(coins, amount) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static final long MOD = 1_000_000_007L;

    static long countWays(int[] coins, int amount) {
        // TODO: number of unordered coin combinations summing to amount, modulo MOD.
        return 0;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt(), amount = in.nextInt();
        int[] coins = new int[n];
        for (int i = 0; i < n; i++) coins[i] = in.nextInt();
        System.out.println(countWays(coins, amount));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);
const MOD = 1000000007;

function countWays(coins, amount) {
  // TODO: number of unordered coin combinations summing to amount, modulo MOD.
  return 0;
}

const n = data[0];
console.log(String(countWays(data.slice(2, 2 + n), data[1])));
''',
    },
    reference_solutions={
        "PYTHON": _COINS_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

const long long MOD = 1000000007LL;

long long countWays(const vector<int>& coins, int amount) {
    vector<long long> ways(amount + 1, 0);
    ways[0] = 1;
    for (int coin : coins)
        for (int value = coin; value <= amount; value++)
            ways[value] = (ways[value] + ways[value - coin]) % MOD;
    return ways[amount];
}

int main() {
    int n, amount;
    cin >> n >> amount;
    vector<int> coins(n);
    for (auto& c : coins) cin >> c;
    cout << countWays(coins, amount) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static final long MOD = 1_000_000_007L;

    static long countWays(int[] coins, int amount) {
        long[] ways = new long[amount + 1];
        ways[0] = 1;
        for (int coin : coins)
            for (int value = coin; value <= amount; value++)
                ways[value] = (ways[value] + ways[value - coin]) % MOD;
        return ways[amount];
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt(), amount = in.nextInt();
        int[] coins = new int[n];
        for (int i = 0; i < n; i++) coins[i] = in.nextInt();
        System.out.println(countWays(coins, amount));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);
const MOD = 1000000007;

function countWays(coins, amount) {
  const ways = new Array(amount + 1).fill(0);
  ways[0] = 1;
  for (const coin of coins) {
    for (let value = coin; value <= amount; value++) {
      ways[value] = (ways[value] + ways[value - coin]) % MOD;
    }
  }
  return ways[amount];
}

const n = data[0];
console.log(String(countWays(data.slice(2, 2 + n), data[1])));
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
MOD = 1000000007
data = sys.stdin.read().split()
n, amount = int(data[0]), int(data[1])
coins = list(map(int, data[2:2 + n]))
ways = [0] * (amount + 1)
ways[0] = 1
for value in range(1, amount + 1):
    for coin in coins:
        if coin <= value:
            ways[value] = (ways[value] + ways[value - coin]) % MOD
print(ways[amount])
''', "Counts ordered sequences (2+1 and 1+2 twice) instead of combinations."),
    ),
    tests=_coin_tests(),
    oracle=python_oracle(_COINS_PY),
    time_limit_seconds=1.0,
    estimated_minutes=25,
)


# ---------------------------------------------------------------------------
# 8. Budget combinations — recursion / backtracking
# ---------------------------------------------------------------------------

_SUBSET_PY = '''import sys


def count_subsets(prices, budget):
    n = len(prices)

    def go(i, remaining):
        if remaining == 0:
            return 1
        if i == n or remaining < 0:
            return 0
        return go(i + 1, remaining - prices[i]) + go(i + 1, remaining)

    return go(0, budget)


def main():
    data = sys.stdin.read().split()
    n, budget = int(data[0]), int(data[1])
    prices = list(map(int, data[2:2 + n]))
    print(count_subsets(prices, budget))


main()
'''


def _subset_tests() -> tuple[Test, ...]:
    r = _rng(808)

    def case(prices, budget) -> str:
        return f"{len(prices)} {budget}\n{' '.join(map(str, prices))}\n"

    twenty = [r.randint(1, 60) for _ in range(20)]
    return (
        Test(case([2, 3, 5, 7], 10), hidden=False, explanation="{3, 7} and {2, 3, 5}."),
        Test(case([4, 4, 4], 8), hidden=False, explanation="Items are distinct even when prices are equal: 3 ways."),
        Test(case([5], 5)),
        Test(case([5], 4)),
        Test(case([1] * 20, 10)),
        Test(case(twenty, sum(twenty) // 2)),
        Test(case([r.randint(1, 10**6) for _ in range(20)], 1500000)),
        Test(case([2 ** i for i in range(20)], 2 ** 20 - 1)),
    )


SUBSET_COUNT = ProblemSpec(
    slug="dsa-budget-combinations",
    title="Budget Combinations",
    category="dsa",
    difficulty="EASY",
    summary="Count subsets of items that exactly match a budget (recursion).",
    roles=(*SDE, *LANG_DEVS),
    competencies=("algorithms", *LANG_COMPS),
    statement=(
        "A team has a fixed equipment budget and a shortlist of n items with known prices. Count how "
        "many different subsets of the items cost exactly the budget. Each item can be chosen at most "
        "once; items with the same price are still different items.\n\n"
        "n is small, so an exhaustive recursive search (include / exclude each item) is expected."
    ),
    input_format="The first line contains n and budget. The second line contains n prices.",
    output_format="A single integer: the number of subsets whose total price equals the budget.",
    constraints="1 ≤ n ≤ 20\n1 ≤ budget ≤ 2·10^7\n1 ≤ price ≤ 10^6",
    languages=GENERAL,
    starter_code={
        "PYTHON": '''import sys


def count_subsets(prices, budget):
    # TODO: count subsets of prices whose sum is exactly budget.
    return 0


def main():
    data = sys.stdin.read().split()
    n, budget = int(data[0]), int(data[1])
    print(count_subsets(list(map(int, data[2:2 + n])), budget))


main()
''',
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

long long countSubsets(const vector<long long>& prices, long long budget) {
    // TODO: count subsets of prices whose sum is exactly budget.
    return 0;
}

int main() {
    int n;
    long long budget;
    cin >> n >> budget;
    vector<long long> prices(n);
    for (auto& p : prices) cin >> p;
    cout << countSubsets(prices, budget) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static long countSubsets(long[] prices, long budget) {
        // TODO: count subsets of prices whose sum is exactly budget.
        return 0;
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        long budget = in.nextLong();
        long[] prices = new long[n];
        for (int i = 0; i < n; i++) prices[i] = in.nextLong();
        System.out.println(countSubsets(prices, budget));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function countSubsets(prices, budget) {
  // TODO: count subsets of prices whose sum is exactly budget.
  return 0;
}

const n = data[0];
console.log(String(countSubsets(data.slice(2, 2 + n), data[1])));
''',
    },
    reference_solutions={
        "PYTHON": _SUBSET_PY,
        "CPP": '''#include <bits/stdc++.h>
using namespace std;

long long go(const vector<long long>& prices, size_t i, long long remaining) {
    if (remaining == 0) return 1;
    if (i == prices.size() || remaining < 0) return 0;
    return go(prices, i + 1, remaining - prices[i]) + go(prices, i + 1, remaining);
}

long long countSubsets(const vector<long long>& prices, long long budget) {
    return go(prices, 0, budget);
}

int main() {
    int n;
    long long budget;
    cin >> n >> budget;
    vector<long long> prices(n);
    for (auto& p : prices) cin >> p;
    cout << countSubsets(prices, budget) << '\\n';
    return 0;
}
''',
        "JAVA": _java('''
    static long go(long[] prices, int i, long remaining) {
        if (remaining == 0) return 1;
        if (i == prices.length || remaining < 0) return 0;
        return go(prices, i + 1, remaining - prices[i]) + go(prices, i + 1, remaining);
    }

    static long countSubsets(long[] prices, long budget) {
        return go(prices, 0, budget);
    }

    public static void main(String[] args) throws IOException {
        FastReader in = new FastReader();
        int n = in.nextInt();
        long budget = in.nextLong();
        long[] prices = new long[n];
        for (int i = 0; i < n; i++) prices[i] = in.nextLong();
        System.out.println(countSubsets(prices, budget));
    }
'''),
        "JAVASCRIPT": '''const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);

function countSubsets(prices, budget) {
  function go(i, remaining) {
    if (remaining === 0) return 1;
    if (i === prices.length || remaining < 0) return 0;
    return go(i + 1, remaining - prices[i]) + go(i + 1, remaining);
  }
  return go(0, budget);
}

const n = data[0];
console.log(String(countSubsets(data.slice(2, 2 + n), data[1])));
''',
    },
    wrong_solutions=(
        ("PYTHON", '''import sys
data = sys.stdin.read().split()
n, budget = int(data[0]), int(data[1])
prices = list(map(int, data[2:2 + n]))
def go(i, remaining):
    if remaining < 0:
        return 0
    if i == n:
        return 1
    return go(i + 1, remaining - prices[i]) + go(i + 1, remaining)
print(go(0, budget) - 1)
''', "Counts subsets costing at most the budget instead of exactly."),
    ),
    tests=_subset_tests(),
    oracle=python_oracle(_SUBSET_PY),
    time_limit_seconds=1.0,
    estimated_minutes=15,
)


PROBLEMS = (
    BALANCED_BRACKETS,
    PAIR_SUM_COUNT,
    LONGEST_UNIQUE,
    MERGE_INTERVALS,
    FIRST_OCCURRENCE,
    GRID_PATH,
    COIN_CHANGE,
    SUBSET_COUNT,
)
