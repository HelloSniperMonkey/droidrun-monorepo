# Troubleshooting Guide

Common issues and solutions for AI Job Hunter

## Installation Issues

### uv not found
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Verify installation
uv --version
```

### MongoDB not running
```bash
# macOS with Homebrew
brew services start mongodb-community

# Check if running
brew services list | grep mongodb

# Or use Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Verify connection
mongosh --eval "db.version()"
```

### Python version mismatch
```bash
# Check Python version (need 3.12+)
python --version

# Install Python 3.12 on macOS
brew install python@3.12

# Use specific version with uv
uv python install 3.12
```

## Configuration Issues

### Missing environment variables
```bash
# Verify .env file exists
ls -la .env

# Check required variables
cat .env | grep -E "MOBILERUN_API_KEY|OPENAI_API_KEY|GOOGLE_SHEETS"

# If missing, copy from template
cp .env.example .env
```

### Invalid API keys
```bash
# Test MobileRun API key
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.mobilerun.ai/v1/tasks

# Test OpenAI API key
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.openai.com/v1/models

# Check if keys are properly set in .env
python -c "from src.config import Config; print('MobileRun:', bool(Config.MOBILERUN_API_KEY))"
```

### Google Sheets permission denied
```bash
# Check credentials file exists
ls -la credentials.json

# Verify service account email
cat credentials.json | grep client_email

# Steps to fix:
# 1. Open your Google Sheet
# 2. Click "Share"
# 3. Add the service account email
# 4. Set permission to "Editor"
# 5. Uncheck "Notify people"
```

## Runtime Issues

### Import errors
```bash
# Reinstall dependencies
uv sync

# Or manually install missing package
uv add package-name

# Activate virtual environment
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows
```

### MongoDB connection error
```bash
# Error: MongoServerSelectionTimeoutError

# Check MongoDB is running
pgrep -x mongod

# Check connection string in .env
# Default: mongodb://localhost:27017/

# Test connection
python -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017/').server_info()"
```

### Google Sheets API error
```bash
# Error: Credentials not found

# Verify file path
ls -la credentials.json

# Check GOOGLE_SHEETS_CREDENTIALS_FILE in .env
cat .env | grep GOOGLE_SHEETS_CREDENTIALS_FILE

# Re-download credentials from Google Cloud Console
# https://console.cloud.google.com/

# Error: Sheet not found

# Verify spreadsheet ID
# Open your sheet and copy ID from URL:
# https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit

# Update .env
# GOOGLE_SHEETS_SPREADSHEET_ID=your_actual_id
```

### MobileRun API errors
```bash
# Error: Invalid API key
# - Check MOBILERUN_API_KEY in .env
# - Ensure no extra spaces or quotes
# - Verify key hasn't been revoked

# Error: Rate limit exceeded
# - Wait before making more requests
# - Reduce MAX_STEPS_QUOTA in .env
# - Use slower LLM models

# Error: Insufficient credits
# - Add credits to your MobileRun account
# - Check account balance at https://cloud.mobilerun.ai/
```

### Resume parsing errors
```bash
# Error: No text extracted from PDF

# Check if PDF is text-based (not scanned)
pdftotext resume.pdf -  # Should show text

# Convert scanned PDF to text first
# Use OCR tools like Tesseract

# Error: OpenAI API error

# Verify API key
python -c "import openai; openai.OpenAI(api_key='YOUR_KEY').models.list()"

# Try using Anthropic instead
# Set ANTHROPIC_API_KEY in .env
```

## Web Application Issues

### Flask won't start
```bash
# Error: Port already in use

# Change port in .env
FLASK_PORT=5001

# Or kill process on port 5123
lsof -ti:5123 | xargs kill -9

# Error: Template not found

# Verify templates directory exists
ls -la src/templates/index.html

# Create if missing
mkdir -p src/templates
```

### Can't access web app
```bash
# Check if Flask is running
ps aux | grep flask

# Verify host and port
cat .env | grep FLASK_

# Try different host
FLASK_HOST=127.0.0.1  # or 0.0.0.0

# Check firewall settings
# macOS: System Preferences > Security & Privacy > Firewall
```

### Applications not showing in dashboard
```bash
# Check Google Sheets connection
python -c "from src.google_sheets import GoogleSheetsManager; m = GoogleSheetsManager(); print(m.get_all_applications())"

# Check MongoDB connection
python -c "from src.database import MongoDBManager; db = MongoDBManager(); print(db.get_application_count('default_user'))"

# Verify data in Google Sheets
# Open sheet manually and check for data

# Refresh browser (Ctrl+Shift+R / Cmd+Shift+R)
```

## Job Application Issues

### No jobs found
```bash
# Check job portals in database
python -c "from src.database import MongoDBManager; db = MongoDBManager(); print(db.get_all_job_portals())"

# Initialize default portals
python -c "from src.database import MongoDBManager; db = MongoDBManager(); db.initialize_default_portals()"

# Increase search quota
# Edit .env:
MAX_STEPS_QUOTA=200  # Allow more search steps
```

### Applications failing
```bash
# Check MobileRun task status
# Use task ID from logs

# Reduce complexity
# - Apply to fewer portals
# - Use simpler prompts
# - Increase timeout: AGENT_EXECUTION_TIMEOUT=600

# Enable reasoning mode
# - Already enabled by default
# - Helps with complex forms
```

### Quota reached too quickly
```bash
# Adjust quota settings in .env

# For more applications
MIN_JOBS_APPLIED=20  # Increase minimum jobs

# For more search steps
MAX_STEPS_QUOTA=200  # Increase maximum steps

