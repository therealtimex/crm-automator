"""
UI Components and Theming Module for CRM Automator

This module provides reusable UI components and the Nexus Glass theme
for the web UI. All components follow a consistent design system with
responsive layouts and modern aesthetics.

Functions:
    apply_nexus_theme: Inject Nexus Glass CSS styling
    status_badge: Create colored status badges
    create_header_with_tabs: Build app header with navigation
    create_stat_card: Dashboard stat cards with trend indicators
    create_recent_activity_item: Activity list items
    create_empty_state: Empty state placeholders

Design System:
    - Nexus Glass theme (dark mode with glassmorphism)
    - Responsive design (mobile-first)
    - Tailwind-inspired utility classes
    - Consistent color palette and spacing
"""

from nicegui import ui
from typing import Dict, Any
from datetime import datetime
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("crm-automator")
except PackageNotFoundError:
    # Fallback to hardcoded version if metadata is unavailable
    __version__ = "1.11.0"

def get_project_version():
    """Returns the project version from package metadata."""
    return __version__

def apply_nexus_theme():
    """Injects Nexus Glass styling overrides."""
    ui.add_head_html('''
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; }
            
            /* --- Deep Space Gradient Background --- */
            .body--dark .nicegui-content { 
                background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%); 
                min-height: 100vh; 
            }
            .body--light .nicegui-content { 
                background: #f8fafc; 
                min-height: 100vh; 
            }
            
            /* --- Adaptive Text --- */
            .text-main { color: #1f2937; }
            .body--dark .text-main { color: rgba(255, 255, 255, 0.9); }
            
            .text-secondary { color: #374151; }
            .body--dark .text-secondary { color: rgba(255, 255, 255, 0.7); }

            .text-tertiary { color: #4b5563; }
            .body--dark .text-tertiary { color: rgba(255, 255, 255, 0.6); }
            
            /* --- Top Bar & Header --- */
            .q-header { 
                height: 56px !important;
                background-color: transparent !important; 
                border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
            }
            .body--light .q-header {
                background-color: #ffffff !important;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1) !important;
            }
            .body--dark .q-header {
                background-color: #0f0f23 !important;
            }

            /* --- Glass Cards Override (Dark) --- */
            .body--dark .q-card { 
                background: rgba(255, 255, 255, 0.05) !important; 
                backdrop-filter: blur(10px); 
                border: 1px solid rgba(255, 255, 255, 0.1); 
            }
            
            /* --- Clean Cards Override (Light) --- */
            .body--light .q-card {
                background: #ffffff !important;
                border: 1px solid rgba(0, 0, 0, 0.08);
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            }
            
            /* --- Responsive Header & Branding --- */
            .body--dark .text-branding { color: rgba(255, 255, 255, 0.9) !important; }
            .body--light .text-branding { color: #1f2937 !important; }

            .desktop-only { display: none; }
            @media (min-width: 768px) {
                .desktop-only { display: block !important; }
            }

            /* Hide tab labels on mobile for cleaner look */
            @media (max-width: 767px) {
                .q-tab__label {
                    display: none;
                }
                .q-tab {
                    min-width: 48px !important;
                    padding: 0 8px !important;
                }
            }
            
            /* --- Quasar Component Cleanups --- */
            .q-table, .q-table__card { background: transparent !important; }
            .q-tab__indicator { height: 3px !important; border-radius: 3px 3px 0 0; }
            .q-tabs { height: 100%; }

            /* --- Form Input Refinements (Thinner/Subtler Lines) --- */
            .q-field--outlined .q-field__control:before {
                border-color: rgba(0, 0, 0, 0.15); 
            }
            .body--dark .q-field--outlined .q-field__control:before {
                border-color: rgba(255, 255, 255, 0.1);
            }
            .q-field--outlined:hover .q-field__control:before {
                border-color: rgba(0, 0, 0, 0.3);
            }
            .body--dark .q-field--outlined:hover .q-field__control:before {
                border-color: rgba(255, 255, 255, 0.25);
            }

            /* --- Upload Component Fix --- */
            .q-uploader__list:not(:has(.q-uploader__file)) {
                display: none !important;
            }

            /* --- Responsive Design: Mobile --- */
            @media (max-width: 767px) {
                /* Hide tab labels on mobile, show icons only */
                .q-tab__label {
                    display: none !important;
                }

                /* Reduce header padding on mobile */
                .q-header .q-toolbar {
                    padding-left: 1rem !important;
                    padding-right: 1rem !important;
                }

                /* Reduce gap between tabs */
                .q-tabs {
                    gap: 0 !important;
                }
            }
        </style>
    ''')
    
    # Force Dark Mode by default, but allow toggle
    dark = ui.dark_mode()
    dark.enable()
    return dark

