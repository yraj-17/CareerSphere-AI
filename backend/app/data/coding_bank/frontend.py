"""
JavaScript and frontend problems (Node.js 12.14.0 on Judge0).

These are plain JavaScript problems: Judge0 runs Node.js, which has no DOM or React.
Tasks that need a React component or browser APIs are AI-reviewed practical scenarios
(app/data/practical_scenarios.py), clearly labelled as not executed.

Node.js 12 note: optional chaining (?.), nullish coalescing (??) and String.replaceAll
are not available. Each problem has an independent Python oracle, so the JavaScript
reference solution is checked against a second implementation.
"""

from __future__ import annotations

import json
import random
import re
from urllib.parse import unquote_to_bytes

from app.data.coding_bank import ProblemSpec, Test

JS_ONLY = ("JAVASCRIPT",)
FRONTEND_ROLES = ("frontend-developer", "react-developer", "full-stack-developer")


def _dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# 9. Flatten a settings object — object traversal
# ---------------------------------------------------------------------------


def _flatten_oracle(stdin: str) -> str:
    root = json.loads(stdin)
    lines: list[tuple[str, str]] = []

    def walk(value, path: str) -> None:
        if isinstance(value, dict):
            if not value and path:
                lines.append((path, "{}"))
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            if not value:
                lines.append((path, "[]"))
            for index, child in enumerate(value):
                walk(child, f"{path}.{index}")
        else:
            lines.append((path, _dumps(value)))

    walk(root, "")
    return "\n".join(f"{path}={value}" for path, value in sorted(lines)) + "\n"


def _flatten_tests() -> tuple[Test, ...]:
    r = random.Random(909)

    def rand_value(depth: int):
        kind = r.random()
        if depth > 3 or kind < 0.45:
            return r.choice([r.randint(-1000, 1000), r.choice([True, False]), None, "v" + str(r.randint(0, 99)), ""])
        if kind < 0.75:
            return {f"k{r.randint(0, 30)}_{i}": rand_value(depth + 1) for i in range(r.randint(0, 4))}
        return [rand_value(depth + 1) for _ in range(r.randint(0, 3))]

    big = {f"section{i}": rand_value(0) for i in range(60)}
    return (
        Test(_dumps({"theme": {"dark": True, "accent": "teal"}, "port": 8080}) + "\n", hidden=False,
             explanation="Nested keys are joined with dots and lines are sorted by path."),
        Test(_dumps({"servers": ["api", "web"], "limits": {}, "owner": None}) + "\n", hidden=False,
             explanation="Array items use their index; empty objects print as {}."),
        Test(_dumps({"a": {"b": {"c": {"d": 1}}}}) + "\n"),
        Test(_dumps({"list": [], "nested": [[1, 2], {"x": "y"}]}) + "\n"),
        Test(_dumps({"quote": 'say "hi"', "path": "C:\\temp", "tab": "a\tb"}) + "\n"),
        Test(_dumps({"z": 1, "B": 2, "a": 3, "a_1": 4, "a0": 5}) + "\n"),
        Test(_dumps(big) + "\n", weight=2.0),
    )


