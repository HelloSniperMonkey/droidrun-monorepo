"""Job application orchestrator with quota management"""
from typing import Dict, List, Optional
from datetime import datetime
import time
from job_hunter.config import Config
from job_hunter.resume_parser import ResumeParser, ResumeData
from job_hunter.agent_factory import create_agent, AgentError
from job_hunter.database import MongoDBManager
from job_hunter.google_sheets import GoogleSheetsManager


class QuotaManager:
    """Manage application quota based on steps and job count"""

    def __init__(self, max_steps: int, min_jobs: int):
        self.max_steps = max_steps
        self.min_jobs = min_jobs
        self.total_steps_used = 0
        self.jobs_applied = 0
        self.start_time = datetime.now()

    def add_steps(self, steps: int):
        """Add steps to the counter"""
        self.total_steps_used += steps

    def add_job(self):
        """Increment jobs applied counter"""
        self.jobs_applied += 1

    def is_quota_complete(self) -> bool:
        """Check if quota is complete (either condition met)"""
        return (
            self.total_steps_used >= self.max_steps or
            self.jobs_applied >= self.min_jobs
        )

    def get_status(self) -> Dict:
        """Get current quota status"""
        return {
            "total_steps_used": self.total_steps_used,
            "max_steps": self.max_steps,
            "jobs_applied": self.jobs_applied,
            "min_jobs": self.min_jobs,
            "quota_complete": self.is_quota_complete(),
            "elapsed_time": (datetime.now() - self.start_time).total_seconds()
        }

    def get_remaining(self) -> Dict:
        """Get remaining quota"""
        return {
            "steps_remaining": max(0, self.max_steps - self.total_steps_used),
            "jobs_remaining": max(0, self.min_jobs - self.jobs_applied)
        }


