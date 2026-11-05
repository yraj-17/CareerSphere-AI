# Development tunnels (Qwen/Ollama and Judge0)

In local development the backend reaches the hosted model and Judge0 only through SSH
local forwards:

| Local | Remote | Used by |
|---|---|---|
| `127.0.0.1:11434` | Qwen host `127.0.0.1:11434` (Ollama) | AI Career Assistant, Skill Analysis, AI Interviewer, ... (`OLLAMA_BASE_URL`) |
| `127.0.0.1:2358` | Judge0 private address `:2358` | coding assessments (`JUDGE0_API_URL`) |

When a forward drops, **every** AI feature that uses it fails with a connection error
(the AI Interviewer reports "can't reach the AI model"). Plain `ssh -L` forwards die on
network changes, sleep, or a WSL restart, and do not come back on their own.

## Self-healing forwards

`keep-tunnels.sh` probes both forwards every 15 s and re-creates any that stop answering.
It binds to `127.0.0.1` only and changes nothing on the EC2 hosts.

```bash
# inside WSL
export QWEN_SSH_KEY=~/ec2/CareerSphere.pem        QWEN_SSH_HOST=ubuntu@<qwen-host>
export JUDGE0_SSH_KEY=~/ec2/careersphere-judge0.pem JUDGE0_SSH_HOST=ubuntu@<judge0-host>
export JUDGE0_PRIVATE_ADDR=<judge0-private-ip>
nohup bash infra/dev-tunnels/keep-tunnels.sh >/dev/null 2>&1 &
tail -f ~/.cache/careersphere-tunnels.log
```

Stop it with `pkill -f keep-tunnels.sh`.

## More durable option (recommended for anything beyond one dev machine)

The watchdog lives inside WSL, so a full WSL shutdown stops it too. For a tunnel that
survives that and needs no inbound SSH at all, use **AWS Systems Manager port forwarding**
(requires the SSM agent and an instance profile with `AmazonSSMManagedInstanceCore`):

```bash
aws ssm start-session --target <qwen-instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host=127.0.0.1,portNumber=11434,localPortNumber=11434
```

In a deployed environment the backend should reach both services over the private VPC
network instead of tunnels.
