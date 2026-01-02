"""Smart error handler for LLM API calls with circuit breaker pattern."""

import logging
import time
from enum import Enum
from typing import Tuple

logger = logging.getLogger(__name__)


class LLMErrorType(Enum):
    """Classification of LLM error types."""
    # Fatal - Disable LLM immediately
    NETWORK_UNREACHABLE = "network_unreachable"  # Connection refused, DNS failed
    AUTH_FAILED = "auth_failed"                  # 401, 403

    # Recoverable - Retry with backoff
    RATE_LIMITED = "rate_limited"                # 429
    SERVER_ERROR = "server_error"                # 500, 502, 503
    TIMEOUT = "timeout"                          # Request timeout

    # Soft errors - Continue processing
    PARSE_ERROR = "parse_error"                  # Invalid JSON response
    MODEL_ERROR = "model_error"                  # 400, 404 (wrong model/params)
    CONTENT_FILTER = "content_filter"            # Content policy violation
    UNKNOWN = "unknown"                          # Unclassified error


class SmartLLMHandler:
    """
    Intelligent error handler for LLM API calls.

    Distinguishes between different types of failures and applies
    appropriate strategies (disable, retry, backoff, etc.)
    """

    def __init__(
        self,
        network_failure_threshold: int = 2,
        server_error_threshold: int = 10,
        timeout_threshold: int = 3
    ):
        """
        Initialize the smart error handler.

        Args:
            network_failure_threshold: Number of network errors before disabling LLM
            server_error_threshold: Number of server errors before disabling LLM
            timeout_threshold: Number of timeouts before disabling LLM
        """
        self.network_failure_threshold = network_failure_threshold
        self.server_error_threshold = server_error_threshold
        self.timeout_threshold = timeout_threshold

        self.circuit_breaker = {
            'network_failures': 0,
            'server_errors': 0,
            'timeouts': 0,
            'is_open': False,
            'last_check': None,
            'open_reason': None
        }

        self.rate_limit_backoff = 1.0
        self.max_backoff = 60.0

        # Statistics for reporting
        self.stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'errors_by_type': {}
        }

    def classify_error(self, exception) -> Tuple[LLMErrorType, bool]:
        """
        Classify an exception and determine if LLM should be disabled.

        Args:
            exception: The exception that occurred

        Returns:
            Tuple of (error_type, should_disable_llm)
        """
        error_str = str(exception).lower()

        # Network errors - immediate disable after threshold
        if any(x in error_str for x in [
            'connection refused', 'network unreachable', 'connection error',
            'dns', 'name resolution', 'no route to host',
            'failed to establish a new connection', 'errno 61', 'errno 111'
        ]):
            return LLMErrorType.NETWORK_UNREACHABLE, False  # Will check threshold

        # Check OpenAI/HTTP-specific errors
        if hasattr(exception, 'status_code'):
            code = exception.status_code

            # Auth errors - immediate disable with clear message
            if code in [401, 403]:
                return LLMErrorType.AUTH_FAILED, True

            # Rate limiting - retry with backoff, don't disable
            if code == 429:
                return LLMErrorType.RATE_LIMITED, False

            # Server errors - retry, but disable after many failures
            if code in [500, 502, 503, 504]:
                return LLMErrorType.SERVER_ERROR, False

            # Client errors - continue, likely our request format
            if 400 <= code < 500:
                return LLMErrorType.MODEL_ERROR, True  # Config issue

        # Timeout errors - could be network or server
        if 'timeout' in error_str or 'timed out' in error_str or 'time out' in error_str:
            return LLMErrorType.TIMEOUT, False

        # Parse/JSON errors - LLM is working, just bad response
        if 'json' in error_str or 'parse' in error_str or 'decode' in error_str:
            return LLMErrorType.PARSE_ERROR, False

        # Content filter/policy violations
        if 'content_filter' in error_str or 'content policy' in error_str:
            return LLMErrorType.CONTENT_FILTER, False

        # Unknown error - treat as recoverable
        return LLMErrorType.UNKNOWN, False

    def handle_error(self, exception, context: str = "LLM call") -> bool:
        """
        Handle an LLM error and determine if processing should continue.

        Args:
            exception: The exception that occurred
            context: Description of what was being processed (e.g., email subject)

        Returns:
            True if LLM should be disabled, False otherwise
        """
        self.stats['failed_calls'] += 1

        error_type, should_disable_immediately = self.classify_error(exception)

        # Track error statistics
        error_name = error_type.value
        self.stats['errors_by_type'][error_name] = self.stats['errors_by_type'].get(error_name, 0) + 1

        if error_type == LLMErrorType.NETWORK_UNREACHABLE:
            self.circuit_breaker['network_failures'] += 1
            logger.error(f"🔌 LLM network unreachable: {exception}")
            logger.warning("💡 Tip: Check if LLM endpoint is accessible on your current network")

            if self.circuit_breaker['network_failures'] >= self.network_failure_threshold:
                self.circuit_breaker['is_open'] = True
                self.circuit_breaker['open_reason'] = 'Network unreachable'
                logger.error(f"❌ Network unreachable after {self.network_failure_threshold} attempts. Disabling LLM.")
                return True

        elif error_type == LLMErrorType.AUTH_FAILED:
            logger.error(f"🔐 LLM authentication failed: {exception}")
            logger.error("💡 Check your API key in settings or environment variables (LLM_API_KEY)")
            self.circuit_breaker['is_open'] = True
            self.circuit_breaker['open_reason'] = 'Authentication failed'
            return True

        elif error_type == LLMErrorType.RATE_LIMITED:
            self.rate_limit_backoff = min(self.rate_limit_backoff * 2, self.max_backoff)
            logger.warning(f"⏱️  Rate limited. Waiting {self.rate_limit_backoff:.1f}s before retry...")
            time.sleep(self.rate_limit_backoff)
            return False  # Don't disable, just slow down

        elif error_type == LLMErrorType.SERVER_ERROR:
            self.circuit_breaker['server_errors'] += 1
            logger.warning(f"⚠️  LLM server error (likely temporary): {exception}")

            # Only disable after many server errors
            if self.circuit_breaker['server_errors'] >= self.server_error_threshold:
                self.circuit_breaker['is_open'] = True
                self.circuit_breaker['open_reason'] = 'Server errors'
                logger.error(f"❌ LLM server appears down after {self.server_error_threshold} errors. Disabling AI features.")
                return True

            # Brief backoff for server errors
            time.sleep(min(2 ** min(self.circuit_breaker['server_errors'], 5), 30))
            return False

        elif error_type == LLMErrorType.TIMEOUT:
            self.circuit_breaker['timeouts'] += 1
            logger.warning(f"⏰ LLM request timeout for '{context}'")

            # Disable after consecutive timeouts
            if self.circuit_breaker['timeouts'] >= self.timeout_threshold:
                self.circuit_breaker['is_open'] = True
                self.circuit_breaker['open_reason'] = 'Connection timeouts'
                logger.error(f"❌ LLM connection unstable after {self.timeout_threshold} timeouts. Disabling AI features.")
                return True
            return False

        elif error_type == LLMErrorType.PARSE_ERROR:
            logger.warning(f"📄 LLM returned invalid response for '{context}'")
            # Don't count toward circuit breaker - LLM is working
            return False

        elif error_type == LLMErrorType.MODEL_ERROR:
            logger.error(f"🤖 LLM model/request error: {exception}")
            logger.error("💡 Check model name and parameters in config/settings")
            self.circuit_breaker['is_open'] = True
            self.circuit_breaker['open_reason'] = 'Model configuration error'
            return True

        elif error_type == LLMErrorType.CONTENT_FILTER:
            logger.warning(f"🚫 Content filtered for '{context}': {exception}")
            return False  # Continue with other emails

        else:
            logger.error(f"❓ Unknown LLM error for '{context}': {exception}")
            return False  # Be conservative, don't disable on unknown errors

        return False

    def record_success(self):
        """Record a successful LLM call."""
        self.stats['successful_calls'] += 1

        # Reset failure counters on success
        self.circuit_breaker['network_failures'] = 0
        self.circuit_breaker['server_errors'] = 0
        self.circuit_breaker['timeouts'] = 0
        self.rate_limit_backoff = 1.0

        # Don't auto-close circuit breaker - some errors are permanent

    def record_attempt(self):
        """Record an LLM call attempt."""
        self.stats['total_calls'] += 1

    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open (LLM disabled)."""
        return self.circuit_breaker['is_open']

    def get_stats_summary(self) -> dict:
        """Get summary statistics for reporting."""
        total = self.stats['total_calls']
        success = self.stats['successful_calls']
        failed = self.stats['failed_calls']

        return {
            'total_calls': total,
            'successful_calls': success,
            'failed_calls': failed,
            'success_rate': (success / total * 100) if total > 0 else 0,
            'errors_by_type': self.stats['errors_by_type'],
            'circuit_breaker_status': 'OPEN' if self.circuit_breaker['is_open'] else 'CLOSED',
            'circuit_open_reason': self.circuit_breaker.get('open_reason', 'N/A')
        }

    def format_stats_summary(self) -> str:
        """Format statistics as a human-readable string."""
        stats = self.get_stats_summary()

        if stats['total_calls'] == 0:
            return ""

        lines = []

        if stats['circuit_breaker_status'] == 'OPEN':
            lines.append(f"⚠️  AI Processing: Disabled ({stats['circuit_open_reason']})")
        else:
            lines.append(
                f"AI Processing: {stats['successful_calls']} succeeded, "
                f"{stats['failed_calls']} failed ({stats['success_rate']:.1f}% success rate)"
            )

        if stats['errors_by_type']:
            error_details = ", ".join([f"{k}: {v}" for k, v in stats['errors_by_type'].items()])
            lines.append(f"   Error breakdown: {error_details}")

        return "\n".join(lines)
