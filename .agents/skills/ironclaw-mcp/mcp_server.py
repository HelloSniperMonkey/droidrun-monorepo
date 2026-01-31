"""
Iron Claw MCP Server

Model Context Protocol (MCP) server that exposes Iron Claw functionality
as tools for LLM integration. This can be used with Claude, OpenClaw, or
any MCP-compatible client.

Usage:
    # Run as standalone MCP server
    python -m ironclaw_mcp.server

    # Or import and use programmatically
    from ironclaw_mcp import IronClawMCPServer
    server = IronClawMCPServer(base_url="http://localhost:8000", token="ubuntu@clawdbot")
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime
import httpx


@dataclass
class MCPToolDefinition:
    """Definition of an MCP tool."""
    name: str
    description: str
    inputSchema: dict
    endpoint: str
    method: str = "POST"


@dataclass
class MCPResourceDefinition:
    """Definition of an MCP resource."""
    uri: str
    name: str
    description: str
    mimeType: str = "application/json"


@dataclass
class MCPPromptDefinition:
    """Definition of an MCP prompt."""
    name: str
    description: str
    template: str
    variables: list = field(default_factory=list)


class IronClawMCPServer:
    """
    MCP Server for Iron Claw.
    
    Provides tools, resources, and prompts for Android automation.
    """
    
    def __init__(
        self,
        base_url: str = None,
        token: str = None,
    ):
        self.base_url = base_url or os.getenv("IRONCLAW_BASE_URL", "http://localhost:8000")
        self.token = token or os.getenv("IRONCLAW_WEBHOOK_TOKEN", "ubuntu@clawdbot")
        self._client: Optional[httpx.AsyncClient] = None
        
        # Define tools
        self.tools = self._define_tools()
        self.resources = self._define_resources()
        self.prompts = self._define_prompts()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _define_tools(self) -> list[MCPToolDefinition]:
        """Define all available MCP tools."""
        return [
            # Core webhook tool
            MCPToolDefinition(
                name="ironclaw_execute",
                description="Execute a task on the Iron Claw Android automation agent. Supports log, mobile_action, http_action, click, extract step types.",
                inputSchema={
                    "type": "object",
                    "required": ["taskId", "stepType"],
                    "properties": {
                        "taskId": {"type": "string", "description": "Unique task identifier"},
                        "stepType": {
                            "type": "string",
                            "enum": ["log", "mobile_action", "http_action", "click", "extract"],
                            "description": "Type of step to execute"
                        },
                        "message": {"type": "string", "description": "Message for log steps"},
                        "action": {"type": "string", "description": "Action for mobile_action steps"},
                        "url": {"type": "string", "description": "URL for http_action steps"},
                        "selector": {"type": "string", "description": "Selector for click/extract steps"},
                    }
                },
                endpoint="/openclaw/webhook",
                method="POST",
            ),
            
            # Chat
            MCPToolDefinition(
                name="ironclaw_chat",
                description="Send a natural language command to the Iron Claw AI agent. The AI will interpret and execute on Android device.",
                inputSchema={
                    "type": "object",
                    "required": ["message"],
                    "properties": {
                        "message": {"type": "string", "description": "Natural language command"},
                        "thread_id": {"type": "string", "description": "Optional conversation thread ID"},
                    }
                },
                endpoint="/api/chat",
                method="POST",
            ),
            
            # Cloud Chat (Recommended)
            MCPToolDefinition(
                name="ironclaw_cloud_execute",
                description="Execute a task on MobileRun cloud agent with live step-by-step updates. RECOMMENDED for cloud automation. Returns task_id for polling.",
                inputSchema={
                    "type": "object",
                    "required": ["message"],
                    "properties": {
                        "message": {"type": "string", "description": "Natural language command"},
                        "device_id": {"type": "string", "description": "Optional device ID (auto-selects if omitted)"},
                        "llm_model": {"type": "string", "default": "google/gemini-2.5-flash"},
                        "max_steps": {"type": "integer", "default": 100},
                        "vision": {"type": "boolean", "default": True},
                        "reasoning": {"type": "boolean", "default": True},
                        "temperature": {"type": "number", "default": 0.5},
                    }
                },
                endpoint="/api/chat-cloud",
                method="POST",
            ),
            MCPToolDefinition(
                name="ironclaw_cloud_poll",
                description="Poll cloud task status and get live step updates. Use this repeatedly until status is completed/failed.",
                inputSchema={
                    "type": "object",
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID from ironclaw_cloud_execute"}
                    }
                },
                endpoint="/api/chat-cloud/tasks/{task_id}",
                method="GET",
            ),
            MCPToolDefinition(
                name="ironclaw_cloud_devices",
                description="List all available MobileRun cloud devices.",
                inputSchema={"type": "object", "properties": {}},
                endpoint="/api/chat-cloud/devices",
                method="GET",
            ),
            
            # Tab management
            MCPToolDefinition(
                name="ironclaw_tabs_list",
                description="Get list of all currently open Chrome tabs on the Android device.",
                inputSchema={"type": "object", "properties": {}},
                endpoint="/api/v1/tabs/list",
                method="GET",
            ),
            MCPToolDefinition(
                name="ironclaw_tabs_organize",
                description="Organize Chrome tabs into AI-categorized groups (Work, Social, Shopping, Research, Entertainment).",
                inputSchema={"type": "object", "properties": {}},
                endpoint="/api/v1/tabs/organize",
                method="POST",
            ),
            MCPToolDefinition(
                name="ironclaw_tabs_close_old",
                description="Close Chrome tabs older than specified days.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days_old": {"type": "integer", "default": 7, "minimum": 1, "maximum": 30}
                    }
                },
                endpoint="/api/v1/tabs/close-old",
                method="POST",
            ),
            MCPToolDefinition(
                name="ironclaw_tabs_merge_duplicates",
                description="Find and close duplicate Chrome tabs with the same URL.",
                inputSchema={"type": "object", "properties": {}},
                endpoint="/api/v1/tabs/merge-duplicates",
                method="POST",
            ),
            MCPToolDefinition(
                name="ironclaw_tabs_save_session",
                description="Save current Chrome tabs as a named session for later restoration.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Optional session name"}
                    }
                },
                endpoint="/api/v1/tabs/save-session",
                method="POST",
            ),
            MCPToolDefinition(
                name="ironclaw_tabs_restore_session",
                description="Restore a previously saved tab session.",
                inputSchema={
                    "type": "object",
                    "required": ["session_id"],
                    "properties": {
                        "session_id": {"type": "string", "description": "Session ID to restore"}
                    }
                },
                endpoint="/api/v1/tabs/restore-session",
                method="POST",
            ),
            
            # Alarms
            MCPToolDefinition(
                name="ironclaw_alarm_set",
                description="Set an alarm on the Android device.",
                inputSchema={
                    "type": "object",
                    "required": ["hour", "minute"],
                    "properties": {
                        "hour": {"type": "integer", "minimum": 0, "maximum": 23},
                        "minute": {"type": "integer", "minimum": 0, "maximum": 59},
                        "label": {"type": "string", "description": "Alarm label"},
                        "days": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recurring days"
                        }
                    }
                },
                endpoint="/api/v1/alarms/set",
                method="POST",
            ),
            MCPToolDefinition(
                name="ironclaw_calendar_event",
                description="Create a calendar event on the Android device.",
                inputSchema={
                    "type": "object",
                    "required": ["title", "start_time"],
                    "properties": {
                        "title": {"type": "string"},
                        "start_time": {"type": "string", "format": "date-time"},
                        "end_time": {"type": "string", "format": "date-time"},
                        "description": {"type": "string"}
                    }
                },
                endpoint="/api/v1/alarms/calendar/event",
                method="POST",
            ),
            
            # Jobs
            MCPToolDefinition(
                name="ironclaw_jobs_search",
                description="Start automated job search and application workflow.",
                inputSchema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "description": "Job search query"},
                        "max_applications": {"type": "integer", "default": 5},
                        "filters": {
                            "type": "object",
                            "properties": {
                                "experience_level": {"type": "string"},
                                "job_type": {"type": "string"}
                            }
                        }
                    }
                },
                endpoint="/api/v1/jobs/search-and-apply",
                method="POST",
            ),
            MCPToolDefinition(
                name="ironclaw_jobs_status",
                description="Get status of a job search task.",
                inputSchema={
                    "type": "object",
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {"type": "string"}
                    }
                },
                endpoint="/api/v1/jobs/status/{task_id}",
                method="GET",
            ),
            
            # HITL
            MCPToolDefinition(
                name="ironclaw_hitl_pending",
                description="Get all pending Human-in-the-Loop intervention requests.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Optional filter by task"}
                    }
                },
                endpoint="/api/v1/hitl/pending",
                method="GET",
            ),
            MCPToolDefinition(
                name="ironclaw_hitl_respond",
                description="Respond to a HITL intervention request.",
                inputSchema={
                    "type": "object",
                    "required": ["request_id", "action"],
                    "properties": {
                        "request_id": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["Retry", "Abort", "I solved it"]
                        },
                        "custom_input": {"type": "string"}
                    }
                },
                endpoint="/api/v1/hitl/{request_id}/respond",
                method="POST",
            ),
            
            # Task management
            MCPToolDefinition(
                name="ironclaw_tasks_list",
                description="List all Iron Claw tasks and their statuses.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "limit": {"type": "integer", "default": 50}
                    }
                },
                endpoint="/openclaw/tasks",
                method="GET",
            ),
            MCPToolDefinition(
                name="ironclaw_task_status",
                description="Get status of a specific task by run ID.",
                inputSchema={
                    "type": "object",
                    "required": ["run_id"],
                    "properties": {
                        "run_id": {"type": "string"}
                    }
                },
                endpoint="/openclaw/tasks/{run_id}",
                method="GET",
            ),
            MCPToolDefinition(
                name="ironclaw_task_cancel",
                description="Cancel a pending or running task.",
                inputSchema={
                    "type": "object",
                    "required": ["run_id"],
                    "properties": {
                        "run_id": {"type": "string"}
                    }
                },
                endpoint="/openclaw/tasks/{run_id}",
                method="DELETE",
            ),
        ]
    
    def _define_resources(self) -> list[MCPResourceDefinition]:
        """Define all available MCP resources."""
        return [
            MCPResourceDefinition(
                uri="ironclaw://health",
                name="Health Status",
                description="Iron Claw service health and status",
            ),
            MCPResourceDefinition(
                uri="ironclaw://tabs",
                name="Chrome Tabs",
                description="Current Chrome tabs on the Android device",
            ),
            MCPResourceDefinition(
                uri="ironclaw://sessions",
                name="Tab Sessions",
                description="Saved tab sessions",
            ),
            MCPResourceDefinition(
                uri="ironclaw://hitl",
                name="HITL Requests",
                description="Pending Human-in-the-Loop intervention requests",
            ),
            MCPResourceDefinition(
                uri="ironclaw://tasks",
                name="Task Queue",
                description="All queued and completed tasks",
            ),
        ]
    
    def _define_prompts(self) -> list[MCPPromptDefinition]:
        """Define all available MCP prompts."""
        return [
            MCPPromptDefinition(
                name="open_app",
                description="Open an app on the Android device",
                template="Open the {app_name} app on my phone",
                variables=[{"name": "app_name", "required": True}],
            ),
            MCPPromptDefinition(
                name="search_web",
                description="Search the web using Chrome",
                template="Search for '{query}' in Chrome",
                variables=[{"name": "query", "required": True}],
            ),
            MCPPromptDefinition(
                name="set_alarm",
                description="Set an alarm",
                template="Set an alarm for {time} with label '{label}'",
                variables=[
                    {"name": "time", "required": True},
                    {"name": "label", "required": False},
                ],
            ),
            MCPPromptDefinition(
                name="organize_tabs",
                description="Organize Chrome tabs",
                template="Organize my Chrome tabs into categories",
            ),
            MCPPromptDefinition(
                name="job_search",
                description="Start job search",
                template="Search for {job_type} jobs in {location} and apply to up to {count} positions",
                variables=[
                    {"name": "job_type", "required": True},
                    {"name": "location", "required": True},
                    {"name": "count", "required": False, "default": "5"},
                ],
            ),
            MCPPromptDefinition(
                name="cleanup_tabs",
                description="Clean up Chrome tabs",
                template="Close all Chrome tabs older than {days} days and remove duplicates",
                variables=[{"name": "days", "required": False, "default": "7"}],
            ),
        ]
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """
        Call an MCP tool by name.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        # Find the tool
        tool = next((t for t in self.tools if t.name == name), None)
        if not tool:
            return {"error": f"Unknown tool: {name}"}
        
        client = await self._get_client()
        
        # Build endpoint URL with path parameters
        endpoint = tool.endpoint
        for key, value in arguments.items():
            endpoint = endpoint.replace(f"{{{key}}}", str(value))
        
        # Build request body for webhook
        if name == "ironclaw_execute":
            body = {
                "taskId": arguments.get("taskId", f"mcp-{datetime.utcnow().isoformat()}"),
                "type": "execute-step",
                "payload": {
                    "stepType": arguments.get("stepType", "log"),
                    "params": {
                        k: v for k, v in arguments.items()
                        if k not in ["taskId", "stepType"]
                    }
                }
            }
        else:
            body = {
                k: v for k, v in arguments.items()
                if f"{{{k}}}" not in tool.endpoint
            }
        
        try:
            if tool.method == "GET":
                response = await client.get(endpoint, params=body if body else None)
            elif tool.method == "POST":
                response = await client.post(endpoint, json=body if body else None)
            elif tool.method == "DELETE":
                response = await client.delete(endpoint)
            else:
                return {"error": f"Unsupported method: {tool.method}"}
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            return {
                "error": f"HTTP {e.response.status_code}",
                "detail": e.response.text,
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def read_resource(self, uri: str) -> dict:
        """
        Read an MCP resource by URI.
        
        Args:
            uri: Resource URI (e.g., ironclaw://health)
            
        Returns:
            Resource data
        """
        client = await self._get_client()
        
        endpoint_map = {
            "ironclaw://health": "/health",
            "ironclaw://tabs": "/api/v1/tabs/list",
            "ironclaw://sessions": "/api/v1/tabs/sessions",
            "ironclaw://hitl": "/api/v1/hitl/pending",
            "ironclaw://tasks": "/openclaw/tasks",
        }
        
        endpoint = endpoint_map.get(uri)
        if not endpoint:
            return {"error": f"Unknown resource: {uri}"}
        
        try:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_prompt(self, name: str, variables: dict = None) -> str:
        """
        Get a prompt template with variables filled in.
        
        Args:
            name: Prompt name
            variables: Variables to fill in
            
        Returns:
            Filled prompt string
        """
        prompt = next((p for p in self.prompts if p.name == name), None)
        if not prompt:
            return f"Unknown prompt: {name}"
        
        result = prompt.template
        variables = variables or {}
        
        for var in prompt.variables:
            value = variables.get(var["name"], var.get("default", ""))
            result = result.replace(f"{{{var['name']}}}", str(value))
        
        return result
    
    def to_mcp_manifest(self) -> dict:
        """
        Generate MCP manifest for this server.
        
        Returns:
            MCP manifest dict
        """
        return {
            "name": "ironclaw",
            "version": "1.0.0",
            "description": "Iron Claw - Mobile-First Android Automation Agent",
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
                for t in self.tools
            ],
            "resources": [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mimeType,
                }
                for r in self.resources
            ],
            "prompts": [
                {
                    "name": p.name,
                    "description": p.description,
                    "arguments": [
                        {"name": v["name"], "required": v.get("required", False)}
                        for v in p.variables
                    ] if p.variables else [],
                }
                for p in self.prompts
            ],
        }