# Monitor steps per job
# Check logs for average steps per application
# Optimize prompts to reduce steps
```

### CAPTCHA blocking applications
```bash
# This is expected behavior
# Human intervention required

# Options:
# 1. Solve CAPTCHA manually when prompted
# 2. Use job portals with fewer CAPTCHAs
# 3. Space out applications (reduce frequency)
# 4. Use residential proxies (MobileRun Cloud uses phone)
```

## Data Issues

### Duplicate applications
```bash
# Check duplicate prevention
python -c "from src.database import MongoDBManager; db = MongoDBManager(); print(db.is_job_already_applied('default_user', 'https://example.com/job'))"

# Clear cache if needed
python -c "from src.database import MongoDBManager; db = MongoDBManager(); db.job_listings.delete_many({'user_id': 'default_user'})"
```

### Google Sheets not syncing
```bash
# Verify credentials
python -c "from src.google_sheets import GoogleSheetsManager; m = GoogleSheetsManager(); print(m.get_sheet_url())"

# Re-share sheet with service account
# Get email from credentials.json
cat credentials.json | grep client_email

# Manually sync
python examples.py  # See Example 7
```

## Performance Issues

### Slow resume parsing
```bash
# OpenAI is usually fast
# If slow, check:
# 1. Network connection
# 2. API rate limits
# 3. Server location

# Try Anthropic instead
# Set in .env:
ANTHROPIC_API_KEY=your_key
```

### Slow job applications
```bash
# This is normal - each job takes 2-5 minutes

# To speed up:
# 1. Use faster LLM model
#    LLM_MODEL=google/gemini-2.5-flash
# 
# 2. Reduce max steps per job
#    Edit mobilerun_agent.py:
#    max_steps=30  # Instead of 40
#
# 3. Apply to fewer jobs
#    MIN_JOBS_APPLIED=5
```

## Debugging Tips

### Enable debug logging
```python
# Add to top of main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test individual components
```bash
# Test resume parser
python -c "from src.resume_parser import ResumeParser; p = ResumeParser(); print(p.parse_resume('resume.pdf'))"

# Test MongoDB
python -c "from src.database import MongoDBManager; db = MongoDBManager(); print('OK')"

# Test Google Sheets
python -c "from src.google_sheets import GoogleSheetsManager; m = GoogleSheetsManager(); print('OK')"

# Test MobileRun API
python -c "from src.mobilerun_agent import MobileRunAgent; a = MobileRunAgent(); print('OK')"
```

### Check Python environment
```bash
# Verify correct Python version
python --version

# Check installed packages
uv pip list

# Verify virtual environment is activated
which python  # Should point to .venv/bin/python
```

### Reset everything
```bash
# Remove virtual environment
rm -rf .venv

# Reinstall
uv sync

# Clear MongoDB data
python -c "from src.database import MongoDBManager; db = MongoDBManager(); db.application_history.delete_many({}); db.job_listings.delete_many({})"

# Restart MongoDB
brew services restart mongodb-community

# Restart Flask
pkill -f flask
uv run python main.py web
```

## Getting Help

### Check logs
```bash
# Flask logs (in terminal where you ran main.py)

# MongoDB logs
tail -f /usr/local/var/log/mongodb/mongo.log

# System logs (macOS)
log show --predicate 'processImagePath contains "python"' --last 1h
```

### Search documentation
- MobileRun: https://docs.mobilerun.ai/
- DroidRun: https://docs.droidrun.ai/
- MongoDB: https://docs.mongodb.com/
- Google Sheets API: https://developers.google.com/sheets/api

### Community support
- Discord: https://discord.gg/droidrun
- GitHub Issues: Create an issue with:
  - Error message
  - Steps to reproduce
  - Environment (OS, Python version)
  - Relevant logs

### Emergency fixes
```bash
# Quick reset
./setup.sh

# Nuclear option (delete everything)
rm -rf .venv uploads src/__pycache__
uv sync
```

## Common Error Messages

### "Configuration errors: MOBILERUN_API_KEY is required"
**Solution**: Add MOBILERUN_API_KEY to .env file

### "Failed to extract text from PDF"
**Solution**: Ensure PDF is text-based, not scanned image

### "Permission denied" (Google Sheets)
**Solution**: Share sheet with service account email (editor permissions)

### "No module named 'src'"
**Solution**: Run from project root directory or activate virtual environment

### "MongoClient could not connect"
**Solution**: Start MongoDB: `brew services start mongodb-community`

### "Rate limit exceeded"
**Solution**: Wait and reduce quotas in .env

### "Insufficient credits"
**Solution**: Add credits to MobileRun account

### "Task timeout"
**Solution**: Increase AGENT_EXECUTION_TIMEOUT in .env

## Prevention Tips

1. **Always validate config before running**
   ```python
   from src.config import Config
   Config.validate()
   ```

2. **Start with low quotas for testing**
   ```env
   MIN_JOBS_APPLIED=1
   MAX_STEPS_QUOTA=20
   ```

3. **Monitor API usage and costs**
   - Check MobileRun dashboard daily
   - Set up billing alerts

4. **Keep credentials secure**
   - Never commit .env or credentials.json
   - Rotate API keys monthly

5. **Backup data regularly**
   - Export MongoDB data
   - Download Google Sheets as CSV

6. **Test on single job first**
   ```bash
   uv run python main.py apply resume.pdf --user-id test
   ```

---

Still having issues? Create a detailed bug report with:
- Error message (full traceback)
- Steps to reproduce
- Environment details
- What you've already tried
