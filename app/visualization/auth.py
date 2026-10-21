"""Prototype authentication and role-based access control.

This module implements role-appropriate authorization required by Section 9
of the TECH5 specification, supporting Administrator, Programme Coordinator,
and Student Viewer roles.
"""

import flask


class UserRole:
    """User role constants and descriptions."""

    ADMIN = "ADMIN"
    COORDINATOR = "COORDINATOR"
    STUDENT = "STUDENT"

    ALL_ROLES = {
        ADMIN: "Administrator (Full Control)",
        COORDINATOR: "Programme Coordinator (Runs & Analysis)",
        STUDENT: "Student Viewer (Read Only)",
    }


def get_current_role() -> str:
    """Retrieves the active user role from session.

    Returns:
        The active role string (defaults to ADMIN for convenience).
    """
    return flask.session.get("user_role", UserRole.ADMIN)


def set_current_role(role: str) -> None:
    """Updates the active user role in session.

    Args:
        role: Target role string.
    """
    if role in UserRole.ALL_ROLES:
        flask.session["user_role"] = role


def can_edit_cohort_data() -> bool:
    """Checks whether the current user has permission to modify cohort data.

    Returns:
        True if current role has edit permissions.
    """
    return get_current_role() in (UserRole.ADMIN,)


def can_trigger_optimization() -> bool:
    """Checks whether current user can execute optimization runs.

    Returns:
        True if user can run solver.
    """
    return get_current_role() in (UserRole.ADMIN, UserRole.COORDINATOR)
