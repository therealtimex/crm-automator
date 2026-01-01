"""
Email filtering system for CRM Automator.

Provides hybrid filtering approach combining:
- Fast heuristics (headers, sender patterns)
- EESA custom headers (pre-classification)
- LLM classification (for ambiguous cases)
"""

from .categories import EmailCategory, FilterDecision
from .heuristic_filter import HeuristicFilter
from .eesa_filter import EESAHeaderFilter
from .llm_classifier import LLMEmailClassifier
from .orchestrator import EmailFilterOrchestrator
from .logging import log_suppressed_email

__all__ = [
    "EmailCategory",
    "FilterDecision",
    "HeuristicFilter",
    "EESAHeaderFilter",
    "LLMEmailClassifier",
    "EmailFilterOrchestrator",
    "log_suppressed_email",
]
