"""Claim fidelity: does a derived text claim more than its source?

The typed questions and the scoring live here, separate from the agent wiring, so they can be
evaluated on a benchmark exactly as they run in the agent. Every question below is the one the
evaluation scripts in research/ import, so the measured numbers describe this code.

Scoring (measured on the Wright & Augenstein 2021 benchmark, see research/):
each sentence's claim strength is classified on the four-level scale used in science
communication research (no relationship < correlational < conditional causal < direct causal),
and the overclaim score is the probability that the derived sentence sits on a higher level
than the source:

    P(overclaim) = sum_{i > j} P(derived = i) * P(source = j)

Comparing two separately classified strengths beat asking the model to compare the pair
directly (macro-F1 0.498 vs 0.408, AUROC 0.716 vs 0.676, zero-shot).

Two document-level advisories use the same trick on other scales (measured on InSciOut, the
462 real UK press releases coded by Sumner et al. 2014):
- advice inflation, a four-level advice scale on the whole release and on the paper's
  conclusion (AUROC 0.84 for inflated vs not);
- animal-to-human inference, a yes/no on the whole release (AUROC 0.61, weak: shown as a
  hint, never used to block).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .decider import Decider

STRENGTH = ["no_relationship", "correlational", "conditional_causal", "direct_causal"]

STRENGTH_Q = {
    "type": "choice",
    "instructions": "How strong is the relationship this scientific statement claims?",
    "criteria": {
        "no_relationship": "no correlational or causal relationship is stated; it reports a "
        "description, a method, a null result or a single finding",
        "correlational": "states an association between variables without claiming one causes "
        "the other, e.g. 'associated with', 'linked to', 'more likely to have'",
        "conditional_causal": "states a causal relationship with hedging, e.g. 'may reduce', "
        "'might cause', 'could improve'",
        "direct_causal": "states outright that one thing causes, prevents, reduces, improves or "
        "increases another, e.g. 'reduces', 'leads to', 'saves lives'",
    },
}

ADVICE = ["no_advice", "implicit", "explicit_indirect", "explicit_direct"]

ADVICE_Q = {
    "type": "choice",
    "instructions": "What is the strongest advice or recommendation this text gives?",
    "criteria": {
        "no_advice": "no advice or recommendation of any kind",
        "implicit": "only implies what might be done, e.g. 'has implications for treatment', "
        "'could help doctors'",
        "explicit_indirect": "explicitly recommends what others should do, e.g. 'doctors should', "
        "'policy makers need to', 'parents ought to'",
        "explicit_direct": "explicitly tells the reader what to do, e.g. 'you should', 'eat more', "
        "'avoid', 'people should take'",
    },
}

ANIMAL_Q = {
    "type": "noul",
    "instructions": "Does the press release present the finding as if it applied to people?",
    "criteria": {
        "true": "the press release talks about people, patients or humans as if the study had shown "
        "the effect in them",
        "false": "the press release keeps clear that the finding is in animals, cells or a lab model",
    },
}


def split_sentences(text: str) -> list[str]:
    """Plain-text sentence split; good enough for press-release prose."""
    parts = re.split(r"(?<=[.!?])[\"')\]]?\s+(?=[A-Z0-9\"'(])", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]


def overclaim_probability(p_derived: list[float], p_source: list[float]) -> float:
    n = len(p_derived)
    return sum(p_derived[i] * p_source[j] for i in range(n) for j in range(n) if i > j)


@dataclass
class SentenceVerdict:
    sentence: str
    strength: str
    p_strength: list[float]
    p_overclaim: float


@dataclass
class DocumentVerdict:
    source_strength: str
    p_source: list[float]
    sentences: list[SentenceVerdict]
    # Document-level advisories; empty when not requested.
    advisory: dict[str, float] = field(default_factory=dict)


def strength(decider: Decider, text: str) -> list[float]:
    ans = decider.ask(text, {"strength": STRENGTH_Q})["strength"]
    return [ans["probabilities"][k] for k in STRENGTH]


def advice_level(decider: Decider, text: str) -> list[float]:
    ans = decider.ask(text, {"advice": ADVICE_Q})["advice"]
    return [ans["probabilities"][k] for k in ADVICE]


def check_document(decider: Decider, source: str, derived: str, advisory: bool = True) -> DocumentVerdict:
    """Score every sentence of `derived` against `source`: one decider request per sentence,
    one for the source, plus three for the document-level advisories."""
    p_src = strength(decider, source)
    verdicts = []
    for sent in split_sentences(derived):
        p = strength(decider, sent)
        verdicts.append(SentenceVerdict(sent, STRENGTH[p.index(max(p))], p, overclaim_probability(p, p_src)))

    adv: dict[str, float] = {}
    if advisory:
        a_rel, a_src = advice_level(decider, derived), advice_level(decider, source)
        adv["advice_inflated"] = round(overclaim_probability(a_rel, a_src), 4)
        adv["advice_level"] = a_rel.index(max(a_rel))
        # The InSciOut measurement told the model the study *was* non-human (the coders knew);
        # here the subject is unknown, so the state only raises the possibility. Treat as a hint.
        state = ("The study this press release reports may have been done in animals, cells or a lab model.\n\n"
                 f"PAPER'S CONCLUSION: {source}\n\nPRESS RELEASE:\n{derived}")
        adv["animal_to_human"] = round(decider.ask(state, {"q": ANIMAL_Q})["q"]["noul"], 4)
    return DocumentVerdict(STRENGTH[p_src.index(max(p_src))], p_src, verdicts, adv)
