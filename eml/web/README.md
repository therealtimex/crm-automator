# Web UI Module Structure

This directory contains the refactored web UI components for the CRM Automator, extracted from the monolithic `web_ui.py` file for better maintainability.

## Module Overview

### `state.py` (76 lines)
**Purpose**: Global state management and logging

**Exports**:
- `ProcessingState` - Tracks file processing state (progress, logs, uploaded files)
- `WebUILogHandler` - Custom logging handler that captures logs for UI display
- `state` - Global singleton instance

**Key Responsibilities**:
- Managing upload queue and processing status
- Capturing application logs for real-time display
- Cleanup of temporary files

---

### `config.py` (273 lines)
**Purpose**: Configuration management for `.env` files

**Exports**:
- `ConfigManager` - Handles loading, saving, and validating configuration

**Key Features**:
- Preserves comments and structure when saving `.env` files
- Validates email addresses, domains, and URLs
- Tests CRM and LLM API connectivity
- Smart path resolution (CWD → home directory → temp fallback)

**Methods**:
- `load_config()` - Read configuration from `.env`
- `save_config()` - Write configuration while preserving structure
- `validate_config()` - Validate all configuration fields
- `test_crm_connection()` - Test RealTimeX CRM API
- `test_llm_connection()` - Test LLM API with detailed diagnostics

---

### `analytics.py` (492 lines)
**Purpose**: Analytics data generation and visualization

**Exports**:
- `AnalyticsEngine` - Main analytics class
- `get_database_stats()` - Fetch processing statistics
- `get_suppressed_emails()` - Query suppressed email list
- `get_suppression_stats()` - Get suppression breakdown

**Chart Types**:
- Processing pie chart (processed/suppressed/failed breakdown)
- Success rate gauge chart
- Category bar chart (suppression by category)
- Timeline chart (daily processing trends)
- Top domains chart (most suppressed senders)

**Data Sources**:
- SQLite `processing_log` table via `PersistenceLayer`
- Real-time aggregation and filtering

---

### `components.py` (280 lines)
**Purpose**: Reusable UI components and theming

**Exports**:
- `apply_nexus_theme()` - Inject Nexus Glass CSS styling
- `status_badge()` - Create colored status badges
- `create_header_with_tabs()` - Build app header with navigation
- `create_stat_card()` - Dashboard stat cards with trends
- `create_recent_activity_item()` - Activity list items
- `create_empty_state()` - Empty state placeholders

**Design System**:
- Nexus Glass theme (dark mode with glassmorphism)
- Responsive design (mobile-first)
- Tailwind-inspired utility classes
- Consistent color palette and spacing

---

## Main Application (`../web_ui.py`)

**Size**: 1,394 lines (reduced from 2,416 lines)

**Responsibilities**:
- Application entry point and routing
- Tab panel composition (Dashboard, Upload, Analytics, Suppressed, Configuration)
- File upload and processing orchestration
- Real-time UI updates and auto-refresh logic

**Key Functions**:
- `main_page()` - Main UI composition with all tabs
- `process_files_async()` - Async file processing with progress tracking
- `show_processing_detail()` - Modal dialog for detailed email view
- `run_ui()` - Application startup and server configuration

---

## Architecture Benefits

### Before Refactoring
- Single 2,416-line file
- Mixed concerns (state, config, analytics, UI)
- Difficult to navigate and maintain

### After Refactoring
- Modular structure with clear separation of concerns
- Each module has a single, well-defined purpose
- 42% reduction in main file size
- Easier testing and future enhancements

---

## Import Pattern

```python
# In web_ui.py
from eml.web.state import state, WebUILogHandler
from eml.web.config import ConfigManager
from eml.web.analytics import AnalyticsEngine, get_database_stats
from eml.web.components import apply_nexus_theme, create_header_with_tabs
```

---

## Development Guidelines

1. **State Management**: All global state should go through `state.py`
2. **Configuration**: Use `ConfigManager` for all `.env` operations
3. **Analytics**: Add new charts to `AnalyticsEngine` class
4. **UI Components**: Create reusable components in `components.py`
5. **Main App**: Keep `web_ui.py` focused on composition and orchestration

---

## Dependencies

- **NiceGUI** v3.4.1+ - Web UI framework
- **Plotly** - Interactive charts
- **SQLite3** - Database queries (via `PersistenceLayer`)
- **Python-dotenv** - Environment variable management

---

## Testing

Run syntax check on all modules:
```bash
python3 -m py_compile eml/web/*.py eml/web_ui.py
```

Start the UI server:
```bash
uv run python eml/eml_automator.py --ui
```

Access at: `http://127.0.0.1:8080`
