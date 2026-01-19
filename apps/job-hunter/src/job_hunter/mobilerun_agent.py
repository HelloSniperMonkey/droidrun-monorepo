"""MobileRun AI agent for automated job applications"""
import requests
from typing import Dict, List, Optional
from datetime import datetime
from job_hunter.config import Config
from job_hunter.resume_parser import ResumeData


class MobileRunAgent:
    """Interface for MobileRun Cloud API to automate job applications"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.MOBILERUN_API_KEY
        self.base_url = Config.MOBILERUN_API_URL
        print(f"DEBUG: MobileRunAgent initialized with base_url={self.base_url}")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.device_id = None
        self._get_available_device()

    def _get_available_device(self):
        """Get an available device from MobileRun Cloud"""
        try:
            response = requests.get(
                f"{self.base_url}/devices",
                headers=self.headers,
                params={"state": "ready", "pageSize": 1}
            )
            response.raise_for_status()
            data = response.json()

            if data.get('items') and len(data['items']) > 0:
                self.device_id = data['items'][0]['id']
                print(f"Connected to device: {data['items'][0].get('name', self.device_id)}")
            else:
                print("No ready devices found. Tasks will be queued.")
        except Exception as e:
            print(f"Could not fetch device: {str(e)}")

    def create_task(self,
                   task_prompt: str,
                   max_steps: int = 50,
                   execution_timeout: int = 300,
                   apps: Optional[List[str]] = None,
                   output_schema: Optional[Dict] = None,
                   reasoning: bool = True,
                   vision: bool = True) -> Dict:
        """
        Create and execute a task on MobileRun Cloud

        Args:
            task_prompt: Natural language description of the task
            max_steps: Maximum number of actions the agent can take
            execution_timeout: Time limit in seconds
            apps: List of app package names to make available
            output_schema: JSON schema for structured output
            reasoning: Enable reasoning mode for complex tasks
            vision: Enable vision for UI understanding

        Returns:
            Task execution result
        """
        payload = {
            "task": task_prompt,
            "llmModel": Config.LLM_MODEL,
            "maxSteps": max_steps,
            "executionTimeout": execution_timeout,
            "temperature": Config.AGENT_TEMPERATURE,
            "reasoning": reasoning,
            "vision": vision
        }

        # Add device ID if available
        if self.device_id:
            payload["deviceId"] = self.device_id

        if apps:
            payload["apps"] = apps

        if output_schema:
            payload["outputSchema"] = output_schema

        try:
            url = f"{self.base_url}/tasks/"
            print(f"    DEBUG: Creating task at URL: {url}")
            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Print more details about the error
            error_msg = f"Failed to create MobileRun task: {str(e)}"
            try:
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f"\n    Response: {e.response.text[:500]}"
            except:
                pass
            raise Exception(error_msg)

    def get_task_status(self, task_id: str) -> Dict:
        """Get the status and results of a task"""
        try:
            url = f"{self.base_url}/tasks/{task_id}/"
            print(f"    DEBUG: Checking task status at URL: {url}")
            response = requests.get(
                url,
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            # API returns {"task": {...}} - extract the task object
            return data.get('task', data)
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get task status: {str(e)}"
            try:
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f"\n    Response: {e.response.text[:500]}"
            except:
                pass
            raise Exception(error_msg)

    def search_jobs_on_portal(self,
                             portal_url: str,
                             keywords: List[str],
                             location: Optional[str] = None,
                             max_steps: int = 30) -> Dict:
        """
        Search for jobs on a specific portal using MobileRun agent

        Args:
            portal_url: URL of the job portal
            keywords: Search keywords (job titles, skills)
            location: Preferred job location
            max_steps: Maximum steps for this search

        Returns:
            Search results with job listings
        """
        location_text = f" in {location}" if location else ""
        keywords_text = ", ".join(keywords[:3])  # Use top 3 keywords

        task_prompt = f"""
        Open the browser and navigate to {portal_url}.
        Search for jobs with keywords: {keywords_text}{location_text}.
        Browse through the job listings and collect the following information for each job:
        - Job title
        - Company name
        - Location (remote/onsite/hybrid)
        - Job type (full-time/part-time/internship/contract)
        - Salary range (if available)
        - Application link/URL
        - Job posting date

        Return a list of at least 10 relevant job postings.
        """

        output_schema = {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "company": {"type": "string"},
                            "location": {"type": "string"},
                            "job_type": {"type": "string"},
                            "salary": {"type": "string"},
                            "apply_link": {"type": "string"},
                            "posted_date": {"type": "string"}
                        }
                    }
                },
                "portal": {"type": "string"},
                "search_keywords": {"type": "array", "items": {"type": "string"}}
            }
        }

        return self.create_task(
            task_prompt=task_prompt,
            max_steps=max_steps,
            output_schema=output_schema
        )

    def apply_to_job(self,
                    apply_url: str,
                    resume_data: ResumeData,
                    user_preferences: Dict,
                    max_steps: int = 40) -> Dict:
        """
        Apply to a job using MobileRun agent

        Args:
            apply_url: URL of the job application
            resume_data: Parsed resume information
            user_preferences: User preferences (visa status, sponsorship, etc.)
            max_steps: Maximum steps for application

        Returns:
            Application result
        """
        task_prompt = f"""
        Navigate to {apply_url} and complete the job application.

        Use the following information to fill out the application:
        - Full Name: {resume_data.full_name}
        - Email: {resume_data.email}
        - Phone: {resume_data.phone or 'Not provided'}
        - Location: {resume_data.location or 'Not provided'}

        Work Experience:
        {self._format_experience(resume_data.experience)}

        Education:
        {self._format_education(resume_data.education)}

        Skills: {', '.join(resume_data.skills[:10])}

        If asked about visa status or sponsorship:
        {self._format_preferences(user_preferences)}

        If you encounter any question that cannot be answered with the provided information:
        1. Note the question
        2. Mark it as requiring clarification
        3. Pause the application and return the question

        If the application requires uploading a resume, indicate that resume upload is needed.
        If there's a CAPTCHA, pause and indicate CAPTCHA intervention needed.

        Complete the application if all information is available.
        """

        output_schema = {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["completed", "needs_clarification", "needs_resume_upload", "captcha_required", "failed"]
                },
                "application_id": {"type": "string"},
                "questions_needing_clarification": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "error_message": {"type": "string"},
                "steps_taken": {"type": "integer"}
            }
        }

        return self.create_task(
            task_prompt=task_prompt,
            max_steps=max_steps,
            output_schema=output_schema,
            reasoning=True
        )

    def google_search_jobs(self, keywords: List[str], location: Optional[str] = None) -> Dict:
        """
        Perform Google search for job listings

        Args:
            keywords: Search keywords
            location: Preferred location

        Returns:
            Search results with job portals and listings
        """
        location_text = f" in {location}" if location else ""
        keywords_text = " ".join(keywords[:3])

        task_prompt = f"""
        Open Google Chrome and search for: "{keywords_text} jobs{location_text}"

        Browse through the search results and:
        1. Identify job portal URLs (Indeed, LinkedIn, Glassdoor, etc.)
        2. Collect job listings with:
           - Job title
           - Company
           - Location
           - Job portal URL
           - Direct application link

        Return at least 15 job opportunities from various portals.
        """

        output_schema = {
            "type": "object",
            "properties": {
                "job_portals": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "jobs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "company": {"type": "string"},
                            "location": {"type": "string"},
                            "portal": {"type": "string"},
                            "apply_link": {"type": "string"}
                        }
                    }
                }
            }
        }

        return self.create_task(
            task_prompt=task_prompt,
            max_steps=50,
            output_schema=output_schema,
            apps=["com.android.chrome"]
        )

    def _format_experience(self, experience: List[Dict[str, str]]) -> str:
        """Format work experience for prompt"""
        if not experience:
            return "No work experience provided"

        formatted = []
        for exp in experience[:3]:  # Top 3 experiences
            formatted.append(
                f"- {exp.get('role', 'N/A')} at {exp.get('company', 'N/A')} "
                f"({exp.get('duration', 'N/A')})"
            )
        return "\n".join(formatted)

    def _format_education(self, education: List[Dict[str, str]]) -> str:
        """Format education for prompt"""
        if not education:
            return "No education provided"

        formatted = []
        for edu in education:
            formatted.append(
                f"- {edu.get('degree', 'N/A')} in {edu.get('major', 'N/A')} "
                f"from {edu.get('institution', 'N/A')} ({edu.get('year', 'N/A')})"
            )
        return "\n".join(formatted)

    def _format_preferences(self, preferences: Dict) -> str:
        """Format user preferences for prompt"""
        lines = []
        if 'visa_status' in preferences:
            lines.append(f"- Visa Status: {preferences['visa_status']}")
        if 'requires_sponsorship' in preferences:
            lines.append(f"- Requires Sponsorship: {'Yes' if preferences['requires_sponsorship'] else 'No'}")
        if 'willing_to_relocate' in preferences:
            lines.append(f"- Willing to Relocate: {'Yes' if preferences['willing_to_relocate'] else 'No'}")
        return "\n".join(lines) if lines else "No preferences specified"
