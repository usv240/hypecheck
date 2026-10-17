#!/bin/bash
# Run on the HypeCheck box (via SSM send-command) to pick up the latest main and the Decider key.
#   aws ssm send-command --instance-ids <id> --document-name AWS-RunShellScript \
#     --parameters 'commands=["bash /opt/hypecheck/deploy/update-ec2.sh"]'
set -euo pipefail
git -C /opt/hypecheck pull -q
/opt/hypecheck/.venv/bin/pip install -q -r /opt/hypecheck/requirements.txt

# The key that guards /decider/v1/systemone lives in SSM Parameter Store, never in the repo.
cat >/usr/local/bin/hypecheck-env <<'EOF'
#!/bin/bash
mkdir -p /run/hypecheck
/opt/hypecheck/.venv/bin/python - >/run/hypecheck/env <<'PY'
import boto3
try:
    k = boto3.client("ssm", region_name="us-east-1").get_parameter(
        Name="/hypecheck/decider-key", WithDecryption=True)["Parameter"]["Value"]
    print(f"HYPECHECK_DECIDER_KEY={k}")
except Exception:
    pass
PY
chmod 600 /run/hypecheck/env
EOF
chmod +x /usr/local/bin/hypecheck-env

mkdir -p /etc/systemd/system/hypecheck.service.d
cat >/etc/systemd/system/hypecheck.service.d/key.conf <<'EOF'
[Service]
ExecStartPre=/usr/local/bin/hypecheck-env
EnvironmentFile=-/run/hypecheck/env
Environment=HYPEWATCH_DATA=/var/lib/hypecheck/hypewatch.json
Environment=HYPECHECK_STATE=/var/lib/hypecheck
EOF

# HypeWatch: seed from the repo's backfill once, then check new NIH releases every morning.
mkdir -p /var/lib/hypecheck
[ -f /var/lib/hypecheck/hypewatch.json ] || cp /opt/hypecheck/hypecheck/hypewatch.json /var/lib/hypecheck/hypewatch.json 2>/dev/null || true
cat >/etc/systemd/system/hypewatch.service <<'UNIT'
[Unit]
Description=HypeWatch daily check of new NIH news releases
After=decider.service
[Service]
Type=oneshot
WorkingDirectory=/opt/hypecheck
Environment=AWS_DEFAULT_REGION=us-east-1
Environment=HYPEWATCH_DATA=/var/lib/hypecheck/hypewatch.json
Environment=HYPECHECK_STATE=/var/lib/hypecheck
ExecStart=/opt/hypecheck/.venv/bin/python -m hypecheck.hypewatch update
UNIT
cat >/etc/systemd/system/hypewatch.timer <<'UNIT'
[Unit]
Description=Run HypeWatch every morning
[Timer]
OnCalendar=*-*-* 13:17:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now hypewatch.timer
systemctl restart hypecheck
sleep 5
systemctl is-active decider hypecheck
curl -s -m 10 http://127.0.0.1/api/health | head -c 160; echo
