"""MCP (Model Context Protocol) utilities for agent tools integration."""
import os
from typing import List, Any, Dict
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.state import RunnableConfig
from dotenv import load_dotenv

load_dotenv()
async def setup_mcp_tools(config: RunnableConfig) -> List[Any]:
    
    token = config.get("configurable", {}).get("token") if config else None
    
    if not token:
        print("⚠️  Warning: Token not provided in config. Running without MCP tools.")
        # For testing, allow running without token if needed, or strictly return empty
        return []
    
    try:
        client = MultiServerMCPClient({
            "zenior": {
                "transport": "streamable_http",
                "url": os.getenv("ZENIOR_MCP_SERVER_URL"),
                "headers": {
                    "Authorization": f"Bearer {token}"
                }
            }
        })

        mcp_tools = await client.get_tools()
        print(f"✓ Successfully loaded {len(mcp_tools)} MCP tools")
        return mcp_tools
    except Exception as e:
        print(f"⚠️  Warning: MCP setup failed: {e}")
        import traceback
        traceback.print_exc()
        return []
