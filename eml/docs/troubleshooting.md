# Troubleshooting Guide

Common issues and solutions for CRM Automator.

## Installation Issues

### "uv: command not found"

**Problem:** uv is not installed.

**Solution:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart terminal or reload shell
source ~/.bashrc  # or ~/.zshrc
```

### "No module named 'crm_client'"

**Problem:** Dependencies not installed.

**Solution:**
```bash
# Reinstall dependencies
uv sync

# Or with pip
pip install -r requirements.txt
pip install -e ".[dev]"
```

### Import errors with filters module

**Problem:** Filter module not found.

**Solution:**
```bash
# Ensure you're in the right directory
cd eml/

# Test imports
python -c "from filters import EmailFilterOrchestrator; print('✓ Filters working')"
```

## Configuration Issues

### "CRM_API_KEY not set"

**Problem:** Environment variable not configured.

**Solution:**
```bash
# 1. Check if .env exists
ls -la .env

# 2. If not, create from example
cp .env.example .env

# 3. Edit and add your API key
nano .env

# 4. Verify it's set
grep CRM_API_KEY .env

# 5. Test loading
uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('CRM_API_KEY'))"
```

### "LLM_BASE_URL is not set"

**Problem:** LLM endpoint not configured.

**Solution:**

For OpenAI:
```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-key
LLM_MODEL=gpt-4o-mini
```

For local LM Studio:
```bash
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=your-local-model
```

### Environment variables not loading

**Problem:** .env file not being read.

**Solution:**
```bash
# Specify .env file explicitly
uv run python eml/eml_automator.py "emails/" --env-file ".env"

# Check .env syntax (no spaces around =)
# Correct: API_KEY=value
# Wrong: API_KEY = value

# Check file permissions
ls -la .env
chmod 600 .env
```

## Processing Issues

### "Failed to parse email"

**Problem:** Invalid or corrupted EML file.

**Solution:**
```bash
# Check file format
file email.eml

# Should show: "message/rfc822" or "RFC 822 mail"

# Verify file is not empty
ls -lh email.eml

# Try opening with mail client (Thunderbird, etc.)

# Check for binary corruption
head -n 20 email.eml
# Should show readable email headers
```

### "No contacts resolved. Cannot link activities."

**Problem:** All participants are internal or filtering excluded everyone.

**Solution:**
```bash
# 1. Check internal domains config
grep INTERNAL_DOMAINS .env
grep INTERNAL_EMAILS .env

# 2. Verify email has external participants
grep "^From:" email.eml
grep "^To:" email.eml

# 3. Check if filtering suppressed it
sqlite3 eml_processing.db "
SELECT * FROM suppressed_emails
WHERE file_name LIKE '%email-filename.eml%';
"

# 4. Temporarily disable internal filtering
# Comment out in .env:
# INTERNAL_DOMAINS=
# INTERNAL_EMAILS=
```

### "Intelligence layer failed to return analysis"

**Problem:** LLM analysis failed.

**Solution:**
```bash
# 1. Test LLM connection
uv run python -c "
from eml.intelligence import IntelligenceLayer
ai = IntelligenceLayer()
result = ai.client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[{'role': 'user', 'content': 'test'}],
    max_tokens=5
)
print('LLM working:', result.choices[0].message.content)
"

# 2. Check LLM URL is correct
grep LLM_BASE_URL .env

# 3. Verify API key
grep LLM_API_KEY .env

# 4. Check model name
grep LLM_MODEL .env

# 5. Try with verbose logging
uv run python eml/eml_automator.py "email.eml" --verbose
```

### Emails being processed twice

**Problem:** Persistence layer not working.

**Solution:**
```bash
# 1. Check if database exists
ls -la eml_processing.db

# 2. Check database has entries
sqlite3 eml_processing.db "SELECT COUNT(*) FROM processed_emails;"

# 3. Verify Message-ID in email
grep "Message-ID:" email.eml

# 4. Check if --force flag is being used
# Don't use --force unless intentionally reprocessing

