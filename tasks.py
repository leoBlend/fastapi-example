import logging

from database import SessionLocal
from models import AuditLog

logger = logging.getLogger(__name__)


def write_audit_log(username: str, action: str, detail: str = "") -> None:
    # Background tasks run after the request session is closed, so they open their own DB session.
    db = SessionLocal()
    try:
        entry = AuditLog(username=username, action=action, detail=detail)
        db.add(entry)
        db.commit()
        logger.info("Audit: [%s] %s — %s", username, action, detail)
    except Exception:
        logger.exception("Failed to write audit log for action '%s' by '%s'", action, username)
    finally:
        db.close()
