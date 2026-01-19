# Quick Start Guide 🚀

Get your AI Job Hunter up and running in 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.12+ installed
- [ ] MongoDB installed and running
- [ ] MobileRun API key
- [ ] OpenAI or Anthropic API key
- [ ] Google Cloud service account set up

## 5-Minute Setup

### 1. Install Dependencies (1 min)

```bash
# Run the setup script
./setup.sh

# Or manually:
uv sync
```

### 2. Configure Environment (2 min)

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your keys:
nano .env  # or use your favorite editor
```

Required variables:
```env
MOBILERUN_API_KEY=your_mobilerun_key
OPENAI_API_KEY=your_openai_key
GOOGLE_SHEETS_SPREADSHEET_ID=your_sheet_id
```

### 3. Set Up Google Sheets (2 min)

Quick steps:
1. Create a service account → Download `credentials.json`
2. Create a Google Sheet → Copy the ID from URL
3. Share sheet with service account email

📖 Detailed guide: See [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)

### 4. Start the App (30 sec)

```bash
# Start web app
uv run python main.py web

# Open browser to http://localhost:5123
```

## First Run

### Using Web Interface (Easiest)

1. Open http://localhost:5123
2. Enter your user ID (email or username)
3. Drag & drop your resume PDF
4. Click "Start Job Hunt"
5. Watch the magic happen! ✨

### Using CLI

```bash
# Apply to jobs from command line
uv run python main.py apply /path/to/resume.pdf --user-id your.email@example.com
```

## What Happens Next?

1. **Resume Parsing** (10-20 seconds)
   - AI extracts your information
   - Identifies your skills and experience

2. **Preference Setup** (first time only)
   - Answer a few questions
   - Saved for future runs

3. **Job Search** (2-5 minutes)
   - Searches multiple job portals
   - Google search for additional opportunities
   - Finds 20-30 relevant jobs

4. **Applications** (5-10 minutes)
   - Applies to jobs automatically
   - Uses smartphone via MobileRun Cloud
   - Stops at quota (10 jobs or 100 steps)

5. **Results**
   - View in web dashboard
   - Check Google Sheets
   - Get summary report

## Understanding Quotas

The app stops when **either** condition is met:

- ✅ Applied to minimum number of jobs (default: 10)
- ✅ Used maximum agent steps (default: 100)

Customize in `.env`:
```env
MIN_JOBS_APPLIED=10
MAX_STEPS_QUOTA=100
```

## Cost Estimation

### For 10 Job Applications

**MobileRun Cloud:**
- ~50-100 steps total
- ~$2-5 per session
- Model: gemini-2.5-flash (cheapest)

**OpenAI (Resume Parsing):**
- ~$0.01-0.05 per resume
- Model: gpt-4o-mini

**Total: ~$2-5 per session**

💡 **Tip**: Start with these settings for testing:
```env
MIN_JOBS_APPLIED=1
MAX_STEPS_QUOTA=20
LLM_MODEL=google/gemini-2.5-flash
```

## Viewing Your Applications

### Web Dashboard
- http://localhost:5123
- Real-time updates
- Filter by status, type, location
- Search functionality

### Google Sheets
- Shared with public (view only)
- Update manually if needed
- Download as CSV

### MongoDB
- Full history in database
- Query with MongoDB Compass
- Export for analysis

## Troubleshooting

### "MongoDB connection error"
```bash
# Start MongoDB
brew services start mongodb-community

# Or with Docker
docker run -d -p 27017:27017 mongo
```

### "Google Sheets permission denied"
- Check service account has editor access
- Verify spreadsheet ID is correct
- See [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)

### "MobileRun API error"
- Verify API key is correct
- Check account has credits
- See [MOBILERUN_SETUP.md](MOBILERUN_SETUP.md)

### "Resume parsing failed"
- Ensure PDF is text-based (not scanned)
- Check OpenAI/Anthropic API key
- Try different AI provider

## Best Practices

### 🎯 For Testing
```env
MIN_JOBS_APPLIED=1
MAX_STEPS_QUOTA=20
LLM_MODEL=google/gemini-2.5-flash
```

### 💼 For Production Use
```env
MIN_JOBS_APPLIED=10
MAX_STEPS_QUOTA=100
LLM_MODEL=google/gemini-1.5-pro
AGENT_TEMPERATURE=0.3
```

### 🚀 For Aggressive Job Hunting
```env
MIN_JOBS_APPLIED=25
MAX_STEPS_QUOTA=200
LLM_MODEL=anthropic/claude-3-5-sonnet
```

## Next Steps

After successful first run:

1. **Review Applications**
   - Check Google Sheets
   - Verify information is correct
   - Update statuses as you hear back

2. **Customize Settings**
   - Adjust quotas based on budget
   - Add more job portals to MongoDB
   - Fine-tune agent prompts

3. **Schedule Regular Runs**
   - Run daily or weekly
   - Set up cron job (Linux/macOS)
   - Use Task Scheduler (Windows)

4. **Monitor Results**
   - Track response rates
   - Analyze successful applications
   - Optimize resume and preferences

## Advanced Usage

### Add Custom Job Portals

```python
from src.database import MongoDBManager

db = MongoDBManager()
db.add_job_portal(
    url="https://jobs.example.com",
    name="Example Jobs",
    category="Tech"
)
```

### Update User Preferences

```python
db.update_user_preference(
    user_id="your.email@example.com",
    key="preferred_salary",
    value="100000-150000"
)
```

### Query Application History

```python
apps = db.get_user_applications("your.email@example.com")
for app in apps:
    print(f"{app['company']} - {app['status']}")
```

## Support & Resources

- 📖 Full Documentation: [README.md](README.md)
- 🔧 MobileRun Setup: [MOBILERUN_SETUP.md](MOBILERUN_SETUP.md)
- 📊 Google Sheets Setup: [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)
- 💬 Discord: https://discord.gg/droidrun
- 🐛 Issues: Create an issue on GitHub

## Success Tips

1. **Keep Resume Updated** - Better parsing = better matches
2. **Set Realistic Quotas** - Start small, scale up
3. **Monitor Spending** - Check MobileRun dashboard
4. **Review Applications** - Quality over quantity
5. **Update Preferences** - Add answers to new questions
6. **Track Responses** - Update Google Sheets with interview/offer status

---

Happy Job Hunting! 🎉
