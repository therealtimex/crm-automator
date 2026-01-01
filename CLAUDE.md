# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CRM Automator is a modular, agentic toolkit that transforms unstructured data (emails, transcripts, documents) into structured CRM records. It's built with a tool-based architecture where components can be imported by AI agents or run as standalone pipelines.

## Development Commands

### Installation
```bash
# Standard pip
pip install -r requirements.txt
pip install -e ".[dev]"

# Modern uv
uv sync
uv lock
```

### Process Emails
```bash
# Process a single file
uv run python eml/eml_automator.py "path/to/email.eml" --env-file ".env"

# Process a directory recursively (skips non-EML files)
uv run python eml/eml_automator.py "path/to/directory" --env-file ".env"

# Instant tool run (zero-install uvx)
uvx eml/eml_automator.py "path/to/email.eml" --env-file ".env"

# Force re-processing (ignores persistence layer)
uv run python eml/eml_automator.py "path/to/directory" --env-file ".env" --force

# Verbose mode
uv run python eml/eml_automator.py "path/to/directory" --env-file ".env" --verbose

# Show filtering statistics after processing
uv run python eml/eml_automator.py "path/to/directory" --env-file ".env" --show-filter-stats
```

### Run Generic Agent Demo
```bash
uv run python eml/agent_demo.py --api-key "your_key"
```

### Testing & Debugging
There are debug scripts in `eml/test-run/` for testing specific features:
- `debug_attachment.py` - Test attachment handling
- `debug_activity.py` - Test activity logging
- `debug_multipart.py` - Test multipart email parsing
- `debug_upload.py` - Test file uploads
- `test_filtering.py` - Test email filtering system

Run them with: `uv run python eml/test-run/filename.py`

### Code Quality
```bash
# Linting & Formatting
uv run ruff check .
uv run ruff format .
```

## Email Filtering System

CRM Automator includes a hybrid email filtering system to suppress irrelevant emails (promotions, newsletters, automated messages) before CRM processing. This saves API costs and improves data quality.

### How It Works

The system uses a 3-stage approach:

1. **Fast Heuristics** (free, ~90% accuracy)
   - Checks email headers (List-Unsubscribe, Auto-Submitted, etc.)
   - Pattern matching on sender addresses (newsletter@, marketing@, noreply@)
   - Subject line patterns (promotional language, automated replies)

2. **EESA Custom Headers** (pre-classification)
   - Supports X-EESA-Category, X-CRM-Category headers
   - Allows email clients to pre-classify emails
   - Explicit suppress flags (X-CRM-Suppress, X-CRM-Priority)

3. **LLM Classification** (for ambiguous cases only)
   - Only used when heuristics can't decide confidently
   - Uses cheap model (gpt-4o-mini) for cost efficiency
   - Classifies into: conversation, transactional, promotional, newsletter, notification, automated, spam

### Email Categories

- **conversation**: Human-to-human business dialogue (customers, leads, partners) → **PROCESS**
- **transactional**: Receipts, confirmations, password resets → **PROCESS** (unless suppressed)
- **promotional**: Marketing emails, sales pitches → **SUPPRESS** (by default)
- **newsletter**: Regular updates, digests → **SUPPRESS** (by default)
- **notification**: CI/CD alerts, monitoring → **SUPPRESS** (by default)
- **automated**: Auto-replies, out-of-office → **SUPPRESS** (by default)
- **spam**: Unwanted emails → **SUPPRESS** (by default)

### Configuration

Configure filtering in `.env`:

```bash
# Categories to suppress (default: promotional,newsletter,automated,spam)
SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam

# Force-suppress specific domains
SUPPRESS_DOMAINS=@marketing.company.com,noreply@vendor.com

# Force-process VIP domains (override suppressions)
ALLOWLIST_DOMAINS=@important-client.com,vip@partner.com

# Classification strategy: heuristic, llm, or hybrid (default)
CLASSIFICATION_STRATEGY=hybrid

# LLM model for classification (default: gpt-4o-mini)
CLASSIFICATION_MODEL=gpt-4o-mini

# Log suppressed emails to SQLite database (default: true)
LOG_SUPPRESSED=true

# Note: Suppressed emails are stored in SQLite (eml_processing.db)
# Query database: sqlite3 eml_processing.db "SELECT * FROM suppressed_emails"
```

### Using EESA Custom Headers

You can pre-classify emails at the email client level using custom headers:

```
X-EESA-Category: conversation
X-CRM-Category: promotional
X-CRM-Suppress: true
X-CRM-Priority: 0
```

These headers have highest priority and skip heuristics/LLM classification.

### Monitoring & Stats

View filtering statistics:

```bash
uv run python eml/eml_automator.py "path/to/directory" --show-filter-stats
```

Query suppressed emails database:

```bash
# View all suppressed emails
sqlite3 eml_processing.db "SELECT * FROM suppressed_emails;"

# Count by category
sqlite3 eml_processing.db "SELECT category, COUNT(*) FROM suppressed_emails GROUP BY category;"

# Find specific sender
sqlite3 eml_processing.db "SELECT * FROM suppressed_emails WHERE sender LIKE '%example.com%';"
```
