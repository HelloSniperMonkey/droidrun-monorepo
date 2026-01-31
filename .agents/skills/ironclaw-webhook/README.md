# Iron Claw Webhook Skill

OpenClaw skill for executing tasks on Iron Claw via webhook integration.

## Overview

This skill enables OpenClaw agents to:
- **Execute steps** on Iron Claw mobile automation platform
- **Query status** of running tasks
- **Cancel tasks** that are pending or running

## Installation

1. Copy the skill directory to your OpenClaw skills folder:
   ```bash
   cp -r ironclaw-webhook ~/.openclaw/skills/
   ```

2. Install dependencies:
   ```bash
   pip install httpx
   ```

3. Configure environment variables:
   ```bash
   export IRONCLAW_WEBHOOK_URL="https://your-tunnel.trycloudflare.com"
   export OPENCLAW_HOOK_TOKEN="your-secret-token"
   ```

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `IRONCLAW_WEBHOOK_URL` | Base URL for Iron Claw webhook | No | `https://complimentary-actress-rfc-mile.trycloudflare.com` |
| `OPENCLAW_HOOK_TOKEN` | Bearer token for authentication | **Yes** | - |

### skill.yaml Configuration

```yaml
config:
  ironclaw_url: "https://your-tunnel.trycloudflare.com"
  hook_token: "${OPENCLAW_HOOK_TOKEN}"  # Reference env var
```

## Actions

### 1. run-step

Execute a step/task on Iron Claw.

**Parameters:**
- `task_id` (string, required): Unique identifier for the task
- `step_type` (string, required): Type of step to execute
  - `log` - Log a message
  - `http_action` - Make an HTTP request
  - `click` - Click on a UI element
  - `extract` - Extract data from screen
  - `mobile_action` - Perform mobile action
  - `script` - Execute a script
- `params` (object, optional): Parameters specific to the step type

**Example:**
```python
result = await skill.run_step(
    task_id="job-apply-001",
    step_type="mobile_action",
    params={
        "action": "click",
        "selector": "button.apply-now"
    }
)
# Returns: {"ok": True, "runId": "abc-123", "status": "queued"}
```

### 2. query-status

Query the status of a running task.

**Parameters:**
- `run_id` (string, required): Run ID returned from run-step

**Example:**
```python
status = await skill.query_status(run_id="abc-123")
# Returns: {"ok": True, "runId": "abc-123", "status": "completed"}
```

**Status Values:**
- `pending` - Task received but not yet queued
- `queued` - Task in queue waiting for execution
- `running` - Task currently executing
- `completed` - Task finished successfully
- `failed` - Task failed with error
- `cancelled` - Task was cancelled

### 3. cancel-task

Cancel a pending or running task.

**Parameters:**
- `run_id` (string, required): Run ID of the task to cancel

**Example:**
```python
result = await skill.cancel_task(run_id="abc-123")
# Returns: {"ok": True, "runId": "abc-123", "status": "cancelled"}
```

## Usage Examples

### Basic Usage

```python
from ironclaw_skill import IronClawSkill

async def main():
    async with IronClawSkill() as skill:
        # Execute a log step
        result = await skill.run_step(
            task_id="test-001",
            step_type="log",
            params={"message": "Hello from OpenClaw!"}
        )
        print(f"Task queued with run_id: {result['runId']}")
        
        # Wait and check status
        import asyncio
        await asyncio.sleep(2)
        
        status = await skill.query_status(result["runId"])
        print(f"Task status: {status['status']}")
```

### Job Application Workflow

```python
async def apply_to_job(job_url: str):
    async with IronClawSkill() as skill:
        # Navigate to job page
        result = await skill.run_step(
            task_id=f"job-{job_url[:20]}",
            step_type="http_action",
            params={
                "url": job_url,
                "method": "GET"
            }
        )
        
        # Click apply button
        await skill.run_step(
            task_id=f"apply-{job_url[:20]}",
            step_type="mobile_action",
            params={
                "action": "click",
                "selector": "button.easy-apply"
            }
        )
```

### Using with OpenClaw Hooks

Add to your OpenClaw `hooks.mappings`:

```yaml
hooks:
  enabled: true
  mappings:
    - source: "session.action"
      target: "ironclaw-webhook.run-step"
      transform:
        task_id: "{{ session.key }}"
        step_type: "{{ action.type }}"
        params: "{{ action.params }}"
```

## Testing

Run unit tests:

```bash
cd ironclaw-webhook
pytest test_ironclaw_skill.py -v
```

Run with coverage:

```bash
pytest test_ironclaw_skill.py --cov=ironclaw_skill --cov-report=html
```

## Troubleshooting

### Authentication Error

```
AuthenticationError: Invalid token
```

**Solution:** Verify `OPENCLAW_HOOK_TOKEN` is set correctly and matches the token configured in Iron Claw.

### Connection Error

```
httpx.ConnectError: Unable to connect
```

**Solution:** 
1. Check that Iron Claw is running
2. Verify the tunnel URL is accessible
3. Check firewall/network settings

### Task Not Found

```
TaskNotFoundError: Task not found
```

**Solution:** The `run_id` may be expired or invalid. Tasks are stored in memory and may be lost on server restart.

## API Reference

### IronClawSkill

```python
class IronClawSkill:
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        config: Optional[SkillConfig] = None,
    ): ...
    
    async def run_step(
        self,
        task_id: str,
        step_type: str,
        params: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> dict: ...
    
    async def query_status(self, run_id: str) -> dict: ...
    
    async def cancel_task(self, run_id: str) -> dict: ...
    
    async def list_tasks(
        self,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> dict: ...
    
    async def health_check(self) -> dict: ...
```

## License

MIT License - see LICENSE file for details.
