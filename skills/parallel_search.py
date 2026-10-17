"""Anonymous Parallel Search MCP over Streamable HTTP, using existing httpx."""

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

from config import MODEL


MCP_URL = "https://search.parallel.ai/mcp"
USER_AGENT = "GemmaCore/0.1 (+https://github.com/VoxelMafia/GemmaCore)"
PROTOCOL_VERSION = "2025-03-26"


class ParallelSearchError(RuntimeError):
    pass


class ParallelSearch:
    def __init__(self):
        # Stable across all searches in this research run, including failures.
        self.session_id = uuid.uuid4().hex

    def search(self, query, goal=None, cancelled=lambda: False):
        """Return source URLs and excerpts for the existing reflection consumer."""
        if cancelled() or not query.strip():
            return ""
        # Sync Playwright keeps an asyncio loop active on the research thread
        # after navigation. Run MCP on its own thread to avoid nesting loops.
        with ThreadPoolExecutor(max_workers=1) as worker:
            return worker.submit(
                lambda: asyncio.run(self._search_until_stopped(query, goal, cancelled))
            ).result()

    async def _search_until_stopped(self, query, goal, cancelled):
        task = asyncio.create_task(asyncio.wait_for(self._search(query, goal), timeout=30))
        try:
            while not task.done():
                if cancelled():
                    return ""
                await asyncio.wait({task}, timeout=0.1)
            return "" if cancelled() else task.result()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _search(self, query, goal):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/event-stream"}
        async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=False) as client:
            initialized = await self._rpc(client, 1, "initialize", {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "GemmaCore", "version": "0.1"},
            })
            if initialized.get("protocolVersion") != PROTOCOL_VERSION:
                raise ParallelSearchError("Unsupported MCP protocol version")
            client.headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
            await self._rpc(client, None, "notifications/initialized", {})
            result = await self._rpc(client, 2, "tools/call", {
                "name": "web_search",
                "arguments": {"objective": goal or query, "search_queries": [query],
                              "session_id": self.session_id, "model_name": MODEL},
            })
            if result.get("isError"):
                raise ParallelSearchError(str(result.get("content", "MCP tool failed")))
            return self._format(result)

    @staticmethod
    async def _rpc(client, request_id, method, params):
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if request_id is not None:
            payload["id"] = request_id
        async with client.stream("POST", MCP_URL, json=payload) as response:
            response.raise_for_status()
            if response.headers.get("mcp-session-id"):
                client.headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
            if request_id is None:
                return {}
            if "text/event-stream" in response.headers.get("content-type", ""):
                # MCP streams may include keepalives/notifications before the reply.
                data = []
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        message = json.loads("\n".join(data))
                        data = []
                        if message.get("id") == request_id:
                            break
                else:
                    raise ParallelSearchError("MCP stream ended without a reply")
            else:
                await response.aread()
                message = response.json()
            if message.get("id") != request_id or message.get("jsonrpc") != "2.0":
                raise ParallelSearchError("Invalid MCP reply")
            if "error" in message:
                raise ParallelSearchError(str(message["error"]))
            if not isinstance(message.get("result"), dict):
                raise ParallelSearchError("Missing MCP result")
            return message["result"]

    @staticmethod
    def _format(result):
        data = result.get("structuredContent")
        if data is None:
            text = "\n".join(block["text"] for block in result.get("content", [])
                             if block.get("type") == "text")
            try:
                data = json.loads(text)
            except ValueError:
                raise ParallelSearchError("Missing structured search results") from None
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ParallelSearchError("Invalid search results")
        sources = []
        for item in data["results"][:5]:
            url = item.get("url", "")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                continue
            excerpts = "\n".join(item.get("excerpts", []))[:1500]
            sources.append(f"SOURCE: {url}\nTITLE: {item.get('title') or url}\n{excerpts}")
        return "\n\n".join(sources)[:7000]
