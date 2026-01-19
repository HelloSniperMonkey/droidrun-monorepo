# AI Job Hunter 🤖

Automated job application system powered by **MobileRun AI** that parses your resume, finds relevant job positions, and applies to them automatically using a smartphone (organic traffic pattern).

## Features

✅ **AI-Powered Resume Parsing** - Extracts relevant information using OpenRouter (FREE) or Anthropic  
✅ **Automated Job Search** - Searches across multiple job portals  
✅ **Smart Application** - Applies to jobs using MobileRun Cloud (smartphone automation)  
✅ **Quota Management** - Stops based on steps executed or minimum jobs applied  
✅ **MongoDB Storage** - Stores job portals, user preferences, and application history  
✅ **Google Sheets Integration** - Tracks all applications with public access  
✅ **User Preference Memory** - Remembers answers to repetitive questions  
✅ **Human-in-the-Loop** - Pauses for clarification and CAPTCHA solving  
✅ **Web Dashboard** - Beautiful UI to view and manage applications  
✅ **DroidRun Backup** - Local backup system using DroidRun framework  

## Architecture

- **Primary**: MobileRun Cloud API (smartphone-based automation for organic traffic)
- **Backup**: DroidRun framework (local laptop/server)
- **Database**: MongoDB (job portals, user preferences, application history)
- **Tracking**: Google Sheets API (public job application tracking)
- **Resume Parsing**: OpenRouter (openai/gpt-oss-120b:free) or Anthropic Claude
- **Web App**: Flask with responsive HTML/CSS/JavaScript

## Installation

### Prerequisites