class JobApplicationOrchestrator:
    """Orchestrate the entire job application process"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.resume_parser = ResumeParser()
        # Use agent factory with fallback support
        try:
            self.agent = create_agent(use_fallback=True)
            agent_type = getattr(self.agent, 'get_agent_type', lambda: Config.EXECUTION_MODE)()
            print(f"JobApplicationOrchestrator: Using {agent_type} agent")
        except AgentError as e:
            print(f"Warning: Agent initialization failed: {e}")
            self.agent = None
        self.db = MongoDBManager()
        self.sheets = None  # Initialize when needed
        self.quota = QuotaManager(
            max_steps=Config.MAX_STEPS_QUOTA,
            min_jobs=Config.MIN_JOBS_APPLIED
        )

        # Initialize default job portals
        self.db.initialize_default_portals()

    def initialize_google_sheets(self):
        """Initialize Google Sheets manager"""
        if not self.sheets:
            self.sheets = GoogleSheetsManager()

    def parse_resume(self, resume_path: str) -> ResumeData:
        """Parse the resume and return structured data"""
        print(f"Parsing resume from {resume_path}...")
        resume_data = self.resume_parser.parse_resume(resume_path)
        print(f"Resume parsed successfully for {resume_data.full_name}")
        return resume_data

    def get_user_preferences(self) -> Dict:
        """Get or prompt for user preferences"""
        preferences = self.db.get_user_preferences(self.user_id)

        if not preferences:
            print("\nSetting up user preferences...")
            preferences = self._prompt_for_preferences()
            self.db.save_user_preferences(self.user_id, preferences)

        return preferences

    def _prompt_for_preferences(self) -> Dict:
        """Prompt user for common preferences"""
        preferences = {}

        print("\nPlease answer the following questions (used for all applications):")

        # Visa status
        visa = input("Do you hold a valid work visa for your target country? (yes/no): ").strip().lower()
        preferences['visa_status'] = 'yes' if visa == 'yes' else 'no'

        # Sponsorship
        sponsor = input("Do you require visa sponsorship? (yes/no): ").strip().lower()
        preferences['requires_sponsorship'] = sponsor == 'yes'

        # Relocation
        relocate = input("Are you willing to relocate? (yes/no): ").strip().lower()
        preferences['willing_to_relocate'] = relocate == 'yes'

        # Preferred location
        location = input("Preferred job location (or 'remote'): ").strip()
        preferences['preferred_location'] = location if location else None

        # Work authorization
        work_auth = input("Countries where you're authorized to work (comma-separated): ").strip()
        preferences['work_authorization'] = [c.strip() for c in work_auth.split(',')] if work_auth else []

        return preferences

    def search_jobs(self, resume_data: ResumeData, preferences: Dict) -> List[Dict]:
        """Search for jobs across portals"""
        print("\nSearching for relevant jobs...")

        # Check if agent is available
        if not self.agent:
            print("Error: No agent available. Please check your configuration.")
            return []

        keywords = self.resume_parser.generate_search_keywords(resume_data)
        location = preferences.get('preferred_location')

        all_jobs = []
        portals = self.db.get_all_job_portals()

        # Check if we need to do Google search
        if self.quota.is_quota_complete():
            print("Quota already complete, skipping search")
            return all_jobs

        # Search on each portal
        for portal in portals[:3]:  # Limit to 3 portals initially
            if self.quota.is_quota_complete():
                break

            try:
                print(f"  Searching on {portal['name']}...")
                result = self.agent.search_jobs_on_portal(
                    portal_url=portal['url'],
                    keywords=keywords,
                    location=location,
                    max_steps=30  # Increased from 30 to allow more exploration
                )

                # Update quota with steps used
                task_id = result.get('id')
                if task_id:
                    # Wait for task completion (with timeout)
                    try:
                        task_result = self._wait_for_task(task_id)
                        steps_used = task_result.get('steps', 0)
                        self.quota.add_steps(steps_used)

                        # Only extract jobs if task succeeded
                        if task_result.get('status') == 'completed' and task_result.get('succeeded', False):
                            jobs = task_result.get('output', {}).get('jobs', [])
                            for job in jobs:
                                job['portal'] = portal['name']
                                # Cache job in database
                                self.db.cache_job_listing(self.user_id, job)
                            all_jobs.extend(jobs)
                            print(f"    Found {len(jobs)} jobs from {portal['name']}")
                        else:
                            print(f"    No jobs extracted (task did not succeed)")
                    except Exception as e:
                        print(f"    Task polling error: {e}")
                        continue  # Move to next portal

            except Exception as e:
                print(f"  Error searching {portal['name']}: {e}")
                continue  # Move to next portal

        # If quota not complete and not enough jobs, do Google search
        if not self.quota.is_quota_complete() and len(all_jobs) < 15:
            print("  Performing Google search for more jobs...")
            try:
                result = self.agent.google_search_jobs(keywords, location)
                task_id = result.get('id')
                if task_id:
                    try:
                        task_result = self._wait_for_task(task_id)
                        self.quota.add_steps(task_result.get('steps', 0))

                        if task_result.get('status') == 'completed' and task_result.get('succeeded', False):
                            google_jobs = task_result.get('output', {}).get('jobs', [])
                            # Add new portals to database
                            new_portals = task_result.get('output', {}).get('job_portals', [])
                            for portal_url in new_portals:
                                portal_name = portal_url.split("//")[1].split("/")[0]
                                self.db.add_job_portal(portal_url, portal_name)

                            # Cache jobs
                            for job in google_jobs:
                                self.db.cache_job_listing(self.user_id, job)

                            all_jobs.extend(google_jobs)
                            print(f"    Found {len(google_jobs)} jobs from Google search")
                    except Exception as e:
                        print(f"    Task polling error: {e}")
            except Exception as e:
                print(f"  Error with Google search: {e}")

        print(f"Found {len(all_jobs)} job opportunities")
        return all_jobs

    def apply_to_jobs(self, jobs: List[Dict], resume_data: ResumeData, preferences: Dict):
        """Apply to jobs using the agent"""
        print(f"\nStarting job applications (max: {self.quota.min_jobs})...")

        # Check if agent is available
        if not self.agent:
            print("Error: No agent available. Please check your configuration.")
            return

        self.initialize_google_sheets()

        for job in jobs:
            if self.quota.is_quota_complete():
                print("\nQuota complete!")
                break

            apply_link = job.get('apply_link')

            # Skip if already applied
            if self.db.is_job_already_applied(self.user_id, apply_link):
                print(f"  Skipping {job.get('title')} - already applied")
                continue

            if self.sheets.check_if_applied(apply_link):
                print(f"  Skipping {job.get('title')} - already in sheet")
                self.db.mark_job_as_applied(self.user_id, apply_link)
                continue

            print(f"\n  Applying to: {job.get('title')} at {job.get('company')}")

            try:
                # Apply to the job
                result = self.agent.apply_to_job(
                    apply_url=apply_link,
                    resume_data=resume_data,
                    user_preferences=preferences,
                    max_steps=40
                )

                task_id = result.get('id')
                if task_id:
                    task_result = self._wait_for_task(task_id)
                    output = task_result.get('output', {})
                    steps_used = output.get('steps_taken', 0)
                    status = output.get('status', 'failed')

                    self.quota.add_steps(steps_used)

                    # Handle different statuses
                    if status == 'completed':
                        print(f"  Application completed!")
                        self.quota.add_job()

                        # Save to database and sheets
                        app_data = {
                            'company': job.get('company'),
                            'job_title': job.get('title'),
                            'apply_link': apply_link,
                            'date_applied': datetime.now().strftime('%Y-%m-%d'),
                            'salary': job.get('salary', ''),
                            'job_type': job.get('job_type', ''),
                            'location': job.get('location', ''),
                            'status': 'Applied',
                            'portal': job.get('portal'),
                            'application_id': output.get('application_id'),
                            'steps_taken': steps_used
                        }

                        self.db.save_application(self.user_id, app_data)
                        self.db.mark_job_as_applied(self.user_id, apply_link)
                        self.sheets.add_application(app_data)

                    elif status == 'needs_clarification':
                        print(f"  Needs clarification:")
                        questions = output.get('questions_needing_clarification', [])
                        for q in questions:
                            print(f"    - {q}")
                        self._handle_clarification(questions, preferences)

                    elif status == 'captcha_required':
                        print(f"  CAPTCHA detected - human intervention needed")
                        # TODO: Implement CAPTCHA handling

                    else:
                        print(f"  Application failed: {output.get('error_message', 'Unknown error')}")

            except Exception as e:
                print(f"  Error applying: {e}")

            # Print quota status
            status = self.quota.get_status()
            print(f"\n  Progress: {status['jobs_applied']}/{status['min_jobs']} jobs | "
                  f"{status['total_steps_used']}/{status['max_steps']} steps")

    def _wait_for_task(self, task_id: str, poll_interval: int = 3, max_wait: int = 120) -> Dict:
        """Wait for a MobileRun task to complete"""
        elapsed = 0
        terminal_statuses = ['completed', 'failed', 'cancelled', 'timeout']

        print(f"    Waiting for task {task_id[:8]}...")

        while elapsed < max_wait:
            try:
                task_data = self.agent.get_task_status(task_id)
                status = task_data.get('status', 'unknown')

                if status in terminal_statuses:
                    if status == 'completed' and task_data.get('succeeded', False):
                        print(f"    Task completed successfully")
                    elif status == 'failed' or (status == 'completed' and not task_data.get('succeeded', True)):
                        error_msg = task_data.get('error', 'No error message')
                        print(f"    Task failed: {error_msg}")
                    else:
                        print(f"    Task ended with status: {status}")
                    return task_data

                # Still running
                if elapsed % 15 == 0 and elapsed > 0:
                    print(f"    Still running... ({elapsed}s elapsed)")

            except Exception as e:
                print(f"    Error checking task: {e}")
                # Don't fail completely, continue polling

            time.sleep(poll_interval)
            elapsed += poll_interval

        print(f"    Task timed out after {max_wait}s")
        return {"status": "timeout", "output": {}}

    def _handle_clarification(self, questions: List[str], preferences: Dict):
        """Handle questions that need user clarification"""
        print("\nPlease answer the following questions:")
        for question in questions:
            answer = input(f"  {question}: ").strip()
            # Store in preferences for future use
            # Simple key generation from question
            key = question.lower().replace(' ', '_').replace('?', '')[:50]
            preferences[key] = answer
            self.db.update_user_preference(self.user_id, key, answer)

    def run(self, resume_path: str) -> Dict:
        """
        Run the complete job application workflow

        Args:
            resume_path: Path to resume PDF file

        Returns:
            Summary of the application session
        """
        print("Starting AI Job Hunter...\n")

        # Step 1: Parse resume
        resume_data = self.parse_resume(resume_path)

        # Step 2: Get user preferences
        preferences = self.get_user_preferences()

        # Step 3: Search for jobs
        jobs = self.search_jobs(resume_data, preferences)

        if not jobs:
            print("\nNo jobs found. Please try again with different criteria.")
            return {"success": False, "message": "No jobs found"}

        # Step 4: Apply to jobs
        self.apply_to_jobs(jobs, resume_data, preferences)

        # Return summary
        summary = {
            "success": True,
            "resume_parsed": True,
            "jobs_found": len(jobs),
            "quota_status": self.quota.get_status(),
            "applications_submitted": self.quota.jobs_applied,
            "google_sheet_url": self.sheets.get_sheet_url() if self.sheets else None
        }

        print(f"\n{'='*60}")
        print("Job Application Session Complete!")
        print(f"{'='*60}")
        print(f"Jobs Found: {summary['jobs_found']}")
        print(f"Applications Submitted: {summary['applications_submitted']}")
        print(f"Steps Used: {summary['quota_status']['total_steps_used']}/{summary['quota_status']['max_steps']}")
        if summary['google_sheet_url']:
            print(f"\nView your applications: {summary['google_sheet_url']}")
        print(f"{'='*60}\n")

        return summary

    def get_application_status(self) -> List[Dict]:
        """Get all applications for the user"""
        return self.db.get_user_applications(self.user_id)

    def cleanup(self):
        """Clean up resources"""
        self.db.close()
