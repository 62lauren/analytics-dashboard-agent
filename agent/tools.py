import asyncio
import json

from charts.plotly_builder import build_chart
from salesforce.client import SalesforceClient

TOOL_SCHEMAS = [
    {
        "name": "list_salesforce_objects",
        "description": "List the available Salesforce CRM objects (Opportunity, Lead, Account, etc.). Call this first to discover what data sources exist before deciding what to query.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "describe_salesforce_object",
        "description": "Get all field names, labels, and types for a Salesforce object. Always call this before writing SOQL so you know the exact field names to use.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "The API name of the Salesforce object, e.g. 'Opportunity'",
                },
            },
            "required": ["object_name"],
        },
    },
    {
        "name": "query_salesforce",
        "description": "Execute a SOQL query against Salesforce and return the results as a list of records. Use aggregates (SUM, COUNT, GROUP BY) to summarize data for charts. Results are auto-paginated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "soql": {
                    "type": "string",
                    "description": "A valid SOQL query string, e.g. 'SELECT StageName, COUNT(Id) total FROM Opportunity GROUP BY StageName'",
                },
            },
            "required": ["soql"],
        },
    },
    {
        "name": "generate_chart",
        "description": "Generate an interactive Plotly chart from Salesforce query results. Returns a chart specification that will be rendered in the dashboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie", "scatter", "funnel", "heatmap"],
                    "description": "Chart type: bar=comparisons, line=trends over time, pie=share/composition, scatter=correlations, funnel=pipeline stages, heatmap=two-dimensional breakdown",
                },
                "data": {
                    "type": "array",
                    "description": "The records returned by query_salesforce to visualize",
                    "items": {"type": "object"},
                },
                "x_field": {
                    "type": "string",
                    "description": "Field name for the X axis or category labels (must match a key in the data records)",
                },
                "y_field": {
                    "type": "string",
                    "description": "Field name for the Y axis or numeric values (must be numeric)",
                },
                "title": {
                    "type": "string",
                    "description": "Human-readable chart title shown above the visualization",
                },
                "color_field": {
                    "type": "string",
                    "description": "Optional field to use for color grouping / series breakdown",
                },
            },
            "required": ["chart_type", "data", "x_field", "y_field", "title"],
        },
    },
    {
        "name": "create_insight",
        "description": "Record an action-oriented insight derived from the data. Each insight should state a specific finding and a concrete recommendation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short headline for this insight, e.g. 'Pipeline stalled in Negotiation stage'",
                },
                "finding": {
                    "type": "string",
                    "description": "What the data shows — be specific with numbers, names, and percentages",
                },
                "recommendation": {
                    "type": "string",
                    "description": "What the team should do about it — specific and actionable",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "high=revenue impact or urgent risk, medium=notable trend, low=informational",
                },
            },
            "required": ["title", "finding", "recommendation", "priority"],
        },
    },
]


async def execute_tool(name: str, tool_input: dict, sf: SalesforceClient) -> str:
    if name == "list_salesforce_objects":
        data = await asyncio.to_thread(sf.list_objects)
        return json.dumps(data)

    elif name == "describe_salesforce_object":
        data = await asyncio.to_thread(sf.describe_object, tool_input["object_name"])
        return json.dumps(data)

    elif name == "query_salesforce":
        data = await asyncio.to_thread(sf.query, tool_input["soql"])
        return json.dumps(data)

    elif name == "generate_chart":
        fig = build_chart(**tool_input)
        return json.dumps(fig)

    elif name == "create_insight":
        return json.dumps(tool_input)

    else:
        raise ValueError(f"Unknown tool: {name}")
