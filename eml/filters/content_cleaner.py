"""Content cleaning utilities for optimizing email content for LLM processing."""

import re
import logging

logger = logging.getLogger(__name__)


class ContentCleaner:
    """
    Utilities for cleaning and preparing email content for LLM processing.
    Reduces token usage by 30-40% while preserving essential information.
    """

    @staticmethod
    def clean_email_body(text: str, max_length: int = 1500) -> str:
        """
        Cleans email body by removing noise, quoted replies, and footers.

        Args:
            text: Raw email body (HTML or plain text)
            max_length: Maximum characters to return (default: 1500)

        Returns:
            Cleaned text optimized for LLM processing
        """
        if not text:
            return ""

        # Step 1: HTML to Markdown conversion (lightweight)
        text = ContentCleaner._html_to_markdown(text)

        # Step 2: Remove quoted replies and thread history
        text = ContentCleaner._remove_quoted_replies(text)

        # Step 3: Remove footers and boilerplate
        text = ContentCleaner._remove_footers(text)

        # Step 4: Collapse whitespace
        text = ContentCleaner._collapse_whitespace(text)

        # Step 5: Truncate to max length (preserve complete sentences)
        if len(text) > max_length:
            text = ContentCleaner._smart_truncate(text, max_length)

        return text.strip()

    @staticmethod
    def _html_to_markdown(text: str) -> str:
        """Convert basic HTML to Markdown for better token efficiency."""
        if not text or '<' not in text:
            return text

        # Structure: <br>, <p> -> Newlines
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p.*?>', '', text, flags=re.IGNORECASE)

        # Headers <h1>-<h6> -> # Title
        text = re.sub(
            r'<h[1-6].*?>(.*?)</h[1-6]>',
            r'\n# \1\n',
            text,
            flags=re.DOTALL | re.IGNORECASE
        )

        # Lists <li> -> - Item
        text = re.sub(
            r'<li.*?>(.*?)</li>',
            r'\n- \1',
            text,
            flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r'<ul.*?>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</ul>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<ol.*?>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</ol>', '\n', text, flags=re.IGNORECASE)

        # Links: <a href="...">text</a> -> [text](href)
        text = re.sub(
            r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>',
            r'[\2](\1)',
            text,
            flags=re.DOTALL | re.IGNORECASE
        )

        # Images: <img src="..." alt="..."> -> ![alt](src)
        text = re.sub(
            r'<img\s+(?:[^>]*?\s+)?src="([^"]*)"(?:[^>]*?\s+)?alt="([^"]*)"[^>]*>',
            r'![\2](\1)',
            text,
            flags=re.DOTALL | re.IGNORECASE
        )

        # Remove scripts and styles (strictly remove content)
        text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Decode HTML entities
        text = re.sub(r'&nbsp;', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'&amp;', '&', text, flags=re.IGNORECASE)
        text = re.sub(r'&lt;', '<', text, flags=re.IGNORECASE)
        text = re.sub(r'&gt;', '>', text, flags=re.IGNORECASE)
        text = re.sub(r'&quot;', '"', text, flags=re.IGNORECASE)
        text = re.sub(r'&#39;', "'", text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def _remove_quoted_replies(text: str) -> str:
        """
        Remove quoted reply chains to reduce token usage.
        Stops at "On ... wrote:" pattern which indicates previous messages.
        """
        lines = text.splitlines()
        cleaned_lines = []

        # Reply header patterns that indicate start of previous messages
        reply_header_patterns = [
            r'^On .* wrote:$',              # Gmail style
            r'^From: .*$',                  # Outlook style
            r'^Sent: .*$',                  # Outlook continued
            r'^-{3,}.*Original Message',   # Outlook divider
            r'^_{3,}',                      # Thunderbird divider
        ]

        for line in lines:
            line_stripped = line.strip()

            # Skip lines starting with > (quoted text)
            if line_stripped.startswith('>'):
                continue

            # Check for reply headers - STOP processing if found
            # This aggressively cuts off thread history to save tokens
            for pattern in reply_header_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    # Stop here - everything after is old thread history
                    logger.debug(f"Truncating at reply header: {line_stripped[:50]}")
                    return '\n'.join(cleaned_lines)

            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    @staticmethod
    def _remove_footers(text: str) -> str:
        """
        Remove email footers, unsubscribe links, and legal boilerplate.
        Only processes lines shorter than 100 chars to avoid false positives.
        """
        footer_patterns = [
            r'unsubscribe',
            r'privacy policy',
            r'terms of service',
            r'view in browser',
            r'copyright \d{4}',
            r'confidential.*notice',
            r'this email.*intended',
            r'sent from my (iphone|ipad|android)',
        ]

        lines = text.splitlines()
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Only check short lines (footers are usually short)
            if len(line_stripped) < 100:
                is_footer = False
                for pattern in footer_patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        is_footer = True
                        logger.debug(f"Removing footer: {line_stripped[:50]}")
                        break
                if is_footer:
                    continue

            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    @staticmethod
    def _collapse_whitespace(text: str) -> str:
        """Collapse multiple newlines and excessive whitespace."""
        # Collapse multiple spaces to single space (but preserve newlines)
        text = re.sub(r'[ \t]+', ' ', text)

        # Collapse 3+ newlines to 2 newlines (preserve paragraph breaks)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text

    @staticmethod
    def _smart_truncate(text: str, max_length: int) -> str:
        """
        Truncate text to max_length while trying to preserve complete sentences.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text ending at a sentence boundary if possible
        """
        if len(text) <= max_length:
            return text

        # Try to find last sentence boundary before max_length
        truncated = text[:max_length]

        # Look for sentence endings: . ! ? followed by space or newline
        sentence_endings = [
            truncated.rfind('. '),
            truncated.rfind('! '),
            truncated.rfind('? '),
            truncated.rfind('.\n'),
            truncated.rfind('!\n'),
            truncated.rfind('?\n'),
        ]

        # Get the last sentence boundary
        last_boundary = max(sentence_endings)

        if last_boundary > max_length * 0.7:  # At least 70% of max_length
            # Truncate at sentence boundary
            return truncated[:last_boundary + 1].strip() + "..."
        else:
            # No good boundary found, just truncate
            return truncated.strip() + "..."

    @staticmethod
    def extract_metadata_signals(email_msg) -> dict:
        """
        Extract useful metadata signals from email headers.

        Args:
            email_msg: Email message object

        Returns:
            Dict of metadata signals for LLM classification
        """
        signals = {}

        # List-Unsubscribe header (strong signal for newsletters/promotional)
        if email_msg.get('List-Unsubscribe'):
            signals['list_unsubscribe'] = True

        # Priority/Importance headers
        priority = email_msg.get('X-Priority') or email_msg.get('Importance')
        if priority:
            signals['priority'] = priority

        # Auto-Submitted header (indicates automated messages)
        auto_submitted = email_msg.get('Auto-Submitted')
        if auto_submitted:
            signals['auto_submitted'] = auto_submitted

        # Precedence header (bulk mail indicator)
        precedence = email_msg.get('Precedence')
        if precedence and precedence.lower() in ['bulk', 'list']:
            signals['bulk_mail'] = True

        return signals
