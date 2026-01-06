"""LLM-based email classification for ambiguous cases."""

import json
import logging
import re
from email.message import Message
from typing import Optional, Dict

from pydantic import BaseModel, Field, ValidationError
import openai

from .categories import EmailCategory
from .llm_error_handler import SmartLLMHandler
from .content_cleaner import ContentCleaner

logger = logging.getLogger(__name__)


class EmailClassificationResult(BaseModel):
    """Structured result from LLM classification."""
    category: EmailCategory = Field(
        description="The email category"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score (0.0-1.0)"
    )
    reasoning: str = Field(
        description="Brief explanation for the classification"
    )


class LLMEmailClassifier:
    """
    Use LLM to classify emails that heuristics can't handle confidently.

    Uses a lightweight/cheap model for cost efficiency.
    Only called when heuristics return None (ambiguous).
    Includes error handling, circuit breaker, and health checks.
    """

    CLASSIFICATION_PROMPT_TEMPLATE = """Classify this email into ONE category:

Categories:
- conversation: Human-to-human business or personal dialogue (customers, leads, partners)
- transactional: Order confirmations, receipts, account actions, password resets
- promotional: Marketing emails, sales pitches, advertisements, special offers
- newsletter: Regular content updates, digests, industry news
- notification: Automated system alerts (CI/CD, monitoring, build failures, GitHub/GitLab)
- automated: Auto-replies, out-of-office messages, delivery notifications
- spam: Unwanted or suspicious emails

Instructions:
1. Focus on whether this email represents a REAL business opportunity or customer interaction
2. "conversation" = emails from potential/existing customers, partners, or business contacts
3. Everything automated, promotional, or mass-sent should NOT be "conversation"
4. Provide confidence score and brief reasoning

Email Details:
From: {sender}
To: {recipient}
Subject: {subject}

Body Preview:
{preview}

Metadata Signals:
{signals}

REQUIRED OUTPUT FORMAT (JSON):
{{
  "category": "category_name",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Return ONLY valid JSON."""

    def __init__(self, llm_client: openai.OpenAI, model: str = "gpt-4o-mini", max_tokens: int = 150, temperature: float = 0.3):
        """
        Initialize LLM classifier.

        Args:
            llm_client: OpenAI-compatible client (already configured)
            model: Model name (default: gpt-4o-mini for cost efficiency)
            max_tokens: Max tokens for response (default: 150)
            temperature: Sampling temperature (default: 0.3)
        """
        self.client = llm_client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enabled = True
        self.base_url = llm_client.base_url if hasattr(llm_client, 'base_url') else None

        # Initialize error handler with circuit breaker
        self.error_handler = SmartLLMHandler(
            network_failure_threshold=2,
            server_error_threshold=10,
            timeout_threshold=3
        )

        logger.info(f"Initialized LLM classifier with model: {model}, max_tokens: {max_tokens}, temp: {temperature}")

    def check_health(self) -> bool:
        """
        Quick health check to test LLM connectivity before processing.

        Returns:
            True if healthy, False otherwise.
        """
        if not self.enabled:
            return True

        try:
            logger.info("Testing LLM connectivity...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                timeout=5.0
            )
            logger.info(f"✅ LLM is reachable ({self.base_url or 'OpenAI'})")
            return True
        except Exception as e:
            logger.error(f"❌ LLM health check failed: {e}")
            should_disable = self.error_handler.handle_error(e, "health check")
            if should_disable:
                logger.warning("LLM classification will be disabled for this session.")
                self.enabled = False
            return False

    def classify(
        self,
        email_msg: Message,
        email_body_preview: str,
        max_preview_chars: int = 1500
    ) -> Optional[EmailCategory]:
        """
        Use LLM to classify email with optimized content cleaning.

        Args:
            email_msg: Email message object
            email_body_preview: Email body text (will be cleaned and truncated)
            max_preview_chars: Maximum characters to send to LLM (default: 1500)

        Returns:
            EmailCategory if successful, None if LLM call fails
        """
        # Check if LLM is enabled and circuit breaker is closed
        if not self.enabled or self.error_handler.is_circuit_open():
            logger.debug("LLM classifier disabled or circuit breaker open, skipping classification")
            return None

        sender = email_msg.get('From', 'Unknown')
        recipient = email_msg.get('To', 'Unknown')
        subject = email_msg.get('Subject', 'No Subject')

        # Clean and optimize email body (removes HTML, quoted replies, footers)
        cleaned_body = ContentCleaner.clean_email_body(email_body_preview, max_preview_chars)

        # Extract metadata signals
        signals = ContentCleaner.extract_metadata_signals(email_msg)
        signals_str = self._format_signals(signals)

        prompt = self.CLASSIFICATION_PROMPT_TEMPLATE.format(
            sender=sender,
            recipient=recipient,
            subject=subject,
            preview=cleaned_body,
            signals=signals_str
        )

        try:
            self.error_handler.record_attempt()
            logger.debug(f"Calling LLM to classify email: {subject[:50]}...")

            # Determine if we should use JSON mode (OpenAI only)
            is_openai = not self.base_url or "openai.com" in str(self.base_url)

            completion_args = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an email classification expert. Classify emails accurately and provide reasoning in JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "timeout": 30.0
            }

            # Only add response_format for OpenAI
            if is_openai:
                completion_args["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**completion_args)

            # Parse response
            content = response.choices[0].message.content
            result_dict = self._parse_json_response(content)

            if not result_dict:
                raise ValueError(f"Failed to parse LLM response as JSON: {content[:200]}")

            # Validate with Pydantic
            result = EmailClassificationResult(**result_dict)

            self.error_handler.record_success()

            logger.info(
                f"LLM classified as: {result.category.value} "
                f"(confidence: {result.confidence:.2f}) - {result.reasoning[:100]}"
            )

            return result.category

        except ValidationError as e:
            logger.error(f"LLM response validation failed: {e}")
            self.error_handler.handle_error(e, subject[:50])
            return None

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            should_disable = self.error_handler.handle_error(e, subject[:50])
            if should_disable:
                logger.warning("LLM classifier disabled due to persistent errors")
                self.enabled = False
            return None

    def _format_signals(self, signals: dict) -> str:
        """
        Format metadata signals for inclusion in prompt.

        Args:
            signals: Dict of metadata signals

        Returns:
            Formatted string for prompt
        """
        if not signals:
            return "- None"

        signal_lines = []
        if signals.get('list_unsubscribe'):
            signal_lines.append("- Contains List-Unsubscribe header (Likely Newsletter/Promotional)")
        if signals.get('priority'):
            signal_lines.append(f"- Priority/Importance level: {signals['priority']}")
        if signals.get('auto_submitted'):
            signal_lines.append(f"- Auto-Submitted header: {signals['auto_submitted']} (Automated message)")
        if signals.get('bulk_mail'):
            signal_lines.append("- Bulk mail indicator present (Mass mailing)")

        return '\n'.join(signal_lines) if signal_lines else "- None"

    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """
        Robustly parse JSON from LLM response, handling markdown blocks and comments.

        Args:
            text: Raw LLM response text

        Returns:
            Parsed dict or None if parsing fails
        """
        if not text:
            return None

        text = text.strip()

        def strip_comments(json_str: str) -> str:
            """Strip C-style comments from JSON string."""
            # Remove // comments (but be careful about URLs)
            # Simple approach: remove anything from // to end of line if not preceded by :
            return re.sub(r'(?<!:)\/\/.*$', '', json_str, flags=re.MULTILINE)

        # Stage 1: Direct parsing with comment stripping
        try:
            return json.loads(strip_comments(text))
        except json.JSONDecodeError:
            pass

        # Stage 2: Extract from markdown code blocks
        if "```" in text:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if json_match:
                try:
                    return json.loads(strip_comments(json_match.group(1).strip()))
                except json.JSONDecodeError:
                    pass

        # Stage 3: Find anything between first { and last }
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(strip_comments(text[start:end+1]))
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def get_stats(self) -> str:
        """Get formatted statistics summary."""
        return self.error_handler.format_stats_summary()

    def classify_batch(
        self,
        emails: list[tuple[Message, str]],
        max_preview_chars: int = 500
    ) -> list[Optional[EmailCategory]]:
        """
        Classify multiple emails in batch (for future optimization).

        Args:
            emails: List of (email_msg, body_preview) tuples
            max_preview_chars: Maximum characters per preview

        Returns:
            List of categories (same length as input)
        """
        # For now, just iterate (can optimize with concurrent calls later)
        results = []
        for email_msg, body_preview in emails:
            category = self.classify(email_msg, body_preview, max_preview_chars)
            results.append(category)
        return results
