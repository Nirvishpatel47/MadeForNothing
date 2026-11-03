"""
MADE FOR NOTHING — Database Facade
===================================
Re-exports all modular database operations and schemas from the `database` package.
This maintains 100% backward-compatibility for all existing modules and scripts
(`import db`, `from db import ...`) while allowing modular imports from `database.*`.
"""

from database import *
import database

__all__ = database.__all__