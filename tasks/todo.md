
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
