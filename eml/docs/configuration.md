# Configuration Guide

Complete reference for all CRM Automator configuration options.

## Environment Variables

All configuration is done via environment variables, typically stored in a `.env` file.

### Quick Reference

```bash
# Copy example config
cp .env.example .env

# Edit configuration
nano .env  # or vim, code, etc.
```

## Required Configuration

### CRM API Settings

```bash
# CRM API Base URL (Required)
# Your RealTimeX CRM endpoint
CRM_API_BASE_URL=https://your-project.supabase.co/functions/v1

# CRM API Key (Required)
# Your RealTimeX API key (starts with ak_live_ or ak_test_)
CRM_API_KEY=ak_live_your_api_key_here
```

**How to get:**
1. Log into your RealTimeX CRM dashboard
2. Go to Settings → API Keys
3. Copy the API key and base URL

### LLM Configuration

```bash
# LLM Base URL (Required)
# OpenAI-compatible API endpoint
LLM_BASE_URL=https://api.openai.com/v1

# LLM API Key (Required)
# API key for your LLM provider
LLM_API_KEY=sk-your-openai-api-key

# LLM Model (Required)
# Model name to use for analysis
LLM_MODEL=gpt-4o-mini

# LLM Max Tokens (Optional)
# Maximum tokens for LLM response (default: 4096)
# Increase this for local models like GPT-OSS or Qwen that are verbose
LLM_MAX_TOKENS=4096

# LLM Temperature (Optional)
# Sampling temperature (0.0 - 2.0, default: 0.1)
# Lower for deterministic extraction, higher for creativity
LLM_TEMPERATURE=0.1
```

**Supported Providers:**
- **OpenAI**: `https://api.openai.com/v1`
- **LM Studio**: `http://localhost:1234/v1`
- **Ollama**: `http://localhost:11434/v1`
- **Together AI**: `https://api.together.xyz/v1`
- **Any OpenAI-compatible endpoint**

**Model Recommendations:**
- **Cost-effective**: `gpt-4o-mini`, `gpt-3.5-turbo`
- **High quality**: `gpt-4o`, `gpt-4-turbo`
- **Local**: Any Ollama model (e.g., `llama2`, `mistral`)

## Email Filtering Configuration

### Suppress Categories

```bash
# Categories to suppress (comma-separated)
# Default: promotional,newsletter,automated,spam
SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam
```

**Available Categories:**
- `conversation` - Business dialogue (usually NOT suppressed)
- `transactional` - Receipts, confirmations (usually NOT suppressed)
- `promotional` - Marketing, sales
- `newsletter` - Updates, digests
- `notification` - CI/CD alerts
- `automated` - Auto-replies
- `spam` - Unwanted emails

**Examples:**

```bash
# Suppress only spam
SUPPRESS_CATEGORIES=spam

# Suppress everything except conversations
SUPPRESS_CATEGORIES=transactional,promotional,newsletter,notification,automated,spam

# Suppress promotional and newsletters only
SUPPRESS_CATEGORIES=promotional,newsletter
```

### Domain Filtering

```bash
# Force-suppress specific domains (comma-separated)
# These domains are ALWAYS suppressed, regardless of content
SUPPRESS_DOMAINS=@marketing.company.com,noreply@vendor.com,newsletter@spam.com

# Force-process specific domains (comma-separated)
# These domains are ALWAYS processed, overriding category-based suppression
ALLOWLIST_DOMAINS=@important-client.com,vip@partner.com,ceo@enterprise-customer.com
```

**Supported Formats:**
- Full email: `user@domain.com`
- Domain with @: `@domain.com`
- Domain only: `domain.com`

### Classification Strategy

```bash
# Classification strategy: heuristic, llm, or hybrid
# Default: hybrid (recommended)
CLASSIFICATION_STRATEGY=hybrid
```

**Options:**
- `heuristic` - Fast pattern matching only (free, ~90% accuracy)
- `llm` - Always use LLM (expensive, ~100% accuracy)
- `hybrid` - Heuristics first, LLM for ambiguous cases (recommended)

### Classification Model

```bash
# LLM model for email classification (if using llm/hybrid strategy)
# Default: gpt-4o-mini
# Recommend using a cheap, fast model
CLASSIFICATION_MODEL=gpt-4o-mini
```

**Recommendations:**
- **Best value**: `gpt-4o-mini` ($0.0001/email)
- **Budget**: `gpt-3.5-turbo` ($0.00005/email)
- **Local/Free**: Any Ollama model ($0)

