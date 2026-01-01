# Getting Started with CRM Automator

This guide will help you install, configure, and run CRM Automator for the first time.

## Prerequisites

Before you begin, ensure you have:

1. **Python 3.10+** installed
2. **RealTimeX CRM** account and API key
3. **LLM API** access (OpenAI, LM Studio, Ollama, or compatible)
4. **Git** (to clone the repository)

## Installation

### Option 1: Using `uv` (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager.

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/your-org/crm-automator.git
cd crm-automator/eml

# Install dependencies
uv sync

# Lock dependencies
uv lock
```

### Option 2: Using `pip`

```bash
# Clone the repository
git clone https://github.com/your-org/crm-automator.git
cd crm-automator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Configuration

### 1. Create Environment File

Copy the example environment file:

```bash
cp .env.example .env
```

### 2. Configure Required Settings

Edit `.env` and set the following **required** variables:

```bash
# =============================================================================
# CRM API Configuration (Required)
# =============================================================================
CRM_API_BASE_URL=https://your-project.supabase.co/functions/v1
CRM_API_KEY=ak_live_your_api_key_here

# =============================================================================
# LLM Configuration (Required)
# =============================================================================
LLM_BASE_URL=http://localhost:1234/v1  # Or OpenAI endpoint
LLM_API_KEY=your_openai_api_key        # Or "not-needed" for local LLM
LLM_MODEL=gpt-4o-mini                   # Or your local model name
```

### 3. Configure Optional Settings

#### Email Filtering (Recommended)

```bash
# Categories to suppress (default: promotional,newsletter,automated,spam)
SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam

# Classification strategy: heuristic, llm, or hybrid
CLASSIFICATION_STRATEGY=hybrid

# LLM model for classification (cheap/fast model recommended)
CLASSIFICATION_MODEL=gpt-4o-mini
```

#### Internal Staff Filtering

```bash
# Company domains to exclude from CRM sync
INTERNAL_DOMAINS=yourcompany.com,partner.vn

# Specific email addresses to exclude
INTERNAL_EMAILS=admin@gmail.com,support@outlook.com
```

#### Web Enrichment

```bash
# Search providers (comma-separated, in priority order)
SEARCH_PROVIDERS=duckduckgo,serper,serpapi

# Optional: Serper API key for better search results
SERPER_API_KEY=your_serper_key_here

# Optional: SerpAPI key
SERPAPI_KEY=your_serpapi_key_here
```

### 4. Verify Configuration

Test your configuration with a simple import:

```bash
uv run python -c "
from eml.crm_client import RealTimeXClient
from eml.intelligence import IntelligenceLayer
print('✅ Configuration validated successfully')
"
```

## First Run

### Process a Single Email

```bash
# Process a single .eml file
uv run python eml/eml_automator.py "path/to/test-email.eml" --env-file ".env"
```

**What happens:**
1. Email is parsed (headers, body, attachments)
2. Filtering checks if it should be processed
3. LLM analyzes content and extracts data
4. CRM records are created/updated
5. Original EML is attached to activities
6. Processing status is saved

### Process a Directory

```bash
# Process all .eml files in a directory (recursive)
uv run python eml/eml_automator.py "path/to/emails/" --env-file ".env"
```

### Enable Verbose Logging

```bash
# See detailed processing logs
uv run python eml/eml_automator.py "path/to/emails/" --env-file ".env" --verbose
```

### View Filtering Statistics

```bash
# Show what emails were suppressed and why
uv run python eml/eml_automator.py "path/to/emails/" --env-file ".env" --show-filter-stats
```

## Understanding the Output

### Console Output

```
Processing emails: 100%|████████████████| 25/25 [00:45<00:00,  1.80s/email]

INFO - --- Processing Summary ---
INFO - Total Files: 25
INFO - Successfully Processed: 18
INFO - Failed: 0
INFO - Suppressed: 7
INFO - --------------------------
```

### Suppressed Emails

Suppressed emails are logged to `logs/suppressed_emails.jsonl`:

```bash
# View suppressed emails
cat logs/suppressed_emails.jsonl | jq

# Count by category
cat logs/suppressed_emails.jsonl | jq -r '.category' | sort | uniq -c
```

### Processing Database

Processed emails are tracked in `eml_processing.db` (SQLite):

```bash
# View processed emails
sqlite3 eml_processing.db "SELECT * FROM processed_emails LIMIT 5;"
```

## Common Commands

### Force Re-processing

Ignore persistence layer and re-process all emails:

```bash
uv run python eml/eml_automator.py "emails/" --force
```

### Custom Environment File

Use a different `.env` file:

```bash
uv run python eml/eml_automator.py "emails/" --env-file "/path/to/custom.env"
```

### Override Configuration

Override specific settings via CLI:

```bash
uv run python eml/eml_automator.py "emails/" \
  --api-key "ak_live_override_key" \
  --base-url "https://custom-crm.com/v1" \
  --llm-model "gpt-4o"
```

## Testing the Installation

Run the test suite to verify everything works:

```bash
# Test email filtering
uv run python eml/test-run/test_filtering.py

# Test with sample debug scripts
uv run python eml/test-run/debug_activity.py
uv run python eml/test-run/debug_multipart.py
```

## Next Steps

Now that you have CRM Automator running:

1. **Configure Filtering**: See [Email Filtering](./email-filtering.md) to customize which emails get processed
2. **Use EESA Headers**: See [EESA Headers](./eesa-headers.md) to pre-classify emails at the email client level
3. **Optimize LLM Costs**: See [Intelligence Layer](./intelligence-layer.md) for cost optimization tips
4. **Automate Processing**: Set up a cron job or workflow to automatically process incoming emails

## Troubleshooting

### "CRM_API_KEY not set"

Make sure your `.env` file exists and contains `CRM_API_KEY`.

```bash
# Verify .env exists
ls -la .env

# Check if key is set
grep CRM_API_KEY .env
```

### "LLM_BASE_URL is not set"

Configure your LLM endpoint in `.env`:

```bash
# For OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-openai-key

# For local LM Studio
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
```

### "Failed to parse email"

Ensure the file is a valid EML file:

```bash
# Check file format
file path/to/email.eml

# Should output: "message/rfc822" or "text/plain"
```

### Import Errors

Reinstall dependencies:

```bash
# With uv
uv sync --reinstall

# With pip
pip install -r requirements.txt --force-reinstall
```

## Getting Help

- **Documentation**: Browse the [docs folder](./README.md)
- **Examples**: Check `eml/test-run/` for working examples
- **Issues**: Report bugs on GitHub Issues
- **Configuration Reference**: See [Configuration Guide](./configuration.md)
