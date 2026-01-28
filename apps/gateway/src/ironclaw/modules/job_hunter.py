"""
Job Hunter Module - Resume parsing and job application automation.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from ..agents.adb_connection import ADBConnection
from ..agents.ironclaw_agent import create_ironclaw_agent
from ..utils.config import get_app_config, get_settings

logger = logging.getLogger("ironclaw.modules.job_hunter")

# In-memory task storage (use Redis in production)
_task_storage: dict = {}


class JobHunterService:
    """
    Service for job hunting automation.

    Capabilities:
    - Parse resumes from PDF
    - Search for jobs via mobile Chrome
    - Auto-fill job applications
    """

    def __init__(self):
        self.settings = get_settings()
        self.config = get_app_config().job_hunter_config
        self.adb = ADBConnection()
        self.data_dir = Path(__file__).parent.parent.parent.parent / "data" / "uploads"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def parse_resume(self, file: UploadFile) -> dict:
        """
        Parse a resume PDF and extract structured data.

        Returns dict with:
        - name, email, phone
        - skills (list)
        - experience (list of dicts)
        - education (list of dicts)
        """
        # Save the uploaded file
        filename = file.filename or "resume.pdf"
        file_path = self.data_dir / filename
        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved resume to {file_path}")

        # Extract text from PDF
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(file_path))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""

        except ImportError:
            # Fallback: just read raw bytes for now
            text = f"[Resume uploaded: {file.filename}]"
            logger.warning("PyPDF2 not available, using placeholder text")

        # For MVP: Create a simple structured format
        # In production, use LLM to extract structured data
        bio_memory = {
            "resume_file": str(file_path),
            "resume_text": text[:2000],  # Truncate for context window
            "parsed_at": datetime.now().isoformat(),
        }

        # Save bio-memory for later use
        bio_memory_path = self.data_dir / "bio_memory.json"
        with open(bio_memory_path, "w") as f:
            json.dump(bio_memory, f, indent=2)

        # Push resume to device
        await self.adb.push_file(
            str(file_path),
            f"/sdcard/Download/{file.filename}"
        )
        logger.info("Resume pushed to device /sdcard/Download/")

        return bio_memory

    async def search_and_apply(
        self,
        query: str,
        max_applications: int = 3,
        filters: Optional[dict] = None,
        task_id: str = "",
    ) -> dict:
        """
        Search for jobs and apply automatically.

        Args:
            query: Job search query (e.g., "Senior Python Developer remote")
            max_applications: Maximum number of applications to submit
            filters: Optional filters (e.g., {"posted_within": "24h"})
            task_id: Unique task identifier for status tracking
        """
        logger.info(f"[{task_id}] Starting job search: {query}")

        # Initialize task status
        _task_storage[task_id] = {
            "status": "running",
            "query": query,
            "started_at": datetime.now().isoformat(),
            "applications_submitted": 0,
            "logs": [],
        }

        try:
            # Load bio-memory if available
            bio_memory_path = self.data_dir / "bio_memory.json"
            if bio_memory_path.exists():
                # Bio-memory is loaded into the agent via the path
                pass

            # Build the agent goal - Simplified for testing
            goal = f"""
            Find 5 Python Developer jobs and apply to them.

            Steps:
            1. Open Chrome browser
            2. Go to LinkedIn Jobs and search "Python Developer"
            3. Apply to 2 jobs using Easy Apply
            4. Go to Indeed.com and search "Python Developer"
            5. Apply to 2 jobs
            6. Go to Glassdoor and search "Python Developer"
            7. Apply to 1 job
            8. After each application, note the job title and company

            Target: Apply to 5 jobs total across these platforms.
            Use resume from /sdcard/Download/ if file upload is needed.
            Skip jobs requiring cover letters or extensive forms.
            Report each successful application.
            """

            if filters and filters.get("posted_within"):
                goal += f"\n- Filter for jobs posted within {filters['posted_within']}"

            # Create and run the agent
            agent = await create_ironclaw_agent(
                goal=goal,
                bio_memory_path=bio_memory_path,
            )

            self._log_task(task_id, "Agent created, starting execution")

            result = await agent.run()

            # Update task status
            _task_storage[task_id]["status"] = "completed" if result["success"] else "failed"
            _task_storage[task_id]["completed_at"] = datetime.now().isoformat()
            _task_storage[task_id]["result"] = result

            self._log_task(task_id, f"Completed: {result.get('reason', 'Unknown')}")

            return result

        except Exception as e:
            logger.error(f"[{task_id}] Job search failed: {e}")
            _task_storage[task_id]["status"] = "error"
            _task_storage[task_id]["error"] = str(e)
            return {"success": False, "error": str(e)}

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get the status of a job search task."""
        return _task_storage.get(task_id)

    def _log_task(self, task_id: str, message: str):
        """Add a log entry to the task."""
        if task_id in _task_storage:
            _task_storage[task_id]["logs"].append({
                "timestamp": datetime.now().isoformat(),
                "message": message,
            })
        logger.info(f"[{task_id}] {message}")
