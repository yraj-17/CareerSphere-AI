"""
Deterministic IPv4 practical assessments (Network Engineer / Administrator roles).

Every answer is computed with Python's standard `ipaddress` module and graded by
exact comparison after normalisation — no model is involved in correctness.

Task types
----------
subnet_details  host address with prefix → network, broadcast, first/last usable host,
                usable host count, subnet mask
subnet_split    split a network into at least N equal subnets → new prefix, subnet count,
                usable hosts per subnet, the k-th subnet and its broadcast address
ip_validation   classify each string as invalid / private (RFC 1918) / public
same_subnet     are two hosts with a given mask in the same subnet? + the first host's network

Conventions (stated to the candidate)
-------------------------------------
* Usable hosts exclude the network and broadcast addresses, except /31 (RFC 3021: both
  addresses usable, no broadcast) and /32 (one host). Generated tasks use /8–/30.
* An IPv4 address is valid only in strict dotted-decimal form: four decimal octets 0–255,
  no leading zeros (except "0"), no whitespace or other characters.

A task is fully described by its parameters (stored on the question); expected answers
are recomputed from them when grading and are never sent to the client beforehand.
"""

from __future__ import annotations

import hashlib
import ipaddress
import random
import re
from typing import Optional

TASK_TYPES = ("subnet_details", "subnet_split", "ip_validation", "same_subnet")
TYPES_BY_DIFFICULTY = {
    "EASY": ("subnet_details", "ip_validation", "same_subnet"),
    "MEDIUM": ("subnet_details", "subnet_split", "same_subnet", "ip_validation"),
    "HARD": ("subnet_split", "subnet_details", "same_subnet"),
}
PREFIX_RANGE = {"EASY": (24, 30), "MEDIUM": (16, 30), "HARD": (8, 30)}
RFC1918 = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
_DOTTED = re.compile(r"^(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}$")
LABEL = "Auto-graded — calculated deterministically with Python ipaddress"


class CalcAnswerError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------


def strict_ipv4(text: str) -> Optional[ipaddress.IPv4Address]:
    """Parse strict dotted-decimal IPv4, or return None."""
    if not isinstance(text, str) or not _DOTTED.match(text):
        return None
    if any(int(part) > 255 for part in text.split(".")):
        return None
    return ipaddress.IPv4Address(text)


def classify(text: str) -> str:
    address = strict_ipv4(text)
    if address is None:
        return "invalid"
    return "private" if any(address in net for net in RFC1918) else "public"


def subnet_details(cidr: str) -> dict:
    interface = ipaddress.IPv4Interface(cidr)
    net = interface.network
    if net.prefixlen == 32:
        first = last = net.network_address
        usable, broadcast = 1, None
    elif net.prefixlen == 31:
        first, last = net.network_address, net.broadcast_address
        usable, broadcast = 2, None
    else:
        first, last = net.network_address + 1, net.broadcast_address - 1
        usable, broadcast = net.num_addresses - 2, net.broadcast_address
    return {
        "network_address": str(net.network_address),
        "broadcast_address": str(broadcast) if broadcast is not None else "none",
        "first_host": str(first),
        "last_host": str(last),
        "usable_hosts": str(usable),
        "subnet_mask": str(net.netmask),
    }


def usable_hosts(prefix: int) -> int:
    if prefix == 32:
        return 1
    if prefix == 31:
        return 2
    return 2 ** (32 - prefix) - 2


def subnet_split(network: str, at_least: int, index: int) -> dict:
    net = ipaddress.IPv4Network(network)
    bits = max(0, (at_least - 1).bit_length())
    new_prefix = net.prefixlen + bits
    if new_prefix > 30:
        raise ValueError("split leaves no usable hosts")
    subnet = next(s for i, s in enumerate(net.subnets(new_prefix=new_prefix), start=1) if i == index)
    return {
        "new_prefix": str(new_prefix),
        "subnet_count": str(2 ** bits),
        "hosts_per_subnet": str(usable_hosts(new_prefix)),
        "nth_subnet": str(subnet),
        "nth_broadcast": str(subnet.broadcast_address),
    }


def same_subnet(host_a: str, host_b: str, mask: str) -> dict:
    a = ipaddress.IPv4Interface(f"{host_a}/{mask}")
    b = ipaddress.IPv4Interface(f"{host_b}/{mask}")
    return {"same_subnet": "yes" if a.network == b.network else "no", "network_a": str(a.network.network_address)}


# ---------------------------------------------------------------------------
# Task generation (deterministic from a seed)
# ---------------------------------------------------------------------------


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))


def _random_private_host(r: random.Random) -> ipaddress.IPv4Address:
    base = r.choice(RFC1918)
    return base.network_address + r.randrange(1, base.num_addresses - 1)


