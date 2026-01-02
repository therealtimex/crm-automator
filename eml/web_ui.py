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


class ProcessingState:
    """Global state for processing operations (single-user localhost app)"""
    def __init__(self):
        self.is_processing = False
        self.current_file = ""
        self.progress = 0
        self.total = 0
        self.logs = []
        self.uploaded_files: List[Path] = []
        self.stats = {
            "total": 0,
            "processed": 0,
            "suppressed": 0,
            "failed": 0
        }

    def cleanup_files(self):
        """Clean up uploaded temporary files"""
        for file_path in self.uploaded_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup file {file_path}: {e}")
        self.uploaded_files.clear()


# Global state (acceptable for localhost-only app)
state = ProcessingState()

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
                border: 1px solid rgba(0, 0, 0, 0.1);
                box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
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
        'skipped': 'text-gray-400 bg-gray-500/10 border-gray-500/20',
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



# ========== Shared UI Components ==========

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
                # App name (hidden on mobile, visible on medium+ screens)
                ui.label('CRM AUTOMATOR').classes('desktop-only text-sm font-bold tracking-wide text-branding')
                # Separator visible only on mobile when text is hidden
                ui.element('div').classes('w-[1px] h-6 bg-white/10 mx-1 md:hidden')

            # Center: Tabs (Self-stretch to fill height)
            with ui.tabs().classes('bg-transparent self-stretch text-gray-400') \
                .props('indicator-color="blue-400" active-color="blue-400" dense no-caps') as tabs:
                dashboard_tab = ui.tab('Dashboard', icon='dashboard')
                upload_tab = ui.tab('Upload & Process', icon='upload')
                analytics_tab = ui.tab('Analytics', icon='bar_chart')
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

    return tabs, dashboard_tab, upload_tab, analytics_tab, suppressed_tab, config_tab


