# Iron Claw

🦾 **Mobile-First Autonomous Agent Architecture**

A Python gateway that orchestrates Android device automation, voice AI calls, and job hunting - all controllable via Telegram or API.

## What is Iron Claw?

Iron Claw is an autonomous agent that can:
- **Job Hunter**: Parse your resume, search for jobs, and auto-apply using mobile Chrome
- **Temporal Guardian**: Set alarms and calendar events via Android intents
- **Active Interrupter**: Call you at 2 AM with Vapi to verify you're awake

## Quick Start

```bash
# Install dependencies
uv sync

# Configure your environment
cp .env.example .env
# Add your API keys to .env

# Start the gateway
uv run uvicorn ironclaw.main:app --reload
```

## Project Structure

```
monorepo/
├── apps/
│   └── gateway/              # Python FastAPI backend
│       └── src/ironclaw/
│           ├── main.py       # FastAPI app
│           ├── api/          # REST endpoints
│           ├── agents/       # DroidRun agent logic
│           └── modules/      # Feature modules
├── data/
│   └── uploads/              # Resume and file storage
├── packages/
│   └── shared/               # Shared configs
├── resume.pdf                # Your resume for testing
├── pyproject.toml            # Python dependencies
└── .env.example              # Environment template
```

## Requirements

- Python 3.11+
- Mobilerun Cloud instance OR Android device with ADB
- API Keys: Gemini, Vapi, (optional) Telegram

## API Documentation

Start the server and visit: `http://localhost:8000/docs`

## Security

- Package whitelist prevents agent from accessing sensitive apps
- No secrets in code - environment variables only
- ADB traffic should be tunneled (Tailscale/SSH) for production

## License

MIT
