# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.17] - 2026-01-02

### Fixed
- **Web UI - Drag & Drop**: Fixed issue where upload drop zone would not initialize correctly when switching tabs
  - Added explicit re-initialization handler on tab change events
  - Refactored drop zone setup to be accessible globally via `window.initUploadDropZone`

## [1.9.16] - 2026-01-02

### Improved
- **Web UI - UX**: Implemented notification debouncing for file uploads to prevent "toast flood" when adding multiple files
  - Grouped success messages into a single summary
  - Batched error and warning notifications for better readability

## [1.9.15] - 2026-01-02

### Improved
- **Web UI**: Enhanced Drag & Drop reliability using MutationObserver and native Quasar file picking
- **Web UI**: Better Live Logs auto-scrolling and window management
- **Code Quality**: Removed unused imports and cleaned up code in web_ui.py

## [1.9.14] - 2026-01-02

### Added
- **Web UI - Drag & Drop**: Implemented drag and drop support for file management
- **Web UI - File Browser**: Added file browser functionality for better file handling

### Changed
- **Web UI - Structure**: Restructured the Web UI layout for better organization and usability

### Improved
- **System**: Applied efficiency optimizations for better performance

## [1.9.13] - 2026-01-02

### Fixed
- **Web UI - Auto-Refresh**: Fixed modal interference where auto-refresh would abruptly close the Email Detail Modal
  - Auto-refresh now pauses when modal is open and resumes when closed (all methods: close button, backdrop click, ESC key)
  - Added visual feedback showing "Auto-refresh paused (modal open)" in status indicator
  - Uses Quasar's native `hide` event for reliable detection of all modal close methods
- **Web UI - Analytics Refresh**: Fixed Analytics tab "Refresh Data" button that was reloading entire page
  - Now refreshes only chart data without page reload, preserving user state
  - Timeline chart automatically updates when date range selector changes
  - Shows success notification after refresh completes
- **Web UI - Live Logs**: Added auto-scroll to Live Logs section
  - Logs automatically scroll to bottom to show latest entries during processing
  - Uses JavaScript scroll after each 1-second update for smooth UX

### Changed
- **Web UI - User Experience**: Improved overall responsiveness and state preservation across the web interface
  - Users can now read email details without interruption from auto-refresh
  - Analytics exploration is faster and doesn't lose tab/filter state
  - Real-time logs are easier to follow during batch processing

## [1.9.12] - 2026-01-01

### Fixed
- **Configuration Path Resilience**: Implemented robust path resolution for `.env` files in `ConfigManager` to avoid permission errors in sandbox environments.
- **Sandbox Protection**: Prevents automatic writing to system directories by falling back to user home or temporary directories for configuration storage.
- **CLI-UI Integration**: Correctly passed the `--env-file` command-line argument from `eml_automator.py` to the Web UI.

## [1.9.11] - 2026-01-01

### Fixed
- **CRM Connection Test**: Fixed `ModuleNotFoundError: No module named 'crm_client'` when testing connection from the Web UI.
- **Imports**: Standardized all remaining local/function-scope imports to use the robust tiered pattern.

## [1.9.10] - 2026-01-01

### Fixed
- **Sandbox Resilience**: Implemented robust database path resolution in `PersistenceLayer` to avoid `OperationalError` in restricted environments.
- **System Path Protection**: Added logic to avoid writing to root-level system folders (like `/bin`, `/var/www`, etc.) automatically, falling back to user home or temp directories as needed.
- **CLI Enhancement**: Ensured `--db-path` argument in `eml_automator.py` is correctly passed to the persistence layer.

## [1.9.9] - 2026-01-01

### Fixed
- **Packaging**: Updated `pyproject.toml` to use `find_packages` to ensure sub-packages like `eml.filters` are included in the distribution.
- **Imports**: Standardized internal imports across the codebase to prioritize absolute package paths (`from eml.xxx`) for better compatibility when installed as a library.

## [1.9.8] - 2026-01-01

### Fixed
- **Robust Imports**: Implemented tiered import logic using relative imports (`from .xxx`), absolute package imports (`from eml.xxx`), and local fallbacks to ensure compatibility across all execution environments (local, installed package, and `uvx`).

## [1.9.7] - 2026-01-01

### Changed
- **CLI Entry Point**: Renamed executable from `eml-automator` to `crm-automator` to match package name, enabling seamless execution via `uvx crm-automator`.

## [1.9.6] - 2026-01-01

### Fixed
- **Package Execution (uvx)**: Fixed `ModuleNotFoundError` when running as an installed package by updating internal imports to use absolute package paths (e.g., `from eml.xxx`) with local fallbacks.

## [1.9.5] - 2026-01-01

### Fixed
- **UI Layout**: Fixed Email Detail Modal layout issues where tabs and content were hidden due to global CSS conflicts (added `!h-12` and `min-h-0`).
- **UI Alignment**: Fixed alignment of "No data" placeholders in AI Analysis, CRM Integration, and Error Details tabs to be centered.
- **Search**: Fixed "Recent Activity" search by adding live search (debounced) and restoring Enter key functionality.
- **Pagination**: Fixed pagination event handling in "Recent Activity" table by using `on_change` listener.
- **Graceful Exit**: Added `KeyboardInterrupt` handling to `eml_automator.py` and `web_ui.py` for a clean "Bye!" message on Ctrl+C.
- **Serialization Error**: Fixed `TypeError: Object of type bytes is not JSON serializable` by sanitizing binary content from `crm_activities_payload` logs.

