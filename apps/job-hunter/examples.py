"""
Example usage scripts for AI Job Hunter
"""

# Example 1: Basic CLI Usage
# ========================

# Apply to jobs with your resume
# uv run python -m job_hunter.main apply resume.pdf --user-id john.doe@email.com


# Example 2: Web App Usage
# ========================

# Start the web application
# uv run python -m job_hunter.main web
# Then open http://localhost:5123 in your browser


# Example 3: Direct Python Usage
# ==============================

from job_hunter.orchestrator import JobApplicationOrchestrator

# Initialize orchestrator
orchestrator = JobApplicationOrchestrator(user_id="john.doe@email.com")

# Run job hunting workflow
result = orchestrator.run(resume_path="path/to/resume.pdf")

# Check results
print(f"Jobs found: {result['jobs_found']}")
print(f"Applications submitted: {result['applications_submitted']}")
print(f"Google Sheet: {result['google_sheet_url']}")

# Cleanup
orchestrator.cleanup()


# Example 4: Resume Parsing Only
# ==============================

from job_hunter.resume_parser import ResumeParser

parser = ResumeParser()
resume_data = parser.parse_resume("resume.pdf")

print(f"Name: {resume_data.full_name}")
print(f"Email: {resume_data.email}")
print(f"Skills: {', '.join(resume_data.skills[:5])}")


# Example 5: Job Search Only
# ==========================

from job_hunter.mobilerun_agent import MobileRunAgent

agent = MobileRunAgent()
result = agent.google_search_jobs(
    keywords=["Python Developer", "Software Engineer"],
    location="San Francisco"
)

task_id = result.get('id')
# Wait for task completion and get results


# Example 6: MongoDB Operations
# =============================

from job_hunter.database import MongoDBManager

db = MongoDBManager()

# Add custom job portal
db.add_job_portal(
    url="https://startup-jobs.com",
    name="Startup Jobs",
    category="Startups"
)

# Get all applications
apps = db.get_user_applications("john.doe@email.com")
print(f"Total applications: {len(apps)}")

# Update application status
db.update_application_status(
    user_id="john.doe@email.com",
    apply_link="https://company.com/apply/123",
    status="Interview Scheduled"
)

# Get user preferences
prefs = db.get_user_preferences("john.doe@email.com")
print(f"Preferences: {prefs}")

db.close()


# Example 7: Google Sheets Operations
# ===================================

from job_hunter.google_sheets import GoogleSheetsManager

sheets = GoogleSheetsManager()

# Add single application
application = {
    'company': 'Tech Corp',
    'job_title': 'Senior Python Developer',
    'apply_link': 'https://techcorp.com/jobs/123',
    'date_applied': '2026-01-18',
    'salary': '$120k - $160k',
    'job_type': 'Full-time',
    'location': 'Remote',
    'status': 'Applied'
}
sheets.add_application(application)

# Get all applications
all_apps = sheets.get_all_applications()
print(f"Total in sheet: {len(all_apps)}")

# Update status
sheets.update_application_status(
    apply_link='https://techcorp.com/jobs/123',
    new_status='Interview'
)

# Get sheet URL
print(f"View sheet: {sheets.get_sheet_url()}")


# Example 8: Custom Agent Task
# ============================

from job_hunter.mobilerun_agent import MobileRunAgent

agent = MobileRunAgent()

# Create custom task
result = agent.create_task(
    task_prompt="""
    Open LinkedIn and:
    1. Search for 'Machine Learning Engineer' jobs in 'New York'
    2. Apply filters: Remote, Full-time, Entry Level
    3. Collect first 10 job listings with company, title, and apply link
    """,
    max_steps=40,
    reasoning=True,
    vision=True,
    output_schema={
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "title": {"type": "string"},
                        "apply_link": {"type": "string"}
                    }
                }
            }
        }
    }
)

task_id = result.get('id')
print(f"Task created: {task_id}")


# Example 9: DroidRun Backup
# ==========================

from job_hunter.droidrun_backup import DroidRunBackup

backup = DroidRunBackup()

if backup.is_available():
    result = backup.create_agent(
        task="Open Indeed and search for remote Python jobs",
        llm_provider="openai",
        model="gpt-4o-mini"
    )
    print(f"DroidRun result: {result}")
