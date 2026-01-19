"""Google Sheets integration for tracking job applications"""
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Optional
from datetime import datetime
from job_hunter.config import Config


class GoogleSheetsManager:
    """Manage job applications in Google Sheets"""

    # Define the required scopes
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    # Sheet headers
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

    def __init__(self, credentials_file: Optional[str] = None, spreadsheet_id: Optional[str] = None):
        """
        Initialize Google Sheets manager

        Args:
            credentials_file: Path to Google service account credentials JSON
            spreadsheet_id: Google Sheets spreadsheet ID
        """
        self.credentials_file = credentials_file or Config.GOOGLE_SHEETS_CREDENTIALS_FILE
        self.spreadsheet_id = spreadsheet_id or Config.GOOGLE_SHEETS_SPREADSHEET_ID

        # Authenticate and build service
        self.service = self._authenticate()

        # Ensure sheet is initialized
        self._initialize_sheet()

    def _authenticate(self):
        """Authenticate with Google Sheets API"""
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.SCOPES
            )
            service = build('sheets', 'v4', credentials=creds)
            return service
        except Exception as e:
            raise Exception(f"Failed to authenticate with Google Sheets: {str(e)}")

    def _initialize_sheet(self):
        """Initialize the sheet with headers if it doesn't exist"""
        try:
            # Try to read the first row
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A1:J1'
            ).execute()

            values = result.get('values', [])

            # If no headers, add them
            if not values or values[0] != self.HEADERS:
                self._write_headers()
        except HttpError as e:
            if e.resp.status == 404:
                raise Exception(f"Spreadsheet not found: {self.spreadsheet_id}")
            raise Exception(f"Error initializing sheet: {str(e)}")

    def _write_headers(self):
        """Write headers to the sheet"""
        body = {
            'values': [self.HEADERS]
        }

        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range='A1:J1',
            valueInputOption='RAW',
            body=body
        ).execute()

        # Format header row (bold)
        requests = [{
            'repeatCell': {
                'range': {
                    'sheetId': 0,
                    'startRowIndex': 0,
                    'endRowIndex': 1
                },
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {
                            'bold': True
                        }
                    }
                },
                'fields': 'userEnteredFormat.textFormat.bold'
            }
        }]

        body = {'requests': requests}
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body=body
        ).execute()

    def add_application(self, application_data: Dict) -> bool:
        """
        Add a job application to the Google Sheet

        Args:
            application_data: Dictionary with application details

        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare row data
            row = [
                application_data.get('company', ''),
                application_data.get('job_title', ''),
                application_data.get('apply_link', ''),
                application_data.get('date_applied', datetime.now().strftime('%Y-%m-%d')),
                application_data.get('deadline', ''),
                application_data.get('salary', ''),
                application_data.get('job_type', ''),
                application_data.get('contact', ''),
                application_data.get('location', ''),
                application_data.get('status', 'Applied')
            ]

            # Append to sheet
            body = {
                'values': [row]
            }

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='A:J',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            return True
        except Exception as e:
            print(f"Error adding application to Google Sheets: {str(e)}")
            return False

    def get_all_applications(self) -> List[Dict]:
        """
        Retrieve all applications from the Google Sheet

        Returns:
            List of application dictionaries
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A2:J'  # Skip header row
            ).execute()

            values = result.get('values', [])

            applications = []
            for row in values:
                # Ensure row has enough columns
                while len(row) < len(self.HEADERS):
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

            return applications
        except Exception as e:
            print(f"Error retrieving applications from Google Sheets: {str(e)}")
            return []

    def update_application_status(self, apply_link: str, new_status: str) -> bool:
        """
        Update the status of an application

        Args:
            apply_link: The application link to identify the row
            new_status: New status value

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get all applications
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A2:J'
            ).execute()

            values = result.get('values', [])

            # Find the row with matching apply_link
            for idx, row in enumerate(values, start=2):  # Start from row 2 (after header)
                if len(row) > 2 and row[2] == apply_link:
                    # Update status (column J)
                    range_to_update = f'J{idx}'
                    body = {
                        'values': [[new_status]]
                    }

                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_to_update,
                        valueInputOption='RAW',
                        body=body
                    ).execute()

                    return True

            return False  # Application not found
        except Exception as e:
            print(f"Error updating application status: {str(e)}")
            return False

    def check_if_applied(self, apply_link: str) -> bool:
        """
        Check if already applied to a job

        Args:
            apply_link: The application link to check

        Returns:
            True if already applied, False otherwise
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='C2:C'  # Column C contains apply links
            ).execute()

            values = result.get('values', [])
            apply_links = [row[0] for row in values if row]

            return apply_link in apply_links
        except Exception as e:
            print(f"Error checking application: {str(e)}")
            return False

    def bulk_add_applications(self, applications: List[Dict]) -> int:
        """
        Add multiple applications at once

        Args:
            applications: List of application dictionaries

        Returns:
            Number of successfully added applications
        """
        try:
            rows = []
            for app in applications:
                row = [
                    app.get('company', ''),
                    app.get('job_title', ''),
                    app.get('apply_link', ''),
                    app.get('date_applied', datetime.now().strftime('%Y-%m-%d')),
                    app.get('deadline', ''),
                    app.get('salary', ''),
                    app.get('job_type', ''),
                    app.get('contact', ''),
                    app.get('location', ''),
                    app.get('status', 'Applied')
                ]
                rows.append(row)

            body = {
                'values': rows
            }

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='A:J',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            return len(rows)
        except Exception as e:
            print(f"Error bulk adding applications: {str(e)}")
            return 0

    def get_sheet_url(self) -> str:
        """Get the URL of the Google Sheet"""
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
