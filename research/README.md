# Reproducing every number

All scripts talk to a local `strands-decider serve` on port 8099 (`STRANDS_DECIDER_URL` overrides).
Each experiment has a `PREREGISTRATION-*.md` written before it ran, with the outcome appended after.
Per-item outputs are in `results/`.

```bash
pip install -r requirements-research.txt
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099
```

## Data (not redistributed here)

| Set | Where | Licence | Put at |
|---|---|---|---|
| Wright & Augenstein 2021 release/abstract pairs | https://huggingface.co/datasets/copenlu/scientific-exaggeration-detection | GPL-3.0 | `data/train.jsonl`, `data/test.jsonl` |
| Yu, Li & Wang 2019 causal language | https://github.com/junwang4/causal-language-use-in-science | GPL-3.0 | `data/pubmed_causal_language_use.csv` |
| InSciOut (Sumner et al. 2014) | https://figshare.com/articles/dataset/InSciOut/903704 | CC BY 4.0 | unzip anywhere; pass `open data/` |

Yu's labels are 1 = direct causal, 2 = conditional, 3 = correlational (not the order our scale uses;
`spike.py` records the raw prediction and `PREREGISTRATION-spike.md` explains the one-time mis-map).

## Commands, in the order they were run

| Step | Command | Writes |
|---|---|---|
| Zero-shot spike (W&A test + Yu19) | `python research/spike.py --wa data/test.jsonl --yu data/pubmed_causal_language_use.csv --out research/results/spike-v1` | `spike-v1/` |
| Claude baselines on Bedrock | `python research/baseline_bedrock.py --wa data/test.jsonl --model us.anthropic.claude-haiku-4-5-20251001-v1:0 --out research/results/baseline-haiku45` (also `claude-sonnet-4-6`, `claude-opus-4-6-v1` with `--workers 1 --max-tokens 400`) | `baseline-*/` |
| Conformal threshold on train, checked on test | `python research/calibration_eval.py` | `calibration/` |
| Advisory checks on real releases | `python -m research.insciout_eval --insciout "path/open data"` | `insciout/` |
| Signal combination (train-only rule, not adopted) | see `PREREGISTRATION-combo.md` | `calibration/combo_decision.json` |
| Prompt wording (train-only rule, not adopted) | `python research/prompt_select.py` | `prompt-select/` |
| Cascade: Claude only on REVIEW (offline, not adopted) | `python research/cascade_eval.py` | `cascade/` |
| Paired-bootstrap 95% CIs for every headline gap (offline) | `python research/significance.py` | `significance/` |
| AWS-native baseline: Bedrock Guardrails contextual grounding (creates and deletes one guardrail) | `python research/guardrails_baseline.py --wa-dir data` | `guardrails/` |
| No-model baseline: the site's cue-word lists as a classifier (offline) | `python research/keyword_baseline.py --wa-dir data` | `keyword-baseline/` |
| Other Decider 2B checkpoints (hobson-v21, v19) and an ensemble, train split only (not adopted) | `python research/checkpoint_eval.py score --url … --name hobson-v21 --split train --wa-dir data`, then `summary` | `checkpoints/` |
| AI summaries: Claude summarises the HypeWatch papers, the gate checks them (on the EC2 box) | `python -m research.ai_summary_eval` | `ai-summaries/` |
| Fingerprint every result file | `python research/manifest.py` (`--check` to verify) | `MANIFEST.json` |

`python research/reproduce.py` recomputes every headline number from these per-item outputs, offline, and checks it against the README (21 of 21 reproduce).

`python -m pytest -q tests` runs the offline tests of the pattern itself.

## Hardware used

RTX 4070 Laptop GPU (8 GB) under WSL2 for all Decider numbers; the live demo box is a c7i.4xlarge
(CPU), about six times slower per decision. Bedrock calls from us-east-1.
