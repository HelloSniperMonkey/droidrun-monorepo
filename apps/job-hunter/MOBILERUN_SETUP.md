# MobileRun API Setup Guide

## Getting Your MobileRun API Key

### Step 1: Sign Up

1. Go to [MobileRun Cloud](https://cloud.mobilerun.ai/)
2. Click "Sign Up" or "Get Started"
3. Create an account with your email
4. Verify your email address

### Step 2: Access Dashboard

1. Log in to your account
2. Navigate to the Dashboard
3. Look for "API Keys" section in the sidebar

### Step 3: Create API Key

1. Click "Create API Key" or "+ New API Key"
2. Give it a descriptive name: "AI Job Hunter"
3. Click "Create"
4. **IMPORTANT**: Copy the API key immediately (it won't be shown again)
5. Save it securely

### Step 4: Add to Environment

1. Open your `.env` file
2. Add the API key:
   ```env
   MOBILERUN_API_KEY=your_api_key_here
   ```

## Understanding MobileRun Pricing

MobileRun Cloud operates on a credit-based system:

- **Steps**: Each action the agent takes (tap, type, scroll, etc.)
- **Execution Time**: Time the agent runs
- **LLM Calls**: AI model usage for decision-making

Check the [Pricing Page](https://mobilerun.ai/pricing) for current rates.

## Configuration Options

### LLM Models

Available models (set in `.env`):

```env
# Fast and cheap (recommended for testing)
LLM_MODEL=google/gemini-2.5-flash

# More accurate (costs more)
LLM_MODEL=google/gemini-1.5-pro
LLM_MODEL=anthropic/claude-3-5-sonnet

# OpenAI models
LLM_MODEL=openai/gpt-4o
LLM_MODEL=openai/gpt-4o-mini
```

### Quota Settings

Control spending with quotas:

```env
# Maximum steps before stopping
MAX_STEPS_QUOTA=100

# Minimum jobs to apply to before stopping
MIN_JOBS_APPLIED=10

# Execution timeout per task (seconds)
AGENT_EXECUTION_TIMEOUT=300

# Temperature (0-2, lower = more deterministic)
AGENT_TEMPERATURE=0.5
```

## Best Practices

### 1. Start Small
- Test with `MIN_JOBS_APPLIED=1` initially
- Use `MAX_STEPS_QUOTA=20` for testing
- Use fast models like `gemini-2.5-flash`

### 2. Monitor Usage
- Check your dashboard regularly
- Set up billing alerts
- Review task logs for optimization

### 3. Optimize Prompts
- Clear, specific instructions reduce steps
- Enable reasoning mode for complex tasks
- Use structured output schemas

### 4. Handle Failures
- Set reasonable timeouts
- Implement retry logic (planned feature)
- Use DroidRun backup for critical tasks

## API Endpoints

The application uses these MobileRun API endpoints:

```
POST /v1/tasks              # Create new task
GET  /v1/tasks/{id}         # Get task status
GET  /v1/devices            # List devices
POST /v1/apps               # Upload apps
```

Full API documentation: https://docs.mobilerun.ai/api-reference

## Troubleshooting

### Error: "Invalid API key"
- Check that you copied the entire key
- Ensure no extra spaces in `.env` file
- Verify key hasn't been revoked

### Error: "Rate limit exceeded"
- Wait before making more requests
- Check your account limits
- Contact support to increase limits

### Error: "Insufficient credits"
- Add credits to your account
- Reduce quota settings
- Use cheaper LLM models

## Device Selection

MobileRun Cloud provides:

- **Temporary Devices**: Fresh device for each task (recommended)
- **Persistent Devices**: Reusable device with saved state
- **VPN Routing**: Route traffic through specific countries

Configure in task creation:

```python
result = agent.create_task(
    task_prompt="...",
    device_type="temporary",  # or "persistent"
    vpn_country="US",         # Optional
    apps=["com.linkedin.android"]  # Pre-install apps
)
```

## Support

- Documentation: https://docs.mobilerun.ai/
- Discord: https://discord.gg/droidrun
- Email: support@mobilerun.ai
- Twitter: [@droid_run](https://x.com/droid_run)

## Security Tips

1. **Never commit API keys** to version control
2. **Rotate keys** periodically (monthly recommended)
3. **Use environment variables** for all secrets
4. **Monitor usage** for unexpected activity
5. **Revoke old keys** when no longer needed
6. **Use separate keys** for dev/staging/production