def create_stat_card(title: str, value: int, icon: str = None, color: str = None, trend: str = None, trend_value: str = None):
    """Create Nexus Glass stat card"""
    with ui.card().classes('flex-1 p-4'):
        with ui.row().classes('w-full justify-between items-start'):
            with ui.column().classes('gap-1'):
                ui.label(title).classes('text-xs text-gray-400 uppercase tracking-wider mb-1')
                ui.label(str(value)).classes('text-3xl font-bold text-white')

                if trend and trend_value:
                    # Map trend to color and icon
                    trend_styles = {
                        'up': ('text-green-400', 'trending_up'),
                        'down': ('text-red-400', 'trending_down'),
                        'neutral': ('text-gray-400', 'remove')  # horizontal line icon
                    }
                    trend_color, trend_icon = trend_styles.get(trend, ('text-gray-400', 'remove'))

                    with ui.row().classes('items-center gap-1 mt-1'):
                        ui.icon(trend_icon, size='xs').classes(trend_color)
                        ui.label(trend_value).classes(f'text-xs {trend_color}')

            if icon:
                ui.icon(icon, size='md').classes('text-white/20')


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
            ui.label(sender).classes('text-caption text-gray-400')

        # Timestamp
        timestamp = item.get('processing_started_at', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M')
                ui.label(time_str).classes('text-caption text-gray-500')
            except:
                pass


def create_empty_state(icon: str, title: str, description: str, action_label: str = None, action_route: str = None):
    """Create empty state UI"""
    with ui.column().classes('w-full items-center justify-center p-12 gap-4'):
        ui.icon(icon, size='xl').classes('text-grey-4')
        ui.label(title).classes('text-h6 text-gray-500')
        ui.label(description).classes('text-caption text-gray-600 text-center')

        if action_label and action_route:
            ui.button(action_label, on_click=lambda: ui.navigate.to(action_route), icon='add').props('color=primary')


class AnalyticsEngine:
    """Generate analytics data and charts for email processing"""

    def __init__(self):
        self.db = PersistenceLayer()

    def get_processing_stats(self) -> Dict[str, int]:
        """Get overall processing statistics"""
        return get_database_stats()

    def get_suppression_breakdown(self) -> Dict[str, int]:
        """Get suppression counts by category using new processing_log table"""
        try:
            return self.db.get_suppression_breakdown()
        except Exception as e:
            logger.error(f"Error getting suppression breakdown: {e}")
            return {}

    def get_reason_breakdown(self) -> Dict[str, int]:
        """Get suppression counts by reason using new processing_log table"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT suppression_reason, COUNT(*) as count
                    FROM processing_log
                    WHERE status = 'suppressed' AND suppression_reason IS NOT NULL
                    GROUP BY suppression_reason
                    ORDER BY count DESC
                    LIMIT 10
                """)

                results = {}
                for row in cursor.fetchall():
                    results[row[0]] = row[1]

                return results

        except Exception as e:
            logger.error(f"Error getting reason breakdown: {e}")
            return {}

    def get_top_suppressed_domains(self, limit: int = TOP_DOMAINS_LIMIT) -> Dict[str, int]:
        """Get top suppressed email domains/senders using new processing_log table"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT sender, COUNT(*) as count
                    FROM processing_log
                    WHERE status = 'suppressed' AND sender IS NOT NULL
                    GROUP BY sender
                    ORDER BY count DESC
                    LIMIT ?
                """, (limit,))

                results = {}
                for row in cursor.fetchall():
                    results[row[0]] = row[1]

                return results

        except Exception as e:
            logger.error(f"Error getting top domains: {e}")
            return {}

    def get_timeline_data(self, days: int = 30) -> Dict[str, List]:
        """Get daily processing counts for timeline chart using new processing_log table"""
        try:
            from datetime import datetime, timedelta

            # Get timeline data from persistence layer
            timeline = self.db.get_timeline_data(days=days)

            # Extract processed and suppressed data
            processed_data = {}
            suppressed_data = {}

            for date, counts in timeline.items():
                processed_data[date] = counts.get('success', 0)
                suppressed_data[date] = counts.get('suppressed', 0)

            # Create complete date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            dates = []
            processed_counts = []
            suppressed_counts = []

            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                dates.append(date_str)
                processed_counts.append(processed_data.get(date_str, 0))
                suppressed_counts.append(suppressed_data.get(date_str, 0))
                current_date += timedelta(days=1)

            return {
                'dates': dates,
                'processed': processed_counts,
                'suppressed': suppressed_counts
            }

        except Exception as e:
            logger.error(f"Error getting timeline data: {e}")
            return {'dates': [], 'processed': [], 'suppressed': []}

    def create_processing_pie_chart(self, stats: Dict[str, int]) -> go.Figure:
        """Create enhanced pie chart of processing breakdown"""
        labels = ['✅ Processed', '🚫 Suppressed', '❌ Failed']
        values = [stats.get('processed', 0), stats.get('suppressed', 0), stats.get('failed', 0)]
        colors = ['#10B981', '#F59E0B', '#EF4444']  # Modern Tailwind-like colors

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(
                colors=colors,
                line=dict(color='white', width=2)
            ),
            hole=0.4,  # Donut chart
            textinfo='label+percent',
            textfont=dict(size=14, family='Arial, sans-serif'),
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>',
            pull=[0.05, 0, 0]  # Slightly pull out the first slice
        )])

        fig.update_layout(
            title=dict(
                text='<b>Email Processing Overview</b>',
                font=dict(size=18, family='Arial, sans-serif')
            ),
            height=350,
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.2,
                xanchor='center',
                x=0.5
            ),
            margin=dict(t=60, b=60, l=20, r=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    def create_success_gauge_chart(self, stats: Dict[str, int]) -> go.Figure:
        """Create enhanced gauge chart for success rate"""
        total = stats.get('total', 0)
        if total == 0:
            success_rate = 0
        else:
            success_rate = (stats.get('processed', 0) / total) * 100

        # Determine color based on success rate
        if success_rate >= 90:
            bar_color = "#10B981"  # Green
        elif success_rate >= 70:
            bar_color = "#F59E0B"  # Amber
        else:
            bar_color = "#EF4444"  # Red

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=success_rate,
            number={'suffix': "%", 'font': {'size': 40, 'family': 'Arial, sans-serif'}},
            domain={'x': [0, 1], 'y': [0, 1]},
            title={
                'text': "<b>Success Rate</b>",
                'font': {'size': 18, 'family': 'Arial, sans-serif'}
            },
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 2},
                'bar': {'color': bar_color, 'thickness': 0.75},
                'bgcolor': 'white',
                'borderwidth': 2,
                'bordercolor': '#E5E7EB',
                'steps': [
                    {'range': [0, 70], 'color': '#FEE2E2'},
                    {'range': [70, 90], 'color': '#FEF3C7'},
                    {'range': [90, 100], 'color': '#D1FAE5'}
                ],
                'threshold': {
                    'line': {'color': "#10B981", 'width': 3},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))

        fig.update_layout(
            height=350,
            margin=dict(t=60, b=40, l=40, r=40),
            paper_bgcolor='rgba(0,0,0,0)',
            font={'family': 'Arial, sans-serif'}
        )

        return fig

    def create_category_bar_chart(self, category_data: Dict[str, int]) -> go.Figure:
        """Enhanced horizontal bar chart of suppression by category"""
        if not category_data:
            # Return empty chart
            fig = go.Figure()
            fig.update_layout(
                title='<b>No suppression data available</b>',
                height=300,
                paper_bgcolor='rgba(0,0,0,0)'
            )
            return fig

        categories = list(category_data.keys())
        counts = list(category_data.values())

        # Modern gradient colors for bars
        colors = ['#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#10B981']
        bar_colors = [colors[i % len(colors)] for i in range(len(categories))]

        fig = go.Figure(data=[go.Bar(
            y=categories,
            x=counts,
            orientation='h',
            marker=dict(
                color=bar_colors,
                line=dict(color='white', width=2)
            ),
            text=counts,
            textposition='outside',
            textfont=dict(size=12, family='Arial, sans-serif'),
            hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
        )])

        fig.update_layout(
            title=dict(
                text='<b>Suppression by Category</b>',
                font=dict(size=18, family='Arial, sans-serif')
            ),
            xaxis=dict(
                title='<b>Count</b>',
                gridcolor='#E5E7EB',
                showgrid=True
            ),
            yaxis=dict(
                title='<b>Category</b>',
                tickfont=dict(size=12)
            ),
            height=max(350, len(categories) * 50),
            margin=dict(t=60, b=60, l=150, r=60),
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'family': 'Arial, sans-serif'}
        )

        return fig

    def create_timeline_chart(self, timeline_data: Dict[str, List]) -> go.Figure:
        """Enhanced line chart showing processing timeline"""
        dates = timeline_data.get('dates', [])
        processed = timeline_data.get('processed', [])
        suppressed = timeline_data.get('suppressed', [])

        if not dates:
            fig = go.Figure()
            fig.update_layout(
                title='<b>No timeline data available</b>',
                height=400,
                paper_bgcolor='rgba(0,0,0,0)'
            )
            return fig

        fig = go.Figure()

        # Processed line with area fill
        fig.add_trace(go.Scatter(
            x=dates,
            y=processed,
            mode='lines+markers',
            name='✅ Processed',
            line=dict(color='#10B981', width=3, shape='spline'),
            marker=dict(size=8, symbol='circle', line=dict(color='white', width=2)),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.1)',
            hovertemplate='<b>%{x}</b><br>Processed: %{y}<extra></extra>'
        ))

        # Suppressed line with area fill
        fig.add_trace(go.Scatter(
            x=dates,
            y=suppressed,
            mode='lines+markers',
            name='🚫 Suppressed',
            line=dict(color='#F59E0B', width=3, shape='spline'),
            marker=dict(size=8, symbol='circle', line=dict(color='white', width=2)),
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.1)',
            hovertemplate='<b>%{x}</b><br>Suppressed: %{y}<extra></extra>'
        ))

        fig.update_layout(
            title=dict(
                text='<b>Processing Timeline</b>',
                font=dict(size=18, family='Arial, sans-serif')
            ),
            xaxis=dict(
                title='<b>Date</b>',
                gridcolor='#E5E7EB',
                showgrid=True,
                tickangle=-45
            ),
            yaxis=dict(
                title='<b>Count</b>',
                gridcolor='#E5E7EB',
                showgrid=True
            ),
            height=400,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='#E5E7EB',
                borderwidth=1
            ),
            margin=dict(t=80, b=80, l=60, r=40),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'family': 'Arial, sans-serif'}
        )

        return fig

    def create_top_domains_chart(self, domains_data: Dict[str, int]) -> go.Figure:
        """Horizontal bar chart of top suppressed domains"""
        if not domains_data:
            fig = go.Figure()
            fig.update_layout(title='No domain data available', height=300)
            return fig

        domains = list(domains_data.keys())
        counts = list(domains_data.values())

        # Truncate long email addresses for display
        display_domains = [d if len(d) <= 40 else d[:37] + '...' for d in domains]

        fig = go.Figure(data=[go.Bar(
            y=display_domains,
            x=counts,
            orientation='h',
            marker=dict(
                color='#2196F3',
                line=dict(color='#1976D2', width=1)
            ),
            text=counts,
            textposition='outside',
            hovertemplate='%{y}<br>Count: %{x}<extra></extra>'
        )])

        fig.update_layout(
            title='Top 10 Suppressed Domains',
            xaxis_title='Count',
            yaxis_title='Sender',
            height=max(350, len(domains) * 35),
            margin=dict(t=40, b=40, l=200, r=40),
            showlegend=False
        )

        return fig


