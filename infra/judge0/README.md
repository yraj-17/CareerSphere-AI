# Judge0 execution service (isolated)

Candidate code is compiled and executed by **Judge0 CE**, on a dedicated Linux VM.
It never runs inside FastAPI, the application host, Docker Desktop/WSL2, or the
Qwen/GPU server. The backend is the only client; the frontend never sees Judge0.

Judge0 CE 1.13.x requires **cgroup v1**. This repo's dev machine uses Docker Desktop on
WSL2 with cgroup v2, which must not be changed (it affects every project), so Judge0
runs in its own VM where cgroup v1 is set on that VM's kernel only.

## Option A — local VirtualBox VM (development)

Needs VirtualBox + Vagrant and about 3 GB of free RAM for the VM.

```bash
cd infra/judge0
vagrant up                                   # provisions, reboots into cgroup v1, installs Judge0
vagrant ssh -c "sudo cat /opt/judge0/credentials.env"
```

The API is published only on the host-only address `192.168.56.20:2358`.
Override with `JUDGE0_VM_IP`, `JUDGE0_VM_MEMORY_MB`, `JUDGE0_VM_CPUS`.

## Option B — cloud CPU VM (staging/production)

Ubuntu 22.04, 2+ vCPU, 4 GB RAM, **CPU only**, in the same private network as the backend.

```bash
sudo bash provision-cgroup.sh && sudo reboot
sudo JUDGE0_BIND_IP=<private-ip> bash provision-judge0.sh
```

Bind to the private IP, and allow TCP 2358 from the backend's security group only.
Never expose Judge0 publicly.

## Wire up the backend

Copy two values from `/opt/judge0/credentials.env` into the backend `.env`:

```
JUDGE0_API_URL=http://127.0.0.1:2358   # dev: through the SSH/SSM tunnel (never the public IP)
JUDGE0_AUTH_TOKEN=<token>
```

## Verify real execution

```bash
backend/.venv/Scripts/python infra/judge0/verify_judge0.py --env-file .env
```

This runs real programs in C++, Java, Python and JavaScript and checks every verdict
(Accepted, Wrong Answer, Compilation Error, Runtime Error, Time Limit Exceeded,
Memory Limit Exceeded) and that the sandbox has no network access.

## Sandbox policy (set by provision-judge0.sh)

- Network disabled for submissions; cannot be enabled per request.
- CPU 2 s default / 10 s max; wall 5 s / 20 s; memory 256 MB / 512 MB; 64 processes; 1 MB output files.
- Token authentication on every request; separate admin token.
- Asynchronous submissions only (no blocking waits, no callbacks); batches of up to 20.

## Runtimes and limits verified on the CareerSphere instance

| Use | Judge0 language | Notes |
|---|---|---|
| C++ | C++ (GCC 9.2.0), id 54 | compiled with `-std=c++17 -O2` |
| Java | Java (OpenJDK 13.0.1), id 62 | public class must be `Main`; Java 17 is not installed |
| Python | Python (3.8.1), id 71 | |
| JavaScript | JavaScript (Node.js 12.14.0), id 63 | no `?.`, `??`, `replaceAll` |
| Bash | Bash (5.0.0), id 46 | coreutils, GNU sed 4.7, **mawk** (no gawk), no `bc` |
| SQL | SQL (SQLite 3.27.2), id 82 | runs `cat script.sql \| sqlite3 db.sqlite`: stdin is ignored, so the backend builds schema + seed data + candidate SQL into one script (fresh database per execution); window functions available |

- **Program stdout is truncated at exactly 64 KiB (65 536 bytes).** Problem-bank expected
  outputs are kept below 60 000 bytes (enforced when seeding), and a candidate whose
  output reaches the cap gets an explicit "output truncated" reason.
- Inputs of ~2 MB per test are accepted.

## Problem bank

From `backend/`: `python -m scripts.seed_coding_bank --verify` seeds the curated bank
(idempotent) and verifies every problem on this instance: each reference solution must be
Accepted, each known-wrong solution rejected, and each starter template must run. Only
verified problems are assigned to interviews.
