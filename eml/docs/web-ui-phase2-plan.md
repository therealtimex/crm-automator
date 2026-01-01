# Web UI Phase 2 Implementation Plan

## Overview

Phase 2 builds on the Phase 1 MVP with advanced features for configuration management, data visualization, and database exploration.

**Goals:**
- Make configuration management user-friendly
- Provide visual insights into email processing patterns
- Enable power users to explore data with SQL

**Timeline:** Estimated 4-6 hours of development

---

## Feature 1: Configuration Editor (`/config`)

### Description
Visual interface for editing `.env` configuration without touching files. Includes validation, testing, and organized categories.

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️ Configuration                                            │
├─────────────────────────────────────────────────────────────┤
│  [Save Configuration] [Reset to Defaults] [Test All]        │
│                                                              │
│  📦 CRM API Settings                                        │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ CRM API Base URL *                                     │ │
│  │ [https://...supabase.co/functions/v1_______________]   │ │
│  │                                                         │ │
│  │ CRM API Key * (required)                               │ │
│  │ [ak_live_*********************] [Show] [Test]         │ │
│  │ ✅ Connected to RealTimeX CRM                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  🤖 LLM Configuration                                       │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ LLM Base URL *                                         │ │
│  │ [https://api.openai.com/v1_____________________]       │ │
│  │                                                         │ │
│  │ LLM API Key *                                          │ │
│  │ [sk-proj-*********************] [Show] [Test]         │ │
│  │                                                         │ │
│  │ LLM Model                                              │ │
│  │ [gpt-4o-mini ▼] gpt-3.5-turbo, gpt-4o, gpt-4-turbo   │ │
│  │ ✅ Connected (gpt-4o-mini available)                   │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  🔍 Email Filtering                                         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Suppress Categories (comma-separated)                  │ │
│  │ [promotional,newsletter,automated,spam____________]    │ │
│  │                                                         │ │
│  │ Classification Strategy                                │ │
│  │ ○ Heuristic (fast, free, ~90% accuracy)              │ │
│  │ ○ LLM (accurate, costs ~$0.0001/email)               │ │
│  │ ● Hybrid (recommended - best balance)                │ │
│  │                                                         │ │
│  │ Classification Model (for LLM/Hybrid)                  │ │
│  │ [gpt-4o-mini ▼]                                       │ │
│  │                                                         │ │
│  │ Allowlist Domains (force process)                      │ │
│  │ [@important-client.com,vip@partner.com_________]       │ │
│  │                                                         │ │
│  │ Blocklist Domains (force suppress)                     │ │
│  │ [@marketing.spam.com,noreply@ads.com___________]       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  🏢 Internal Staff Filtering                                │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Internal Domains (exclude from CRM)                    │ │
│  │ [mycompany.com,partner.co______________________]       │ │
│  │                                                         │ │
│  │ Internal Emails (staff using public domains)           │ │
│  │ [admin@gmail.com,ceo@personal.com______________]       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  🔎 Search Provider Configuration                           │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Search Providers (priority order)                      │ │
│  │ [duckduckgo,serper,serpapi_____________________]       │ │
│  │                                                         │ │
│  │ Serper API Key (optional, for paid search)            │ │
│  │ [your_serper_key_here__________________________]       │ │
│  │                                                         │ │
│  │ SerpAPI Key (optional)                                 │ │
│  │ [your_serpapi_key_here_________________________]       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  💾 Persistence Configuration                               │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Database Path (optional override)                      │ │
│  │ [/custom/path/to/db.sqlite_____________________]       │ │
│  │ Current: /Users/.../eml_processing.db                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  [Save Configuration] [Reset to Defaults] [Test All]        │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Details

**File Structure:**
```python
# In web_ui.py

class ConfigManager:
    """Manages .env file reading/writing"""

    def __init__(self, env_path: str = ".env"):
        self.env_path = env_path

    def load_config(self) -> Dict[str, str]:
        """Load all config from .env"""
        # Parse .env file
        # Return dict of key-value pairs

    def save_config(self, config: Dict[str, str]) -> bool:
        """Save config to .env file"""
        # Validate required fields
        # Write to .env with comments preserved
        # Return success/failure

    def test_crm_connection(self, api_key: str, base_url: str) -> Dict:
        """Test CRM API connectivity"""
        # Try to connect to CRM
        # Return status + error message if any

    def test_llm_connection(self, api_key: str, base_url: str, model: str) -> Dict:
        """Test LLM API connectivity"""
        # Try simple completion request
        # Return status + available models if successful

    def validate_config(self, config: Dict[str, str]) -> List[str]:
        """Validate configuration"""
        # Check required fields
        # Validate formats (URLs, etc.)
        # Return list of validation errors

@ui.page('/config')
def config_page():
    """Configuration editor page"""

    config_manager = ConfigManager()
    current_config = config_manager.load_config()

    # Header with save buttons
    with ui.row().classes('w-full mb-4'):
        ui.button('Save', on_click=save_config)
        ui.button('Reset to Defaults', on_click=reset_config)
        ui.button('Test All', on_click=test_all_connections)

    # CRM Settings Card
    with ui.card().classes('w-full mb-4'):
        ui.label('CRM API Settings').classes('text-h6')

        crm_url_input = ui.input(
            'CRM API Base URL',
            value=current_config.get('CRM_API_BASE_URL', '')
        ).props('required')

        crm_key_input = ui.input(
            'CRM API Key',
            value=current_config.get('CRM_API_KEY', ''),
            password=True,
            password_toggle_button=True
        ).props('required')

        crm_status = ui.label()
        ui.button('Test Connection', on_click=lambda: test_crm(crm_url_input.value, crm_key_input.value))

    # LLM Settings Card
    # ... similar structure

    # Filtering Settings Card
    # ... similar structure
```

**Features:**
- ✅ Live validation (red border for invalid fields)
- ✅ Password fields with show/hide toggle
- ✅ Test buttons for API connections (async, non-blocking)
- ✅ Success/error indicators
- ✅ Dropdown presets for common values (models, strategies)
- ✅ Help tooltips explaining each setting
- ✅ Preserve comments when saving .env
- ✅ Undo/redo support
- ✅ Unsaved changes warning

**Technical Challenges:**
1. **Preserving .env comments** - Need custom parser to keep comment lines
2. **Async API testing** - Non-blocking UI during connection tests
3. **Security** - Don't log API keys, mask in UI
4. **Validation** - Real-time feedback without being annoying

---

## Feature 2: Charts & Analytics (`/analytics`)

### Description
Visual data analysis with interactive charts showing email processing patterns, filtering statistics, and trends over time.

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  📊 Analytics & Charts                                       │
├─────────────────────────────────────────────────────────────┤
│  🗓️ Date Range: [Last 30 Days ▼]  [Refresh Data]           │
│                                                              │
│  ┌──────────────────────────┐ ┌──────────────────────────┐ │
│  │ 📈 Processing Overview   │ │ 🎯 Success Rate          │ │
│  │ ┌────────────────────┐   │ │ ┌────────────────────┐   │ │
│  │ │ Pie Chart:         │   │ │ │ Gauge Chart:       │   │ │
│  │ │ - Processed: 65%   │   │ │ │    95.3%           │   │ │
│  │ │ - Suppressed: 33%  │   │ │ │    Success         │   │ │
│  │ │ - Failed: 2%       │   │ │ │                    │   │ │
│  │ └────────────────────┘   │ │ └────────────────────┘   │ │
│  └──────────────────────────┘ └──────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 📊 Suppression by Category                           │   │
│  │ ┌──────────────────────────────────────────────────┐ │   │
│  │ │ Horizontal Bar Chart:                            │ │   │
│  │ │ promotional    ████████████████████ 234          │ │   │
│  │ │ newsletter     ██████████████ 189                │ │   │
│  │ │ automated      ███████ 97                        │ │   │
│  │ │ spam           ████ 67                           │ │   │
│  │ │ notification   ██ 34                             │ │   │
│  │ └──────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 📈 Processing Timeline (Last 30 Days)                │   │
│  │ ┌──────────────────────────────────────────────────┐ │   │
│  │ │ Line Chart:                                      │ │   │
│  │ │    ^                                             │ │   │
│  │ │ 50 │     ●──●                                    │ │   │
│  │ │    │    /    \    ●──●                           │ │   │
│  │ │ 25 │   ●      ●──●    \                          │ │   │
│  │ │    │                   ●──●                      │ │   │
│  │ │  0 └────────────────────────────────────>        │ │   │
│  │ │     1  5  10  15  20  25  30 (days)             │ │   │
│  │ │                                                   │ │   │
│  │ │ Legend: ─ Processed  ─ Suppressed  ─ Failed    │ │   │
│  │ └──────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🔝 Top 10 Suppressed Domains                         │   │
│  │ ┌──────────────────────────────────────────────────┐ │   │
│  │ │ Horizontal Bar Chart:                            │ │   │
│  │ │ marketing@vendor.com    ████████████████ 87      │ │   │
│  │ │ newsletter@company.com  █████████████ 65         │ │   │
│  │ │ noreply@ads.com         ████████ 43              │ │   │
│  │ │ updates@service.com     ██████ 32                │ │   │
│  │ │ ...                                              │ │   │
│  │ └──────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🎨 Classification Method Distribution                │   │
│  │ ┌──────────────────────────────────────────────────┐ │   │
│  │ │ Stacked Bar Chart:                               │ │   │
│  │ │ Heuristics: ████████████████████ 450 (90%)       │ │   │
│  │ │ LLM:        ████ 50 (10%)                        │ │   │
│  │ │ EESA:       █ 10 (2%)                            │ │   │
│  │ └──────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Chart Library Selection

**Option 1: Plotly (Recommended)**
- ✅ Interactive (zoom, pan, hover tooltips)
- ✅ Professional appearance
- ✅ Good NiceGUI integration
- ✅ Wide variety of chart types
- ❌ Larger file size (~3MB)

**Option 2: ECharts**
- ✅ Lightweight
- ✅ Beautiful defaults
- ✅ Good performance
- ❌ Less Python-friendly

**Decision: Use Plotly**

### Implementation Details

```python
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

class AnalyticsEngine:
    """Generate analytics data and charts"""

    def __init__(self, db: PersistenceLayer):
        self.db = db

    def get_date_range_data(self, days: int = 30) -> Dict:
        """Get processing data for date range"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()

        # Get daily counts
        cursor.execute("""
            SELECT DATE(timestamp) as date,
                   COUNT(*) as count
            FROM suppressed_emails
            WHERE timestamp >= date('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        """.format(days))

        # Process results
        # Return structured data

    def create_processing_pie_chart(self, stats: Dict) -> go.Figure:
        """Create pie chart of processing breakdown"""
        fig = go.Figure(data=[go.Pie(
            labels=['Processed', 'Suppressed', 'Failed'],
            values=[stats['processed'], stats['suppressed'], stats['failed']],
            marker=dict(colors=['#4CAF50', '#FF9800', '#F44336'])
        )])

        fig.update_layout(
            title='Email Processing Overview',
            height=300
        )

        return fig

    def create_category_bar_chart(self, category_stats: Dict) -> go.Figure:
        """Horizontal bar chart of suppression by category"""
        categories = list(category_stats.keys())
        counts = list(category_stats.values())

        fig = go.Figure(data=[go.Bar(
            y=categories,
            x=counts,
            orientation='h',
            marker=dict(color='#FF9800')
        )])

        fig.update_layout(
            title='Suppression by Category',
            xaxis_title='Count',
            yaxis_title='Category',
            height=400
        )

        return fig

    def create_timeline_chart(self, daily_data: List[Dict]) -> go.Figure:
        """Line chart showing processing over time"""
        dates = [d['date'] for d in daily_data]
        processed = [d['processed'] for d in daily_data]
        suppressed = [d['suppressed'] for d in daily_data]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=dates, y=processed,
            mode='lines+markers',
            name='Processed',
            line=dict(color='#4CAF50', width=2)
        ))

        fig.add_trace(go.Scatter(
            x=dates, y=suppressed,
            mode='lines+markers',
            name='Suppressed',
            line=dict(color='#FF9800', width=2)
        ))

        fig.update_layout(
            title='Processing Timeline',
            xaxis_title='Date',
            yaxis_title='Count',
            height=400,
            hovermode='x unified'
        )

        return fig

@ui.page('/analytics')
def analytics_page():
    """Analytics and charts page"""

    analytics = AnalyticsEngine(PersistenceLayer())

    # Date range selector
    date_range = ui.select(
        ['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'All Time'],
        value='Last 30 Days'
    )

    ui.button('Refresh Data', on_click=refresh_charts)

    # Overview cards with pie chart and gauge
    with ui.row().classes('w-full gap-4 mb-4'):
        with ui.card().classes('flex-1'):
            stats = get_database_stats()
            pie_chart = analytics.create_processing_pie_chart(stats)
            ui.plotly(pie_chart).classes('w-full')

        with ui.card().classes('flex-1'):
            # Gauge chart for success rate
            success_rate = calculate_success_rate()
            gauge_chart = create_gauge_chart(success_rate)
            ui.plotly(gauge_chart).classes('w-full')

    # Category breakdown
    with ui.card().classes('w-full mb-4'):
        category_stats = analytics.get_category_breakdown()
        category_chart = analytics.create_category_bar_chart(category_stats)
        ui.plotly(category_chart).classes('w-full')

    # Timeline
    with ui.card().classes('w-full mb-4'):
        timeline_data = analytics.get_timeline_data(days=30)
        timeline_chart = analytics.create_timeline_chart(timeline_data)
        ui.plotly(timeline_chart).classes('w-full')

    # Top domains
    with ui.card().classes('w-full'):
        top_domains = analytics.get_top_suppressed_domains(limit=10)
        domains_chart = create_domains_chart(top_domains)
        ui.plotly(domains_chart).classes('w-full')
```

**Features:**
- ✅ Interactive charts (zoom, pan, tooltips)
- ✅ Date range filtering
- ✅ Auto-refresh option
- ✅ Export charts as PNG
- ✅ Responsive design
- ✅ Color-coded by category
- ✅ Comparison views (this week vs last week)

---

## Feature 3: Database Explorer (`/database`)

### Description
Interactive SQL query interface for power users to explore and analyze data directly.

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  💾 Database Explorer                                        │
├─────────────────────────────────────────────────────────────┤
│  📋 Quick Queries                                           │
│  [All Processed] [All Suppressed] [Last 24h] [Failed Only]  │
│                                                              │
│  🗂️ Table: [suppressed_emails ▼] processed_emails          │
│  📊 Rows: 356 | Size: 1.2 MB | Last Modified: 2 mins ago   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🔧 Query Builder                                     │   │
│  │ ┌────────────────────────────────────────────────┐   │   │
│  │ │ SELECT [* ▼] [COUNT(*), sender, category]     │   │   │
│  │ │ FROM   [suppressed_emails ▼]                  │   │   │
│  │ │ WHERE  [category ▼] [= ▼] [promotional____]  │   │   │
│  │ │        [+ Add Condition]                       │   │   │
│  │ │ ORDER BY [timestamp ▼] [DESC ▼]               │   │   │
│  │ │ LIMIT  [100____]                               │   │   │
│  │ │                                                 │   │   │
│  │ │ [🔨 Build Query] [🧹 Clear]                   │   │   │
│  │ └────────────────────────────────────────────────┘   │   │
│  │                                                       │   │
│  │ 💻 Raw SQL Editor                                    │   │
│  │ ┌────────────────────────────────────────────────┐   │   │
│  │ │ SELECT sender, COUNT(*) as count               │   │   │
│  │ │ FROM suppressed_emails                         │   │   │
│  │ │ WHERE category = 'promotional'                 │   │   │
│  │ │ GROUP BY sender                                │   │   │
│  │ │ ORDER BY count DESC                            │   │   │
│  │ │ LIMIT 10;                                      │   │   │
│  │ │                                                 │   │   │
│  │ │ [▶ Run Query (Ctrl+Enter)] [💾 Save] [📋 Copy]│   │   │
│  │ └────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ✅ Query executed in 12ms | 45 rows returned               │
│                                                              │
│  📊 Results                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ sender                  │ count │                     │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ marketing@vendor.com    │  87   │                     │   │
│  │ newsletter@company.com  │  65   │                     │   │
│  │ noreply@ads.com         │  43   │                     │   │
│  │ ...                     │  ...  │                     │   │
│  └──────────────────────────────────────────────────────┘   │
│  [⬅ Previous] Page 1 of 5 [Next ➡]                         │
│                                                              │
│  [📥 Export CSV] [📄 Export JSON] [📊 Visualize Results]   │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Details

```python
import sqlite3
import csv
import json
from io import StringIO

class DatabaseExplorer:
    """SQL query interface and database exploration"""

    def __init__(self, db: PersistenceLayer):
        self.db = db
        self.read_only = True  # Safety: only allow SELECT queries

    def execute_query(self, sql: str, params: tuple = ()) -> Dict:
        """Execute SQL query safely"""

        # Safety check: only allow SELECT
        if not sql.strip().upper().startswith('SELECT'):
            return {
                'success': False,
                'error': 'Only SELECT queries are allowed for safety'
            }

        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            start_time = time.time()
            cursor.execute(sql, params)
            execution_time = (time.time() - start_time) * 1000  # ms

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            conn.close()

            return {
                'success': True,
                'columns': columns,
                'rows': rows,
                'row_count': len(rows),
                'execution_time': execution_time
            }

        except sqlite3.Error as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_table_schema(self, table_name: str) -> List[Dict]:
        """Get table column information"""
        result = self.execute_query(f"PRAGMA table_info({table_name})")
        if result['success']:
            return [
                {
                    'name': row[1],
                    'type': row[2],
                    'nullable': not row[3],
                    'primary_key': bool(row[5])
                }
                for row in result['rows']
            ]
        return []

    def get_table_stats(self, table_name: str) -> Dict:
        """Get table statistics"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()

        # Row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]

        # Size (approximate)
        cursor.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
        size_bytes = cursor.fetchone()[0]

        conn.close()

        return {
            'row_count': row_count,
            'size_bytes': size_bytes,
            'size_mb': size_bytes / (1024 * 1024)
        }

    def export_to_csv(self, columns: List[str], rows: List[tuple]) -> str:
        """Export query results to CSV"""
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        writer.writerows(rows)
        return output.getvalue()

    def export_to_json(self, columns: List[str], rows: List[tuple]) -> str:
        """Export query results to JSON"""
        data = [dict(zip(columns, row)) for row in rows]
        return json.dumps(data, indent=2, default=str)

class QueryBuilder:
    """Visual query builder"""

    def build_select_query(
        self,
        table: str,
        columns: List[str] = None,
        where_conditions: List[Dict] = None,
        order_by: str = None,
        order_dir: str = 'ASC',
        limit: int = 100
    ) -> str:
        """Build SELECT query from components"""

        # SELECT clause
        if columns:
            select_clause = f"SELECT {', '.join(columns)}"
        else:
            select_clause = "SELECT *"

        # FROM clause
        query = f"{select_clause} FROM {table}"

        # WHERE clause
        if where_conditions:
            where_parts = []
            for cond in where_conditions:
                where_parts.append(f"{cond['column']} {cond['operator']} '{cond['value']}'")
            query += " WHERE " + " AND ".join(where_parts)

        # ORDER BY clause
        if order_by:
            query += f" ORDER BY {order_by} {order_dir}"

        # LIMIT clause
        if limit:
            query += f" LIMIT {limit}"

        return query

@ui.page('/database')
def database_explorer_page():
    """Database explorer page"""

    explorer = DatabaseExplorer(PersistenceLayer())
    query_builder = QueryBuilder()

    # Quick query buttons
    with ui.row().classes('gap-2 mb-4'):
        ui.button('All Processed', on_click=lambda: run_quick_query('processed'))
        ui.button('All Suppressed', on_click=lambda: run_quick_query('suppressed'))
        ui.button('Last 24h', on_click=lambda: run_quick_query('recent'))
        ui.button('Failed Only', on_click=lambda: run_quick_query('failed'))

    # Table selector
    table_select = ui.select(
        ['suppressed_emails', 'processed_emails'],
        value='suppressed_emails',
        label='Table'
    ).classes('mb-4')

    # Table stats
    stats_label = ui.label().classes('text-caption mb-4')

    # Query builder card
    with ui.card().classes('w-full mb-4'):
        ui.label('Query Builder').classes('text-h6 mb-2')

        # SELECT
        columns_input = ui.input('Columns (comma-separated)', value='*')

        # WHERE conditions
        where_container = ui.column().classes('w-full')

        def add_where_condition():
            with where_container:
                with ui.row().classes('gap-2'):
                    ui.select(['category', 'sender', 'reason'], label='Column')
                    ui.select(['=', 'LIKE', '!=', '>', '<'], value='=')
                    ui.input('Value')
                    ui.button('−', on_click=lambda: row.delete())

        ui.button('+ Add Condition', on_click=add_where_condition)

        # ORDER BY
        with ui.row().classes('gap-2'):
            order_by_input = ui.select(['timestamp', 'sender', 'category'], label='Order By')
            order_dir_input = ui.select(['ASC', 'DESC'], value='DESC')

        # LIMIT
        limit_input = ui.number('Limit', value=100, min=1, max=10000)

        ui.button('Build & Run Query', on_click=build_and_run_query)

    # Raw SQL editor
    with ui.card().classes('w-full mb-4'):
        ui.label('Raw SQL Editor').classes('text-h6 mb-2')

        sql_editor = ui.textarea(
            placeholder='Enter SQL query...',
            value='SELECT * FROM suppressed_emails LIMIT 10;'
        ).classes('w-full font-mono').style('min-height: 150px')

        with ui.row().classes('gap-2'):
            ui.button('▶ Run Query', on_click=lambda: run_sql_query(sql_editor.value), icon='play_arrow').props('color=primary')
            ui.button('Save', icon='save')
            ui.button('Copy', icon='content_copy', on_click=lambda: copy_to_clipboard(sql_editor.value))

    # Results section
    results_status = ui.label().classes('mb-2')

    results_container = ui.column().classes('w-full mb-4')

    # Export buttons
    with ui.row().classes('gap-2'):
        ui.button('Export CSV', icon='download', on_click=export_csv)
        ui.button('Export JSON', icon='download', on_click=export_json)
        ui.button('Visualize Results', icon='bar_chart', on_click=visualize_results)

    # Functions
    def run_sql_query(sql: str):
        result = explorer.execute_query(sql)

        if result['success']:
            results_status.text = f"✅ Query executed in {result['execution_time']:.1f}ms | {result['row_count']} rows returned"

            # Display results in table
            results_container.clear()
            with results_container:
                if result['rows']:
                    # Convert to table format
                    table_data = {
                        'columns': [{'name': col, 'label': col, 'field': col} for col in result['columns']],
                        'rows': [dict(zip(result['columns'], row)) for row in result['rows']]
                    }
                    ui.table(**table_data).classes('w-full')
                else:
                    ui.label('No results').classes('text-grey-7')
        else:
            results_status.text = f"❌ Error: {result['error']}"
            results_status.classes('text-negative')
```

**Features:**
- ✅ Visual query builder (no SQL knowledge needed)
- ✅ Raw SQL editor for power users
- ✅ Syntax validation
- ✅ Quick query presets
- ✅ Table schema viewer
- ✅ Table statistics
- ✅ Export to CSV/JSON
- ✅ Query history (saved queries)
- ✅ Read-only mode (safety)
- ✅ Execution time display
- ✅ Pagination for large results
- ✅ Copy results to clipboard

**Security:**
- ✅ Only SELECT queries allowed (no DELETE/UPDATE/INSERT)
- ✅ No access to system tables
- ✅ Query timeout (5 seconds max)
- ✅ Result size limit (10,000 rows max)

---

## Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...
    "nicegui>=3.4.1",
    "plotly>=5.18.0",     # For charts
    "python-dotenv",       # Already have this
]
```

---

## Implementation Order

### Priority 1: Analytics (Highest Value)
Users will love seeing charts immediately. Start here.

**Estimated time:** 2 hours

### Priority 2: Configuration Editor
Makes setup easier for new users.

**Estimated time:** 2-3 hours

### Priority 3: Database Explorer
Power user feature, less urgent.

**Estimated time:** 1-2 hours

---

## Testing Plan

### Configuration Editor Tests
- ✅ Load existing .env
- ✅ Save with validation
- ✅ Test CRM connection
- ✅ Test LLM connection
- ✅ Preserve comments
- ✅ Handle missing .env file

### Analytics Tests
- ✅ Charts render correctly
- ✅ Data accuracy (compare with DB)
- ✅ Date range filtering
- ✅ Handle empty database
- ✅ Chart interactions (zoom, pan)

### Database Explorer Tests
- ✅ Query execution
- ✅ Query validation (reject DELETE/UPDATE)
- ✅ Query builder SQL generation
- ✅ CSV export
- ✅ JSON export
- ✅ Error handling (syntax errors)

---

## Success Metrics

**Configuration Editor:**
- Time to configure app: < 2 minutes
- Error rate: < 5%
- Connection test success rate: > 95%

**Analytics:**
- Charts load time: < 1 second
- User engagement: Average 3+ charts viewed per session
- Insight discovery: Users find top suppressed domains within 30 seconds

**Database Explorer:**
- Query success rate: > 90%
- Export usage: > 20% of users export data
- Advanced users: > 10% use raw SQL

---

## Future Phase 3 Ideas

1. **Email Preview Modal** - View full email content in UI
2. **Bulk Operations** - Select and reprocess/delete multiple emails
3. **Scheduled Processing** - Cron-like scheduling for batch processing
4. **Webhooks** - Notify external systems when emails processed
5. **User Management** - Multi-user support with roles
6. **API Documentation** - Interactive API explorer
7. **Backup/Restore** - Database backup and restore functionality
8. **Performance Monitoring** - Real-time processing speed charts

---

## Questions Before Implementation

1. **Chart Library Preference?** Plotly (interactive, 3MB) vs ECharts (lightweight)?

2. **Configuration Security?** Should we encrypt API keys in .env or leave as plain text?

3. **Database Write Access?** Should Database Explorer allow UPDATE/DELETE with confirmation dialog, or keep read-only?

4. **Export Limits?** Max rows for CSV/JSON export? (Suggest 10,000)

5. **Analytics Auto-Refresh?** Should charts auto-refresh every N seconds, or manual only?

Let me know your preferences and I'll start implementing Phase 2!
