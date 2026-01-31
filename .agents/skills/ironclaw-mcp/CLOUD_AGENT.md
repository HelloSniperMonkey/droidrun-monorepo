# Iron Claw Cloud Agent API

## Overview

The **Cloud Agent API** (`/chat-cloud`) provides **direct access to MobileRun Cloud's AI agent** without the complexity of Iron Claw's local execution service. This is the **preferred method** for OpenClaw/ClawdBot integration when you want:

- ✅ **Pure cloud execution** (no local ADB required)
- ✅ **Live step-by-step updates** (real-time progress tracking)
- ✅ **Automatic device selection** (picks ready device from your pool)
- ✅ **Async task execution** (non-blocking, poll for results)
- ✅ **Full MobileRun features** (vision, reasoning, multi-step planning)

---

## Key Differences: `/chat-cloud` vs `/api/chat`

| Feature | `/chat-cloud` | `/api/chat` |
|---------|---------------|-------------|
| **Backend** | MobileRun Cloud API (direct) | Iron Claw agents (DroidRun/MobileRun) |
| **Device** | Cloud devices only | Cloud OR local ADB |
| **Execution** | Async with polling | Sync/blocking |
| **Updates** | Live step tracking | Final result only |
| **Complexity** | Simple HTTP proxy | Full agent framework |
| **Use Case** | Pure cloud automation | Hybrid local/cloud |
| **OpenClaw** | ✅ **Recommended** | Alternative |

---

## Endpoints

### 1. Execute Cloud Task

#### `POST /chat-cloud`

Start an AI task on MobileRun cloud device.

**Request:**
```json
{
  "message": "Open Chrome and search for restaurants near me",
  "device_id": "optional-device-id",
  "llm_model": "google/gemini-2.5-flash",
  "max_steps": 100,
  "vision": true,
  "reasoning": true,
  "temperature": 0.5,
  "execution_timeout": 1000,
  "wait_for_completion": false
}
```

**Parameters:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | string | **required** | Natural language command for the agent |
| `device_id` | string | auto-select | MobileRun device ID (omit to auto-select ready device) |
| `llm_model` | string | `google/gemini-2.5-flash` | LLM model to use |
| `max_steps` | integer | 100 | Max steps before timeout |
| `vision` | boolean | true | Enable vision/screenshot analysis |
| `reasoning` | boolean | true | Enable chain-of-thought reasoning |
| `temperature` | float | 0.5 | LLM temperature (0.0-1.0) |
| `execution_timeout` | integer | 1000 | Timeout in seconds |
| `wait_for_completion` | boolean | false | Block until task completes (not recommended) |

**Response:**
```json
{
  "success": true,
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "stream_url": "https://stream.mobilerun.ai/...",
  "message": "Task started. Poll /api/chat-cloud/tasks/{task_id} for live updates.",
  "status": "created"
}
```

---

### 2. Get Task Status with Live Steps (Polling Endpoint)

#### `GET /chat-cloud/tasks/{task_id}`

**Use this endpoint** to poll for task progress and get live step updates.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "steps": [
    {
      "step_number": 1,
      "event": "ExecutorActionEvent",
      "description": "Opening Chrome app",
      "action": "{\"action\": \"tap\", \"package\": \"com.android.chrome\"}",
      "thought": "I need to open Chrome to perform web search",
      "success": true,
      "timestamp": "2026-02-01T10:00:01Z"
    },
    {
      "step_number": 2,
      "event": "ExecutorActionEvent",
      "description": "Tapping search bar",
      "action": "{\"action\": \"tap\", \"element\": \"search_box\"}",
      "thought": "Now I'll tap the search bar to enter the query",
      "success": true,
      "timestamp": "2026-02-01T10:00:03Z"
    }
  ],
  "total_steps": 2,
  "final_answer": null,
  "success": null,
  "error": null
}
```

**Status Values:**
- `created` - Task just started
- `running` - Task executing (poll this endpoint every 1-2 seconds)
- `completed` - Task finished successfully
- `failed` - Task failed
- `cancelled` - Task cancelled
- `timeout` - Task exceeded timeout

**When to stop polling:**
- Status is `completed`, `failed`, `cancelled`, or `timeout`
- Then read `final_answer` and `success` fields

---

### 3. Get Simple Status

#### `GET /chat-cloud/status/{task_id}`

Lightweight endpoint for status check only (no steps).

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running"
}
```

---

### 4. Get Task Trajectory (Steps)

#### `GET /chat-cloud/trajectory/{task_id}`

