import os
from typing import List, Any, Dict
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.state import RunnableConfig
from dotenv import load_dotenv
import traceback

load_dotenv()

async def setup_mcp_tools(config: RunnableConfig) -> List[Any]:
    token = config.get("configurable", {}).get("token") if config else None
    
    if not token:
        print("⚠️  Warning: Token not provided in config. Running without MCP tools.")

        return []
    
    mcp_url = os.getenv("ZENIOR_MCP_SERVER_URL")

    if not mcp_url:
        print("⚠️  Warning: ZENIOR_MCP_SERVER_URL environment variable is not set. Running without MCP tools.")

        return []
    
    try:
        client = MultiServerMCPClient({
            "zenior": {
                "transport": "streamable_http",
                "url": mcp_url,
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
        print(f"   MCP URL was: {mcp_url}")
        print(f"   Make sure the MCP server is running and accessible at this URL")

        traceback.print_exc()

        return []
