# Iron Claw MCP Skill

Model Context Protocol (MCP) server that exposes Iron Claw mobile automation capabilities to LLM agents like OpenClaw/ClawdBot, Claude, or any MCP-compatible client.

## Overview

Iron Claw is a **Mobile-First Autonomous Agent** that orchestrates Android device automation through a FastAPI gateway. This MCP skill wraps all Iron Claw functionality in a standard MCP format for easy integration.

## Features

| Feature | Description | Status |
|---------|-------------|--------|
| 🤖 **AI Chat** | Natural language control of Android device | ✅ Active |
| 📑 **Tab Manager** | Organize, merge, save/restore Chrome tabs | ✅ Active |
| ⏰ **Alarms & Calendar** | Set alarms and calendar events | ✅ Active |
| 💼 **Job Hunter** | Auto-parse resume and apply to jobs | ✅ Active |
| 🤝 **Human-in-the-Loop** | Smart intervention for CAPTCHAs/logins | ✅ Active |
| 🎙️ **Speech-to-Text** | Audio transcription via Gemini | ✅ Active |
| 📞 **Voice Calls** | Vapi wake-up calls | ❌ Not Supported (Regional) |

## Quick Start

### 1. Start Iron Claw Gateway

```bash
cd /path/to/monorepo
./start.sh

# Or manually:
cd apps/gateway
uv run uvicorn ironclaw.main:app --host 0.0.0.0 --port 8000
```

### 2. Start Cloudflare Tunnel (for cloud access)

```bash
cloudflared tunnel --url http://localhost:8000 --protocol http2
# Note the generated URL (e.g., https://xxx.trycloudflare.com)
```

### 3. Configure OpenClaw

Set environment variables:
```bash
export IRONCLAW_BASE_URL=https://xxx.trycloudflare.com
export IRONCLAW_WEBHOOK_TOKEN=ubuntu@clawdbot
```

### 4. Run MCP Server (Optional - for stdio transport)

```bash
python mcp_server.py
```

## Files

| File | Description |
|------|-------------|
| `skill.yaml` | MCP manifest with all tools, resources, and prompts |
| `mcp_server.py` | Python MCP server implementation |
| `INTEGRATION.md` | Detailed endpoint documentation |
| `CLOUD_AGENT.md` | **Cloud Agent API** - Direct MobileRun integration with live updates |
| `OPENCLAW_PROMPT.md` | System prompt for OpenClaw configuration |
| `requirements.txt` | Python dependencies |

## Available Tools

### Core Tools

| Tool | Description |
|------|-------------|
| `ironclaw_execute` | Execute a task via webhook (log, mobile_action, http_action, click, extract) |
| `ironclaw_chat` | Send natural language command to AI agent |
| `ironclaw_cloud_execute` | **Execute cloud task** with live step updates (MobileRun direct) |
| `ironclaw_cloud_poll` | **Poll cloud task** for progress and results |

### Tab Management

| Tool | Description |
|------|-------------|
| `ironclaw_tabs_list` | List all open Chrome tabs |
| `ironclaw_tabs_organize` | AI-categorize tabs |
| `ironclaw_tabs_close_old` | Close tabs older than N days |
| `ironclaw_tabs_merge_duplicates` | Remove duplicate tabs |
| `ironclaw_tabs_save_session` | Save current tabs as session |
| `ironclaw_tabs_restore_session` | Restore saved session |

### Alarms & Calendar

| Tool | Description |
|------|-------------|
| `ironclaw_alarm_set` | Set an alarm |
| `ironclaw_calendar_event` | Create calendar event |

### Job Hunter

| Tool | Description |
|------|-------------|
| `ironclaw_jobs_search` | Start job search and auto-apply |
| `ironclaw_jobs_status` | Check job search task status |

### Human-in-the-Loop

| Tool | Description |
|------|-------------|
| `ironclaw_hitl_pending` | Get pending intervention requests |
| `ironclaw_hitl_respond` | Respond to HITL request |

### Task Management

| Tool | Description |
|------|-------------|
| `ironclaw_tasks_list` | List all tasks |
| `ironclaw_task_status` | Get specific task status |
| `ironclaw_task_cancel` | Cancel a task |

## Available Resources

| URI | Description |
|-----|-------------|
| `ironclaw://health` | Service health status |
| `ironclaw://tabs` | Current Chrome tabs |
| `ironclaw://sessions` | Saved tab sessions |
| `ironclaw://hitl` | Pending HITL requests |
| `ironclaw://tasks` | Task queue |

