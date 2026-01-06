"""
Detail Modal View for CRM Automator

This module provides the processing detail modal dialog that displays
comprehensive information about a processed email, including AI analysis,
CRM integration results, and error details.

Functions:
    show_processing_detail: Display detailed processing information in a modal
"""

import json
from typing import Dict, Any
from nicegui import ui
from eml.web.components import status_badge


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
                                    with ui.column().classes('w-full p-2 overflow-auto max-h-96'):
                                        ui.code(json.dumps(summary_data, indent=2), language='json').classes('w-full')
                                except:
                                    # Fallback if ai_summary is already a dict-like object (Pydantic model)
                                    if hasattr(ai_summary, 'model_dump') or hasattr(ai_summary, 'dict'):
                                        data = ai_summary.model_dump() if hasattr(ai_summary, 'model_dump') else ai_summary.dict()
                                        with ui.column().classes('w-full p-2 overflow-auto max-h-96'):
                                            ui.code(json.dumps(data, indent=2), language='json').classes('w-full')
                                    else:
                                        ui.label(str(ai_summary)).classes('text-sm text-gray-300 leading-relaxed whitespace-pre-wrap')

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
                                        with ui.column().classes('w-full p-2 overflow-auto max-h-64'):
                                            ui.code(json.dumps(data, indent=2), language='json').classes('w-full')
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
