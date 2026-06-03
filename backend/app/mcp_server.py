"""Job-Intel MCP Server — 让外部 Agent 系统能调用本项目的能力。

V1 暴露 4 必选 + 2 可选工具，复用现有 service 函数，无状态、不写 DB。
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="job-intel",
    host=os.getenv("MCP_HOST", "::"),       # IPv6，兼容 Railway 私网
    port=int(os.getenv("PORT", "9001")),
)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
