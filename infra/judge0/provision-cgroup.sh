#!/usr/bin/env bash
# Switch this machine (the Judge0 VM only) to cgroup v1. Judge0 CE 1.13.x's isolate sandbox
# does not support cgroup v2. Safe to re-run.
set -euo pipefail
if grep -q "systemd.unified_cgroup_hierarchy=0" /etc/default/grub; then
  echo "cgroup v1 already configured"
  exit 0
fi
sed -i 's/^GRUB_CMDLINE_LINUX="\(.*\)"/GRUB_CMDLINE_LINUX="\1 systemd.unified_cgroup_hierarchy=0"/' /etc/default/grub
update-grub
echo "cgroup v1 configured; rebooting"
