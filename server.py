"""Executable entry point for Claude Desktop and the MCP Inspector."""

from gmail_interview_scheduler_mcp.server import main, mcp

__all__ = ["main", "mcp"]

if __name__ == "__main__":
    main()
