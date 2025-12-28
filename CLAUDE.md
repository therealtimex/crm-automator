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

Run them with: `uv run python eml/test-run/filename.py`

### Code Quality
```bash
# Linting & Formatting
uv run ruff check .
uv run ruff format .
```