# 5. Reset database if corrupted
rm eml_processing.db
```

## Filtering Issues

### Important emails being suppressed

**Problem:** Legitimate emails classified as promotional/spam.

**Solution:**

1. **Check suppression database:**
   ```bash
   sqlite3 eml_processing.db "
   SELECT * FROM suppressed_emails
   WHERE sender LIKE '%client.com%';
   "
   ```

2. **Add to allowlist:**
   ```bash
   # .env
   ALLOWLIST_DOMAINS=@important-client.com,vip@partner.com
   ```

3. **Adjust suppress categories:**
   ```bash
   # Only suppress spam
   SUPPRESS_CATEGORIES=spam
   ```

4. **Use EESA headers to override:**
   ```
   X-EESA-Category: conversation
   ```

5. **Review with verbose logging:**
   ```bash
   uv run python eml/eml_automator.py "email.eml" --verbose
   # Look for filtering decision reasoning
   ```

### Too many promotional emails getting through

**Problem:** Heuristics not catching all promotional emails.

**Solution:**

1. **Switch to LLM classification:**
   ```bash
   CLASSIFICATION_STRATEGY=llm
   ```

2. **Add to blocklist:**
   ```bash
   SUPPRESS_DOMAINS=@marketing.vendor.com,newsletter@company.com
   ```

3. **Expand suppress categories:**
   ```bash
   SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam,notification,transactional
   ```

### LLM classification not working

**Problem:** All emails using heuristics, LLM never called.

**Solution:**
```bash
# 1. Check classification strategy
grep CLASSIFICATION_STRATEGY .env
# Should be "hybrid" or "llm", not "heuristic"

# 2. Verify LLM client configured
uv run python -c "
from eml.eml_automator import EMLProcessor
from eml.intelligence import IntelligenceLayer
from eml.crm_client import RealTimeXClient
from eml.persistence import PersistenceLayer
import os

client = RealTimeXClient(os.getenv('CRM_API_KEY'), os.getenv('CRM_API_BASE_URL'))
ai = IntelligenceLayer()
db = PersistenceLayer()
processor = EMLProcessor(client, ai, db)

print('Filter orchestrator LLM client:', processor.filter_orchestrator.llm_classifier)
# Should not be None
"

# 3. Test with ambiguous email (no clear patterns)
# LLM should be called for emails that heuristics can't classify
```

## CRM Sync Issues

### "Failed to create contact/company"

**Problem:** CRM API error.

**Solution:**
```bash
# 1. Test CRM API directly
uv run python -c "
from eml.crm_client import RealTimeXClient
import os
client = RealTimeXClient(os.getenv('CRM_API_KEY'), os.getenv('CRM_API_BASE_URL'))
result = client.upsert_contact('test@example.com', first_name='Test', last_name='User')
print('Contact created:', result)
"

# 2. Check API key permissions
# Ensure key has write access to contacts, companies, activities

# 3. Verify base URL
grep CRM_API_BASE_URL .env
# Should end with /v1 or /functions/v1

# 4. Check for rate limiting
# Add delays between requests if processing many emails

# 5. Enable verbose logging
uv run python eml/eml_automator.py "email.eml" --verbose
```

### Attachments not uploading

**Problem:** EML file not attached to CRM activities.

**Solution:**
```bash
# 1. Check file exists and is readable
ls -lh email.eml

# 2. Verify file size (some CRMs have limits)
du -h email.eml

# 3. Test file upload directly
uv run python eml/test-run/debug_upload.py

# 4. Check CRM storage limits
# Contact RealTimeX support if storage quota exceeded
```

## Performance Issues

### Processing is very slow

**Problem:** Each email takes >10 seconds.

**Solution:**

1. **Use heuristic classification:**
   ```bash
   CLASSIFICATION_STRATEGY=heuristic
   # Skips LLM classification entirely
   ```

2. **Disable web enrichment:**
   ```bash
   # Remove or comment out
   # SEARCH_PROVIDERS=...
   ```

3. **Use faster LLM model:**
   ```bash
   LLM_MODEL=gpt-3.5-turbo  # Faster than gpt-4
   CLASSIFICATION_MODEL=gpt-3.5-turbo
   ```

4. **Process in batches:**
   ```bash
   # Process 100 at a time
   find emails/ -name "*.eml" | head -100 | xargs -I {} uv run python eml/eml_automator.py {}
   ```

5. **Use local LLM:**
   ```bash
   # Ollama or LM Studio (no network latency)
   LLM_BASE_URL=http://localhost:1234/v1
   ```

### High LLM API costs

**Problem:** OpenAI bills are high.

**Solution:**

1. **Use cheaper model:**
   ```bash
   LLM_MODEL=gpt-4o-mini  # ~10x cheaper than gpt-4
   CLASSIFICATION_MODEL=gpt-4o-mini
   ```

2. **Use hybrid classification:**
   ```bash
   CLASSIFICATION_STRATEGY=hybrid
   # Only 10% of emails use LLM
   ```

3. **Aggressive filtering:**
   ```bash
   SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam,notification
   # Reduces emails processed
   ```

4. **Switch to local LLM:**
   ```bash
   # Use Ollama (free, local)
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_MODEL=llama2
   ```

## Database Issues

### "Database is locked"

**Problem:** SQLite database locked by another process.

**Solution:**
```bash
# 1. Check for other running processes
ps aux | grep eml_automator

