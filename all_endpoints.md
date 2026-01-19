# Monorepo Backend Endpoints - Complete Reference

This document lists all backend API endpoints available in the monorepo for all agents to reference.

**Total Endpoints:** 44  
**Last Updated:** 2026-01-19

---

## Table of Contents
1. [Iron Claw Gateway (FastAPI)](#iron-claw-gateway-fastapi)
2. [Job Hunter Dashboard (Flask)](#job-hunter-dashboard-flask)
3. [Response Formats](#response-formats)
4. [Notes](#notes)

---

## Iron Claw Gateway (FastAPI)

**Base URL:** `http://localhost:8000`  
**Framework:** FastAPI (Python)  
**Location:** `/monorepo/apps/gateway/src/ironclaw/`  
**Total Endpoints:** 35

### Health & Status

| Method | Route | File | Description |
|--------|-------|------|-------------|
| GET | `/health` | api/health.py:9 | Basic health check endpoint. Returns service status. |
| GET | `/` | api/health.py:15 | Root endpoint with service info, version, and available endpoints listing. |

### Web Chat & Transcription (`/api`)

| Method | Route | File | Description |
|--------|-------|------|-------------|
| POST | `/api/chat` | api/chat.py:38 | Handle chat messages. Processes user commands and routes to appropriate agents (IronClawAgent, PersonalizationService, TabManager). Supports image context. |
| POST | `/api/upload` | api/chat.py:155 | Handle file uploads. Saves files to data/uploads directory. Used for resume uploads and images. |
| POST | `/api/schedule-call` | api/chat.py:182 | Proxy to schedule a wake-up call. Expects time (HH:MM) and reason. Supports both 12h and 24h time formats. |
| POST | `/api/transcribe` | api/chat.py:238 | Transcribe audio to text using Gemini or OpenAI Whisper. Accepts audio files (webm, wav, mp3). |

### Job Hunter (`/api/v1/jobs`)

| Method | Route | File | Description |
|--------|-------|------|-------------|
| POST | `/api/v1/jobs/upload-resume` | api/jobs.py:38 | Upload and parse resume PDF. Extracts structured data for job applications. Max 16MB. |
| POST | `/api/v1/jobs/search-and-apply` | api/jobs.py:56 | Start job search and application workflow. Accepts query, max_applications, and filters. Runs asynchronously. Returns task_id for status polling. |
| GET | `/api/v1/jobs/status/{task_id}` | api/jobs.py:91 | Get the status of a job search background task. |

### Tab Manager (`/api/v1/tabs`)

| Method | Route | File | Description |
|--------|-------|------|-------------|
| POST | `/api/v1/tabs/organize` | api/tabs.py:106 | Organize Chrome tabs into AI-determined groups (Work, Social Media, Shopping, Research, Entertainment). Runs asynchronously. |
| POST | `/api/v1/tabs/close-old` | api/tabs.py:144 | Close old/stale Chrome tabs. Accepts `days_old` parameter (1-30, default: 7). Conservative approach - won't close important tabs. |
| POST | `/api/v1/tabs/merge-duplicates` | api/tabs.py:178 | Find and close duplicate Chrome tabs with the same URL. |
| GET | `/api/v1/tabs/list` | api/tabs.py:211 | Get a list of all currently open Chrome tabs with titles and URLs. |
| POST | `/api/v1/tabs/save-session` | api/tabs.py:228 | Save current Chrome tabs as a session for later restoration. Optional session name. |
| POST | `/api/v1/tabs/restore-session` | api/tabs.py:251 | Restore a previously saved tab session. Requires session_id. |
| GET | `/api/v1/tabs/sessions` | api/tabs.py:274 | List all saved tab sessions with names, tab counts, and creation dates. |
| DELETE | `/api/v1/tabs/sessions/{session_id}` | api/tabs.py:296 | Delete a saved session by ID. |
| GET | `/api/v1/tabs/status/{task_id}` | api/tabs.py:319 | Get the status of a tab management background task. Returns status, logs, and results. |

### Human-in-the-Loop (`/api/v1/hitl`)

| Method | Route | File | Description |
|--------|-------|------|-------------|
| GET | `/api/v1/hitl/pending` | api/hitl.py:36 | Get all pending HITL intervention requests. Optional task_id filter. |
| GET | `/api/v1/hitl/{request_id}` | api/hitl.py:55 | Get details of a specific HITL request including message, options, and status. |
| GET | `/api/v1/hitl/{request_id}/screenshot` | api/hitl.py:71 | Get the screenshot for a HITL request (base64 encoded). |
| POST | `/api/v1/hitl/{request_id}/respond` | api/hitl.py:87 | Respond to a HITL request. Actions: "Retry", "Abort", "I solved it", or custom action with custom_input. |
| DELETE | `/api/v1/hitl/{request_id}` | api/hitl.py:114 | Cancel a pending HITL request. |

### Active Interrupter - Wake-up Calls (`/api/v1/wake`)

| Method | Route | File | Description |
|--------|-------|------|-------------|
| POST | `/api/v1/wake/call-now` | api/wake.py:40 | Immediately trigger a wake-up call via Vapi. AI calls and verifies user is awake. Supports custom messages and verification questions. |
| POST | `/api/v1/wake/schedule` | api/wake.py:76 | Schedule a wake-up call for specific time. Supports device location-based timezone detection. Validates hour (0-23) and minute (0-59). |
| GET | `/api/v1/wake/location` | api/wake.py:117 | Get current location and timezone from Android device for timezone-aware scheduling. |
| DELETE | `/api/v1/wake/schedule/{job_id}` | api/wake.py:132 | Cancel a scheduled wake-up call by job ID. |

### Temporal Guardian - Alarms & Calendar (`/api/v1/alarms`)

| Method | Route | File | Description |
|--------|-------|------|-------------|
| POST | `/api/v1/alarms/set` | api/alarms.py:41 | Set an alarm on Android device using native intents. Validates hour (0-23) and minute (0-59). Optional label and recurring days. |
| DELETE | `/api/v1/alarms/cancel` | api/alarms.py:72 | Cancel all pending alarms (opens clock app for manual selection). |
| POST | `/api/v1/alarms/calendar/event` | api/alarms.py:84 | Schedule a calendar event. Opens calendar app and creates event with title, start_time, end_time, and description. |
| GET | `/api/v1/alarms/time` | api/alarms.py:104 | Get the current time from the connected Android device. |

---

## Job Hunter Dashboard (Flask)

**Base URL:** `http://localhost:5000`  
**Framework:** Flask (Python)  
**Location:** `/monorepo/apps/job-hunter/src/job_hunter/app.py`  
**Total Endpoints:** 9

### Applications

| Method | Route | File | Description |
|--------|-------|------|-------------|
| GET | `/api/applications/<user_id>` | app.py:32 | Get all job applications for a specific user from MongoDB. Returns applications array and count. |
| GET | `/api/applications/google-sheets` | app.py:49 | Get all applications from Google Sheets. Returns empty list if credentials not configured. |
| POST | `/api/applications/<user_id>/status` | app.py:77 | Update job application status. Updates both MongoDB and Google Sheets. Requires apply_link and status in request body. |

### User Preferences

| Method | Route | File | Description |
|--------|-------|------|-------------|
| GET | `/api/preferences/<user_id>` | app.py:109 | Get user job search preferences from MongoDB. |
| POST | `/api/preferences/<user_id>` | app.py:125 | Save user job search preferences to MongoDB. |

### Statistics

| Method | Route | File | Description |
|--------|-------|------|-------------|
| GET | `/api/stats/<user_id>` | app.py:142 | Get application statistics including total count, status breakdown, job types, locations, and recent applications. |

### File Upload

| Method | Route | File | Description |
|--------|-------|------|-------------|
| POST | `/api/upload-resume` | app.py:180 | Upload and process resume PDF. Starts job application process using JobApplicationOrchestrator. Requires 'resume' file and optional 'user_id' form field. |

### Job Portals

| Method | Route | File | Description |
|--------|-------|------|-------------|
| GET | `/api/job-portals` | app.py:226 | Get all configured job portals from MongoDB. |

### Pages

| Method | Route | File | Description |
|--------|-------|------|-------------|
| GET | `/` | app.py:26 | Home page with dashboard. Renders index.html template. |

---

## Response Formats

### Success Response (General)
```json
{
  "success": true,
  "message": "Operation completed successfully"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error description here"
}
```

### Chat Response
```json
{
  "response": "Response text from agent",
  "steps": ["step1", "step2"],
  "success": true
}
```

### Task Status Response (Background Jobs)
```json
{
  "task_id": "abc123",
  "status": "completed",
  "message": "Task completed",
  "result": {}
}
```

### Tab List Response
```json
{
  "tabs": [
    {
      "title": "Tab Title",
      "url": "https://example.com"
    }
  ],
  "count": 1
}
```

### HITL Request Response
```json
{
  "request_id": "uuid",
  "message": "Human assistance needed",
  "options": ["Retry", "Abort", "Custom"],
  "screenshot": "base64_encoded_string",
  "status": "pending",
  "created_at": "2026-01-19T12:00:00"
}
```

---

## Notes

### General
1. All endpoints return JSON responses
2. Most endpoints include a `success` boolean field
3. Error responses include an `error` string with the error message
4. Background tasks return a `task_id` that can be used to poll for status
5. CORS is enabled for localhost origins (3000, 5000, 8000)

### File Upload Constraints
- Resume uploads only accept PDF files (16MB max)
- Image uploads saved to `data/uploads` directory
- Audio transcription supports webm, wav, mp3 formats

### Authentication
- Currently no authentication required (development mode)
- Production deployment should add JWT/OAuth

### Rate Limiting
- No rate limiting currently implemented
- Consider adding for production deployment

### Background Tasks
- Use `/status/{task_id}` endpoints to poll for completion
- Tasks include: tab organization, job searches, AI processing
- Task statuses: `pending`, `running`, `completed`, `failed`

### External Dependencies
- **ADB:** Required for Android device control (alarms, wake calls)
- **Vapi:** Required for voice call functionality
- **MongoDB:** Required for Job Hunter app persistence
- **Google Sheets API:** Optional for job application tracking
- **Chrome/Chromium:** Required for tab management features

### Time Formats
- Wake calls and alarms support both 12h (e.g., "3:30 PM") and 24h (e.g., "15:30") formats
- Timezone detection uses Android device location when available
- Calendar events use ISO 8601 datetime format

### AI Agent Integration
- Chat endpoint routes to appropriate specialized agents
- Supports image context for visual understanding
- Personalization service learns from user interactions
- Tab manager uses AI for intelligent categorization

---

## Statistics Summary

**Total Endpoints:** 44
- **GET:** 17 endpoints
- **POST:** 22 endpoints
- **DELETE:** 5 endpoints

**By Functionality:**
- Health/Info: 2
- Chat & Transcription: 4
- Tab Management: 9
- Job Hunting (Gateway): 3
- Job Hunting (Flask): 9
- Human-in-the-Loop: 5
- Wake-up Calls: 4
- Alarms & Calendar: 4

**Technologies:**
- FastAPI (async/await)
- Flask (traditional routing)
- Pydantic validation
- MongoDB
- Google Sheets API
- ADB (Android Debug Bridge)
- Vapi (Voice API)
- AI/LLM integration
