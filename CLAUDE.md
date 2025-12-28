# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CRM Automator is a modular, agentic toolkit that transforms unstructured data (emails, transcripts, documents) into structured CRM records. It's built with a tool-based architecture where components can be imported by AI agents or run as standalone pipelines.

## Development Commands

### Installation
```bash
pip install -r requirements.txt
# or for editable install with dev tools:
pip install -e ".[dev]"
```

### Process an Email
```bash
# Basic usage
python3 eml/eml_automator.py "path/to/email.eml" --env-file ".env"

# Force re-processing (ignores persistence layer)
python3 eml/eml_automator.py "path/to/email.eml" --env-file ".env" --force

# Verbose mode (shows HTTP requests and LLM reasoning)
python3 eml/eml_automator.py "path/to/email.eml" --env-file ".env" --verbose

# Using the installed script
eml-automator "path/to/email.eml" --env-file ".env"
```

### Run Generic Agent Demo
```bash
python3 eml/agent_demo.py --api-key "your_key"
```

### Testing
There are debug scripts in `eml/test-run/` for testing specific features:
- `debug_attachment.py` - Test attachment handling
- `debug_activity.py` - Test activity logging
- `debug_multipart.py` - Test multipart email parsing
- `debug_upload.py` - Test file uploads

### Code Quality
```bash
# Format code
black eml/

# Lint code
ruff check eml/
```

## Architecture

The system follows a modular three-layer architecture:

### 1. Ingestion Layer
- **`eml_automator.py`** (`EMLProcessor` class): Parses `.eml` files, extracts headers, cleans HTML bodies, and manages the full email processing pipeline
- **Future**: Can extend to PDF, Audio, Excel processors
- Each ingestor composes the core tools rather than reimplementing them

### 2. Intelligence & State Layer
- **`intelligence.py`** (`IntelligenceLayer` class): The semantic extraction engine
  - Uses `instructor` library with OpenAI-compatible LLMs (supports local models via LM Studio/Ollama)
  - Extracts structured data from unstructured text into Pydantic models
  - Implements "Opportunistic Search" - if company details are sparse, triggers web search for enrichment
  - Grounds relative dates (e.g., "next Tuesday") to ISO format using context dates
  - Uses `Mode.MD_JSON` for high compatibility with local LLMs

- **`persistence.py`** (`PersistenceLayer` class): SQLite-based state tracking
  - Prevents duplicate processing across runs using `resource_id` (e.g., email `Message-ID`)
  - Database path controlled by `PERSISTENCE_DB_PATH` env var (defaults to `eml_processing.db` in CWD)
  - Implements idempotent `is_already_processed()` and `mark_as_processed()` operations

### 3. CRM Integration Layer
- **`crm_client.py`** (`RealTimeXClient` class): Stateless CRM API client
  - Implements "Search-before-Update" pattern for idempotent operations
  - Key methods: `upsert_contact()`, `upsert_company()`, `log_activity()`, `create_task()`, `create_deal()`
  - All requests have 10s timeout policy
  - Filters public domains (gmail.com, outlook.com, etc.) to prevent noise in company records

## Data Flow & Deduplication Strategy

The system employs three levels of deduplication:

1. **Persistence Layer** (cross-run): SQLite tracks `resource_id` to prevent reprocessing the same email
2. **Discovery Layer** (CRM-level): Search before create/update using unique identifiers:
   - Contacts: Search by email
   - Companies: Dual-search by website domain AND name
3. **Optimization Layer** (intra-run): In-memory caching of `domain -> company_id` and `email -> contact_id` mappings to reduce API calls when processing emails with many CC'd participants

## Key Pydantic Models

Located in `intelligence.py`:
- **`Contact`**: Email, first_name, last_name, title, background, linkedin_url, status
- **`CompanyDetails`**: Sector, size, revenue, website, address fields, name, search query hint
- **`ExtractedTask`**: Description, due_date (ISO format), priority
- **`DealInfo`**: Suggested name, amount, stage
- **`SenderInfo`**: Links Contact + CompanyDetails for the email sender
- **`AnalysisResult`**: Top-level extraction container with summary, sentiment, intent, sender_info, company_details, suggested_tasks, deal_info

