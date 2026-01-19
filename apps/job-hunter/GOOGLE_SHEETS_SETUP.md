# Google Sheets Setup Guide

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name: "AI Job Hunter"
4. Click "Create"

## Step 2: Enable Google Sheets API

1. In the search bar, type "Google Sheets API"
2. Click on "Google Sheets API"
3. Click "Enable"

## Step 3: Create Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Fill in details:
   - Service account name: `ai-job-hunter`
   - Service account ID: `ai-job-hunter`
   - Description: "Service account for AI Job Hunter app"
4. Click "Create and Continue"
5. Grant role: "Editor" (or create custom role with Sheets permissions)
6. Click "Done"

## Step 4: Download Credentials

1. Click on the created service account
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Select "JSON"
5. Click "Create"
6. Save the downloaded file as `credentials.json` in your project root

## Step 5: Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com/)
2. Click "Blank" to create a new spreadsheet
3. Name it: "AI Job Hunter - Applications"
4. Copy the Spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
   ```
5. Paste this ID in your `.env` file as `GOOGLE_SHEETS_SPREADSHEET_ID`

## Step 6: Share Sheet with Service Account

1. Open the `credentials.json` file
2. Find the `client_email` field (looks like: `ai-job-hunter@project-id.iam.gserviceaccount.com`)
3. In your Google Sheet, click "Share"
4. Paste the service account email
5. Set permission to "Editor"
6. Uncheck "Notify people"
7. Click "Share"

## Step 7: Make Sheet Publicly Viewable (Optional)

If you want anyone to view the sheet:

1. Click "Share" button
2. Click "Change to anyone with the link"
3. Set to "Viewer"
4. Click "Done"

## Troubleshooting

### Error: "Permission denied"
- Ensure the service account email has Editor permissions on the sheet
- Check that the spreadsheet ID in `.env` is correct

### Error: "Credentials not found"
- Verify `credentials.json` is in the project root directory
- Check the file path in `.env` matches the actual location

### Error: "API not enabled"
- Go to Google Cloud Console
- Ensure Google Sheets API is enabled for your project

## Security Notes

- Never commit `credentials.json` to version control
- The `.gitignore` file is configured to exclude it
- Keep your service account email private
- Rotate credentials periodically
- Use least privilege principles (only grant necessary permissions)

## Example credentials.json structure

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "ai-job-hunter@your-project-id.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```
