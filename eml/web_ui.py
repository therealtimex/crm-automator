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
import logging
import tempfile
import uuid

from nicegui import ui, app
from dotenv import load_dotenv
import plotly.graph_objects as go

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
MAX_FILE_SIZE = 20_000_000  # 20MB per file
MAX_UPLOAD_FILES = 50  # Maximum number of files that can be uploaded
MAX_TOTAL_SIZE = 500_000_000  # 500MB total across all files
MAX_LOG_LINES = 50
TIMER_INTERVAL = 1.0  # seconds



# Refactored Modules
from eml.web.state import state, WebUILogHandler
from eml.web.components import (
    apply_nexus_theme,
    status_badge,
    create_header_with_tabs,
    create_stat_card
)
from eml.web.analytics import (
    AnalyticsEngine,
    get_database_stats,
    get_suppressed_emails
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

                if result == 'success':
                    state.stats["processed"] += 1
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Processed {file_path.name}")
                elif result == 'suppressed':
                    state.stats["suppressed"] += 1
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⊘ Suppressed {file_path.name}")
                elif result == 'skipped':
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏭️ Skipped {file_path.name} (already processed)")

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
        with ui.row().classes('w-full justify-between items-start p-4 border-b border-black/10 dark:border-white/10 shrink-0'):
            with ui.column().classes('flex-1'):
                subject = log_entry.get('subject', 'No Subject')
                ui.label(subject).classes('text-xl font-bold text-main mb-2')

                with ui.row().classes('gap-4 text-xs text-secondary'):
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
        with ui.tabs().classes('w-full shrink-0 border-b border-black/5 dark:border-white/5 !h-12 text-secondary') \
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
                                ui.separator().classes('border-black/5 dark:border-white/5 my-2')
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


def render_dashboard_tab(dashboard_tab, page_is_visible, modal_is_open):
    """Render the Dashboard tab content"""
    with ui.tab_panel(dashboard_tab):
        with ui.column().classes('w-full p-6 gap-6'):
            # Stats overview
            @ui.refreshable
            def stats_cards_ui():
                stats = get_database_stats()
                total = stats['total'] if stats['total'] > 0 else 1

                # Calculate percentages
                processed_pct = (stats['processed'] / total * 100) if total > 0 else 0
                suppressed_pct = (stats['suppressed'] / total * 100) if total > 0 else 0
                failed_pct = (stats['failed'] / total * 100) if total > 0 else 0

                # Stat cards
                with ui.row().classes('w-full gap-4 mb-6'):
                    create_stat_card('TOTAL EMAILS', stats['total'], 'mail', trend='neutral', trend_value='All emails')
                    create_stat_card('PROCESSED', stats['processed'], 'check_circle', trend='up' if stats['processed'] > 0 else 'neutral', trend_value=f"{processed_pct:.0f}% of total")
                    create_stat_card('SUPPRESSED', stats['suppressed'], 'block', trend='neutral', trend_value=f"{suppressed_pct:.0f}% filtered")
                    create_stat_card('FAILED', stats['failed'], 'error', trend='neutral' if stats['failed'] == 0 else 'down', trend_value=f"{failed_pct:.0f}% errors" if stats['failed'] > 0 else '0% errors')

            stats_cards_ui()

            # Recent Activity
            with ui.card().classes('w-full p-0 gap-0'):
                auto_refresh_enabled = {'value': True}
                last_refresh_time = {'value': datetime.now()}

                # Header
                with ui.row().classes('p-4 border-b border-black/10 dark:border-white/10 items-center justify-between'):
                    ui.label('RECENT ACTIVITY').classes('text-sm font-bold tracking-wide text-main')
                    with ui.row().classes('gap-2 items-center'):
                        refresh_indicator = ui.label().classes('text-xs text-gray-500')
                        def update_refresh_indicator():
                            if not auto_refresh_enabled['value']: refresh_indicator.text = 'Auto-refresh disabled'
                            elif modal_is_open['value']: refresh_indicator.text = 'Auto-refresh paused (modal open)'
                            else:
                                elapsed = (datetime.now() - last_refresh_time['value']).seconds
                                refresh_indicator.text = f'Updated {elapsed}s ago'
                        ui.timer(1.0, update_refresh_indicator)
                        ui.switch(value=True, on_change=lambda e: auto_refresh_enabled.__setitem__('value', e.value)).props('dense color=primary').classes('ml-2').tooltip('Toggle auto-refresh (5s interval)')

                # Search
                with ui.row().classes('px-4 py-3 gap-2 border-b border-black/10 dark:border-white/10'):
                    search_input = ui.input('Search emails...', on_change=lambda: handle_search()).props('outlined dense debounce="500" clearable').classes('flex-1')

                # Activity List
                current_page = {'value': 1}
                items_per_page = 10
                activity_container = ui.column().classes('w-full')

                def load_activity(page: int = 1, search_query: str = ''):
                    activity_container.clear()
                    last_refresh_time['value'] = datetime.now()
                    try:
                        db = PersistenceLayer()
                        offset = (page - 1) * items_per_page
                        recent_items, total_count = db.get_recent_activity(limit=items_per_page, offset=offset, search_query=search_query)
                        total_pages = max(1, (total_count + items_per_page - 1) // items_per_page)

                        with activity_container:
                            if recent_items:
                                with ui.row().classes('w-full px-4 py-2 border-b border-black/10 dark:border-white/10 text-xs font-bold text-secondary uppercase tracking-wider'):
                                    ui.label('Subject').classes('flex-[2]')
                                    ui.label('Sender').classes('flex-[1]')
                                    ui.label('Status').classes('w-24 text-center')
                                    ui.label('Time').classes('w-24 text-right')

                                for item in recent_items:
                                    status = item.get('status') or 'skipped'
                                    subject = item.get('subject') or 'No Subject'
                                    sender = item.get('sender') or 'Unknown'
                                    timestamp = item.get('processing_started_at') or ''
                                    time_str = '-'
                                    if timestamp:
                                        try: time_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%H:%M')
                                        except: pass

                                    with ui.row().classes('w-full px-4 py-3 border-b border-black/5 dark:border-white/5 items-center hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer').on('click', lambda i=item: show_processing_detail(i, modal_is_open)):
                                        ui.label(subject[:60] + ('...' if len(subject) > 60 else '')).classes('flex-[2] font-medium text-sm truncate pr-2 text-main')
                                        ui.label(sender[:30] + ('...' if len(sender) > 30 else '')).classes('flex-[1] text-xs text-gray-400 truncate pr-2')
                                        with ui.element('div').classes('w-24 flex justify-center'): status_badge(status, status)
                                        ui.label(time_str).classes('w-24 text-right text-xs text-gray-500 font-mono')

                                if total_pages > 1:
                                    with ui.row().classes('w-full p-4 justify-center border-t border-white/10'):
                                        ui.pagination(min=1, max=total_pages, value=current_page['value'], direction_links=True, on_change=lambda e: handle_page_change(e.value))
                            else:
                                with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                                    ui.icon('inbox', size='xl').classes('text-gray-400')
                                    ui.label('No matching emails found' if search_query else 'No Activity Yet').classes('text-h6 text-gray-500')
                    except Exception as e:
                        with activity_container: ui.label(f'Error: {e}').classes('text-negative text-caption')

                def handle_page_change(page: int):
                    current_page['value'] = page
                    load_activity(page, search_input.value or '')

                def handle_search():
                    current_page['value'] = 1
                    load_activity(1, search_input.value or '')

                search_input.on('keydown.enter', handle_search)
                load_activity()
                
                # Adaptive Polling Logic
                last_full_refresh = {'time': datetime.now()}
                
                def adaptive_refresh():
                    if not auto_refresh_enabled['value'] or modal_is_open['value'] or not page_is_visible['value']:
                        return
                        
                    now = datetime.now()
                    is_active = state.is_processing
                    seconds_since_refresh = (now - last_full_refresh['time']).total_seconds()
                    
                    # 1s refresh when processing, 30s when idle
                    if is_active or seconds_since_refresh >= 30:
                        stats_cards_ui.refresh()
                        load_activity(current_page['value'], search_input.value or '')
                        last_full_refresh['time'] = now

                ui.timer(1.0, adaptive_refresh)


def render_upload_tab(upload_tab, page_is_visible):
    """Render the Upload & Process tab content"""
    with ui.tab_panel(upload_tab):
        with ui.column().classes('w-full p-6 gap-4'):
            # Notification debouncing to prevent "toast flood" when many files are uploaded
            notification_data = {'success': 0, 'errors': [], 'warnings': []}
            notification_timer = [None]  # Use a list to make it mutable in nested scopes

            def flush_notifications():
                if notification_data['success'] > 0:
                    if notification_data['success'] == 1:
                        ui.notify('✅ File uploaded successfully', type='positive', position='top')
                    else:
                        ui.notify(f'✅ {notification_data["success"]} files uploaded successfully', type='positive', position='top')
                    notification_data['success'] = 0
                
                if notification_data['errors']:
                    if len(notification_data['errors']) == 1:
                        ui.notify(f'❌ {notification_data["errors"][0]}', type='negative', position='top', timeout=5000)
                    else:
                        ui.notify(f'❌ {len(notification_data["errors"])} errors during upload', type='negative', position='top', timeout=7000)
                    notification_data['errors'] = []

                if notification_data['warnings']:
                    if len(notification_data['warnings']) == 1:
                        ui.notify(f'⚠️ {notification_data["warnings"][0]}', type='warning', position='top', timeout=5000)
                    else:
                        ui.notify(f'⚠️ {len(notification_data["warnings"])} warnings during upload', type='warning', position='top', timeout=5000)
                    notification_data['warnings'] = []
                
                notification_timer[0] = None

            def notify_debounced(category, message=None):
                if category == 'success': notification_data['success'] += 1
                elif category == 'error': notification_data['errors'].append(message)
                elif category == 'warning': notification_data['warnings'].append(message)
                
                if notification_timer[0]:
                    notification_timer[0].cancel()
                notification_timer[0] = ui.timer(0.5, flush_notifications, once=True)

            # File list container needs to be defined in this scope
            file_list_container = None

            ui.add_head_html('''
                <style>
                .q-scrollarea__thumb--v {
                    background: rgba(59, 130, 246, 0.5);
                    border-radius: 4px;
                }
                .q-scrollarea__thumb--v:hover {
                    background: rgba(59, 130, 246, 0.8);
                }
                /* Webkit scrollbar styling */
                .overflow-y-auto::-webkit-scrollbar {
                    width: 8px;
                }
                .overflow-y-auto::-webkit-scrollbar-track {
                    background: transparent;
                }
                .overflow-y-auto::-webkit-scrollbar-thumb {
                    background: rgba(59, 130, 246, 0.5);
                    border-radius: 4px;
                }
                .overflow-y-auto::-webkit-scrollbar-thumb:hover {
                    background: rgba(59, 130, 246, 0.8);
                }
                </style>
            ''')

            async def handle_upload(e):
                """Handle file upload with validation and security checks"""
                if not hasattr(e, 'file'):
                    logger.warning(f"Upload event missing file: {e}")
                    return

                file_obj = e.file
                safe_filename = os.path.basename(file_obj.name)

                # Validation: File count limit
                if len(state.uploaded_files) >= MAX_UPLOAD_FILES:
                    notify_debounced('warning', f'Maximum {MAX_UPLOAD_FILES} files allowed')
                    return

                # Validation: File type
                if not file_obj.name.lower().endswith('.eml'):
                    notify_debounced('warning', f'{safe_filename}: Only .eml files are accepted')
                    return

                # Validation: Duplicate filenames
                if any((f.name.split('_', 1)[1] if '_' in f.name else f.name) == safe_filename for f in state.uploaded_files):
                    notify_debounced('warning', f'{safe_filename} is already in the queue')
                    return

                unique_name = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
                temp_path = Path(tempfile.gettempdir()) / unique_name

                try:
                    # Read file data
                    file_data = await file_obj.read()
                    file_size = len(file_data)

                    # Validation: Individual file size
                    if file_size > MAX_FILE_SIZE:
                        notify_debounced('warning', f'{safe_filename} too large (> {state.format_size(MAX_FILE_SIZE)})')
                        return

                    # Validation: Total size limit
                    current_total = state.get_total_size()
                    if current_total + file_size > MAX_TOTAL_SIZE:
                        notify_debounced('warning', f'Total size limit exceeded ({state.format_size(MAX_TOTAL_SIZE)})')
                        return

                    # Save file
                    with open(temp_path, 'wb') as f:
                        f.write(file_data)

                    state.uploaded_files.append(temp_path)
                    logger.info(f"File uploaded: {safe_filename} ({state.format_size(file_size)}) -> {unique_name}")

                    notify_debounced('success')
                    update_file_display()

                except Exception as ex:
                    logger.error(f"Upload error for {safe_filename}: {ex}", exc_info=True)
                    notify_debounced('error', f'Upload failed: {safe_filename}')

            def update_file_display():
                """Update the file list display"""
                if file_list_container is None: return
                file_list_container.clear()

                file_count = len(state.uploaded_files)
                total_size = state.get_total_size()

                with file_list_container:
                    if not state.uploaded_files:
                        # Empty state
                        with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                            ui.icon('cloud_upload', size='xl').classes('text-primary')
                            ui.label('Drag & drop EML files here').classes('text-h6 font-medium text-main')
                            ui.label('or click anywhere to browse').classes('text-sm text-gray-400')
                            with ui.row().classes('gap-4 mt-3 text-xs text-gray-500'):
                                ui.label(f'0 of {MAX_UPLOAD_FILES} files')
                                ui.label('•')
                                ui.label(f'Max {state.format_size(MAX_FILE_SIZE)} per file')
                                ui.label('•')
                                ui.label(f'Max {state.format_size(MAX_TOTAL_SIZE)} total')
                    else:
                        # File list with header showing stats (always visible)
                        with ui.card().classes('w-full mb-3 bg-blue-900/20 border border-blue-500/20'):
                            with ui.row().classes('items-center justify-between p-3'):
                                with ui.row().classes('items-center gap-4'):
                                    ui.icon('inventory_2', size='sm').classes('text-blue-400')
                                    ui.label(f'{file_count} of {MAX_UPLOAD_FILES} files').classes('text-sm font-bold text-blue-400')
                                    ui.label('•').classes('text-gray-600')
                                    ui.label(f'{state.format_size(total_size)} of {state.format_size(MAX_TOTAL_SIZE)}').classes('text-sm font-bold text-blue-400')

                                # Progress bar for total size
                                size_percentage = (total_size / MAX_TOTAL_SIZE * 100) if MAX_TOTAL_SIZE > 0 else 0
                                size_color = 'green' if size_percentage < 70 else 'orange' if size_percentage < 90 else 'red'
                                with ui.row().classes('items-center gap-2'):
                                    ui.label(f'{size_percentage:.0f}%').classes(f'text-xs font-mono text-{size_color}-400')

                            # Scroll hint when there are many files
                            if file_count > 8:
                                with ui.row().classes('w-full px-3 pb-2 items-center justify-center gap-2'):
                                    ui.icon('keyboard_arrow_down', size='xs').classes('text-gray-500')
                                    ui.label('Scroll to see all files').classes('text-xs text-gray-500')
                                    ui.icon('keyboard_arrow_down', size='xs').classes('text-gray-500')

                        # Scrollable file list container with custom scrollbar
                        scroll_container = ui.column().classes('w-full gap-2 p-4 overflow-y-auto').style('''
                            max-height: 400px;
                            scroll-behavior: smooth;
                            scrollbar-width: thin;
                            scrollbar-color: rgba(59, 130, 246, 0.5) transparent;
                        ''')

                        with scroll_container:
                            for file_path in state.uploaded_files:
                                display_name = file_path.name.split('_', 1)[1] if '_' in file_path.name else file_path.name

                                # Get file size
                                try:
                                    file_size = file_path.stat().st_size if file_path.exists() else 0
                                    file_size_str = state.format_size(file_size)
                                except:
                                    file_size_str = 'Unknown'

                                def remove_file(f=file_path, n=display_name):
                                    if f in state.uploaded_files:
                                        state.uploaded_files.remove(f)
                                        if f.exists(): f.unlink()
                                        ui.notify(f'✅ Removed {n}', type='info', position='top')
                                        update_file_display()

                                with ui.row().classes('items-center gap-3 p-3 bg-black/5 dark:bg-white/5 rounded-lg border border-black/10 dark:border-white/10 hover:bg-black/10 dark:hover:bg-white/10 transition-colors'):
                                    ui.icon('description', size='sm').classes('text-primary flex-shrink-0')
                                    with ui.column().classes('flex-1 min-w-0'):
                                        ui.label(display_name).classes('text-sm text-main truncate')
                                        ui.label(file_size_str).classes('text-xs text-gray-400')
                                    ui.button(icon='close', on_click=remove_file).props('flat dense round size=sm').classes('text-secondary hover:text-main')

            def handle_rejected(e):
                """Handle rejected files with detailed error messages"""
                if hasattr(e, 'file') and hasattr(e.file, 'name'):
                    notify_debounced('warning', f'Rejected: {e.file.name}')
                else:
                    notify_debounced('warning', 'Some files were rejected')

            # UI components
            upload_card = ui.card().classes('w-full mb-4 overflow-hidden eml-upload-drop-zone')
            with upload_card:
                with ui.element('div').classes('relative w-full min-h-[200px]'):
                    file_list_container = ui.column().classes('w-full')
                    upload_component = ui.upload(
                        multiple=True, auto_upload=True, max_file_size=MAX_FILE_SIZE,
                        on_upload=handle_upload,
                        on_rejected=handle_rejected
                    ).props('accept=.eml').classes('absolute inset-0 w-full h-full opacity-0 cursor-pointer').style('z-index: 10; pointer-events: auto;')
            
            update_file_display()

            # JS for interactions - Make entire card clickable to trigger file browser
            ui.run_javascript(f'''
                (function() {{
                    const uploaderId = {upload_component.id};

                    window.initUploadDropZone = () => {{
                        const card = document.querySelector('.eml-upload-drop-zone');
                        if (!card) {{
                            return false;
                        }}
                        if (card.dataset.clickableInit === 'true') {{
                            return true;
                        }}

                        card.dataset.clickableInit = 'true';
                        card.style.cursor = 'pointer';

                        const triggerFileBrowser = (e) => {{
                            if (e.target.closest('button')) {{
                                return;
                            }}
                            if (typeof runMethod === 'function') {{
                                runMethod(uploaderId, 'pickFiles', []);
                                return;
                            }}
                            let input = card.querySelector('input[type="file"]');
                            if (!input) {{
                                input = document.querySelector('input[type="file"]');
                            }}
                            if (input) {{
                                input.click();
                            }}
                        }};

                        card.addEventListener('click', triggerFileBrowser);

                        card.addEventListener('dragenter', (e) => {{
                            e.preventDefault();
                            card.style.borderColor = 'rgb(59, 130, 246)';
                            card.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
                        }});

                        card.addEventListener('dragover', (e) => {{
                            e.preventDefault();
                        }});

                        ['dragleave', 'drop'].forEach(eventName => {{
                            card.addEventListener(eventName, () => {{
                                card.style.borderColor = '';
                                card.style.backgroundColor = '';
                            }});
                        }});

                        console.log('✅ Upload drop zone initialized');
                        return true;
                    }};

                    window.initUploadDropZone();
                }})();
            ''')

            # Options and controls
            with ui.card().classes('w-full mb-4'):
                ui.label('Processing Options').classes('text-h6 mb-2')
                force_checkbox = ui.checkbox('Force reprocessing (ignore persistence)')
                verbose_checkbox = ui.checkbox('Verbose logging')

            # Control buttons
            with ui.row().classes('gap-2 mb-4'):
                async def start_processing():
                    if not state.uploaded_files:
                        ui.notify('Please upload files first', type='warning')
                        return
                    if state.is_processing:
                        ui.notify('Processing already in progress', type='warning')
                        return
                    ui.notify('Starting processing...', type='info')
                    await process_files_async(state.uploaded_files, force=force_checkbox.value, verbose=verbose_checkbox.value)
                    update_file_display() # Refresh list after cleanup

                ui.button('Start Processing', on_click=start_processing, icon='play_arrow').props('color=primary unelevated').bind_enabled_from(state, 'is_processing', lambda x: not x)
                
                async def clear_all():
                    for f in list(state.uploaded_files):
                        if f.exists(): f.unlink()
                    state.uploaded_files.clear()
                    update_file_display()
                    ui.notify('All files cleared', type='info')

                ui.button('Clear Files', on_click=clear_all, icon='clear').props('color=grey-7 outline').bind_enabled_from(state, 'is_processing', lambda x: not x)

            # Progress indicator
            with ui.card().classes('w-full mb-4'):
                ui.label('Progress').classes('text-h6 mb-2')
                ui.label().bind_text_from(state, 'current_file', lambda x: f'Processing: {x}' if state.is_processing else 'Idle')
                ui.linear_progress().props('instant-feedback').bind_value_from(state, 'progress', lambda p: p / state.total if state.total > 0 else 0)
                ui.label().bind_text_from(state, 'progress', lambda p: f'{p} / {state.total}' if state.total > 0 else '0 / 0')

            # Live logs
            with ui.card().classes('w-full'):
                ui.label('LIVE LOGS').classes('text-xs font-bold text-gray-400 mb-2')
                log_container = ui.column().classes('w-full bg-gray-900 p-4 rounded font-mono text-xs text-gray-300').style('max-height: 400px; overflow-y: auto')
                displayed_log_count = {'value': 0}
                window_start = {'value': 0}

                def update_logs():
                    current_log_count = len(state.logs)
                    if current_log_count < displayed_log_count['value']:
                        log_container.clear()
                        displayed_log_count['value'] = 0
                        window_start['value'] = 0
                    new_start = max(0, current_log_count - MAX_LOG_LINES)
                    if new_start != window_start['value']:
                        log_container.clear()
                        window_start['value'] = new_start
                        displayed_log_count['value'] = new_start
                    new_logs = state.logs[displayed_log_count['value']:current_log_count]
                    if new_logs:
                        with log_container:
                            for log in new_logs: ui.label(log).classes('font-mono text-sm')
                        displayed_log_count['value'] = current_log_count
                        ui.run_javascript(f"const c = document.getElementById('{log_container.id}'); if (c) c.scrollTop = c.scrollHeight;")

                ui.timer(TIMER_INTERVAL, update_logs, active=lambda: state.is_processing and page_is_visible['value'])


def render_analytics_tab(analytics_tab):
    """Render the Analytics tab content"""
    with ui.tab_panel(analytics_tab):
        with ui.column().classes('w-full p-6 gap-4'):
            analytics = AnalyticsEngine()
            tab_state = {'range': 'Last 30 Days'}

            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Analytics & Reports').classes('text-h4 font-bold')
                ui.icon('bar_chart', size='lg').classes('text-primary')

            with ui.row().classes('w-full items-center justify-between gap-2 mb-4'):
                @ui.refreshable
                def date_chips():
                    with ui.row().classes('gap-2'):
                        for label in ['Last 7 Days', 'Last 30 Days', 'Last 90 Days']:
                            ui.chip(label, selectable=True, on_click=lambda l=label: (tab_state.__setitem__('range', l), refresh_analytics_data(), date_chips.refresh())) \
                                .props('color=primary unelevated shadow-none text-xs') \
                                .bind_selected_from(tab_state, 'range', backward=lambda v, l=label: v == l)
                date_chips()
                refresh_button = ui.button('Refresh Data', icon='refresh', on_click=lambda: refresh_analytics_data()).props('flat round color=primary').tooltip('Manually refresh dashboard')

            overview_charts_container = ui.row().classes('w-full gap-4 mb-4')
            category_container = ui.card().classes('w-full mb-4')
            timeline_container = ui.card().classes('w-full mb-4')
            bottom_charts_container = ui.row().classes('w-full gap-4')

            def refresh_analytics_data():
                overview_charts_container.clear()
                category_container.clear()
                timeline_container.clear()
                bottom_charts_container.clear()

                with overview_charts_container:
                    stats = analytics.get_processing_stats()
                    with ui.card().classes('flex-1'): ui.plotly(analytics.create_processing_pie_chart(stats)).classes('w-full')
                    with ui.card().classes('flex-1'): ui.plotly(analytics.create_success_gauge_chart(stats)).classes('w-full')

                with category_container:
                    cat_data = analytics.get_suppression_breakdown()
                    if cat_data: ui.plotly(analytics.create_category_bar_chart(cat_data)).classes('w-full')
                    else: ui.label('No suppression data available yet').classes('text-gray-400 p-4')

                with timeline_container:
                    days = {'Last 7 Days': 7, 'Last 30 Days': 30, 'Last 90 Days': 90}.get(tab_state['range'], 30)
                    time_data = analytics.get_timeline_data(days=days)
                    if time_data['dates']: ui.plotly(analytics.create_timeline_chart(time_data)).classes('w-full')
                    else: ui.label('No timeline data available yet').classes('text-gray-400 p-4')

                with bottom_charts_container:
                    with ui.card().classes('flex-1'):
                        top_domains = analytics.get_top_suppressed_domains(limit=10)
                        if top_domains: ui.plotly(analytics.create_top_domains_chart(top_domains)).classes('w-full')
                        else: ui.label('No suppression data available yet').classes('text-gray-400 p-4')
                    with ui.card().classes('flex-1'):
                        reason_data = analytics.get_reason_breakdown()
                        if reason_data:
                            ui.label('Suppression by Reason').classes('text-h6 mb-2')
                            reasons, counts = list(reason_data.keys()), list(reason_data.values())
                            reason_fig = go.Figure(data=[go.Bar(x=counts, y=reasons, orientation='h', marker=dict(color='#9C27B0'), text=counts, textposition='outside')])
                            reason_fig.update_layout(title='Top 10 Suppression Reasons', height=max(300, len(reasons) * 30), margin=dict(t=40, b=40, l=200, r=40))
                            ui.plotly(reason_fig).classes('w-full')
                        else: ui.label('No reason data available yet').classes('text-gray-400 p-4')
                ui.notify('Analytics data refreshed', type='positive')

            refresh_analytics_data()


def render_config_tab(config_tab):
    """Render the Configuration tab content"""
    def strip_inline_comment(value: str) -> str:
        in_single = False
        in_double = False
        escaped = False
        result = []
        for ch in value:
            if ch == '\\' and not escaped:
                escaped = True
                result.append(ch)
                continue
            if ch == "'" and not in_double and not escaped:
                in_single = not in_single
            elif ch == '"' and not in_single and not escaped:
                in_double = not in_double
            elif ch == '#' and not in_single and not in_double:
                break
            result.append(ch)
            escaped = False
        return ''.join(result).rstrip()

    def parse_env_text(content: str) -> Dict[str, str]:
        parsed = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.lower().startswith('export '):
                line = line[7:].strip()
            line = strip_inline_comment(line).strip()
            if not line or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            parsed[key] = value
        return parsed

    async def handle_import(e):
        try:
            content = await e.file.text()
            new_cfg = parse_env_text(content)
            
            # Update form fields
            count = 0
            for k, v in new_cfg.items():
                if k in form_data:
                    form_data[k].set_value(v)
                    count += 1
            ui.notify(f"Imported {count} settings from file", type='positive')
        except Exception as ex:
            ui.notify(f"Failed to parse .env file: {ex}", type='negative')

    with ui.tab_panel(config_tab):
        with ui.column().classes('w-full p-6 gap-4'):
            custom_env = app.storage.user.get('env_path')
            config_manager = ConfigManager(env_path=custom_env)
            current_config = config_manager.load_config()
            form_data = {}

            with ui.row().classes('w-full items-center justify-between mb-2 h-9'):
                ui.label('Configuration').classes('text-h4 font-bold')
                with ui.row().classes('gap-2 items-center h-9'):
                    upload_component = ui.upload(on_upload=handle_import, auto_upload=True, max_files=1) \
                        .props('accept=.env,.txt')
                    upload_component.style('position: absolute; left: -10000px; width: 1px; height: 1px; opacity: 0;')
                    ui.button('Import .env', icon='file_upload', on_click=lambda: upload_component.run_method('pickFiles')) \
                        .props('flat color=primary').classes('h-9 min-h-9 px-3')
                    ui.icon('settings', size='lg').classes('text-primary')

            def create_section(title, icon=None):
                card = ui.card().classes('w-full mb-4 bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10')
                with card: 
                    with ui.row().classes('items-center gap-2 mb-3'):
                        if icon: ui.icon(icon, size='sm').classes('text-primary')
                        ui.label(title).classes('text-h6')
                return card

            # 1. CRM Settings
            with create_section('CRM API Settings', 'cloud'):
                form_data['CRM_API_BASE_URL'] = ui.input('CRM API Base URL', value=current_config.get('CRM_API_BASE_URL', '')).classes('w-full').props('outlined dense')
                form_data['CRM_API_KEY'] = ui.input('CRM API Key', value=current_config.get('CRM_API_KEY', ''), password=True, password_toggle_button=True).classes('w-full').props('outlined dense')
                
                with ui.row().classes('items-center gap-2 mt-2'):
                    crm_status = ui.label().classes('text-xs')
                    async def test_crm():
                        crm_status.text = '⏳ Testing...'; await asyncio.sleep(0.1)
                        res = await asyncio.to_thread(config_manager.test_crm_connection, form_data['CRM_API_KEY'].value, form_data['CRM_API_BASE_URL'].value)
                        crm_status.text = f"{('✅' if res['success'] else '❌')} {res['message']}"
                        crm_status.classes('text-positive' if res['success'] else 'text-negative')
                    ui.button('Test Connection', on_click=test_crm).props('outline dense text-xs')

            # 2. LLM Settings
            with create_section('LLM Configuration', 'psychology'):
                form_data['LLM_BASE_URL'] = ui.input('LLM Base URL', value=current_config.get('LLM_BASE_URL', '')).classes('w-full').props('outlined dense')
                form_data['LLM_API_KEY'] = ui.input('LLM API Key', value=current_config.get('LLM_API_KEY', ''), password=True, password_toggle_button=True).classes('w-full').props('outlined dense')
                form_data['LLM_MODEL'] = ui.input('LLM Model', value=current_config.get('LLM_MODEL', 'gpt-4o-mini')).classes('w-full').props('outlined dense')
                
                with ui.row().classes('items-center gap-2 mt-2'):
                    llm_status = ui.label().classes('text-xs')
                    async def test_llm():
                        llm_status.text = '⏳ Testing...'; await asyncio.sleep(0.1)
                        res = await asyncio.to_thread(config_manager.test_llm_connection, form_data['LLM_API_KEY'].value, form_data['LLM_BASE_URL'].value, form_data['LLM_MODEL'].value)
                        llm_status.text = f"{('✅' if res['success'] else '❌')} {res['message']}"
                        llm_status.classes('text-positive' if res['success'] else 'text-negative')
                    ui.button('Test Connection', on_click=test_llm).props('outline dense text-xs')

            # 3. Search Provider Settings
            with create_section('Search Providers (Optional)', 'search'):
                ui.label('Comma-separated list (duckduckgo, serper, serpapi)').classes('text-[10px] text-gray-500')
                form_data['SEARCH_PROVIDERS'] = ui.input('Providers', value=current_config.get('SEARCH_PROVIDERS', 'duckduckgo')).classes('w-full').props('outlined dense')
                form_data['SERPER_API_KEY'] = ui.input('Serper API Key', value=current_config.get('SERPER_API_KEY', ''), password=True).classes('w-full').props('outlined dense')
                form_data['SERPAPI_KEY'] = ui.input('SerpAPI Key', value=current_config.get('SERPAPI_KEY', ''), password=True).classes('w-full').props('outlined dense')

            # 4. Internal Staff Filtering
            with create_section('Internal Staff Filtering', 'person_off'):
                ui.label('Define who NOT to sync to CRM').classes('text-[10px] text-gray-500')
                form_data['INTERNAL_DOMAINS'] = ui.input('Internal Domains (e.g. company.com)', value=current_config.get('INTERNAL_DOMAINS', '')).classes('w-full').props('outlined dense')
                form_data['INTERNAL_EMAILS'] = ui.input('Internal Emails (e.g. staff@gmail.com)', value=current_config.get('INTERNAL_EMAILS', '')).classes('w-full').props('outlined dense')

            # 5. Email Filtering & Logic
            with create_section('Email Processing Logic', 'filter_alt'):
                form_data['CLASSIFICATION_STRATEGY'] = ui.select(['heuristic', 'llm', 'hybrid'], value=current_config.get('CLASSIFICATION_STRATEGY', 'hybrid'), label='Strategy').classes('w-full').props('outlined dense')
                form_data['CLASSIFICATION_MODEL'] = ui.input('Classification Model Override', value=current_config.get('CLASSIFICATION_MODEL', 'gpt-4o-mini')).classes('w-full').props('outlined dense')
                form_data['SUPPRESS_CATEGORIES'] = ui.input('Suppress Categories', value=current_config.get('SUPPRESS_CATEGORIES', 'promotional,newsletter,automated,spam')).classes('w-full').props('outlined dense')
                form_data['ALLOWLIST_DOMAINS'] = ui.input('Force-Process (Allowlist)', value=current_config.get('ALLOWLIST_DOMAINS', '')).classes('w-full').props('outlined dense')
                form_data['SUPPRESS_DOMAINS'] = ui.input('Force-Suppress (Blocklist)', value=current_config.get('SUPPRESS_DOMAINS', '')).classes('w-full').props('outlined dense')
                form_data['LOG_SUPPRESSED'] = ui.switch('Log Suppressions to DB', value=current_config.get('LOG_SUPPRESSED', 'true').lower() == 'true').props('dense color=primary')

            # 6. Persistence
            with create_section('Database Settings', 'storage'):
                form_data['PERSISTENCE_DB_PATH'] = ui.input('Database Path', value=current_config.get('PERSISTENCE_DB_PATH', 'eml_processing.db')).classes('w-full').props('outlined dense')

            async def save_config():
                # Extract values, handling Switch special case
                cfg = {}
                for k, v in form_data.items():
                    if isinstance(v, ui.switch):
                        cfg[k] = 'true' if v.value else 'false'
                    elif hasattr(v, 'value'):
                        cfg[k] = str(v.value)

                errs = config_manager.validate_config(cfg)
                if errs: 
                    ui.notify(f"Validation Errors: {', '.join(errs[:3])}...", type='negative')
                    return

                ok, msg = config_manager.save_config(cfg)
                if ok: 
                    ui.notify(msg, type='positive')
                    # Force reload of environment
                    load_dotenv(override=True)
                else: 
                    ui.notify(msg, type='negative')

            with ui.row().classes('w-full gap-2 mt-4 sticky bottom-0 bg-white/10 p-4 rounded-lg backdrop-blur-md z-10'):
                ui.button('Apply & Save Changes', on_click=save_config, icon='save').props('color=primary unelevated').classes('flex-1')

def render_suppressed_tab(suppressed_tab, page_is_visible):
    """Render the Suppressed Emails tab content"""
    with ui.tab_panel(suppressed_tab):
        with ui.column().classes('w-full p-6 gap-4'):
            auto_refresh = {'value': False}
            last_refresh = {'value': datetime.now()}

            tab_state = {'category': 'All'}
            db = PersistenceLayer()

            @ui.refreshable
            def chips_ui():
                try:
                    stats = db.get_suppression_breakdown()
                    overall = db.get_processing_stats()
                    total = overall.get('suppressed', 0)
                    
                    with ui.row().classes('gap-1 items-center'):
                        # 'All' Chip
                        ui.chip(f"All ({total})", selectable=True, on_click=lambda: (tab_state.__setitem__('category', 'All'), refresh_table())) \
                            .props('color=primary unelevated shadow-none text-xs') \
                            .bind_selected_from(tab_state, 'category', backward=lambda v: v == 'All')
                        
                        if stats:
                            for cat, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
                                if cat == '':
                                    continue
                                category_value = '__null__' if cat is None else cat
                                category_label = 'null' if cat is None else cat
                                ui.chip(f"{category_label} ({count})", selectable=True, on_click=lambda c=category_value: (tab_state.__setitem__('category', c), refresh_table())) \
                                    .props('color=primary unelevated shadow-none text-xs') \
                                    .bind_selected_from(tab_state, 'category', backward=lambda v, c=category_value: v == c)
                        elif total > 0:
                            ui.chip(f"unclassified ({total})", selectable=True, on_click=lambda: (tab_state.__setitem__('category', 'unknown'), refresh_table())) \
                                .props('color=primary unelevated shadow-none text-xs') \
                                .bind_selected_from(tab_state, 'category', backward=lambda v: v == 'unknown')
                except Exception as e:
                    logger.error(f"Error rendering chips: {e}")
                    ui.label("Error loading categories").classes('text-xs text-red-400')

            def refresh_table():
                last_refresh['value'] = datetime.now()
                
                try:
                    # 1. Fetch data for table
                    category_filter = tab_state['category'] if tab_state['category'] != 'All' else None
                    emails = get_suppressed_emails(
                        limit=100, 
                        category=category_filter, 
                        search=search_input.value
                    )
                    
                    # 2. Update table
                    table_container.clear()
                    with table_container:
                        if emails:
                            with ui.row().classes('w-full px-4 py-2 border-b border-black/10 dark:border-white/10 text-xs font-bold text-secondary uppercase tracking-wider'):
                                ui.label('Date').classes('w-32'); ui.label('Sender').classes('flex-[1]'); ui.label('Subject').classes('flex-[2]'); ui.label('Category').classes('w-32 text-center')
                            for e in emails:
                                with ui.row().classes('w-full px-4 py-3 border-b border-black/5 dark:border-white/5 items-center hover:bg-black/5 dark:hover:bg-white/5 transition-colors'):
                                    ui.label(e.get('timestamp', '')[:10]).classes('w-32 text-xs font-mono text-secondary')
                                    ui.label(e.get('sender', '')[:40]).classes('flex-[1] text-xs truncate text-secondary')
                                    ui.label(e.get('subject', '')[:50]).classes('flex-[2] font-medium text-sm truncate text-main')
                                    ui.label(e.get('category', 'unknown')).classes('w-32 text-center text-[10px] bg-black/10 dark:bg-white/10 rounded-full text-secondary')
                        else: ui.label('No suppressed emails found').classes('text-secondary italic text-center w-full py-10 opacity-70')
                    
                    # 3. Refresh Chips
                    chips_ui.refresh()

                except Exception as e:
                    logger.error(f"Error refreshing suppressed table: {e}", exc_info=True)
                    ui.notify("Failed to refresh data", type='negative')

            with ui.row().classes('w-full items-center justify-between mb-2'):
                with ui.row().classes('items-center gap-4'):
                    ui.label('Suppressed Emails').classes('text-h4 font-bold')
                    ui.button(on_click=refresh_table, icon='refresh').props('round flat dense color=primary').tooltip('Refresh List')
                
                with ui.row().classes('gap-2 items-center'):
                    ui.icon('sync', size='xs').classes('text-primary' if auto_refresh['value'] else 'text-secondary')
                    refresh_indicator = ui.label().classes('text-[10px] text-secondary font-mono w-32')
                    ui.timer(1.0, lambda: refresh_indicator.__setattr__('text', f"Updated {(datetime.now() - last_refresh['value']).seconds}s ago" if auto_refresh['value'] else "Auto-refresh off"))
                    ui.switch(value=False, on_change=lambda e: auto_refresh.__setitem__('value', e.value)).props('dense color=primary').tooltip('Toggle Auto-refresh')

            search_input = ui.input('Search', placeholder='Search sender or subject...', on_change=refresh_table) \
                .classes('w-full mb-2') \
                .props('outlined dense icon=search debounce="400" clearable')
            
            with ui.row().classes('gap-2 mb-4 items-center'):
                ui.label('Categories:').classes('text-xs text-secondary uppercase tracking-wider mr-2')
                chips_ui()

            table_container = ui.column().classes('w-full bg-black/5 dark:bg-white/5 rounded-lg overflow-hidden border border-black/10 dark:border-white/10')
            refresh_table()
            search_input.on('keydown.enter', refresh_table)
            search_input.on('blur', refresh_table)
            ui.timer(10.0, lambda: refresh_table() if auto_refresh['value'] and page_is_visible['value'] else None)

@ui.page('/')
def main_page():
    """Main page with tabbed interface"""
    app_dark_mode = apply_nexus_theme()
    tabs, dashboard_tab, upload_tab, analytics_tab, suppressed_tab, config_tab = create_header_with_tabs(app_dark_mode)
    upload_tab_name = upload_tab.props['name']

    page_is_visible = {'value': True}
    modal_is_open = {'value': False}

    ui.run_javascript('''
        document.addEventListener('visibilitychange', () => { window.pageIsVisible = !document.hidden; });
        window.pageIsVisible = !document.hidden;
    ''')
    
    async def sync_visibility():
        visible = await ui.run_javascript('return window.pageIsVisible;')
        page_is_visible['value'] = visible if visible is not None else True
    
    ui.timer(2.0, sync_visibility)

    def handle_tab_change(e):
        if e.value == upload_tab_name:
            ui.run_javascript('setTimeout(() => { if (window.initUploadDropZone) { window.initUploadDropZone(); } }, 50);')

    tabs.on_value_change(handle_tab_change)

    with ui.tab_panels(tabs, value=dashboard_tab).classes('w-full flex-1 bg-transparent'):
        render_dashboard_tab(dashboard_tab, page_is_visible, modal_is_open)
        render_upload_tab(upload_tab, page_is_visible)
        render_analytics_tab(analytics_tab)
        render_suppressed_tab(suppressed_tab, page_is_visible)
        render_config_tab(config_tab)


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
