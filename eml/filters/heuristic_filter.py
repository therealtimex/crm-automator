"""Fast heuristic-based email classification using headers and patterns."""

import re
import logging
from email.message import Message
from typing import Optional

from .categories import EmailCategory

logger = logging.getLogger(__name__)


class HeuristicFilter:
    """
    Fast rule-based email classification.
    Uses headers, sender patterns, and subject patterns for instant classification.
    """

    # Newsletter indicators (highest confidence)
    NEWSLETTER_HEADERS = [
        'List-Unsubscribe',
        'List-Id',
        'List-Post',
        'List-Subscribe',
        'List-Help',
    ]

    NEWSLETTER_HEADER_VALUES = {
        'Precedence': ['bulk', 'list'],
        'X-Mailer': ['mailchimp', 'sendgrid', 'constant contact'],
        'X-Campaign': True,  # Any value
    }

    NEWSLETTER_SENDER_PATTERNS = [
        r'newsletter@',
        r'news@',
        r'updates@',
        r'digest@',
        r'bulletin@',
    ]

    NEWSLETTER_SUBJECT_PATTERNS = [
        r'weekly\s+digest',
        r'monthly\s+update',
        r'daily\s+brief',
        r'newsletter',
        r'\[newsletter\]',
    ]

    # Promotional indicators
    PROMOTIONAL_SENDER_PATTERNS = [
        r'marketing@',
        r'promo@',
        r'deals@',
        r'offers@',
        r'sales@',
        r'noreply@',
        r'no-reply@',
    ]

    PROMOTIONAL_SUBJECT_PATTERNS = [
        r'\d+%\s+off',
        r'limited\s+time',
        r'\bsale\b',
        r'\bdeal\b',
        r'flash\s+sale',
        r'exclusive\s+offer',
        r'discount',
        r'save\s+\$',
        r'free\s+shipping',
    ]

    # Automated email indicators
    AUTOMATED_HEADERS = [
        'Auto-Submitted',
        'X-Auto-Response-Suppress',
        'X-Autoreply',
    ]

    AUTOMATED_SENDER_PATTERNS = [
        r'noreply@',
        r'no-reply@',
        r'donotreply@',
        r'do-not-reply@',
        r'mailer-daemon@',
        r'postmaster@',
    ]

    AUTOMATED_SUBJECT_PATTERNS = [
        r'^(re:|fwd:)*\s*out\s+of\s+(the\s+)?office',
        r'automatic\s+reply',
        r'auto\s*-?\s*reply',
        r'away\s+from\s+(my\s+)?desk',
        r'vacation\s+response',
    ]

    # Notification indicators (CI/CD, monitoring, alerts)
    NOTIFICATION_SENDER_PATTERNS = [
        r'notifications?@',
        r'alerts?@',
        r'monitor(ing)?@',
        r'ci@',
        r'cd@',
        r'builds?@',
        r'github@',
        r'gitlab@',
        r'jenkins@',
        r'travis@',
        r'circleci@',
        r'noreply.*github',
        r'noreply.*gitlab',
    ]

    NOTIFICATION_SUBJECT_PATTERNS = [
        r'\[build\s+(failed|passed|success)\]',
        r'\[ci\]',
        r'\[alert\]',
        r'\[notification\]',
        r'deployment\s+(failed|succeeded)',
        r'pipeline\s+(failed|passed)',
        r'test\s+(failed|passed)',
    ]

    # Transactional indicators
    TRANSACTIONAL_SUBJECT_PATTERNS = [
        r'receipt',
        r'invoice',
        r'order\s+confirmation',
        r'payment\s+confirmation',
        r'shipping\s+confirmation',
        r'password\s+reset',
        r'verify\s+your\s+email',
        r'account\s+verification',
        r'confirm\s+your\s+email',
    ]

    def classify(self, email_msg: Message) -> Optional[EmailCategory]:
        """
        Classify email using fast heuristics.
        Returns category if confident, None if ambiguous (needs LLM).
        """
        # Priority order: Check most specific patterns first

        # 1. Check for newsletters (high confidence indicators)
        if self._is_newsletter(email_msg):
            logger.debug("Classified as newsletter via heuristics")
            return EmailCategory.NEWSLETTER

        # 2. Check for automated emails
        if self._is_automated(email_msg):
            logger.debug("Classified as automated via heuristics")
            return EmailCategory.AUTOMATED

        # 3. Check for notifications (CI/CD, monitoring)
        if self._is_notification(email_msg):
            logger.debug("Classified as notification via heuristics")
            return EmailCategory.NOTIFICATION

        # 4. Check for promotional
        if self._is_promotional(email_msg):
            logger.debug("Classified as promotional via heuristics")
            return EmailCategory.PROMOTIONAL

        # 5. Check for transactional
        if self._is_transactional(email_msg):
            logger.debug("Classified as transactional via heuristics")
            return EmailCategory.TRANSACTIONAL

        # Ambiguous - needs LLM classification
        logger.debug("No heuristic match - needs LLM classification")
        return None

    def _is_newsletter(self, email_msg: Message) -> bool:
        """Check if email is a newsletter."""
        # Check for newsletter-specific headers
        for header in self.NEWSLETTER_HEADERS:
            if email_msg.get(header):
                return True

        # Check for header values
        for header, values in self.NEWSLETTER_HEADER_VALUES.items():
            header_value = email_msg.get(header, '').lower()
            if header_value:
                if values is True:  # Any value counts
                    return True
                elif isinstance(values, list):
                    if any(v in header_value for v in values):
                        return True

        # Check sender patterns
        sender = email_msg.get('From', '').lower()
        if self._matches_patterns(sender, self.NEWSLETTER_SENDER_PATTERNS):
            return True

        # Check subject patterns
        subject = email_msg.get('Subject', '').lower()
        if self._matches_patterns(subject, self.NEWSLETTER_SUBJECT_PATTERNS):
            return True

        return False

    def _is_automated(self, email_msg: Message) -> bool:
        """Check if email is automated (auto-reply, out-of-office)."""
        # Check headers
        for header in self.AUTOMATED_HEADERS:
            if email_msg.get(header):
                return True

        # Check sender
        sender = email_msg.get('From', '').lower()
        if self._matches_patterns(sender, self.AUTOMATED_SENDER_PATTERNS):
            return True

        # Check subject
        subject = email_msg.get('Subject', '').lower()
        if self._matches_patterns(subject, self.AUTOMATED_SUBJECT_PATTERNS):
            return True

        return False

    def _is_notification(self, email_msg: Message) -> bool:
        """Check if email is a notification (CI/CD, monitoring, alerts)."""
        sender = email_msg.get('From', '').lower()
        if self._matches_patterns(sender, self.NOTIFICATION_SENDER_PATTERNS):
            return True

        subject = email_msg.get('Subject', '').lower()
        if self._matches_patterns(subject, self.NOTIFICATION_SUBJECT_PATTERNS):
            return True

        return False

    def _is_promotional(self, email_msg: Message) -> bool:
        """Check if email is promotional."""
        sender = email_msg.get('From', '').lower()
        if self._matches_patterns(sender, self.PROMOTIONAL_SENDER_PATTERNS):
            # Double-check subject to avoid false positives
            subject = email_msg.get('Subject', '').lower()
            if self._matches_patterns(subject, self.PROMOTIONAL_SUBJECT_PATTERNS):
                return True
            # If sender matches promo patterns, still likely promotional
            if any(pattern in sender for pattern in ['marketing@', 'promo@', 'deals@', 'offers@']):
                return True

        # Check subject alone (stronger indicators)
        subject = email_msg.get('Subject', '').lower()
        if self._matches_patterns(subject, self.PROMOTIONAL_SUBJECT_PATTERNS):
            return True

        return False

    def _is_transactional(self, email_msg: Message) -> bool:
        """Check if email is transactional."""
        subject = email_msg.get('Subject', '').lower()
        return self._matches_patterns(subject, self.TRANSACTIONAL_SUBJECT_PATTERNS)

    def _matches_patterns(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the regex patterns."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
