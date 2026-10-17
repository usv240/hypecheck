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
EOF
systemctl daemon-reload
systemctl restart hypecheck
sleep 5
systemctl is-active decider hypecheck
curl -s -m 10 http://127.0.0.1/api/health | head -c 160; echo
