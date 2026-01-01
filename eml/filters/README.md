# Email Filtering System

Hybrid email filtering system for CRM Automator that suppresses irrelevant emails before CRM processing.

## Architecture

The filtering system uses a multi-stage approach to classify emails efficiently:

```
┌─────────────────────────────────────────────────────────────┐
│                    Email Input (EML file)                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Allowlist Check (Force Process)                  │
│  - VIP clients, important partners                          │
│  - Configured via ALLOWLIST_DOMAINS                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: Blocklist Check (Force Suppress)                 │
│  - Known spam domains, unwanted senders                     │
│  - Configured via SUPPRESS_DOMAINS                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: EESA Custom Headers                               │
│  - X-EESA-Category, X-CRM-Category                         │
│  - Pre-classification at email client level                 │
│  - Highest priority if present                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 4: Fast Heuristics (90% coverage, free)             │
│  - Newsletter headers (List-Unsubscribe, etc.)             │
│  - Sender patterns (marketing@, noreply@)                   │
│  - Subject patterns (promotional language)                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 5: LLM Classification (ambiguous cases only)        │
│  - Uses gpt-4o-mini for cost efficiency                    │
│  - Only called when heuristics return None                  │
│  - Classifies into 7 categories                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Decision Made   │
                    └─────────────────┘
                       /           \
                      /             \
              PROCESS              SUPPRESS
                 ↓                     ↓
        Continue to CRM          Log & Skip
```

## Modules

### `categories.py`
Defines email classification categories and filter decision types.

**Categories:**
- `CONVERSATION`: Human-to-human business dialogue
- `TRANSACTIONAL`: Receipts, confirmations, account actions
- `PROMOTIONAL`: Marketing, sales, advertisements
- `NEWSLETTER`: Regular updates, digests
- `NOTIFICATION`: CI/CD alerts, monitoring
- `AUTOMATED`: Auto-replies, out-of-office
- `SPAM`: Unwanted/suspicious

### `heuristic_filter.py`
Fast pattern-based classification using headers and regex patterns.

**Features:**
- Newsletter detection (List-Unsubscribe, Precedence: bulk)
- Promotional detection (sender patterns, subject patterns)
- Automated email detection (Auto-Submitted, noreply@)
- Notification detection (CI/CD platforms, alerts)
- Transactional detection (receipts, password resets)

**Performance:** ~90% accuracy, zero cost, instant

### `eesa_filter.py`
EESA (Email Enhanced Structured Analysis) custom header support.

**Supported Headers:**
- `X-EESA-Category`: Pre-classified category
- `X-CRM-Category`: Alternative category header
- `X-CRM-Suppress`: Explicit suppress flag
- `X-CRM-Priority`: Priority level (0 = suppress)

### `llm_classifier.py`
LLM-based classification for ambiguous emails.

**Features:**
- Uses OpenAI-compatible API (gpt-4o-mini by default)
- Structured output with Pydantic models
- Confidence scoring
- Reasoning explanation

**Cost:** ~$0.0001 per email (with gpt-4o-mini)

### `orchestrator.py`
Coordinates all filtering strategies in priority order.

**Decision Flow:**
1. Allowlist → Force process
2. Blocklist → Force suppress
3. EESA headers → Use pre-classification
4. Heuristics → Fast rules
5. LLM → Ambiguous cases
6. Default → Process (fail-safe)

### `logging.py`
Audit trail for suppressed emails.

**Features:**
- SQLite database storage for fast queries
- Includes sender, subject, reason, category, timestamps
- Statistics generation and aggregation
- Formatted reports
- Indexed queries for performance

## Configuration

Environment variables (`.env`):

```bash
# Categories to suppress
SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam

# Force-suppress domains
SUPPRESS_DOMAINS=@marketing.company.com,noreply@vendor.com

# Force-process domains (VIP)
ALLOWLIST_DOMAINS=@important-client.com,vip@partner.com

# Classification strategy: heuristic, llm, hybrid
CLASSIFICATION_STRATEGY=hybrid

# LLM model for classification
CLASSIFICATION_MODEL=gpt-4o-mini

# Logging (suppressed emails stored in SQLite)
LOG_SUPPRESSED=true

# Note: Suppressed emails are stored in SQLite (eml_processing.db)
# Query: sqlite3 eml_processing.db "SELECT * FROM suppressed_emails"
```

## Usage Examples

### Basic Usage

```python
from filters import EmailFilterOrchestrator
from email.parser import BytesParser
from email import policy
import openai

# Initialize
llm_client = openai.OpenAI(api_key="...", base_url="...")
orchestrator = EmailFilterOrchestrator(llm_client=llm_client)

# Parse email
with open('email.eml', 'rb') as f:
    msg = BytesParser(policy=policy.default).parse(f)
    body = msg.get_body(preferencelist=('plain', 'html')).get_content()

# Filter decision
decision = orchestrator.should_process(msg, body)

if decision.should_process:
    print(f"Processing: {decision.reason}")
    # Continue to CRM processing...
else:
    print(f"Suppressed: {decision.reason}")
    # Log and skip...
```

### Custom Configuration

```python
from filters import EmailFilterOrchestrator, EmailCategory

# Custom suppress categories
suppress = {EmailCategory.PROMOTIONAL, EmailCategory.SPAM}

# Custom allowlist/blocklist
allowlist = ["@vip-client.com", "important@partner.com"]
blocklist = ["@spam-domain.com", "noreply@ads.com"]

orchestrator = EmailFilterOrchestrator(
    suppress_categories=suppress,
    allowlist_domains=allowlist,
    blocklist_domains=blocklist,
    classification_strategy="hybrid",
    llm_client=llm_client,
    llm_model="gpt-4o-mini"
)
```

### Heuristics Only (No LLM)

```python
orchestrator = EmailFilterOrchestrator(
    classification_strategy="heuristic",
    llm_client=None  # No LLM needed
)
```

## Testing

Run the test suite:

```bash
python eml/test-run/test_filtering.py
```

Test individual components:

```python
from filters import HeuristicFilter, EmailCategory
from email.message import EmailMessage

filter = HeuristicFilter()
msg = EmailMessage()
msg['Subject'] = "Weekly Newsletter"
msg['From'] = "newsletter@example.com"

category = filter.classify(msg)
print(category)  # EmailCategory.NEWSLETTER
```

## Performance

| Stage | Coverage | Latency | Cost |
|-------|----------|---------|------|
| Heuristics | ~90% | <1ms | $0 |
| LLM | ~100% | 100-500ms | $0.0001 |
| Hybrid | ~100% | 1-100ms* | $0.00001* |

*Average assuming 90% heuristic hits

## Monitoring

View suppression statistics:

```bash
# After processing
python eml/eml_automator.py "emails/" --show-filter-stats

# Query database directly
sqlite3 eml_processing.db "SELECT reason, COUNT(*) FROM suppressed_emails GROUP BY reason;"

# Count by category
sqlite3 eml_processing.db "SELECT category, COUNT(*) FROM suppressed_emails GROUP BY category ORDER BY COUNT(*) DESC;"

# Find specific emails
sqlite3 eml_processing.db "SELECT * FROM suppressed_emails WHERE sender LIKE '%example.com%';"
```

## Future Enhancements

- [ ] Batch LLM classification for efficiency
- [ ] User feedback loop for improved heuristics
- [ ] Domain reputation scoring
- [ ] ML-based classification (local, no API cost)
- [ ] Real-time statistics dashboard