class ConfigManager:
    """Manages .env file reading/writing with comment preservation"""

    def __init__(self, env_path: str = ".env"):
        self.env_path = env_path

    @staticmethod
    def validate_email(email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip()))

    @staticmethod
    def validate_domain(domain: str) -> bool:
        """Basic domain validation (supports @domain.com or domain.com)"""
        import re
        domain = domain.strip()
        # Allow @domain.com or domain.com format
        if domain.startswith('@'):
            domain = domain[1:]
        pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))

    def load_config(self) -> Dict[str, str]:
        """Load all config from .env file"""
        config = {}

        if not os.path.exists(self.env_path):
            return config

        try:
            with open(self.env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Parse key=value
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip().strip('"').strip("'")
                        config[key.strip()] = value

            return config

        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    def save_config(self, config: Dict[str, str]) -> tuple[bool, str]:
        """Save config to .env file, preserving structure"""
        try:
            # Read existing file to preserve comments and structure
            lines = []
            existing_keys = set()

            if os.path.exists(self.env_path):
                with open(self.env_path, 'r') as f:
                    for line in f:
                        stripped = line.strip()

                        # Preserve comments and empty lines
                        if not stripped or stripped.startswith('#'):
                            lines.append(line.rstrip())
                            continue

                        # Update existing key-value pairs
                        if '=' in stripped:
                            key = stripped.split('=', 1)[0].strip()
                            existing_keys.add(key)

                            if key in config:
                                # Update with new value
                                value = config[key]
                                lines.append(f"{key}={value}")
                            else:
                                # Keep original line
                                lines.append(line.rstrip())
                        else:
                            lines.append(line.rstrip())

            # Add new keys that weren't in the original file
            for key, value in config.items():
                if key not in existing_keys:
                    lines.append(f"{key}={value}")

            # Write back to file
            with open(self.env_path, 'w') as f:
                f.write('\n'.join(lines))
                f.write('\n')  # Final newline

            return True, "Configuration saved successfully"

        except Exception as e:
            return False, f"Error saving config: {str(e)}"

    def validate_config(self, config: Dict[str, str]) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []

        # Required fields
        required = ['CRM_API_KEY', 'CRM_API_BASE_URL', 'LLM_BASE_URL', 'LLM_MODEL']

        for field in required:
            if not config.get(field):
                errors.append(f"{field} is required")

        # URL validation
        url_fields = ['CRM_API_BASE_URL', 'LLM_BASE_URL']
        for field in url_fields:
            value = config.get(field, '')
            if value and not (value.startswith('http://') or value.startswith('https://')):
                errors.append(f"{field} must be a valid URL (http:// or https://)")

        # Validate email lists
        email_list_fields = ['INTERNAL_EMAILS', 'ALLOWLIST_DOMAINS', 'SUPPRESS_DOMAINS']
        for field in email_list_fields:
            value = config.get(field, '')
            if value:
                items = [item.strip() for item in value.split(',') if item.strip()]
                for item in items:
                    # Check if it's an email or domain
                    if '@' in item and not item.startswith('@'):
                        # Full email address
                        if not self.validate_email(item):
                            errors.append(f"Invalid email in {field}: {item}")
                    else:
                        # Domain (with or without @)
                        if not self.validate_domain(item):
                            errors.append(f"Invalid domain in {field}: {item}")

        # Validate domain lists (INTERNAL_DOMAINS)
        if config.get('INTERNAL_DOMAINS'):
            domains = [d.strip() for d in config['INTERNAL_DOMAINS'].split(',') if d.strip()]
            for domain in domains:
                if '@' in domain:
                    errors.append(f"INTERNAL_DOMAINS should not contain @ symbol: {domain}")
                elif not self.validate_domain(domain):
                    errors.append(f"Invalid domain in INTERNAL_DOMAINS: {domain}")

        return errors

    def test_crm_connection(self, api_key: str, base_url: str) -> Dict[str, Any]:
        """Test CRM API connectivity"""
        try:
            from crm_client import RealTimeXClient

            if not api_key or not base_url:
                return {
                    'success': False,
                    'message': 'API key and base URL are required'
                }

            client = RealTimeXClient(api_key, base_url)

            # Try a simple operation (this will depend on your CRM client's API)
            # For now, just check if we can instantiate the client
            return {
                'success': True,
                'message': 'Connected to RealTimeX CRM successfully'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }

    def test_llm_connection(self, api_key: str, base_url: str, model: str) -> Dict[str, Any]:
        """Test LLM API connectivity with detailed diagnostics"""
        try:
            from openai import OpenAI, APIConnectionError, AuthenticationError, APIStatusError
            
            if not base_url or not model:
                return {
                    'success': False,
                    'message': 'Base URL and model are required'
                }

            # Ensure base_url is a full URL
            if not base_url.startswith(('http://', 'https://')):
                return {
                    'success': False,
                    'message': 'Base URL must start with http:// or https://'
                }

            client = OpenAI(
                api_key=api_key or "not-needed", 
                base_url=base_url,
                timeout=15.0 # Local models might be slow to respond initially
            )

            # Try a simple completion
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )

            return {
                'success': True,
                'message': f'Connected successfully. Model: {model}',
                'model': model
            }

        except APIConnectionError as e:
            logger.error(f"LLM connection test failed (Connection): {e}")
            return {
                'success': False,
                'message': f'Connection Error: Could not reach {base_url}. Ensure the server is running and accessible. (Detail: {str(e)})'
            }
        except AuthenticationError as e:
            logger.error(f"LLM connection test failed (Auth): {e}")
            return {
                'success': False,
                'message': f'Authentication Error: Check your API key. (Detail: {str(e)})'
            }
        except APIStatusError as e:
            logger.error(f"LLM connection test failed (Status): {e}")
            return {
                'success': False,
                'message': f'API Error: {e.status_code} - {e.message}'
            }
        except Exception as e:
            logger.error(f"LLM connection test failed (General): {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }


def get_database_stats() -> Dict[str, int]:
    """Get statistics from SQLite database using new processing_log table"""
    try:
        db = PersistenceLayer()
        stats = db.get_processing_stats()

        # Map to legacy format for dashboard compatibility
        return {
            "total": stats["total"],
            "processed": stats["success"],
            "suppressed": stats["suppressed"],
            "failed": stats["failed"]
        }
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"total": 0, "processed": 0, "suppressed": 0, "failed": 0}


