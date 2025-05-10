# auth.py

from PySide6.QtWidgets import QMessageBox
from roles import has_permission

def require_permission(action):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            role = self.user[3] if hasattr(self, 'user') else None
            if not has_permission(role, action):
                QMessageBox.critical(None, "Permission Denied", "You do not have permission to perform this action.")
                return
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
