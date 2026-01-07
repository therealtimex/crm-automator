# CRM Automator User Guide

**AI-Powered Email Processing for RealTimeX CRM**

Version 1.10.0

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Features](#features)
6. [Advanced Topics](#advanced-topics)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

**Fastest way (with uv/uvx):**

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Run (no installation needed!)
uvx --from git+https://github.com/therealtimex/crm-automator eml-automator email.eml --env-file .env
```

**Traditional method:**

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Run
python3 eml/eml_automator.py path/to/email.eml --env-file .env
```

---

### Option 1: uv/uvx (Recommended - Modern Python)

**What is uv/uvx?**  
[uv](https://github.com/astral-sh/uv) is a blazing-fast Python package installer and resolver written in Rust. `uvx` allows running Python applications without installation.

**Install uv:**
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

**Run without installation (uvx):**
```bash
# One-time execution (downloads dependencies automatically)
uvx --from git+https://github.com/therealtimex/crm-automator eml-automator email.eml --env-file .env

# Or if published to PyPI
uvx crm-automator email.eml --env-file .env
```

**Install with uv:**
```bash
# Clone and install
git clone https://github.com/therealtimex/crm-automator.git
cd crm-automator
uv pip install -e .

# Run
eml-automator email.eml --env-file .env
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required: CRM API
CRM_API_BASE_URL=https://your-instance.supabase.co/functions/v1
CRM_API_KEY=ak_live_your_api_key_here

# Required: LLM API
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=qwen/qwen3-4b-2507

# Optional: LLM Parameters (High compatibility for local models)
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.1

# Optional: Search Providers (for company/person enrichment)
SEARCH_PROVIDERS=duckduckgo,serper,serpapi
SERPER_API_KEY=your_serper_key  # Optional
SERPAPI_KEY=your_serpapi_key    # Optional

# Optional: Persistence
PERSISTENCE_DB_PATH=./eml_processing.db

# Optional: Internal Domain/Email Filtering (to skip upserting your own staff)
INTERNAL_DOMAINS=yourcompany.com,partner.vn
INTERNAL_EMAILS=sales.manager@gmail.com,support.temp@outlook.com
```

---

## Usage

### Basic Usage

```bash
python3 eml/eml_automator.py email.eml --env-file .env
```

### Command-Line Options

```bash
python3 eml/eml_automator.py [OPTIONS] <eml_path>

Arguments:
  eml_path              Path to the .eml file to process

Options:
  --env-file PATH       Path to .env file (default: .env)
  --force, -f           Force reprocessing (ignore deduplication)
  --verbose, -v         Enable debug logging
  --dryrun              Simulate processing without modifying CRM
  --api-key KEY         Override CRM_API_KEY
  --base-url URL        Override CRM_API_BASE_URL
  --llm-url URL         Override LLM_BASE_URL
  --llm-model MODEL     Override LLM_MODEL
  --llm-max-tokens N    Override LLM_MAX_TOKENS
  --llm-temperature N   Override LLM_TEMPERATURE
```

---

## Features

### 📧 Multi-Contact Notes

**All email participants get activity logs**, not just the sender.

- **Sender**: "📤 Email from..." note
- **Recipients**: Linked to their respective contacts
- **Company**: Optional company-level activity note

### 👤 Improved Name Parsing

The system uses advanced logic to ensure high-quality contact data:
- **Header Cleaning**: Automatically fixes `"Last, First"` patterns in email headers.
- **Cultural Awareness**: Intelligent handling of three-part names.
- **Title Removal**: Strips professional titles like `Mr.`, `Ms.`, `Dr.`, etc.
- **Reconciliation**: Verified names from email signatures take precedence over header abbreviations.

### 🤖 AI-Powered Extraction

**Structured data from unstructured emails:**

- **Contacts**: Name, email, title, company, LinkedIn
- **Companies**: Name, industry, size, revenue, website
- **Sentiment**: Positive, Neutral, Negative
- **Intent**: Sales, Demo, Support, Other
- **Tasks**: Auto-generated follow-ups with due dates
- **Deals**: Opportunity detection and creation

### 🏢 Internal vs External Contacts

**Avoid CRM pollution from your own team:**

- **Filtering**: Set `INTERNAL_DOMAINS` for company domains and `INTERNAL_EMAILS` for staff members using public domains (e.g., Gmail/Outlook).
- **Smart Labels**: Notes are labeled `📤 Email from Internal Staff` or `📥 Email from External Contact`.
- **Intelligent Linking**: Activities are linked to the most relevant customer contact, regardless of who sent the email.

### 🔍 Company & Person Enrichment

**Multi-source data gathering:**

1. **Active Person Enrichment** (NEW)
   - Searches for LinkedIn profiles and current job titles.
   - Generates professional backgrounds for key contacts.
2. **Website Scraping** (Primary)
   - Crawls homepage, /about, /contact
   - Extracts rich company details
3. **Search Fallback** (Secondary)
   - DuckDuckGo (free)
   - Serper.dev (paid, better B2B data)
   - SerpAPI (paid, alternative)

### 🎯 Enum Validation

**Standardized field values** for data consistency:

- **Lifecycle Stages**: prospect, customer, churned, lost, archived
- **Company Types**: customer, prospect, partner, vendor, competitor, internal
- **Industries**: SaaS, E-commerce, Healthcare, Fintech, Manufacturing, etc.

---

## Advanced Topics

### Batch Processing

Process multiple emails:

```bash
uv run python eml/eml_automator.py "path/to/emails/"
```

### Dry Run Mode

Test your configuration and extraction logic without pushing any data to the CRM:

```bash
python3 eml/eml_automator.py email.eml --dryrun
```
Dry run attempts are logged to the database with a distinct `dryrun` status.

---

## Troubleshooting

### Common Issues

**❌ "TypeError: LLMEmailClassifier.__init__() got unexpected keyword argument 'max_tokens'"**
- **Solution**: Ensure you are running the latest version. This was a known issue in v1.9.x resolved in v1.10.0.

**❌ "Failed to parse LLM response" (Truncated JSON)**
- **Solution**: Increase `LLM_MAX_TOKENS` in your `.env` or use `--llm-max-tokens 4096`. Local models often require higher limits.

**❌ "Hallucinated Company Info" (Wrong Region)**
- **Solution**: The system now uses **Geographic Grounding**. Ensure your email signatures contain address footers or currency symbols to help the AI ground its search queries.

---

**Version:** 1.10.0  
**Last Updated:** 2026-01-06