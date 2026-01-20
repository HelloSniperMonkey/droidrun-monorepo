"""
Step Parser Utility.

Parses verbose agent logs to extract structured step information
for display in the frontend chat interface.
"""

import re
import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class StepInfo:
    """Represents a single step in agent execution."""

    step_number: int
    total_steps: int
    description: str
    action: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_step_logs(logs: str) -> list[StepInfo]:
    """
    Parse verbose agent logs into structured StepInfo list.

    Extracts:
    - Step markers: 🔄 Step X/Y
    - Descriptions: ### Description ### followed by text
    - Actions: {"action": "...", ...} JSON

    Args:
        logs: Raw log string from agent execution

    Returns:
        List of StepInfo objects
    """
    if not logs:
        return []

    steps: list[StepInfo] = []
    lines = logs.split("\n")

    current_step_num = 0
    current_total = 0
    current_description = ""
    current_action = ""

    # Patterns
    step_pattern = re.compile(r"🔄 Step (\d+)/(\d+)")
    desc_pattern = re.compile(r"### Description ###")
    action_pattern = re.compile(r'\{"action":\s*"([^"]+)"')
    # Pattern to strip timestamp and logger prefixes like "2026-01-20 12:44:12,551 - droidrun - INFO - "
    timestamp_prefix_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - [\w\.]+ - \w+ - "
    )
    # Pattern to strip PM2/gateway log prefixes like "0|gateway  | "
    log_prefix_pattern = re.compile(r"^\d+\|[\w\-]+\s*\|\s*")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Strip timestamp and PM2 prefixes before processing
        clean_line = timestamp_prefix_pattern.sub("", line)
        clean_line = log_prefix_pattern.sub("", clean_line)
        clean_line = clean_line.strip()

        # Check for step marker
        step_match = step_pattern.search(clean_line)
        if step_match:
            # Save previous step if exists
            if current_step_num > 0 and current_description:
                steps.append(
                    StepInfo(
                        step_number=current_step_num,
                        total_steps=current_total,
                        description=current_description.strip(),
                        action=current_action if current_action else None,
                    )
                )

            current_step_num = int(step_match.group(1))
            current_total = int(step_match.group(2))
            current_description = ""
            current_action = ""
            i += 1
            continue

        # Check for description marker
        if desc_pattern.search(clean_line):
            # Get the next non-empty line as description
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                desc_line = lines[j]
                # Strip all prefixes
                desc_line = timestamp_prefix_pattern.sub("", desc_line)
                desc_line = log_prefix_pattern.sub("", desc_line)
                current_description = desc_line.strip()
            i = j + 1
            continue

        # Check for action JSON
        action_match = action_pattern.search(clean_line)
        if action_match:
            current_action = action_match.group(1)

        i += 1

    # Don't forget the last step
    if current_step_num > 0 and current_description:
        steps.append(
            StepInfo(
                step_number=current_step_num,
                total_steps=current_total,
                description=current_description.strip(),
                action=current_action if current_action else None,
            )
        )

    return steps


def format_steps_for_response(steps: list[StepInfo]) -> list[dict]:
    """Convert StepInfo list to dict list for JSON response."""
    return [step.to_dict() for step in steps]


def extract_step_summary(logs: str) -> str:
    """
    Extract a brief summary of steps from logs.

    Returns a condensed string like:
    "Step 1/30: Clicking element... → Step 2/30: Scrolling..."
    """
    steps = parse_step_logs(logs)
    if not steps:
        return ""

    summaries = []
    for step in steps[:5]:  # Limit to first 5 steps for summary
        desc = step.description[:50] + "..." if len(step.description) > 50 else step.description
        summaries.append(f"Step {step.step_number}/{step.total_steps}: {desc}")

    result = " → ".join(summaries)
    if len(steps) > 5:
        result += f" ... (+{len(steps) - 5} more steps)"

    return result