### Suppression Logging

```bash
# Log suppressed emails to database (for audit trail and analytics)
# Suppressed emails are stored in the same SQLite database as processed emails
# Default: true
LOG_SUPPRESSED=true

# Note: Suppressed emails are now stored in SQLite (eml_processing.db)
# Use --show-filter-stats to view suppression statistics
# Query database: sqlite3 eml_processing.db "SELECT * FROM suppressed_emails"
```

## Internal Staff Filtering

Exclude internal emails from CRM sync to avoid polluting your database.

```bash
# Company domains to exclude from CRM sync (comma-separated)
# Example: yourcompany.com,partner.vn
INTERNAL_DOMAINS=yourcompany.com,partner.vn

# Specific email addresses to exclude from CRM sync (comma-separated)
# Use this for staff using public domains like Gmail
# Example: admin@gmail.com,support@outlook.com
INTERNAL_EMAILS=admin@gmail.com,support@outlook.com,ceo@personal-email.com
```

**How it works:**
- Emails from internal domains/addresses are **still processed** (not suppressed)
- But **CRM records are not created** for internal participants
- Activities are still logged for external participants
- Useful for filtering out internal staff from contact lists

## Search Provider Configuration

For company enrichment via web search.

```bash
# Search providers (comma-separated, in priority order)
# Default: duckduckgo,serper,serpapi
SEARCH_PROVIDERS=duckduckgo,serper,serpapi
```

**Available Providers:**
- `duckduckgo` - Free, no API key needed (recommended first choice)
- `serper` - Paid, requires SERPER_API_KEY
- `serpapi` - Paid, requires SERPAPI_KEY

### Serper.dev Configuration

```bash
# Serper.dev API Key (optional)
# Get your key at: https://serper.dev
SERPER_API_KEY=your_serper_key_here
```

**Cost:** ~$0.001 per search

### SerpAPI Configuration

```bash
# SerpAPI Key (optional)
# Get your key at: https://serpapi.com
SERPAPI_KEY=your_serpapi_key_here
```

**Cost:** ~$0.002 per search

## Persistence Configuration

```bash
# Path to SQLite database for tracking processed emails
# Default: eml_processing.db in current working directory
PERSISTENCE_DB_PATH=/custom/path/to/db.sqlite
```

**Purpose:**
- Tracks processed emails by Message-ID
- Prevents duplicate processing
- Use `--force` flag to bypass and reprocess

## Advanced Configuration

### Custom LLM Base URL Examples

```bash
# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-proj-...
LLM_MODEL=gpt-4o-mini

# LM Studio (local)
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=your-local-model-name

# Ollama (local)
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama2

# Together AI
LLM_BASE_URL=https://api.together.xyz/v1
LLM_API_KEY=your-together-key
LLM_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1

# Azure OpenAI
LLM_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment
LLM_API_KEY=your-azure-key
LLM_MODEL=gpt-4
```

## Complete .env Example

```bash
# =============================================================================
# CRM API Configuration (Required)
# =============================================================================
CRM_API_BASE_URL=https://abc123.supabase.co/functions/v1
CRM_API_KEY=ak_live_1234567890abcdef

# =============================================================================
# LLM Configuration (Required)
# =============================================================================
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-proj-abc123xyz
LLM_MODEL=gpt-4o-mini

# =============================================================================
# Email Filtering Configuration (Optional)
# =============================================================================
SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam
SUPPRESS_DOMAINS=@marketing-vendor.com,noreply@ads.com
ALLOWLIST_DOMAINS=@vip-client.com,ceo@enterprise.com
CLASSIFICATION_STRATEGY=hybrid
CLASSIFICATION_MODEL=gpt-4o-mini
LOG_SUPPRESSED=true

# =============================================================================
# Internal Staff Filtering (Optional)
# =============================================================================
INTERNAL_DOMAINS=mycompany.com,partner.co
INTERNAL_EMAILS=admin@gmail.com

# =============================================================================
# Search Provider Configuration (Optional)
# =============================================================================
SEARCH_PROVIDERS=duckduckgo,serper
SERPER_API_KEY=abc123xyz

# =============================================================================
# Persistence Configuration (Optional)
# =============================================================================
PERSISTENCE_DB_PATH=./data/processing.db
```

## CLI Flag Overrides

Environment variables can be overridden via CLI flags:

