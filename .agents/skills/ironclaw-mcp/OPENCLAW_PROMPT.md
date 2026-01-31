# OpenClaw Integration Prompt for Iron Claw Skill

## System Prompt for OpenClaw/ClawdBot

Use this prompt to configure OpenClaw to use Iron Claw as a skill:

---

### PROMPT START

```markdown
# Iron Claw - Mobile Automation Skill

You have access to **Iron Claw**, a Mobile-First Autonomous Agent that controls Android devices via cloud API. Use this skill to automate mobile tasks, manage Chrome tabs, set alarms, search for jobs, and more.

## Connection Details

- **Base URL:** `${IRONCLAW_BASE_URL}` (e.g., `https://ironclaw.snipermonkey.in` or `https://pack-nickel-occasionally-tube.trycloudflare.com`)
- **Authentication:** `Authorization: Bearer ubuntu@clawdbot`
- **Health Check:** `GET /health`

## Available Actions

### 1. 🤖 Execute Webhook Task (Main Entry Point)

**When to use:** For any mobile automation task that needs to be tracked.

**Endpoint:** `POST /openclaw/webhook`

**Request Format:**
```json
{
  "taskId": "<unique-id>",
  "type": "execute-step",
  "payload": {
    "stepType": "log|mobile_action|http_action|click|extract",
    "params": {
      "message": "For log steps",
      "action": "For mobile actions",
      "url": "For HTTP actions"
    }
  }
}
```

**Step Types:**
- `log` - Log a message (appears in Telegram)
- `mobile_action` - Execute Android action (open app, tap, swipe)
- `http_action` - Make HTTP request from device
- `click` - Click element on screen
- `extract` - Extract data from screen

### 2. 💬 Natural Language Chat

**When to use:** For complex commands that need AI interpretation.

**Endpoint:** `POST /api/chat`

**Examples:**
- "Open Chrome and search for restaurants near me"
- "Send a WhatsApp message to Mom"
- "Take a screenshot of my current screen"
- "Navigate to LinkedIn and check notifications"

**Request:**
```json
{
  "message": "Your natural language command here"
}
```

### 2b. ☁️ Cloud Agent (RECOMMENDED)

**When to use:** For cloud automation with live step-by-step progress tracking.

**Endpoints:**
- `POST /api/chat-cloud` - Start task
- `GET /api/chat-cloud/tasks/{task_id}` - Poll for updates

**Why use this:**
- ✅ Real-time progress updates
- ✅ Async execution with polling
- ✅ Automatic device selection
- ✅ Direct MobileRun API access

**Example Flow:**
```json
// 1. Start task
POST /api/chat-cloud
{
  "message": "Open Chrome and search for Python tutorials",
  "max_steps": 100,
  "vision": true,
  "reasoning": true
}
→ Returns: {"task_id": "abc123", "status": "created"}

// 2. Poll for updates (every 2 seconds)
GET /api/chat-cloud/tasks/abc123
→ Returns: {
  "status": "running",
  "steps": [
    {"step_number": 1, "description": "Opening Chrome", "success": true},
    {"step_number": 2, "description": "Tapping search bar", "success": true}
  ],
  "total_steps": 2,
  "final_answer": null
}

// 3. Keep polling until status = "completed"
→ Returns: {
  "status": "completed",
  "final_answer": "I found 10 Python tutorials. Here are the top ones...",
  "success": true
}
```

### 3. 📑 Tab Management

**Available Actions:**

| Action | Endpoint | Description |
|--------|----------|-------------|
| List tabs | `GET /api/v1/tabs/list` | Get all open Chrome tabs |
| Organize | `POST /api/v1/tabs/organize` | AI-categorize tabs |
| Close old | `POST /api/v1/tabs/close-old` | Close stale tabs |
| Merge dupes | `POST /api/v1/tabs/merge-duplicates` | Remove duplicates |
| Save session | `POST /api/v1/tabs/save-session` | Bookmark current tabs |
| Restore session | `POST /api/v1/tabs/restore-session` | Restore saved tabs |

### 4. ⏰ Alarm & Calendar

| Action | Endpoint | Request |
|--------|----------|---------|
| Set alarm | `POST /api/v1/alarms/set` | `{"hour": 7, "minute": 30, "label": "Wake up"}` |
| Calendar event | `POST /api/v1/alarms/calendar/event` | `{"title": "Meeting", "start_time": "..."}` |
| Get device time | `GET /api/v1/alarms/time` | - |

### 5. 💼 Job Hunter

| Action | Endpoint | Description |
|--------|----------|-------------|
| Upload resume | `POST /api/v1/jobs/upload-resume` | Parse resume PDF |
| Search & apply | `POST /api/v1/jobs/search-and-apply` | Auto-apply to jobs |
| Check status | `GET /api/v1/jobs/status/{task_id}` | Get task progress |

### 6. 🤝 Human-in-the-Loop (HITL)

When automation encounters CAPTCHAs, logins, or needs human help:

| Action | Endpoint |
|--------|----------|
| Get pending | `GET /api/v1/hitl/pending` |
| View request | `GET /api/v1/hitl/{request_id}` |
| Get screenshot | `GET /api/v1/hitl/{request_id}/screenshot` |
| Respond | `POST /api/v1/hitl/{request_id}/respond` |

### 7. 🔍 Task Management

| Action | Endpoint |
|--------|----------|
| List all tasks | `GET /openclaw/tasks` |
| Get task status | `GET /openclaw/tasks/{run_id}` |
| Cancel task | `DELETE /openclaw/tasks/{run_id}` |

## ❌ Disabled Features

The following features are **NOT AVAILABLE** (Vapi not supported in this region):
- Voice wake-up calls (`/api/v1/wake/*`)
- Active Interrupter calls
- Schedule call (`/api/schedule-call`)

