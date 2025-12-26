# CRM Automator User Guide

**AI-Powered Email Processing for RealTimeX CRM**

Version 1.5.1

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

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

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

**Benefits:**
- ⚡ 10-100x faster than pip
- 🔒 Automatic virtual environment management
- 📦 No manual dependency installation
- 🚀 Run directly from GitHub

### Option 2: Traditional pip Install

```bash
cd crm-automator
pip install -r requirements.txt

# Run
python3 eml/eml_automator.py email.eml --env-file .env
```

### Option 3: Package Install (Editable)

```bash
pip install -e .
eml-automator email.eml --env-file .env
```

### Dependencies

- Python 3.10+
- OpenAI-compatible LLM API
- RealTimeX CRM API access

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

# Optional: Search Providers (for company enrichment)
SEARCH_PROVIDERS=duckduckgo,serper,serpapi
SERPER_API_KEY=your_serper_key  # Optional
SERPAPI_KEY=your_serpapi_key    # Optional

# Optional: Persistence
PERSISTENCE_DB_PATH=./eml_processing.db
```

### API Scopes Required

Your CRM API key needs these scopes:
- `contacts:write` - Create/update contacts
- `companies:write` - Create/update companies
- `activities:write` - Create notes
- `tasks:write` - Create tasks
- `deals:write` - Create deals

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
  --api-key KEY         Override CRM_API_KEY
  --base-url URL        Override CRM_API_BASE_URL
  --llm-url URL         Override LLM_BASE_URL
  --llm-model MODEL     Override LLM_MODEL
```

### Examples

**Process a single email:**
```bash
python3 eml/eml_automator.py inbox/meeting-request.eml
```

**Force reprocess (bypass deduplication):**
```bash
python3 eml/eml_automator.py email.eml --force
```

**Debug mode:**
```bash
python3 eml/eml_automator.py email.eml --verbose
```

**Custom LLM:**
```bash
python3 eml/eml_automator.py email.eml \
  --llm-url https://api.openai.com/v1 \
  --llm-model gpt-4
```

---

## Features

### 📧 Multi-Contact Notes

**All email participants get activity logs**, not just the sender.

- **Sender**: "📧 Email Sent" note
- **Recipients**: "📨 Email Received" note
- **Company**: Optional company-level note

**Benefits:**
- Complete interaction history
- Team visibility
- Accurate relationship tracking

### 📎 Smart Attachments

**One upload, multiple references** for storage efficiency.

- EML file uploaded once
- URL reused across all notes
- ~67% storage savings

### ⏰ Accurate Timestamps

Notes use the **email's Date header**, not processing time.

- Chronological accuracy
- Proper timeline tracking
- Historical context preserved

### 🤖 AI-Powered Extraction

**Structured data from unstructured emails:**

- **Contacts**: Name, email, title, company, LinkedIn
- **Companies**: Name, industry, size, revenue, website
- **Sentiment**: Positive, Neutral, Negative
- **Intent**: Sales, Demo, Support, Other
- **Tasks**: Auto-generated follow-ups with due dates
- **Deals**: Opportunity detection and creation

### 🔍 Company Enrichment

**Multi-source data gathering:**

1. **Website Scraping** (Primary)
   - Crawls homepage, /about, /contact
   - Extracts rich company details
   - Uses Crawl4AI for clean markdown

2. **Search Fallback** (Secondary)
   - DuckDuckGo (free)
   - Serper.dev (paid, better B2B data)
   - SerpAPI (paid, alternative)

### 🎯 Enum Validation

**Standardized field values** for data consistency:

- **Lifecycle Stages**: prospect, customer, churned, lost, archived
- **Company Types**: customer, prospect, partner, vendor, competitor, internal
- **Industries**: SaaS, E-commerce, Healthcare, Fintech, Manufacturing, etc.
- **Qualification**: qualified, unqualified, duplicate, spam, test

### 🔄 Deduplication

**Prevents duplicate processing:**

- Tracks processed emails by Message-ID
- SQLite persistence layer
- Use `--force` to override

---

## Advanced Topics

### Batch Processing

Process multiple emails:

```bash
for eml in inbox/*.eml; do
  python3 eml/eml_automator.py "$eml" --env-file .env
done
```

### Custom LLM Models

**Local Models** (LM Studio, Ollama):
```bash
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=qwen/qwen3-4b-2507
```

**OpenAI:**
```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4
```

**Anthropic Claude:**
```bash
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-3-sonnet-20240229
```

### Search Provider Configuration

**Free Only:**
```bash
SEARCH_PROVIDERS=duckduckgo
```

**Paid Priority:**
```bash
SEARCH_PROVIDERS=serper,duckduckgo
SERPER_API_KEY=your_key
```

**Disable Search (Website Only):**
```bash
SEARCH_PROVIDERS=
```

### Integration with Email Clients

**Gmail (via IMAP):**
```python
import imaplib
import email

mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login('user@gmail.com', 'password')
mail.select('inbox')

_, data = mail.search(None, 'UNSEEN')
for num in data[0].split():
    _, msg_data = mail.fetch(num, '(RFC822)')
    with open(f'email_{num}.eml', 'wb') as f:
        f.write(msg_data[0][1])
```

**Outlook (via .msg to .eml conversion):**
```bash
# Install msgconvert
sudo apt-get install libemail-outlook-message-perl

# Convert
msgconvert email.msg
python3 eml/eml_automator.py email.eml
```

---

## Troubleshooting

### Common Issues

**❌ "CRM_API_KEY not set"**
```bash
# Solution: Check .env file exists and is loaded
cat .env | grep CRM_API_KEY
python3 eml/eml_automator.py email.eml --env-file .env
```

**❌ "LLM Analysis Error: 400"**
```bash
# Solution: Email too long for model context
# Use a larger context model or shorter emails
LLM_MODEL=gpt-4-turbo  # 128K context
```

**❌ "Attachment icon shows but not clickable"**
```bash
# Solution: Fixed in v1.5.1
# Ensure you're using latest version
git pull origin main
```

**❌ "Contact created but no note"**
```bash
# Solution: Check API key has activities:write scope
# Verify in CRM settings
```

**❌ "Company enrichment not working"**
```bash
# Solution: Check search provider configuration
SEARCH_PROVIDERS=duckduckgo  # Ensure at least one provider
```

### Debug Mode

Enable verbose logging:

```bash
python3 eml/eml_automator.py email.eml --verbose
```

Check logs for:
- API request/response details
- LLM extraction results
- Search provider attempts
- Attachment upload status

### Performance Tips

**Faster Processing:**
- Use local LLM (LM Studio) instead of API calls
- Reduce `max_chars` in `_smart_clean()` for shorter prompts
- Disable company enrichment if not needed

**Better Accuracy:**
- Use GPT-4 or Claude for complex emails
- Enable all search providers for company data
- Increase LLM temperature for creative task generation

---

## Support

**Documentation:**
- [API Reference](../dev-docs/API.md)
- [Database Schema](../dev-docs/table-definition.md)
- [Agent Integration](agent_sync_example.md)

**Issues:**
- GitHub: https://github.com/therealtimex/crm-automator/issues

**Version:** 1.5.1  
**Last Updated:** 2025-12-26
