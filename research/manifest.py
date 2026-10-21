"""Write results/MANIFEST.json: every result file with its SHA-256, size and the experiment it belongs to,
so anyone can confirm the numbers in the README come from these exact files.

    python research/manifest.py           # write
    python research/manifest.py --check   # verify the files still match
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
MODELS = {
    "decider": "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610",
    "claude_sonnet": "us.anthropic.claude-sonnet-4-6",
    "claude_haiku": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "claude_opus": "us.anthropic.claude-opus-4-6-v1",
}
PREREG = {
    "spike-v1": "PREREGISTRATION-spike.md", "spike-train": "PREREGISTRATION-spike.md",
    "baseline-haiku45": "PREREGISTRATION-spike.md", "baseline-sonnet-4-6": "PREREGISTRATION-spike.md",
    "baseline-opus-4-6": "PREREGISTRATION-spike.md", "baseline-opus-4-6-60tok": "PREREGISTRATION-spike.md",
    "significance": "PREREGISTRATION-spike.md", "calibration": "PREREGISTRATION-combo.md",
    "insciout": "PREREGISTRATION-insciout.md", "prompt-select": "PREREGISTRATION-prompts.md",
    "cascade": "PREREGISTRATION-cascade.md", "ai-summaries": "PREREGISTRATION-ai-summaries.md",
    "hypewatch-summary.json": "PREREGISTRATION-hypewatch.md",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build() -> dict:
    files = {}
    for p in sorted(R.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.json":
            rel = p.relative_to(R).as_posix()
            files[rel] = {"sha256": sha(p), "bytes": p.stat().st_size,
                          "preregistration": PREREG.get(rel.split("/")[0])}
    return {"models": MODELS, "files": files}


def main() -> int:
    path = R / "MANIFEST.json"
    if "--check" in sys.argv:
        old, new = json.loads(path.read_text())["files"], build()["files"]
        bad = [f for f in old if f not in new or new[f]["sha256"] != old[f]["sha256"]]
        print("all files match" if not bad else f"changed or missing: {bad}")
        return 1 if bad else 0
    path.write_text(json.dumps(build(), indent=1))
    print(f"wrote {path} ({len(build()['files'])} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