else:
    print("DroidRun not available - install with: pip install droidrun")


# Example 10: Quota Management
# ============================

from job_hunter.orchestrator import QuotaManager

# Create quota manager
quota = QuotaManager(max_steps=100, min_jobs=10)

# Simulate job application process
for i in range(15):
    quota.add_steps(8)  # 8 steps per job
    quota.add_job()

    if quota.is_quota_complete():
        print(f"Quota complete at job {i+1}")
        break

# Get final status
status = quota.get_status()
print(f"Steps used: {status['total_steps_used']}/{status['max_steps']}")
print(f"Jobs applied: {status['jobs_applied']}/{status['min_jobs']}")


# Example 11: Flask API Usage
# ===========================

import requests

# Upload resume via API
files = {'resume': open('resume.pdf', 'rb')}
data = {'user_id': 'john.doe@email.com'}
response = requests.post('http://localhost:5123/api/upload-resume',
                        files=files, data=data)
print(response.json())

# Get applications
response = requests.get('http://localhost:5123/api/applications/google-sheets')
apps = response.json()
print(f"Total applications: {apps['count']}")

# Update status
update_data = {
    'apply_link': 'https://company.com/job/123',
    'status': 'Interview'
}
response = requests.post('http://localhost:5123/api/applications/john.doe@email.com/status',
                        json=update_data)
print(response.json())


# Example 12: Scheduled Job Hunting
# =================================

import schedule
import time

def run_job_hunt():
    """Run job hunting daily"""
    orchestrator = JobApplicationOrchestrator(user_id="john.doe@email.com")
    result = orchestrator.run(resume_path="resume.pdf")
    orchestrator.cleanup()
    print(f"Daily run complete: {result['applications_submitted']} jobs applied")

# Schedule daily at 9 AM
schedule.every().day.at("09:00").do(run_job_hunt)

# Run scheduler (in a background service)
while True:
    schedule.run_pending()
    time.sleep(60)


# Example 13: Advanced Filtering
# ==============================

from job_hunter.database import MongoDBManager

db = MongoDBManager()

# Get all applications
apps = db.get_user_applications("john.doe@email.com")

# Filter by status
interviews = [app for app in apps if app['status'] == 'Interview']
print(f"Interviews scheduled: {len(interviews)}")

# Filter by job type
remote_jobs = [app for app in apps if 'remote' in app['location'].lower()]
print(f"Remote opportunities: {len(remote_jobs)}")

# Filter by date
from datetime import datetime, timedelta
last_week = datetime.now() - timedelta(days=7)
recent_apps = [app for app in apps
               if datetime.strptime(app['date_applied'], '%Y-%m-%d') > last_week]
print(f"Applications last week: {len(recent_apps)}")

db.close()


# Example 14: Error Handling
# ==========================

from job_hunter.orchestrator import JobApplicationOrchestrator
from job_hunter.config import Config

try:
    # Validate config first
    Config.validate()

    orchestrator = JobApplicationOrchestrator(user_id="john.doe@email.com")
    result = orchestrator.run(resume_path="resume.pdf")

    if result['success']:
        print("✅ Success!")
    else:
        print(f"❌ Failed: {result.get('message')}")

except ValueError as e:
    print(f"Configuration error: {e}")
except FileNotFoundError as e:
    print(f"Resume file not found: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    if 'orchestrator' in locals():
        orchestrator.cleanup()


# Example 15: Testing Configuration
# =================================

from job_hunter.config import Config

# Print configuration (without secrets)
print("Configuration:")
print(f"MongoDB: {Config.MONGODB_URI}")
print(f"Max Steps: {Config.MAX_STEPS_QUOTA}")
print(f"Min Jobs: {Config.MIN_JOBS_APPLIED}")
print(f"LLM Model: {Config.LLM_MODEL}")
print(f"Flask Port: {Config.FLASK_PORT}")

# Check if required keys are set
required_keys = [
    'MOBILERUN_API_KEY',
    'OPENROUTER_API_KEY',
    'GOOGLE_SHEETS_SPREADSHEET_ID'
]

for key in required_keys:
    value = getattr(Config, key, None)
    status = "✅" if value else "❌"
    print(f"{status} {key}: {'Set' if value else 'Not set'}")
