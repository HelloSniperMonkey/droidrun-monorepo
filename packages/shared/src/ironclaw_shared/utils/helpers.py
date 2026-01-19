"""
Common helper functions used across Iron Claw services.
"""
import re
import uuid
from typing import Optional, Tuple


def generate_task_id(prefix: str = "task") -> str:
    """Generate a unique task ID."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to remove unsafe characters.
    Security: Prevents path traversal attacks.
    """
    # Remove path separators and null bytes
    filename = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")
    # Remove leading dots (hidden files)
    filename = filename.lstrip(".")
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:250] + ("." + ext if ext else "")
    return filename or "unnamed"


def truncate_text(text: str, max_length: int = 2000, suffix: str = "...") -> str:
    """Truncate text to a maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def parse_time_string(time_str: str) -> Optional[Tuple[int, int]]:
    """
    Parse a time string like "07:30" or "7:30 AM" into (hour, minute).
    Returns None if parsing fails.
    """
    # Try 24-hour format first
    match = re.match(r"^(\d{1,2}):(\d{2})$", time_str.strip())
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)
        return None

    # Try 12-hour format with AM/PM
    match = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", time_str.strip(), re.IGNORECASE)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        period = match.group(3).upper()

        if hour < 1 or hour > 12 or minute > 59:
            return None

        if period == "PM" and hour != 12:
            hour += 12
        elif period == "AM" and hour == 12:
            hour = 0

        return (hour, minute)

    return None


def format_phone_number(phone: str) -> str:
    """
    Format a phone number to E.164 format.
    Assumes US number if no country code provided.
    """
    # Remove all non-digit characters except leading +
    cleaned = re.sub(r"[^\d+]", "", phone)

    # If starts with +, assume it's already international
    if cleaned.startswith("+"):
        return cleaned

    # If 10 digits, assume US number
    if len(cleaned) == 10:
        return f"+1{cleaned}"

    # If 11 digits starting with 1, assume US with country code
    if len(cleaned) == 11 and cleaned.startswith("1"):
        return f"+{cleaned}"

    # Return as-is with + prefix
    return f"+{cleaned}" if not cleaned.startswith("+") else cleaned
