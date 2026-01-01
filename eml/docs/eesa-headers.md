# EESA Headers Guide

EESA (Email Enhanced Structured Analysis) headers allow you to pre-classify and enrich emails at the email client level, bypassing heuristics and LLM classification.

## What Are EESA Headers?

EESA headers are custom email headers that contain metadata about email classification and extraction results. They are injected by email clients, mail servers, or upstream processing systems.

### Benefits

- ✅ **Skip LLM Classification**: Pre-classified emails don't need expensive LLM analysis
- ✅ **Faster Processing**: Heuristics and LLM stages are skipped
- ✅ **Consistent Classification**: Email client can apply custom rules
- ✅ **Cost Savings**: Reduce LLM API calls by 100% for pre-classified emails
- ✅ **Custom Categories**: Use your own classification logic

## Supported Headers

### Classification Headers

#### `X-EESA-Category`

Primary category classification header.

```
X-EESA-Category: conversation
X-EESA-Category: promotional
X-EESA-Category: newsletter
```

**Supported Values:**
- `conversation` - Business dialogue, process in CRM
- `transactional` - Receipts, confirmations
- `promotional` - Marketing, sales
- `newsletter` - Updates, digests
- `notification` - CI/CD, monitoring
- `automated` - Auto-replies
- `spam` - Unwanted emails

#### `X-CRM-Category`

Alternative category header (same as X-EESA-Category).

```
X-CRM-Category: conversation
```

#### `X-Email-Category`

Another alternative category header.

```
X-Email-Category: promotional
```

### Suppression Headers

#### `X-CRM-Suppress`

Explicit suppress flag to skip CRM processing.

```
X-CRM-Suppress: true
X-CRM-Suppress: 1
X-CRM-Suppress: yes
```

#### `X-CRM-Priority`

Priority level (0 = suppress).

```
X-CRM-Priority: 0    # Suppress
X-CRM-Priority: 1    # Low priority
X-CRM-Priority: 5    # Normal
X-CRM-Priority: 10   # High priority
```

### Extraction Headers

#### `X-EESA-Summary`

Pre-generated email summary.

```
X-EESA-Summary: Customer inquiry about enterprise pricing. Requires follow-up.
```

#### `X-EESA-Processed-At`

Timestamp when email was pre-processed.

```
X-EESA-Processed-At: 2025-01-15T10:30:45Z
```

#### `X-EESA-Raw-JSON`

Complete extraction results in Base64-encoded JSON.

```
X-EESA-Raw-JSON: eyJjbGFzc2lmaWNhdGlvbiI6eyJjYXRlZ29yeSI6InNhbGVzIiwiY29uZmlkZW5jZSI6MC45NX0...
```

**JSON Structure:**
```json
{
  "classification": {
    "category": "sales",
    "confidence": 0.95
  },
  "extraction": {
    "summary": "Customer inquiry about pricing",
    "action_items": ["Send pricing document", "Schedule demo call"],
    "entities": {
      "organizations": ["Acme Corp"],
      "monetary_values": ["$50,000"]
    }
  }
}
```

## Header Priority

When multiple headers are present, CRM Automator checks them in this order:

1. **X-EESA-Category** (highest priority)
2. **X-CRM-Category**
3. **X-Email-Category**
4. **X-CRM-Suppress**
5. **X-CRM-Priority**

If any of these headers are found, **heuristics and LLM classification are skipped**.

## Usage Examples

### Example 1: Mark Email as Conversation

```
From: john@client.com
To: you@company.com
Subject: Enterprise Pricing Inquiry
X-EESA-Category: conversation

Body: Hi, I'm interested in your enterprise plan...
```

**Result:** Email is processed in CRM, LLM analysis skipped for classification but still used for extraction.

### Example 2: Suppress Newsletter

```
From: newsletter@techcrunch.com
To: you@company.com
Subject: Weekly Tech Digest
X-CRM-Suppress: true

Body: Here are this week's top stories...
```

**Result:** Email is suppressed, not processed in CRM.

### Example 3: Complete EESA Metadata

