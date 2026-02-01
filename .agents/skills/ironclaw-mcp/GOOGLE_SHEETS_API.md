# Google Sheets Integration for ClawdBot/OpenClaw

This document describes how to use the Google Sheets API endpoint to add job application entries from ClawdBot/OpenClaw.

## Overview

The endpoint allows ClawdBot to append job application data to a Google Sheet for tracking purposes. After successfully applying to a job on mobile, ClawdBot can call this endpoint to record the application.

## Prerequisites

### 1. Environment Variables

Add these to your `.env` file in the monorepo root:

```bash
# Google Sheets Configuration
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
```

### 2. Credentials File

Place your Google Service Account credentials file (`credentials.json`) in the monorepo root. See [apps/job-hunter/GOOGLE_SHEETS_SETUP.md](../../apps/job-hunter/GOOGLE_SHEETS_SETUP.md) for detailed setup instructions.

### 3. Sheet Structure

Your Google Sheet must have these columns in the header row:

| Column | Header |
|--------|--------|
| A | Company |
| B | Job Title |
| C | Apply Link |
| D | Date Applied |
| E | Deadline |
| F | Salary |
| G | Job Type |
| H | Contact |
| I | Location |
| J | Status |

## API Endpoints

### Base URL
```
http://ironclaw.snipermonkey.in/api/v1/sheets
```

---

### 1. Append Single Entry

**Endpoint:** `POST /api/v1/sheets/append`

Add a single job application entry to the sheet.

#### Request Body

```json
{
  "entry": {
    "company": "Google",
    "job_title": "Software Engineer",
    "apply_link": "https://careers.google.com/jobs/123",
    "date_applied": "2026-02-02",
    "deadline": "2026-02-15",
    "salary": "$150,000 - $200,000",
    "job_type": "Full-time",
    "contact": "recruiter@google.com",
    "location": "Mountain View, CA",
    "status": "Applied"
  }
}
```

#### Required Fields
- `company` (string): Company name
- `job_title` (string): Job title/position

#### Optional Fields
- `apply_link` (string): URL to the job posting
- `date_applied` (string): Date in YYYY-MM-DD format. Defaults to today.
- `deadline` (string): Application deadline
- `salary` (string): Salary/compensation info
- `job_type` (string): Full-time, Part-time, Contract, etc.
- `contact` (string): Recruiter or contact info
- `location` (string): Job location
- `status` (string): Application status. Defaults to "Applied"

#### Example cURL

```bash
curl -X POST http://ironclaw.snipermonkey.in/api/v1/sheets/append \
  -H "Content-Type: application/json" \
  -d '{
    "entry": {
      "company": "Twixor",
      "job_title": "Tech Lead (Full Stack Developer)",
      "apply_link": "https://linkedin.com/jobs/view/123",
      "location": "Bengaluru, Karnataka, India (On-site)",
      "status": "Applied"
    }
  }'
```

#### Response

```json
{
  "success": true,
  "message": "Successfully added application for Tech Lead (Full Stack Developer) at Twixor",
  "rows_added": 1,
  "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit"
}
```

---

### 2. Bulk Append Multiple Entries

**Endpoint:** `POST /api/v1/sheets/bulk-append`

Add multiple job applications at once.

#### Request Body

```json
{
  "entries": [
    {
      "company": "Google",
      "job_title": "Software Engineer",
      "location": "Mountain View, CA",
      "status": "Applied"
    },
    {
      "company": "Meta",
      "job_title": "Frontend Developer",
      "location": "Menlo Park, CA",
      "status": "Applied"
    }
  ]
}
```

#### Example cURL

```bash
curl -X POST http://ironclaw.snipermonkey.in/api/v1/sheets/bulk-append \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [
      {"company": "Google", "job_title": "SWE", "status": "Applied"},
      {"company": "Meta", "job_title": "FE Dev", "status": "Applied"}
    ]
  }'
```

#### Response

```json
{
  "success": true,
  "message": "Successfully added 2 job applications",
  "rows_added": 2,
  "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit"
}
```

---

### 3. Get All Applications

**Endpoint:** `GET /api/v1/sheets/applications`

Retrieve all job applications from the sheet.

#### Example cURL

```bash
curl http://ironclaw.snipermonkey.in/api/v1/sheets/applications
```

#### Response

```json
{
  "success": true,
  "applications": [
    {
      "company": "Twixor",
      "job_title": "Tech Lead (Full Stack Developer)",
      "apply_link": "",
      "date_applied": "2026-01-19",
      "deadline": "Be an early applicant",
      "salary": "",
      "job_type": "",
      "contact": "",
      "location": "Bengaluru, Karnataka, India (On-site)",
      "status": "Applied"
    }
  ],
  "count": 1,
  "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit"
}
```

---

### 4. Get Sheet URL

**Endpoint:** `GET /api/v1/sheets/url`

Get the URL of the Google Sheet.

#### Example cURL

```bash
curl http://ironclaw.snipermonkey.in/api/v1/sheets/url
```

#### Response

```json
{
  "url": "https://docs.google.com/spreadsheets/d/abc123/edit"
}
```

---

## MCP Tool Usage

If using the Iron Claw MCP server, the following tools are available:

### `ironclaw_sheets_append`
Append a single job application entry.

```json
{
  "name": "ironclaw_sheets_append",
  "arguments": {
    "entry": {
      "company": "Google",
      "job_title": "Software Engineer",
      "status": "Applied"
    }
  }
}
```

### `ironclaw_sheets_bulk_append`
Append multiple entries at once.

### `ironclaw_sheets_get_applications`
Get all applications from the sheet.

### `ironclaw_sheets_url`
Get the Google Sheet URL.

---

## Error Handling

### Common Errors

| Status Code | Error | Solution |
|-------------|-------|----------|
| 500 | Credentials not found | Ensure `credentials.json` exists and `GOOGLE_SHEETS_CREDENTIALS_FILE` is set |
| 500 | GOOGLE_SHEETS_SPREADSHEET_ID not set | Add the spreadsheet ID to your `.env` file |
| 500 | Google Sheets API error | Check that the service account has Editor access to the sheet |

---

## Status Values

Recommended status values for tracking:
- `Applied` - Application submitted
- `Interview` - Interview scheduled or completed
- `Offer` - Received job offer
- `Rejected` - Application rejected
- `Withdrawn` - Withdrew application
- `Follow-up` - Need to follow up

---

## Integration with ClawdBot

When ClawdBot applies to a job on mobile, it should:

1. Complete the job application on the device
2. Call the `/api/v1/sheets/append` endpoint with the job details
3. Check the response for success

Example workflow in ClawdBot:
```
1. Open LinkedIn
2. Search for "Software Engineer"
3. Click on job posting
4. Apply to job
5. ✅ Call ironclaw_sheets_append with job details
6. Move to next job
```

---

## Need Help?

- Google Sheets setup: [apps/job-hunter/GOOGLE_SHEETS_SETUP.md](../../apps/job-hunter/GOOGLE_SHEETS_SETUP.md)
- Troubleshooting: [apps/job-hunter/TROUBLESHOOTING.md](../../apps/job-hunter/TROUBLESHOOTING.md)