def status_badge(text: str, state: str = 'neutral'):
    colors = {
        'success': 'text-green-400 bg-green-500/10 border-green-500/20',
        'positive': 'text-green-400 bg-green-500/10 border-green-500/20',
        'neutral': 'text-blue-400 bg-blue-500/10 border-blue-500/20',
        'primary': 'text-blue-400 bg-blue-500/10 border-blue-500/20',
        'warning': 'text-orange-400 bg-orange-500/10 border-orange-500/20',
        'error':   'text-red-400 bg-red-500/10 border-red-500/20',
        'negative': 'text-red-400 bg-red-500/10 border-red-500/20',
        'skipped': 'text-secondary bg-gray-500/10 border-gray-500/20',
        'failed': 'text-red-400 bg-red-500/10 border-red-500/20',
        'suppressed': 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    }
    # Map common status codes to our keys
    state_map = {
        'processed': 'success',
        'suppressed': 'warning', 
        'failed': 'error'
    }
    
    # Normalize state key
    key = state_map.get(state, state)
    style = colors.get(key, colors['neutral'])
    
    ui.label(text.upper()).classes(f'px-2 py-0.5 text-[10px] rounded-full border {style}')

def create_header_with_tabs(dark_mode_handler, active_tab_name: str = 'dashboard'):
    """Create header with top tabs navigation (Nexus Glass style)"""
    # Header container (p-0 to allow full control by inner row)
    with ui.header().classes('p-0'):
        # Inner row with fixed height and responsive padding
        with ui.row().classes('w-full items-center justify-between px-3 md:px-6 h-14'):
            
            # Left: App branding (responsive: icon-only on mobile)
            with ui.row().classes('items-center gap-2 md:gap-3'):
                # Inline SVG logo (always visible)
                ui.html('''
                    <svg width="32" height="32" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                      <defs>
                        <linearGradient id="logoGrad" x1="0%" y1="100%" x2="100%" y2="0%">
                          <stop offset="0%" style="stop-color:#818CF8;stop-opacity:1" />
                          <stop offset="100%" style="stop-color:#22D3EE;stop-opacity:1" />
                        </linearGradient>
                      </defs>
                      <g transform="translate(50,50)">
                        <g transform="rotate(30)">
                          <path d="M0,-40 L35,-20 L35,20 L0,40 L-35,20 L-35,-20 Z"
                                fill="none"
                                stroke="url(#logoGrad)"
                                stroke-width="7"
                                stroke-linejoin="round"/>
                          <circle cx="0" cy="0" r="8" fill="#60A5FA" />
                          <line x1="0" y1="0" x2="0" y2="-40" stroke="#60A5FA" stroke-width="4" />
                          <line x1="0" y1="0" x2="25" y2="15" stroke="#60A5FA" stroke-width="4" />
                          <line x1="0" y1="0" x2="-25" y2="15" stroke="#60A5FA" stroke-width="4" />
                        </g>
                      </g>
                    </svg>
                ''', sanitize=False).classes('flex-shrink-0')
                # App name and version (hidden on mobile, visible on medium+ screens)
                with ui.row().classes('desktop-only items-baseline gap-2'):
                    ui.label('CRM AUTOMATOR').classes('text-sm font-bold tracking-wide text-branding')
                    ui.label(f'v{get_project_version()}').classes('text-[10px] text-tertiary font-medium opacity-70')
                # Separator visible only on mobile when text is hidden
                ui.element('div').classes('w-[1px] h-6 bg-white/10 mx-1 md:hidden')

            # Center: Tabs
            with ui.tabs().classes('bg-transparent text-secondary') \
                .props('indicator-color="blue-400" active-color="blue-400" dense no-caps') as tabs:
                dashboard_tab = ui.tab('Dashboard', icon='dashboard')
                upload_tab = ui.tab('Upload & Process', icon='upload')
                suppressed_tab = ui.tab('Suppressed', icon='filter_list')
                config_tab = ui.tab('Configuration', icon='settings')

            # Right: System Status & Theme Toggle (responsive)
            with ui.row().classes('items-center gap-2 md:gap-6'):
                 # Theme Switcher (Icon with Menu)
                 with ui.button(icon='brightness_6').props('flat round dense text-color=grey-5'):
                     ui.tooltip('Change Theme')
                     with ui.menu().classes('bg-gray-800 text-white border border-gray-700'):
                         ui.menu_item('Light', on_click=lambda: dark_mode_handler.disable()).classes('hover:bg-gray-700')
                         ui.menu_item('Dark', on_click=lambda: dark_mode_handler.enable()).classes('hover:bg-gray-700')
                         ui.menu_item('System', on_click=lambda: dark_mode_handler.auto()).classes('hover:bg-gray-700')

                 # System Status (icon-only on mobile, full text on desktop)
                 with ui.row().classes('items-center gap-2'):
                     ui.element('div').classes('w-2 h-2 rounded-full bg-green-500 animate-pulse')
                     ui.label('SYSTEM ONLINE').classes('desktop-only text-[10px] font-bold text-green-500 tracking-wider')

    return tabs, dashboard_tab, upload_tab, suppressed_tab, config_tab