## Configuration

The `.env` file controls all runtime behavior:

```bash
# CRM API Configuration
CRM_API_BASE_URL=https://project.supabase.co/functions/v1
CRM_API_KEY=ak_live_...

# LLM Configuration (OpenAI-compatible)
LLM_BASE_URL=http://localhost:1234/v1  # or https://api.openai.com/v1
LLM_API_KEY=not-needed  # or sk-...
LLM_MODEL=qwen/qwen3-4b-2507  # or gpt-4, claude-3-5-sonnet, etc.

# Search Provider (comma-separated priority list)
SEARCH_PROVIDERS=duckduckgo,serper,serpapi
# SERPER_API_KEY=...  # Optional paid search
# SERPAPI_KEY=...     # Optional paid search

# Internal Staff Filtering
INTERNAL_DOMAINS=yourcompany.com,partner.vn
INTERNAL_EMAILS=sales.manager@gmail.com,support@outlook.com

# Database Path (optional, defaults to eml_processing.db in CWD)
# PERSISTENCE_DB_PATH=/custom/path/to/db.sqlite
```

### Internal Staff Filtering

The system filters internal staff from CRM sync to avoid cluttering the database:
- **`INTERNAL_DOMAINS`**: Company domains (e.g., "yourcompany.com")
- **`INTERNAL_EMAILS`**: Specific emails for staff using public domains (e.g., "admin@gmail.com")

Filtering logic in `eml_automator.py:155-162` checks both domain and email against these lists. Internal contacts are labeled but not synced as external contacts.

## Email Processing Pipeline

1. **Parse EML**: Extract headers (Subject, From, To, Cc, Date, Message-ID) and body
2. **Clean Body**:
   - Strip HTML noise, convert to Markdown
   - Remove email signatures and quoted replies using `email-reply-parser`
   - Resolve tracking links (Proofpoint, Safelinks, HubSpot redirects)
3. **Check Persistence**: Skip if `Message-ID` already processed (unless `--force`)
4. **LLM Analysis**: Extract structured data via `IntelligenceLayer.analyze()`
5. **Web Search** (if needed): Enrich sparse company data
6. **Relationship Resolution**: Create/update in order: Company → Contact → Activity → Deal
7. **Mark Processed**: Record `Message-ID` in SQLite

## EESA (Email-to-EML Secure Archiver) Integration