```bash
# Override CRM API key
uv run python eml/eml_automator.py "emails/" --api-key "ak_live_override"

# Override CRM base URL
uv run python eml/eml_automator.py "emails/" --base-url "https://custom.com/v1"

# Override LLM URL
uv run python eml/eml_automator.py "emails/" --llm-url "http://localhost:1234/v1"

# Override LLM model
uv run python eml/eml_automator.py "emails/" --llm-model "gpt-4o"

# Override persistence DB path
uv run python eml/eml_automator.py "emails/" --db-path "/tmp/custom.db"

# Perform a dry run (no CRM changes)
uv run python eml/eml_automator.py "emails/" --dryrun

# Use custom .env file
uv run python eml/eml_automator.py "emails/" --env-file "/path/to/custom.env"
```

## Configuration Validation

### Test CRM Connection

```bash
uv run python -c "
from eml.crm_client import RealTimeXClient
import os
client = RealTimeXClient(os.getenv('CRM_API_KEY'), os.getenv('CRM_API_BASE_URL'))
print('✅ CRM connection successful')
"
```

### Test LLM Connection

```bash
uv run python -c "
from eml.intelligence import IntelligenceLayer
import os
ai = IntelligenceLayer()
result = ai.client.chat.completions.create(
    model=os.getenv('LLM_MODEL'),
    messages=[{'role': 'user', 'content': 'Hi'}],
    max_tokens=5
)
print('✅ LLM connection successful:', result.choices[0].message.content)
"
```

### Validate All Settings

```bash
uv run python -c "
import os
from dotenv import load_dotenv

load_dotenv()

required = ['CRM_API_KEY', 'CRM_API_BASE_URL', 'LLM_BASE_URL', 'LLM_MODEL']
missing = [var for var in required if not os.getenv(var)]

if missing:
    print(f'❌ Missing required variables: {missing}')
else:
    print('✅ All required variables set')

# Check optional
optional = ['SUPPRESS_CATEGORIES', 'CLASSIFICATION_STRATEGY', 'INTERNAL_DOMAINS']
for var in optional:
    value = os.getenv(var)
    print(f'{var}: {value if value else \"(not set, using default)\"}')
"
```

## Environment-Specific Configurations

### Development

```bash
# .env.dev
CRM_API_KEY=ak_test_dev_key
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=local-model
CLASSIFICATION_STRATEGY=heuristic  # Skip LLM costs
LOG_SUPPRESSED=true
```

```bash
# Use dev config
uv run python eml/eml_automator.py "emails/" --env-file ".env.dev"
```

### Production

```bash
# .env.prod
CRM_API_KEY=ak_live_prod_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-proj-prod-key
LLM_MODEL=gpt-4o-mini
CLASSIFICATION_STRATEGY=hybrid
SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam
ALLOWLIST_DOMAINS=@vip-client.com
LOG_SUPPRESSED=true
```

### Testing

```bash
# .env.test
CRM_API_KEY=ak_test_key
LLM_BASE_URL=http://localhost:1234/v1
CLASSIFICATION_STRATEGY=heuristic
SUPPRESS_CATEGORIES=  # Don't suppress anything in tests
PERSISTENCE_DB_PATH=/tmp/test_processing.db
```

## Security Best Practices

1. **Never commit `.env` files to git**
   ```bash
   echo ".env" >> .gitignore
   echo ".env.*" >> .gitignore
   ```

2. **Use different API keys for dev/prod**
3. **Rotate API keys regularly**
4. **Use environment variables in CI/CD** instead of .env files
5. **Restrict file permissions**
   ```bash
   chmod 600 .env
   ```

## Troubleshooting

### "Environment variable not set" errors

```bash
# Check if .env file exists
ls -la .env

# Check if variable is in .env
grep VARIABLE_NAME .env

# Load and print all vars
uv run python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print(dict(os.environ))
"
```

### Variables not loading

1. **Check .env location**: Must be in current directory or explicitly specified
2. **Check syntax**: No spaces around `=`
   ```bash
   # Correct
   API_KEY=value

   # Wrong
   API_KEY = value
   ```
3. **Check for quotes**: Usually not needed unless value has spaces
   ```bash
   # Usually fine
   API_KEY=abc123

   # Needed for spaces
   BASE_URL="https://example.com/v1"
   ```

## Next Steps

- **Getting Started**: Complete setup guide - [Getting Started](./getting-started.md)
- **Email Filtering**: Configure filtering - [Email Filtering](./email-filtering.md)
- **EESA Headers**: Use custom headers - [EESA Headers](./eesa-headers.md)
