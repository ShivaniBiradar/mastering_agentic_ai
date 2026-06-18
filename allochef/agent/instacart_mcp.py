"""
Instacart MCP client — turns an approved grocery list into a shoppable
Instacart page once the human approves the plan.

Server (official, hosted — nothing to run locally):
  https://docs.instacart.com/developer_platform_api/guide/tutorials/mcp/
    dev : https://mcp.dev.instacart.tools/mcp
    prod: https://mcp.instacart.com/mcp
  Transport: Streamable HTTP
  Auth:      Authorization: Bearer <INSTACART_API_KEY>
  Tools:     create-recipe, create-shopping-list

We call `create-shopping-list`, which returns a `products_link_url` — a page
where the user can add every item to their Instacart cart in one tap.

"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INSTACART_API_KEY, INSTACART_MCP_URL

_SHOPPING_LIST_TOOL = "create-shopping-list"


# ── async core ──────────────────────────────────────────────────────────────

async def _call_create_shopping_list(title: str, line_items: list[dict]):
    """Connect to the Instacart MCP server and invoke create-shopping-list."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {INSTACART_API_KEY}"}

    async with streamablehttp_client(INSTACART_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(
                _SHOPPING_LIST_TOOL,
                arguments={"title": title, "line_items": line_items},
            )


async def _list_tools():
    """Connect to the Instacart MCP server and list its available tools."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {INSTACART_API_KEY}"}

    async with streamablehttp_client(INSTACART_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.list_tools()


def _run_async(coro):
    """
    Run an async coroutine from sync code (LangGraph node / Streamlit thread).

    asyncio.run() works when no loop is running. If one already is, fall back
    to a dedicated thread with its own loop so we never hit
    "event loop is already running".
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        box: dict = {}

        def _runner():
            loop = asyncio.new_event_loop()
            try:
                box["result"] = loop.run_until_complete(coro)
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc
            finally:
                loop.close()

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        if "error" in box:
            raise box["error"]
        return box.get("result")


# ── response parsing ────────────────────────────────────────────────────────

def _extract_url(result) -> str | None:
    """Pull the products_link_url out of an MCP CallToolResult."""
    # 1) structured content (preferred when the server provides it)
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        url = structured.get("products_link_url") or structured.get("url")
        if url:
            return url
        for value in structured.values():
            if isinstance(value, dict):
                nested = value.get("products_link_url") or value.get("url")
                if nested:
                    return nested

    # 2) text content blocks — may be JSON or plain text containing a URL
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                url = data.get("products_link_url") or data.get("url")
                if url:
                    return url
        except (json.JSONDecodeError, TypeError):
            pass
        match = re.search(r"https?://\S+", text)
        if match:
            return match.group(0).rstrip(').,"\'')

    return None


# ── public sync entrypoint ──────────────────────────────────────────────────

def create_instacart_shopping_list(title: str, items: list[dict]) -> dict:
    """
    Create a shoppable Instacart page from the approved grocery list.

    Args:
      title: page title shown on Instacart (e.g. "AlloChef — Garlic Chicken").
      items: list of {"name", optional "quantity", "unit", "display_text"}.

    Returns a dict:
      {"url": str | None, "error": str | None}

    Never raises — callers can rely on the local cart draft as a fallback.
    """
    if not INSTACART_API_KEY:
        return {"url": None, "error": "INSTACART_API_KEY not set — skipping Instacart, using local cart draft."}
    if not items:
        return {"url": None, "error": "No items to send to Instacart."}

    line_items = []
    for it in items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        entry: dict = {"name": name}
        if it.get("quantity"):
            entry["quantity"] = it["quantity"]
        if it.get("unit"):
            entry["unit"] = it["unit"]
        entry["display_text"] = it.get("display_text") or name
        line_items.append(entry)

    if not line_items:
        return {"url": None, "error": "No valid items to send to Instacart."}

    try:
        result = _run_async(_call_create_shopping_list(title, line_items))
    except Exception as exc:  # noqa: BLE001
        return {"url": None, "error": f"Instacart MCP call failed: {exc}"}

    url = _extract_url(result)
    if url:
        return {"url": url, "error": None}
    return {"url": None, "error": "Instacart responded but no products_link_url was found."}
