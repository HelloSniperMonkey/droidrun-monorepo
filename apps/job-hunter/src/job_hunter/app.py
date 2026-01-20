"""Flask web application for viewing job applications"""

from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
from job_hunter.config import Config
from job_hunter.database import MongoDBManager
from job_hunter.google_sheets import GoogleSheetsManager
from job_hunter.orchestrator import JobApplicationOrchestrator
import os
from werkzeug.utils import secure_filename
from pathlib import Path

# Get the directory where this module is located
MODULE_DIR = Path(__file__).parent

app = Flask(__name__, template_folder=str(MODULE_DIR / "templates"))
app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY
app.config["UPLOAD_FOLDER"] = str(MODULE_DIR.parent.parent / "data" / "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

# Enable CORS for all routes (allows frontend at localhost:3000 to call this API)
CORS(
    app,
    origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8000",
        "http://localhost:8080",
    ],
)

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize managers
db = MongoDBManager()


@app.route("/")
def index():
    """Home page with dashboard"""
    return render_template("index.html")


@app.route("/api/applications/<user_id>")
def get_applications(user_id):
    """Get all applications for a user"""
    try:
        applications = db.get_user_applications(user_id)
        return jsonify({"success": True, "applications": applications, "count": len(applications)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/applications/google-sheets")
def get_applications_from_sheets():
    """Get applications from Google Sheets"""
    try:
        sheets = GoogleSheetsManager()
        applications = sheets.get_all_applications()
        return jsonify({"success": True, "applications": applications, "count": len(applications)})
    except FileNotFoundError as e:
        # Credentials file not found - return empty list
        return jsonify(
            {
                "success": True,
                "applications": [],
                "count": 0,
                "message": "Google Sheets not configured yet",
            }
        )
    except Exception as e:
        return jsonify(
            {"success": False, "error": str(e), "applications": [], "count": 0}
        ), 200  # Return 200 to prevent UI error


@app.route("/api/applications/<user_id>/status", methods=["POST"])
def update_application_status(user_id):
    """Update application status"""
    try:
        data = request.json
        apply_link = data.get("apply_link")
        new_status = data.get("status")

        if not apply_link or not new_status:
            return jsonify({"success": False, "error": "Missing apply_link or status"}), 400

        # Update in MongoDB
        db.update_application_status(user_id, apply_link, new_status)

        # Update in Google Sheets
        sheets = GoogleSheetsManager()
        sheets.update_application_status(apply_link, new_status)

        return jsonify({"success": True, "message": "Status updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/preferences/<user_id>")
def get_preferences(user_id):
    """Get user preferences"""
    try:
        preferences = db.get_user_preferences(user_id)
        return jsonify({"success": True, "preferences": preferences or {}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/preferences/<user_id>", methods=["POST"])
def save_preferences(user_id):
    """Save user preferences"""
    try:
        preferences = request.json
        db.save_user_preferences(user_id, preferences)
        return jsonify({"success": True, "message": "Preferences saved successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats/<user_id>")
def get_stats(user_id):
    """Get application statistics"""
    try:
        applications = db.get_user_applications(user_id)

        stats = {
            "total_applications": len(applications),
            "status_breakdown": {},
            "job_types": {},
            "locations": {},
            "recent_applications": applications[:5] if applications else [],
        }

        for app in applications:
            # Status breakdown
            status = app.get("status", "Unknown")
            stats["status_breakdown"][status] = stats["status_breakdown"].get(status, 0) + 1

            # Job types
            job_type = app.get("job_type", "Unknown")
            stats["job_types"][job_type] = stats["job_types"].get(job_type, 0) + 1

            # Locations
            location = app.get("location", "Unknown")
            stats["locations"][location] = stats["locations"].get(location, 0) + 1

        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/upload-resume", methods=["POST"])
def upload_resume():
    """Upload and process resume"""
    try:
        if "resume" not in request.files:
            return jsonify({"success": False, "error": "No resume file provided"}), 400

        file = request.files["resume"]
        user_id = request.form.get("user_id", "default_user")

        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        if file and file.filename.endswith(".pdf"):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            # Start job application process
            orchestrator = JobApplicationOrchestrator(user_id)
            result = orchestrator.run(filepath)
            orchestrator.cleanup()

            return jsonify(
                {
                    "success": True,
                    "message": "Resume processed and job applications started",
                    "result": result,
                }
            )
        else:
            return jsonify({"success": False, "error": "Only PDF files are supported"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/job-portals")
def get_job_portals():
    """Get all job portals"""
    try:
        portals = db.get_all_job_portals()
        return jsonify({"success": True, "portals": portals})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def run_app():
    """Run the Flask application"""
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=True,
        use_reloader=False,  # Disable reloader to prevent restarts when other agents modify files
    )


if __name__ == "__main__":
    run_app()
