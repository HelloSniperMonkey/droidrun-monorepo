"""
Google Sheets API endpoints for ClawdBot/OpenClaw integration.
Allows appending job application data to Google Sheets.
"""
import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..utils.config import MONOREPO_ROOT

logger = logging.getLogger("ironclaw.api.google_sheets")
router = APIRouter()

# Google Sheets Configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Sheet headers (must match the existing sheet structure)
HEADERS = [
    'Company',
    'Job Title', 
    'Apply Link',
    'Date Applied',
    'Deadline',
    'Salary',
    'Job Type',
    'Contact',
    'Location',
    'Status'
]


class JobApplicationEntry(BaseModel):
    """Model for a single job application entry."""
    company: str = Field(..., description="Company name")
    job_title: str = Field(..., description="Job title/position")
    apply_link: Optional[str] = Field(default="", description="URL to the job posting/application")
    date_applied: Optional[str] = Field(default=None, description="Date applied (YYYY-MM-DD format). Defaults to today.")
    deadline: Optional[str] = Field(default="", description="Application deadline")
    salary: Optional[str] = Field(default="", description="Salary/compensation information")
    job_type: Optional[str] = Field(default="", description="Job type (Full-time, Part-time, Contract, etc.)")
    contact: Optional[str] = Field(default="", description="Contact person or recruiter info")
    location: Optional[str] = Field(default="", description="Job location")
    status: Optional[str] = Field(default="Applied", description="Application status (Applied, Interview, Rejected, etc.)")


class AppendRowRequest(BaseModel):
    """Request model for appending a single row."""
    entry: JobApplicationEntry


class BulkAppendRequest(BaseModel):
    """Request model for appending multiple rows at once."""
    entries: List[JobApplicationEntry]


class AppendResponse(BaseModel):
    """Response model for append operations."""
    success: bool
    message: str
    rows_added: int = 0
    sheet_url: Optional[str] = None


class GetApplicationsResponse(BaseModel):
    """Response model for getting applications."""
    success: bool
    applications: List[dict] = []
    count: int = 0
    sheet_url: Optional[str] = None
    error: Optional[str] = None


def _get_credentials_path() -> str:
    """Get the path to the credentials file."""
    # Check environment variable first
    creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
    if creds_path:
        if os.path.isabs(creds_path):
            return creds_path
        return str(MONOREPO_ROOT / creds_path)
    
    # Default locations to check
    default_paths = [
        MONOREPO_ROOT / "credentials.json",
        MONOREPO_ROOT / "credential.json",
        MONOREPO_ROOT / "apps" / "job-hunter" / "credentials.json",
    ]
    
    for path in default_paths:
        if path.exists():
            return str(path)
    
    raise FileNotFoundError(
        "Google Sheets credentials file not found. "
        "Set GOOGLE_SHEETS_CREDENTIALS_FILE env var or place credentials.json in monorepo root."
    )


def _get_spreadsheet_id() -> str:
    """Get the spreadsheet ID from environment."""
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ValueError(
            "GOOGLE_SHEETS_SPREADSHEET_ID environment variable is not set. "
            "Please add it to your .env file."
        )
    return spreadsheet_id


def _get_sheets_service():
    """Create and return a Google Sheets service instance."""
    creds_path = _get_credentials_path()
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service


def _get_sheet_url() -> str:
    """Get the URL of the Google Sheet."""
    return f"https://docs.google.com/spreadsheets/d/{_get_spreadsheet_id()}/edit"