def _random_public_host(r: random.Random) -> ipaddress.IPv4Address:
    while True:
        address = ipaddress.IPv4Address(r.randrange(0x01000000, 0xDF000000))
        if address.is_global and not any(address in net for net in RFC1918):
            return address


def _invalid_ipv4(r: random.Random) -> str:
    a, b, c, d = (r.randint(0, 255) for _ in range(4))
    return r.choice([
        f"{a}.{b}.{c}.{r.randint(256, 999)}",
        f"{a}.{b}.{c}",
        f"{a}.{b}.{c}.{d}.{r.randint(0, 9)}",
        f"{a}.{b}.0{r.randint(1, 9)}.{d}",
        f"{a}.{b}..{d}",
        f"{a}.{b}.{c}.{d} ",
        f"{a}.-{b}.{c}.{d}",
        f"{a}.{b}.{c}.x{d}",
    ])


def generate_task(seed: str, difficulty: str, avoid_types: tuple[str, ...] = ()) -> dict:
    r = _rng(seed)
    allowed = TYPES_BY_DIFFICULTY.get(difficulty, TYPES_BY_DIFFICULTY["MEDIUM"])
    choices = [t for t in allowed if t not in avoid_types] or list(allowed)
    task_type = r.choice(choices)
    low, high = PREFIX_RANGE.get(difficulty, PREFIX_RANGE["MEDIUM"])

    if task_type == "subnet_details":
        prefix = r.randint(low, high)
        host = _random_private_host(r) if r.random() < 0.8 else _random_public_host(r)
        net = ipaddress.IPv4Interface(f"{host}/{prefix}").network
        if host in (net.network_address, net.broadcast_address):
            host = net.network_address + 1
        params = {"cidr": f"{host}/{prefix}"}
    elif task_type == "subnet_split":
        base_prefix = r.choice([16, 20, 22, 24]) if difficulty == "HARD" else r.choice([22, 24])
        at_least = r.choice([3, 4, 5, 6, 8, 10, 12, 16, 20, 30])
        bits = (at_least - 1).bit_length()
        if base_prefix + bits > 30:
            at_least = 4
            bits = 2
        host = _random_private_host(r)
        network = ipaddress.IPv4Interface(f"{host}/{base_prefix}").network
        params = {"network": str(network), "at_least": at_least, "index": r.randint(2, 2 ** bits)}
    elif task_type == "ip_validation":
        items = [str(_random_private_host(r)), str(_random_public_host(r)), _invalid_ipv4(r), _invalid_ipv4(r)]
        items += [str(_random_private_host(r)) if r.random() < 0.5 else str(_random_public_host(r)), _invalid_ipv4(r)]
        r.shuffle(items)
        params = {"addresses": items}
    else:
        prefix = r.randint(low, high)
        host = _random_private_host(r)
        net = ipaddress.IPv4Interface(f"{host}/{prefix}").network
        if r.random() < 0.5:
            other = net.network_address + r.randrange(1, max(2, net.num_addresses - 1))
        else:
            other = net.broadcast_address + r.randint(1, 300)
        params = {"host_a": str(host), "host_b": str(other), "mask": str(net.netmask)}
    return {"type": task_type, "params": params, "difficulty": difficulty}


# ---------------------------------------------------------------------------
# Presentation (public — no answers) and grading
# ---------------------------------------------------------------------------

_FIELD_LABELS = {
    "network_address": ("Network address", "e.g. 192.168.1.0"),
    "broadcast_address": ("Broadcast address", "e.g. 192.168.1.255"),
    "first_host": ("First usable host", "dotted decimal"),
    "last_host": ("Last usable host", "dotted decimal"),
    "usable_hosts": ("Number of usable hosts", "integer"),
    "subnet_mask": ("Subnet mask", "dotted decimal, e.g. 255.255.255.0"),
    "new_prefix": ("New prefix length", "e.g. /26"),
    "subnet_count": ("Number of subnets created", "integer"),
    "hosts_per_subnet": ("Usable hosts per subnet", "integer"),
    "nth_subnet": ("The requested subnet", "network/prefix, e.g. 10.0.1.64/26"),
    "nth_broadcast": ("Broadcast address of that subnet", "dotted decimal"),
    "same_subnet": ("Same subnet?", "yes or no"),
    "network_a": ("Network address of host A", "dotted decimal"),
}


def expected_answers(task: dict) -> dict[str, str]:
    p = task["params"]
    kind = task["type"]
    if kind == "subnet_details":
        return subnet_details(p["cidr"])
    if kind == "subnet_split":
        return subnet_split(p["network"], p["at_least"], p["index"])
    if kind == "ip_validation":
        return {f"address_{i + 1}": classify(a) for i, a in enumerate(p["addresses"])}
    if kind == "same_subnet":
        return same_subnet(p["host_a"], p["host_b"], p["mask"])
    raise ValueError(f"unknown task type {kind}")


