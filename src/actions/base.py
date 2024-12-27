"""Base classes and utilities for actions"""

from typing import Dict, Callable, Any, List, Optional
from dataclasses import dataclass
from langgraph.graph import END
from ..state import State

# Type alias for action functions
ActionFunction = Callable[[State], Dict[str, Any]]

# Registry to store all available actions
actions: Dict[str, ActionFunction] = {}

def register_action(name: str) -> Callable[[ActionFunction], ActionFunction]:
    """Decorator to register an action function"""
    def decorator(func: ActionFunction) -> ActionFunction:
        # Validate action follows patterns
        if not hasattr(func, '__annotations__'):
            raise ValueError(f"Action {name} must have type annotations")
        if not func.__annotations__.get('return'):
            raise ValueError(f"Action {name} must specify return type")
            
        actions[name] = func
        return func
    return decorator

def create_result(
    output: Any = None,
    state_updates: Dict[str, Any] = None,
    messages: List[Dict[str, str]] = None,
    next: str = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """Create a standardized action result"""
    result = {}
    if output is not None:
        result["output"] = output
    if state_updates:
        result.update(state_updates)
    if messages:
        result["messages"] = messages
    if next:
        result["next"] = next
    if error:
        result["error"] = error
        result["next"] = "error_recovery"
    return result