```
From: customer@acme.com
To: sales@company.com
Subject: Demo Request
X-EESA-Category: sales
X-EESA-Summary: Acme Corp requesting product demo
X-EESA-Raw-JSON: eyJjbGFzc2lmaWNhdGlvbiI6eyJjYXRlZ29yeSI6InNhbGVzIn0sImV4dHJhY3Rpb24iOnsic3VtbWFyeSI6IkFjbWUgQ29ycCByZXF1ZXN0aW5nIHByb2R1Y3QgZGVtbyIsImFjdGlvbl9pdGVtcyI6WyJTY2hlZHVsZSBkZW1vIl0sImVudGl0aWVzIjp7Im9yZ2FuaXphdGlvbnMiOlsiQWNtZSBDb3JwIl19fX0=

Body: We'd like to schedule a demo...
```

**Result:** Email uses pre-extracted data, skips LLM entirely, saves maximum cost.

## Adding EESA Headers

### Option 1: Email Client Plugins

Create a plugin/extension for your email client (Thunderbird, Outlook, etc.) to add headers based on rules.

**Example Thunderbird Filter:**
```
Match: From contains "newsletter"
Action: Add header "X-CRM-Suppress: true"
```

### Option 2: Mail Server Rules

Configure your mail server (Postfix, Exchange, etc.) to add headers during delivery.

**Example Postfix header_checks:**
```
/^From:.*newsletter@/ PREPEND X-CRM-Suppress: true
/^List-Unsubscribe:/ PREPEND X-EESA-Category: newsletter
```

### Option 3: Upstream Processing

Process emails through an AI service before they reach CRM Automator:

```python
import email
from email import policy
import base64
import json

# Parse email
with open('email.eml', 'rb') as f:
    msg = email.message_from_binary_file(f, policy=policy.default)

# Classify with your own logic
category = classify_email(msg)  # Your custom classifier

# Add EESA header
msg['X-EESA-Category'] = category

# Save modified email
with open('email_with_eesa.eml', 'wb') as f:
    f.write(msg.as_bytes())
```

### Option 4: API Pre-Processing

Build an API that accepts emails, classifies them, and adds EESA headers:

```python
from fastapi import FastAPI, File, UploadFile
import email
from email import policy

app = FastAPI()

@app.post("/classify-email")
async def classify_email(file: UploadFile):
    # Parse email
    content = await file.read()
    msg = email.message_from_bytes(content, policy=policy.default)

    # Classify
    category = your_classifier(msg)

    # Add header
    msg['X-EESA-Category'] = category

    return {
        "category": category,
        "modified_email": msg.as_string()
    }
```

## EESA Raw JSON Format

The `X-EESA-Raw-JSON` header contains complete extraction results.

### Structure

```json
{
  "classification": {
    "category": "sales|support|newsletter|transactional|demo|other",
    "confidence": 0.0-1.0
  },
  "extraction": {
    "summary": "Brief email summary",
    "action_items": ["Task 1", "Task 2"],
    "entities": {
      "organizations": ["Company A", "Company B"],
      "people": ["John Doe", "Jane Smith"],
      "monetary_values": ["$50,000", "$1M"],
      "dates": ["2025-01-15", "next week"]
    }
  }
}
```

### Encoding

Base64-encode the JSON before adding to header:

```python
import base64
import json

eesa_data = {
    "classification": {"category": "sales", "confidence": 0.95},
    "extraction": {
        "summary": "Demo request from Acme",
        "action_items": ["Schedule demo"],
        "entities": {"organizations": ["Acme Corp"]}
    }
}

# Encode
json_str = json.dumps(eesa_data)
encoded = base64.b64encode(json_str.encode()).decode()

# Add to email
msg['X-EESA-Raw-JSON'] = encoded
```

### Decoding in CRM Automator

CRM Automator automatically decodes and uses this data:

```python
# eml/eml_automator.py (already implemented)
eesa_raw_json = headers.get("X-EESA-Raw-JSON")
if eesa_raw_json:
    eesa_data = json.loads(base64.b64decode(eesa_raw_json))
    analysis = self.ai.hydrate_from_eesa(eesa_data, metadata=metadata)
    # Skips LLM analysis entirely!
```

## Testing EESA Headers

### Create Test Email with Header

```python
from email.message import EmailMessage

msg = EmailMessage()
msg['From'] = 'customer@acme.com'
msg['To'] = 'sales@company.com'
msg['Subject'] = 'Demo Request'
msg['X-EESA-Category'] = 'conversation'
msg.set_content('We would like to schedule a demo...')

# Save
with open('test_eesa.eml', 'wb') as f:
    f.write(msg.as_bytes())
```