EML files downloaded by the [Email-to-EML Secure Archiver (EESA)](https://github.com/therealtimex/email-archiver) app include pre-processed metadata as custom email headers. This metadata can be used to optimize processing or skip redundant LLM analysis.

### EESA Custom Headers

EESA adds the following `X-EESA-*` headers to `.eml` files:

**`X-EESA-Category`**: Email classification category (e.g., `newsletter`, `transactional`, `sales`, `support`)

**`X-EESA-Summary`**: Plain text summary of the email content

**`X-EESA-Processed-At`**: RFC 2822 timestamp when EESA processed the email

**`X-EESA-Raw-JSON`**: Base64-encoded JSON containing detailed metadata with the following structure:
- `classification`: Category, confidence score, reasoning, importance flag, and tags
- `extraction`: Summary, entities (organizations/people/dates/monetary values), structured data, action items
- `internal_metadata`: Internal date and other archival metadata

### Using EESA Metadata

When processing EESA-enhanced emails, you can:
1. **Skip LLM classification** if `X-EESA-Category` exists and is trusted
2. **Pre-populate summaries** from `X-EESA-Summary` to reduce token usage
3. **Extract entities** from the decoded JSON to avoid redundant entity recognition
4. **Prioritize processing** based on `classification.is_important` flag
5. **Use action items** from `extraction.action_items` for task creation

Example header extraction:
```python
# In eml_automator.py or custom processors
eesa_category = msg.get('X-EESA-Category', None)
eesa_summary = msg.get('X-EESA-Summary', None)
eesa_raw_json = msg.get('X-EESA-Raw-JSON', None)

if eesa_raw_json:
    import base64, json
    eesa_data = json.loads(base64.b64decode(eesa_raw_json))
    # Use eesa_data['classification'], eesa_data['extraction'], etc.
```

## CRM API Integration

The RealTimeX CRM API (documented in `dev-docs/API.md`) uses:
- Bearer token authentication (`Authorization: Bearer ak_live_...`)
- RESTful endpoints at `/api-v1-{contacts,companies,deals,tasks,activities}`
- Search support: `?email=...` for contacts, `?website=...` or `?name=...` for companies
- Rate limit: 100 requests/minute

### Activity vs Task Distinction
- **Activities** (`log_activity()`): Immutable notes/logs attached to contacts, companies, or deals
  - Types: `contact_note`, `company_note`, `deal_note`, `task_note`
  - Supports file attachments via `multipart/form-data` or attachment URLs
- **Tasks** (`create_task()`): Action items with status tracking (todo, in_progress, done, etc.)

## Important Implementation Details

### Public Domain Filtering
`RealTimeXClient.is_public_domain()` checks against hardcoded list: gmail.com, outlook.com, yahoo.com, hotmail.com, icloud.com, me.com, msn.com. Companies with these domains are automatically excluded from creation.

### Date Grounding
The LLM receives the email's `Date` header as context, allowing it to resolve relative dates like "next Tuesday" or "in 2 weeks" to absolute ISO timestamps.

### HTML Cleaning Pipeline
1. BeautifulSoup extracts text from HTML
2. `markdownify` converts to Markdown
3. `email-reply-parser` strips quoted replies
4. Link resolution using `crawl4ai` for tracking redirects

### Search-before-Update Pattern
Every `upsert_*` method:
1. Searches for existing record by unique identifier
2. If found: `PATCH` to update (preserves ID, enriches metadata)
3. If not found: `POST` to create new record
4. Returns the record ID for relationship linking

## Testing & Debugging

The `eml/test-data/` directory contains sample `.eml` files for testing. When testing:
- Use `--verbose` to see LLM reasoning and HTTP request/response details
- Check `eml_processing.db` to verify persistence state
- Use `--force` to reprocess already-synced emails during development
- Debug scripts in `eml/test-run/` demonstrate isolated feature testing

## Extending the System

To add a new ingestion source:
1. Create a new processor class (similar to `EMLProcessor`)
2. Compose `IntelligenceLayer`, `RealTimeXClient`, and `PersistenceLayer`
3. Extract text and context date from your source format
4. Call `intelligence.analyze(text, context_date)` → `AnalysisResult`
5. Use `RealTimeXClient` methods to sync to CRM
6. Mark resource as processed using `PersistenceLayer`

See `eml/agent_demo.py` for a minimal example of generic text ingestion.

## Changelog Maintenance

This project maintains a changelog following [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format with [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### When to Update CHANGELOG.md

Update the changelog for ANY user-facing changes:
- New features or capabilities
- Bug fixes
- Breaking changes
- Deprecations
- Security fixes
- Performance improvements

### Changelog Format

Add entries under the `[Unreleased]` section during development:

```markdown
## [Unreleased]

### Added
- New feature description

### Changed
- Modified behavior description

### Fixed
- Bug fix description

### Removed
- Deprecated feature removal
```

### On Release

When creating a new release:
1. Change `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
2. Update version in `pyproject.toml`
3. Create a new `[Unreleased]` section above it
4. Commit with message: `chore: bump version to X.Y.Z`

### Version Numbering (Semantic Versioning)

- **MAJOR** (X.0.0): Breaking changes to API or behavior
- **MINOR** (0.X.0): New features, backward-compatible
- **PATCH** (0.0.X): Bug fixes, backward-compatible

Examples:
- Adding EESA metadata support → MINOR version bump
- Fixing email parsing bug → PATCH version bump
- Changing `IntelligenceLayer.analyze()` signature → MAJOR version bump