def get_suppressed_emails(limit: int = DEFAULT_LIMIT, category: str = None, search: str = None) -> List[Dict]:
    """Get suppressed emails from database using new processing_log table"""
    try:
        db = PersistenceLayer()

        # Use persistence layer's method which queries processing_log
        category_filter = category if category and category != "All" else None
        results = db.get_suppressed_emails(
            limit=limit,
            category=category_filter,
            sender=search if search else None
        )

        return results
    except Exception as e:
        logger.error(f"Error getting suppressed emails: {e}")
        return []


def get_suppression_stats() -> Dict[str, Any]:
    """Get suppression statistics"""
    try:
        db = PersistenceLayer()
        return db.get_suppression_stats()
    except Exception as e:
        logger.error(f"Error getting suppression stats: {e}")
        return {}


async def process_files_async(files: List[Path], force: bool = False, verbose: bool = False):
    """Process uploaded files asynchronously"""
    state.is_processing = True
    state.progress = 0
    state.total = len(files)
    state.logs = []

    # Initialize components
    load_dotenv()

    try:
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

        for idx, file_path in enumerate(files):
            state.current_file = file_path.name
            state.progress = idx

            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Processing {file_path.name}...")

            try:
                # Process in a thread to avoid blocking
                result = await asyncio.to_thread(
                    processor.process_email_file,
                    str(file_path),
                    force=force,
                    verbose=verbose
                )

                if result:
                    state.stats["processed"] += 1
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Processed {file_path.name}")
                else:
                    state.stats["suppressed"] += 1
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⊘ Suppressed {file_path.name}")

            except Exception as e:
                state.stats["failed"] += 1
                state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ Error: {file_path.name} - {str(e)}")

            await asyncio.sleep(0.1)  # Allow UI updates

        state.progress = state.total
        state.current_file = "Complete"
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Processing complete!")
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Processed: {state.stats['processed']}, Suppressed: {state.stats['suppressed']}, Failed: {state.stats['failed']}")

    except Exception as e:
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ Fatal error: {str(e)}")
        logger.error(f"Fatal error in process_files_async: {e}", exc_info=True)

    finally:
        state.is_processing = False
        # Clean up temporary files
        state.cleanup_files()


