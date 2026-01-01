"""EESA custom header support for pre-classified emails."""

import logging
from email.message import Message
from typing import Optional

from .categories import EmailCategory

logger = logging.getLogger(__name__)


class EESAHeaderFilter:
    """
    Extract email classification from EESA custom headers.

    EESA (Email Enhanced Structured Analysis) headers allow pre-classification
    at the email client level or by upstream processing systems.

    Supported headers:
    - X-EESA-Category: Email category (conversation, promotional, etc.)
    - X-CRM-Category: Alternative category header
    - X-CRM-Suppress: Explicit suppress flag (true/false)
    - X-CRM-Priority: Priority level (0 = suppress)
    - X-Email-Category: Another alternative header name
    """

    # Supported header names in priority order
    CATEGORY_HEADERS = [
        'X-EESA-Category',
        'X-CRM-Category',
        'X-Email-Category',
    ]

    SUPPRESS_HEADERS = [
        'X-CRM-Suppress',
        'X-EESA-Suppress',
    ]

    PRIORITY_HEADERS = [
        'X-CRM-Priority',
        'X-EESA-Priority',
    ]

    def get_category(self, email_msg: Message) -> Optional[EmailCategory]:
        """
        Extract category from EESA headers if present.
        Returns None if no valid category header found.
        """
        # Check for explicit suppress flags first
        if self._is_suppressed(email_msg):
            logger.debug("Email marked for suppression via EESA header")
            return EmailCategory.SPAM  # Use SPAM category to indicate suppression

        # Check for category headers
        for header in self.CATEGORY_HEADERS:
            category_value = email_msg.get(header)
            if category_value:
                category = self._parse_category(category_value)
                if category:
                    logger.info(f"Found EESA category: {category.value} (from {header})")
                    return category

        return None

    def _is_suppressed(self, email_msg: Message) -> bool:
        """Check if email has explicit suppress flag."""
        # Check suppress flags
        for header in self.SUPPRESS_HEADERS:
            suppress_value = email_msg.get(header, '').lower()
            if suppress_value in ['true', '1', 'yes', 'suppress']:
                return True

        # Check priority (0 = suppress)
        for header in self.PRIORITY_HEADERS:
            priority_value = email_msg.get(header)
            if priority_value:
                try:
                    priority = int(priority_value)
                    if priority == 0:
                        return True
                except ValueError:
                    logger.warning(f"Invalid priority value in {header}: {priority_value}")

        return False

    def _parse_category(self, category_value: str) -> Optional[EmailCategory]:
        """
        Parse category value from header.
        Handles various formats and variations.
        """
        category_lower = category_value.strip().lower()

        # Direct mapping
        category_map = {
            'conversation': EmailCategory.CONVERSATION,
            'transactional': EmailCategory.TRANSACTIONAL,
            'promotional': EmailCategory.PROMOTIONAL,
            'newsletter': EmailCategory.NEWSLETTER,
            'notification': EmailCategory.NOTIFICATION,
            'automated': EmailCategory.AUTOMATED,
            'spam': EmailCategory.SPAM,
            # Variations/aliases
            'promo': EmailCategory.PROMOTIONAL,
            'marketing': EmailCategory.PROMOTIONAL,
            'auto': EmailCategory.AUTOMATED,
            'auto-reply': EmailCategory.AUTOMATED,
            'autoreply': EmailCategory.AUTOMATED,
            'alert': EmailCategory.NOTIFICATION,
            'alerts': EmailCategory.NOTIFICATION,
            'personal': EmailCategory.CONVERSATION,
            'business': EmailCategory.CONVERSATION,
        }

        category = category_map.get(category_lower)
        if category:
            return category

        logger.warning(f"Unknown EESA category value: {category_value}")
        return None
