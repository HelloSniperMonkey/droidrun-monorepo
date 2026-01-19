# Iron Claw Gateway

Mobile-First Autonomous Agent Architecture

## Quick Start

```bash
# From monorepo root
cd /Users/soumyayotimohanta/Developer/hackathon/monorepo

# Install dependencies with uv
uv sync

# Copy environment template and fill in your keys
cp .env.example .env
# Edit .env with your API keys

# Run the gateway
uv run python -m ironclaw.main
```

## API Endpoints

### Health Check
```
GET /health
GET /
```

### Job Hunter (The "Body")
```
POST /api/v1/jobs/upload-resume  - Upload and parse resume PDF
POST /api/v1/jobs/search-and-apply  - Start job search automation
GET /api/v1/jobs/status/{task_id}  - Check task status
```

### Temporal Guardian (Calendar & Alarms)
```
POST /api/v1/alarms/set  - Set an alarm via Android Intent
DELETE /api/v1/alarms/cancel  - Open clock app for manual management
POST /api/v1/alarms/calendar/event  - Create calendar event
GET /api/v1/alarms/time  - Get device time
```

### Active Interrupter (Vapi Wake-up Calls)
```
POST /api/v1/wake/call-now  - Trigger immediate wake-up call
POST /api/v1/wake/schedule  - Schedule a wake-up call
GET /api/v1/wake/location  - Get device location & timezone
DELETE /api/v1/wake/schedule/{job_id}  - Cancel scheduled call
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| GEMINI_API_KEY | Google Gemini API key | Yes |
| VAPI_API_KEY | Vapi API key | Yes |
| VAPI_PHONE_NUMBER_ID | Vapi phone number ID | Yes |
| DEVICE_SERIAL | ADB device serial (IP:PORT for Mobilerun) | No |
| USER_PHONE_NUMBER | User's phone for wake-up calls | Yes |
| TELEGRAM_BOT_TOKEN | Telegram bot token | No |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│   Gateway API   │────▶│  Mobilerun/ADB  │
│  (User Input)   │     │   (FastAPI)     │     │  (Android)      │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────┴────────┐
                        ▼                 ▼
               ┌─────────────┐    ┌─────────────┐
               │  Vapi API   │    │  Gemini LLM │
               │  (Calls)    │    │  (Reasoning)│
               └─────────────┘    └─────────────┘
```