Get detailed trajectory after task completion.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "steps": [
    {
      "step_number": 1,
      "event": "ExecutorActionEvent",
      "description": "Opening Chrome",
      "action": "...",
      "thought": "...",
      "success": true
    }
  ],
  "total_steps": 5,
  "final_answer": "I found 10 restaurants near you. The top result is..."
}
```

---

### 5. List Available Devices

#### `GET /chat-cloud/devices`

Get list of all MobileRun devices in your account.

**Response:**
```json
{
  "items": [
    {
      "id": "2e9c8957-47d8-471c-8043-9f0fa44f75cb",
      "name": "Android Device 1",
      "state": "ready",
      "status": "ready"
    }
  ]
}
```

---

## Usage Examples

### Example 1: Basic Task Execution

```bash
# 1. Start task
curl -X POST "https://your-tunnel.trycloudflare.com/chat-cloud" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Open Chrome and go to google.com",
    "max_steps": 20
  }'

# Response: {"success": true, "task_id": "abc123", ...}

# 2. Poll for updates
curl "https://your-tunnel.trycloudflare.com/chat-cloud/tasks/abc123"

# 3. Keep polling every 2 seconds until status is "completed"
```

### Example 2: Python Client

```python
import asyncio
import httpx

BASE_URL = "https://your-tunnel.trycloudflare.com"

async def execute_cloud_task(message: str):
    async with httpx.AsyncClient() as client:
        # Start task
        response = await client.post(
            f"{BASE_URL}/chat-cloud",
            json={"message": message}
        )
        data = response.json()
        task_id = data["task_id"]
        print(f"Task started: {task_id}")
        
        # Poll for completion
        while True:
            status_response = await client.get(
                f"{BASE_URL}/chat-cloud/tasks/{task_id}"
            )
            status_data = status_response.json()
            
            print(f"Status: {status_data['status']}")
            print(f"Steps: {status_data['total_steps']}")
            
            # Print latest step
            if status_data['steps']:
                latest = status_data['steps'][-1]
                print(f"  {latest['step_number']}. {latest['description']}")
            
            # Check if done
            if status_data['status'] in ['completed', 'failed', 'cancelled']:
                print(f"Final answer: {status_data['final_answer']}")
                break
            
            await asyncio.sleep(2)

# Usage
asyncio.run(execute_cloud_task("Set an alarm for 7:30 AM"))
```

### Example 3: OpenClaw Integration

Add this to your OpenClaw skill definition:

```yaml
tools:
  - name: ironclaw_cloud_execute
    description: |
      Execute a task on Iron Claw's MobileRun cloud agent.
      Returns a task_id that you must poll for completion.
    inputSchema:
      type: object
      required: ["message"]
      properties:
        message:
          type: string
          description: "Natural language command"
        max_steps:
          type: integer
          default: 100
        vision:
          type: boolean
          default: true
        reasoning:
          type: boolean
          default: true
    endpoint: "/chat-cloud"
    method: "POST"
    responseType: "async"
  
  - name: ironclaw_cloud_poll
    description: |
      Poll the status of a cloud task. Use this repeatedly until
      status is 'completed', 'failed', or 'cancelled'.
    inputSchema:
      type: object
      required: ["task_id"]
      properties:
        task_id:
          type: string
    endpoint: "/chat-cloud/tasks/{task_id}"
    method: "GET"
```

---

## Workflow for OpenClaw

### 1. **Execute Task**
```
POST /chat-cloud
{"message": "Open Chrome and search for Python tutorials"}
→ Returns: {"task_id": "abc123", "status": "created"}
```

### 2. **Poll for Updates**
```
Loop every 2 seconds:
  GET /chat-cloud/tasks/abc123
  → Returns: {"status": "running", "steps": [...], "total_steps": 3}
  
  If status in [completed, failed, cancelled]:
    Break loop
```

### 3. **Get Final Result**
```
Final response contains:
- final_answer: "I found 10 Python tutorials. Here are the top ones..."
- success: true
- steps: [...] (all steps taken)
```

---

## Device Selection Logic

The endpoint **automatically selects a device** using this priority:

1. **Request parameter:** Use `device_id` from request if provided
2. **Environment variable:** Use `MOBILERUN_DEVICE_ID` from `.env`
3. **Auto-select from API:**
   - First try devices with `state: "ready"`
   - Then try devices with `state: "assigned"`
   - Finally try any non-terminated device

**Manual device selection:**
```bash
# List devices
curl "https://your-tunnel.trycloudflare.com/chat-cloud/devices"

# Use specific device
curl -X POST "https://your-tunnel.trycloudflare.com/chat-cloud" \
  -d '{"message": "...", "device_id": "2e9c8957-..."}'
