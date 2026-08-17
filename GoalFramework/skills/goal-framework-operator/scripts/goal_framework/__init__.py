"""Public interface for the bundled goal-framework command."""

from . import model
from .cli import build_parser, dispatch, main
from .model import GoalFrameworkError, Project

__all__ = [
    "GoalFrameworkError",
    "Project",
    "build_parser",
    "dispatch",
    "main",
    "model",
]
