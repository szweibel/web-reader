"""Error handling utilities for the screen reader application"""

from typing import Dict, Any
from langgraph.graph import END

class ReaderActionError(Exception):
    """Base class for recoverable action errors"""
    def __init__(self, message: str, action: str, context: str = ""):
        self.action = action
        self.context = context
        super().__init__(message)

class ElementNotFoundError(ReaderActionError):
    """Raised when an element cannot be found"""
    pass

class NavigationError(ReaderActionError):
    """Raised when navigation fails"""
    pass

class InteractionError(ReaderActionError):
    """Raised when element interaction fails"""
    pass

class ContentError(ReaderActionError):
    """Raised when content cannot be read or processed"""
    pass

def create_error_response(message: str) -> Dict[str, Any]:
    """Create a standard error response"""
    return {
        "messages": [{"role": "assistant", "content": message}],
        "next": END
    }

def handle_error(error: Exception) -> Dict[str, Any]:
    """Handle different types of errors"""
    if isinstance(error, ReaderActionError):
        return {
            "error": str(error),
            "error_context": {
                "action": error.action,
                "context": error.context
            },
            "messages": [{"role": "assistant", "content": str(error)}],
            "next": None  # Allow error recovery to handle
        }
    return create_error_response(str(error))