```

---

## LLM Model Options

Supported models via MobileRun:

| Model | ID | Notes |
|-------|----|----|
| Gemini 2.0 Flash | `google/gemini-2.0-flash-exp` | Fast, efficient |
| Gemini 2.5 Flash | `google/gemini-2.5-flash` | **Default**, best balance |
| Gemini Pro | `google/gemini-pro` | More capable |
| Claude 3.5 Sonnet | `anthropic/claude-3.5-sonnet` | High quality reasoning |
| GPT-4o | `openai/gpt-4o` | OpenAI's latest |

**Set model in request:**
```json
{
  "message": "...",
  "llm_model": "anthropic/claude-3.5-sonnet",
  "temperature": 0.7
}
```

---

## Event Types in Steps

| Event | Description |
|-------|-------------|
| `ExecutorActionEvent` | Actual action taken (tap, swipe, type, etc.) |
| `ExecutorActionResultEvent` | Result of action (success/failure) |
| `ManagerPlanDetailsEvent` | Agent's plan and current subgoal |
| `ResultEvent` | Final task result |
| `FinalizeEvent` | Task finalization |

**Most useful:** `ExecutorActionEvent` - shows what the agent is doing

---

## Error Handling

### No Device Available
```json
{
  "success": false,
  "error": "No device ID provided and no ready devices found. Please select a device."
}
```

**Solution:** 
- Set `MOBILERUN_DEVICE_ID` in `.env`, or
- Pass `device_id` in request, or
- Ensure you have ready devices in MobileRun dashboard

### Task Failed
```json
{
  "task_id": "abc123",
  "status": "failed",
  "success": false,
  "error": "Task failed",
  "final_answer": "I couldn't complete the task because..."
}
```

### Timeout
```json
{
  "task_id": "abc123",
  "status": "timeout",
  "success": false
}
```

---

## Best Practices for OpenClaw

### 1. Always Poll for Completion

```javascript
async function executeCloudTask(message) {
  // Start task
  const response = await fetch('/chat-cloud', {
    method: 'POST',
    body: JSON.stringify({ message })
  });
  const { task_id } = await response.json();
  
  // Poll until done
  while (true) {
    const statusResp = await fetch(`/chat-cloud/tasks/${task_id}`);
    const status = await statusResp.json();
    
    if (['completed', 'failed', 'cancelled'].includes(status.status)) {
      return status.final_answer;
    }
    
    await sleep(2000); // Wait 2 seconds
  }
}
```

### 2. Set Appropriate Timeouts

- **Quick tasks** (open app): `max_steps: 10-20`
- **Medium tasks** (search, navigate): `max_steps: 50-100`
- **Complex tasks** (job apply, multi-step): `max_steps: 200-500`

### 3. Enable Vision for UI Tasks

```json
{
  "message": "Click the blue button",
  "vision": true,  // ← Required for visual tasks
  "reasoning": true
}
```

### 4. Use Reasoning for Complex Tasks

```json
{
  "message": "Find the cheapest flight to Paris",
  "reasoning": true,  // ← Enables chain-of-thought
  "max_steps": 200
}
```

---

## Comparison with Webhook

| Feature | `/chat-cloud` | `/openclaw/webhook` |
|---------|---------------|---------------------|
| **Direct MobileRun** | ✅ Yes | ❌ No (goes through service) |
| **Live Updates** | ✅ Step-by-step | ❌ Final result only |
| **Device** | Cloud only | Cloud or local |
| **Auth Required** | ❌ No | ✅ Yes (Bearer token) |
| **Polling** | ✅ Yes | ❌ No |
| **Use Case** | Cloud automation | Webhook integration |

**Recommendation:** Use `/chat-cloud` for **real-time cloud automation** with live progress tracking. Use `/openclaw/webhook` for **webhook-based integration** where you need token auth and task queuing.

---

## Summary

| What | Endpoint |
|------|----------|
| **Execute task** | `POST /chat-cloud` |
| **Poll progress** | `GET /chat-cloud/tasks/{task_id}` ← **Use this** |
| **Quick status** | `GET /chat-cloud/status/{task_id}` |
| **Get trajectory** | `GET /chat-cloud/trajectory/{task_id}` |
| **List devices** | `GET /chat-cloud/devices` |

**Typical Flow:**
1. `POST /chat-cloud` → Get `task_id`
2. Poll `GET /chat-cloud/tasks/{task_id}` every 2s
3. Stop when `status` ∈ {completed, failed, cancelled}
4. Read `final_answer` and `steps`

---

*Cloud Agent API - Powered by MobileRun*
