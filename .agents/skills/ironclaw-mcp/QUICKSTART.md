# Iron Claw - Quick Reference

## Deployed Endpoint
🌐 **Production:** `https://ironclaw.snipermonkey.in`  
🔐 **Auth Token:** `ubuntu@clawdbot`

---

## Quick Test Commands

### 1. Health Check
```bash
curl https://ironclaw.snipermonkey.in/health
```

### 2. List All Endpoints
```bash
curl https://ironclaw.snipermonkey.in/
```

### 3. Execute via Webhook (OpenClaw)
```bash
curl -X POST https://ironclaw.snipermonkey.in/openclaw/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ubuntu@clawdbot" \
  -d '{
    "taskId": "test-001",
    "type": "execute-step",
    "payload": {
      "stepType": "log",
      "params": {"message": "Hello from OpenClaw!"}
    }
  }'
```

### 4. Cloud Agent (Recommended)
```bash
# Start task
curl -X POST https://ironclaw.snipermonkey.in/api/chat-cloud \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What time is it on my phone?",
    "max_steps": 20
  }'

# Returns: {"task_id": "abc123", ...}

# Poll for updates
curl https://ironclaw.snipermonkey.in/api/chat-cloud/tasks/abc123
```

### 5. Natural Language Chat
```bash
curl -X POST https://ironclaw.snipermonkey.in/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Set an alarm for 7:30 AM"}'
```

### 6. List Cloud Devices
```bash
curl https://ironclaw.snipermonkey.in/api/chat-cloud/devices
```

### 7. Check Task Status
```bash
curl https://ironclaw.snipermonkey.in/openclaw/tasks
```

---

## OpenClaw Configuration

### Environment Variables
```bash
export IRONCLAW_BASE_URL=https://ironclaw.snipermonkey.in
export IRONCLAW_WEBHOOK_TOKEN=ubuntu@clawdbot
```

### System Prompt Addition
See [OPENCLAW_PROMPT.md](OPENCLAW_PROMPT.md) for the full prompt to add to OpenClaw.

---

## All Available Endpoints

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| **Health** | `/health` | GET | Service health check |
| **Root** | `/` | GET | List all endpoints |
| **OpenClaw** | `/openclaw/webhook` | POST | Execute webhook task (requires auth) |
| | `/openclaw/tasks` | GET | List all tasks |
| | `/openclaw/tasks/{run_id}` | GET | Get task status |
| | `/openclaw/tasks/{run_id}` | DELETE | Cancel task |
| **Cloud Agent** | `/api/chat-cloud` | POST | Execute cloud task (live updates) |
| | `/api/chat-cloud/tasks/{task_id}` | GET | Poll task status |
| | `/api/chat-cloud/devices` | GET | List devices |
| | `/api/chat-cloud/trajectory/{task_id}` | GET | Get task trajectory |
| **Chat** | `/api/chat` | POST | Natural language chat |
| | `/api/upload` | POST | Upload files |
| | `/api/transcribe` | POST | Audio transcription |
| **Tabs** | `/api/v1/tabs/list` | GET | List Chrome tabs |
| | `/api/v1/tabs/organize` | POST | Organize tabs |
| | `/api/v1/tabs/close-old` | POST | Close old tabs |
| | `/api/v1/tabs/merge-duplicates` | POST | Merge duplicates |
| | `/api/v1/tabs/save-session` | POST | Save session |
| | `/api/v1/tabs/restore-session` | POST | Restore session |
| | `/api/v1/tabs/sessions` | GET | List sessions |
| **Alarms** | `/api/v1/alarms/set` | POST | Set alarm |
| | `/api/v1/alarms/cancel` | DELETE | Cancel alarms |
| | `/api/v1/alarms/calendar/event` | POST | Create calendar event |
| | `/api/v1/alarms/time` | GET | Get device time |
| **Jobs** | `/api/v1/jobs/upload-resume` | POST | Upload resume |
| | `/api/v1/jobs/search-and-apply` | POST | Search and apply |
| | `/api/v1/jobs/status/{task_id}` | GET | Check job status |
| **HITL** | `/api/v1/hitl/pending` | GET | Get pending requests |
| | `/api/v1/hitl/{request_id}` | GET | Get request details |
| | `/api/v1/hitl/{request_id}/respond` | POST | Respond to request |

---

## Recommended Workflow for OpenClaw

### Option 1: Cloud Agent (Best for Real-time Updates)
```
1. POST /api/chat-cloud → Get task_id
2. Poll GET /api/chat-cloud/tasks/{task_id} every 2 seconds
3. Stop when status = "completed" | "failed" | "cancelled"
4. Read final_answer and steps
```

### Option 2: Webhook (Best for Fire-and-Forget)
```
1. POST /openclaw/webhook with auth token
2. Get runId in response
3. Optionally poll GET /openclaw/tasks/{runId}
```

### Option 3: Direct Chat (Best for Simple Commands)
```
1. POST /api/chat with message
2. Get immediate response
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [INTEGRATION.md](INTEGRATION.md) | Complete API reference (44 endpoints) |
| [CLOUD_AGENT.md](CLOUD_AGENT.md) | Cloud agent guide with polling |
| [OPENCLAW_PROMPT.md](OPENCLAW_PROMPT.md) | System prompt for OpenClaw |
| [skill.yaml](skill.yaml) | MCP manifest |
| [mcp_server.py](mcp_server.py) | Python MCP server |

---

## Telegram Notifications

All webhook executions send notifications to Telegram:
- **Chat ID:** 6107382837
- **Format:** Task ID, type, message, timestamp

---

## Verification Checklist

- [x] Health endpoint: ✅ Working
- [x] OpenClaw webhook: ✅ Working (with auth)
- [x] Cloud agent: ✅ Working
- [x] Cloud devices list: ✅ Working
- [x] Endpoints listed in root: ✅ Updated
- [x] MCP tools updated: ✅ Cloud tools added
- [x] Documentation: ✅ Complete

---

*Last verified: 2026-02-01*  
*Deployed at: https://ironclaw.snipermonkey.in*
