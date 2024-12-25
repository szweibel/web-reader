#!/usr/bin/env python3
import json
import logging
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain_ollama import ChatOllama
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import time

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create formatters
detailed_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
simple_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# Create file handlers with proper file modes
debug_handler = logging.FileHandler('logs/debug.log', mode='w', encoding='utf-8')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(detailed_formatter)

info_handler = logging.FileHandler('logs/info.log', mode='w', encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(simple_formatter)

error_handler = logging.FileHandler('logs/error.log', mode='w', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(detailed_formatter)

# Ensure logger is not propagating to avoid duplicate logs
logger.propagate = False

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(simple_formatter)

# Add handlers to logger
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)

class State(TypedDict):
    messages: Annotated[list, add_messages]
    driver: webdriver.Chrome
    current_element_index: int
    focusable_elements: list
    current_action: str | None
    action_confidence: float
    action_context: str
    last_found_element: webdriver.remote.webelement.WebElement | None

def get_focusable_elements(driver):
    """Get all focusable elements on the page"""
    focusable_selectors = [
        "a[href]", "button", "input", "select", "textarea",
        "[tabindex]:not([tabindex='-1'])", "[contenteditable='true']",
        "[role='button']", "[role='link']", "[role='menuitem']"
    ]
    elements = driver.find_elements(By.CSS_SELECTOR, ", ".join(focusable_selectors))
    return [e for e in elements if e.is_displayed()]

def get_landmarks_and_anchors(driver):
    """Get all ARIA landmarks and anchor points"""
    seen_elements = set()  # Track elements we've already added
    landmarks = []
    
    def add_landmark(elem, desc_prefix, text=None):
        """Helper to add landmark if not already seen"""
        if elem not in seen_elements and elem.is_displayed():
            text = text or elem.text.strip()
            if text:
                seen_elements.add(elem)
                landmarks.append((elem, f"{desc_prefix}: {text[:100]}"))
    
    # Find elements with ARIA roles
    for role in ["banner", "complementary", "contentinfo", "form", "main", "navigation", "region", "search"]:
        elements = driver.find_elements(By.CSS_SELECTOR, f"[role='{role}']")
        for elem in elements:
            add_landmark(elem, role)
    
    # Find elements with standard HTML5 landmark tags
    for tag in ["header", "nav", "main", "aside", "footer", "form", "section"]:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for elem in elements:
            add_landmark(elem, tag)
    
    # Add headings as landmarks
    for level in range(1, 7):
        elements = driver.find_elements(By.TAG_NAME, f"h{level}")
        for elem in elements:
            add_landmark(elem, f"heading {level}")
    
    # Add elements with aria-label or title
    elements = driver.find_elements(By.CSS_SELECTOR, "[aria-label], [title]")
    for elem in elements:
        label = elem.get_attribute("aria-label") or elem.get_attribute("title")
        if label:
            add_landmark(elem, "labeled section", label)
    
    # Add div elements with specific class names
    section_classes = ["section", "content", "main", "header", "footer", "nav"]
    for class_name in section_classes:
        elements = driver.find_elements(By.CSS_SELECTOR, f"div[class*='{class_name}' i]")
        for elem in elements:
            add_landmark(elem, "section")
    
    return landmarks


def setup_browser():
    """Initialize headless Chrome browser"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-pipe")
    return webdriver.Chrome(options=chrome_options)

# Initialize LLM
llm = ChatOllama(
    model="llama3.2",
    format="json",
    temperature=0,
    prefix="""You are a screen reader assistant that helps users navigate and understand web content.
    You can navigate to URLs, read page content, click elements, and find specific text.
    Always be clear and concise in describing what you find on the page.
    Always respond with a valid JSON object containing exactly these fields:
    {
        "action": "one of the allowed actions",
        "confidence": number between 0 and 1,
        "context": "any relevant context"
    }"""
)

# Define valid actions mapping
VALID_ACTIONS = {
    "navigate": "navigate",
    "read": "read_page",
    "click": "click_element",
    "check": "check_element",
    "list_headings": "list_headings",
    "find": "find_text",
    "next": "next_element",
    "prev": "prev_element",
    "list_landmarks": "list_landmarks",
    "goto": "goto_landmark",
    "read_section": "read_section"
}

def get_action_prompt(state: State) -> str:
    """Generate the action prompt from user input"""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    return f"""Analyze this user message and determine the next action: "{last_message}"
    
    Available actions and their use cases:
    - navigate: Go to website/URL (e.g., "go to", "open", "visit")
    - read: Read page content (e.g., "read", "what does it say", "where am I")
    - click: Click elements (e.g., "click", "press", "select")
    - check: Check element properties (e.g., "is this clickable", "is that a link")
    - list_headings: Show headings (e.g., "show headings", "what are the headings")
    - find: Search text (e.g., "find", "search", "locate")
    - next: Next element (e.g., "next", "forward")
    - prev: Previous element (e.g., "previous", "back") 
    - goto: Go to section (e.g., "go to main", "jump to nav")
    - list_landmarks: Show landmarks (e.g., "list landmarks", "show sections")
    - read_section: Read current section (e.g., "read this part")

    Return JSON with:
    - action: One of the exact action names listed above
    - confidence: How confident (0-1)
    - context: Any extracted context needed (e.g., URL, text to click)
    
    Example: {{"action": "navigate", "confidence": 0.95, "context": "google.com"}}"""

def determine_action(state: State) -> dict:
    """Determine which action to take based on user input"""
    try:
        # Get prompt from state
        prompt = get_action_prompt(state)
        
        # Get LLM response
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Clean up response
        content = content.replace("'", '"').replace('\n', ' ')
        if not content.startswith('{'):
            content = '{' + content.split('{', 1)[1]
        if not content.endswith('}'):
            content = content.rsplit('}', 1)[0] + '}'
        
        # Parse JSON
        result = json.loads(content)
        logger.debug(f"Parsed LLM response: {json.dumps(result, indent=2)}")
        
        # Validate fields
        action = result.get("action", "").lower()
        confidence = result.get("confidence", 0)
        context = result.get("context", "")
        
        if not action or confidence < 0.7 or action not in VALID_ACTIONS:
            return {
                "messages": [{"role": "assistant", "content": "I'm not sure what action you want to take. Could you rephrase your request?"}],
                "next": END
            }
            
        # Update state with Command return value
        return {
            "messages": [],
            "current_action": action,
            "action_confidence": confidence,
            "action_context": context,
            "next": VALID_ACTIONS[action]
        }
        
    except Exception as e:
        logger.error(f"Error in determine_action: {str(e)}")
        return {
            "messages": [{"role": "assistant", "content": "Sorry, I encountered an error. Could you try again?"}],
            "next": None
        }

def clarify(state: State):
    """Ask for clarification when confidence is low"""
    return {
        "messages": [{"role": "assistant", "content": "I'm not sure what action you want to take. Could you rephrase your request?"}],
        "next": None
    }

def navigate(state: State):
    """Navigate to a URL"""
    logger.debug("Entering navigate")
    url = state.get("action_context")
    logger.debug(f"Navigating to URL: {url}")
    
    if not url:
        logger.error("No URL provided in action_context")
        return {
            "messages": [{"role": "assistant", "content": "No URL provided. Please specify a URL to navigate to."}],
            "next": None
        }
        
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        logger.debug("Sending GET request")
        state["driver"].get(url)
        logger.debug("Waiting for page load")
        time.sleep(2)
        # Reset navigation state
        state["focusable_elements"] = get_focusable_elements(state["driver"])
        state["current_element_index"] = -1
        return {
            "messages": [{"role": "assistant", "content": f"Navigated to {url}. Would you like me to read the page content?"}],
            "next": None
        }
    except Exception as e:
        logger.error(f"Navigation error: {str(e)}")
        return {
            "messages": [{"role": "assistant", "content": f"Failed to navigate to {url}. Error: {str(e)}"}],
            "next": None
        }

def read_page(state: State):
    """Read the current page content"""
    logger.debug("Entering read_page")
    logger.debug("Getting page source")
    soup = BeautifulSoup(state["driver"].page_source, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "footer"]):
        tag.decompose()
    
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    content = "\n".join(lines)
    content = content[:1000] + "..." if len(content) > 1000 else content
    
    return {
        "messages": [{"role": "assistant", "content": f"Here's what I found on the page:\n\n{content}"}],
        "next": None
    }

def click_element(state: State):
    """Click an element on the page"""
    logger.debug("Entering click_element")
    element_desc = state["action_context"].lower()
    logger.debug(f"Looking for element: {element_desc}")
    
    def find_clickable(element):
        """Check if element or its children are clickable"""
        # Check if element itself is clickable
        if element.tag_name in ['a', 'button'] or element.get_attribute('onclick') or element.get_attribute('role') in ['button', 'link']:
            return element
        
        # Check children
        clickable = element.find_elements(By.CSS_SELECTOR, 'a, button, [onclick], [role="button"], [role="link"]')
        return next((e for e in clickable if e.is_displayed() and element_desc in e.text.lower()), None)
    
    def is_navigation_element(element):
        """Check if element is in navigation area"""
        try:
            # Check if element or its parents are navigation elements
            current = element
            for _ in range(3):  # Check up to 3 levels up
                if current.tag_name in ['nav', 'header'] or current.get_attribute('role') in ['navigation', 'banner']:
                    return True
                parent = state["driver"].execute_script("return arguments[0].parentElement;", current)
                if not parent:
                    break
                current = parent
            return False
        except:
            return False
    
    # First try navigation elements
    nav_strategies = [
        (By.XPATH, f"//nav//a[translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
        (By.XPATH, f"//header//a[translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
        (By.XPATH, f"//*[@role='navigation']//a[translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
        (By.XPATH, f"//nav//*[contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{element_desc}')]"),
        (By.XPATH, f"//header//*[contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{element_desc}')]")
    ]
    
    # Then try general clickable elements
    general_strategies = [
        (By.LINK_TEXT, element_desc),
        (By.XPATH, f"//a[translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
        (By.XPATH, f"//button[translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
        (By.XPATH, f"//*[@role='button' and translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
        (By.XPATH, f"//*[@role='link' and translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
        (By.PARTIAL_LINK_TEXT, element_desc),
        (By.XPATH, f"//*[contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{element_desc}')]")
    ]
    
    # Try navigation elements first
    for by, value in nav_strategies:
        try:
            elements = state["driver"].find_elements(by, value)
            for element in elements:
                if element.is_displayed() and is_navigation_element(element):
                    clickable = find_clickable(element)
                    if clickable:
                        state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", clickable)
                        time.sleep(0.5)
                        clickable.click()
                        time.sleep(1)
                        return {
                            "messages": [{"role": "assistant", "content": f"Clicked navigation element: '{clickable.text or element_desc}'. Would you like me to read the updated content?"}],
                            "next": None
                        }
        except Exception as e:
            continue
    
    # Then try general clickable elements
    for by, value in general_strategies:
        try:
            elements = state["driver"].find_elements(by, value)
            for element in elements:
                if element.is_displayed():
                    clickable = find_clickable(element)
                    if clickable:
                        state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", clickable)
                        time.sleep(0.5)
                        clickable.click()
                        time.sleep(1)
                        return {
                            "messages": [{"role": "assistant", "content": f"Clicked element: '{clickable.text or element_desc}'. Would you like me to read the updated content?"}],
                            "next": None
                        }
        except Exception as e:
            continue
    
    return {
        "messages": [{"role": "assistant", "content": f"Could not find clickable element matching '{element_desc}'. Try using the exact text as shown on the page."}],
        "next": None
    }

def check_element(state: State):
    """Check properties of the last found element"""
    try:
        element = state["last_found_element"]
        if element and element.is_displayed():
            tag_name = element.tag_name
            href = element.get_attribute("href")
            onclick = element.get_attribute("onclick")
            role = element.get_attribute("role")
            is_clickable = (
                tag_name in ["a", "button"] or
                href is not None or
                onclick is not None or
                role in ["button", "link"]
            )
            return {
                "messages": [{"role": "assistant", "content": f"{'Yes' if is_clickable else 'No'}, this {'is' if is_clickable else 'is not'} a clickable element."}],
                "next": None
            }
    except:
        pass
    return {
        "messages": [{"role": "assistant", "content": "I don't see any recently found element to check."}],
        "next": None
    }

def list_headings(state: State):
    """List all headings on the page"""
    soup = BeautifulSoup(state["driver"].page_source, "html.parser")
    headings = []
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        for heading in soup.find_all(tag):
            text = heading.get_text().strip()
            if text:
                headings.append(f"{tag.upper()}: {text}")
    
    if headings:
        content = "\n".join(headings)
        return {
            "messages": [{"role": "assistant", "content": f"Found these headings:\n\n{content}"}],
            "next": None
        }
    else:
        return {
            "messages": [{"role": "assistant", "content": "No headings found on this page."}],
            "next": None
        }

def find_text(state: State):
    """Find text on the page"""
    search_text = state["action_context"]
    strategies = [
        (By.XPATH, f"//*[contains(text(), '{search_text}')]"),
        (By.ID, search_text),
        (By.CLASS_NAME, search_text),
        (By.NAME, search_text)
    ]
    
    for by, value in strategies:
        try:
            element = state["driver"].find_element(by, value)
            state["last_found_element"] = element
            return {
                "messages": [{"role": "assistant", "content": f"Found content: {element.text}"}],
                "next": None
            }
        except:
            continue
    
    return {
        "messages": [{"role": "assistant", "content": f"Could not find content matching '{search_text}'"}],
        "next": None
    }

def next_element(state: State):
    """Move to next focusable element"""
    if "focusable_elements" not in state:
        state["focusable_elements"] = get_focusable_elements(state["driver"])
        state["current_element_index"] = -1
    
    if not state["focusable_elements"]:
        return {
            "messages": [{"role": "assistant", "content": "No focusable elements found on the page."}],
            "next": None
        }
    
    state["current_element_index"] = (state["current_element_index"] + 1) % len(state["focusable_elements"])
    element = state["focusable_elements"][state["current_element_index"]]
    
    # Scroll element into view
    state["driver"].execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(0.5)
    
    # Get element description
    tag_name = element.tag_name
    text = element.text or element.get_attribute("value") or element.get_attribute("placeholder")
    role = element.get_attribute("role") or tag_name
    state["last_found_element"] = element
    
    return {
        "messages": [{"role": "assistant", "content": f"Moved to {role}: {text}"}],
        "next": None
    }

def prev_element(state: State):
    """Move to previous focusable element"""
    if "focusable_elements" not in state:
        state["focusable_elements"] = get_focusable_elements(state["driver"])
        state["current_element_index"] = 0
    
    if not state["focusable_elements"]:
        return {
            "messages": [{"role": "assistant", "content": "No focusable elements found on the page."}],
            "next": None
        }
    
    state["current_element_index"] = (state["current_element_index"] - 1) % len(state["focusable_elements"])
    element = state["focusable_elements"][state["current_element_index"]]
    
    # Scroll element into view
    state["driver"].execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(0.5)
    
    # Get element description
    tag_name = element.tag_name
    text = element.text or element.get_attribute("value") or element.get_attribute("placeholder")
    role = element.get_attribute("role") or tag_name
    state["last_found_element"] = element
    
    return {
        "messages": [{"role": "assistant", "content": f"Moved to {role}: {text}"}],
        "next": None
    }

def list_landmarks(state: State):
    """List all landmarks and sections"""
    landmarks = get_landmarks_and_anchors(state["driver"])
    if landmarks:
        content = "\n".join(desc for _, desc in landmarks)
        return {
            "messages": [{"role": "assistant", "content": f"Found these landmarks and sections:\n\n{content}"}],
            "next": None
        }
    else:
        return {
            "messages": [{"role": "assistant", "content": "No landmarks or major sections found on this page."}],
            "next": None
        }

def goto_landmark(state: State):
    """Navigate to a specific landmark"""
    target = state["action_context"]
    landmarks = get_landmarks_and_anchors(state["driver"])
    for element, desc in landmarks:
        if target.lower() in desc.lower():
            # Scroll to landmark
            state["driver"].execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            
            # Get content
            text = element.text.strip()
            preview = text[:200] + "..." if len(text) > 200 else text
            state["last_found_element"] = element
            
            return {
                "messages": [{"role": "assistant", "content": f"Moved to {desc}. Content preview:\n\n{preview}"}],
                "next": None
            }
    
    return {
        "messages": [{"role": "assistant", "content": f"Could not find landmark or section matching '{target}'"}],
        "next": None
    }

def read_section(state: State):
    """Read the current section content"""
    if "current_element_index" not in state or not state.get("focusable_elements"):
        return {
            "messages": [{"role": "assistant", "content": "Please navigate to a section or element first using next/previous element or goto landmark."}],
            "next": None
        }
    
    element = state["focusable_elements"][state["current_element_index"]]
    text = element.text.strip()
    if not text:
        # Try to get parent section content
        parent = element
        for _ in range(3):  # Look up to 3 levels up
            parent = state["driver"].execute_script("return arguments[0].parentElement;", parent)
            if parent:
                text = parent.text.strip()
                if text:
                    break
    
    if text:
        preview = text[:500] + "..." if len(text) > 500 else text
        return {
            "messages": [{"role": "assistant", "content": f"Content of current section:\n\n{preview}"}],
            "next": None
        }
    else:
        return {
            "messages": [{"role": "assistant", "content": "No readable content found in current section."}]
            , "next": None
        }

def should_continue(state: State):
    """Determine if we should continue processing"""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    logger.debug(f"Processing last message in should_continue: {last_message}")
    
    # After listing landmarks, prompt for navigation
    if "Found these landmarks and sections:" in last_message:
        return {
            "messages": [{"role": "assistant", "content": "Which section would you like to go to? You can say 'go to [section name]'"}],
            "next": None
        }
    
    # After navigating to a section, offer to read it
    if "Moved to" in last_message and "Content preview" in last_message:
        return {
            "messages": [{"role": "assistant", "content": "Would you like me to read this section? Say 'read section' to view the content."}],
            "next": None
        }
    
    # After reading content, offer navigation options
    if "Content of current section:" in last_message:
        return {
            "messages": [{"role": "assistant", "content": "You can say 'next element' to move forward, 'previous element' to go back, or 'list landmarks' to see all sections."}],
            "next": None
        }
    
    # Default: end the chain
    return {
        "messages": [],
        "next": None
    }

# Build graph using Command pattern
workflow = StateGraph(State)

# Add nodes for each action
for action_name, node_name in VALID_ACTIONS.items():
    workflow.add_node(node_name, locals()[node_name])

# Add determine_action node that uses Command to specify next node
workflow.add_node("determine_action", determine_action)

# Add conditional edges for all actions at once
workflow.add_conditional_edges(
    "determine_action",
    lambda x: x.get("next"),
    {action: action for action in VALID_ACTIONS.values()}
)

# Set entry point and compile
workflow.set_entry_point("determine_action")
graph = workflow.compile()

class ReaderError(Exception):
    """Base error for reader operations"""
    pass

class NavigationError(ReaderError):
    """Error during page navigation"""
    pass

class ElementError(ReaderError):
    """Error finding or interacting with elements"""
    pass

def handle_error(error: Exception) -> dict:
    """Handle errors in a consistent way"""
    error_msg = str(error)
    if isinstance(error, NavigationError):
        msg = f"Failed to navigate: {error_msg}"
    elif isinstance(error, ElementError):
        msg = f"Failed to interact with element: {error_msg}"
    else:
        msg = f"An error occurred: {error_msg}"
    logger.error(msg)
    return {
        "messages": [{"role": "assistant", "content": msg}],
        "next": None
    }

def update_state_with_result(state: State, result: dict) -> dict:
    """Update state with action result and return next node"""
    if "messages" in result:
        state["messages"].extend(result["messages"])
    return {"next": result.get("next")}

def main():
    logger.info("Starting Natural Language Screen Reader")
    logger.debug("Initializing browser")
    
    try:
        driver = setup_browser()
        logger.info("Browser initialized successfully")
        
        print("You can give commands like:")
        print("- 'Go to example.com'")
        print("- 'Read the current page'")
        print("- 'Click the login button'")
        print("- 'Find text about pricing'")
        print("- 'Move to next element'")
        print("- 'Go to previous element'")
        print("- 'List all landmarks'")
        print("- 'Go to main content section'")
        print("- 'Read current section'")
        print("\nType 'exit' to quit")
        
        while True:
            try:
                user_input = input("\nWhat would you like me to do? ").strip()
                if user_input.lower() in ["exit", "quit", "q"]:
                    break
                
                state = State({
                    "messages": [{"role": "user", "content": user_input}],
                    "driver": driver,
                    "current_element_index": -1,
                    "focusable_elements": [],
                    "current_action": None,
                    "action_confidence": 0,
                    "action_context": "",
                    "last_found_element": None
                })
                
                logger.debug(f"Processing user input: {user_input}")
                for event in graph.stream(state):
                    logger.debug(f"Processing event: {event}")
                    if event is None:
                        continue
                    for key, value in event.items():
                        if isinstance(value, dict) and "messages" in value:
                            for msg in value["messages"]:
                                if isinstance(msg, dict) and msg.get("role") == "assistant":
                                    print(f"\n{msg['content']}")
                                    
            except KeyboardInterrupt:
                print("\nOperation cancelled by user")
                continue
            except ReaderError as e:
                print(f"\n{str(e)}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                print(f"\nAn unexpected error occurred. Please try again.")
                continue
                
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        print(f"\nFatal error: {str(e)}")
        
    finally:
        print("\nClosing browser...")
        try:
            driver.quit()
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")

if __name__ == "__main__":
    main()
