from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi.templating import Jinja2Templates

PARIS_TZ = ZoneInfo("Europe/Paris")


def to_paris(dt: datetime) -> datetime:
    """Convert a naive UTC datetime to Paris time."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(PARIS_TZ)


def create_templates(directory: str = "templates") -> Jinja2Templates:
    """Create a Jinja2Templates instance with custom filters."""
    templates = Jinja2Templates(directory=directory)
    templates.env.filters["paris"] = to_paris
    return templates
