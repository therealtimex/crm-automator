"""Email category definitions and filter decision types."""

from enum import Enum
from typing import NamedTuple


class EmailCategory(str, Enum):
    """Email classification categories."""
    CONVERSATION = "conversation"          # Human-to-human dialogue
    TRANSACTIONAL = "transactional"        # Receipts, confirmations, password resets
    PROMOTIONAL = "promotional"            # Marketing, sales pitches
    NEWSLETTER = "newsletter"              # Regular content updates
    NOTIFICATION = "notification"          # Automated alerts (CI/CD, monitoring)
    AUTOMATED = "automated"                # Auto-replies, out-of-office
    SPAM = "spam"                          # Unwanted/suspicious


class FilterDecision(NamedTuple):
    """Result of a filtering decision."""
    should_process: bool
    reason: str
    category: EmailCategory | None = None
