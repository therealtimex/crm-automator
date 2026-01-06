# Email Filtering Guide

CRM Automator includes a sophisticated hybrid filtering system to suppress irrelevant emails (promotions, newsletters, automated messages) before expensive CRM processing.

## Why Filter Emails?

Processing every email wastes:
- **💰 API costs**: LLM analysis costs ~$0.001-0.01 per email
- **⏱️ Time**: Processing takes 2-10 seconds per email
- **📊 Data quality**: Promotional emails clutter your CRM

**Solution**: Filter out 80-90% of irrelevant emails before processing.

## How It Works

The filtering system uses a **multi-stage cascade**:

```
Email → Allowlist? → Blocklist? → EESA Headers? → Heuristics? → LLM? → Decision
         ↓ Process    ↓ Suppress    ↓ Category      ↓ Category    ↓ Category
```

### Stage 1: Allowlist (Force Process)

VIP clients and important partners bypass all filters.

```bash
# .env configuration
ALLOWLIST_DOMAINS=@important-client.com,vip@partner.com,@enterprise-customer.com
```

**Supports:**
- Full emails: `john@company.com`
- Domain patterns: `@company.com`
- Partial domains: `company.com`

### Stage 2: Blocklist (Force Suppress)

Known spam domains and unwanted senders are blocked immediately.

```bash
# .env configuration
SUPPRESS_DOMAINS=@marketing.spam.com,noreply@ads.com,newsletter@vendor.com
```

### Stage 3: EESA Custom Headers

Pre-classified emails skip all heuristics and LLM analysis.

```
X-EESA-Category: conversation
X-CRM-Category: promotional
X-CRM-Suppress: true
X-CRM-Priority: 0
```

See [EESA Headers Guide](./eesa-headers.md) for details.

### Stage 4: Fast Heuristics (90% Coverage)

Pattern matching on headers, senders, and subjects.

**Newsletter Detection:**
- Headers: `List-Unsubscribe`, `List-Id`, `Precedence: bulk`
- Senders: `newsletter@`, `news@`, `updates@`, `digest@`
- Subjects: `weekly digest`, `monthly update`, `newsletter`

**Promotional Detection:**
- Senders: `marketing@`, `promo@`, `deals@`, `offers@`, `noreply@`
- Subjects: `50% OFF`, `limited time`, `sale`, `discount`, `free shipping`

**Automated Detection:**
- Headers: `Auto-Submitted`, `X-Auto-Response-Suppress`
- Senders: `noreply@`, `donotreply@`, `mailer-daemon@`
- Subjects: `out of office`, `automatic reply`, `vacation response`

**Notification Detection:**
- Senders: `notifications@github.com`, `ci@gitlab.com`, `alerts@monitoring.com`
- Subjects: `[Build Failed]`, `[CI]`, `[Alert]`, `deployment succeeded`

**Transactional Detection:**
- Subjects: `receipt`, `invoice`, `order confirmation`, `password reset`

### Stage 5: LLM Classification (Ambiguous Cases Only)

When heuristics can't decide confidently, LLM is used.

**Prompt Template:**
```
Classify this email into ONE category:
- conversation: Human-to-human business dialogue
- transactional: Receipts, confirmations, account actions
- promotional: Marketing, sales, advertisements
- newsletter: Regular updates, digests
- notification: CI/CD alerts, monitoring
- automated: Auto-replies, out-of-office
- spam: Unwanted emails

Email Details:
From: {sender}
Subject: {subject}
Body Preview: {first 500 chars}
```

**Cost**: ~$0.0001 per email (with gpt-4o-mini)

## Email Categories

| Category | Examples | Default Action |
|----------|----------|----------------|
| **conversation** | Customer emails, partner discussions, lead inquiries | ✅ **PROCESS** |
| **transactional** | Receipts, confirmations, password resets, invoices | ✅ **PROCESS** |
| **promotional** | Marketing emails, sales pitches, special offers | ⊘ **SUPPRESS** |
| **newsletter** | Weekly digests, industry news, content updates | ⊘ **SUPPRESS** |
| **notification** | CI/CD alerts, monitoring, GitHub/GitLab notifications | ⊘ **SUPPRESS** |
| **automated** | Auto-replies, out-of-office, delivery notifications | ⊘ **SUPPRESS** |
| **spam** | Unwanted, suspicious, or explicitly suppressed emails | ⊘ **SUPPRESS** |

## Configuration

### Basic Configuration