@ui.page('/')
def main_page():
    """Main page with tabbed interface (email-archiver style)"""
    app_dark_mode = apply_nexus_theme()
    
    # Create header with tabs
    tabs, dashboard_tab, upload_tab, analytics_tab, suppressed_tab, config_tab = create_header_with_tabs(app_dark_mode)

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

                # Recent Activity - Full width
                with ui.card().classes('w-full p-0 gap-0'): # p-0 for table-like feel
                    with ui.row().classes('p-4 border-b border-white/10 items-center justify-between'):
                         ui.label('RECENT ACTIVITY').classes('text-sm font-bold tracking-wide text-white')
                         ui.button('View All', icon='arrow_forward', color='white').props('flat dense size=sm')

                    # Get recent activity
                    try:
                        db = PersistenceLayer()
                        recent_items = db.get_processing_history(limit=10)

                        if recent_items:
                            # Header
                            with ui.row().classes('w-full px-4 py-2 border-b border-white/10 text-xs font-bold text-gray-400 uppercase tracking-wider'):
                                ui.label('Subject').classes('flex-[2]')
                                ui.label('Sender').classes('flex-[1]')
                                ui.label('Status').classes('w-24 text-center')
                                ui.label('Time').classes('w-24 text-right')

                            # Rows
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
                                
                                with ui.row().classes('w-full px-4 py-3 border-b border-white/5 items-center hover:bg-white/5 transition-colors'):
                                     ui.label(subject[:60] + '...').classes('flex-[2] font-medium text-sm truncate pr-2 text-white')
                                     ui.label(sender[:30] + '...').classes('flex-[1] text-xs text-gray-400 truncate pr-2')
                                     with ui.element('div').classes('w-24 flex justify-center'):
                                         status_badge(status, status)
                                     ui.label(time_str).classes('w-24 text-right text-xs text-gray-500 font-mono')

                        else:
                            # Empty state - Start fresh
                            with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                                ui.icon('inbox', size='xl').classes('text-gray-400')
                                ui.label('No Activity Yet').classes('text-h6 text-gray-500')
                                ui.label('Start fresh! Upload emails to begin processing.').classes('text-caption text-gray-600 text-center')
                    except Exception as e:
                        ui.label(f'Error loading activity: {e}').classes('text-negative text-caption')

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

                    # Auto-update logs (only when processing)
                    def update_logs():
                        log_container.clear()
                        with log_container:
                            for log in state.logs[-MAX_LOG_LINES:]:  # Show last N logs
                                ui.label(log).classes('font-mono text-sm')

                    # Timer only active when processing
                    ui.timer(TIMER_INTERVAL, update_logs, active=lambda: state.is_processing)

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
                    with ui.button('Refresh Data', on_click=lambda: ui.navigate.reload(), icon='refresh').props('outline'):
                        ui.tooltip('Reload analytics data')

                # Overview cards with charts
                with ui.row().classes('w-full gap-4 mb-4'):
                    # Pie chart card
                    with ui.card().classes('flex-1'):
                        stats = analytics.get_processing_stats()
                        pie_chart = analytics.create_processing_pie_chart(stats)
                        ui.plotly(pie_chart).classes('w-full')

                    # Gauge chart card
                    with ui.card().classes('flex-1'):
                        gauge_chart = analytics.create_success_gauge_chart(stats)
                        ui.plotly(gauge_chart).classes('w-full')

                # Category breakdown
                with ui.card().classes('w-full mb-4'):
                    category_data = analytics.get_suppression_breakdown()
                    if category_data:
                        category_chart = analytics.create_category_bar_chart(category_data)
                        ui.plotly(category_chart).classes('w-full')
                    else:
                        ui.label('No suppression data available yet').classes('text-gray-400 p-4')

                # Timeline chart
                with ui.card().classes('w-full mb-4'):
                    # Get number of days from selection
                    days_map = {'Last 7 Days': 7, 'Last 30 Days': 30, 'Last 90 Days': 90}
                    days = days_map.get(date_range_select.value, 30)

                    timeline_data = analytics.get_timeline_data(days=days)
                    if timeline_data['dates']:
                        timeline_chart = analytics.create_timeline_chart(timeline_data)
                        ui.plotly(timeline_chart).classes('w-full')
                    else:
                        ui.label('No timeline data available yet').classes('text-gray-400 p-4')

                # Two column layout for remaining charts
                with ui.row().classes('w-full gap-4'):
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

        # ========== CONFIG TAB ==========
        with ui.tab_panel(config_tab):
            with ui.column().classes('w-full p-6 gap-4'):
                config_manager = ConfigManager()
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
                # Page header
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Suppressed Emails').classes('text-h4 font-bold')
                    ui.icon('filter_list', size='lg').classes('text-primary')

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


def run_ui(host: str = '127.0.0.1', port: int = 8080):
    """Run the web UI"""
    ui.run(
        host=host,
        port=port,
        title='CRM Automator',
        favicon='📧',
        reload=False,
        show=True
    )


if __name__ == '__main__':
    run_ui()
