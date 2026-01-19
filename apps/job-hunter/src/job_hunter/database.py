"""MongoDB integration for storing job portals and user preferences"""
from pymongo import MongoClient
from typing import Dict, List, Optional
from datetime import datetime
from job_hunter.config import Config


class MongoDBManager:
    """Manage MongoDB operations for job portals and user data"""

    def __init__(self):
        self.client = MongoClient(Config.MONGODB_URI)
        self.db = self.client[Config.MONGODB_DB_NAME]

        # Collections
        self.job_portals = self.db['job_portals']
        self.user_preferences = self.db['user_preferences']
        self.application_history = self.db['application_history']
        self.job_listings = self.db['job_listings']

        # Create indexes
        self._create_indexes()

    def _create_indexes(self):
        """Create database indexes for better performance"""
        self.job_portals.create_index("url", unique=True)
        self.user_preferences.create_index("user_id", unique=True)
        self.application_history.create_index([("user_id", 1), ("date_applied", -1)])
        self.job_listings.create_index([("apply_link", 1), ("user_id", 1)], unique=True)

    # Job Portals Management
    def add_job_portal(self, url: str, name: str, category: Optional[str] = None) -> bool:
        """Add a new job portal to the database"""
        try:
            portal = {
                "url": url,
                "name": name,
                "category": category,
                "added_date": datetime.now(),
                "last_used": None,
                "success_rate": 0.0,
                "total_applications": 0
            }
            self.job_portals.insert_one(portal)
            return True
        except Exception as e:
            print(f"Error adding job portal: {e}")
            return False

    def get_all_job_portals(self) -> List[Dict]:
        """Get all job portals from database"""
        return list(self.job_portals.find({}, {"_id": 0}))

    def update_portal_stats(self, url: str, successful: bool = True):
        """Update job portal statistics after application"""
        portal = self.job_portals.find_one({"url": url})
        if portal:
            total = portal.get("total_applications", 0) + 1
            successful_count = int(portal.get("success_rate", 0) * portal.get("total_applications", 0))
            if successful:
                successful_count += 1

            self.job_portals.update_one(
                {"url": url},
                {
                    "$set": {
                        "last_used": datetime.now(),
                        "total_applications": total,
                        "success_rate": successful_count / total
                    }
                }
            )

    def initialize_default_portals(self):
        """Initialize database with default job portals"""
        for url in Config.DEFAULT_JOB_PORTALS:
            name = url.split("//")[1].split("/")[0].replace("www.", "").title()
            try:
                self.add_job_portal(url, name, category="General")
            except:
                pass  # Portal already exists

    # User Preferences Management
    def save_user_preferences(self, user_id: str, preferences: Dict) -> bool:
        """Save user preferences for repetitive questions"""
        try:
            pref_doc = {
                "user_id": user_id,
                "preferences": preferences,
                "last_updated": datetime.now()
            }
            self.user_preferences.update_one(
                {"user_id": user_id},
                {"$set": pref_doc},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error saving user preferences: {e}")
            return False

    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Get user preferences"""
        user_pref = self.user_preferences.find_one({"user_id": user_id}, {"_id": 0})
        if user_pref:
            return user_pref.get("preferences", {})
        return None

    def update_user_preference(self, user_id: str, key: str, value: any) -> bool:
        """Update a specific user preference"""
        try:
            self.user_preferences.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        f"preferences.{key}": value,
                        "last_updated": datetime.now()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error updating user preference: {e}")
            return False

    # Application History
    def save_application(self, user_id: str, application_data: Dict) -> str:
        """Save job application to history"""
        app_doc = {
            "user_id": user_id,
            "company": application_data.get("company"),
            "job_title": application_data.get("job_title"),
            "apply_link": application_data.get("apply_link"),
            "date_applied": datetime.now(),
            "deadline": application_data.get("deadline"),
            "salary": application_data.get("salary"),
            "job_type": application_data.get("job_type"),
            "location": application_data.get("location"),
            "contact": application_data.get("contact"),
            "status": application_data.get("status", "Applied"),
            "portal": application_data.get("portal"),
            "application_id": application_data.get("application_id"),
            "steps_taken": application_data.get("steps_taken", 0)
        }

        result = self.application_history.insert_one(app_doc)
        return str(result.inserted_id)

    def get_user_applications(self, user_id: str) -> List[Dict]:
        """Get all applications for a user"""
        return list(self.application_history.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("date_applied", -1))

    def update_application_status(self, user_id: str, apply_link: str, status: str):
        """Update application status"""
        self.application_history.update_one(
            {"user_id": user_id, "apply_link": apply_link},
            {"$set": {"status": status}}
        )

    def get_application_count(self, user_id: str) -> int:
        """Get total number of applications for user"""
        return self.application_history.count_documents({"user_id": user_id})

    # Job Listings Cache
    def cache_job_listing(self, user_id: str, job_data: Dict):
        """Cache a job listing to avoid duplicate applications"""
        try:
            job_doc = {
                "user_id": user_id,
                "title": job_data.get("title"),
                "company": job_data.get("company"),
                "location": job_data.get("location"),
                "apply_link": job_data.get("apply_link"),
                "portal": job_data.get("portal"),
                "salary": job_data.get("salary"),
                "job_type": job_data.get("job_type"),
                "posted_date": job_data.get("posted_date"),
                "cached_date": datetime.now(),
                "applied": False
            }
            self.job_listings.update_one(
                {"user_id": user_id, "apply_link": job_data.get("apply_link")},
                {"$set": job_doc},
                upsert=True
            )
        except Exception as e:
            print(f"Error caching job listing: {e}")

    def mark_job_as_applied(self, user_id: str, apply_link: str):
        """Mark a cached job as applied"""
        self.job_listings.update_one(
            {"user_id": user_id, "apply_link": apply_link},
            {"$set": {"applied": True}}
        )

    def is_job_already_applied(self, user_id: str, apply_link: str) -> bool:
        """Check if user already applied to this job"""
        job = self.job_listings.find_one({
            "user_id": user_id,
            "apply_link": apply_link,
            "applied": True
        })
        return job is not None

    def get_cached_jobs(self, user_id: str, applied: bool = False) -> List[Dict]:
        """Get cached job listings"""
        return list(self.job_listings.find(
            {"user_id": user_id, "applied": applied},
            {"_id": 0}
        ).sort("cached_date", -1))

    def close(self):
        """Close database connection"""
        self.client.close()