## [1.9.4] - 2025-12-31

### Added
- **SQLite Database Storage**: Migrated suppressed email logging from JSONL to SQLite for faster queries and better data management.
- **Migration Script**: Added `migrate_jsonl_to_sqlite.py` for backward compatibility with existing JSONL logs.
- **Database Indexes**: Added 4 indexes on `suppressed_emails` table (timestamp, category, reason, sender) for optimized query performance.
- **Query API**: Added Python API methods for querying suppressed emails (`get_suppressed_emails()`, `get_suppression_stats()`).

### Changed
- **Documentation**: Updated all documentation (email-filtering.md, configuration.md, troubleshooting.md, CLAUDE.md, filters/README.md) to reflect SQLite storage with query examples.
- **Persistence Layer**: Enhanced with suppressed email logging, statistics generation, and aggregation methods.
- **Unified Storage**: Suppressed emails now stored in the same SQLite database as processed emails (`eml_processing.db`).

### Removed
- **JSONL Logging**: Removed JSONL file-based logging in favor of SQLite database.
- **Configuration**: Removed obsolete `SUPPRESSED_LOG_PATH` environment variable (SQLite storage is automatic).

## [1.9.3] - 2025-12-28

### Changed
- **Premium CLI Experience**: Enhanced `tqdm` progress bar with green colors, units ("emails"), and persistent completion state.

### Fixed
- **Robust Scanner Error Handling**: Added OS error handling (PermissionError, FileNotFoundError) to the directory scanner to prevent crashes during batch operations.

## [1.9.2] - 2025-12-28

### Added
- **Visual Progress Bar**: Integrated `tqdm` for better visual feedback during batch processing.

### Fixed
- **Robust Scanner**: Added validation to skip empty `.eml` files during directory scans.
- **Pydantic Compatibility**: Ensured consistent `model_fields` access pattern to avoid future deprecation warnings.

## [1.9.1] - 2025-12-28

### Fixed
- **Pydantic Deprecation**: Fixed `PydanticDeprecatedSince211` by accessing `model_fields` from the class instead of the instance in `eml_automator.py`.

## [1.9.0] - 2025-12-28

### Added
- **Batch Directory Processing**: Support for passing a directory path to process all `.eml` files recursively.
- **Filtering**: Automatically ignores non-EML files during directory scans.
- **Summary Reporting**: Added a summary report at the end of runs showing success, failure, and total file counts.

## [1.8.0] - 2025-12-28

### Added
- **`uv` Support**: Added `uv.lock` for extremely fast, reproducible dependency management and virtual environment synchronization.
- **`uvx` Support**: Added PEP 723 inline script metadata to `eml/eml_automator.py` to enable zero-install execution (e.g., `uvx eml/eml_automator.py`).
- **Modern Documentation**: Comprehensive updates to `CLAUDE.md` and `README.md` with updated installation and usage instructions using `uv`.

## [1.7.7] - 2025-12-28

### Fixed
- **Documentation Sync**: Updated `eml/docs/agent_demo.py` to use the refined `AnalysisResult` field names (`primary_contact`) to maintain consistency and functionality of example code.

## [1.7.6] - 2025-12-28

### Refined
- **Model Consolidation**: Merged `revenue` and `revenue_range` into a single validated field
- **Field Renaming**: Renamed `sender_info` → `primary_contact` and `other_contacts` → `additional_contacts` for better semantic clarity
- **Enhanced Extraction**: Updated system prompt to explicitly prioritize first/last name extraction and social profiles
- **Validation**: Added bounds validation for `founded_year` (1800-2100)

### Fixed
- **Redundancy Cleanup**: Removed manual field mapping logic in `crm_client.py` now handled by models
- **Logic Sync**: Synchronized `eml_automator.py` with new model field names

## [1.7.5] - 2025-12-28

### Changed
- **Model Refactoring**: Renamed `SenderInfo` to `ParticipantInfo` to better reflect multi-contact extraction
- **Multi-Contact Support**: Extraction now explicitly separates `first_name` and `last_name` for all participants
- **Schema Alignment**: Fully aligned `CompanyDetails` with CRM `api-v1-companies` schema (added industry, employee_count, founded_year, social_profiles, logo_url, etc.)
- **Cleanup**: Removed unused legacy `Contact` model classes

### Fixed
- **Name Extraction**: Improved reliability of contact name extraction by using LLM-extracted first/last names with header fallbacks
- **Data Integrity**: Enforced consistent `ParticipantInfo` structure for all thread participants (To, Cc, Bcc)

## [1.7.4] - 2025-12-28

### Fixed
- **Schema Alignment**: Fixed critical data model mismatches with CRM API
  - Changed `Contact.email` from a list of dicts to a single string for better compatibility with email extraction
  - Implemented automatic mapping for `revenue` model field to CRM's `revenue_range` field
  - Improved phone number handling: intelligence `phone` field now correctly maps to CRM's `phone_jsonb` structure
- **Documentation**: Added comprehensive documentation to `CLAUDE.md` detailing known schema gaps and enrichment limitations

## [1.7.3] - 2025-12-28

### Changed
- **Dependencies**: Migrated from deprecated `duckduckgo-search` to `ddgs` package
  - Removes deprecation warnings during web search operations
  - Uses actively maintained package with same API
  - Improves search reliability with multiple backend support (Wikipedia, Grokipedia, DuckDuckGo, Brave)

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

