"""DroidRun local agent for job applications when MobileRun Cloud is unavailable"""
import asyncio
import uuid
import queue
import threading
import atexit
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from job_hunter.config import Config


class TaskStatus(str, Enum):
    """Task status enum for tracking progress"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskItem(BaseModel):
    """Single task item in the task list"""
    id: int = Field(description="Task number")
    description: str = Field(description="What needs to be done")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    result: str = Field(default="", description="Result or notes from completing the task")


class JobListing(BaseModel):
    """Schema for a single job listing"""
    title: str = Field(description="Job title", default="")
    company: str = Field(description="Company name", default="")
    location: str = Field(description="Job location (remote/onsite/hybrid)", default="")
    job_type: str = Field(description="Job type (full-time/part-time/contract)", default="")
    salary: str = Field(description="Salary range if available", default="")
    apply_link: str = Field(description="URL to apply for the job", default="")
    posted_date: str = Field(description="When the job was posted", default="")
    relevance_score: int = Field(description="How relevant is this job 1-10", default=5)
    applied: bool = Field(description="Whether application was submitted", default=False)
    application_status: str = Field(description="Application result if applied", default="")


class JobSearchAndApplyResult(BaseModel):
    """Schema for combined job search and application results"""
    jobs_found: List[JobListing] = Field(description="All jobs discovered", default_factory=list)
    jobs_applied: List[JobListing] = Field(description="Jobs successfully applied to", default_factory=list)
    jobs_skipped: List[JobListing] = Field(description="Jobs skipped with reason", default_factory=list)
    portal: str = Field(description="Job portal name", default="")
    search_keywords: List[str] = Field(description="Keywords used for search", default_factory=list)
    task_summary: List[TaskItem] = Field(description="Summary of all tasks performed", default_factory=list)
    total_jobs_found: int = Field(default=0)
    total_applications_submitted: int = Field(default=0)


class JobSearchResult(BaseModel):
    """Schema for job search results"""
    jobs: List[JobListing] = Field(description="List of job listings found", default_factory=list)
    portal: str = Field(description="Job portal name", default="")
    search_keywords: List[str] = Field(description="Keywords used for search", default_factory=list)


class GoogleSearchResult(BaseModel):
    """Schema for Google job search results"""
    job_portals: List[str] = Field(description="Job portal URLs found", default_factory=list)
    jobs: List[JobListing] = Field(description="List of job listings found", default_factory=list)


class ApplicationResult(BaseModel):
    """Schema for job application result"""
    status: str = Field(description="Application status: completed, needs_clarification, needs_resume_upload, captcha_required, failed", default="failed")
    application_id: str = Field(description="Application confirmation ID if available", default="")
    job_title: str = Field(description="Title of the job applied to", default="")
    company: str = Field(description="Company name", default="")
    questions_needing_clarification: List[str] = Field(description="Questions that need user input", default_factory=list)
    error_message: str = Field(description="Error message if failed", default="")
    steps_taken: int = Field(description="Number of steps taken", default=0)


# ============= Google Sheets Update Queue =============

class GoogleSheetsQueue:
    """
    Async queue for updating Google Sheets without blocking main agent execution.
    Uses a background thread to process updates.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one queue exists"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._sheets_manager = None
        self._initialized = True
        
        # Register cleanup on program exit
        atexit.register(self.stop)
    
    def start(self):
        """Start the background worker thread"""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        print("    [GoogleSheetsQueue] Background worker started")
    
    def stop(self):
        """Stop the background worker thread gracefully"""
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            # Add sentinel to unblock the queue
            self._queue.put(None)
            self._worker_thread.join(timeout=5)
            print("    [GoogleSheetsQueue] Background worker stopped")
    
    def _get_sheets_manager(self):
        """Lazy initialization of Google Sheets manager"""
        if self._sheets_manager is None:
            try:
                from job_hunter.google_sheets import GoogleSheetsManager
                self._sheets_manager = GoogleSheetsManager()
                print("    [GoogleSheetsQueue] Google Sheets manager initialized")
            except Exception as e:
                print(f"    [GoogleSheetsQueue] Failed to initialize Google Sheets: {e}")
                return None
        return self._sheets_manager
    
    def _process_queue(self):
        """Background worker that processes queued updates"""
        while self._running:
            try:
                # Wait for an item with timeout to allow checking _running flag
                item = self._queue.get(timeout=1.0)
                
                if item is None:  # Sentinel to stop
                    break
                
                action = item.get("action")
                data = item.get("data")
                
                manager = self._get_sheets_manager()
                if manager is None:
                    print(f"    [GoogleSheetsQueue] Skipping update - no sheets manager")
                    continue
                
                if action == "add_application":
                    success = manager.add_application(data)
                    if success:
                        print(f"    [GoogleSheetsQueue] Added application: {data.get('job_title', 'Unknown')} at {data.get('company', 'Unknown')}")
                    else:
                        print(f"    [GoogleSheetsQueue] Failed to add application")
                
                elif action == "update_status":
                    success = manager.update_application_status(
                        data.get("apply_link"),
                        data.get("status")
                    )
                    if success:
                        print(f"    [GoogleSheetsQueue] Updated status to: {data.get('status')}")
                
                elif action == "bulk_add":
                    count = manager.bulk_add_applications(data.get("applications", []))
                    print(f"    [GoogleSheetsQueue] Bulk added {count} applications")
                
                self._queue.task_done()
                
            except queue.Empty:
                continue  # Timeout, check _running and continue
            except Exception as e:
                print(f"    [GoogleSheetsQueue] Error processing queue item: {e}")
    
    def enqueue_application(self, job_data: Dict[str, Any]):
        """
        Add a job application to the queue for async update.
        
        Args:
            job_data: Dictionary with job application details
        """
        # Start worker if not running
        if not self._running:
            self.start()
        
        # Transform JobListing format to Google Sheets format
        application_data = {
            "company": job_data.get("company", ""),
            "job_title": job_data.get("title", job_data.get("job_title", "")),
            "apply_link": job_data.get("apply_link", ""),
            "date_applied": datetime.now().strftime('%Y-%m-%d'),
            "salary": job_data.get("salary", ""),
            "job_type": job_data.get("job_type", ""),
            "location": job_data.get("location", ""),
            "status": job_data.get("application_status", "Applied")
        }
        
        self._queue.put({
            "action": "add_application",
            "data": application_data
        })
        print(f"    [GoogleSheetsQueue] Queued: {application_data.get('job_title')} at {application_data.get('company')}")
    
    def enqueue_status_update(self, apply_link: str, status: str):
        """Queue a status update for an existing application"""
        if not self._running:
            self.start()
        
        self._queue.put({
            "action": "update_status",
            "data": {"apply_link": apply_link, "status": status}
        })
    
    def enqueue_bulk_applications(self, applications: List[Dict[str, Any]]):
        """Queue multiple applications for bulk update"""
        if not self._running:
            self.start()
        
        formatted = []
        for job in applications:
            formatted.append({
                "company": job.get("company", ""),
                "job_title": job.get("title", job.get("job_title", "")),
                "apply_link": job.get("apply_link", ""),
                "date_applied": datetime.now().strftime('%Y-%m-%d'),
                "salary": job.get("salary", ""),
                "job_type": job.get("job_type", ""),
                "location": job.get("location", ""),
                "status": job.get("application_status", "Applied")
            })
        
        self._queue.put({
            "action": "bulk_add",
            "data": {"applications": formatted}
        })
        print(f"    [GoogleSheetsQueue] Queued bulk add: {len(formatted)} applications")
    
    def get_queue_size(self) -> int:
        """Get the current queue size"""
        return self._queue.qsize()
    
    def wait_for_completion(self, timeout: Optional[float] = None):
        """Wait for all queued items to be processed"""
        self._queue.join()