def _prompt(task: dict) -> tuple[str, str]:
    p = task["params"]
    kind = task["type"]
    if kind == "subnet_details":
        return "Subnet details", f"A host is configured as {p['cidr']}. Work out the details of its subnet."
    if kind == "subnet_split":
        return ("Subnetting a network",
                f"Split {p['network']} into equal subnets so that there are at least {p['at_least']} subnets, "
                f"using the smallest prefix that achieves this. Subnets are numbered from 1 in address order. "
                f"Give the details for subnet #{p['index']}.")
    if kind == "ip_validation":
        return ("IPv4 address validation",
                "Classify each string as 'invalid' (not a strict dotted-decimal IPv4 address), 'private' "
                "(inside 10.0.0.0/8, 172.16.0.0/12 or 192.168.0.0/16) or 'public' (any other valid address). "
                "Strict form means four decimal octets 0–255 with no leading zeros, spaces or other characters.")
    return ("Same subnet?",
            f"Host A is {p['host_a']} and host B is {p['host_b']}, both using subnet mask {p['mask']}. "
            "Are they in the same subnet, and what is host A's network address?")


def public_view(task: dict) -> dict:
    title, prompt = _prompt(task)
    keys = list(expected_answers(task).keys())
    if task["type"] == "ip_validation":
        fields = [
            {"key": key, "label": f"“{task['params']['addresses'][i]}”", "hint": "invalid, private or public",
             "options": ["invalid", "private", "public"]}
            for i, key in enumerate(keys)
        ]
    else:
        fields = []
        for key in keys:
            label, hint = _FIELD_LABELS[key]
            field = {"key": key, "label": label, "hint": hint}
            if key == "same_subnet":
                field["options"] = ["yes", "no"]
            fields.append(field)
    return {
        "type": "calculation",
        "label": LABEL,
        "title": title,
        "prompt": prompt,
        "task_type": task["type"],
        "fields": fields,
        "conventions": (
            "Usable hosts exclude the network and broadcast addresses. Write addresses in dotted "
            "decimal; prefixes as /n; counts as plain integers."
        ),
    }


def _normalise(key: str, value: str) -> Optional[str]:
    text = (value or "").strip().lower()
    if not text:
        return None
    if key in ("usable_hosts", "subnet_count", "hosts_per_subnet"):
        digits = text.replace(",", "").replace("_", "").replace(" ", "")
        return str(int(digits)) if digits.isdigit() else None
    if key == "new_prefix":
        digits = text.lstrip("/")
        return str(int(digits)) if digits.isdigit() else None
    if key == "subnet_mask":
        if text.lstrip("/").isdigit():
            prefix = int(text.lstrip("/"))
            return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask) if 0 <= prefix <= 32 else None
        address = strict_ipv4(text)
        return str(address) if address is not None else None
    if key == "nth_subnet":
        try:
            return str(ipaddress.IPv4Network(text.replace(" ", ""), strict=True))
        except ValueError:
            return None
    if key in ("same_subnet",):
        return {"y": "yes", "yes": "yes", "n": "no", "no": "no"}.get(text)
    if key.startswith("address_"):
        return text if text in ("invalid", "private", "public") else None
    if key == "broadcast_address" and text in ("none", "n/a", "-"):
        return "none"
    address = strict_ipv4(text)
    return str(address) if address is not None else None


def grade(task: dict, answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise CalcAnswerError("Answers must be an object of field values.")
    expected = expected_answers(task)
    unknown = set(answers) - set(expected)
    if unknown:
        raise CalcAnswerError("Unknown answer fields: " + ", ".join(sorted(unknown)))
    view = {f["key"]: f["label"] for f in public_view(task)["fields"]}
    fields = []
    for key, value in expected.items():
        given = answers.get(key)
        given_text = str(given) if given is not None else ""
        correct = _normalise(key, given_text) == value
        fields.append({"key": key, "label": view[key], "given": given_text, "expected": value, "correct": correct})
    correct_count = sum(1 for f in fields if f["correct"])
    score = int(round(100 * correct_count / len(fields)))
    return {"score": score, "correct": correct_count, "total": len(fields), "fields": fields}


def answer_summary(task: dict, answers: dict) -> str:
    """Readable text form of structured answers (stored as the answer text)."""
    labels = {f["key"]: f["label"] for f in public_view(task)["fields"]}
    return "\n".join(f"{labels[k]}: {answers.get(k, '') or '—'}" for k in expected_answers(task))
