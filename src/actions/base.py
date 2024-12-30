"""Base action handling and determination"""

import json
from typing import Dict, Any, Optional, Callable, TypeAlias, Literal
from functools import wraps
from langchain.schema import HumanMessage
from pydantic import BaseModel
from ..utils.logging import logger
from ..config import llm
from ..state import State

# Define valid commands
Command = Literal["navigate", "read", "click", "check", "list_headings", 
                 "list_headlines", "goto_headline", "find", "next", "prev", 
                 "goto", "list_landmarks", "read_section", "error_recovery"]

class ActionResponse(BaseModel):
    """Action response"""
    action: Command
    confidence: float
    context: str

def create_result(
    messages: Optional[list] = None,
    next_step: str = "end",
    error: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a standardized result dictionary"""
    result = {
        "messages": messages or [],
        "next": next_step,
        **kwargs
    }
    if error:
        result["error"] = error
        result["next"] = "error_recovery"
    return result

def determine_action(state: State) -> Command:
    """Determine next action from user input"""
    try:
        messages = state.get('messages', [])
        if not messages:
            logger.error("No messages in state")
            return "error_recovery"
            
        user_input = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
        
        # Simple, focused prompt
        prompt = HumanMessage(content=f"""Here is a user request: "{user_input}"

Return a JSON response in this exact format:
{{
    "action": "one of [navigate, read, click, check, list_headings, list_headlines, goto_headline, find, next, prev, goto, list_landmarks, read_section]",
    "confidence": number between 0 and 1,
    "context": "relevant details (like URL or element)"
}}

Example: {{"action": "navigate", "confidence": 0.95, "context": "google.com"}}""")

        logger.debug("Sending prompt to LLM", extra={"prompt": prompt.content})
        
        # Get LLM response
        response = llm.invoke([prompt])
        logger.debug("Raw LLM response", extra={"response": str(response)})
        
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
            
        logger.debug("Parsing content", extra={"content": content})
        
        try:
            parsed = json.loads(content)
            logger.debug("Parsed response", extra={"parsed": parsed})
            
            # Validate and store in state
            validated = ActionResponse(**parsed)
            logger.debug("Validated response", extra={"validated": validated.dict()})
            
            # Store action details in state
            state["current_action"] = validated.action
            state["action_context"] = validated.context
            state["action_confidence"] = validated.confidence
            
            # Return command name
            return validated.action
            
        except Exception as e:
            logger.error(f"Response parsing error: {str(e)}")
            return "error_recovery"
            
    except Exception as e:
        logger.error(f"Action determination error: {str(e)}")
        return "error_recovery"

# Action registry
actions: Dict[Command, Callable[[State], Dict[str, Any]]] = {}

def register_action(name: Command) -> Callable:
    """Register an action handler"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: State) -> Dict[str, Any]:
            try:
                return func(state)
            except Exception as e:
                logger.error(f"Action {name} failed: {str(e)}")
                return create_result(error=str(e))
        actions[name] = wrapper
        return wrapper
    return decorator

def get_action(name: str) -> Optional[Callable]:
    """Get registered action by name"""
    return actions.get(name)