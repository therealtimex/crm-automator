"""LLM configuration utilities with proper fallback hierarchy."""

import os
import logging
from typing import Optional
import openai

logger = logging.getLogger(__name__)


def get_llm_config() -> dict:
    """
    Returns a normalized LLM configuration from environment variables.

    Priority: LLM_* > OPENAI_* > Defaults

    Returns:
        Dict with 'base_url', 'api_key', 'model' keys
    """
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("CLASSIFICATION_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": model
    }


def create_llm_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 60.0
) -> Optional[openai.OpenAI]:
    """
    Create an OpenAI-compatible client with proper configuration.

    Args:
        api_key: Optional API key override
        base_url: Optional base URL override
        timeout: Request timeout in seconds

    Returns:
        OpenAI client or None if configuration is invalid
    """
    # Get config with fallbacks
    config = get_llm_config()

    # Override with provided values
    final_api_key = api_key or config.get('api_key')
    final_base_url = base_url or config.get('base_url')

    # Infer if we're using a local provider that doesn't need an API key
    is_openai = not final_base_url or "openai.com" in final_base_url
    if not is_openai and not final_api_key:
        logger.info("Local LLM detected (no API key required)")
        final_api_key = "not-needed"

    # Validate configuration
    if not final_base_url and not final_api_key:
        logger.error(
            "No LLM configuration found. Set LLM_API_KEY and optionally LLM_BASE_URL "
            "environment variables."
        )
        return None

    try:
        client = openai.OpenAI(
            api_key=final_api_key,
            base_url=final_base_url,
            timeout=timeout
        )
        logger.info(
            f"Created LLM client: {final_base_url or 'OpenAI'} "
            f"(timeout: {timeout}s)"
        )
        return client
    except Exception as e:
        logger.error(f"Failed to create LLM client: {e}")
        return None
