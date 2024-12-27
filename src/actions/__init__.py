"""Action registry and management for the screen reader application"""

import json
from typing import Dict, Any, List, Optional
import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import core dependencies
from src.state import State
from src.utils.logging import logger
from src.utils.errors import create_error_response
import src.config as config

# Import base functionality
from .base import (
    register_action,
    create_result,
    actions,
    ActionFunction
)

# Import all action modules to register their actions via decorators
from . import navigation
from . import reading
from . import interaction

def get_action(name: str) -> ActionFunction:
    """Get an action function by name"""
    logger.debug(f"Available actions: {list(actions.keys())}")
    logger.debug(f"Requested action: {name}")
    if name not in actions:
        raise ValueError(f"Unknown action: {name}")
    return actions[name]

def get_action_prompt(state: State) -> str:
    """Generate the action prompt from user input"""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    
    prompt = f"""Analyze this user message and determine the next action: "{last_message}"
    
    Available actions and their use cases:
    - navigate: Go to website/URL (e.g., "go to", "open", "visit")
    - read: Read page content (e.g., "what does it say", "where am I")
    - click: Click elements (e.g., "click", "press", "select")
    - check: Check element properties (e.g., "is this clickable", "is that a link")
    - list_headings: Show headings (e.g., "show headings", "what are the headings")
    - list_headlines: Show news headlines (e.g., "read headlines", "list headlines", "show news", "what are the headlines")
    - goto_headline: Go to a specific headline (e.g., "go to headline 1", "read article 3", "open headline 2")
    - find: Search text (e.g., "find", "search", "locate")
    - next: Next element (e.g., "next", "forward")
    - prev: Previous element (e.g., "previous", "back") 
    - goto: Go to section (e.g., "go to main", "jump to nav")
    - list_landmarks: Show landmarks (e.g., "list landmarks", "show sections", "read landmarks")
    - read_section: Read current section (e.g., "read this part", "read current section")

    IMPORTANT: For "read headlines" command, use list_headlines action, not read action.

    The message may contain multiple actions (e.g., "go to nytimes.com and read headlines").
    In this case, identify the first action to perform.

    Return JSON with:
    - action: One of the exact action names listed above
    - confidence: How confident (0-1)
    - context: Any extracted context needed (e.g., URL, text to click)
    - next_action: Optional, if there's a follow-up action in the command
    - next_context: Optional, context for the follow-up action
    
    Example for single action: '{{"action": "navigate", "confidence": 0.95, "context": "google.com"}}'
    Example for compound action: '{{"action": "navigate", "confidence": 0.95, "context": "nytimes.com", "next_action": "list_headlines", "next_context": ""}}'"""
    
    # Add current state context if available
    page_context = state.get("page_context")
    page_type = None
    if page_context:
        if isinstance(page_context, dict) and page_context.get("type"):
            page_type = page_context.get("type")
        elif hasattr(page_context, 'type') and page_context.type:
            page_type = page_context.type
            
    page_suggestions = state.get("page_suggestions", [])
    if page_type:
        prompt += f"\nCurrent page type: {page_type}"
        if page_suggestions:
            prompt += f"\nSuggested actions: {', '.join(page_suggestions)}"
            
    return prompt

def determine_action(state: State) -> Dict[str, Any]:
    """Determine which action to take based on user input and page type"""
    try:
        # Get prompt and LLM response
        try:
            prompt = get_action_prompt(state)
            logger.debug(f"Generated action prompt: {prompt}")
        except Exception as e:
            logger.error(f"Error in get_action_prompt: {str(e)}")
            error_msg = f"Sorry, I encountered an error in get_action_prompt: {str(e)}"
            logger.log_error(error_msg)
            return create_result(error=error_msg)
        
        try:
            response = config.llm.invoke(prompt)
            logger.debug(f"LLM response: {response}")
            logger.debug(f"LLM raw response: {response.content}")
            
            # Parse the JSON response
            parsed_response = json.loads(response.content)
            action = parsed_response.get("action")
            confidence = parsed_response.get("confidence", 0)
            context = parsed_response.get("context")
            next_action = parsed_response.get("next_action")
            next_context = parsed_response.get("next_context")
            
            # Validate action and confidence
            if not action or action not in config.VALID_ACTIONS:
                return {
                    "error": "I'm not sure what action you want to take. Could you rephrase your request?",
                    "next": "error_recovery"
                }
                
            # Check confidence threshold
            page_context = state.get("page_context")
            has_page_type = False
            if page_context:
                if isinstance(page_context, dict):
                    has_page_type = bool(page_context.get("type"))
                else:  # PageContext object
                    has_page_type = bool(page_context.type)
                    
            threshold = 0.6 if has_page_type else 0.7
            if confidence < threshold:
                error_msg = (f"I'm not sure what you want to do. You can try: {', '.join(state['page_suggestions'])}"
                          if state.get("page_suggestions")
                          else "I'm not sure about that action. Could you be more specific?")
                return {
                    "error": error_msg,
                    "next": "error_recovery"
                }
            
            # Return successful result
            return {
                "current_action": action,
                "action_context": context,
                "next_action": next_action,
                "next_context": next_context,
                "next": config.VALID_ACTIONS[action]
            }
        except Exception as e:
            logger.error(f"Error in LLM processing: {str(e)}")
            return create_result(error=f"Failed to process command: {str(e)}")
    except Exception as e:
        logger.error(f"Error in determine_action: {str(e)}")
        return create_result(error="Sorry, I encountered an error determining the action")
