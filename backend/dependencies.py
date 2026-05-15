# backend/dependencies.py
from auth.router import get_current_user, get_current_admin
from models.user import User

__all__ = ["get_current_user", "get_current_admin", "User"]