Do not attempt to use these endpoints.

## Usage Guidelines

1. **Always use unique taskIds** - Use UUID or descriptive IDs like `openclaw-tabs-20260131-001`

2. **Check task status for async operations** - Tab organize, job search, etc. are async. Poll status endpoint.

3. **Handle HITL requests** - When tasks pause for human input, check `/api/v1/hitl/pending`

4. **Use chat for complex commands** - The AI chat endpoint is powerful for natural language

5. **Rate limits apply:**
   - 60 requests/minute
   - 500 requests/hour
   - 5 concurrent tasks

## Example Workflows

### Workflow 1: Morning Productivity

```
1. POST /api/v1/alarms/set {"hour": 7, "minute": 0, "label": "Morning routine"}
2. POST /api/chat {"message": "Open my calendar and show today's events"}
3. POST /api/v1/tabs/organize
```

### Workflow 2: Job Search

```
1. POST /api/v1/jobs/upload-resume (with PDF)
2. POST /api/v1/jobs/search-and-apply {"query": "Python Developer", "max_applications": 5}
3. GET /api/v1/jobs/status/{task_id} (poll until complete)
4. GET /api/v1/hitl/pending (check for CAPTCHAs)
```

### Workflow 3: Tab Cleanup

```
1. GET /api/v1/tabs/list (see current tabs)
2. POST /api/v1/tabs/close-old {"days_old": 7}
3. POST /api/v1/tabs/merge-duplicates
4. POST /api/v1/tabs/save-session {"name": "Clean slate"}
```

## Error Handling

All errors return:
```json
{
  "ok": false,
  "error": "Error message",
  "detail": "Additional info"
}
```

Common errors:
- `401` - Check Authorization header
- `400` - Validate request body
- `404` - Task/resource not found
- `500` - Check Iron Claw logs

## Testing Connection

Before using, verify connection:
```bash
curl -s https://<tunnel-urironclaw.snipermonkey.in
IRONCLAW_WEBHOOK_TOKEN=ubuntu@clawdbot

# Or use Cloudflare tunnel for temporary access
IRONCLAW_BASE_URL=https://pack-nickel-occasionally-tube.trycloudflare.com

Expected: `{"status": "healthy", ...}`
```

### PROMPT END

---

## Configuration for OpenClaw

### Skill Registration

Add this to your OpenClaw skill configuration:

```yaml
skills:
  - id: ironclaw
    name: "Iron Claw"
    description: "Mobile-First Android Automation Agent"
    baseUrl: "${IRONCLAW_BASE_URL}"
    auth:
      type: bearer
      token: "ubuntu@clawdbot"
    healthCheck:
      endpoint: "/health"
      interval: 60
    capabilities:
      - android_control
      - web_automation
      - job_hunting
      - tab_management
      - alarm_calendar
      - speech_to_text
      - human_in_loop
    disabled:
      - voice_calls
```

### Environment Variables

Set these in your OpenClaw environment:

```bash
# Iron Claw connection
IRONCLAW_BASE_URL=https://pack-nickel-occasionally-tube.trycloudflare.com
IRONCLAW_WEBHOOK_TOKEN=ubuntu@clawdbot

# Or for local development
IRONCLAW_BASE_URL=http://localhost:8000
```

### Webhook Configuration

If OpenClaw needs to receive callbacks from Iron Claw:

```yaml
webhooks:
  ironclaw_callback:
    url: "${OPENCLAW_CALLBACK_URL}"
    events:
      - task.completed
      - task.failed
      - hitl.required
```

---

## Deployment Options

### Option 1: Cloudflare Tunnel (Recommended)

```bash
# On Iron Claw server
cd /path/to/monorepo
./start.sh  # Start Iron Claw services

# In separate terminal
cloudflared tunnel --url http://localhost:8000 --protocol http2
```

Use the generated URL (e.g., `https://xxx.trycloudflare.com`) as `IRONCLAW_BASE_URL`.

### Option 2: Permanent Cloudflare Tunnel

```bash
# Create named tunnel
cloudflared tunnel create ironclaw

# Configure tunnel
cloudflared tunnel route dns ironclaw ironclaw.yourdomain.com

# Run tunnel
cloudflared tunnel run ironclaw
```

### Option 3: Direct Deployment

Deploy Iron Claw to a cloud provider with a public IP:
- Railway
- Render
- DigitalOcean
- AWS EC2

Then set `IRONCLAW_BASE_URL` to the public URL.

---

## Verification Checklist

Before going live, verify:

- [ ] `GET /health` returns `{"status": "healthy"}`
- [ ] `POST /openclaw/webhook` with test payload works
- [ ] Telegram notifications are received
- [ ] Task status queries work
- [ ] At least one Android device is connected (MobileRun or ADB)
- [ ] AI chat responds correctly

---

## Troubleshooting

### "Connection refused"
- Check Iron Claw is running: `curl localhost:8000/health`
- Check Cloudflare tunnel is running
- Verify URL is correct

### "401 Unauthorized"
- Check `Authorization: Bearer ubuntu@clawdbot` header
- Verify `OPENCLAW_HOOK_TOKEN` in Iron Claw `.env`

### "No device connected"
- Check MobileRun API key in `.env`
- Verify device ID if using specific device
- Check ADB connection if using local device

### "Task stuck in pending"
- Check for HITL requests: `GET /api/v1/hitl/pending`
- Check Iron Claw logs for errors
- Verify device is responsive

---

## Support

- **Logs:** `tail -f apps/gateway/logs/ironclaw.log`
- **Health:** `curl http://localhost:8000/health`
- **Telegram:** Notifications go to configured bot

---

*Iron Claw × OpenClaw Integration - Ready for Production*