- Python 3.12+
- MongoDB installed and running
- Google Cloud service account with Sheets API enabled
- MobileRun API key
- OpenRouter API key (FREE at https://openrouter.ai/) or Anthropic API key

### Setup

1. **Navigate to the project** (from monorepo root):
```bash
cd apps/job-hunter
```

2. **Install dependencies with uv**:
```bash
uv sync
```

3. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

4. **Set up Google Sheets**:
   - Create a Google Cloud project
   - Enable Google Sheets API
   - Create a service account and download credentials JSON
   - Save as `credentials.json` in the project root
   - Create a new Google Sheet
   - Share it with the service account email (editor permissions)
   - Copy the spreadsheet ID from the URL

5. **Start MongoDB** (if not already running):
```bash
# macOS with Homebrew
brew services start mongodb-community

# Or use Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

## Usage

### Web Mode (Recommended)

Start the web application:
```bash
uv run python main.py web
```

Then open your browser to `http://localhost:5123`

**Features:**
- Upload resume via drag & drop
- View all applications in a table
- Filter by status, job type, or search
- Real-time statistics dashboard
- Automatic refresh from Google Sheets

### CLI Mode

Apply to jobs directly from command line:
```bash
uv run python main.py apply path/to/resume.pdf --user-id john.doe@email.com
```

## Configuration

Edit `.env` file:

```env
# MobileRun API
MOBILERUN_API_KEY=your_key_here

# MongoDB
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=ai_job_hunter

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_sheet_id

# AI for Resume Parsing
OPENAI_API_KEY=your_openai_key
# or
ANTHROPIC_API_KEY=your_anthropic_key

# Quota Management
MAX_STEPS_QUOTA=100        # Maximum agent steps
MIN_JOBS_APPLIED=10        # Minimum jobs to apply to

# Agent Settings
LLM_MODEL=google/gemini-2.5-flash
AGENT_EXECUTION_TIMEOUT=300
AGENT_TEMPERATURE=0.5
```

## How It Works

1. **Resume Upload**: User uploads resume PDF
2. **AI Parsing**: Resume is parsed using GPT-4o-mini/Claude to extract:
   - Personal info (name, email, phone, location)
   - Skills, experience, education
   - Preferred job roles
3. **User Preferences**: First-time setup for repetitive questions:
   - Visa status
   - Sponsorship requirements
   - Relocation willingness
   - Work authorization
4. **Job Search**: Agent searches for jobs across:
   - Predefined job portals (LinkedIn, Indeed, Glassdoor, etc.)
   - Google search for additional opportunities
   - New portals are added to MongoDB automatically
5. **Job Application**: For each relevant job:
   - Check if already applied (MongoDB + Google Sheets)
   - Use MobileRun Cloud to fill application on smartphone
   - Handle questions using resume data + user preferences
   - Pause for clarification if needed
   - Pause for CAPTCHA (human intervention)
   - Record in MongoDB + Google Sheets
6. **Quota Management**: Stops when either:
   - Maximum steps reached (default: 100)
   - Minimum jobs applied (default: 10)
7. **Dashboard**: View all applications in web interface

## Project Structure

```
apps/job-hunter/
├── main.py                    # Entry point (CLI/Web)
├── src/job_hunter/
│   ├── __init__.py
│   ├── config.py             # Configuration management
│   ├── resume_parser.py      # AI resume parsing
│   ├── mobilerun_agent.py    # MobileRun Cloud API client
│   ├── database.py           # MongoDB operations
│   ├── google_sheets.py      # Google Sheets integration
│   ├── orchestrator.py       # Main workflow orchestration
│   ├── app.py                # Flask web application
│   ├── main.py               # Package entry point
│   ├── droidrun_backup.py    # DroidRun backup integration
│   └── templates/
│       └── index.html        # Web dashboard
├── data/uploads/             # Uploaded resumes
├── examples.py               # Example usage scripts
├── .env                      # Environment variables
├── .env.example              # Environment template
├── credentials.json          # Google service account credentials
├── pyproject.toml            # Python dependencies
└── README.md                 # This file
```

## Google Sheets Structure

The application creates a Google Sheet with the following columns:

| Company | Job Title | Apply Link | Date Applied | Deadline | Salary | Job Type | Contact | Location | Status |
|---------|-----------|------------|--------------|----------|--------|----------|---------|----------|--------|

**Status values**: Applied, Interview, Offer, Rejected

## MongoDB Collections

- **job_portals**: URLs and stats for job portals
- **user_preferences**: Stored answers to repetitive questions
- **application_history**: Complete application records
- **job_listings**: Cached job listings to avoid duplicates

## API Endpoints

- `GET /` - Dashboard home page
- `GET /api/applications/<user_id>` - Get user applications from MongoDB
- `GET /api/applications/google-sheets` - Get applications from Google Sheets
- `POST /api/applications/<user_id>/status` - Update application status
- `GET /api/preferences/<user_id>` - Get user preferences
- `POST /api/preferences/<user_id>` - Save user preferences
- `GET /api/stats/<user_id>` - Get application statistics
- `POST /api/upload-resume` - Upload resume and start job hunt
- `GET /api/job-portals` - Get all job portals

## DroidRun Backup Setup

For local backup automation (when MobileRun Cloud is unavailable):

```bash
# Install DroidRun
pip install 'droidrun[google,anthropic,openai,deepseek,ollama,dev]'

# Connect Android device via ADB
# Follow instructions at: https://docs.droidrun.ai/
```

## Troubleshooting

### MongoDB Connection Error
```bash
# Check if MongoDB is running
brew services list | grep mongodb

# Start MongoDB
brew services start mongodb-community
```

### Google Sheets Permission Denied
- Ensure the service account email has editor permissions on the sheet
- Check that the spreadsheet ID in `.env` is correct

### MobileRun API Error
- Verify your API key is correct
- Check API quota/limits at https://mobilerun.ai/

### Resume Parsing Error
- Ensure PDF is text-based (not scanned image)
- Check OpenAI/Anthropic API key is valid

## Contributing

Contributions are welcome! Areas for improvement:

- [ ] Add support for more job portals
- [ ] Implement CAPTCHA solving automation
- [ ] Add email notifications
- [ ] Support resume upload in other formats (DOCX, TXT)
- [ ] Add application status tracking via email parsing
- [ ] Implement retry logic for failed applications
- [ ] Add multi-language support

## License

MIT License

## Acknowledgments

- [MobileRun AI](https://mobilerun.ai/) - Smartphone automation platform
- [DroidRun](https://github.com/droidrun/droidrun) - Mobile device control framework
- OpenAI & Anthropic - AI models for resume parsing

## Support

For issues and questions:
- MobileRun Docs: https://docs.mobilerun.ai/
- DroidRun Docs: https://docs.droidrun.ai/
- Discord: https://discord.gg/droidrun

---

Built with ❤️ for job seekers everywhere
