"""Claim fidelity: does a derived sentence claim more than its source?

The typed questions and the scoring live here, separate from the agent wiring, so they can be
evaluated on a benchmark exactly as they run in the agent.

Scoring (measured on the Wright & Augenstein 2021 benchmark, see research/):
each sentence's claim strength is classified on the four-level scale used in science
communication research (no relationship < correlational < conditional causal < direct causal),
and the overclaim score is the probability that the derived sentence sits on a higher level
than the source:

    P(overclaim) = sum_{i > j} P(derived = i) * P(source = j)

Comparing two separately classified strengths beat asking the model to compare the pair
directly (macro-F1 0.498 vs 0.408, AUROC 0.716 vs 0.676, zero-shot).
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

# Advisory checks. They ride along in the same request as the pair state, so they cost almost
# nothing, but there is no public labelled set to calibrate them on: they are reported, never
# used on their own to block a publish.
ADVISORY_Q = {
    "animal_to_human": {
        "type": "noul",
        "instructions": "Does the press release sentence present a finding from animals, cells "
        "or a lab model as if it applied to people?",
        "criteria": {
            "true": "the paper studied animals, cells or a lab model, and the sentence talks "
            "about people or patients",
            "false": "the sentence is about the same kind of subject the paper studied",
        },
    },
    "unsupported_advice": {
        "type": "noul",
        "instructions": "Does the press release sentence tell readers what to do (eat, take, "
        "avoid, change) in a way the paper's conclusion does not recommend?",
        "criteria": {
            "true": "the sentence gives readers advice or a recommendation the paper does not make",
            "false": "the sentence gives no advice, or only advice the paper itself gives",
        },
    },
}


def split_sentences(text: str) -> list[str]:
    """Plain-text sentence split; good enough for press-release prose."""
    parts = re.split(r"(?<=[.!?])[\"')\]]?\s+(?=[A-Z0-9\"'(])", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]


def pair_state(source: str, sentence: str) -> str:
    return (
        "A scientific paper's conclusion and a sentence from the press release written about it.\n\n"
        f"PAPER'S CONCLUSION: {source}\n\nPRESS RELEASE SENTENCE: {sentence}"
    )


def overclaim_probability(p_derived: list[float], p_source: list[float]) -> float:
    n = len(p_derived)
    return sum(p_derived[i] * p_source[j] for i in range(n) for j in range(n) if i > j)


@dataclass
class SentenceVerdict:
    sentence: str
    strength: str
    p_strength: list[float]
    p_overclaim: float
    advisory: dict[str, float] = field(default_factory=dict)


@dataclass
class DocumentVerdict:
    source_strength: str
    p_source: list[float]
    sentences: list[SentenceVerdict]


def strength(decider: Decider, text: str) -> list[float]:
    ans = decider.ask(text, {"strength": STRENGTH_Q})["strength"]
    return [ans["probabilities"][k] for k in STRENGTH]


def check_document(decider: Decider, source: str, derived: str, advisory: bool = True) -> DocumentVerdict:
    """Score every sentence of `derived` against `source`. Two decider requests per sentence."""
    p_src = strength(decider, source)
    verdicts = []
    for sent in split_sentences(derived):
        p = strength(decider, sent)
        adv = {}
        if advisory:
            ans = decider.ask(pair_state(source, sent), ADVISORY_Q)
            adv = {k: round(v["noul"], 4) for k, v in ans.items()}
        verdicts.append(SentenceVerdict(
            sentence=sent, strength=STRENGTH[p.index(max(p))], p_strength=p,
            p_overclaim=overclaim_probability(p, p_src), advisory=adv,
        ))
    return DocumentVerdict(STRENGTH[p_src.index(max(p_src))], p_src, verdicts)
