#!/usr/bin/env python3
"""
Web UI for CRM Automator using NiceGUI
Phase 1 MVP: Dashboard, Upload/Process, Suppressed Browser
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import asyncio
import threading
import logging
import tempfile
import sqlite3
from contextlib import contextmanager

from nicegui import ui, app
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px

# Import CRM Automator components
try:
    from eml.eml_automator import EMLProcessor
    from eml.crm_client import RealTimeXClient
    from eml.intelligence import IntelligenceLayer
    from eml.persistence import PersistenceLayer
except ImportError:
    try:
        from eml_automator import EMLProcessor
        from crm_client import RealTimeXClient
        from intelligence import IntelligenceLayer
        from persistence import PersistenceLayer
    except ImportError:
        sys.path.insert(0, os.path.dirname(__file__))
        from eml_automator import EMLProcessor
        from crm_client import RealTimeXClient
        from intelligence import IntelligenceLayer
        from persistence import PersistenceLayer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 20_000_000  # 20MB
MAX_UPLOAD_FILES_DISPLAY = 10
MAX_LOG_LINES = 50
DEFAULT_LIMIT = 100
TOP_DOMAINS_LIMIT = 10
TIMER_INTERVAL = 1.0  # seconds
HEADER_HEIGHT = 56  # pixels



# Refactored Modules
from eml.web.state import state, WebUILogHandler
from eml.web.components import (
    apply_nexus_theme,
    status_badge,
    create_header_with_tabs,
    create_stat_card,
    create_recent_activity_item,
    create_empty_state
)
from eml.web.analytics import (
    AnalyticsEngine,
    get_database_stats,
    get_suppressed_emails,
    get_suppression_stats
)
from eml.web.config import ConfigManager

async def process_files_async(files: List[Path], force: bool = False, verbose: bool = False):
    """Process uploaded files asynchronously"""
    state.is_processing = True
    state.progress = 0
    state.total = len(files)
    state.logs = []

    # Set up custom log handler to capture logs in real-time
    web_handler = WebUILogHandler(state)
    web_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Add handler to root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.addHandler(web_handler)

    # Initialize components
    load_dotenv()

    try:
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Initializing CRM Automator...")

        crm_client = RealTimeXClient(
            api_key=os.getenv("CRM_API_KEY"),
            base_url=os.getenv("CRM_API_BASE_URL")
        )
        intelligence = IntelligenceLayer()
        persistence = PersistenceLayer()
        processor = EMLProcessor(crm_client, intelligence, persistence)

        state.stats["processed"] = 0
        state.stats["suppressed"] = 0
        state.stats["failed"] = 0

        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Initialized. Processing {len(files)} file(s)...")

        for idx, file_path in enumerate(files):
            state.current_file = file_path.name
            state.progress = idx

            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📧 Processing {file_path.name}...")

            try:
                # Process in a thread to avoid blocking
                result = await asyncio.to_thread(
                    processor.process,
                    str(file_path),
                    force=force
                )

                if result:
                    state.stats["processed"] += 1
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Processed {file_path.name}")
                else:
                    state.stats["suppressed"] += 1
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⊘ Suppressed {file_path.name}")

            except Exception as e:
                state.stats["failed"] += 1
                state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {file_path.name} - {str(e)}")

            await asyncio.sleep(0.1)  # Allow UI updates

        state.progress = state.total
        state.current_file = "Complete"
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 Processing complete!")
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Processed: {state.stats['processed']}, Suppressed: {state.stats['suppressed']}, Failed: {state.stats['failed']}")

    except Exception as e:
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 Fatal error: {str(e)}")
        logger.error(f"Fatal error in process_files_async: {e}", exc_info=True)

    finally:
        # Remove the log handler to prevent memory leaks
        root_logger.removeHandler(web_handler)
        web_handler.close()

        state.is_processing = False
        # Clean up temporary files
        state.cleanup_files()


def show_processing_detail(log_entry: Dict[str, Any], modal_state: Dict[str, bool] = None):
    """Show detailed processing information in a modal dialog"""
    # Track modal state for auto-refresh coordination
    if modal_state is not None:
        modal_state['value'] = True

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-5xl h-[90vh] flex flex-col overflow-hidden p-0'):
        # Header with close button
        with ui.row().classes('w-full justify-between items-start p-4 border-b border-white/10 shrink-0'):
            with ui.column().classes('flex-1'):
                subject = log_entry.get('subject', 'No Subject')
                ui.label(subject).classes('text-xl font-bold text-white mb-2')

                with ui.row().classes('gap-4 text-xs text-gray-400'):
                    sender = log_entry.get('sender', 'Unknown')
                    ui.label(f"From: {sender}")

                    email_date = log_entry.get('email_date', '')
                    if email_date:
                        ui.label(f"Date: {email_date[:16]}")

                    file_name = log_entry.get('file_name', '')
                    if file_name:
                        ui.label(f"File: {file_name}")

            def close_modal():
                """Close modal and update state"""
                if modal_state is not None:
                    modal_state['value'] = False
                dialog.close()

            ui.button(icon='close', on_click=close_modal).props('flat round').classes('text-gray-400')

        # Fixed Tabs (shrink-0 prevents them from growing)
        with ui.tabs().classes('w-full shrink-0 border-b border-white/5 !h-12 text-gray-400') \
            .props('dense no-caps indicator-color="blue-400" active-color="blue-400"') as tabs:
            overview_tab = ui.tab('Overview', icon='info')
            ai_tab = ui.tab('AI Analysis', icon='psychology')
            crm_tab = ui.tab('CRM Integration', icon='business')
            error_tab = ui.tab('Error Details', icon='error')

        # Scrollable Panels (flex-1 takes remaining height)
        with ui.tab_panels(tabs, value=overview_tab).classes('w-full flex-1 min-h-0 overflow-y-auto bg-transparent p-6'):
            # OVERVIEW TAB
            with ui.tab_panel(overview_tab):
                with ui.column().classes('gap-4 w-full'):
                    # Status Card
                    with ui.card().classes('w-full bg-blue-900/20 border border-blue-500/20'):
                        ui.label('Processing Status').classes('text-xs font-bold text-blue-400 uppercase mb-3')

                        status = log_entry.get('status', 'unknown')
                        with ui.row().classes('items-center gap-3 mb-3'):
                            status_badge(status, status)

                            duration = log_entry.get('processing_duration_ms', 0)
                            if duration:
                                ui.label(f"Duration: {duration}ms").classes('text-xs text-gray-400')

                        started_at = log_entry.get('processing_started_at', '')
                        completed_at = log_entry.get('processing_completed_at', '')

                        with ui.column().classes('gap-2 mt-3'):
                            if started_at:
                                ui.label(f"Started: {started_at}").classes('text-xs text-gray-400')
                            if completed_at:
                                ui.label(f"Completed: {completed_at}").classes('text-xs text-gray-400')

                    # Email Metadata
                    with ui.card().classes('w-full bg-purple-900/20 border border-purple-500/20'):
                        ui.label('Email Metadata').classes('text-xs font-bold text-purple-400 uppercase mb-3')

                        with ui.column().classes('gap-2'):
                            recipient = log_entry.get('recipient', '')
                            if recipient:
                                ui.label(f"To: {recipient}").classes('text-sm text-gray-300')

                            message_id = log_entry.get('message_id', '')
                            if message_id:
                                ui.label(f"Message ID: {message_id}").classes('text-xs text-gray-400 font-mono break-all')

                            file_path = log_entry.get('file_path', '')
                            if file_path:
                                ui.separator().classes('border-white/5 my-2')
                                ui.label('File Path').classes('text-xs text-gray-400 font-bold uppercase mb-1')
                                ui.label(file_path).classes('text-xs text-indigo-300 font-mono bg-black/20 p-2 rounded break-all')

            # AI ANALYSIS TAB
            with ui.tab_panel(ai_tab):
                with ui.column().classes('gap-4 w-full'):
                    ai_summary = log_entry.get('ai_summary', '')
                    suppression_category = log_entry.get('suppression_category', '')
                    suppression_reason = log_entry.get('suppression_reason', '')

                    if ai_summary or suppression_category or suppression_reason:
                        # AI Summary
                        if ai_summary:
                            with ui.card().classes('w-full bg-indigo-900/20 border border-indigo-500/20'):
                                ui.label('AI Analysis Summary').classes('text-xs font-bold text-indigo-400 uppercase mb-3')

                                try:
                                    import json
                                    summary_data = json.loads(ai_summary)
                                    ui.json_editor({'content': {'json': summary_data}}).classes('w-full')
                                except:
                                    ui.label(ai_summary).classes('text-sm text-gray-300 leading-relaxed whitespace-pre-wrap')

                        # Suppression Info
                        if suppression_category or suppression_reason:
                            with ui.card().classes('w-full bg-yellow-900/20 border border-yellow-500/20'):
                                ui.label('Suppression Details').classes('text-xs font-bold text-yellow-400 uppercase mb-3')

                                if suppression_category:
                                    with ui.row().classes('items-center gap-2 mb-2'):
                                        ui.label('Category:').classes('text-xs text-gray-400 font-bold')
                                        ui.label(suppression_category.upper()).classes('px-3 py-1 bg-yellow-500/20 rounded-full text-xs font-bold text-yellow-400')

                                if suppression_reason:
                                    ui.label('Reason:').classes('text-xs text-gray-400 font-bold mb-1')
                                    ui.label(suppression_reason).classes('text-sm text-gray-300 leading-relaxed')
                    else:
                        with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                            ui.icon('psychology', size='xl').classes('text-gray-400')
                            ui.label('No AI analysis data available').classes('text-sm text-gray-500')

            # CRM INTEGRATION TAB
            with ui.tab_panel(crm_tab):
                with ui.column().classes('gap-4 w-full'):
                    contacts_created = log_entry.get('crm_contacts_created', 0)
                    companies_created = log_entry.get('crm_companies_created', 0)
                    activities_created = log_entry.get('crm_activities_created', 0)
                    crm_error = log_entry.get('crm_error', '')

                    if contacts_created or companies_created or activities_created or crm_error:
                        # CRM Results
                        with ui.card().classes('w-full bg-green-900/20 border border-green-500/20'):
                            ui.label('CRM Results').classes('text-xs font-bold text-green-400 uppercase mb-3')

                            with ui.row().classes('gap-6 mb-3'):
                                with ui.column().classes('items-center'):
                                    ui.label(str(contacts_created)).classes('text-3xl font-bold text-green-400')
                                    ui.label('Contacts').classes('text-xs text-gray-400')

                                with ui.column().classes('items-center'):
                                    ui.label(str(companies_created)).classes('text-3xl font-bold text-green-400')
                                    ui.label('Companies').classes('text-xs text-gray-400')

                                with ui.column().classes('items-center'):
                                    ui.label(str(activities_created)).classes('text-3xl font-bold text-green-400')
                                    ui.label('Activities').classes('text-xs text-gray-400')

                        # CRM Payloads
                        ui.label('Payloads').classes('text-xs font-bold text-blue-400 uppercase mt-4 mb-2')
                        
                        payloads = [
                            ("Contacts Payload", log_entry.get('crm_contacts_payload'), contacts_created),
                            ("Companies Payload", log_entry.get('crm_companies_payload'), companies_created),
                            ("Activities Payload", log_entry.get('crm_activities_payload'), activities_created),
                            ("Deals Payload", log_entry.get('crm_deals_payload'), log_entry.get('crm_deals_created', 0)),
                            ("Tasks Payload", log_entry.get('crm_tasks_payload'), log_entry.get('crm_tasks_created', 0))
                        ]

                        for label, payload_json, count in payloads:
                            if payload_json:
                                with ui.expansion(f"{label} ({count} items)", icon="code").classes("w-full bg-blue-900/10 border border-blue-500/20 rounded mb-2"):
                                    try:
                                        import json
                                        data = json.loads(payload_json)
                                        ui.json_editor({'content': {'json': data}}).classes('w-full')
                                    except:
                                        ui.label(str(payload_json)).classes('text-xs font-mono whitespace-pre-wrap p-2')
                            elif count > 0:
                                    # Show empty payload warning if count > 0 but no payload (legacy records)
                                    with ui.expansion(f"{label} ({count} items - Legacy)", icon="warning").classes("w-full bg-orange-900/10 border border-orange-500/20 rounded mb-2"):
                                        ui.label("Payload data not available for this record.").classes("text-xs text-gray-400 p-2")

                        # CRM Error
                        if crm_error:
                            with ui.card().classes('w-full bg-red-900/20 border border-red-500/20'):
                                ui.label('CRM Error').classes('text-xs font-bold text-red-400 uppercase mb-3')
                                ui.label(crm_error).classes('text-sm text-red-300 leading-relaxed whitespace-pre-wrap')
                    else:
                        with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                            ui.icon('business', size='xl').classes('text-gray-400')
                            ui.label('No CRM integration data').classes('text-sm text-gray-500')

            # ERROR DETAILS TAB
            with ui.tab_panel(error_tab):
                with ui.column().classes('gap-4 w-full'):
                    error_message = log_entry.get('error_message', '')
                    error_type = log_entry.get('error_type', '')
                    error_traceback = log_entry.get('error_traceback', '')

                    if error_message or error_type or error_traceback:
                        with ui.card().classes('w-full bg-red-900/20 border border-red-500/20'):
                            ui.label('Error Information').classes('text-xs font-bold text-red-400 uppercase mb-3')

                            if error_type:
                                ui.label(f"Error Type: {error_type}").classes('text-sm font-bold text-red-300 mb-2')

                            if error_message:
                                ui.label('Message:').classes('text-xs text-gray-400 font-bold mb-1')
                                ui.label(error_message).classes('text-sm text-red-300 mb-3 leading-relaxed')

                            if error_traceback:
                                ui.label('Traceback:').classes('text-xs text-gray-400 font-bold mb-1')
                                ui.label(error_traceback).classes('text-xs text-gray-400 font-mono bg-black/40 p-3 rounded whitespace-pre-wrap overflow-x-auto')
                    else:
                        with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                            ui.icon('check_circle', size='xl').classes('text-green-400')
                            ui.label('No errors - Processing completed successfully').classes('text-sm text-green-400')

        # Ensure modal state resets when dialog closes (any method: button, backdrop, ESC)
        if modal_state is not None:
            # Use Quasar's 'hide' event which fires on all close methods
            dialog.on('hide', lambda: modal_state.__setitem__('value', False))

        dialog.open()


@ui.page('/')
def main_page():
    """Main page with tabbed interface (email-archiver style)"""
    app_dark_mode = apply_nexus_theme()

    # Create header with tabs
    tabs, dashboard_tab, upload_tab, analytics_tab, suppressed_tab, config_tab = create_header_with_tabs(app_dark_mode)

    # Page Visibility API - Pause auto-refresh when tab is not visible to save resources
    page_is_visible = {'value': True}  # Track if page is visible

    # Setup Page Visibility API listener
    ui.run_javascript('''
        // Page Visibility API to detect when user switches tabs
        document.addEventListener('visibilitychange', () => {
            const isVisible = !document.hidden;
            // Store visibility state in window object for access from Python
            window.pageIsVisible = isVisible;
        });
        // Initialize
        window.pageIsVisible = !document.hidden;
    ''')

    # Timer to sync visibility state from JavaScript to Python
    async def sync_visibility_state():
        """Sync page visibility state from JavaScript to Python"""
        visible = await ui.run_javascript('return window.pageIsVisible;')
        page_is_visible['value'] = visible if visible is not None else True

    ui.timer(2.0, sync_visibility_state)  # Check every 2 seconds

    # Main content with tab panels
    with ui.tab_panels(tabs, value=dashboard_tab).classes('w-full flex-1 bg-transparent'):
        # ========== DASHBOARD TAB ==========
        with ui.tab_panel(dashboard_tab):
            with ui.column().classes('w-full p-6 gap-6'):
                # Stats overview
                stats = get_database_stats()
                total = stats['total'] if stats['total'] > 0 else 1  # Avoid division by zero

                # Calculate percentages for visual consistency
                processed_pct = (stats['processed'] / total * 100) if total > 0 else 0
                suppressed_pct = (stats['suppressed'] / total * 100) if total > 0 else 0
                failed_pct = (stats['failed'] / total * 100) if total > 0 else 0

                # Enhanced stat cards with icons (all with 3rd row for visual balance)
                with ui.row().classes('w-full gap-4 mb-6'):
                    create_stat_card('TOTAL EMAILS', stats['total'], 'mail',
                                   trend='neutral',
                                   trend_value='All emails')
                    create_stat_card('PROCESSED', stats['processed'], 'check_circle',
                                   trend='up' if stats['processed'] > 0 else 'neutral',
                                   trend_value=f"{processed_pct:.0f}% of total")
                    create_stat_card('SUPPRESSED', stats['suppressed'], 'block',
                                   trend='neutral',
                                   trend_value=f"{suppressed_pct:.0f}% filtered")
                    create_stat_card('FAILED', stats['failed'], 'error',
                                   trend='neutral' if stats['failed'] == 0 else 'down',
                                   trend_value=f"{failed_pct:.0f}% errors" if stats['failed'] > 0 else '0% errors')

                # Recent Activity - Full width with search and pagination
                with ui.card().classes('w-full p-0 gap-0'):
                    # State for auto-refresh
                    auto_refresh_enabled = {'value': True}
                    last_refresh_time = {'value': datetime.now()}
                    modal_is_open = {'value': False}  # Track if detail modal is open

                    # Header with title and controls
                    with ui.row().classes('p-4 border-b border-white/10 items-center justify-between'):
                        ui.label('RECENT ACTIVITY').classes('text-sm font-bold tracking-wide text-white')

                        # Auto-refresh controls
                        with ui.row().classes('gap-2 items-center'):
                            # Last refresh indicator
                            refresh_indicator = ui.label().classes('text-xs text-gray-500')

                            def update_refresh_indicator():
                                if not auto_refresh_enabled['value']:
                                    refresh_indicator.text = 'Auto-refresh disabled'
                                elif modal_is_open['value']:
                                    refresh_indicator.text = 'Auto-refresh paused (modal open)'
                                else:
                                    elapsed = (datetime.now() - last_refresh_time['value']).seconds
                                    refresh_indicator.text = f'Updated {elapsed}s ago'

                            # Update indicator every second
                            ui.timer(1.0, update_refresh_indicator)

                            # Auto-refresh toggle
                            def toggle_auto_refresh(e):
                                auto_refresh_enabled['value'] = e.value
                                if e.value:
                                    # Immediately refresh when enabled
                                    load_activity(current_page['value'], search_input.value or '')

                            ui.switch(value=True, on_change=toggle_auto_refresh) \
                                .props('dense color=primary') \
                                .classes('ml-2') \
                                .tooltip('Toggle auto-refresh (5s interval)')

                    # Search and filters
                    with ui.row().classes('px-4 py-3 gap-2 border-b border-white/10'):
                        search_input = ui.input('Search emails...',
                                              on_change=lambda: handle_search()) \
                                      .props('outlined dense debounce="500" clearable') \
                                      .classes('flex-1')

                    # State for pagination
                    current_page = {'value': 1}
                    items_per_page = 10
                    activity_container = ui.column().classes('w-full')

                    def load_activity(page: int = 1, search_query: str = ''):
                        """Load activity with pagination and search"""
                        activity_container.clear()

                        # Update last refresh time
                        last_refresh_time['value'] = datetime.now()

                        try:
                            db = PersistenceLayer()

                            # Calculate offset
                            offset = (page - 1) * items_per_page

                            # Get total count for pagination
                            with sqlite3.connect(db.db_path) as conn:
                                cursor = conn.cursor()

                                # Build query with search
                                if search_query:
                                    count_query = """
                                        SELECT COUNT(*) FROM processing_log
                                        WHERE subject LIKE ? OR sender LIKE ? OR recipient LIKE ?
                                    """
                                    search_pattern = f'%{search_query}%'
                                    cursor.execute(count_query, (search_pattern, search_pattern, search_pattern))
                                else:
                                    count_query = "SELECT COUNT(*) FROM processing_log"
                                    cursor.execute(count_query)

                                total_count = cursor.fetchone()[0]
                                total_pages = max(1, (total_count + items_per_page - 1) // items_per_page)

                                # Get items for current page
                                if search_query:
                                    data_query = """
                                        SELECT * FROM processing_log
                                        WHERE subject LIKE ? OR sender LIKE ? OR recipient LIKE ?
                                        ORDER BY processing_started_at DESC
                                        LIMIT ? OFFSET ?
                                    """
                                    cursor.execute(data_query, (search_pattern, search_pattern, search_pattern, items_per_page, offset))
                                else:
                                    data_query = """
                                        SELECT * FROM processing_log
                                        ORDER BY processing_started_at DESC
                                        LIMIT ? OFFSET ?
                                    """
                                    cursor.execute(data_query, (items_per_page, offset))

                                # Convert to dict
                                columns = [desc[0] for desc in cursor.description]
                                recent_items = [dict(zip(columns, row)) for row in cursor.fetchall()]

                            with activity_container:
                                if recent_items:
                                    # Header
                                    with ui.row().classes('w-full px-4 py-2 border-b border-white/10 text-xs font-bold text-gray-400 uppercase tracking-wider'):
                                        ui.label('Subject').classes('flex-[2]')
                                        ui.label('Sender').classes('flex-[1]')
                                        ui.label('Status').classes('w-24 text-center')
                                        ui.label('Time').classes('w-24 text-right')

                                    # Rows with click handler
                                    for item in recent_items:
                                        status = item.get('status') or 'skipped'
                                        subject = item.get('subject') or 'No Subject'
                                        sender = item.get('sender') or 'Unknown'

                                        # Format timestamp
                                        timestamp = item.get('processing_started_at') or ''
                                        time_str = '-'
                                        if timestamp:
                                            try:
                                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                                time_str = dt.strftime('%H:%M')
                                            except:
                                                pass

                                        # Clickable row
                                        with ui.row().classes('w-full px-4 py-3 border-b border-white/5 items-center hover:bg-white/5 transition-colors cursor-pointer').on('click', lambda i=item: show_processing_detail(i, modal_is_open)):
                                            subject_display = subject if len(subject) <= 60 else subject[:60] + '...'
                                            sender_display = sender if len(sender) <= 30 else sender[:30] + '...'

                                            ui.label(subject_display).classes('flex-[2] font-medium text-sm truncate pr-2 text-white')
                                            ui.label(sender_display).classes('flex-[1] text-xs text-gray-400 truncate pr-2')
                                            with ui.element('div').classes('w-24 flex justify-center'):
                                                status_badge(status, status)
                                            ui.label(time_str).classes('w-24 text-right text-xs text-gray-500 font-mono')

                                    # Pagination
                                    if total_pages > 1:
                                        with ui.row().classes('w-full p-4 justify-center border-t border-white/10'):
                                            ui.pagination(
                                                min=1,
                                                max=total_pages,
                                                value=current_page['value'],
                                                direction_links=True,
                                                on_change=lambda e: handle_page_change(e.value)
                                            )

                                else:
                                    # Empty state
                                    with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                                        ui.icon('inbox', size='xl').classes('text-gray-400')
                                        if search_query:
                                            ui.label('No matching emails found').classes('text-h6 text-gray-500')
                                            ui.label('Try a different search term').classes('text-caption text-gray-600 text-center')
                                        else:
                                            ui.label('No Activity Yet').classes('text-h6 text-gray-500')
                                            ui.label('Start fresh! Upload emails to begin processing.').classes('text-caption text-gray-600 text-center')

                        except Exception as e:
                            with activity_container:
                                ui.label(f'Error loading activity: {e}').classes('text-negative text-caption')

                    def handle_page_change(page: int):
                        """Handle pagination change"""
                        current_page['value'] = page
                        load_activity(page, search_input.value or '')

                    def handle_search():
                        """Handle search input"""
                        current_page['value'] = 1  # Reset to first page
                        load_activity(1, search_input.value or '')

                    # Connect search input (Enter key support)
                    search_input.on('keydown.enter', handle_search)

                    # Initial load
                    load_activity()

                    # Auto-refresh timer (5 second interval)
                    def auto_refresh():
                        """Automatically refresh activity if enabled, modal is closed, and page is visible"""
                        if auto_refresh_enabled['value'] and not modal_is_open['value'] and page_is_visible['value']:
                            load_activity(current_page['value'], search_input.value or '')

                    ui.timer(5.0, auto_refresh)

        # ========== UPLOAD TAB ==========
        with ui.tab_panel(upload_tab):
            with ui.column().classes('w-full p-6 gap-4'):
                # File upload area - Drag & Drop
                with ui.card().classes('w-full mb-4'):
                    uploaded_files_list = ui.column().classes('w-full')

                    async def handle_upload(e):
                        """Handle file upload"""
                        # Check for file attribute (files might be rejected if too large)
                        if not hasattr(e, 'file'):
                            logger.warning(f"Upload event missing file. Attributes: {dir(e)}")
                            ui.notify(f"File could not be processed (possibly rejected/too large).", type='negative')
                            return

                        # e.file is a FileUpload object which contains name, content etc.
                        file_obj = e.file
                        if file_obj.name.endswith('.eml'):
                            # Save to temp directory (cross-platform)
                            temp_dir = Path(tempfile.gettempdir())
                            temp_path = temp_dir / file_obj.name
                            with open(temp_path, 'wb') as f:
                                # Use async read() method mandated by NiceGUI FileUpload interface
                                file_data = await file_obj.read()
                                f.write(file_data)
                            state.uploaded_files.append(temp_path)
                            logger.info(f"Uploaded file saved to: {temp_path}")

                        # Update file list display
                        uploaded_files_list.clear()
                        with uploaded_files_list:
                            ui.label(f'✓ Selected {len(state.uploaded_files)} files').classes('text-positive font-medium mb-3')
                            for file in state.uploaded_files[:MAX_UPLOAD_FILES_DISPLAY]:
                                with ui.row().classes('items-center gap-2 p-2 bg-grey-1 rounded'):
                                    ui.icon('description', size='sm').classes('text-primary')
                                    ui.label(file.name).classes('text-sm')
                            if len(state.uploaded_files) > MAX_UPLOAD_FILES_DISPLAY:
                                ui.label(f'...and {len(state.uploaded_files) - MAX_UPLOAD_FILES_DISPLAY} more').classes('text-caption text-gray-400 mt-2')

                    # Drag & drop upload area
                    with ui.column().classes('w-full items-center justify-center p-12 cursor-pointer border-2 border-dashed border-white/20 rounded-xl bg-white/5 hover:bg-white/10 transition-colors'):
                        ui.icon('cloud_upload', size='xl').classes('text-primary mb-3')
                        ui.label('Drag & drop EML files here').classes('text-h6 font-medium mb-1 text-white')
                        ui.label('or click to browse').classes('text-caption text-gray-400 mb-4')

                        upload_element = ui.upload(
                            on_upload=handle_upload,
                            multiple=True,
                            auto_upload=True,
                            label='Choose Files',
                            max_file_size=MAX_FILE_SIZE
                        ).props('accept=.eml color=primary flat').classes('w-full max-w-xs')

                # Processing options
                with ui.card().classes('w-full mb-4'):
                    ui.label('Processing Options').classes('text-h6 mb-2')
                    force_checkbox = ui.checkbox('Force reprocessing (ignore persistence)')
                    verbose_checkbox = ui.checkbox('Verbose logging')

                # Control buttons
                with ui.row().classes('gap-2 mb-4'):
                    async def start_processing():
                        """Start processing uploaded files"""
                        if not state.uploaded_files:
                            ui.notify('Please upload files first', type='warning')
                            return

                        if state.is_processing:
                            ui.notify('Processing already in progress', type='warning')
                            return

                        ui.notify('Starting processing...', type='info')
                        await process_files_async(
                            state.uploaded_files,
                            force=force_checkbox.value,
                            verbose=verbose_checkbox.value
                        )

                    with ui.button('Start Processing',
                             on_click=start_processing,
                             icon='play_arrow').props('color=primary unelevated').bind_enabled_from(state, 'is_processing', lambda x: not x):
                         ui.tooltip('Begin processing all uploaded EML files')

                    def clear_all_files():
                        state.uploaded_files.clear()
                        uploaded_files_list.clear()  # Clear the visual list
                        upload_element.reset()       # Reset the upload component

                    with ui.button('Clear Files',
                             on_click=clear_all_files,
                             icon='clear').props('color=grey-7 outline').bind_enabled_from(state, 'is_processing', lambda x: not x):
                         ui.tooltip('Remove all files from the upload list')

                # Progress indicator
                progress_card = ui.card().classes('w-full mb-4')
                with progress_card:
                    ui.label('Progress').classes('text-h6 mb-2')
                    progress_label = ui.label().bind_text_from(state, 'current_file',
                                                                lambda x: f'Processing: {x}' if state.is_processing else 'Idle')
                    progress_bar = ui.linear_progress().props('instant-feedback').classes('w-full')
                    progress_bar.bind_value_from(state, 'progress',
                                                 lambda p: p / state.total if state.total > 0 else 0)

                    stats_label = ui.label().bind_text_from(state, 'progress',
                                                             lambda p: f'{p} / {state.total}' if state.total > 0 else '0 / 0')

                # Live logs
                with ui.card().classes('w-full'):
                    ui.label('LIVE LOGS').classes('text-xs font-bold text-gray-400 uppercase tracking-wider mb-2')
                    log_container = ui.column().classes('w-full bg-gray-900 p-4 rounded font-mono text-xs text-gray-300').style('max-height: 400px; overflow-y: auto')

                    # Track number of logs already displayed for efficient appending
                    displayed_log_count = {'value': 0}

                    # Auto-update logs (only when processing)
                    def update_logs():
                        """Efficiently append only new log entries instead of rebuilding entire container"""
                        current_log_count = len(state.logs)

                        # If log count decreased (e.g., cleared), rebuild from scratch
                        if current_log_count < displayed_log_count['value']:
                            log_container.clear()
                            displayed_log_count['value'] = 0

                        # Get logs to display (last MAX_LOG_LINES)
                        logs_to_show = state.logs[-MAX_LOG_LINES:]

                        # If we're showing fewer logs than displayed, rebuild
                        if len(logs_to_show) < displayed_log_count['value']:
                            log_container.clear()
                            with log_container:
                                for log in logs_to_show:
                                    ui.label(log).classes('font-mono text-sm')
                            displayed_log_count['value'] = len(logs_to_show)
                        else:
                            # Append only new logs
                            new_logs = logs_to_show[displayed_log_count['value']:]
                            if new_logs:
                                with log_container:
                                    for log in new_logs:
                                        ui.label(log).classes('font-mono text-sm')
                                displayed_log_count['value'] = len(logs_to_show)

                        # Auto-scroll to bottom to show latest logs (only if new logs were added)
                        if displayed_log_count['value'] > 0:
                            ui.run_javascript(f'''
                                const container = document.getElementById('{log_container.id}');
                                if (container) {{
                                    container.scrollTop = container.scrollHeight;
                                }}
                            ''')

                    # Timer only active when processing and page is visible
                    ui.timer(TIMER_INTERVAL, update_logs, active=lambda: state.is_processing and page_is_visible['value'])

        # ========== ANALYTICS TAB ==========
        with ui.tab_panel(analytics_tab):
            with ui.column().classes('w-full p-6 gap-4'):
                analytics = AnalyticsEngine()

                # Page header
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Analytics & Reports').classes('text-h4 font-bold')
                    ui.icon('bar_chart', size='lg').classes('text-primary')

                # Date range selector and refresh
                with ui.row().classes('gap-2 mb-4'):
                    date_range_select = ui.select(
                        ['Last 7 Days', 'Last 30 Days', 'Last 90 Days'],
                        value='Last 30 Days',
                        label='Date Range'
                    )
                    # Refresh button (will be connected later)
                    refresh_button = ui.button('Refresh Data', icon='refresh').props('outline')
                    with refresh_button:
                        ui.tooltip('Reload analytics data')

                # Overview cards with charts
                overview_charts_container = ui.row().classes('w-full gap-4 mb-4')

                # Category breakdown
                category_container = ui.card().classes('w-full mb-4')

                # Timeline chart
                timeline_container = ui.card().classes('w-full mb-4')

                # Two column layout for remaining charts
                bottom_charts_container = ui.row().classes('w-full gap-4')

                # Define refresh function
                def refresh_analytics_data():
                    """Refresh all analytics charts without page reload"""
                    # Clear all containers
                    overview_charts_container.clear()
                    category_container.clear()
                    timeline_container.clear()
                    bottom_charts_container.clear()

                    # Reload overview charts
                    with overview_charts_container:
                        with ui.card().classes('flex-1'):
                            stats = analytics.get_processing_stats()
                            pie_chart = analytics.create_processing_pie_chart(stats)
                            ui.plotly(pie_chart).classes('w-full')

                        with ui.card().classes('flex-1'):
                            gauge_chart = analytics.create_success_gauge_chart(stats)
                            ui.plotly(gauge_chart).classes('w-full')

                    # Reload category breakdown
                    with category_container:
                        category_data = analytics.get_suppression_breakdown()
                        if category_data:
                            category_chart = analytics.create_category_bar_chart(category_data)
                            ui.plotly(category_chart).classes('w-full')
                        else:
                            ui.label('No suppression data available yet').classes('text-gray-400 p-4')

                    # Reload timeline chart
                    with timeline_container:
                        days_map = {'Last 7 Days': 7, 'Last 30 Days': 30, 'Last 90 Days': 90}
                        days = days_map.get(date_range_select.value, 30)

                        timeline_data = analytics.get_timeline_data(days=days)
                        if timeline_data['dates']:
                            timeline_chart = analytics.create_timeline_chart(timeline_data)
                            ui.plotly(timeline_chart).classes('w-full')
                        else:
                            ui.label('No timeline data available yet').classes('text-gray-400 p-4')

                    # Reload bottom charts
                    with bottom_charts_container:
                        # Top suppressed domains
                        with ui.card().classes('flex-1'):
                            top_domains = analytics.get_top_suppressed_domains(limit=10)
                            if top_domains:
                                domains_chart = analytics.create_top_domains_chart(top_domains)
                                ui.plotly(domains_chart).classes('w-full')
                            else:
                                ui.label('Top Suppressed Domains').classes('text-h6 mb-2')
                                ui.label('No suppression data available yet').classes('text-gray-400 p-4')

                        # Suppression by reason
                        with ui.card().classes('flex-1'):
                            reason_data = analytics.get_reason_breakdown()
                            if reason_data:
                                ui.label('Suppression by Reason').classes('text-h6 mb-2')

                                # Create simple bar chart for reasons
                                reasons = list(reason_data.keys())
                                counts = list(reason_data.values())

                                reason_fig = go.Figure(data=[go.Bar(
                                    x=counts,
                                    y=reasons,
                                    orientation='h',
                                    marker=dict(color='#9C27B0', line=dict(color='#7B1FA2', width=1)),
                                    text=counts,
                                    textposition='outside'
                                )])

                                reason_fig.update_layout(
                                    title='Top 10 Suppression Reasons',
                                    xaxis_title='Count',
                                    yaxis_title='Reason',
                                    height=max(300, len(reasons) * 30),
                                    margin=dict(t=40, b=40, l=200, r=40),
                                    showlegend=False
                                )

                                ui.plotly(reason_fig).classes('w-full')
                            else:
                                ui.label('Suppression by Reason').classes('text-h6 mb-2')
                                ui.label('No reason data available yet').classes('text-gray-400 p-4')

                    ui.notify('Analytics data refreshed', type='positive')

                # Connect refresh button
                refresh_button.on('click', refresh_analytics_data)

                # Auto-refresh timeline when date range changes
                date_range_select.on('update:model-value', refresh_analytics_data)

                # Initial load
                refresh_analytics_data()

        # ========== CONFIG TAB ==========
        with ui.tab_panel(config_tab):
            with ui.column().classes('w-full p-6 gap-4'):
                # Try to get custom env_path from storage
                custom_env = app.storage.user.get('env_path')
                config_manager = ConfigManager(env_path=custom_env) if custom_env else ConfigManager()
                current_config = config_manager.load_config()

                # State for form inputs
                form_data = {}

                # Page header
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Configuration').classes('text-h4 font-bold')
                    ui.icon('settings', size='lg').classes('text-primary')

                # Status messages
                status_message = ui.label().classes('mb-4')

                # CRM API Settings
                with ui.card().classes('w-full mb-4'):
                    ui.label('CRM API Settings').classes('text-h6 mb-3')

                    form_data['CRM_API_BASE_URL'] = ui.input(
                        'CRM API Base URL',
                        value=current_config.get('CRM_API_BASE_URL', ''),
                        placeholder='https://your-project.supabase.co/functions/v1'
                    ).classes('w-full').props('outlined dense')
                    with form_data['CRM_API_BASE_URL']:
                        ui.tooltip('The base endpoint for RealTimeX CRM functions')

                    form_data['CRM_API_KEY'] = ui.input(
                        'CRM API Key',
                        value=current_config.get('CRM_API_KEY', ''),
                        placeholder='ak_live_...',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined dense')
                    with form_data['CRM_API_KEY']:
                        ui.tooltip('Your secret API key from RealTimeX Dashboard')

                    crm_status_label = ui.label().classes('mt-2')

                    async def test_crm():
                        """Test CRM connection"""
                        crm_status_label.text = '⏳ Testing connection...'
                        await asyncio.sleep(0.1)  # Allow UI to update

                        result = await asyncio.to_thread(
                            config_manager.test_crm_connection,
                            form_data['CRM_API_KEY'].value,
                            form_data['CRM_API_BASE_URL'].value
                        )

                        if result['success']:
                            crm_status_label.text = f"✅ {result['message']}"
                            crm_status_label.classes('text-positive')
                            ui.notify('CRM connection successful!', type='positive')
                        else:
                            crm_status_label.text = f"❌ {result['message']}"
                            crm_status_label.classes('text-negative')
                            ui.notify('CRM connection failed', type='negative')

                    ui.button('Test Connection', on_click=test_crm, icon='link').props('outline')

                # LLM Configuration
                with ui.card().classes('w-full mb-4'):
                    ui.label('LLM Configuration').classes('text-h6 mb-3')

                    form_data['LLM_BASE_URL'] = ui.input(
                        'LLM Base URL',
                        value=current_config.get('LLM_BASE_URL', ''),
                        placeholder='https://api.openai.com/v1'
                    ).classes('w-full').props('outlined dense')
                    with form_data['LLM_BASE_URL']:
                         ui.tooltip('API endpoint for the Language Model provider')

                    form_data['LLM_API_KEY'] = ui.input(
                        'LLM API Key',
                        value=current_config.get('LLM_API_KEY', ''),
                        placeholder='sk-proj-...',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined dense')
                    with form_data['LLM_API_KEY']:
                        ui.tooltip('Private key for authenticating with LLM provider')

                    form_data['LLM_MODEL'] = ui.input(
                        'LLM Model',
                        value=current_config.get('LLM_MODEL', 'gpt-4o-mini'),
                        placeholder='gpt-4o-mini'
                    ).classes('w-full').props('outlined dense')
                    with form_data['LLM_MODEL']:
                        ui.tooltip('The AI model name (e.g., gpt-4o, claude-3-5-sonnet)')

                    llm_status_label = ui.label().classes('mt-2')

                    async def test_llm():
                        """Test LLM connection"""
                        llm_status_label.text = '⏳ Testing connection...'
                        await asyncio.sleep(0.1)

                        model = form_data['LLM_MODEL'].value

                        result = await asyncio.to_thread(
                            config_manager.test_llm_connection,
                            form_data['LLM_API_KEY'].value,
                            form_data['LLM_BASE_URL'].value,
                            model
                        )

                        if result['success']:
                            llm_status_label.text = f"✅ {result['message']}"
                            llm_status_label.classes('text-positive')
                            ui.notify('LLM connection successful!', type='positive')
                        else:
                            llm_status_label.text = f"❌ {result['message']}"
                            llm_status_label.classes('text-negative')
                            ui.notify('LLM connection failed', type='negative')

                    ui.button('Test Connection', on_click=test_llm, icon='link').props('outline')

                # Email Filtering
                with ui.card().classes('w-full mb-4'):
                    ui.label('Email Filtering').classes('text-h6 mb-3')

                    form_data['SUPPRESS_CATEGORIES'] = ui.input(
                        'Suppress Categories',
                        value=current_config.get('SUPPRESS_CATEGORIES', 'promotional,newsletter,automated,spam'),
                        placeholder='promotional,newsletter,automated,spam'
                    ).classes('w-full').props('outlined dense')
                    with form_data['SUPPRESS_CATEGORIES']:
                        ui.tooltip('Comma-separated list of categories to exclude')

                    form_data['CLASSIFICATION_STRATEGY'] = ui.select(
                        ['heuristic', 'llm', 'hybrid'],
                        value=current_config.get('CLASSIFICATION_STRATEGY', 'hybrid'),
                        label='Classification Strategy'
                    ).classes('w-full').props('outlined dense')
                    with form_data['CLASSIFICATION_STRATEGY']:
                        ui.tooltip('Method used to categorize incoming emails')

                    with ui.row().classes('w-full gap-2'):
                        ui.label('• Heuristic: Fast, free, ~90% accuracy').classes('text-caption text-gray-400')
                    with ui.row().classes('w-full gap-2'):
                        ui.label('• LLM: Accurate, costs ~$0.0001/email').classes('text-caption text-gray-400')
                    with ui.row().classes('w-full gap-2 mb-3'):
                        ui.label('• Hybrid: Best balance (recommended)').classes('text-caption text-gray-400')

                    form_data['CLASSIFICATION_MODEL'] = ui.input(
                        'Classification Model',
                        value=current_config.get('CLASSIFICATION_MODEL', 'gpt-4o-mini'),
                        placeholder='gpt-4o-mini'
                    ).classes('w-full').props('outlined dense')
                    with form_data['CLASSIFICATION_MODEL']:
                        ui.tooltip('Model used for LLM/Hybrid classification')

                    form_data['ALLOWLIST_DOMAINS'] = ui.input(
                        'Allowlist Domains',
                        value=current_config.get('ALLOWLIST_DOMAINS', ''),
                        placeholder='@important-client.com,vip@partner.com'
                    ).classes('w-full').props('outlined dense')
                    with form_data['ALLOWLIST_DOMAINS']:
                        ui.tooltip('Always process emails from these domains')

                    form_data['SUPPRESS_DOMAINS'] = ui.input(
                        'Blocklist Domains',
                        value=current_config.get('SUPPRESS_DOMAINS', ''),
                        placeholder='@marketing.spam.com,noreply@ads.com'
                    ).classes('w-full').props('outlined dense')
                    with form_data['SUPPRESS_DOMAINS']:
                        ui.tooltip('Always suppress emails from these domains')

                    form_data['LOG_SUPPRESSED'] = ui.checkbox(
                        'Log Suppressed Emails',
                        value=current_config.get('LOG_SUPPRESSED', 'true').lower() == 'true'
                    ).props('dense')
                    with form_data['LOG_SUPPRESSED']:
                        ui.tooltip('Store suppressed emails in the database log')

                # Internal Staff Filtering
                with ui.card().classes('w-full mb-4'):
                    ui.label('Internal Staff Filtering').classes('text-h6 mb-3')
                    ui.label('Exclude internal staff from CRM sync').classes('text-caption text-gray-400 mb-2')

                    form_data['INTERNAL_DOMAINS'] = ui.input(
                        'Internal Domains',
                        value=current_config.get('INTERNAL_DOMAINS', ''),
                        placeholder='mycompany.com,partner.co'
                    ).classes('w-full').props('outlined dense')
                    with form_data['INTERNAL_DOMAINS']:
                        ui.tooltip('Domains to exclude from CRM sync')

                    form_data['INTERNAL_EMAILS'] = ui.input(
                        'Internal Emails',
                        value=current_config.get('INTERNAL_EMAILS', ''),
                        placeholder='admin@gmail.com,ceo@personal.com'
                    ).classes('w-full').props('outlined dense')
                    with form_data['INTERNAL_EMAILS']:
                        ui.tooltip('Specific email addresses to exclude')

                # Search Provider Configuration
                with ui.card().classes('w-full mb-4'):
                    ui.label('Search Provider Configuration').classes('text-h6 mb-3')
                    ui.label('For company enrichment via web search').classes('text-caption text-gray-400 mb-2')

                    form_data['SEARCH_PROVIDERS'] = ui.input(
                        'Search Providers',
                        value=current_config.get('SEARCH_PROVIDERS', 'duckduckgo,serper,serpapi'),
                        placeholder='duckduckgo,serper,serpapi'
                    ).classes('w-full').props('outlined dense')
                    with form_data['SEARCH_PROVIDERS']:
                        ui.tooltip('Priority list of search engines for enrichment')

                    form_data['SERPER_API_KEY'] = ui.input(
                        'Serper API Key',
                        value=current_config.get('SERPER_API_KEY', ''),
                        placeholder='Your Serper.dev API key',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined dense')
                    with form_data['SERPER_API_KEY']:
                        ui.tooltip('API key for Serper.dev Google Search API')

                    form_data['SERPAPI_KEY'] = ui.input(
                        'SerpAPI Key',
                        value=current_config.get('SERPAPI_KEY', ''),
                        placeholder='Your SerpAPI key',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined dense')
                    with form_data['SERPAPI_KEY']:
                        ui.tooltip('API key for SerpAPI Google Search API')

                # Persistence Configuration
                with ui.card().classes('w-full mb-4'):
                    ui.label('Persistence Configuration').classes('text-h6 mb-3')

                    form_data['PERSISTENCE_DB_PATH'] = ui.input(
                        'Database Path',
                        value=current_config.get('PERSISTENCE_DB_PATH', ''),
                        placeholder='./eml_processing.db'
                    ).classes('w-full').props('outlined dense')
                    with form_data['PERSISTENCE_DB_PATH']:
                        ui.tooltip('Path to the SQLite database file')

                    current_db = os.getenv('PERSISTENCE_DB_PATH', './eml_processing.db')
                    ui.label(f'Current: {current_db}').classes('text-caption text-gray-400')

                # Save configuration function
                async def save_configuration():
                    """Save configuration to .env file"""
                    # Collect all form data
                    config_to_save = {}
                    for key, input_field in form_data.items():
                        if hasattr(input_field, 'value'):
                            value = input_field.value or ''
                            config_to_save[key] = value

                    # Validate
                    errors = config_manager.validate_config(config_to_save)
                    if errors:
                        status_message.text = '❌ Validation errors: ' + ', '.join(errors)
                        status_message.classes('text-negative')
                        ui.notify('Validation failed', type='negative')
                        return

                    # Save
                    success, message = config_manager.save_config(config_to_save)
                    if success:
                        status_message.text = f'✅ {message}'
                        status_message.classes('text-positive')
                        ui.notify('Configuration saved successfully!', type='positive')

                        # Reload environment
                        load_dotenv(override=True)
                    else:
                        status_message.text = f'❌ {message}'
                        status_message.classes('text-negative')
                        ui.notify('Save failed', type='negative')

                # Final action buttons (at bottom after all fields)
                with ui.row().classes('gap-2 mt-4'):
                    ui.button('Save Configuration', on_click=save_configuration, icon='save').props('color=primary unelevated')
                    
                    # Import Configuration Dialog
                    with ui.dialog() as import_dialog, ui.card():
                        ui.label('Import Configuration').classes('text-h6')
                        ui.label('Upload an .env file to populate fields').classes('text-caption text-gray-400')
                        
                        async def handle_import(e):
                            try:
                                # Access content via e.file.read() (async)
                                if hasattr(e, 'file'):
                                    content_bytes = await e.file.read()
                                    content = content_bytes.decode('utf-8')
                                else:
                                    # Fallback (unlikely given typical NiceGUI versions > 1.4)
                                    raise Exception("Event has no 'file' attribute")

                                count = 0
                                for line in content.splitlines():
                                    line = line.strip()
                                    if not line or line.startswith('#'):
                                        continue
                                    if '=' in line:
                                        key, value = line.split('=', 1)
                                        key = key.strip()
                                        value = value.strip().strip("'").strip('"')
                                        if key in form_data:
                                            form_data[key].value = value
                                            count += 1
                                
                                ui.notify(f'Imported {count} configuration values', type='positive')
                                import_dialog.close()
                            except Exception as ex:
                                ui.notify(f'Failed to import: {str(ex)}', type='negative')

                        ui.upload(on_upload=handle_import, auto_upload=True).props('accept=.env flat').classes('w-full')
                        ui.button('Close', on_click=import_dialog.close).props('flat')

                    with ui.button('Import Configuration', on_click=import_dialog.open, icon='upload_file').props('outline'):
                        ui.tooltip('Import values from an .env file')

        # ========== SUPPRESSED TAB ==========
        with ui.tab_panel(suppressed_tab):
            with ui.column().classes('w-full p-6 gap-4'):
                # State for auto-refresh
                auto_refresh_enabled_suppressed = {'value': False}  # Disabled by default
                last_refresh_time_suppressed = {'value': datetime.now()}

                # Page header
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Suppressed Emails').classes('text-h4 font-bold')

                    # Auto-refresh controls
                    with ui.row().classes('gap-2 items-center'):
                        ui.icon('filter_list', size='lg').classes('text-primary')

                        # Last refresh indicator
                        refresh_indicator_suppressed = ui.label().classes('text-xs text-gray-500')

                        def update_refresh_indicator_suppressed():
                            if not auto_refresh_enabled_suppressed['value']:
                                refresh_indicator_suppressed.text = 'Auto-refresh disabled'
                            else:
                                elapsed = (datetime.now() - last_refresh_time_suppressed['value']).seconds
                                refresh_indicator_suppressed.text = f'Updated {elapsed}s ago'

                        # Update indicator every second
                        ui.timer(1.0, update_refresh_indicator_suppressed)

                        # Auto-refresh toggle
                        def toggle_auto_refresh_suppressed(e):
                            auto_refresh_enabled_suppressed['value'] = e.value

                        ui.switch(value=False, on_change=toggle_auto_refresh_suppressed) \
                            .props('dense color=primary') \
                            .classes('ml-2') \
                            .tooltip('Toggle auto-refresh (10s interval)')

                # Filters
                search_input = ui.input('Search', placeholder='Search sender or subject...').classes('w-full mb-2')
                category_select = ui.select(
                    ['All', 'promotional', 'newsletter', 'automated', 'spam', 'notification'],
                    value='All',
                    label='Category'
                ).classes('mb-4')

                # Stats summary
                stats = get_suppression_stats()
                with ui.card().classes('w-full mb-4'):
                    ui.label('Suppression Statistics').classes('text-h6 mb-2')
                    with ui.row().classes('gap-4'):
                        if 'by_category' in stats:
                            for category, count in list(stats['by_category'].items())[:5]:
                                with ui.column():
                                    ui.label(category).classes('text-caption text-gray-400')
                                    ui.label(str(count)).classes('text-h6')

                # Email list
                table_container = ui.column().classes('w-full')

                def refresh_table():
                    """Refresh the email table"""
                    # Update last refresh time
                    last_refresh_time_suppressed['value'] = datetime.now()

                    emails = get_suppressed_emails(
                        limit=100,
                        category=category_select.value if category_select.value != 'All' else None,
                        search=search_input.value if search_input.value else None
                    )

                    table_container.clear()
                    with table_container:
                        ui.label(f'Showing {len(emails)} suppressed emails').classes('text-caption text-gray-400 mb-2')

                        if emails:
                            # Header
                            with ui.row().classes('w-full px-4 py-2 border-b border-white/10 text-xs font-bold text-gray-400 uppercase tracking-wider'):
                                ui.label('Date').classes('w-32')
                                ui.label('Sender').classes('flex-[1]')
                                ui.label('Subject').classes('flex-[2]')
                                ui.label('Category').classes('w-32 text-center')
                                ui.label('Reason').classes('flex-[1]')

                            # Rows
                            for email in emails:
                                date_str = email.get('timestamp', '')[:10]
                                sender = email.get('sender', 'Unknown')[:40]
                                subject = email.get('subject', 'No subject')[:50]
                                category = email.get('category', 'unknown')
                                reason = email.get('reason', 'unknown')[:30]

                                with ui.row().classes('w-full px-4 py-3 border-b border-white/5 items-center hover:bg-white/5 transition-colors'):
                                    ui.label(date_str).classes('w-32 text-xs text-gray-500 font-mono')
                                    ui.label(sender).classes('flex-[1] text-xs text-gray-400 truncate pr-2')
                                    ui.label(subject).classes('flex-[2] font-medium text-sm text-white truncate pr-2')
                                    with ui.element('div').classes('w-32 flex justify-center'):
                                          # Use a simple badge for category
                                          ui.label(category).classes('px-2 py-0.5 rounded-full text-[10px] bg-white/10 text-gray-300')
                                    ui.label(reason).classes('flex-[1] text-xs text-gray-500 italic truncate')

                        else:
                            ui.label('No suppressed emails found').classes('text-grey-7 italic')

                # Refresh button
                with ui.button('Refresh', on_click=refresh_table, icon='refresh').props('color=primary unelevated'):
                    ui.tooltip('Reload the list of suppressed emails')

                # Initial load
                refresh_table()

                # Auto-refresh on filter change
                search_input.on('blur', refresh_table)
                category_select.on('update:model-value', refresh_table)

                # Auto-refresh timer (10 second interval - less frequent than Recent Activity)
                def auto_refresh_suppressed():
                    """Automatically refresh suppressed emails if enabled and page is visible"""
                    if auto_refresh_enabled_suppressed['value'] and page_is_visible['value']:
                        refresh_table()

                ui.timer(10.0, auto_refresh_suppressed)


def run_ui(host: str = '127.0.0.1', port: int = 8080, show_browser: bool = False, env_path: str = None):
    """Run the web UI

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to listen on (default: 8080)
        show_browser: Whether to automatically open browser (default: False)
        env_path: Path to custom .env file
    """
    if env_path:
        app.storage.user['env_path'] = env_path

    ui.run(
        host=host,
        port=port,
        title='CRM Automator',
        favicon='📧',
        reload=False,
        show=show_browser,
        storage_secret='crm-automator-secret' # Required for app.storage.user
    )


if __name__ == '__main__':
    try:
        run_ui()
    except KeyboardInterrupt:
        print("\nStopping CRM Automator... Bye!")
        sys.exit(0)
