# Iron Claw API - OpenClaw Integration Guide

## Overview

Iron Claw is a Mobile-First Autonomous Agent that provides AI-powered Android device automation through a FastAPI gateway. This document details all available endpoints for integration with OpenClaw/ClawdBot.

**Base URL:** `https://<your-tunnel>.trycloudflare.com` (via Cloudflare Tunnel)  
**Local URL:** `http://localhost:8000`  
**Authentication:** `Bearer ubuntu@clawdbot`

---

## Quick Start

```bash
# Test the connection
curl -X GET "https://your-tunnel.trycloudflare.com/health"

# Execute a simple command
curl -X POST "https://your-tunnel.trycloudflare.com/openclaw/webhook" \
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

---

## Authentication

All requests to `/openclaw/*` endpoints require Bearer token authentication:

```
Authorization: Bearer ubuntu@clawdbot
```

Other endpoints (`/api/*`) do not require authentication in the current configuration.

---

## Endpoint Reference

### 1. OpenClaw Webhook (Main Entry Point)

The primary integration point for OpenClaw to control Iron Claw.

#### `POST /openclaw/webhook`

Execute tasks on the Android device via webhook.

**Headers:**
```
Content-Type: application/json
Authorization: Bearer ubuntu@clawdbot
```

**Request Body:**
```json
{
  "taskId": "unique-task-id",
  "type": "execute-step",
  "metadata": {
    "source": "openclaw",
    "session_id": "optional-session",
    "correlation_id": "optional-correlation"
  },
  "payload": {
    "stepType": "mobile_action|log|http_action|script|click|extract",
    "params": {
      "message": "For log type",
      "action": "For mobile_action type",
      "url": "For http_action type",
      "selector": "For click/extract types"
    }
  }
}
```

**Step Types:**
| Type | Description | Required Params |
|------|-------------|-----------------|
| `log` | Log a message (sent to Telegram) | `message` |
| `mobile_action` | Execute Android action | `action`, `extra` |
| `http_action` | Make HTTP request | `url`, `method`, `body` |
| `script` | Run a script | `script`, `language` |
| `click` | Click element on screen | `selector` |
| `extract` | Extract data from screen | `selector`, `pattern` |

**Response (202 Accepted):**
```json
{
  "ok": true,
  "runId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Task queued for execution"
}
```

---

### 2. Task Management

#### `GET /openclaw/tasks`

List all tasks with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `queued`, `running`, `completed`, `failed`, `cancelled`)
- `limit` (optional): Max results (default: 50)

**Response:**
```json
{
  "ok": true,
  "tasks": [
    {
      "run_id": "uuid",
      "task_id": "original-task-id",
      "status": "completed",
      "created_at": "2026-01-31T10:00:00Z",
      "updated_at": "2026-01-31T10:00:05Z",
      "step_type": "log",
      "result": {"output": "success"},
      "error": null
    }
  ],
  "total": 1
}
```

#### `GET /openclaw/tasks/{run_id}`

Get status of a specific task.

**Response:**
```json
{
  "ok": true,
  "task": {
    "run_id": "uuid",
    "task_id": "original-task-id",
    "status": "completed",
    "result": {"output": "Task completed successfully"}
  }
}
```

#### `DELETE /openclaw/tasks/{run_id}`

Cancel a pending or running task.

**Response:**
```json
{
  "ok": true,
  "message": "Task cancelled"
}
```

---

### 3. AI Chat Interface

#### `POST /api/chat`

Send natural language commands to the AI agent.

**Request:**
```json
{
  "message": "Open Chrome and search for Python tutorials",
  "thread_id": "optional-thread-id"
}
```

**Response:**
```json
{
  "response": "I've opened Chrome and searched for Python tutorials. Here are the top results...",
  "steps": [
    "Opened Chrome app",
    "Navigated to Google",
    "Searched for 'Python tutorials'"
  ],
  "success": true
}
```

**Use Cases:**
- "Open Settings and check my battery level"
- "Send a WhatsApp message to Mom saying I'll be late"
- "Take a screenshot and save it"
- "Navigate to LinkedIn and apply to jobs"

---

### 4. Tab Management

#### `GET /api/v1/tabs/list`

Get all open Chrome tabs.

**Response:**
```json
{
  "tabs": [
    {"title": "Google", "url": "https://google.com"},
    {"title": "GitHub", "url": "https://github.com"}
  ],
  "count": 2
}
```

#### `POST /api/v1/tabs/organize`

Organize tabs into AI-categorized groups (Work, Social, Shopping, Research, Entertainment).

**Response:**
```json
{
  "task_id": "tab-organize-001",
  "status": "started",
  "message": "Tab organization in progress"
}
```

#### `POST /api/v1/tabs/close-old`

Close tabs older than specified days.

**Request:**
```json
{
  "days_old": 7
}
```

#### `POST /api/v1/tabs/merge-duplicates`

Find and close duplicate tabs with the same URL.

#### `POST /api/v1/tabs/save-session`

Save current tabs as a named session.

**Request:**
```json
{
  "name": "Work Research Session"
}
```

**Response:**
```json
{
  "session_id": "sess-001",
  "name": "Work Research Session",
  "tab_count": 12,
  "created_at": "2026-01-31T10:00:00Z"
}
```

#### `POST /api/v1/tabs/restore-session`

Restore a saved session.

**Request:**
```json
{
  "session_id": "sess-001"
}
```

#### `GET /api/v1/tabs/sessions`

List all saved sessions.

#### `DELETE /api/v1/tabs/sessions/{session_id}`

Delete a saved session.

#### `GET /api/v1/tabs/status/{task_id}`

Check status of async tab operations.

---

### 5. Alarm & Calendar (Temporal Guardian)

#### `POST /api/v1/alarms/set`

Set an alarm on the Android device.

**Request:**
```json
{
  "hour": 7,
  "minute": 30,
  "label": "Wake up!",
  "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
}
```

#### `DELETE /api/v1/alarms/cancel`

Cancel alarms (opens clock app).

#### `POST /api/v1/alarms/calendar/event`

Create a calendar event.

**Request:**
```json
{
  "title": "Team Meeting",
  "start_time": "2026-02-01T14:00:00",
  "end_time": "2026-02-01T15:00:00",
  "description": "Weekly sync with the team"
}
```

#### `GET /api/v1/alarms/time`

Get current time from Android device.

---

### 6. Job Hunter

#### `POST /api/v1/jobs/upload-resume`

Upload and parse a resume PDF.

**Request:** `multipart/form-data` with `file` field

**Response:**
```json
{
  "success": true,
  "resume_data": {
    "name": "John Doe",
    "email": "john@example.com",
    "skills": ["Python", "JavaScript", "AWS"],
    "experience": [...],
    "education": [...]
  }
}
```

#### `POST /api/v1/jobs/search-and-apply`

Start automated job search and application.

**Request:**
```json
{
  "query": "Senior Python Developer",
  "max_applications": 5,
  "filters": {
    "experience_level": "senior",
    "job_type": "remote"
  }
}
```

**Response:**
```json
{
  "task_id": "job-search-001",
  "status": "started",
  "message": "Job search initiated"
}
```

#### `GET /api/v1/jobs/status/{task_id}`

Check status of job search task.

---

### 7. Human-in-the-Loop (HITL)

For handling CAPTCHAs, logins, and situations requiring human intervention.

#### `GET /api/v1/hitl/pending`

Get all pending intervention requests.

**Query Parameters:**
- `task_id` (optional): Filter by task

**Response:**
```json
{
  "requests": [
    {
      "request_id": "hitl-001",
      "message": "CAPTCHA detected - please solve",
      "options": ["Retry", "Abort", "I solved it"],
      "screenshot": "base64...",
      "status": "pending",
      "created_at": "2026-01-31T10:00:00Z"
    }
  ],
  "count": 1
}
```

#### `GET /api/v1/hitl/{request_id}`

Get details of a specific HITL request.

#### `GET /api/v1/hitl/{request_id}/screenshot`

Get the screenshot for a HITL request.

#### `POST /api/v1/hitl/{request_id}/respond`

Respond to a HITL request.

**Request:**
```json
{
  "action": "I solved it",
  "custom_input": "Optional additional input"
}
```

#### `DELETE /api/v1/hitl/{request_id}`

Cancel a pending HITL request.

---

### 8. Speech & Transcription

#### `POST /api/transcribe`

Transcribe audio to text.

**Request:** `multipart/form-data` with `audio` field (webm, wav, mp3)

**Response:**
```json
{
  "text": "Transcribed text from audio",
  "confidence": 0.95
}
```

---

### 9. Health & Status

#### `GET /health`

Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-31T10:00:00Z"
}
```

#### `GET /`

Root endpoint with service info.

**Response:**
```json
{
  "service": "Iron Claw Gateway",
  "version": "1.0.0",
  "endpoints": [...]
}
```

---

## Disabled Features

The following features are **NOT available** due to regional restrictions:

| Feature | Reason | Affected Endpoints |
|---------|--------|-------------------|
| **Voice Wake-up Calls** | Vapi not supported in this region | `/api/v1/wake/*`, `/api/schedule-call` |
| **Active Interrupter** | Requires Vapi voice AI | All voice call features |

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "ok": false,
  "error": "Error description",
  "detail": "Additional details if available"
}
```

**HTTP Status Codes:**
- `200` - Success
- `202` - Accepted (async task queued)
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not Found
- `500` - Internal Server Error

---

## Rate Limits

- **Requests per minute:** 60
- **Requests per hour:** 500
- **Concurrent tasks:** 5

---

## Telegram Notifications

All webhook executions send notifications to Telegram:
- **Bot:** @IronClawBot
- **Chat ID:** Configured in environment

Notification format:
```
🤖 *Iron Claw Task*
📋 Task: {taskId}
🔧 Type: {stepType}
📝 Message: {params.message}
⏰ Time: {timestamp}
```

---

## Integration Examples

### Example 1: Execute a Mobile Action

```bash
curl -X POST "https://your-tunnel.trycloudflare.com/openclaw/webhook" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ubuntu@clawdbot" \
  -d '{
    "taskId": "open-chrome-001",
    "type": "execute-step",
    "payload": {
      "stepType": "mobile_action",
      "params": {
        "action": "open_app",
        "extra": {"package": "com.android.chrome"}
      }
    }
  }'
```

### Example 2: Natural Language Command

```bash
curl -X POST "https://your-tunnel.trycloudflare.com/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Set an alarm for 7:30 AM tomorrow for my morning workout"
  }'
```

### Example 3: Batch Tab Cleanup

```bash
# 1. Close old tabs
curl -X POST "https://your-tunnel.trycloudflare.com/api/v1/tabs/close-old" \
  -H "Content-Type: application/json" \
  -d '{"days_old": 5}'

# 2. Merge duplicates
curl -X POST "https://your-tunnel.trycloudflare.com/api/v1/tabs/merge-duplicates"

# 3. Organize remaining tabs
curl -X POST "https://your-tunnel.trycloudflare.com/api/v1/tabs/organize"
```

### Example 4: Job Search Automation

```bash
# 1. Upload resume
curl -X POST "https://your-tunnel.trycloudflare.com/api/v1/jobs/upload-resume" \
  -F "file=@resume.pdf"

# 2. Start job search
curl -X POST "https://your-tunnel.trycloudflare.com/api/v1/jobs/search-and-apply" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Software Engineer",
    "max_applications": 10,
    "filters": {"job_type": "remote"}
  }'

# 3. Check status
curl "https://your-tunnel.trycloudflare.com/api/v1/jobs/status/job-task-id"
```

---

## Cloudflare Tunnel Setup

To expose Iron Claw to OpenClaw via Cloudflare Tunnel:

```bash
# Start the tunnel (run from monorepo root)
cloudflared tunnel --url http://localhost:8000 --protocol http2

# The tunnel will output a URL like:
# https://pack-nickel-occasionally-tube.trycloudflare.com
```

Use this URL as the base URL for OpenClaw integration.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENCLAW_HOOK_TOKEN` | Yes | Webhook auth token (`ubuntu@clawdbot`) |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot for notifications |
| `TELEGRAM_CHAT_ID` | Yes | Telegram chat for notifications |
| `MOBILERUN_API_KEY` | Yes | MobileRun cloud API key |
| `GEMINI_API_KEY` | Yes | Google Gemini for AI |

---

## Support

For issues or questions:
- Check the logs: `tail -f apps/gateway/logs/ironclaw.log`
- Verify health: `curl http://localhost:8000/health`
- Test webhook: Use the test commands above

---

*Documentation generated for OpenClaw integration - 2026-01-31*
