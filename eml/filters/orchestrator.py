"""Email filter orchestrator coordinating all filtering strategies."""

import os
import logging
import re
from email.message import Message
from typing import Optional

import openai

from .categories import EmailCategory, FilterDecision
from .heuristic_filter import HeuristicFilter
from .eesa_filter import EESAHeaderFilter
from .llm_classifier import LLMEmailClassifier
from .llm_config import create_llm_client

logger = logging.getLogger(__name__)


class EmailFilterOrchestrator:
    """
    Coordinates all filtering strategies in priority order:
    1. Allowlist (force process)
    2. Blocklist (force suppress)
    3. EESA custom headers (pre-classified)
    4. Heuristics (fast rules)
    5. LLM classification (for ambiguous cases)
    """

    def __init__(
        self,
        suppress_categories: Optional[set[EmailCategory]] = None,
        allowlist_domains: Optional[list[str]] = None,
        blocklist_domains: Optional[list[str]] = None,
        classification_strategy: str = "hybrid",
        llm_client: Optional[openai.OpenAI] = None,
        llm_model: Optional[str] = None,
        llm_max_tokens: int = 150,
        llm_temperature: float = 0.3,
    ):
        """
        Initialize filter orchestrator.

        Args:
            suppress_categories: Set of categories to suppress
            allowlist_domains: Domains to always process (override suppressions)
            blocklist_domains: Domains to always suppress
            classification_strategy: "heuristic", "llm", or "hybrid" (default)
            llm_client: OpenAI-compatible client for LLM classification
            llm_model: Model name for classification (default: from env or gpt-4o-mini)
            llm_max_tokens: Max tokens for classification response
            llm_temperature: Temperature for classification
        """
        # Load configuration from environment if not provided
        self.suppress_categories = suppress_categories or self._load_suppress_categories()
        self.allowlist_domains = allowlist_domains or self._load_list_from_env("ALLOWLIST_DOMAINS")
        self.blocklist_domains = blocklist_domains or self._load_list_from_env("SUPPRESS_DOMAINS")
        self.classification_strategy = classification_strategy or os.environ.get(
            "CLASSIFICATION_STRATEGY", "hybrid"
        )

        # Initialize filters
        self.heuristic_filter = HeuristicFilter()
        self.eesa_filter = EESAHeaderFilter()

        # Initialize LLM classifier if needed
        self.llm_classifier: Optional[LLMEmailClassifier] = None
        if self.classification_strategy in ["llm", "hybrid"]:
            # Use provided client or create one from environment config
            final_client = llm_client
            if not final_client:
                logger.info("No LLM client provided, attempting to create from environment config")
                final_client = create_llm_client()

            if final_client:
                model = llm_model or os.environ.get("CLASSIFICATION_MODEL", "gpt-4o-mini")
                self.llm_classifier = LLMEmailClassifier(
                    final_client, 
                    model, 
                    max_tokens=llm_max_tokens, 
                    temperature=llm_temperature
                )

                # Run health check
                if not self.llm_classifier.check_health():
                    logger.warning("LLM health check failed, but will retry on first classification")
            else:
                logger.warning(
                    "LLM classification requested but no client available. "
                    "Falling back to heuristics only."
                )
                self.classification_strategy = "heuristic"

        logger.info(
            f"Filter orchestrator initialized:\n"
            f"  Strategy: {self.classification_strategy}\n"
            f"  Suppress categories: {[c.value for c in self.suppress_categories]}\n"
            f"  Allowlist domains: {len(self.allowlist_domains)}\n"
            f"  Blocklist domains: {len(self.blocklist_domains)}"
        )

    def should_process(self, email_msg: Message, email_body: str) -> FilterDecision:
        """
        Determine if email should be processed.

        Args:
            email_msg: Email message object
            email_body: Email body text

        Returns:
            FilterDecision with (should_process, reason, category)
        """
        # Stage 1: Check allowlist (highest priority)
        if self._is_allowlisted(email_msg):
            logger.info("Email allowlisted - will process")
            return FilterDecision(
                should_process=True,
                reason="allowlist_override",
                category=None
            )

        # Stage 2: Check blocklist
        if self._is_blocklisted(email_msg):
            logger.info("Email blocklisted - will suppress")
            return FilterDecision(
                should_process=False,
                reason="blocklist_suppress",
                category=None
            )

        # Stage 3: EESA custom headers
        eesa_category = self.eesa_filter.get_category(email_msg)
        if eesa_category:
            should_process = eesa_category not in self.suppress_categories
            reason = f"eesa_header:{eesa_category.value}"
            logger.info(f"EESA classification: {eesa_category.value} -> {'process' if should_process else 'suppress'}")
            return FilterDecision(
                should_process=should_process,
                reason=reason,
                category=eesa_category
            )

        # Stage 4: Heuristics
        heuristic_category = self.heuristic_filter.classify(email_msg)
        if heuristic_category:
            should_process = heuristic_category not in self.suppress_categories
            reason = f"heuristic:{heuristic_category.value}"
            logger.info(f"Heuristic classification: {heuristic_category.value} -> {'process' if should_process else 'suppress'}")
            return FilterDecision(
                should_process=should_process,
                reason=reason,
                category=heuristic_category
            )

        # Stage 5: LLM (only if hybrid/llm strategy)
        if self.classification_strategy in ["hybrid", "llm"] and self.llm_classifier:
            llm_category = self.llm_classifier.classify(email_msg, email_body)
            if llm_category:
                should_process = llm_category not in self.suppress_categories
                reason = f"llm:{llm_category.value}"
                logger.info(f"LLM classification: {llm_category.value} -> {'process' if should_process else 'suppress'}")
                return FilterDecision(
                    should_process=should_process,
                    reason=reason,
                    category=llm_category
                )

        # Default: process if unsure (fail-safe to avoid missing important emails)
        logger.info("No classification match - defaulting to process (fail-safe)")
        return FilterDecision(
            should_process=True,
            reason="default:no_classification",
            category=None
        )

    def _is_allowlisted(self, email_msg: Message) -> bool:
        """Check if sender is in allowlist."""
        if not self.allowlist_domains:
            return False

        sender = email_msg.get('From', '').lower()
        return self._matches_domain_list(sender, self.allowlist_domains)

    def _is_blocklisted(self, email_msg: Message) -> bool:
        """Check if sender is in blocklist."""
        if not self.blocklist_domains:
            return False

        sender = email_msg.get('From', '').lower()
        return self._matches_domain_list(sender, self.blocklist_domains)

    def _matches_domain_list(self, sender: str, domain_list: list[str]) -> bool:
        """Check if sender matches any domain in the list."""
        for domain in domain_list:
            # Support both full emails and domain patterns
            if domain.startswith('@'):
                # @example.com format
                if domain.lower() in sender:
                    return True
            elif '@' in domain:
                # full email: user@example.com
                if domain.lower() in sender:
                    return True
            else:
                # domain only: example.com
                if f"@{domain.lower()}" in sender or domain.lower() in sender:
                    return True
        return False

    def _load_suppress_categories(self) -> set[EmailCategory]:
        """Load suppress categories from environment."""
        categories_str = os.environ.get("SUPPRESS_CATEGORIES", "promotional,newsletter,automated,spam")
        categories = set()

        for cat_str in categories_str.split(","):
            cat_str = cat_str.strip().lower()
            if cat_str:
                try:
                    category = EmailCategory(cat_str)
                    categories.add(category)
                except ValueError:
                    logger.warning(f"Unknown category in SUPPRESS_CATEGORIES: {cat_str}")

        return categories

    def _load_list_from_env(self, env_var: str) -> list[str]:
        """Load comma-separated list from environment variable."""
        value = os.environ.get(env_var, "")
        if not value:
            return []
        return [item.strip().lower() for item in value.split(",") if item.strip()]

    def get_llm_stats(self) -> str:
        """Get LLM classification statistics summary."""
        if self.llm_classifier:
            return self.llm_classifier.get_stats()
        return ""
