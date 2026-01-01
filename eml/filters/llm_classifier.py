"""LLM-based email classification for ambiguous cases."""

import logging
from email.message import Message
from typing import Optional

from pydantic import BaseModel, Field
import instructor
import openai

from .categories import EmailCategory

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

Body Preview (first 500 chars):
{preview}

Classify this email."""

    def __init__(self, llm_client: openai.OpenAI, model: str = "gpt-4o-mini"):
        """
        Initialize LLM classifier.

        Args:
            llm_client: OpenAI-compatible client (already configured)
            model: Model name (default: gpt-4o-mini for cost efficiency)
        """
        self.client = instructor.from_openai(llm_client, mode=instructor.Mode.MD_JSON)
        self.model = model
        logger.info(f"Initialized LLM classifier with model: {model}")

    def classify(
        self,
        email_msg: Message,
        email_body_preview: str,
        max_preview_chars: int = 500
    ) -> Optional[EmailCategory]:
        """
        Use LLM to classify email.

        Args:
            email_msg: Email message object
            email_body_preview: Email body text (will be truncated)
            max_preview_chars: Maximum characters to send to LLM

        Returns:
            EmailCategory if successful, None if LLM call fails
        """
        sender = email_msg.get('From', 'Unknown')
        recipient = email_msg.get('To', 'Unknown')
        subject = email_msg.get('Subject', 'No Subject')
        preview = email_body_preview[:max_preview_chars]

        prompt = self.CLASSIFICATION_PROMPT_TEMPLATE.format(
            sender=sender,
            recipient=recipient,
            subject=subject,
            preview=preview
        )

        try:
            logger.debug(f"Calling LLM to classify email: {subject[:50]}...")

            result: EmailClassificationResult = self.client.chat.completions.create(
                model=self.model,
                response_model=EmailClassificationResult,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an email classification expert. Classify emails accurately and provide reasoning."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=150,  # Keep response concise
            )

            logger.info(
                f"LLM classified as: {result.category.value} "
                f"(confidence: {result.confidence:.2f}) - {result.reasoning[:100]}"
            )

            return result.category

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return None

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
