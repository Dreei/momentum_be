# src/routers/__init__.py - Router package initialization
"""
API Routers Package

This package contains all the FastAPI routers organized by domain:
- auth: Authentication and user management
- user: User CRUD operations
- organization: Organization management
- project: Project management  
- meeting: Meeting management
- agenda: Meeting agenda management
- zoom: Zoom integration and OAuth

Each router focuses on a specific domain and uses services for business logic.
"""

from . import (
    auth,
    user,
    organization, 
    project,
    meeting,
    agenda,
    zoom,
    summary,
    notification
)

__all__ = [
    "auth",
    "user", 
    "organization",
    "project",
    "meeting",
    "agenda",
    "zoom"
    
    "summary",
    "notification"
]
# src/routers/__init__.py
# This file makes the routers directory a Python package

# Import all routers to make them available
try:
    from .action_items import router as action_items_router
except ImportError as e:
    print(f"Could not import action_items router: {e}")

try:
    from .search import router as search_router
except ImportError as e:
    print(f"Could not import search router: {e}")

# Import existing routers
try:
    from .organization import router as organization_router
except ImportError as e:
    print(f"Could not import organization router: {e}")

try:
    from .project import router as project_router
except ImportError as e:
    print(f"Could not import project router: {e}")

try:
    from .meeting import router as meeting_router
except ImportError as e:
    print(f"Could not import meeting router: {e}")

try:
    from .agenda import router as agenda_router
except ImportError as e:
    print(f"Could not import agenda router: {e}")

try:
    from .zoom import router as zoom_router
except ImportError as e:
    print(f"Could not import zoom router: {e}")

try:
    from .recall import router as recall_router
except ImportError as e:
    print(f"Could not import recall router: {e}")

try:
    from .user import router as user_router
except ImportError as e:
    print(f"Could not import user router: {e}")

try:
    from .auth import router as auth_router
except ImportError as e:
    print(f"Could not import auth router: {e}")