```bash
# .env file

# Categories to suppress (comma-separated)
SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam

# Classification strategy
CLASSIFICATION_STRATEGY=hybrid  # heuristic, llm, or hybrid
```

### Advanced Configuration

```bash
# Force-suppress specific domains
SUPPRESS_DOMAINS=@marketing.company.com,noreply@vendor.com

# Force-process VIP domains (override suppressions)
ALLOWLIST_DOMAINS=@important-client.com,vip@partner.com

# LLM model for classification (if using llm/hybrid strategy)
CLASSIFICATION_MODEL=gpt-4o-mini  # Recommend cheap model

# LLM Parameters
LLM_MAX_TOKENS=4096  # Increase for verbose local models
LLM_TEMPERATURE=0.1  # Keep low for consistent classification

# Logging (suppressed emails stored in SQLite)
LOG_SUPPRESSED=true
```

### Strategy Comparison

| Strategy | Speed | Cost | Accuracy | Use Case |
|----------|-------|------|----------|----------|
| `heuristic` | ⚡️ <1ms | $0 | ~90% | High volume, cost-sensitive |
| `llm` | 🐢 100-500ms | $0.0001/email | ~100% | High accuracy needed |
| `hybrid` | ⚡️ 1-100ms avg | $0.00001/email avg | ~100% | **Recommended** |

## Usage Examples

### Example 1: Suppress Only Spam

```bash
# .env
SUPPRESS_CATEGORIES=spam,automated
```

This will process:
- ✅ Conversations
- ✅ Transactional
- ✅ Promotional
- ✅ Newsletters
- ✅ Notifications
- ⊘ Spam
- ⊘ Automated

### Example 2: VIP Client Override

```bash
# .env
SUPPRESS_CATEGORIES=promotional,newsletter
ALLOWLIST_DOMAINS=@vip-client.com
```

All emails from `@vip-client.com` will be processed, even if they're promotional.

### Example 3: Heuristics Only (No LLM Cost)

```bash
# .env
CLASSIFICATION_STRATEGY=heuristic
```

Only use pattern matching, never call LLM. Saves cost but may miss edge cases.

### Example 4: Block Specific Senders

```bash
# .env
SUPPRESS_DOMAINS=marketing@spammer.com,@ads-network.com
```

These senders are blocked regardless of content.

## Monitoring & Analytics

### View Filtering Statistics

```bash
# After processing, show filter stats
uv run python eml/eml_automator.py "emails/" --show-filter-stats
```

**Output:**
```
============================================================
SUPPRESSED EMAILS REPORT
============================================================

Total Suppressed: 47

By Reason:
  heuristic:newsletter: 23
  heuristic:promotional: 15
  llm:automated: 6
  blocklist_suppress: 3

By Category:
  newsletter: 23
  promotional: 15
  automated: 6
  spam: 3
============================================================
```

### Query Suppression Database

```bash
# View all suppressed emails
sqlite3 eml_processing.db "SELECT * FROM suppressed_emails;"

# Count by category
sqlite3 eml_processing.db "
SELECT category, COUNT(*) as count
FROM suppressed_emails
GROUP BY category
ORDER BY count DESC;
"

# Find all promotional emails
sqlite3 eml_processing.db "
SELECT file_name, subject, sender
FROM suppressed_emails
WHERE category = 'promotional';
"

# Check if specific email was suppressed
sqlite3 eml_processing.db "
SELECT * FROM suppressed_emails
WHERE sender LIKE '%example.com%';
"

# Recent suppressions (last 10)
sqlite3 eml_processing.db "
SELECT timestamp, file_name, reason, category
FROM suppressed_emails
ORDER BY timestamp DESC
LIMIT 10;
"

# Python API for querying
python -c "
from persistence import PersistenceLayer
db = PersistenceLayer()

# Get specific suppressed emails
emails = db.get_suppressed_emails(
    limit=10,
    category='promotional',
    sender='example.com'
)

for email in emails:
    print(f'{email[\"file_name\"]}: {email[\"subject\"]}')
"
```

### Database Schema

```sql
CREATE TABLE suppressed_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    category TEXT,
    sender TEXT,
    recipient TEXT,
    subject TEXT,
    email_date TEXT,
    message_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast queries
CREATE INDEX idx_suppressed_timestamp ON suppressed_emails(timestamp);
CREATE INDEX idx_suppressed_category ON suppressed_emails(category);
CREATE INDEX idx_suppressed_reason ON suppressed_emails(reason);
CREATE INDEX idx_suppressed_sender ON suppressed_emails(sender);
```