# 2. Kill stuck processes
pkill -f eml_automator

# 3. Remove lock file
rm eml_processing.db-journal

# 4. If corrupted, reset database
mv eml_processing.db eml_processing.db.backup
# Will be recreated on next run
```

### "Unable to open database file"

**Problem:** Permission or path issue.

**Solution:**
```bash
# 1. Check database path
grep PERSISTENCE_DB_PATH .env

# 2. Ensure directory exists
mkdir -p "$(dirname /path/to/db.sqlite)"

# 3. Check permissions
ls -la eml_processing.db

# 4. Fix permissions
chmod 664 eml_processing.db
```

## Logging Issues

### Logs not being created

**Problem:** Suppressed emails log file empty.

**Solution:**
```bash
# 1. Check if logging enabled
grep LOG_SUPPRESSED .env
# Should be "true"

# 2. Check database exists
ls -lh eml_processing.db

# 3. Verify suppressed_emails table
sqlite3 eml_processing.db ".schema suppressed_emails"

# 4. Check if entries are being logged
sqlite3 eml_processing.db "SELECT COUNT(*) FROM suppressed_emails;"

# 4. Verify permissions
ls -ld logs/
chmod 755 logs/
```

### Too much verbose output

**Problem:** Logs overwhelming console.

**Solution:**
```bash
# Don't use --verbose flag
uv run python eml/eml_automator.py "emails/"

# Or redirect to file
uv run python eml/eml_automator.py "emails/" --verbose > processing.log 2>&1
```

## Common Error Messages

### "ModuleNotFoundError: No module named 'instructor'"

**Solution:**
```bash
uv sync
# or
pip install instructor
```

### "ModuleNotFoundError: No module named 'openai'"

**Solution:**
```bash
pip install openai>=1.0.0
```

### "JSONDecodeError" when parsing EESA headers

**Solution:**
```bash
# Check EESA Raw JSON is valid Base64
uv run python -c "
import base64
import json

# Test encoding/decoding
data = {'test': 'value'}
encoded = base64.b64encode(json.dumps(data).encode()).decode()
decoded = json.loads(base64.b64decode(encoded))
print('Valid:', decoded)
"
```

### "Connection refused" errors

**Solutions:**

For LLM API:
```bash
# If using local LM Studio/Ollama, ensure it's running
# LM Studio: Check server is started on port 1234
# Ollama: ollama serve

# Test connection
curl http://localhost:1234/v1/models
# or
curl http://localhost:11434/api/tags
```

For CRM API:
```bash
# Test CRM endpoint
curl -H "Authorization: Bearer ${CRM_API_KEY}" ${CRM_API_BASE_URL}/health
```

## Getting Help

If you can't resolve the issue:

1. **Check logs with --verbose:**
   ```bash
   uv run python eml/eml_automator.py "email.eml" --verbose 2>&1 | tee debug.log
   ```

2. **Test individual components:**
   ```bash
   # Test filtering
   uv run python eml/test-run/test_filtering.py

   # Test parsing
   uv run python eml/test-run/debug_multipart.py

   # Test CRM upload
   uv run python eml/test-run/debug_upload.py
   ```

3. **Share error details:**
   - Full error message
   - Relevant .env configuration (redact keys!)
   - Sample email (if not confidential)
   - Output of `--verbose` run

4. **Report bugs:**
   - GitHub Issues: [Your repo URL]
   - Include: Python version, uv version, OS

## Next Steps

- **Configuration**: Review all settings - [Configuration Guide](./configuration.md)
- **Email Filtering**: Tune filtering rules - [Email Filtering](./email-filtering.md)
- **Getting Started**: Re-read setup steps - [Getting Started](./getting-started.md)