def create_stat_card(title: str, value: int, icon: str = None, color: str = None, trend: str = None, trend_value: str = None):
    """Create Nexus Glass stat card"""
    with ui.card().classes('flex-1 p-4'):
        with ui.row().classes('w-full justify-between items-start'):
            with ui.column().classes('gap-1'):
                ui.label(title).classes('text-xs text-secondary uppercase tracking-wider mb-1')
                ui.label(str(value)).classes('text-3xl font-bold text-main')

                if trend and trend_value:
                    # Map trend to color and icon
                    trend_styles = {
                        'up': ('text-green-400', 'trending_up'),
                        'down': ('text-red-400', 'trending_down'),
                        'neutral': ('text-secondary', 'remove')  # horizontal line icon
                    }
                    trend_color, trend_icon = trend_styles.get(trend, ('text-secondary', 'remove'))

                    with ui.row().classes('items-center gap-1 mt-1'):
                        ui.icon(trend_icon, size='xs').classes(trend_color)
                        ui.label(trend_value).classes(f'text-xs {trend_color}')

            if icon:
                ui.icon(icon, size='md').classes('text-primary/20 dark:text-white/20')

def create_recent_activity_item(item: Dict[str, Any]):
    """Create a recent activity item"""
    status_colors = {
        'success': 'positive',
        'suppressed': 'warning',
        'failed': 'negative',
        'skipped': 'grey'
    }

    status_icons = {
        'success': 'check_circle',
        'suppressed': 'block',
        'failed': 'error',
        'skipped': 'skip_next'
    }

    status = item.get('status', 'skipped')
    color = status_colors.get(status, 'grey')
    icon = status_icons.get(status, 'circle')

    with ui.row().classes('w-full items-center gap-3 p-3 hover:bg-grey-1 rounded cursor-pointer'):
        ui.icon(icon, size='md').classes(f'text-{color}')

        with ui.column().classes('flex-1 gap-0'):
            subject = item.get('subject', 'No Subject')
            if len(subject) > 50:
                subject = subject[:50] + '...'
            ui.label(subject).classes('font-medium')

            sender = item.get('sender', 'Unknown')
            if len(sender) > 40:
                sender = sender[:40] + '...'
            ui.label(sender).classes('text-caption text-tertiary')

        # Timestamp
        timestamp = item.get('processing_started_at', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%m/%d %H:%M')
                ui.label(time_str).classes('w-28 text-right text-caption text-tertiary font-mono')
            except:
                pass


def create_empty_state(icon: str, title: str, description: str, action_label: str = None, action_route: str = None):
    """Create empty state UI"""
    with ui.column().classes('w-full items-center justify-center p-12 gap-4'):
        ui.icon(icon, size='xl').classes('text-grey-4')
        ui.label(title).classes('text-h6 text-secondary')
        ui.label(description).classes('text-caption text-gray-600 text-center')

        if action_label and action_route:
            ui.button(action_label, on_click=lambda: ui.navigate.to(action_route), icon='add').props('color=primary')