## Performance Metrics

### Filtering Performance

| Metric | Value |
|--------|-------|
| **Heuristic Latency** | <1ms |
| **LLM Latency** | 100-500ms |
| **Hybrid Average Latency** | 1-100ms (90% hit rate) |
| **Memory Usage** | <10MB |
| **Accuracy** | 95-100% |

### Cost Analysis

**Scenario:** Processing 1,000 emails

| Strategy | LLM Calls | Cost | Time |
|----------|-----------|------|------|
| `heuristic` only | 0 | $0 | 1 second |
| `llm` always | 1,000 | $0.10 | 3-8 minutes |
| `hybrid` (90% hit) | 100 | $0.01 | 10-50 seconds |

**Recommendation:** Use `hybrid` for best cost/accuracy balance.

## Troubleshooting

### Emails Being Wrongly Suppressed

**Problem:** Important emails are being filtered out.

**Solutions:**

1. **Add to allowlist:**
   ```bash
   ALLOWLIST_DOMAINS=@important-client.com
   ```

2. **Check suppression database:**
   ```bash
   sqlite3 eml_processing.db "
   SELECT * FROM suppressed_emails
   WHERE sender LIKE '%client.com%';
   "
   ```

3. **Adjust suppress categories:**
   ```bash
   # Only suppress spam
   SUPPRESS_CATEGORIES=spam
   ```

### Too Many Emails Being Processed

**Problem:** Promotional/newsletter emails are getting through.

**Solutions:**

1. **Use LLM classification:**
   ```bash
   CLASSIFICATION_STRATEGY=llm
   ```

2. **Add to blocklist:**
   ```bash
   SUPPRESS_DOMAINS=@marketing.vendor.com,newsletter@company.com
   ```

3. **Expand suppress categories:**
   ```bash
   SUPPRESS_CATEGORIES=promotional,newsletter,automated,spam,notification
   ```

### LLM Classification Not Working

**Problem:** All emails default to "process" without LLM classification.

**Check:**

1. **LLM client configured:**
   ```bash
   grep LLM_BASE_URL .env
   ```

2. **Strategy is not heuristic-only:**
   ```bash
   grep CLASSIFICATION_STRATEGY .env
   # Should be "hybrid" or "llm", not "heuristic"
   ```

3. **Test LLM connection:**
   ```bash
   uv run python -c "
   from eml.intelligence import IntelligenceLayer
   ai = IntelligenceLayer()
   print('LLM connected:', ai.client is not None)
   "
   ```

## Best Practices

1. **Start with hybrid strategy** - Best cost/accuracy balance
2. **Use allowlist for VIPs** - Never miss important clients
3. **Monitor suppression logs** - Review first 100 processed emails
4. **Use EESA headers** - Pre-classify at email client when possible
5. **Adjust over time** - Fine-tune based on your email patterns

## Advanced Topics

### Custom Heuristic Rules

To add custom patterns, edit `eml/filters/heuristic_filter.py`:

```python
# Add custom newsletter pattern
NEWSLETTER_SUBJECT_PATTERNS = [
    r'weekly\s+digest',
    r'monthly\s+update',
    r'your\s+custom\s+pattern',  # Add here
]
```

### Programmatic Usage

```python
from filters import EmailFilterOrchestrator, EmailCategory
from email.parser import BytesParser
from email import policy
import openai

# Initialize
llm_client = openai.OpenAI(...)
orchestrator = EmailFilterOrchestrator(
    suppress_categories={EmailCategory.PROMOTIONAL, EmailCategory.SPAM},
    allowlist_domains=["@vip.com"],
    classification_strategy="hybrid",
    llm_client=llm_client
)

# Parse email
with open('email.eml', 'rb') as f:
    msg = BytesParser(policy=policy.default).parse(f)
    body = msg.get_body(preferencelist=('plain', 'html')).get_content()

# Filter
decision = orchestrator.should_process(msg, body)

if decision.should_process:
    print(f"Processing: {decision.reason}")
else:
    print(f"Suppressed: {decision.reason} ({decision.category})")
```

## Next Steps

- **EESA Headers**: Learn how to pre-classify emails at the email client level - [EESA Headers Guide](./eesa-headers.md)
- **Intelligence Layer**: Understand how LLM analysis works - [Intelligence Layer](./intelligence-layer.md)
- **Configuration**: See all available options - [Configuration Guide](./configuration.md)
