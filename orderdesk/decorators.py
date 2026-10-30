from functools import wraps

from flask import abort
from flask.ext.login import current_user

from extensions import login_manager


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated():
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


editor_required = role_required('admin', 'clerk')
admin_required = role_required('admin')
