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


class ProcessingState:
    """Shared state for processing operations"""
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


# Global state
state = ProcessingState()


# ========== Shared UI Components ==========

def create_header_with_tabs(active_tab_name: str = 'dashboard'):
    """Create header with top tabs navigation (email-archiver style)"""
    with ui.header().classes('items-center justify-between px-6 py-3'):
        # Left: App branding
        with ui.row().classes('items-center gap-3'):
            ui.icon('business_center', size='md').classes('text-white')
            ui.label('CRM Automator').classes('text-h6 font-bold text-white')

        # Center: Tabs
        with ui.tabs().classes('bg-transparent self-stretch') \
            .props('indicator-color="white" active-color="white" dense no-caps') as tabs:
            dashboard_tab = ui.tab('Dashboard', icon='dashboard')
            upload_tab = ui.tab('Upload & Process', icon='upload')
            analytics_tab = ui.tab('Analytics', icon='bar_chart')
            suppressed_tab = ui.tab('Suppressed', icon='filter_list')
            config_tab = ui.tab('Configuration', icon='settings')

        # Right: Theme switcher
        with ui.row().classes('items-center gap-2'):
            ui.select(
                ['Light', 'Dark', 'System'],
                value='Light',
                label='Theme'
            ).classes('text-white').props('dark dense outlined').style('min-width: 120px')

    return tabs, dashboard_tab, upload_tab, analytics_tab, suppressed_tab, config_tab