FLATTEN_OBJECT = ProblemSpec(
    slug="js-flatten-settings-object",
    title="Flatten a Settings Object",
    category="frontend",
    difficulty="EASY",
    summary="Flatten nested JSON settings into sorted dot-separated paths.",
    roles=(*FRONTEND_ROLES, "mobile-app-developer"),
    competencies=("javascript", "mobile-programming"),
    statement=(
        "A settings page stores user preferences as nested JSON, but the analytics service needs a flat "
        "list of key paths.\n\n"
        "Flatten the object: object keys are joined with '.', and array elements use their index as the "
        "key (servers.0, servers.1). For every leaf value print 'path=value', where value is written "
        "exactly as JSON.stringify writes it (strings in quotes, numbers, true/false, null). Empty "
        "objects and empty arrays are leaves too and print as {} and [].\n\n"
        "Print the lines sorted by path in ascending order using the default string comparison."
    ),
    input_format="One line containing a JSON object (keys use only letters, digits and '_').",
    output_format="One 'path=value' line per leaf, sorted by path.",
    constraints="Input size ≤ 50 KB\nNesting depth ≤ 10\nNumbers are integers\nStrings contain printable ASCII characters (and tabs)",
    languages=JS_ONLY,
    starter_code={
        "JAVASCRIPT": '''const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));

function flatten(obj) {
  // TODO: return an array of [path, leafValue] pairs.
  return [];
}

const lines = flatten(input)
  .map(([path, value]) => path + '=' + JSON.stringify(value))
  .sort();
console.log(lines.join('\\n'));
''',
    },
    reference_solutions={
        "JAVASCRIPT": '''const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));

function flatten(obj) {
  const out = [];
  function walk(value, path) {
    if (Array.isArray(value)) {
      if (value.length === 0) out.push([path, []]);
      value.forEach((child, index) => walk(child, path + '.' + index));
    } else if (value !== null && typeof value === 'object') {
      const keys = Object.keys(value);
      if (keys.length === 0 && path !== '') out.push([path, {}]);
      keys.forEach((key) => walk(value[key], path === '' ? key : path + '.' + key));
    } else {
      out.push([path, value]);
    }
  }
  walk(obj, '');
  return out;
}

const lines = flatten(input)
  .map(([path, value]) => [path, path + '=' + JSON.stringify(value)])
  .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
  .map((pair) => pair[1]);
console.log(lines.join('\\n'));
''',
    },
    wrong_solutions=(
        ("JAVASCRIPT", '''const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = [];
function walk(value, path) {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    Object.keys(value).forEach((key) => walk(value[key], path === '' ? key : path + '.' + key));
  } else {
    out.push(path + '=' + JSON.stringify(value));
  }
}
walk(input, '');
console.log(out.sort().join('\\n'));
''', "Treats arrays as leaves and drops empty objects."),
    ),
    tests=_flatten_tests(),
    oracle=_flatten_oracle,
    time_limit_seconds=1.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 10. Customer revenue summary — array/object transformation
# ---------------------------------------------------------------------------


def _summary_oracle(stdin: str) -> str:
    orders = json.loads(stdin)
    totals: dict[str, list[int]] = {}
    for order in orders:
        if order["status"] != "paid":
            continue
        amount = sum(item["qty"] * item["price"] for item in order["items"])
        entry = totals.setdefault(order["customer"], [0, 0])
        entry[0] += amount
        entry[1] += 1
    rows = sorted(totals.items(), key=lambda kv: (-kv[1][0], kv[0]))
    lines = [f"{name} {total} {count}" for name, (total, count) in rows]
    lines.append(f"TOTAL {sum(v[0] for v in totals.values())}")
    return "\n".join(lines) + "\n"


def _summary_tests() -> tuple[Test, ...]:
    r = random.Random(1010)
    names = ["asha", "ben", "chen", "dina", "eli", "farah", "gopal", "hana", "ivan", "jo"]

    def orders(n: int) -> list[dict]:
        out = []
        for i in range(n):
            out.append({
                "id": f"o{i}",
                "customer": r.choice(names),
                "status": r.choice(["paid", "paid", "paid", "refunded", "pending"]),
                "items": [{"sku": f"s{r.randint(1, 50)}", "qty": r.randint(1, 5), "price": r.randint(100, 9999)}
                          for _ in range(r.randint(1, 4))],
            })
        return out

    sample = [
        {"id": "o1", "customer": "maya", "status": "paid", "items": [{"sku": "pen", "qty": 2, "price": 150}]},
        {"id": "o2", "customer": "liam", "status": "paid", "items": [{"sku": "book", "qty": 1, "price": 900}]},
        {"id": "o3", "customer": "maya", "status": "refunded", "items": [{"sku": "bag", "qty": 1, "price": 5000}]},
        {"id": "o4", "customer": "maya", "status": "paid", "items": [{"sku": "ink", "qty": 4, "price": 50}]},
    ]
    tie = [
        {"id": "a", "customer": "zoe", "status": "paid", "items": [{"sku": "x", "qty": 1, "price": 500}]},
        {"id": "b", "customer": "amir", "status": "paid", "items": [{"sku": "y", "qty": 5, "price": 100}]},
        {"id": "c", "customer": "kai", "status": "pending", "items": [{"sku": "z", "qty": 9, "price": 999}]},
    ]
    return (
        Test(_dumps(sample) + "\n", hidden=False,
             explanation="liam: 900 from 1 order; maya: 300 + 200 = 500 from 2 paid orders (the refund is ignored)."),
        Test(_dumps(tie) + "\n", hidden=False, explanation="Equal totals are ordered by name; pending orders are ignored."),
        Test(_dumps([{"id": "x", "customer": "solo", "status": "refunded", "items": [{"sku": "a", "qty": 1, "price": 10}]}]) + "\n"),
        Test(_dumps(orders(40)) + "\n"),
        Test(_dumps(orders(3000)) + "\n", weight=2.0),
    )


ORDER_SUMMARY = ProblemSpec(
    slug="js-customer-revenue-summary",
    title="Customer Revenue Summary",
    category="frontend",
    difficulty="EASY",
    summary="Group paid orders by customer and rank customers by revenue.",
    roles=(*FRONTEND_ROLES, "mobile-app-developer"),
    competencies=("javascript", "mobile-programming"),
    statement=(
        "A dashboard widget shows which customers bring in the most revenue.\n\n"
        "You receive a JSON array of orders. Each order has a customer name, a status (paid, refunded "
        "or pending) and a list of items with qty and price (in cents). Only paid orders count.\n\n"
        "For every customer with at least one paid order, print 'name total paidOrders', where total "
        "is the sum of qty × price over their paid orders. Sort by total descending, then by name "
        "ascending. Finish with a line 'TOTAL x' giving the revenue of all paid orders."
    ),
    input_format="One line containing a JSON array of orders.",
    output_format="One line per customer, then the TOTAL line.",
    constraints="1 ≤ orders ≤ 5000\n1 ≤ items per order ≤ 10\n1 ≤ qty ≤ 100, 1 ≤ price ≤ 100 000\nNames are lowercase letters",
    languages=JS_ONLY,
    starter_code={
        "JAVASCRIPT": '''const orders = JSON.parse(require('fs').readFileSync(0, 'utf8'));

function summarise(list) {
  // TODO: return [{ name, total, count }] for customers with paid orders,
  // sorted by total descending, then name ascending.
  return [];
}

const rows = summarise(orders);
const lines = rows.map((r) => r.name + ' ' + r.total + ' ' + r.count);
lines.push('TOTAL ' + rows.reduce((sum, r) => sum + r.total, 0));
console.log(lines.join('\\n'));
''',
    },
    reference_solutions={
        "JAVASCRIPT": '''const orders = JSON.parse(require('fs').readFileSync(0, 'utf8'));

function summarise(list) {
  const byCustomer = new Map();
  for (const order of list) {
    if (order.status !== 'paid') continue;
    const amount = order.items.reduce((sum, item) => sum + item.qty * item.price, 0);
    const entry = byCustomer.get(order.customer) || { name: order.customer, total: 0, count: 0 };
    entry.total += amount;
    entry.count += 1;
    byCustomer.set(order.customer, entry);
  }
  return Array.from(byCustomer.values()).sort((a, b) =>
    b.total - a.total || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
}

const rows = summarise(orders);
const lines = rows.map((r) => r.name + ' ' + r.total + ' ' + r.count);
lines.push('TOTAL ' + rows.reduce((sum, r) => sum + r.total, 0));
console.log(lines.join('\\n'));
''',
    },
    wrong_solutions=(
        ("JAVASCRIPT", '''const orders = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const m = new Map();
for (const o of orders) {
  if (o.status === 'pending') continue;
  const amount = o.items.reduce((s, i) => s + i.qty * i.price, 0);
  const e = m.get(o.customer) || { name: o.customer, total: 0, count: 0 };
  e.total += amount; e.count += 1; m.set(o.customer, e);
}
const rows = Array.from(m.values()).sort((a, b) => b.total - a.total);
const lines = rows.map((r) => r.name + ' ' + r.total + ' ' + r.count);
lines.push('TOTAL ' + rows.reduce((s, r) => s + r.total, 0));
console.log(lines.join('\\n'));
''', "Counts refunded orders and ignores the name tie-break."),
    ),
    tests=_summary_tests(),
    oracle=_summary_oracle,
    time_limit_seconds=1.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 11. Concurrency-limited task runner — promises and the event loop
# ---------------------------------------------------------------------------

_POOL_HARNESS = '''// ----- Harness (do not change): simulated asynchronous tasks -----
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const log = [];
const state = { running: 0, max: 0 };

function makeTask(spec) {
  return function () {
    state.running++;
    state.max = Math.max(state.max, state.running);
    log.push('start ' + spec.id);
    return new Promise((resolve, reject) => {
      let left = spec.ticks;
      const step = () => {
        left--;
        if (left > 0) {
          setImmediate(step);
          return;
        }
        state.running--;
        log.push('end ' + spec.id);
        if (spec.fail) reject(new Error('task ' + spec.id + ' failed'));
        else resolve(spec.id + '-done');
      };
      setImmediate(step);
    });
  };
}

function report(results) {
  console.log(log.join('\\n'));
  input.tasks.forEach((spec, i) => {
    const r = results[i];
    console.log(spec.id + (r.status === 'fulfilled' ? ' ok ' + r.value : ' error ' + r.reason.message));
  });
  console.log('max_running ' + state.max);
}
// ----- End of harness -----
'''


def _pool_oracle(stdin: str) -> str:
    data = json.loads(stdin)
    limit, tasks = data["limit"], data["tasks"]
    log: list[str] = []
    results: list[str] = [""] * len(tasks)
    remaining: dict[int, int] = {}
    pending: list[int] = []
    running = max_running = 0
    next_index = 0

    def start(i: int) -> None:
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        log.append(f"start {tasks[i]['id']}")
        remaining[i] = tasks[i]["ticks"]
        pending.append(i)

    while next_index < min(limit, len(tasks)):
        start(next_index)
        next_index += 1
    while pending:
        current = pending[:]
        pending.clear()
        for i in current:  # one event-loop iteration: setImmediate callbacks in FIFO order
            remaining[i] -= 1
            if remaining[i] > 0:
                pending.append(i)
                continue
            running -= 1
            spec = tasks[i]
            log.append(f"end {spec['id']}")
            results[i] = f"{spec['id']} error task {spec['id']} failed" if spec.get("fail") else f"{spec['id']} ok {spec['id']}-done"
            # Microtasks run before the next callback: the freed slot starts the next task.
            if next_index < len(tasks):
                start(next_index)
                next_index += 1
    return "\n".join([*log, *results, f"max_running {max_running}"]) + "\n"


def _pool_tests() -> tuple[Test, ...]:
    r = random.Random(1111)

    def case(limit: int, specs: list[tuple[str, int, bool]]) -> str:
        return _dumps({"limit": limit, "tasks": [{"id": i, "ticks": t, "fail": f} for i, t, f in specs]}) + "\n"

    many = [(f"t{i}", r.randint(1, 6), r.random() < 0.2) for i in range(40)]
    return (
        Test(case(2, [("a", 3, False), ("b", 1, False), ("c", 2, False)]), hidden=False,
             explanation="a and b start together; b finishes first, so c starts while a is still running."),
        Test(case(1, [("x", 2, False), ("y", 1, True), ("z", 1, False)]), hidden=False,
             explanation="With limit 1 tasks run one at a time; a failure does not stop the pool."),
        Test(case(5, [("only", 4, False)])),
        Test(case(3, [("p", 2, True), ("q", 2, True), ("r", 2, False), ("s", 1, False)])),
        Test(case(10, [(f"w{i}", 1 + i % 3, False) for i in range(6)])),
        Test(case(3, many)),
        Test(case(1, [(f"s{i}", 1, i % 7 == 0) for i in range(30)])),
    )


PROMISE_POOL = ProblemSpec(
    slug="js-concurrency-limited-runner",
    title="Concurrency-Limited Task Runner",
    category="frontend",
    difficulty="MEDIUM",
    summary="Run asynchronous tasks with at most `limit` in flight (promises).",
    roles=FRONTEND_ROLES,
    competencies=("javascript",),
    statement=(
        "A frontend uploads files through an API that allows only a few requests at a time. Implement "
        "runPool(tasks, limit): tasks is an array of functions that each return a Promise.\n\n"
        "* Start tasks in array order, never with more than `limit` running at once.\n"
        "* As soon as a task settles (resolves or rejects), start the next unstarted task.\n"
        "* A rejected task must not stop the pool.\n"
        "* Resolve with an array, in the original task order, of {status: 'fulfilled', value} or "
        "{status: 'rejected', reason} — the same shape as Promise.allSettled.\n\n"
        "The harness in the starter code builds the tasks, records when each starts and ends, and "
        "prints the log, the results and the maximum number of tasks that ran at once. Do not "
        "change the harness; implement runPool."
    ),
    input_format="One line of JSON: {\"limit\": k, \"tasks\": [{\"id\", \"ticks\", \"fail\"}, ...]} (read by the harness).",
    output_format="Printed by the harness: the start/end log, one result line per task, then max_running.",
    constraints="1 ≤ limit ≤ 10\n1 ≤ tasks ≤ 50\nDo not use setTimeout or setImmediate in runPool; start the next task when a promise settles.",
    languages=JS_ONLY,
    starter_code={
        "JAVASCRIPT": _POOL_HARNESS + '''
function runPool(tasks, limit) {
  // TODO: run the tasks with at most `limit` in flight and resolve with allSettled-style results.
  return Promise.resolve(tasks.map(() => ({ status: 'rejected', reason: new Error('not implemented') })));
}

runPool(input.tasks.map(makeTask), input.limit).then(report);
''',
    },
    reference_solutions={
        "JAVASCRIPT": _POOL_HARNESS + '''
function runPool(tasks, limit) {
  const results = new Array(tasks.length);
  let next = 0;
  async function worker() {
    while (next < tasks.length) {
      const index = next++;
      try {
        results[index] = { status: 'fulfilled', value: await tasks[index]() };
      } catch (error) {
        results[index] = { status: 'rejected', reason: error };
      }
    }
  }
  const workers = [];
  for (let i = 0; i < Math.min(limit, tasks.length); i++) workers.push(worker());
  return Promise.all(workers).then(() => results);
}

runPool(input.tasks.map(makeTask), input.limit).then(report);
''',
    },
    wrong_solutions=(
        ("JAVASCRIPT", _POOL_HARNESS + '''
async function runPool(tasks, limit) {
  const results = [];
  for (let i = 0; i < tasks.length; i += limit) {
    const batch = tasks.slice(i, i + limit).map((task) => task().then(
      (value) => ({ status: 'fulfilled', value }),
      (reason) => ({ status: 'rejected', reason })));
    results.push(...(await Promise.all(batch)));
  }
  return results;
}

runPool(input.tasks.map(makeTask), input.limit).then(report);
''', "Runs fixed batches and waits for the slowest task before starting more."),
        ("JAVASCRIPT", _POOL_HARNESS + '''
function runPool(tasks, limit) {
  return Promise.allSettled ? Promise.allSettled(tasks.map((t) => t())) :
    Promise.all(tasks.map((t) => t().then((value) => ({ status: 'fulfilled', value }), (reason) => ({ status: 'rejected', reason }))));
}

runPool(input.tasks.map(makeTask), input.limit).then(report);
''', "Ignores the concurrency limit."),
    ),
    tests=_pool_tests(),
    oracle=_pool_oracle,
    time_limit_seconds=1.0,
    estimated_minutes=25,
)


# ---------------------------------------------------------------------------
# 12. Parse query strings — practical string handling
# ---------------------------------------------------------------------------

_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _decode(text: str) -> str:
    text = text.replace("+", " ")
    if _BAD_PERCENT.search(text):
        return text
    try:
        return unquote_to_bytes(text).decode("utf-8")
    except UnicodeDecodeError:
        return text


def _query_oracle(stdin: str) -> str:
    out = []
    for line in stdin.split("\n"):
        line = line.rstrip("\r")
        if line == "":
            continue
        query = line[1:] if line.startswith("?") else line
        values: dict[str, list[str]] = {}
        for piece in query.split("&"):
            if piece == "":
                continue
            key, _, value = piece.partition("=")
            values.setdefault(_decode(key), []).append(_decode(value))
        pairs = [[k, v[0] if len(v) == 1 else v] for k, v in sorted(values.items())]
        out.append(_dumps(pairs))
    return "\n".join(out) + "\n"


def _query_tests() -> tuple[Test, ...]:
    r = random.Random(1212)
    alphabet = "abcxyz019-_.~"

    def random_query() -> str:
        parts = []
        for _ in range(r.randint(1, 8)):
            key = "".join(r.choice(alphabet) for _ in range(r.randint(1, 4)))
            value = "".join(r.choice(alphabet + "+%20") for _ in range(r.randint(0, 6)))
            parts.append(f"{key}={value}" if r.random() < 0.85 else key)
        return "&".join(parts)

    return (
        Test("?q=react+hooks&page=2\ntag=js&tag=css&tag=html\n", hidden=False,
             explanation="'+' decodes to a space; a repeated key becomes an array in order of appearance."),
        Test("name=J%C3%BCrgen&flag&empty=\n", hidden=False,
             explanation="Percent-encoding is decoded as UTF-8; a key without '=' has the value \"\"."),
        Test("a=1&&b=2&\n"),
        Test("bad=%zz&ok=%41\n"),
        Test("trunc=%E0%A4%A&next=1\n"),
        Test("x=%26%3D%2B&x=2&x=3\n"),
        Test("?=novalue&k=v\n"),
        Test("\n".join(random_query() for _ in range(200)) + "\n"),
    )


QUERY_STRING = ProblemSpec(
    slug="js-parse-query-strings",
    title="Parse URL Query Strings",
    category="frontend",
    difficulty="MEDIUM",
    summary="Decode URL query strings into sorted key/value pairs.",
    roles=FRONTEND_ROLES,
    competencies=("javascript",),
    statement=(
        "A single-page app restores filters from the URL. Write a parser for query strings.\n\n"
        "Rules for each line:\n"
        "* An optional leading '?' is ignored. Pairs are separated by '&'; empty pieces are ignored.\n"
        "* Each piece is split at the first '='. A piece without '=' has the value \"\".\n"
        "* In keys and values, '+' means a space and %XX sequences are percent-decoded as UTF-8. If a "
        "key or value contains a malformed % sequence (not followed by two hex digits) or decodes to "
        "invalid UTF-8, keep that text as-is (with '+' still turned into spaces).\n"
        "* A key that appears more than once collects its values into an array, in order.\n\n"
        "Print, for each line, JSON.stringify of an array of [key, value] pairs sorted by key, where "
        "value is a string for keys seen once and an array of strings otherwise."
    ),
    input_format="One query string per line (blank lines are ignored).",
    output_format="One JSON array per non-blank input line.",
    constraints="Up to 200 lines, each at most 500 characters",
    languages=JS_ONLY,
    starter_code={
        "JAVASCRIPT": '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');

function parseQuery(query) {
  // TODO: return [[key, value], ...] sorted by key (value is a string or an array of strings).
  return [];
}

const out = [];
for (const line of lines) {
  const text = line.replace(/\\r$/, '');
  if (text !== '') out.push(JSON.stringify(parseQuery(text)));
}
console.log(out.join('\\n'));
''',
    },
    reference_solutions={
        "JAVASCRIPT": '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');

function decode(text) {
  const spaced = text.split('+').join(' ');
  try {
    return decodeURIComponent(spaced);
  } catch (error) {
    return spaced;
  }
}

function parseQuery(query) {
  const source = query.charAt(0) === '?' ? query.slice(1) : query;
  const values = new Map();
  for (const piece of source.split('&')) {
    if (piece === '') continue;
    const at = piece.indexOf('=');
    const key = decode(at === -1 ? piece : piece.slice(0, at));
    const value = decode(at === -1 ? '' : piece.slice(at + 1));
    if (!values.has(key)) values.set(key, []);
    values.get(key).push(value);
  }
  return Array.from(values.keys())
    .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))
    .map((key) => {
      const list = values.get(key);
      return [key, list.length === 1 ? list[0] : list];
    });
}

const out = [];
for (const line of lines) {
  const text = line.replace(/\\r$/, '');
  if (text !== '') out.push(JSON.stringify(parseQuery(text)));
}
console.log(out.join('\\n'));
''',
    },
    wrong_solutions=(
        ("JAVASCRIPT", '''const lines = require('fs').readFileSync(0, 'utf8').split('\\n');
const out = [];
for (const raw of lines) {
  const line = raw.replace(/\\r$/, '');
  if (line === '') continue;
  const obj = {};
  for (const piece of line.replace(/^\\?/, '').split('&')) {
    if (!piece) continue;
    const [k, v] = piece.split('=');
    obj[decodeURIComponent(k)] = v === undefined ? '' : decodeURIComponent(v);
  }
  out.push(JSON.stringify(Object.keys(obj).sort().map((k) => [k, obj[k]])));
}
console.log(out.join('\\n'));
''', "Overwrites repeated keys, ignores '+' and crashes on malformed escapes."),
    ),
    tests=_query_tests(),
    oracle=_query_oracle,
    time_limit_seconds=1.0,
    estimated_minutes=20,
)


PROBLEMS = (FLATTEN_OBJECT, ORDER_SUMMARY, PROMISE_POOL, QUERY_STRING)
