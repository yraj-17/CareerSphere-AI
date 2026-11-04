"""
Verify a Judge0 deployment with real executions (no mocks).

Usage (from the backend virtualenv, which has `requests` and `python-dotenv`):
    python infra/judge0/verify_judge0.py --env-file .env
    python infra/judge0/verify_judge0.py --url http://127.0.0.1:2358   # token from $JUDGE0_AUTH_TOKEN
The token is read from the environment or env file, never from the command line,
so it does not end up in shell history or process listings. It is never printed.

Also checks that requests without a token or with a wrong token are refused, and that
requests trying to enable networking or exceed the CPU/memory ceilings are rejected.

Checks, for C++, Java, Python and JavaScript:
  accepted, wrong answer, compilation error (compiled languages), runtime error,
  time limit exceeded, memory limit exceeded — plus that the sandbox has no network.
Exits non-zero if any verdict differs from what is expected.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time

import requests

LANGUAGE_PATTERNS = {
    "CPP": ("C++ (GCC",),
    "JAVA": ("Java (",),
    "PYTHON": ("Python (3",),
    "JAVASCRIPT": ("JavaScript (Node",),
}

SUM = {  # read two integers, print their sum
    "CPP": "#include <bits/stdc++.h>\nint main(){long long a,b;std::cin>>a>>b;std::cout<<a+b<<\"\\n\";}",
    "JAVA": "import java.util.*;\npublic class Main{public static void main(String[] x){Scanner s=new Scanner(System.in);long a=s.nextLong(),b=s.nextLong();System.out.println(a+b);}}",
    "PYTHON": "a, b = map(int, input().split())\nprint(a + b)",
    "JAVASCRIPT": "const [a,b]=require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);console.log(a+b);",
}
WRONG = {
    "CPP": "#include <bits/stdc++.h>\nint main(){long long a,b;std::cin>>a>>b;std::cout<<a-b<<\"\\n\";}",
    "JAVA": "import java.util.*;\npublic class Main{public static void main(String[] x){Scanner s=new Scanner(System.in);long a=s.nextLong(),b=s.nextLong();System.out.println(a-b);}}",
    "PYTHON": "a, b = map(int, input().split())\nprint(a - b)",
    "JAVASCRIPT": "const [a,b]=require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);console.log(a-b);",
}
COMPILE_ERROR = {
    "CPP": "int main(){ return x; }",
    "JAVA": "public class Main{ public static void main(String[] a){ int x = ; } }",
}
RUNTIME_ERROR = {
    "CPP": "#include <cstdlib>\nint main(){ std::abort(); }",
    "JAVA": "public class Main{public static void main(String[] a){int[] x=new int[1];System.out.println(x[5]);}}",
    "PYTHON": "raise ValueError('boom')",
    "JAVASCRIPT": "throw new Error('boom');",
}
TIME_LIMIT = {
    "CPP": "int main(){ volatile long x=0; while(true){x++;} }",
    "JAVA": "public class Main{public static void main(String[] a){long x=0;while(true){x++;}}}",
    "PYTHON": "while True:\n    pass",
    "JAVASCRIPT": "while(true){}",
}
MEMORY_LIMIT = {
    "CPP": "#include <vector>\n#include <cstdio>\nint main(){ std::vector<std::vector<char>> v; while(true){ v.emplace_back(16<<20, 1); } }",
    "JAVA": "import java.util.*;\npublic class Main{public static void main(String[] a){List<long[]> l=new ArrayList<>();while(true){l.add(new long[4_000_000]);}}}",
    "PYTHON": "x = []\nwhile True:\n    x.append(bytearray(16 * 1024 * 1024))",
    "JAVASCRIPT": "const a=[];while(true){a.push(Buffer.alloc(16*1024*1024,1));}",
}
NETWORK = {
    "PYTHON": "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 80), timeout=3)\n    print('NETWORK-OPEN')\nexcept Exception as e:\n    print('NETWORK-BLOCKED')",
}


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


class Judge0:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.headers = {"X-Auth-Token": token, "Content-Type": "application/json"}

    def languages(self) -> list[dict]:
        res = requests.get(f"{self.url}/languages", headers=self.headers, timeout=15)
        res.raise_for_status()
        return res.json()

    def run(self, language_id: int, source: str, stdin: str = "", expected: str | None = None, **limits) -> dict:
        body = {"language_id": language_id, "source_code": b64(source), "stdin": b64(stdin), **limits}
        if expected is not None:
            body["expected_output"] = b64(expected)
        res = requests.post(f"{self.url}/submissions?base64_encoded=true&wait=false", json=body, headers=self.headers, timeout=15)
        res.raise_for_status()
        token = res.json()["token"]
        for _ in range(120):
            time.sleep(0.5)
            poll = requests.get(
                f"{self.url}/submissions/{token}?base64_encoded=true&fields=status,stdout,stderr,compile_output,time,memory",
                headers=self.headers,
                timeout=15,
            )
            poll.raise_for_status()
            data = poll.json()
            if data["status"]["id"] > 2:  # 1 In Queue, 2 Processing
                for key in ("stdout", "stderr", "compile_output"):
                    if data.get(key):
                        data[key] = base64.b64decode(data[key]).decode(errors="replace")
                return data
        raise TimeoutError("submission did not finish")


def auth_checks(url: str, token: str) -> int:
    """Unauthenticated and wrong-token requests must be refused; the real token must work."""
    failures = 0
    cases = [
        ("no token", {}, 401),
        ("invalid token", {"X-Auth-Token": "0" * 64}, 401),
        ("valid token", {"X-Auth-Token": token}, 200),
    ]
    print("auth checks (GET /languages):")
    for name, headers, expected in cases:
        code = requests.get(f"{url}/languages", headers=headers, timeout=15).status_code
        ok = code == expected
        failures += not ok
        print(f"  {name:<14} -> {code}  {'OK' if ok else f'UNEXPECTED (wanted {expected})'}")
    return failures


def policy_checks(judge: "Judge0", python_id: int) -> int:
    """Requests that try to enable networking or exceed server ceilings must be refused."""
    failures = 0
    base = {"language_id": python_id, "source_code": b64("print(1)")}
    cases = [
        ("enable_network=true", {"enable_network": True}),
        ("cpu_time_limit=20 (max 10)", {"cpu_time_limit": 20}),
        ("memory_limit=600000 (max 512000)", {"memory_limit": 600000}),
    ]
    print("\npolicy checks (must be rejected by the server):")
    for name, extra in cases:
        res = requests.post(
            f"{judge.url}/submissions?base64_encoded=true&wait=false",
            json={**base, **extra},
            headers=judge.headers,
            timeout=15,
        )
        ok = res.status_code == 422
        failures += not ok
        print(f"  {name:<34} -> {res.status_code}  {'OK (rejected)' if ok else 'UNEXPECTED (accepted)'}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None, help="defaults to $JUDGE0_API_URL")
    parser.add_argument("--env-file", default=None, help="load JUDGE0_API_URL / JUDGE0_AUTH_TOKEN from this file")
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv

        load_dotenv(args.env_file)
    url = (args.url or os.environ.get("JUDGE0_API_URL", "")).rstrip("/")
    token = os.environ.get("JUDGE0_AUTH_TOKEN", "")
    if not url or not token:
        print("JUDGE0_API_URL and JUDGE0_AUTH_TOKEN are required (environment or --env-file)")
        return 2
    failures = auth_checks(url, token)
    judge = Judge0(url, token)
    print()

    langs = judge.languages()
    ids: dict[str, dict] = {}
    for key, patterns in LANGUAGE_PATTERNS.items():
        matches = [l for l in langs if any(l["name"].startswith(p) for p in patterns)]
        if not matches:
            print(f"MISSING language for {key}")
            return 1
        ids[key] = max(matches, key=lambda l: l["id"])  # newest runtime of that family
        print(f"{key:<11} -> id {ids[key]['id']:<3} {ids[key]['name']}")

    cases = []
    for lang in LANGUAGE_PATTERNS:
        cases += [
            (lang, "accepted", SUM[lang], "Accepted"),
            (lang, "wrong answer", WRONG[lang], "Wrong Answer"),
            (lang, "runtime error", RUNTIME_ERROR[lang], "Runtime Error"),
            (lang, "time limit", TIME_LIMIT[lang], "Time Limit Exceeded"),
            (lang, "memory limit", MEMORY_LIMIT[lang], "Memory Limit Exceeded|Runtime Error"),
        ]
        if lang in COMPILE_ERROR:
            cases.append((lang, "compilation error", COMPILE_ERROR[lang], "Compilation Error"))

    failures += policy_checks(judge, ids["PYTHON"]["id"])
    print(f"\n{'language':<11} {'case':<18} {'verdict':<28} {'time':>6} {'memory':>8}  result")
    for lang, name, source, expected in cases:
        limits = {"cpu_time_limit": 2, "wall_time_limit": 5, "memory_limit": 128000}
        if lang == "CPP":
            limits["compiler_options"] = "-std=c++17 -O2"
        data = judge.run(ids[lang]["id"], source, stdin="2 3\n", expected="5\n", **limits)
        verdict = data["status"]["description"]
        ok = any(verdict.startswith(v) for v in expected.split("|"))
        failures += not ok
        print(f"{lang:<11} {name:<18} {verdict:<28} {str(data.get('time')):>6} {str(data.get('memory')):>8}  {'OK' if ok else 'UNEXPECTED (wanted ' + expected + ')'}")

    net = judge.run(ids["PYTHON"]["id"], NETWORK["PYTHON"], cpu_time_limit=5, wall_time_limit=8)
    blocked = (net.get("stdout") or "").strip() == "NETWORK-BLOCKED"
    failures += not blocked
    print(f"\nsandbox network: {'blocked (OK)' if blocked else 'OPEN — sandbox network must be disabled'}")
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
