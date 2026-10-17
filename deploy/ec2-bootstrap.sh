#!/bin/bash
# EC2 user-data for a single HypeCheck box: Strands Decider on :8099 (localhost only) and the
# HypeCheck web app on :80. Ubuntu 24.04. Uses the GPU when one is present, CPU otherwise,
# so the same script serves a g6.xlarge and a c7i.4xlarge.
set -euxo pipefail
exec > >(tee /var/log/hypecheck-bootstrap.log) 2>&1

REPO="${HYPECHECK_REPO:-https://github.com/usv240/hypecheck}"
CKPT="StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
export DEBIAN_FRONTEND=noninteractive HF_HOME=/opt/hf

apt-get update
apt-get install -y python3.12-venv python3.12-dev build-essential git

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  DEVICE=cuda; TORCH_INDEX=https://download.pytorch.org/whl/cu126; EXTRA="[cuda]"
else
  DEVICE=cpu;  TORCH_INDEX=https://download.pytorch.org/whl/cpu;   EXTRA=""
fi

# --- Decider ---------------------------------------------------------------
python3 -m venv /opt/decider
/opt/decider/bin/pip install -q --upgrade pip
/opt/decider/bin/pip install -q torch==2.7.1 --index-url "$TORCH_INDEX"
/opt/decider/bin/pip install -q "strands-decider${EXTRA} @ git+https://github.com/strands-labs/strands-decider"

cat >/etc/systemd/system/decider.service <<EOF
[Unit]
Description=Strands Decider 2B
After=network-online.target
[Service]
Environment=HF_HOME=/opt/hf
ExecStart=/opt/decider/bin/strands-decider serve $CKPT --device $DEVICE --port 8099
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF

# --- HypeCheck -------------------------------------------------------------
git clone "$REPO" /opt/hypecheck
python3 -m venv /opt/hypecheck/.venv
/opt/hypecheck/.venv/bin/pip install -q --upgrade pip
/opt/hypecheck/.venv/bin/pip install -q -r /opt/hypecheck/requirements.txt

cat >/etc/systemd/system/hypecheck.service <<EOF
[Unit]
Description=HypeCheck web app
After=decider.service
[Service]
WorkingDirectory=/opt/hypecheck
Environment=AWS_DEFAULT_REGION=us-east-1
Environment=STRANDS_DECIDER_URL=http://127.0.0.1:8099
Environment=HYPECHECK_OUTBOX=/var/lib/hypecheck/outbox
Environment=HYPECHECK_DEVICE=$DEVICE
ExecStart=/opt/hypecheck/.venv/bin/uvicorn hypecheck.web:app --host 0.0.0.0 --port 80
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF

mkdir -p /var/lib/hypecheck/outbox
systemctl daemon-reload
systemctl enable --now decider hypecheck
echo "bootstrap done: device=$DEVICE"