# ============================================================================
# MCP Protocol Handler (for stdio transport)
# ============================================================================

async def handle_mcp_request(server: IronClawMCPServer, request: dict) -> dict:
    """Handle an MCP protocol request."""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {"subscribe": False},
                    "prompts": {},
                },
                "serverInfo": {
                    "name": "ironclaw",
                    "version": "1.0.0",
                },
            },
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.inputSchema,
                    }
                    for t in server.tools
                ]
            },
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        result = await server.call_tool(tool_name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {"type": "text", "text": json.dumps(result, indent=2)}
                ],
            },
        }
    
    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "resources": [
                    {
                        "uri": r.uri,
                        "name": r.name,
                        "description": r.description,
                        "mimeType": r.mimeType,
                    }
                    for r in server.resources
                ]
            },
        }
    
    elif method == "resources/read":
        uri = params.get("uri")
        result = await server.read_resource(uri)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(result, indent=2),
                    }
                ],
            },
        }
    
    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "prompts": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "arguments": [
                            {"name": v["name"], "required": v.get("required", False)}
                            for v in p.variables
                        ] if p.variables else [],
                    }
                    for p in server.prompts
                ]
            },
        }
    
    elif method == "prompts/get":
        name = params.get("name")
        arguments = params.get("arguments", {})
        text = server.get_prompt(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "description": f"Prompt: {name}",
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": text}}
                ],
            },
        }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }


async def run_stdio_server():
    """Run the MCP server using stdio transport."""
    server = IronClawMCPServer()
    
    try:
        while True:
            # Read JSON-RPC request from stdin
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            if not line:
                break
            
            try:
                request = json.loads(line.strip())
                response = await handle_mcp_request(server, request)
                
                # Write response to stdout
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {e}",
                    },
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
                
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(run_stdio_server())
