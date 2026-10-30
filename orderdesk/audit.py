from extensions import db
from models import AuditEntry


def record(user, action, object_type, object_id, detail=None):
    """Add an audit entry to the session. Caller is responsible for commit."""
    entry = AuditEntry(user_id=getattr(user, 'id', None), action=action,
                       object_type=object_type, object_id=object_id, detail=detail)
    db.session.add(entry)
    return entry
