
## UI Updates - January 20, 2026

### Frontend Cleanup
- [x] Remove Gateway Root, Wake location, and Alarm time from the web frontend in `apps/web/src/components/ChatArea.tsx`
- [x] Add keyboard shortcuts: Cmd+Shift+O (New Chat) and Cmd+Shift+S (Toggle Sidebar)
- [x] Add visual key binding hint to "New Chat" button
- [x] Replace Pin icon with Delete icon in Sidebar and implement thread deletion with persistence

## Review
I have implemented the requested key bindings:
1.  **New Chat**: `Cmd + Shift + O` triggers a new chat. Added a visual hint "⇧⌘O" to the New Chat button in the sidebar.
2.  **Toggle Sidebar**: `Cmd + Shift + S` toggles the sidebar visibility.
3.  **Delete Thread**: Replaced the Pin icon with a Trash icon for the active thread. Clicking it prompts for confirmation and then deletes the thread from both the state and local storage.

Changes were made in `apps/web/src/pages/Index.tsx` (event listeners, delete handler), `apps/web/src/hooks/useLocalThreads.ts` (delete logic), and `apps/web/src/components/Sidebar.tsx` (visual hint, delete button).
Verified the build with `npm run build`.

---

## Job Hunter Routing Fix - January 20, 2026

### Problem
1. "Job portals" quick action showed `{ "error": "Failed to fetch" }`
2. "Google Sheets apps" quick action showed `{ "error": "Failed to fetch" }`
3. Resume + "find me a job" was being routed incorrectly

### Root Cause
- The frontend `api.ts` was configured to route job-related API calls to `localhost:5000`
- But the actual job-hunter Flask server runs on `localhost:5123` (configured in `apps/job-hunter/src/job_hunter/config.py`)

### Fixes Applied
- [x] Fixed `JOB_HUNTER_BASE` port from `5000` to `5123` in `apps/web/src/lib/api.ts`
- [x] Changed "Google Sheets apps" action to open the Google Sheets URL directly in a new tab instead of making an API call

### Review

**Change 1: `apps/web/src/lib/api.ts` (line 4)**
```typescript
// Before
const JOB_HUNTER_BASE = "http://localhost:5000";

// After
const JOB_HUNTER_BASE = "http://localhost:5123";
```
This ensures all job-related API calls (`/api/job-portals`, `/api/applications/*`, `/api/preferences/*`, etc.) are routed to the correct port where the Flask job-hunter server is actually running.

**Change 2: `apps/web/src/components/ChatArea.tsx` (line 116)**
```typescript
// Before
{ id: "applications-sheets", label: "Google Sheets apps", category: "jobs", onRun: () => api.applicationsSheets() }

// After
{ 
  id: "applications-sheets", 
  label: "Google Sheets apps", 
  category: "jobs", 
  onRun: () => {
    window.open("https://docs.google.com/spreadsheets/d/1FupoVr33rLLIOtRrlYxFjXvlMqules-_49pVJcrdgx4/edit", "_blank");
    return Promise.resolve({ success: true, message: "Opened Google Sheets in new tab" });
  }
}
```
Instead of making an API call that may fail, this directly opens the Google Sheets document in a new tab. The user wanted to see their job applications tracked in this spreadsheet.

### Build Verification
Verified build with `npm run build` - completed successfully with no errors.

---

## Additional Job Hunter & Gateway Fixes - January 20, 2026

### Problems Identified
1. "Job portals" still showing `{ "error": "Failed to fetch" }` - **CORS issue**
2. Resume + "find me a job" causing validation error: `Input should be a valid dictionary or instance of StepInfo`
3. Job-related intents not being routed from Gateway to Job Hunter service

### Root Causes
1. **CORS Issue**: The Job Hunter Flask app (`localhost:5123`) had no CORS headers, so browser blocked cross-origin requests from frontend (`localhost:3000`)
2. **Validation Error**: `ChatResponse.steps` expected `list[StepInfo]` but agent returned raw strings from `summary_history`
3. **Missing Intent Router**: Gateway's `/api/chat` didn't detect job-related commands to forward to Job Hunter

### Fixes Applied
- [x] Added Flask-CORS to Job Hunter Flask app (`apps/job-hunter/src/job_hunter/app.py`)
- [x] Added `flask-cors>=5.0.0` dependency to `apps/job-hunter/pyproject.toml`
- [x] Created `_normalize_steps()` function to convert raw strings/dicts to `StepInfo` objects
- [x] Added job intent detection in Gateway's chat handler with keywords: `job, apply, resume, career, employment, hire, position, find me a`
- [x] Created `_handle_job_hunting()` function that proxies resume uploads to Job Hunter service

### Files Modified

**1. `apps/job-hunter/src/job_hunter/app.py`**
```python
# Added CORS support
from flask_cors import CORS

# ... after app creation ...
CORS(app, origins=[
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:3002",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8000",
    "http://localhost:8080",
])
```

**2. `apps/job-hunter/pyproject.toml`**
```toml
dependencies = [
    ...
    "flask-cors>=5.0.0",  # NEW
    ...
]
```

**3. `apps/gateway/src/ironclaw/api/chat.py`**
- Added `_normalize_steps()` function (lines 47-92) that converts various step formats to `StepInfo` objects
- Updated all `ChatResponse` returns to use `_normalize_steps()`
- Added job intent detection (lines 177-194)
- Added `_handle_job_hunting()` function (lines 521-590) that:
  - Detects if a PDF resume was recently uploaded
  - Forwards the resume to Job Hunter's `/api/upload-resume` endpoint via httpx
  - Returns appropriate success/error messages with normalized steps

### How It Works Now

1. **User clicks "Job portals"** → Frontend calls `GET /api/job-portals` → Routed to Flask at `localhost:5123` → CORS headers allow response → User sees job portal list

2. **User uploads resume.pdf + types "find me a job"** → Gateway receives at `POST /api/chat` → Job intent detected → `_handle_job_hunting()` called → Resume forwarded to Job Hunter Flask → Job Hunter parses resume and starts automation

3. **User clicks "Google Sheets apps"** → Opens `https://docs.google.com/spreadsheets/d/1FupoVr33rLLIOtRrlYxFjXvlMqules-_49pVJcrdgx4/edit` in new tab

### Architecture Flow

```
Frontend (localhost:3000)
    │
    ├──▶ Job Portals → GET /api/job-portals ──▶ Job Hunter Flask (localhost:5123)
    │                                                ↓
    │                                           MongoDB query
    │
    ├──▶ "find me a job" + resume.pdf → POST /api/chat ──▶ Gateway (localhost:8000)
    │                                                          │
    │                                                          ▼
    │                                                  Job intent detected?
    │                                                     YES → _handle_job_hunting()
    │                                                              │
    │                                                              ▼
    │                                                  POST /api/upload-resume
    │                                                  to Job Hunter Flask
    │                                                              │
    │                                                              ▼
    │                                              Job orchestrator starts automation
    │
    └──▶ Google Sheets apps → Opens spreadsheet URL in new tab
```

### Security Considerations
- CORS is restricted to specific localhost ports (development only)
- For production, CORS origins should be configured via environment variables
- Resume uploads are validated (PDF only, max 16MB)
- No sensitive data exposed in API responses