# Global queue instance
_sheets_queue = GoogleSheetsQueue()


class DroidRunAgent:
    """
    DroidRun-based agent for local Android automation.

    This is used as a backup when MobileRun Cloud is unavailable,
    or when EXECUTION_MODE is set to 'local'.

    Requires:
    - Connected Android device via ADB
    - DroidRun package: pip install 'droidrun[google]'
    - Google Gemini API key
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize DroidRun agent with configuration from Config class"""
        self.available = False
        self.error_message = ""
        self.device_serial = Config.ADB_DEVICE_SERIAL or Config.get_connected_device_serial()
        self.llm_provider = Config.DROIDRUN_LLM_PROVIDER
        self.llm_model = Config.DROIDRUN_LLM_MODEL
        self.gemini_api_key = Config.GEMINI_API_KEY

        # Task tracking (sync execution, so tasks complete immediately)
        self._completed_tasks: Dict[str, Dict] = {}

        self._check_availability()

    def _check_availability(self):
        """Check if DroidRun and required dependencies are available"""
        try:
            from droidrun import DroidAgent, DroidrunConfig
            from llama_index.llms.google_genai import GoogleGenAI

            if not self.device_serial:
                self.error_message = "No ADB device connected"
                return

            if self.llm_provider == "google" and not self.gemini_api_key:
                self.error_message = "GEMINI_API_KEY required for Google provider"
                return

            self.available = True
            print(f"DroidRun agent initialized with device: {self.device_serial}")

        except ImportError as e:
            self.error_message = f"DroidRun not installed: {e}. Install with: pip install 'droidrun[google]'"

    def is_available(self) -> bool:
        """Check if DroidRun is available and configured"""
        return self.available

    def _get_llm(self):
        """Get the configured LLM instance"""
        if self.llm_provider == "google":
            from llama_index.llms.google_genai import GoogleGenAI
            return GoogleGenAI(
                api_key=self.gemini_api_key,
                model=self.llm_model
            )
        elif self.llm_provider == "openai":
            from llama_index.llms.openai import OpenAI
            import os
            return OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                model=self.llm_model
            )
        elif self.llm_provider == "anthropic":
            from llama_index.llms.anthropic import Anthropic
            return Anthropic(
                api_key=Config.ANTHROPIC_API_KEY,
                model=self.llm_model
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    async def _run_agent(self, goal: str, output_model: Optional[type] = None, max_steps: int = 50) -> Dict:
        """Run a DroidRun agent with the given goal"""
        import traceback
        print(f"    DEBUG: _run_agent starting...")
        
        try:
            from droidrun import DroidAgent, DroidrunConfig, AdbTools, AgentConfig, CodeActConfig, ManagerConfig, ExecutorConfig
            print(f"    DEBUG: DroidRun imports successful")
        except ImportError as e:
            print(f"    DEBUG: Failed to import DroidRun: {e}")
            raise

        try:
            # Initialize tools for the connected device
            tools = AdbTools(serial=self.device_serial) if self.device_serial else AdbTools()
            print(f"    DEBUG: AdbTools initialized for device: {self.device_serial}")

            # Get LLM
            llm = self._get_llm()
            print(f"    DEBUG: LLM initialized: {self.llm_provider}/{self.llm_model}")

            # Create config with vision enabled and custom max_steps
            config = DroidrunConfig(
                agent=AgentConfig(
                    max_steps=max_steps,
                    reasoning=True,
                    codeact=CodeActConfig(vision=True),
                    manager=ManagerConfig(vision=True),
                    executor=ExecutorConfig(vision=True)
                )
            )
            print(f"    DEBUG: Config max_steps set to: {config.agent.max_steps} with vision enabled")

            # Build agent kwargs - note: DroidAgent uses 'timeout' not 'max_steps'
            agent_kwargs = {
                "goal": goal,
                "llms": llm,
                "tools": tools,
                "config": config,
                "timeout": Config.AGENT_EXECUTION_TIMEOUT,  # timeout in seconds
            }

            if output_model:
                agent_kwargs["output_model"] = output_model
                print(f"    DEBUG: Using output_model: {output_model.__name__}")

            # Create and run agent
            print(f"    DEBUG: Creating DroidAgent...")
            agent = DroidAgent(**agent_kwargs)
            
            print(f"    DEBUG: Running DroidAgent...")
            result_event = await agent.run()
            print(f"    DEBUG: DroidAgent completed. Result type: {type(result_event)}")
            
            # Convert ResultEvent to dict format expected by the rest of the codebase
            # ResultEvent has: success, reason, steps, structured_output
            result = {
                "success": getattr(result_event, "success", False),
                "reason": getattr(result_event, "reason", ""),
                "steps_taken": getattr(result_event, "steps", 0),
                "structured_output": getattr(result_event, "structured_output", None),
                "output": {}
            }
            
            # If there's a structured output, convert it to dict
            if result["structured_output"] is not None:
                if hasattr(result["structured_output"], "model_dump"):
                    result["output"] = result["structured_output"].model_dump()
                elif hasattr(result["structured_output"], "dict"):
                    result["output"] = result["structured_output"].dict()
            
            print(f"    DEBUG: Converted result: success={result['success']}, steps={result['steps_taken']}")

            return result
        except Exception as e:
            print(f"    DEBUG: Exception in _run_agent: {type(e).__name__}: {e}")
            print(f"    DEBUG: Traceback: {traceback.format_exc()}")
            raise

    def _run_sync(self, goal: str, output_model: Optional[type] = None, max_steps: int = 50) -> Dict:
        """Run agent synchronously (wraps async)"""
        import traceback
        print(f"    DEBUG: _run_sync called with goal (first 100 chars): {goal[:100]}...")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new thread
                print("    DEBUG: Event loop already running, using ThreadPoolExecutor")
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._run_agent(goal, output_model, max_steps)
                    )
                    result = future.result(timeout=Config.AGENT_EXECUTION_TIMEOUT)
                    print(f"    DEBUG: Task completed. Success: {result.get('success', 'unknown')}")
                    return result
            else:
                print("    DEBUG: Running in existing event loop")
                result = loop.run_until_complete(self._run_agent(goal, output_model, max_steps))
                print(f"    DEBUG: Task completed. Success: {result.get('success', 'unknown')}")
                return result
        except RuntimeError as e:
            # No event loop, create one
            print(f"    DEBUG: RuntimeError, creating new event loop: {e}")
            result = asyncio.run(self._run_agent(goal, output_model, max_steps))
            print(f"    DEBUG: Task completed. Success: {result.get('success', 'unknown')}")
            return result
        except Exception as e:
            print(f"    DEBUG: Exception in _run_sync: {type(e).__name__}: {e}")
            print(f"    DEBUG: Traceback: {traceback.format_exc()}")
            raise

    def create_task(self,
                   task_prompt: str,
                   max_steps: int = 50,
                   execution_timeout: int = 300,
                   apps: Optional[List[str]] = None,
                   output_schema: Optional[Dict] = None,
                   reasoning: bool = True,
                   vision: bool = True) -> Dict:
        """
        Create and execute a task (synchronously for DroidRun).

        Unlike MobileRun which is async, DroidRun executes synchronously.
        The task ID returned can be used with get_task_status() which will
        return the already-completed result.
        """
        if not self.available:
            raise Exception(f"DroidRun not available: {self.error_message}")

        task_id = str(uuid.uuid4())
        start_time = datetime.now()

        try:
            result = self._run_sync(task_prompt, max_steps=max_steps)

            # Handle output - use the already-converted output dict from _run_agent
            output = result.get("output", {})
            
            # Store completed task result
            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "completed",
                "succeeded": result.get("success", False),
                "output": output,
                "steps": result.get("steps_taken", 0),
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"    DEBUG: create_task failed with error: {error_msg}")
            print(f"    DEBUG: Full traceback: {traceback.format_exc()}")
            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "failed",
                "succeeded": False,
                "output": {},
                "error": error_msg,
                "steps": 0,
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        return {"id": task_id}

    def get_task_status(self, task_id: str) -> Dict:
        """Get the status and results of a completed task"""
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]

        return {
            "id": task_id,
            "status": "unknown",
            "succeeded": False,
            "output": {},
            "error": "Task not found"
        }

    def search_jobs_on_portal(self,
                             portal_url: str,
                             keywords: List[str],
                             location: Optional[str] = None,
                             max_steps: int = 30,
                             auto_apply: bool = False,
                             resume_data: Optional[Any] = None,
                             user_preferences: Optional[Dict] = None) -> Dict:
        """
        Search for jobs on a specific portal using DroidRun.

        Opens Chrome, navigates to the portal, and searches for jobs.
        Optionally applies to relevant jobs automatically.
        """
        if not self.available:
            raise Exception(f"DroidRun not available: {self.error_message}")

        location_text = f" in {location}" if location else ""
        keywords_text = ", ".join(keywords[:3])

        # Build task list for memory/tracking
        task_list = """
## TASK CHECKLIST (Update status as you complete each):
- [ ] Task 1: Open Chrome browser
- [ ] Task 2: Navigate to job portal
- [ ] Task 3: Enter search keywords in search box
- [ ] Task 4: Apply location filter if available
- [ ] Task 5: Extract job #1 details (title, company, location, salary)
- [ ] Task 6: Extract job #2 details
- [ ] Task 7: Extract job #3 details
- [ ] Task 8: Extract job #4 details  
- [ ] Task 9: Extract job #5 details
- [ ] Task 10: STOP and return structured output
"""

        # Improved goal prompt with anti-loop instructions
        goal = f"""
# MISSION: Search for jobs and extract listings

## CRITICAL RULES TO AVOID LOOPS:
1. DO NOT scroll more than 3 times total
2. DO NOT extract the same job twice - check company+title before adding
3. After collecting 5 unique jobs, IMMEDIATELY stop and return results
4. If you've done the same action twice with no new results, STOP
5. Track your progress using the task checklist below

## SEARCH PARAMETERS:
- Portal: {portal_url}
- Keywords: {keywords_text}
- Location: {location_text if location_text else "Any"}

## STEP-BY-STEP INSTRUCTIONS:

### Phase 1: Navigate (Max 3 steps)
1. Open Chrome browser
2. Go to {portal_url}
3. Find and click the search box

### Phase 2: Search (Max 3 steps)
4. Type: {keywords_text}
5. If there's a location field, enter: {location if location else "skip this"}
6. Click Search/Submit button OR press Enter

### Phase 3: Extract Jobs (Max 5 jobs, then STOP)
For EACH job listing visible on screen, extract:
- title: Job title text
- company: Company name  
- location: Remote/Onsite/Hybrid + city
- job_type: Full-time/Part-time/Contract/Internship
- salary: Salary if shown, otherwise "Not specified"
- apply_link: The URL or button to apply
- posted_date: When posted

### Phase 4: STOP Condition
Once you have extracted 5 UNIQUE jobs (different company+title combinations):
- DO NOT scroll again
- DO NOT look for more jobs
- IMMEDIATELY use request_accomplished with the job data

{task_list}

## ANTI-LOOP SAFEGUARDS:
- If job listings look the same as before scrolling → STOP, you have enough
- If search returns 0 results → STOP and return empty list
- If page is loading indefinitely → STOP and return what you have
- Maximum scrolls allowed: 2
"""

        task_id = str(uuid.uuid4())
        start_time = datetime.now()

        try:
            result = self._run_sync(goal, output_model=JobSearchResult, max_steps=max_steps)

            # Convert structured output to dict format matching MobileRun API
            output = {}
            if result.get("structured_output"):
                structured = result["structured_output"]
                if hasattr(structured, "model_dump"):
                    output = structured.model_dump()
                elif hasattr(structured, "dict"):
                    output = structured.dict()
                else:
                    output = {"jobs": [], "portal": portal_url, "search_keywords": keywords}
            else:
                output = result.get("output", {"jobs": [], "portal": portal_url, "search_keywords": keywords})

            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "completed",
                "succeeded": result.get("success", False),
                "output": output,
                "steps": result.get("steps_taken", 0),
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"    DEBUG: search_jobs_on_portal failed with error: {error_msg}")
            print(f"    DEBUG: Full traceback: {traceback.format_exc()}")
            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "failed",
                "succeeded": False,
                "output": {"jobs": [], "portal": portal_url, "search_keywords": keywords},
                "error": error_msg,
                "steps": 0,
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        return {"id": task_id}

    def search_and_apply_jobs(self,
                             portal_url: str,
                             keywords: List[str],
                             resume_data: Any,
                             user_preferences: Dict,
                             location: Optional[str] = None,
                             max_applications: int = 3,
                             max_steps: int = 60) -> Dict:
        """
        Search for jobs AND apply to relevant ones in a single workflow.
        
        This combines search + apply to avoid context switching issues.
        Results are queued for async Google Sheets update.
        """
        if not self.available:
            raise Exception(f"DroidRun not available: {self.error_message}")

        location_text = f" in {location}" if location else ""
        keywords_text = ", ".join(keywords[:3])
        
        # Format resume data for prompt
        experience_text = self._format_experience(
            resume_data.experience if hasattr(resume_data, 'experience') else []
        )
        education_text = self._format_education(
            resume_data.education if hasattr(resume_data, 'education') else []
        )
        preferences_text = self._format_preferences(user_preferences)
        skills_text = ", ".join(resume_data.skills[:10] if hasattr(resume_data, 'skills') else [])

        # Comprehensive goal with memory/task tracking
        goal = f"""
# MISSION: Search for jobs, find relevant ones, and APPLY to up to {max_applications} jobs

## YOUR PROFILE (for matching relevance):
- Skills: {skills_text}
- Experience Level: {len(resume_data.experience) if hasattr(resume_data, 'experience') else 0} positions
- Looking for: {keywords_text}

## CRITICAL ANTI-LOOP RULES:
1. You have a MAXIMUM of {max_steps} steps total - budget wisely
2. DO NOT scroll more than 2 times during job search
3. After finding 5 jobs, STOP searching and START applying
4. If an application form is complex (>10 fields), SKIP and try next job
5. If you encounter CAPTCHA, skip that job immediately
6. Track completed tasks in memory - never repeat a completed task

## MEMORY - TASK TRACKER (Update as you go):
```
PHASE 1 - SEARCH:
[ ] Opened Chrome
[ ] Navigated to {portal_url}
[ ] Searched for: {keywords_text}
[ ] Collected Job 1: [title] at [company] - Relevance: [1-10]
[ ] Collected Job 2: [title] at [company] - Relevance: [1-10]
[ ] Collected Job 3: [title] at [company] - Relevance: [1-10]
[ ] Collected Job 4: [title] at [company] - Relevance: [1-10]
[ ] Collected Job 5: [title] at [company] - Relevance: [1-10]

PHASE 2 - APPLY (to top {max_applications} relevant jobs):
[ ] Applied to Job: [title] at [company] - Result: [success/failed/skipped]
[ ] Applied to Job: [title] at [company] - Result: [success/failed/skipped]
[ ] Applied to Job: [title] at [company] - Result: [success/failed/skipped]

PHASE 3 - DONE:
[ ] Returned structured output with all results
```

## PHASE 1: SEARCH (Budget: 15 steps max)

1. Open Chrome and go to {portal_url}
2. Search for: {keywords_text}{location_text}
3. For each visible job, quickly assess:
   - Does title match my skills? 
   - Is location acceptable? ({location if location else "Any"})
   - Rate relevance 1-10
4. Extract details for TOP 5 most relevant jobs
5. STOP searching after 5 jobs collected

## PHASE 2: APPLY (Budget: 40 steps max)

For the TOP {max_applications} jobs by relevance score:

6. Click "Apply" or "Easy Apply" button
7. Fill application form with:
   - Name: {resume_data.full_name if hasattr(resume_data, 'full_name') else 'See resume'}
   - Email: {resume_data.email if hasattr(resume_data, 'email') else 'See resume'}
   - Phone: {resume_data.phone if hasattr(resume_data, 'phone') else 'See resume'}
   - Location: {resume_data.location if hasattr(resume_data, 'location') else 'See resume'}
   
8. For work authorization questions:
   {preferences_text}

9. If resume upload required: Note "needs_resume_upload" and continue
10. Click Submit/Apply button
11. Record result (success/failed/needs_clarification)
12. Go back and apply to next job

## PHASE 3: COMPLETE

13. After applying to {max_applications} jobs OR exhausting options:
    - DO NOT search for more jobs
    - Compile final results
    - Return structured output immediately

## SKIP CONDITIONS (Move to next job immediately if):
- Application requires account creation
- CAPTCHA appears
- Form has more than 15 required fields
- "Apply on company site" with complex redirect
- Already applied (shows "Applied" badge)

## OUTPUT STRUCTURE:
Return jobs_found (all 5 collected), jobs_applied (successful applications),
and jobs_skipped (with reason) in the structured output.
"""

        task_id = str(uuid.uuid4())
        start_time = datetime.now()

        try:
            result = self._run_sync(goal, output_model=JobSearchAndApplyResult, max_steps=max_steps)

            # Convert structured output
            output = {}
            if result.get("structured_output"):
                structured = result["structured_output"]
                if hasattr(structured, "model_dump"):
                    output = structured.model_dump()
                elif hasattr(structured, "dict"):
                    output = structured.dict()
            else:
                output = result.get("output", {
                    "jobs_found": [],
                    "jobs_applied": [],
                    "jobs_skipped": [],
                    "portal": portal_url,
                    "search_keywords": keywords
                })

            # Queue successful applications for async Google Sheets update
            jobs_applied = output.get("jobs_applied", [])
            if jobs_applied:
                for job in jobs_applied:
                    job_data = job if isinstance(job, dict) else job.model_dump() if hasattr(job, 'model_dump') else {}
                    job_data["application_status"] = "Applied"
                    _sheets_queue.enqueue_application(job_data)
                print(f"    [DroidRunAgent] Queued {len(jobs_applied)} applications for Google Sheets")

            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "completed",
                "succeeded": result.get("success", False),
                "output": output,
                "steps": result.get("steps_taken", 0),
                "jobs_found": len(output.get("jobs_found", [])),
                "jobs_applied": len(output.get("jobs_applied", [])),
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"    DEBUG: search_and_apply_jobs failed: {error_msg}")
            print(f"    DEBUG: Traceback: {traceback.format_exc()}")
            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "failed",
                "succeeded": False,
                "output": {"jobs_found": [], "jobs_applied": [], "jobs_skipped": []},
                "error": error_msg,
                "steps": 0,
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        return {"id": task_id}

    def apply_to_job(self,
                    apply_url: str,
                    resume_data,  # ResumeData object
                    user_preferences: Dict,
                    max_steps: int = 40,
                    job_title: str = "",
                    company: str = "") -> Dict:
        """
        Apply to a job using DroidRun agent.

        Navigates to the job application page and fills out the form.
        Queues successful applications for async Google Sheets update.
        """
        if not self.available:
            raise Exception(f"DroidRun not available: {self.error_message}")

        # Format experience and education
        experience_text = self._format_experience(resume_data.experience if hasattr(resume_data, 'experience') else [])
        education_text = self._format_education(resume_data.education if hasattr(resume_data, 'education') else [])
        preferences_text = self._format_preferences(user_preferences)
        skills_text = ", ".join(resume_data.skills[:10] if hasattr(resume_data, 'skills') else [])

        # Improved goal with clear steps and anti-loop safeguards
        goal = f"""
# MISSION: Complete job application at {apply_url}

## ANTI-LOOP RULES:
1. Maximum {max_steps} steps - you MUST finish within this budget
2. If a form field doesn't apply to you, skip it or select "N/A"
3. If stuck on same page for 3 steps, click Submit anyway or STOP
4. Do NOT refresh the page
5. Do NOT go back to search results

## TASK CHECKLIST (Mark as complete):
[ ] Step 1: Navigate to application URL
[ ] Step 2: Click Apply/Easy Apply button if needed
[ ] Step 3: Fill personal info (name, email, phone)
[ ] Step 4: Answer experience questions
[ ] Step 5: Answer any screening questions
[ ] Step 6: Handle resume upload (if required)
[ ] Step 7: Review and Submit
[ ] Step 8: Confirm submission, return result

## APPLICATION DATA:

### Personal Information:
- Full Name: {resume_data.full_name if hasattr(resume_data, 'full_name') else 'Not provided'}
- Email: {resume_data.email if hasattr(resume_data, 'email') else 'Not provided'}
- Phone: {resume_data.phone if hasattr(resume_data, 'phone') else 'Not provided'}
- Location: {resume_data.location if hasattr(resume_data, 'location') else 'Not provided'}

### Work Experience (use most recent):
{experience_text}

### Education:
{education_text}

### Key Skills:
{skills_text}

### Work Authorization & Preferences:
{preferences_text}

## FORM FILLING INSTRUCTIONS:

1. NAVIGATE: Go to {apply_url}
   - If it opens a popup, work within the popup
   - If it redirects, follow the redirect once only

2. PERSONAL INFO: Fill all required fields marked with *
   - First name, Last name (split full name if needed)
   - Email, Phone as provided above
   - Current location/city

3. EXPERIENCE QUESTIONS: Common patterns:
   - "Years of experience with X" → Count from experience above
   - "Are you authorized to work in..." → Use authorization info above
   - "Willing to relocate?" → Use preferences above
   - "Salary expectations" → If required, enter "Negotiable" or market rate

4. RESUME UPLOAD:
   - If file upload is REQUIRED and blocking: Set status="needs_resume_upload"
   - If file upload is OPTIONAL: Skip it and continue

5. SCREENING QUESTIONS:
   - Answer honestly based on provided info
   - For questions you can't answer, note them in questions_needing_clarification

6. SUBMIT:
   - Find and click "Submit", "Apply", "Send Application" button
   - Wait for confirmation message
   - If confirmation appears → status="completed"
   - If error appears → status="failed", note the error

## ABORT CONDITIONS (Return immediately with failure):
- CAPTCHA detected → status="captcha_required"
- Account creation required → status="failed", error="Account creation required"
- Page won't load after 10 seconds → status="failed", error="Page timeout"
- Form has >20 required fields → status="failed", error="Form too complex"

## OUTPUT:
Return ApplicationResult with accurate status, any questions needing clarification,
and error messages if applicable.
"""

        task_id = str(uuid.uuid4())
        start_time = datetime.now()

        try:
            result = self._run_sync(goal, output_model=ApplicationResult, max_steps=max_steps)

            # Convert structured output
            output = {}
            if result.get("structured_output"):
                structured = result["structured_output"]
                if hasattr(structured, "model_dump"):
                    output = structured.model_dump()
                elif hasattr(structured, "dict"):
                    output = structured.dict()
                else:
                    output = {"status": "completed" if result.get("success") else "failed", "steps_taken": 0}
            else:
                output = {
                    "status": "completed" if result.get("success") else "failed",
                    "steps_taken": result.get("steps_taken", 0),
                    "error_message": result.get("error", "")
                }

            # Queue for Google Sheets update if application was successful
            if output.get("status") == "completed":
                _sheets_queue.enqueue_application({
                    "title": job_title or output.get("job_title", ""),
                    "company": company or output.get("company", ""),
                    "apply_link": apply_url,
                    "application_status": "Applied"
                })

            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "completed",
                "succeeded": result.get("success", False),
                "output": output,
                "steps": result.get("steps_taken", 0),
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        except Exception as e:
            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "failed",
                "succeeded": False,
                "output": {"status": "failed", "error_message": str(e), "steps_taken": 0},
                "error": str(e),
                "steps": 0,
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        return {"id": task_id}

    def google_search_jobs(self, keywords: List[str], location: Optional[str] = None, max_steps: int = 30) -> Dict:
        """
        Perform Google search for job listings.
        Improved with anti-loop safeguards.
        """
        if not self.available:
            raise Exception(f"DroidRun not available: {self.error_message}")

        location_text = f" in {location}" if location else ""
        keywords_text = " ".join(keywords[:3])

        goal = f"""
# MISSION: Find job listings via Google Search

## ANTI-LOOP RULES:
1. Maximum 2 scrolls on Google results
2. Collect info from what's visible, don't hunt for more
3. After collecting 8 job listings, STOP immediately
4. If same results appear after scroll, you're done

## TASK CHECKLIST:
[ ] Open Chrome browser
[ ] Go to google.com  
[ ] Search: "{keywords_text} jobs{location_text}"
[ ] Extract jobs from Google Jobs widget (if visible)
[ ] Note 3-5 job portal URLs from results
[ ] Collect up to 8 job listings
[ ] STOP and return results

## SEARCH QUERY:
"{keywords_text} jobs{location_text}"

## WHAT TO EXTRACT:

### From Google Jobs Widget (cards at top):
For each job card visible:
- title: Job title
- company: Company name
- location: City/Remote
- posted_date: "X days ago"

### From Regular Search Results:
Job portal URLs to note:
- Indeed.com links
- LinkedIn.com/jobs links  
- Glassdoor.com links
- Other job sites

## STOP CONDITIONS:
- Collected 8 jobs → STOP
- Scrolled 2 times → STOP
- No more job results visible → STOP

## OUTPUT:
Return GoogleSearchResult with jobs list and job_portals list.
Do NOT continue searching after meeting stop conditions.
"""

        task_id = str(uuid.uuid4())
        start_time = datetime.now()

        try:
            result = self._run_sync(goal, output_model=GoogleSearchResult, max_steps=max_steps)

            # Convert structured output
            output = {}
            if result.get("structured_output"):
                structured = result["structured_output"]
                if hasattr(structured, "model_dump"):
                    output = structured.model_dump()
                elif hasattr(structured, "dict"):
                    output = structured.dict()
                else:
                    output = {"jobs": [], "job_portals": []}
            else:
                output = result.get("output", {"jobs": [], "job_portals": []})

            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "completed",
                "succeeded": result.get("success", False),
                "output": output,
                "steps": result.get("steps_taken", 0),
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        except Exception as e:
            self._completed_tasks[task_id] = {
                "id": task_id,
                "status": "failed",
                "succeeded": False,
                "output": {"jobs": [], "job_portals": []},
                "error": str(e),
                "steps": 0,
                "created_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        return {"id": task_id}

    def _format_experience(self, experience: List[Dict[str, str]]) -> str:
        """Format work experience for prompt"""
        if not experience:
            return "No work experience provided"

        formatted = []
        for exp in experience[:3]:
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

    # ============= Google Sheets Queue Methods =============

    def get_sheets_queue_size(self) -> int:
        """Get the current size of the Google Sheets update queue"""
        return _sheets_queue.get_queue_size()

    def wait_for_sheets_updates(self, timeout: Optional[float] = None):
        """Wait for all pending Google Sheets updates to complete"""
        _sheets_queue.wait_for_completion(timeout)

    def queue_job_for_sheets(self, job_data: Dict[str, Any]):
        """Manually queue a job for Google Sheets update"""
        _sheets_queue.enqueue_application(job_data)

    def queue_bulk_jobs_for_sheets(self, jobs: List[Dict[str, Any]]):
        """Queue multiple jobs for bulk Google Sheets update"""
        _sheets_queue.enqueue_bulk_applications(jobs)


# ============= Convenience Functions =============

def get_sheets_queue() -> GoogleSheetsQueue:
    """Get the global Google Sheets queue instance"""
    return _sheets_queue
