# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.2] - 2025-12-28

### Fixed
- **EESA Web Enrichment**: Fixed web search enrichment for EESA-processed emails
  - `hydrate_from_eesa()` now populates `company_search_query` to trigger web enrichment
  - EESA emails now get the same company enrichment as LLM-analyzed emails
  - Maintains feature parity between EESA and standard processing paths

### Changed
- **Logging**: Improved error logging for search result parsing failures
  - Added debug logging for search result count and content
  - Better visibility into why web enrichment might fail
- **Documentation**: Updated `.env.example` with comprehensive parameter documentation
  - All supported environment variables now documented
  - Organized into logical sections with examples and descriptions

## [1.7.1] - 2025-12-28

### Changed
- **Activity Notes**: Added email timestamp to activity note content for better historical context
  - Email date now displayed prominently in both contact-level and company-level notes
  - Improves chronological accuracy when processing historical emails
  - Clear distinction between email send/receive date and processing date

## [1.7.0] - 2025-12-27

### Added
- **EESA Integration**: Full support for [Email-to-EML Secure Archiver (EESA)](https://github.com/therealtimex/email-archiver) custom headers
  - Automatic detection and parsing of `X-EESA-*` headers in `.eml` files
  - `hydrate_from_eesa()` method in `IntelligenceLayer` to convert EESA metadata to `AnalysisResult`
  - Intelligent fallback to LLM analysis if EESA data is invalid or incomplete
  - Skips expensive LLM API calls when EESA metadata is available
- **Performance Optimization**: Significant reduction in processing time and API costs for EESA-enhanced emails

### Changed
- Enhanced email parsing to extract EESA custom headers (`X-EESA-Category`, `X-EESA-Summary`, `X-EESA-Raw-JSON`)
- Improved deal naming to include organization context (e.g., "Vendor Inc - Sales")
- Added confidence score logging for EESA hydration operations

### Fixed
- Proper email address extraction using `parseaddr()` instead of raw header values

## [1.6.2] - 2025-12-27

### Added
- **Config**: Comprehensive config reactivity and sandbox hardening.

