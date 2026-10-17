"""Deploy HypeCheck to Amazon Bedrock AgentCore Runtime with direct code deploy (no Docker).

1. Installs Linux ARM64 wheels for Python 3.12 into a build folder and adds the project code.
2. Zips it and uploads it to an S3 bucket in the account.
3. Creates (or updates) a least-privilege execution role.
4. Creates (or updates) the agent runtime and waits until it is READY.

    python deploy/agentcore_deploy.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-1"
NAME = "hypecheck"
ROLE = "hypecheck-agentcore-role"
DEPS = ["strands-agents>=1.61", "bedrock-agentcore", "boto3"]
CODE = ["agentcore_app.py", "decision_pattern", "hypecheck/__init__.py", "hypecheck/agent.py",
        "research/results/calibration/summary.json"]


def build() -> Path:
    out = ROOT / "build" / "agentcore"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    pip_args = ["install", "-q", "--platform", "manylinux2014_aarch64", "--implementation", "cp",
                "--python-version", "3.12", "--only-binary=:all:", "--upgrade", *DEPS]
    if os.name == "nt":
        # pip on Windows evaluates environment markers (e.g. pywin32; sys_platform == "win32") against
        # the host even with --platform, so resolve the Linux wheels from WSL instead.
        drive, rest = str(out).split(":", 1)
        target = f"/mnt/{drive.lower()}{rest.replace(chr(92), '/')}"
        subprocess.run(["wsl", "-d", "Ubuntu", "--", "/home/ujwal/venvs/decider/bin/pip", *pip_args, "--target", target],
                       check=True)
    else:
        subprocess.run([sys.executable, "-m", "pip", *pip_args, "--target", str(out)], check=True)
    for item in CODE:
        src, dst = ROOT / item, out / item
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "README.md")) if src.is_dir() else shutil.copy2(src, dst)
    zpath = ROOT / "build" / "hypecheck-agentcore.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f.relative_to(out).as_posix())
    print(f"built {zpath} ({zpath.stat().st_size / 1e6:.1f} MB)")
    return zpath


def ensure_role(account: str) -> str:
    iam = boto3.client("iam")
    trust = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "bedrock-agentcore.amazonaws.com"}, "Action": "sts:AssumeRole",
        "Condition": {"StringEquals": {"aws:SourceAccount": account},
                      "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{REGION}:{account}:*"}}}]}
    try:
        arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(trust),
                              Description="HypeCheck on AgentCore Runtime")["Role"]["Arn"]
        time.sleep(10)  # IAM is eventually consistent
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        arn = iam.get_role(RoleName=ROLE)["Role"]["Arn"]
        iam.update_assume_role_policy(RoleName=ROLE, PolicyDocument=json.dumps(trust))
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
         "Resource": [f"arn:aws:bedrock:*::foundation-model/anthropic.*",
                      f"arn:aws:bedrock:*:{account}:inference-profile/us.anthropic.*"]},
        {"Effect": "Allow", "Action": "ssm:GetParameter",
         "Resource": f"arn:aws:ssm:{REGION}:{account}:parameter/hypecheck/decider-key"},
        {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                                       "logs:DescribeLogStreams", "logs:DescribeLogGroups"],
         "Resource": f"arn:aws:logs:{REGION}:{account}:log-group:/aws/bedrock-agentcore/*"},
        {"Effect": "Allow", "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords",
                                       "cloudwatch:PutMetricData"], "Resource": "*"},
    ]}
    iam.put_role_policy(RoleName=ROLE, PolicyName="hypecheck-runtime", PolicyDocument=json.dumps(policy))
    return arn


def main() -> None:
    account = boto3.client("sts").get_caller_identity()["Account"]
    bucket = f"hypecheck-agentcore-{account}"
    s3 = boto3.client("s3", region_name=REGION)
    try:
        s3.create_bucket(Bucket=bucket)
        s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
    zpath = build()
    key = f"code/hypecheck-{int(time.time())}.zip"
    s3.upload_file(str(zpath), bucket, key)
    role = ensure_role(account)

    ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
    spec = dict(
        agentRuntimeArtifact={"codeConfiguration": {"code": {"s3": {"bucket": bucket, "prefix": key}},
                                                    "runtime": "PYTHON_3_12", "entryPoint": ["agentcore_app.py"]}},
        roleArn=role, networkConfiguration={"networkMode": "PUBLIC"},
        protocolConfiguration={"serverProtocol": "HTTP"},
        environmentVariables={"HYPECHECK_DECIDER_URL": "https://d174bz5yly61n4.cloudfront.net/decider",
                              "HYPECHECK_OUTBOX": "/tmp/outbox"},
        description="HypeCheck: Strands agent gated by Strands Decider 2B")
    existing = [r for r in ctl.list_agent_runtimes()["agentRuntimes"] if r["agentRuntimeName"] == NAME]
    for attempt in range(6):
        try:
            if existing:
                rid = existing[0]["agentRuntimeId"]
                ctl.update_agent_runtime(agentRuntimeId=rid, **spec)
            else:
                rid = ctl.create_agent_runtime(agentRuntimeName=NAME, **spec)["agentRuntimeId"]
            break
        except ClientError as e:  # a fresh role may not be assumable yet
            if "role" in str(e).lower() and attempt < 5:
                time.sleep(10)
                continue
            raise
    while True:
        r = ctl.get_agent_runtime(agentRuntimeId=rid)
        print("status", r["status"])
        if r["status"] in ("READY", "CREATE_FAILED", "UPDATE_FAILED"):
            break
        time.sleep(10)
    print(json.dumps({"agentRuntimeArn": r["agentRuntimeArn"], "status": r["status"],
                      "failure": r.get("failureReason")}, indent=1))
    (ROOT / "hypecheck" / "agentcore.json").write_text(json.dumps({"agentRuntimeArn": r["agentRuntimeArn"]}, indent=1))


if __name__ == "__main__":
    main()
