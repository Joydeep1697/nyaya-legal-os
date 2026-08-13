import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger("nova-legal-app")

def extract_deadlines(text: str, metadata: dict) -> list[dict]:
    """
    Extracts dates and deadlines from legal text using common patterns.
    Returns list of {type, date (ISO), description, status} dicts.
    """
    deadlines = []
    now = datetime.now()
    try:
        # Patterns
        patterns = {
            "relative": r"within\s+(\d+)\s+(days|months|years)",
            "absolute": r"(?:on or before|by|expires on|valid until|renewal)\s+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\,?\s+\d{4})",
            "limitation": r"limitation period.*(\d+)\s+(years|months)",
            "filing": r"shall file.*?by\s+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})"
        }
        
        # Parse relative
        for match in re.finditer(patterns["relative"], text, re.IGNORECASE):
            amount = int(match.group(1))
            unit = match.group(2).lower()
            
            # Approximation for relative dates from "now" or doc date
            base_date = now # simplified
            if "day" in unit:
                target_date = base_date + timedelta(days=amount)
            elif "month" in unit:
                target_date = base_date + timedelta(days=amount * 30)
            else:
                target_date = base_date + timedelta(days=amount * 365)
                
            status = _get_status(target_date, now)
            deadlines.append({
                "type": "relative_deadline",
                "date": target_date.isoformat(),
                "description": match.group(0),
                "status": status
            })
            
        # Parse absolute
        for match in re.finditer(patterns["absolute"], text, re.IGNORECASE):
            date_str = match.group(1)
            parsed_date = _parse_date(date_str)
            if parsed_date:
                status = _get_status(parsed_date, now)
                dl_type = "expiry" if "expire" in match.group(0).lower() or "valid" in match.group(0).lower() else "deadline"
                deadlines.append({
                    "type": dl_type,
                    "date": parsed_date.isoformat(),
                    "description": match.group(0),
                    "status": status
                })
                
    except Exception as e:
        logger.error(f"Error extracting deadlines: {e}")
        
    return deadlines

def _parse_date(date_str: str):
    """Helper to parse common Indian date formats."""
    date_str = re.sub(r'(st|nd|rd|th)', '', date_str) # clean suffix
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %B, %Y", "%d %B %Y", "%d %b %Y", "%d %b, %Y"]
    for f in formats:
        try:
            return datetime.strptime(date_str.strip(), f)
        except ValueError:
            continue
    return None

def _get_status(target_date: datetime, now: datetime) -> str:
    """Helper to determine status based on date."""
    delta = (target_date - now).days
    if delta < 0:
        return "overdue"
    elif delta <= 30:
        return "upcoming"
    return "future"
