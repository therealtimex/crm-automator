"""
Analytics and Visualization Module for CRM Automator

This module provides analytics data generation and interactive chart creation
for email processing metrics. It queries the SQLite database and generates
Plotly charts for the web UI.

Classes:
    AnalyticsEngine: Main analytics class with chart generation methods

Functions:
    get_database_stats: Fetch overall processing statistics
    get_suppressed_emails: Query suppressed email list with filters
    get_suppression_stats: Get suppression breakdown by category

Chart Types:
    - Processing pie chart (breakdown by status)
    - Success rate gauge chart
    - Category bar chart (suppression categories)
    - Timeline chart (daily processing trends)
    - Top domains chart (most suppressed senders)
"""

import logging
import sqlite3
from typing import Dict, List, Any
import plotly.graph_objects as go

# Configure logging
logger = logging.getLogger(__name__)

# Constants
TOP_DOMAINS_LIMIT = 10
DEFAULT_LIMIT = 100

# Import PersistenceLayer
try:
    from eml.persistence import PersistenceLayer
except ImportError:
    try:
        from persistence import PersistenceLayer
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from persistence import PersistenceLayer

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
        """Enhanced pie chart of processing breakdown"""
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
        """Enhanced gauge chart for success rate"""
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
