import json
import os
from collections.abc import AsyncGenerator

import anthropic

from agent.prompts import SYSTEM_PROMPT
from agent.session import SessionManager
from agent.tools import TOOL_SCHEMAS, execute_tool
from salesforce.client import SalesforceClient


class DashboardAgent:
    MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 8192
    MAX_TURNS = 20

    def __init__(self, session_manager: SessionManager):
        self.client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.sf = SalesforceClient()
        self.sessions = session_manager

    async def run(self, session_id: str, user_prompt: str) -> AsyncGenerator[dict, None]:
        session = self.sessions.get_or_create(session_id)
        messages = list(session.messages) + [{"role": "user", "content": user_prompt}]
        # Start from prior charts/insights so follow-ups accumulate rather than reset.
        # Deduplicate charts by title so re-generated charts replace their prior version.
        charts: list[dict] = list(session.charts)
        insights: list[dict] = list(session.insights)

        try:
            for _ in range(self.MAX_TURNS):
                async with self.client.messages.stream(
                    model=self.MODEL,
                    max_tokens=self.MAX_TOKENS,
                    thinking={"type": "adaptive"},
                    system=SYSTEM_PROMPT,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                ) as stream:
                    async for event in stream:
                        if event.type == "content_block_delta":
                            if event.delta.type == "thinking_delta":
                                yield {"type": "thinking", "text": event.delta.thinking}
                            elif event.delta.type == "text_delta":
                                yield {"type": "text", "text": event.delta.text}
                    response = await stream.get_final_message()

                # Append assistant turn (includes thinking blocks as-is — required by SDK)
                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    break

                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    yield {"type": "tool_call", "name": block.name, "input": block.input}

                    try:
                        result = await execute_tool(block.name, block.input, self.sf)
                        is_error = False
                        if block.name == "generate_chart":
                            new_chart = json.loads(result)
                            new_title = new_chart.get("layout", {}).get("title", {})
                            if isinstance(new_title, dict):
                                new_title = new_title.get("text", "")
                            charts = [c for c in charts if c.get("layout", {}).get("title", {}).get("text", "") != new_title]
                            charts.append(new_chart)
                        elif block.name == "create_insight":
                            insights.append(json.loads(result))
                    except Exception as exc:
                        result = str(exc)
                        is_error = True

                    yield {"type": "tool_result", "name": block.name, "result": result, "is_error": is_error}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error,
                    })

                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
        finally:
            # Save updated history even if stream was interrupted
            self.sessions.save(session_id, messages, charts, insights)

        yield {"type": "dashboard", "charts": charts, "insights": insights}
