# CRM Automator Documentation Index

Complete documentation for the CRM Automator email processing toolkit.

## 📚 Documentation Guide

### Getting Started
- **[Getting Started Guide](./getting-started.md)** - Installation, setup, and first run
  - Prerequisites and installation
  - Environment configuration
  - First email processing
  - Testing and validation

### Core Features
- **[Email Processing](./README.md)** - How email parsing and CRM sync works
  - Basic CLI usage
  - Command-line flags
  - Environment variables
  - Agent demo

- **[Email Filtering System](./email-filtering.md)** - Suppress irrelevant emails before processing
  - Multi-stage hybrid filtering
  - Email categories and classification
  - Configuration and tuning
  - Performance metrics
  - Monitoring and analytics

- **[EESA Headers](./eesa-headers.md)** - Pre-classify emails at email client level
  - Custom header reference
  - Adding EESA headers
  - EESA Raw JSON format
  - Testing and validation

### Reference
- **[Configuration Guide](./configuration.md)** - Complete environment variable reference
  - Required settings (CRM API, LLM)
  - Email filtering configuration
  - Internal staff filtering
  - Search providers
  - Advanced configuration examples

- **[Troubleshooting](./troubleshooting.md)** - Common issues and solutions
  - Installation issues
  - Configuration problems
  - Processing errors
  - CRM sync issues
  - Performance tuning

### Additional Resources
- **[Technical Specification](./technical_specification.md)** - Original technical spec
- **[User Guide](./USER_GUIDE.md)** - End-user guide
- **[Agent Sync Example](./agent_sync_example.md)** - Agent synchronization patterns

## 🚀 Quick Navigation

### I want to...

**Get started quickly**
→ [Getting Started Guide](./getting-started.md)

**Configure email filtering**
→ [Email Filtering System](./email-filtering.md#configuration)

**Suppress promotional emails**
→ [Email Filtering - Configuration](./email-filtering.md#basic-configuration)

**Pre-classify emails with custom headers**
→ [EESA Headers Guide](./eesa-headers.md)

**Fix configuration issues**
→ [Troubleshooting - Configuration Issues](./troubleshooting.md#configuration-issues)

**Optimize for cost/speed**
→ [Email Filtering - Strategy Comparison](./email-filtering.md#strategy-comparison)

**Understand all config options**
→ [Configuration Guide](./configuration.md)

**Debug processing errors**
→ [Troubleshooting](./troubleshooting.md)

## 📖 Documentation by Topic

### Installation & Setup
1. [Getting Started](./getting-started.md)
2. [Configuration Guide](./configuration.md)
3. [Troubleshooting - Installation](./troubleshooting.md#installation-issues)

### Email Processing
1. [Email Processing Basics](./README.md)
2. [Email Filtering](./email-filtering.md)
3. [EESA Headers](./eesa-headers.md)

### Configuration & Tuning
1. [Configuration Reference](./configuration.md)
2. [Email Filtering Configuration](./email-filtering.md#configuration)
3. [EESA Configuration](./eesa-headers.md#configuration)

### Troubleshooting
1. [Common Issues](./troubleshooting.md)
2. [Performance Tuning](./troubleshooting.md#performance-issues)
3. [Cost Optimization](./troubleshooting.md#high-llm-api-costs)

## 🎯 Use Case Guides

### High-Volume Email Processing
1. Enable heuristic-only filtering: [Email Filtering - Heuristics Only](./email-filtering.md#example-3-heuristics-only-no-llm-cost)
2. Optimize performance: [Troubleshooting - Performance](./troubleshooting.md#processing-is-very-slow)
3. Monitor suppression stats: [Email Filtering - Monitoring](./email-filtering.md#monitoring--analytics)

### Cost-Conscious Setup
1. Use hybrid strategy: [Email Filtering - Strategy](./email-filtering.md#classification-strategy)
2. Choose cheap models: [Configuration - LLM Models](./configuration.md#classification-model)
3. Aggressive filtering: [Email Filtering - Examples](./email-filtering.md#example-1-suppress-only-spam)

### Enterprise with VIP Clients
1. Configure allowlist: [Email Filtering - Allowlist](./email-filtering.md#stage-1-allowlist-force-process)
2. Use EESA headers: [EESA Headers](./eesa-headers.md)
3. Monitor important emails: [Email Filtering - Troubleshooting](./email-filtering.md#important-emails-being-suppressed)

## 🆕 What's New

### v1.9.3 - Email Filtering System
- **Hybrid Filtering**: 3-stage classification (Heuristics → EESA → LLM)
- **7 Email Categories**: Conversation, Transactional, Promotional, Newsletter, Notification, Automated, Spam
- **Smart Suppression**: 90% filtered by free heuristics, 10% by LLM
- **EESA Headers**: Pre-classification support (X-EESA-Category, X-CRM-Suppress)
- **Audit Trail**: Complete logging of suppressed emails
- **Cost Optimization**: Reduce LLM costs by 80-90%
- **Performance**: <1ms for heuristic filtering, 100-500ms for LLM
- **Configuration**: Extensive config options for tuning

See [Email Filtering Guide](./email-filtering.md) for complete documentation.

## 📊 Feature Matrix

| Feature | Docs | Config Required | CLI Flag |
|---------|------|-----------------|----------|
| Email Parsing | [README](./README.md) | ✅ CRM + LLM | `eml_automator.py` |
| Email Filtering | [Filtering](./email-filtering.md) | ⚙️ Optional | `--show-filter-stats` |
| EESA Headers | [EESA](./eesa-headers.md) | ⚙️ Optional | N/A |
| Heuristic Filtering | [Filtering](./email-filtering.md#stage-4-fast-heuristics-90-coverage) | ⚙️ Optional | N/A |
| LLM Classification | [Filtering](./email-filtering.md#stage-5-llm-classification-ambiguous-cases-only) | ✅ LLM API | `--llm-model` |
| Web Enrichment | [Config](./configuration.md#search-provider-configuration) | ⚙️ Optional | N/A |
| Internal Filtering | [Config](./configuration.md#internal-staff-filtering) | ⚙️ Optional | N/A |
| Batch Processing | [README](./README.md) | ✅ CRM + LLM | Input directory |
| Duplicate Prevention | [README](./README.md) | ⚙️ Optional | `--force` to skip |

## 🔧 Quick Reference

### Common Commands

```bash
# Process single email
uv run python eml/eml_automator.py "email.eml"

# Process directory
uv run python eml/eml_automator.py "emails/"

# Show filter statistics
uv run python eml/eml_automator.py "emails/" --show-filter-stats

# Verbose mode
uv run python eml/eml_automator.py "email.eml" --verbose

# Force reprocess
uv run python eml/eml_automator.py "emails/" --force

# Custom env file
uv run python eml/eml_automator.py "emails/" --env-file ".env.prod"
```

### Important Files

- `.env` - Configuration (see [Configuration Guide](./configuration.md))
- `logs/suppressed_emails.jsonl` - Suppressed email audit trail
- `eml_processing.db` - Persistence database
- `eml/filters/` - Filtering system code
- `eml/test-run/` - Debug and test scripts

## 📞 Support

- **Issues**: Report bugs on GitHub Issues
- **Questions**: See [Troubleshooting Guide](./troubleshooting.md)
- **Examples**: Check `eml/test-run/` for working examples
- **Configuration**: See [Configuration Reference](./configuration.md)

## 📝 Contributing

Documentation improvements welcome! Please maintain:
- Clear headings and structure
- Code examples with explanations
- Links to related documentation
- Troubleshooting sections where applicable

---

**Last Updated**: 2025-12-31 (v1.9.3)