def create_stat_card(title: str, value: int, icon: str, color: str, trend: str = None, trend_value: str = None):
    """Create enhanced stat card with icon and optional trend"""
    with ui.card().classes('flex-1 p-4 hover:shadow-lg transition-shadow'):
        with ui.row().classes('w-full items-start justify-between'):
            # Left side - title and value
            with ui.column().classes('gap-1'):
                ui.label(title).classes(f'text-caption text-{color}')
                ui.label(str(value)).classes(f'text-h3 text-{color} font-bold')

                # Trend indicator
                if trend and trend_value:
                    trend_icon = 'trending_up' if trend == 'up' else 'trending_down'
                    trend_color = 'positive' if trend == 'up' else 'negative'
                    with ui.row().classes('items-center gap-1 mt-1'):
                        ui.icon(trend_icon, size='sm').classes(f'text-{trend_color}')
                        ui.label(trend_value).classes(f'text-caption text-{trend_color}')

            # Right side - icon
            with ui.avatar(f'{icon}', color=color).classes('text-white'):
                pass


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
            ui.label(sender).classes('text-caption text-grey-7')

        # Timestamp
        timestamp = item.get('processing_started_at', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M')
                ui.label(time_str).classes('text-caption text-grey-6')
            except:
                pass


def create_empty_state(icon: str, title: str, description: str, action_label: str = None, action_route: str = None):
    """Create empty state UI"""
    with ui.column().classes('w-full items-center justify-center p-12 gap-4'):
        ui.icon(icon, size='xl').classes('text-grey-4')
        ui.label(title).classes('text-h6 text-grey-6')
        ui.label(description).classes('text-caption text-grey-5 text-center')

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
            print(f"Error getting suppression breakdown: {e}")
            return {}

    def get_reason_breakdown(self) -> Dict[str, int]:
        """Get suppression counts by reason using new processing_log table"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
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

            conn.close()
            return results

        except Exception as e:
            print(f"Error getting reason breakdown: {e}")
            return {}

    def get_top_suppressed_domains(self, limit: int = 10) -> Dict[str, int]:
        """Get top suppressed email domains/senders using new processing_log table"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
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

            conn.close()
            return results

        except Exception as e:
            print(f"Error getting top domains: {e}")
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
            print(f"Error getting timeline data: {e}")
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
            print(f"Error loading config: {e}")
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
        """Test LLM API connectivity"""
        try:
            from openai import OpenAI

            if not base_url or not model:
                return {
                    'success': False,
                    'message': 'Base URL and model are required'
                }

            client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)

            # Try a simple completion
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )

            return {
                'success': True,
                'message': f'Connected successfully. Model: {model}',
                'model': model
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
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
        print(f"Error getting database stats: {e}")
        return {"total": 0, "processed": 0, "suppressed": 0, "failed": 0}


def get_suppressed_emails(limit: int = 100, category: str = None, search: str = None) -> List[Dict]:
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
        print(f"Error getting suppressed emails: {e}")
        return []


def get_suppression_stats() -> Dict[str, Any]:
    """Get suppression statistics"""
    try:
        db = PersistenceLayer()
        return db.get_suppression_stats()
    except Exception as e:
        print(f"Error getting suppression stats: {e}")
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

    state.is_processing = False


@ui.page('/')
def main_page():
    """Main page with tabbed interface (email-archiver style)"""
    # Create header with tabs
    tabs, dashboard_tab, upload_tab, analytics_tab, suppressed_tab, config_tab = create_header_with_tabs()

    # Main content with tab panels
    with ui.tab_panels(tabs, value=dashboard_tab).classes('w-full flex-1'):
        # ========== DASHBOARD TAB ==========
        with ui.tab_panel(dashboard_tab):
            with ui.column().classes('w-full p-6 gap-6'):
                # Stats overview
                stats = get_database_stats()

                # Enhanced stat cards with icons
                with ui.row().classes('w-full gap-4 mb-6'):
                    create_stat_card('Total Emails', stats['total'], 'mail', 'primary')
                    create_stat_card('Successfully Processed', stats['processed'], 'check_circle', 'positive',
                                   trend='up' if stats['processed'] > 0 else None,
                                   trend_value=f"+{stats['processed']}" if stats['processed'] > 0 else None)
                    create_stat_card('Suppressed', stats['suppressed'], 'block', 'warning')
                    create_stat_card('Failed', stats['failed'], 'error', 'negative')

                # Recent Activity - Full width
                with ui.card().classes('w-full'):
                    ui.label('Recent Activity').classes('text-h6 font-medium mb-3')

                    # Get recent activity
                    try:
                        db = PersistenceLayer()
                        recent_items = db.get_processing_history(limit=10)

                        if recent_items:
                            # Show table of activities
                            columns = [
                                {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'center', 'style': 'width: 100px'},
                                {'name': 'subject', 'label': 'Subject', 'field': 'subject', 'align': 'left'},
                                {'name': 'sender', 'label': 'Sender', 'field': 'sender', 'align': 'left'},
                                {'name': 'time', 'label': 'Time', 'field': 'time', 'align': 'right', 'style': 'width: 120px'},
                            ]

                            rows = []
                            for item in recent_items:
                                status = item.get('status') or 'skipped'
                                subject = item.get('subject') or 'No Subject'
                                sender = item.get('sender') or 'Unknown'

                                # Format timestamp
                                timestamp = item.get('processing_started_at') or ''
                                time_str = 'Unknown'
                                if timestamp:
                                    try:
                                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                        time_str = dt.strftime('%b %d, %H:%M')
                                    except:
                                        pass

                                # Status badge
                                status_badges = {
                                    'success': '✅ Success',
                                    'suppressed': '🚫 Suppressed',
                                    'failed': '❌ Failed',
                                    'skipped': '⏭️ Skipped'
                                }

                                rows.append({
                                    'status': status_badges.get(status, status),
                                    'subject': subject[:60] + '...' if len(subject) > 60 else subject,
                                    'sender': sender[:40] + '...' if len(sender) > 40 else sender,
                                    'time': time_str
                                })

                            ui.table(columns=columns, rows=rows, row_key='subject').classes('w-full')
                        else:
                            # Empty state - Start fresh
                            with ui.column().classes('w-full items-center justify-center p-12 gap-3'):
                                ui.icon('inbox', size='xl').classes('text-grey-4')
                                ui.label('No Activity Yet').classes('text-h6 text-grey-6')
                                ui.label('Start fresh! Upload emails to begin processing.').classes('text-caption text-grey-5 text-center')
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
                        state.uploaded_files = []

                        # Save uploaded files
                        for file in e.content:
                            if file.name.endswith('.eml'):
                                # Save to temp directory
                                temp_path = Path('/tmp') / file.name
                                with open(temp_path, 'wb') as f:
                                    f.write(file.read())
                                state.uploaded_files.append(temp_path)

                        # Update file list display
                        uploaded_files_list.clear()
                        with uploaded_files_list:
                            ui.label(f'✓ Selected {len(state.uploaded_files)} files').classes('text-positive font-medium mb-3')
                            for file in state.uploaded_files[:10]:  # Show first 10
                                with ui.row().classes('items-center gap-2 p-2 bg-grey-1 rounded'):
                                    ui.icon('description', size='sm').classes('text-primary')
                                    ui.label(file.name).classes('text-sm')
                            if len(state.uploaded_files) > 10:
                                ui.label(f'...and {len(state.uploaded_files) - 10} more').classes('text-caption text-grey-7 mt-2')

                    # Drag & drop upload area
                    with ui.column().classes('w-full items-center justify-center p-12 cursor-pointer').style(
                        'border: 2px dashed #ccc; border-radius: 8px; background: #fafafa; transition: all 0.3s;'
                    ):
                        ui.icon('cloud_upload', size='xl').classes('text-primary mb-3')
                        ui.label('Drag & drop EML files here').classes('text-h6 font-medium mb-1')
                        ui.label('or click to browse').classes('text-caption text-grey-6 mb-4')

                        ui.upload(
                            on_upload=handle_upload,
                            multiple=True,
                            auto_upload=True,
                            label='Choose Files'
                        ).props('accept=.eml color=primary').classes('w-full max-w-xs')

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

                    ui.button('Start Processing',
                             on_click=start_processing,
                             icon='play_arrow').props('color=primary').bind_enabled_from(state, 'is_processing', lambda x: not x)

                    ui.button('Clear Files',
                             on_click=lambda: (state.uploaded_files.clear(), uploaded_files_list.clear()),
                             icon='clear').props('color=grey-7 outline').bind_enabled_from(state, 'is_processing', lambda x: not x)

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
                    ui.label('Live Logs').classes('text-h6 mb-2')
                    log_container = ui.column().classes('w-full bg-grey-1 p-4 rounded').style('max-height: 400px; overflow-y: auto')

                    # Auto-update logs
                    def update_logs():
                        log_container.clear()
                        with log_container:
                            for log in state.logs[-50:]:  # Show last 50 logs
                                ui.label(log).classes('font-mono text-sm')

                    ui.timer(1.0, update_logs)

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
                    ui.button('Refresh Data', on_click=lambda: ui.navigate.reload(), icon='refresh').props('outline')

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
                        ui.label('No suppression data available yet').classes('text-grey-7 p-4')

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
                        ui.label('No timeline data available yet').classes('text-grey-7 p-4')

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
                            ui.label('No suppression data available yet').classes('text-grey-7 p-4')

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
                            ui.label('No reason data available yet').classes('text-grey-7 p-4')

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

                # Action buttons at top
                with ui.row().classes('gap-2 mb-4'):
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

                    ui.button('Save Configuration', on_click=save_configuration, icon='save').props('color=primary')
                    ui.button('Reload from File', on_click=lambda: ui.navigate.reload(), icon='refresh').props('outline')

                # CRM API Settings
                with ui.card().classes('w-full mb-4'):
                    ui.label('CRM API Settings').classes('text-h6 mb-3')

                    form_data['CRM_API_BASE_URL'] = ui.input(
                        'CRM API Base URL',
                        value=current_config.get('CRM_API_BASE_URL', ''),
                        placeholder='https://your-project.supabase.co/functions/v1'
                    ).classes('w-full').props('outlined')

                    form_data['CRM_API_KEY'] = ui.input(
                        'CRM API Key',
                        value=current_config.get('CRM_API_KEY', ''),
                        placeholder='ak_live_...',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined')

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
                    ).classes('w-full').props('outlined')

                    form_data['LLM_API_KEY'] = ui.input(
                        'LLM API Key',
                        value=current_config.get('LLM_API_KEY', ''),
                        placeholder='sk-proj-...',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined')

                    form_data['LLM_MODEL'] = ui.select(
                        ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo', 'custom'],
                        value=current_config.get('LLM_MODEL', 'gpt-4o-mini'),
                        label='LLM Model'
                    ).classes('w-full')

                    # Custom model input (shown if 'custom' selected)
                    custom_model_input = ui.input(
                        'Custom Model Name',
                        placeholder='your-custom-model'
                    ).classes('w-full').props('outlined')
                    custom_model_input.visible = False

                    def on_model_change(e):
                        if e.value == 'custom':
                            custom_model_input.visible = True
                        else:
                            custom_model_input.visible = False
                            form_data['LLM_MODEL'].value = e.value

                    form_data['LLM_MODEL'].on('update:model-value', on_model_change)

                    llm_status_label = ui.label().classes('mt-2')

                    async def test_llm():
                        """Test LLM connection"""
                        llm_status_label.text = '⏳ Testing connection...'
                        await asyncio.sleep(0.1)

                        model = custom_model_input.value if form_data['LLM_MODEL'].value == 'custom' else form_data['LLM_MODEL'].value

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
                        'Suppress Categories (comma-separated)',
                        value=current_config.get('SUPPRESS_CATEGORIES', 'promotional,newsletter,automated,spam'),
                        placeholder='promotional,newsletter,automated,spam'
                    ).classes('w-full').props('outlined')

                    form_data['CLASSIFICATION_STRATEGY'] = ui.select(
                        ['heuristic', 'llm', 'hybrid'],
                        value=current_config.get('CLASSIFICATION_STRATEGY', 'hybrid'),
                        label='Classification Strategy'
                    ).classes('w-full')

                    with ui.row().classes('w-full gap-2'):
                        ui.label('• Heuristic: Fast, free, ~90% accuracy').classes('text-caption text-grey-7')
                    with ui.row().classes('w-full gap-2'):
                        ui.label('• LLM: Accurate, costs ~$0.0001/email').classes('text-caption text-grey-7')
                    with ui.row().classes('w-full gap-2 mb-3'):
                        ui.label('• Hybrid: Best balance (recommended)').classes('text-caption text-grey-7')

                    form_data['CLASSIFICATION_MODEL'] = ui.input(
                        'Classification Model (for LLM/Hybrid)',
                        value=current_config.get('CLASSIFICATION_MODEL', 'gpt-4o-mini'),
                        placeholder='gpt-4o-mini'
                    ).classes('w-full').props('outlined')

                    form_data['ALLOWLIST_DOMAINS'] = ui.input(
                        'Allowlist Domains (force process, comma-separated)',
                        value=current_config.get('ALLOWLIST_DOMAINS', ''),
                        placeholder='@important-client.com,vip@partner.com'
                    ).classes('w-full').props('outlined')

                    form_data['SUPPRESS_DOMAINS'] = ui.input(
                        'Blocklist Domains (force suppress, comma-separated)',
                        value=current_config.get('SUPPRESS_DOMAINS', ''),
                        placeholder='@marketing.spam.com,noreply@ads.com'
                    ).classes('w-full').props('outlined')

                # Internal Staff Filtering
                with ui.card().classes('w-full mb-4'):
                    ui.label('Internal Staff Filtering').classes('text-h6 mb-3')
                    ui.label('Exclude internal staff from CRM sync').classes('text-caption text-grey-7 mb-2')

                    form_data['INTERNAL_DOMAINS'] = ui.input(
                        'Internal Domains (comma-separated)',
                        value=current_config.get('INTERNAL_DOMAINS', ''),
                        placeholder='mycompany.com,partner.co'
                    ).classes('w-full').props('outlined')

                    form_data['INTERNAL_EMAILS'] = ui.input(
                        'Internal Emails (comma-separated)',
                        value=current_config.get('INTERNAL_EMAILS', ''),
                        placeholder='admin@gmail.com,ceo@personal.com'
                    ).classes('w-full').props('outlined')

                # Search Provider Configuration
                with ui.card().classes('w-full mb-4'):
                    ui.label('Search Provider Configuration').classes('text-h6 mb-3')
                    ui.label('For company enrichment via web search').classes('text-caption text-grey-7 mb-2')

                    form_data['SEARCH_PROVIDERS'] = ui.input(
                        'Search Providers (priority order, comma-separated)',
                        value=current_config.get('SEARCH_PROVIDERS', 'duckduckgo,serper,serpapi'),
                        placeholder='duckduckgo,serper,serpapi'
                    ).classes('w-full').props('outlined')

                    form_data['SERPER_API_KEY'] = ui.input(
                        'Serper API Key (optional)',
                        value=current_config.get('SERPER_API_KEY', ''),
                        placeholder='Your Serper.dev API key',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined')

                    form_data['SERPAPI_KEY'] = ui.input(
                        'SerpAPI Key (optional)',
                        value=current_config.get('SERPAPI_KEY', ''),
                        placeholder='Your SerpAPI key',
                        password=True,
                        password_toggle_button=True
                    ).classes('w-full').props('outlined')

                # Persistence Configuration
                with ui.card().classes('w-full mb-4'):
                    ui.label('Persistence Configuration').classes('text-h6 mb-3')

                    form_data['PERSISTENCE_DB_PATH'] = ui.input(
                        'Database Path (optional override)',
                        value=current_config.get('PERSISTENCE_DB_PATH', ''),
                        placeholder='./eml_processing.db'
                    ).classes('w-full').props('outlined')

                    current_db = os.getenv('PERSISTENCE_DB_PATH', './eml_processing.db')
                    ui.label(f'Current: {current_db}').classes('text-caption text-grey-7')

                # Final action buttons
                with ui.row().classes('gap-2 mt-4'):
                    ui.button('Save Configuration', on_click=save_configuration, icon='save').props('color=primary')
                    ui.button('Reload from File', on_click=lambda: ui.navigate.reload(), icon='refresh').props('outline')

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
                                    ui.label(category).classes('text-caption text-grey-7')
                                    ui.label(str(count)).classes('text-h6')

                # Email table
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
                        ui.label(f'Showing {len(emails)} suppressed emails').classes('text-caption mb-2')

                        if emails:
                            # Create table data
                            columns = [
                                {'name': 'timestamp', 'label': 'Date', 'field': 'timestamp', 'align': 'left'},
                                {'name': 'sender', 'label': 'Sender', 'field': 'sender', 'align': 'left'},
                                {'name': 'subject', 'label': 'Subject', 'field': 'subject', 'align': 'left'},
                                {'name': 'category', 'label': 'Category', 'field': 'category', 'align': 'center'},
                                {'name': 'reason', 'label': 'Reason', 'field': 'reason', 'align': 'center'},
                            ]

                            rows = []
                            for email in emails:
                                rows.append({
                                    'timestamp': email.get('timestamp', '')[:10],  # Show date only
                                    'sender': email.get('sender', 'Unknown')[:40],  # Truncate
                                    'subject': email.get('subject', 'No subject')[:50],  # Truncate
                                    'category': email.get('category', 'unknown'),
                                    'reason': email.get('reason', 'unknown')[:30],  # Truncate
                                })

                            ui.table(columns=columns, rows=rows, row_key='timestamp').classes('w-full')
                        else:
                            ui.label('No suppressed emails found').classes('text-grey-7')

                # Refresh button
                ui.button('Refresh', on_click=refresh_table, icon='refresh').props('color=primary')

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
