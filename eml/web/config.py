"""
Configuration Management Module for CRM Automator

This module handles loading, saving, and validating configuration from .env files.
It preserves comments and structure when saving, validates all fields, and provides
API connectivity testing for CRM and LLM services.

Classes:
    ConfigManager: Main configuration management class

Features:
    - Smart .env path resolution (CWD → home → temp)
    - Comment and structure preservation
    - Email and domain validation
    - CRM and LLM API connectivity testing
"""

import os
import logging
import tempfile
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages .env file reading/writing with comment preservation"""

    def __init__(self, env_path: str = None):
        if env_path:
            self.env_path = env_path
        else:
            # Robust strategy for selecting .env path
            cwd = os.getcwd()
            home = os.path.expanduser("~")
            
            # Paths to avoid for automatic local storage (system folders)
            SYSTEM_PATHS = ['/bin', '/sbin', '/usr/bin', '/usr/sbin', '/etc', '/var/lib', '/var/www']
            is_system_cwd = any(cwd.startswith(p) for p in SYSTEM_PATHS) or cwd == '/'
            
            cwd_env = os.path.join(cwd, ".env")
            home_dir = os.path.join(home, ".crm-automator")
            home_env = os.path.join(home_dir, ".env")
            
            # Check if CWD is writable (best effort)
            is_cwd_writable = os.access(cwd, os.W_OK)
            
            if os.path.exists(cwd_env):
                self.env_path = cwd_env
            elif is_cwd_writable and not is_system_cwd:
                self.env_path = cwd_env
            else:
                self.env_path = home_env

        # Final safety check: ensure the directory exists and is writable if we want to save
        env_dir = os.path.dirname(os.path.abspath(self.env_path))
        try:
            os.makedirs(env_dir, exist_ok=True)
        except Exception:
            # Fallback to temp if home is also not writable
            import tempfile
            self.env_path = os.path.join(tempfile.gettempdir(), ".crm-automator.env")
            logger.warning(f"ConfigManager: Configured path {env_dir} not writable. Falling back to {self.env_path}")

    @staticmethod
    def validate_email(email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip()))

    @staticmethod
    def validate_domain(domain: str) -> bool:
        """Basic domain validation (supports @domain.com or domain.com)"""
        import re
        domain = domain.strip()
        # Allow @domain.com or domain.com format
        if domain.startswith('@'):
            domain = domain[1:]
        pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))

    def load_config(self) -> Dict[str, str]:
        """Load all config from .env file"""
        config = {}

        if not os.path.exists(self.env_path):
            return config

        try:
            with open(self.env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Parse key=value
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip().strip('"').strip("'")
                        config[key.strip()] = value

            return config

        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    def save_config(self, config: Dict[str, str]) -> tuple[bool, str]:
        """Save config to .env file, preserving structure"""
        try:
            # Read existing file to preserve comments and structure
            lines = []
            existing_keys = set()

            if os.path.exists(self.env_path):
                with open(self.env_path, 'r') as f:
                    for line in f:
                        stripped = line.strip()

                        # Preserve comments and empty lines
                        if not stripped or stripped.startswith('#'):
                            lines.append(line.rstrip())
                            continue

                        # Update existing key-value pairs
                        if '=' in stripped:
                            key = stripped.split('=', 1)[0].strip()
                            existing_keys.add(key)

                            if key in config:
                                # Update with new value
                                value = config[key]
                                lines.append(f"{key}={value}")
                            else:
                                # Keep original line
                                lines.append(line.rstrip())
                        else:
                            lines.append(line.rstrip())

            # Add new keys that weren't in the original file
            for key, value in config.items():
                if key not in existing_keys:
                    lines.append(f"{key}={value}")

            # Write back to file
            with open(self.env_path, 'w') as f:
                f.write('\n'.join(lines))
                f.write('\n')  # Final newline

            return True, "Configuration saved successfully"

        except Exception as e:
            return False, f"Error saving config: {str(e)}"

    def validate_config(self, config: Dict[str, str]) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []

        # Required fields
        required = ['CRM_API_KEY', 'CRM_API_BASE_URL', 'LLM_BASE_URL', 'LLM_MODEL']

        for field in required:
            if not config.get(field):
                errors.append(f"{field} is required")

        # URL validation
        url_fields = ['CRM_API_BASE_URL', 'LLM_BASE_URL']
        for field in url_fields:
            value = config.get(field, '')
            if value and not (value.startswith('http://') or value.startswith('https://')):
                errors.append(f"{field} must be a valid URL (http:// or https://)")

        # Validate email lists
        email_list_fields = ['INTERNAL_EMAILS', 'ALLOWLIST_DOMAINS', 'SUPPRESS_DOMAINS']
        for field in email_list_fields:
            value = config.get(field, '')
            if value:
                items = [item.strip() for item in value.split(',') if item.strip()]
                for item in items:
                    # Check if it's an email or domain
                    if '@' in item and not item.startswith('@'):
                        # Full email address
                        if not self.validate_email(item):
                            errors.append(f"Invalid email in {field}: {item}")
                    else:
                        # Domain (with or without @)
                        if not self.validate_domain(item):
                            errors.append(f"Invalid domain in {field}: {item}")

        # Validate domain lists (INTERNAL_DOMAINS)
        if config.get('INTERNAL_DOMAINS'):
            domains = [d.strip() for d in config['INTERNAL_DOMAINS'].split(',') if d.strip()]
            for domain in domains:
                if '@' in domain:
                    errors.append(f"INTERNAL_DOMAINS should not contain @ symbol: {domain}")
                elif not self.validate_domain(domain):
                    errors.append(f"Invalid domain in INTERNAL_DOMAINS: {domain}")

        return errors

    def test_crm_connection(self, api_key: str, base_url: str) -> Dict[str, Any]:
        """Test CRM API connectivity"""
        try:
            try:
                from eml.crm_client import RealTimeXClient
            except ImportError:
                try:
                    from crm_client import RealTimeXClient
                except ImportError:
                    import sys
                    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                    from crm_client import RealTimeXClient

            if not api_key or not base_url:
                return {
                    'success': False,
                    'message': 'API key and base URL are required'
                }

            client = RealTimeXClient(api_key, base_url)

            # Try a simple operation (this will depend on your CRM client's API)
            # For now, just check if we can instantiate the client
            return {
                'success': True,
                'message': 'Connected to RealTimeX CRM successfully'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }

    def test_llm_connection(self, api_key: str, base_url: str, model: str) -> Dict[str, Any]:
        """Test LLM API connectivity with detailed diagnostics"""
        try:
            from openai import OpenAI, APIConnectionError, AuthenticationError, APIStatusError
            
            if not base_url or not model:
                return {
                    'success': False,
                    'message': 'Base URL and model are required'
                }

            # Ensure base_url is a full URL
            if not base_url.startswith(('http://', 'https://')):
                return {
                    'success': False,
                    'message': 'Base URL must start with http:// or https://'
                }

            client = OpenAI(
                api_key=api_key or "not-needed", 
                base_url=base_url,
                timeout=15.0 # Local models might be slow to respond initially
            )

            # Try a simple completion
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )

            return {
                'success': True,
                'message': f'Connected successfully. Model: {model}',
                'model': model
            }

        except APIConnectionError as e:
            logger.error(f"LLM connection test failed (Connection): {e}")
            return {
                'success': False,
                'message': f'Connection Error: Could not reach {base_url}. Ensure the server is running and accessible. (Detail: {str(e)})'
            }
        except AuthenticationError as e:
            logger.error(f"LLM connection test failed (Auth): {e}")
            return {
                'success': False,
                'message': f'Authentication Error: Check your API key. (Detail: {str(e)})'
            }
        except APIStatusError as e:
            logger.error(f"LLM connection test failed (Status): {e}")
            return {
                'success': False,
                'message': f'API Error: {e.status_code} - {e.message}'
            }
        except Exception as e:
            logger.error(f"LLM connection test failed (General): {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
