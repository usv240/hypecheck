"""Reusable Strands Decider pattern: gate derived text on claim fidelity to its source."""

from .calibrate import conformal_threshold
from .decider import Decider, DeciderUnavailable
from .fidelity import STRENGTH, check_document, overclaim_probability
from .gate import ClaimFidelityGate, load_threshold
from .receipt import build_receipt, verify_receipt

__all__ = ["Decider", "DeciderUnavailable", "ClaimFidelityGate", "load_threshold", "conformal_threshold",
           "check_document", "overclaim_probability", "STRENGTH", "build_receipt", "verify_receipt"]