@router.post("/append", response_model=AppendResponse)
async def append_job_application(request: AppendRowRequest):
    """
    Append a single job application entry to the Google Sheet.
    
    This endpoint is designed for ClawdBot/OpenClaw to add job applications
    after successfully applying to jobs on mobile.
    """
    try:
        service = _get_sheets_service()
        spreadsheet_id = _get_spreadsheet_id()
        
        entry = request.entry
        
        # Prepare row data
        row = [
            entry.company,
            entry.job_title,
            entry.apply_link or "",
            entry.date_applied or datetime.now().strftime('%Y-%m-%d'),
            entry.deadline or "",
            entry.salary or "",
            entry.job_type or "",
            entry.contact or "",
            entry.location or "",
            entry.status or "Applied"
        ]
        
        # Append to sheet
        body = {'values': [row]}
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A:J',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        logger.info(f"Added job application: {entry.company} - {entry.job_title}")
        
        return AppendResponse(
            success=True,
            message=f"Successfully added application for {entry.job_title} at {entry.company}",
            rows_added=1,
            sheet_url=_get_sheet_url()
        )
        
    except FileNotFoundError as e:
        logger.error(f"Credentials not found: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except HttpError as e:
        logger.error(f"Google Sheets API error: {e}")
        raise HTTPException(status_code=500, detail=f"Google Sheets API error: {e.reason}")
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-append", response_model=AppendResponse)
async def bulk_append_job_applications(request: BulkAppendRequest):
    """
    Append multiple job application entries to the Google Sheet at once.
    
    More efficient than calling /append multiple times.
    """
    try:
        service = _get_sheets_service()
        spreadsheet_id = _get_spreadsheet_id()
        
        rows = []
        for entry in request.entries:
            row = [
                entry.company,
                entry.job_title,
                entry.apply_link or "",
                entry.date_applied or datetime.now().strftime('%Y-%m-%d'),
                entry.deadline or "",
                entry.salary or "",
                entry.job_type or "",
                entry.contact or "",
                entry.location or "",
                entry.status or "Applied"
            ]
            rows.append(row)
        
        body = {'values': rows}
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A:J',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        logger.info(f"Bulk added {len(rows)} job applications")
        
        return AppendResponse(
            success=True,
            message=f"Successfully added {len(rows)} job applications",
            rows_added=len(rows),
            sheet_url=_get_sheet_url()
        )
        
    except FileNotFoundError as e:
        logger.error(f"Credentials not found: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except HttpError as e:
        logger.error(f"Google Sheets API error: {e}")
        raise HTTPException(status_code=500, detail=f"Google Sheets API error: {e.reason}")
    except Exception as e:
        logger.error(f"Error bulk appending to sheet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/applications", response_model=GetApplicationsResponse)
async def get_all_applications():
    """
    Get all job applications from the Google Sheet.
    
    Returns a list of all applications with their details.
    """
    try:
        service = _get_sheets_service()
        spreadsheet_id = _get_spreadsheet_id()
        
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range='A2:J'  # Skip header row
        ).execute()
        
        values = result.get('values', [])
        
        applications = []
        for row in values:
            # Ensure row has enough columns
            while len(row) < len(HEADERS):
                row.append('')
            
            app = {
                'company': row[0],
                'job_title': row[1],
                'apply_link': row[2],
                'date_applied': row[3],
                'deadline': row[4],
                'salary': row[5],
                'job_type': row[6],
                'contact': row[7],
                'location': row[8],
                'status': row[9]
            }
            applications.append(app)
        
        return GetApplicationsResponse(
            success=True,
            applications=applications,
            count=len(applications),
            sheet_url=_get_sheet_url()
        )
        
    except FileNotFoundError as e:
        logger.error(f"Credentials not found: {e}")
        return GetApplicationsResponse(success=False, error=str(e))
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return GetApplicationsResponse(success=False, error=str(e))
    except HttpError as e:
        logger.error(f"Google Sheets API error: {e}")
        return GetApplicationsResponse(success=False, error=f"Google Sheets API error: {e.reason}")
    except Exception as e:
        logger.error(f"Error getting applications: {e}")
        return GetApplicationsResponse(success=False, error=str(e))


@router.get("/url")
async def get_sheet_url():
    """
    Get the URL of the Google Sheet.
    """
    try:
        return {"url": _get_sheet_url()}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