### Process and Verify

```bash
# Process the test email
uv run python eml/eml_automator.py "test_eesa.eml" --verbose

# Check logs for EESA detection
# Should see: "Found EESA category: conversation"
```

## Best Practices

1. **Use Consistent Categories**: Stick to the predefined categories for compatibility
2. **Include Confidence**: In Raw JSON, include confidence scores for debugging
3. **Add Timestamps**: Use `X-EESA-Processed-At` to track when classification happened
4. **Validate JSON**: Ensure Raw JSON is valid before Base64 encoding
5. **Don't Override Allowlist**: EESA headers are checked after allowlist/blocklist
6. **Test Thoroughly**: Verify headers are preserved through your mail pipeline

## Troubleshooting

### EESA Headers Not Being Detected

**Check:**

1. **Header spelling:**
   ```bash
   # Extract headers from EML
   grep "X-EESA" email.eml
   grep "X-CRM" email.eml
   ```

2. **Header format:**
   ```
   # Correct
   X-EESA-Category: conversation

   # Incorrect (extra spaces, wrong case)
   X-EESA-CATEGORY : Conversation
   ```

3. **Enable verbose logging:**
   ```bash
   uv run python eml/eml_automator.py "email.eml" --verbose
   ```

   Look for: `Found EESA category: ...` or `EESA header not found`

### Raw JSON Decoding Errors

**Common issues:**

1. **Not Base64 encoded:**
   ```python
   # Wrong
   msg['X-EESA-Raw-JSON'] = json.dumps(data)

   # Correct
   msg['X-EESA-Raw-JSON'] = base64.b64encode(json.dumps(data).encode()).decode()
   ```

2. **Invalid JSON:**
   ```python
   # Test decoding
   import base64
   import json

   encoded = msg.get('X-EESA-Raw-JSON')
   decoded = base64.b64decode(encoded)
   data = json.loads(decoded)  # Should not raise error
   ```

### Headers Lost in Transit

Some mail servers strip custom headers. Solutions:

1. **Use standard prefixes**: `X-` headers are generally preserved
2. **Check mail server config**: Ensure custom headers allowed
3. **Add at final stage**: Insert headers as late as possible before CRM Automator
4. **Verify preservation**:
   ```bash
   # Check original email
   cat original.eml | grep X-EESA

   # Check after mail server
   cat delivered.eml | grep X-EESA
   ```

## Advanced: EESA Header Generator

Build a standalone EESA header generator:

```python
#!/usr/bin/env python3
"""
EESA Header Generator
Classifies emails and adds EESA headers.
"""

import email
from email import policy
import base64
import json
import sys
from openai import OpenAI

def classify_email(msg, llm_client):
    """Classify email using LLM."""
    sender = msg.get('From', '')
    subject = msg.get('Subject', '')
    body = msg.get_body(preferencelist=('plain',)).get_content()[:500]

    prompt = f"""Classify this email:
From: {sender}
Subject: {subject}
Body: {body}

Category (conversation/promotional/newsletter/transactional/automated/spam):"""

    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10
    )

    return response.choices[0].message.content.strip().lower()

def add_eesa_headers(eml_path, output_path):
    """Add EESA headers to email."""
    # Parse
    with open(eml_path, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    # Classify
    llm = OpenAI(api_key="...")
    category = classify_email(msg, llm)

    # Add headers
    msg['X-EESA-Category'] = category
    msg['X-EESA-Processed-At'] = email.utils.formatdate(localtime=True)

    # Save
    with open(output_path, 'wb') as f:
        f.write(msg.as_bytes())

    print(f"Added EESA headers: category={category}")

if __name__ == "__main__":
    add_eesa_headers(sys.argv[1], sys.argv[2])
```

## Next Steps

- **Email Filtering**: Learn how EESA headers integrate with filtering - [Email Filtering Guide](./email-filtering.md)
- **Intelligence Layer**: Understand how EESA data bypasses LLM - [Intelligence Layer](./intelligence-layer.md)
- **Configuration**: Configure EESA header behavior - [Configuration Guide](./configuration.md)