## Available Prompts

| Prompt | Template |
|--------|----------|
| `open_app` | "Open the {app_name} app on my phone" |
| `search_web` | "Search for '{query}' in Chrome" |
| `set_alarm` | "Set an alarm for {time} with label '{label}'" |
| `organize_tabs` | "Organize my Chrome tabs into categories" |
| `job_search` | "Search for {job_type} jobs in {location}..." |
| `cleanup_tabs` | "Close all Chrome tabs older than {days} days..." |

## Authentication

All requests require Bearer token authentication:

```
Authorization: Bearer ubuntu@clawdbot
```

Token is configured via `IRONCLAW_WEBHOOK_TOKEN` or `OPENCLAW_HOOK_TOKEN` environment variable.

## Usage Examples

### Python

```python
from mcp_server import IronClawMCPServer
import asyncio

async def main():
    server = IronClawMCPServer(
        base_url="https://xxx.trycloudflare.com",
        token="ubuntu@clawdbot"
    )
    
    # Execute a command
    result = await server.call_tool("ironclaw_chat", {
        "message": "Open Chrome and search for restaurants"
    })
    print(result)
    
    # Get tabs
    tabs = await server.call_tool("ironclaw_tabs_list", {})
    print(tabs)
    
    # Set alarm
    await server.call_tool("ironclaw_alarm_set", {
        "hour": 7,
        "minute": 30,
        "label": "Wake up!"
    })
    
    await server.close()

asyncio.run(main())
```

### cURL

```bash
# Health check
curl https://xxx.trycloudflare.com/health

# Execute via webhook
curl -X POST https://xxx.trycloudflare.com/openclaw/webhook \
  -H "Authorization: Bearer ubuntu@clawdbot" \
  -H "Content-Type: application/json" \
  -d '{
    "taskId": "test-001",
    "type": "execute-step",
    "payload": {
      "stepType": "log",
      "params": {"message": "Hello from OpenClaw!"}
    }
  }'

# Chat
curl -X POST https://xxx.trycloudflare.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it?"}'
```

## OpenClaw Integration

### Add to OpenClaw Skills

1. Copy the content from `OPENCLAW_PROMPT.md` to your OpenClaw system prompt
2. Set environment variables:
   ```bash
   IRONCLAW_BASE_URL=https://your-tunnel.trycloudflare.com
   IRONCLAW_WEBHOOK_TOKEN=ubuntu@clawdbot
   ```
3. Test the connection:
   ```bash
   curl $IRONCLAW_BASE_URL/health
   ```

### Example OpenClaw Configuration

```yaml
skills:
  - id: ironclaw
    name: "Iron Claw"
    description: "Mobile-First Android Automation Agent"
    baseUrl: "${IRONCLAW_BASE_URL}"
    auth:
      type: bearer
      token: "${IRONCLAW_WEBHOOK_TOKEN}"
    manifest: ".agents/skills/ironclaw-mcp/skill.yaml"
```

## Disabled Features

The following features are **NOT AVAILABLE** (Vapi not supported in this region):

- Voice wake-up calls (`/api/v1/wake/*`)
- Active Interrupter calls
- Schedule call (`/api/schedule-call`)

## Troubleshooting

### Connection Refused
```bash
# Check Iron Claw is running
curl localhost:8000/health

# Check Cloudflare tunnel
curl https://your-tunnel.trycloudflare.com/health
```

### 401 Unauthorized
- Verify `Authorization: Bearer ubuntu@clawdbot` header
- Check `OPENCLAW_HOOK_TOKEN` in `.env`

### Task Stuck
- Check HITL requests: `GET /api/v1/hitl/pending`
- Check logs: `tail -f apps/gateway/logs/ironclaw.log`

## Architecture

```
OpenClaw/ClawdBot
       │
       │ MCP Protocol (tools/resources/prompts)
       ▼
┌──────────────────┐
│  Iron Claw MCP   │
│     Server       │
└────────┬─────────┘
         │ HTTP/REST
         ▼
┌──────────────────┐
│  Iron Claw       │
│  Gateway         │
│  (FastAPI)       │
└────────┬─────────┘
         │ MobileRun API / ADB
         ▼
┌──────────────────┐
│  Android Device  │
└──────────────────┘
```

## License

Proprietary - Iron Claw Team

---

*Iron Claw × OpenClaw - Mobile Automation Made Easy*
