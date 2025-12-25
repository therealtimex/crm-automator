# CRM Automation Toolkit: CLI Usage & Examples

This guide covers how to use the modular CRM automation tools from the command line, including environment setup and parameter overrides.

## 1. Environment Setup

The toolkit supports automatic loading of environment variables from a `.env` file located in the project root or the `eml/` directory.

### `.env` Template
Copy `.env.example` to `.env` and fill in your credentials:
```bash
CRM_API_BASE_URL=https://your-project.supabase.co/functions/v1
CRM_API_KEY=your_api_key_here
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=your_llm_api_key_here
LLM_MODEL=qwen/qwen3-4b-2507
```

## 2. EML Processor (`eml_automator.py`)
Processes a single `.eml` file, extracts structured data using an LLM, and syncs it to the CRM.

### Basic Usage
```bash
python3 eml/eml_automator.py "path/to/email.eml"
```

### CLI Parameter Overrides
You can override any environment variable using command-line flags. High priority is given to flags, followed by environment variables, then defaults.

```bash
# Override API Key and Base URL
python3 eml/eml_automator.py "email.eml" --api-key "your_key" --base-url "https://api.rta.vn"

# Use a specific .env file and enable verbose logging
python3 eml/eml_automator.py "email.eml" --env-file ".env.production" --verbose
```

**Supported Flags:**
- `--verbose`, `-v`: Enable verbose logging (DEBUG level)
- `--force`, `-f`: Force reprocessing even if EML was already processed
- `--env-file`: Path to a custom `.env` file to load
- `--api-key`: RealTimeX API Key
- `--base-url`: RealTimeX Base URL
- `--db-path`: Path to SQLite persistence database
- `--llm-url`: LLM Base URL
- `--llm-model`: LLM Model name

---

## 3. Agent Demo (`agent_demo.py`)
Demonstrates how to use the `IntelligenceLayer` and `RealTimeXClient` to ingest arbitrary text (e.g., meeting notes, transcripts).

### Usage
```bash
python3 eml/agent_demo.py --api-key "your_key"
```

---

## 4. Troubleshooting & Logging
The toolkit uses structured logging. To see more or less detail, you can adjust the `logging.basicConfig(level=...)` in the script files (default is `INFO`).

- **Success**: `Successfully finished processing for EML.`
- **Duplicate**: `Skipping already processed email: <Message-ID>`
- **Errors**: Check logs for specific CRM API or LLM error messages.
