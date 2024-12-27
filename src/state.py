from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from selenium.webdriver.remote.webelement import WebElement
from selenium import webdriver
import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class PageContext:
    """Rich context about the current page"""
    type: str
    has_main: bool
    has_nav: bool
    has_article: bool
    has_headlines: bool
    has_forms: bool
    dynamic_content: bool
    scroll_position: float
    viewport_height: int
    total_height: int

@dataclass
class ElementContext:
    """Context about the current element"""
    tag_name: str
    role: str
    text: str
    is_clickable: bool
    is_visible: bool
    location: Dict[str, int]
    attributes: Dict[str, str]

@dataclass
class ActionPrediction:
    """Predictions about needed interactions"""
    needs_scroll: bool
    needs_click: bool
    needs_wait: bool
    potential_popups: bool
    confidence: float
    reasoning: str

class State(TypedDict):
    """Enhanced state object with rich context"""
    # Core state
    messages: Annotated[list, add_messages]
    driver: webdriver.Chrome
    
    # Browser state
    current_element_index: int
    focusable_elements: list
    last_found_element: WebElement | None
    
    # Rich context
    page_context: PageContext
    element_context: ElementContext | None
    predictions: ActionPrediction | None
    learned_patterns: List[Dict[str, Any]]
    
    # Action state
    current_action: str | None
    action_context: str
    attempts: int
    last_successful_actions: List[str]
    
    # Task management
    sub_tasks: List[str]
    task_dependencies: Dict[str, List[str]]
    completed_tasks: List[str]
    
    # Execution tracking
    execution_history: List[Dict[str, Any]]
    error: str | None
    strategy: str | None
    recovery_attempts: Dict[str, int]
def create_initial_state(driver: webdriver.Chrome, user_input: str) -> State:
    """Create enhanced initial state with rich context"""
    return State({
        # Core state
        "messages": [{"role": "user", "content": user_input}],
        "driver": driver,
        
        # Browser state
        "current_element_index": -1,
        "focusable_elements": [],
        "last_found_element": None,
        
        # Rich context
        "page_context": PageContext(
            type="unknown",
            has_main=False,
            has_nav=False,
            has_article=False,
            has_headlines=False,
            has_forms=False,
            dynamic_content=False,
            scroll_position=0,
            viewport_height=0,
            total_height=0
        ),
        "element_context": None,
        "predictions": None,
        "learned_patterns": [],
        
        # Action state
        "current_action": None,
        "action_context": "",
        "attempts": 0,
        "last_successful_actions": [],
        
        # Task management
        "sub_tasks": [],
        "task_dependencies": {},
        "completed_tasks": [],
        
        # Execution tracking
        "execution_history": [],
        "error": None,
        "strategy": None,
        "recovery_attempts": {}
    })
