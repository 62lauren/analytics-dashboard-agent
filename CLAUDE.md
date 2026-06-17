# Analytics Dashboard Agent

A conversational analytics agent that accepts plain English prompts, autonomously queries Salesforce CRM data, and generates interactive dashboards with Plotly charts and action-oriented insights.

## Stack

- **LLM**: Claude Opus 4.8 (`claude-opus-4-8`) with adaptive thinking — never downgrade to Sonnet or Haiku
- **Web framework**: FastAPI + Jinja2 + SSE (Server-Sent Events)
- **Charts**: Plotly (Python generates figure dicts → Plotly.js renders in browser)
- **Data source**: Salesforce REST API via `simple-salesforce`
- **Tools**: Claude tool use (native Anthropic SDK — no MCP)
- **Memory**: In-memory session store keyed by UUID, persisted in `localStorage` client-side

## Architecture

```
Browser (index.html + app.js)
  │  POST /api/dashboard {prompt, session_id}
  │  ← SSE stream of events (thinking, tool_call, tool_result, dashboard)
  ▼
FastAPI (main.py)
  └── DashboardAgent (agent/dashboard_agent.py)
        ├── SessionManager — loads/saves conversation history per session_id
        ├── AsyncAnthropic — streaming agentic loop with tool use
        │     thinking={"type": "adaptive"}, model="claude-opus-4-8"
        └── execute_tool() (agent/tools.py)
              ├── SalesforceClient (salesforce/client.py) — via asyncio.to_thread
              └── build_chart() (charts/plotly_builder.py)
```

### Agent workflow (enforced by system prompt)

1. `list_salesforce_objects` — discover available objects
2. `describe_salesforce_object` — get field names before writing SOQL
3. `query_salesforce` — execute SOQL, get aggregated records
4. `generate_chart` — produce a Plotly figure dict per visualization
5. `create_insight` — record a finding + recommendation + priority
6. Text reply — brief summary

On follow-up prompts, the agent skips step 1–2 for objects already described in the session.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and Salesforce credentials
python main.py
# Opens on http://localhost:8000
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `SALESFORCE_USERNAME` | Yes | Salesforce login email |
| `SALESFORCE_PASSWORD` | Yes | Salesforce password |
| `SALESFORCE_SECURITY_TOKEN` | Yes | Security token (from Salesforce profile settings) |
| `SALESFORCE_CLIENT_ID` | Yes | Connected App consumer key |
| `SALESFORCE_CLIENT_SECRET` | Yes | Connected App consumer secret |
| `SALESFORCE_DOMAIN` | Yes | `login` for production/developer orgs, `test` for sandboxes |
| `SALESFORCE_INSTANCE_URL` | Yes | Your org's My Domain URL (e.g. `orgname.develop.my.salesforce.com`) — required for newer orgs that disable SOAP login |
| `PORT` | No | Server port, default `8000` |

### Salesforce Connected App (required for newer orgs)

Newer Salesforce orgs disable SOAP API login by default. The app uses OAuth 2.0 Client Credentials flow instead, which requires an External Client App:

1. Setup → **External Client App Manager** → **New External Client App**
2. Fill in name, email, Distribution State: `Local`
3. Go to **Edit Settings → OAuth Settings**
4. Callback URL: `https://localhost`
5. Selected OAuth Scopes: `Manage user data via APIs (api)` + `Perform requests at any time (refresh_token)`
6. Under Flow Enablement: check **Enable Client Credentials Flow**, set Run As to your user
7. Save → copy Consumer Key → `SALESFORCE_CLIENT_ID`, Consumer Secret → `SALESFORCE_CLIENT_SECRET`
8. Find your My Domain URL in your Salesforce browser tab (e.g. `orgname.develop.my.salesforce.com`) → `SALESFORCE_INSTANCE_URL`

## Key Decisions

- **No MCP**: Tools are Python functions with JSON schemas wired directly into the Anthropic SDK tool use loop. Simple, no subprocess overhead, trivially debuggable.
- **OAuth Client Credentials flow**: Newer Salesforce orgs disable SOAP API login by default. The app authenticates via OAuth 2.0 Client Credentials flow (`grant_type=client_credentials`) using the External Client App's Consumer Key/Secret, posting to the org's My Domain URL (`SALESFORCE_INSTANCE_URL`). The resulting access token is passed to `simple-salesforce` via `session_id` + `instance_url`.
- **Conversation memory**: `SessionManager` stores the full `messages` list (including Claude's thinking blocks and tool results) per session. This lets Claude say "filter that by Q4" on a follow-up without re-discovering Salesforce objects.
- **Async Salesforce**: `simple-salesforce` is synchronous — all SF calls go through `asyncio.to_thread()` to avoid blocking FastAPI's event loop.
- **SSE over WebSockets**: SSE is unidirectional (server → browser), matching the request/stream pattern exactly. `EventSource` doesn't support POST, so the browser uses `fetch` + `ReadableStream`.
- **Adaptive thinking only**: `claude-opus-4-8` only accepts `thinking={"type": "adaptive"}`. Do not add `budget_tokens`, `"enabled"`, `"disabled"`, `temperature`, `top_p`, or `top_k` — all rejected with HTTP 400.

## File Map

| File | Purpose |
|---|---|
| `main.py` | FastAPI app, SSE endpoint, session lifespan |
| `agent/dashboard_agent.py` | Streaming agentic loop — the core of the system |
| `agent/tools.py` | 5 tool schemas + `execute_tool()` dispatcher |
| `agent/prompts.py` | System prompt enforcing discover→describe→query→visualize→insight |
| `agent/session.py` | `SessionManager` + background cleanup task |
| `salesforce/client.py` | Salesforce auth, `list_objects`, `describe_object`, `query` with flattening |
| `charts/plotly_builder.py` | `build_chart()` → Plotly figure dict for all 6 chart types |
| `web/templates/index.html` | Two-panel UI: chat history left, dashboard right |
| `web/static/app.js` | SSE client, Plotly rendering, session UUID management |
| `web/static/style.css` | Layout and styling |

## Extending

**Add a new data source**: add a new tool schema to `TOOL_SCHEMAS` in `agent/tools.py` and a corresponding branch in `execute_tool()`.

**Add a new chart type**: add to the `chart_type` enum in `agent/tools.py` and add a case to `build_chart()` in `charts/plotly_builder.py`. Update the `generate_chart` description so Claude knows when to use it.

**Add Salesforce objects**: append to `SalesforceClient.QUERYABLE_OBJECTS` in `salesforce/client.py`.

**Persist sessions across restarts**: replace the in-memory `dict` in `SessionManager` with SQLite or a file-backed store. Note: `messages` contains Pydantic model objects from the Anthropic SDK — serialize with `model.model_dump()` and deserialize back before passing to the API.
