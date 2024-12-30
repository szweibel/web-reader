================================================
File: /advanced_reader.py
================================================
#!/usr/bin/env python3
import json
import logging
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain_community.chat_models import ChatOllama
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
    try:
        landmarks = get_landmarks_and_anchors(state["driver"])
        if landmarks:
            content = "\n".join(desc for _, desc in landmarks)
            return {
                "messages": [{"role": "assistant", "content": f"Found these landmarks and sections:\n\n{content}"}],
                "next": END
            }
        else:
            return {
                "messages": [{"role": "assistant", "content": "No landmarks or major sections found on this page."}],
                "next": END
            }
    except Exception as e:
        logger.error(f"Error in list_landmarks: {str(e)}")
        return {
            "messages": [{"role": "assistant", "content": "An error occurred while listing landmarks. Please try again."}],
            "next": END
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
    try:
        messages = state["messages"]
        last_message = messages[-1].content if messages else ""
        logger.debug(f"Processing last message in should_continue: {last_message}")
        
        # After listing landmarks, prompt for navigation
        if "Found these landmarks and sections:" in last_message:
            return {
                "messages": [{"role": "assistant", "content": "Which section would you like to go to? You can say 'go to [section name]'"}],
                "next": END
            }
        
        # After navigating to a section, offer to read it
        if "Moved to" in last_message and "Content preview" in last_message:
            return {
                "messages": [{"role": "assistant", "content": "Would you like me to read this section? Say 'read section' to view the content."}],
                "next": END
            }
        
        # After reading content, offer navigation options
        if "Content of current section:" in last_message:
            return {
                "messages": [{"role": "assistant", "content": "You can say 'next element' to move forward, 'previous element' to go back, or 'list landmarks' to see all sections."}],
                "next": END
            }
        
        # Default: end the chain
        return {
            "messages": [],
            "next": END
        }
    except Exception as e:
        logger.error(f"Error in should_continue: {str(e)}")
        return {
            "messages": [],
            "next": END
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
    {**{action: action for action in VALID_ACTIONS.values()}, END: END}
)

# Add edges from action nodes to END
for node_name in VALID_ACTIONS.values():
    workflow.add_edge(node_name, END)

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


================================================
File: /requirements.txt
================================================
aiohappyeyeballs==2.4.4
aiohttp==3.11.11
aiosignal==1.3.2
annotated-types==0.7.0
anyio==4.7.0
asttokens==3.0.0
async-timeout==4.0.3
attrs==24.3.0
beautifulsoup4==4.12.2
black==23.12.1
boto3==1.35.87
botocore==1.35.87
cachetools==5.5.0
certifi==2024.12.14
charset-normalizer==3.4.1
click==8.1.8
coloredlogs==15.0.1
coverage==7.6.10
dataclasses-json==0.6.7
decorator==5.1.1
dill==0.3.9
distro==1.9.0
exceptiongroup==1.2.2
executing==2.1.0
fastembed==0.4.2
filelock==3.16.1
filetype==1.2.0
flake8==7.0.0
flatbuffers==24.12.23
free-proxy==1.1.3
frozenlist==1.5.0
fsspec==2024.12.0
google-ai-generativelanguage==0.6.10
google-api-core==2.24.0
google-api-python-client==2.156.0
google-auth==2.37.0
google-auth-httplib2==0.2.0
google-generativeai==0.8.3
googleapis-common-protos==1.66.0
googlesearch-python==1.2.5
greenlet==3.1.1
grpcio==1.68.1
grpcio-status==1.68.1
grpcio-tools==1.68.1
h11==0.14.0
h2==4.1.0
hpack==4.0.0
html2text==2024.2.26
httpcore==1.0.7
httplib2==0.22.0
httpx==0.27.2
httpx-sse==0.4.0
huggingface-hub==0.27.0
humanfriendly==10.0
hyperframe==6.0.1
idna==3.10
iniconfig==2.0.0
ipython==8.31.0
isort==5.13.2
jedi==0.19.2
jiter==0.8.2
jmespath==1.0.1
jsonpatch==1.33
jsonpointer==3.0.0
jsonschema==4.23.0
jsonschema-specifications==2024.10.1
langchain==0.3.13
langchain-aws==0.2.10
langchain-community==0.3.13
langchain-core==0.3.28
langchain-google-genai==2.0.7
langchain-mistralai==0.2.4
langchain-ollama==0.2.2
langchain-openai==0.2.14
langchain-text-splitters==0.3.4
langchainhub==0.1.21
langgraph==0.2.60
langgraph-checkpoint==2.0.9
langgraph-sdk==0.1.48
langsmith==0.1.147
loguru==0.7.3
lxml==5.3.0
marshmallow==3.23.2
matplotlib-inline==0.1.7
mccabe==0.7.0
minify_html==0.15.0
mmh3==4.1.0
mpire==2.10.2
mpmath==1.3.0
msgpack==1.1.0
multidict==6.1.0
multiprocess==0.70.17
mypy==1.8.0
mypy-extensions==1.0.0
numpy==1.26.4
ollama==0.4.4
onnx==1.17.0
onnxruntime==1.19.2
openai==1.58.1
orjson==3.10.12
outcome==1.3.0.post0
packaging==24.2
pandas==2.2.3
parso==0.8.4
pathspec==0.12.1
pexpect==4.9.0
pillow==10.4.0
platformdirs==4.3.6
playwright==1.49.1
pluggy==1.5.0
portalocker==2.10.1
prompt_toolkit==3.0.48
propcache==0.2.1
proto-plus==1.25.0
protobuf==5.29.2
ptyprocess==0.7.0
pure_eval==0.2.3
py_rust_stemmers==0.1.3
pyasn1==0.6.1
pyasn1_modules==0.4.1
pycodestyle==2.11.1
pydantic==2.9.2
pydantic-settings==2.7.0
pydantic_core==2.23.4
pyee==12.0.0
pyflakes==3.2.0
Pygments==2.18.0
pyparsing==3.2.0
PySocks==1.7.1
pytest==7.4.3
pytest-cov==4.1.0
python-dateutil==2.9.0.post0
python-dotenv==1.0.1
pytz==2024.2
PyYAML==6.0.2
qdrant-client==1.12.1
referencing==0.35.1
regex==2024.11.6
requests==2.32.3
requests-toolbelt==1.0.0
rpds-py==0.22.3
rsa==4.9
s3transfer==0.10.4
safetensors==0.4.5
selenium==4.16.0
semchunk==2.2.2
sentencepiece==0.2.0
simpleeval==1.0.3
six==1.17.0
sniffio==1.3.1
sortedcontainers==2.4.0
soupsieve==2.6
SQLAlchemy==2.0.36
stack-data==0.6.3
sympy==1.13.3
tenacity==8.5.0
tokenizers==0.21.0
tomli==2.2.1
tqdm==4.67.1
traitlets==5.14.3
transformers==4.47.1
trio==0.27.0
trio-websocket==0.11.1
types-requests==2.32.0.20241016
typing-inspect==0.9.0
typing_extensions==4.9.0
tzdata==2024.2
undetected-playwright==0.3.0
uritemplate==4.1.1
urllib3==2.3.0
wcwidth==0.2.13
-e git+https://github.com/szweibel/web-reader.git@6ecabec1bbafc1c30931289ddf83e7c4762d8c00#egg=web_reader
websocket-client==1.8.0
wsproto==1.2.0
yarl==1.18.3


================================================
File: /setup.py
================================================
from setuptools import setup, find_packages

setup(
    name="web-reader",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "beautifulsoup4>=4.12.0",
        "selenium>=4.0.0",
        "langchain>=0.1.0",
        "langchain-ollama>=0.1.0",
        "langgraph>=0.0.1",
        "typing-extensions>=4.0.0"
    ],
    entry_points={
        "console_scripts": [
            "web-reader=src.main:main",
        ],
    },
    python_requires=">=3.10",
    author="Your Name",
    author_email="your.email@example.com",
    description="A natural language screen reader for web content",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="screen reader, accessibility, web, nlp",
    url="https://github.com/yourusername/web-reader",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
    ],
)


================================================
File: /src/config.py
================================================
"""Configuration settings and constants for the screen reader application"""

from langchain_community.chat_models import ChatOllama
from pydantic import BaseModel
from typing import Optional

class ActionResponse(BaseModel):
    action: str
    confidence: float
    context: Optional[str] = None
    next_action: Optional[str] = None
    next_context: Optional[str] = None

class LLMPageAnalysis(BaseModel):
    type: str
    has_main: bool
    has_nav: bool
    has_article: bool
    has_headlines: bool
    has_forms: bool
    reasoning: str

# LLM Configuration
llm = ChatOllama(
    model="llama3.2",
    format="json",
    temperature=0,
    
    prefix="""You are a screen reader assistant that helps users navigate and understand web content.
    You can navigate to URLs, read page content, click elements, and find specific text.
    
    When analyzing a page, consider its type and purpose:
    - For news sites: Use list_headlines to show news articles, list_headings for navigation
    - For social sites (Reddit, HN): Identify posts, comments, and discussions
    - For search engines: Help users search and navigate results
    - For video sites: Identify video content and descriptions
    - For article pages: Identify the main content and sections
    
    Important distinctions:
    - list_headings: Shows all structural headings (h1-h6) for page navigation
    - list_headlines: Shows news article headlines on news sites
    - goto_headline: Opens a specific article by number (e.g., "go to article 3", "read headline 2", "open article 1")
    
    Always be clear and concise in describing what you find on the page.
    Always respond with a valid JSON object containing exactly these fields:
    {
        "action": "one of the allowed actions",
        "confidence": number between 0 and 1,
        "context": "any relevant context",
        "next_action": "optional follow-up action",
        "next_context": "optional context for follow-up action"
    }"""
)

# Action Mapping
VALID_ACTIONS = {
    "navigate": "navigate",
    "read": "read_page",
    "click": "click_element",
    "check": "check_element",
    "list_headings": "list_headings",
    "list_headlines": "list_headlines",
    "goto_headline": "goto_headline",
    "find": "find_text",
    "next": "next_element",
    "prev": "prev_element",
    "list_landmarks": "list_landmarks",
    "goto": "goto_landmark",
    "read_section": "read_section"
}

# Element Selection Configuration
FOCUSABLE_SELECTORS = [
    "a[href]", 
    "button", 
    "input", 
    "select", 
    "textarea",
    "[tabindex]:not([tabindex='-1'])", 
    "[contenteditable='true']",
    "[role='button']", 
    "[role='link']", 
    "[role='menuitem']"
]

LANDMARK_ROLES = [
    "banner", 
    "complementary", 
    "contentinfo", 
    "form", 
    "main", 
    "navigation", 
    "region", 
    "search"
]

LANDMARK_TAGS = [
    "header", 
    "nav", 
    "main", 
    "aside", 
    "footer", 
    "form", 
    "section"
]

SECTION_CLASSES = [
    "section", 
    "content", 
    "main", 
    "header", 
    "footer", 
    "nav"
]

# Browser Configuration
BROWSER_OPTIONS = {
    "headless": False,  # Set to False to see what's happening
    "no_sandbox": True,
    "disable_dev_shm": True,
    "remote_debugging": False  # Disable remote debugging to prevent connection issues
}

# Help Text
USAGE_EXAMPLES = """You can give commands like:
- 'Go to example.com'
- 'Read the current page'
- 'Click the login button'
- 'Find text about pricing'
- 'Move to next element'
- 'Go to previous element'
- 'List all landmarks'
- 'List headings' (shows page structure)
- 'List headlines' (shows news articles)
- 'Go to headline [number]' (opens selected article)
- 'Go to main content section'
- 'Read current section'
"""


================================================
File: /src/main.py
================================================
#!/usr/bin/env python3
"""Main entry point for the screen reader application"""

import sys
import json
import time
from typing import Dict, Any, List, Tuple, Union
from dataclasses import asdict
from bs4 import BeautifulSoup
from langgraph.graph import StateGraph, END
from src.state import State, PageContext, create_initial_state, Task, TaskStatus, create_task, create_task_status
from src.browser import setup_browser, cleanup_browser
import src.config as config
from src.config import VALID_ACTIONS, USAGE_EXAMPLES, llm
from src.utils.logging import logger
from src.utils.errors import ReaderActionError as ReaderError
from src.utils.error_recovery import handle_error_with_llm
from src import actions
from src.config import LLMPageAnalysis

# Import action registry first
from src.actions import determine_action

import json
from typing import Dict, Any
from bs4 import BeautifulSoup

def analyze_context(state: State) -> Dict[str, Any]:
    """Analyze page context and user intent using LLM"""
    try:
        # Get page source and URL
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        url = state["driver"].current_url
        
        # Extract key elements for analysis
        title = soup.title.string if soup.title else ""
        headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text().strip()]
        meta_desc = soup.find("meta", {"name": "description"})
        description = meta_desc.get("content", "") if meta_desc else ""
        
        # Find potential main content areas
        main_candidates = []
        
        # Check explicit main tag
        main_tag = soup.find("main")
        if main_tag:
            main_candidates.append(("main tag", main_tag))
            
        # Check role="main"
        role_main = soup.find(attrs={"role": "main"})
        if role_main:
            main_candidates.append(("role=main", role_main))
            
        # Check common content IDs/classes
        content_patterns = {
            "id": ["content", "main", "article", "post", "story", "body"],
            "class": ["content", "main", "article", "post", "story", "body", "entry", "text"]
        }
        
        for attr, patterns in content_patterns.items():
            for pattern in patterns:
                if attr == "id":
                    content_by_attr = soup.find(id=lambda x: x and pattern in x.lower())
                else:
                    content_by_attr = soup.find(class_=lambda x: x and pattern in x.lower())
                if content_by_attr:
                    main_candidates.append((f"{attr}={pattern}", content_by_attr))
                
        # Check article tags and sections with significant content
        for tag in ["article", "section", "div"]:
            elements = soup.find_all(tag)
            for element in elements:
                # Skip if likely navigation/sidebar/footer
                if any(cls in str(element.get("class", [])).lower() for cls in ["nav", "menu", "sidebar", "footer", "header", "ad"]):
                    continue
                    
                # Check content significance
                text_length = len(element.get_text(strip=True))
                paragraphs = len(element.find_all("p"))
                if text_length > 500 or paragraphs > 2:  # Significant content threshold
                    main_candidates.append((f"content-rich {tag}", element))
            
        # Analyze content density and quality of candidates
        main_content_analysis = []
        for candidate_type, element in main_candidates:
            # Get text content excluding scripts and styles
            element_copy = BeautifulSoup(str(element), "html.parser")  # Create a copy to modify
            for script in element_copy.find_all(["script", "style"]):
                script.decompose()
            text = element_copy.get_text(strip=True)
            
            # Count meaningful elements
            links = len(element.find_all("a"))
            images = len(element.find_all("img"))
            paragraphs = len(element.find_all("p"))
            headings = len(element.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
            lists = len(element.find_all(["ul", "ol"]))
            
            # Calculate content-to-noise ratio
            noise_elements = len(element.find_all(class_=lambda x: x and any(p in str(x).lower() for p in ["ad", "promo", "banner", "widget", "sidebar"])))
            content_elements = paragraphs + headings + lists
            
            # Check semantic structure
            has_article_structure = bool(element.find("article"))
            has_section_structure = bool(element.find("section"))
            has_semantic_headings = bool(element.find(["h1", "h2", "h3"]))
            
            main_content_analysis.append({
                "type": candidate_type,
                "text_length": len(text),
                "links": links,
                "images": images,
                "paragraphs": paragraphs,
                "headings": headings,
                "lists": lists,
                "content_elements": content_elements,
                "noise_elements": noise_elements,
                "content_to_noise_ratio": content_elements / (noise_elements + 1),
                "semantic_structure": {
                    "has_article": has_article_structure,
                    "has_section": has_section_structure,
                    "has_semantic_headings": has_semantic_headings
                }
            })
        
        # Prepare context for LLM analysis
        try:
            main_content_analysis_json = json.dumps(main_content_analysis, indent=2)
        except Exception as e:
            logger.error(f"Error serializing main_content_analysis to JSON: {str(e)}")
            main_content_analysis_json = "Error serializing main_content_analysis to JSON"
            
        prompt = f"""Analyze this webpage and determine its type and structure:

        ... (rest of the prompt)
"""
        # Return analysis result
        return {
                "page_context": PageContext(
                    type="unknown",
                    has_main=bool(main_tag or role_main),
                    has_nav=bool(soup.find("nav")),
                    has_article=bool(soup.find("article")),
                    has_headlines=bool(headings),
                    has_forms=bool(soup.find("form")),
                    dynamic_content=False,
                    scroll_position=0,
                    viewport_height=0,
                    total_height=0
                ),
                "title": title,
                "headings": headings,
                "description": description,
                "main_content_analysis": main_content_analysis,
                "main_content_analysis_json": main_content_analysis_json,
                "url": url,
                "prompt": prompt
            }
    except Exception as e:
        logger.error(f"Error analyzing context: {str(e)}")
        return {"error": str(e)}

def plan_task_execution(state: State) -> Dict[str, Any]:
    """Enhanced task planning with parallel execution support"""
    try:
        # Get initial action from user input
        action_result = determine_action(state)
        logger.debug(f"Action determination result: {action_result}")
        
        if not action_result or action_result.get("error"):
            return {
                "error": action_result.get("error") if action_result else "Failed to determine action",
                "next": "error_recovery"
            }
        
        # Create task graph
        task_graph = build_task_graph(state, action_result)
        
        # Find parallel execution opportunities
        parallel_groups = find_parallel_tasks(task_graph)
        
        # Create execution plan
        execution_plan = create_execution_plan(task_graph, parallel_groups)
        
        # Update state with task information
        state["tasks"] = task_graph
        state["parallel_groups"] = parallel_groups
        state["execution_plan"] = execution_plan
        state["active_tasks"] = set()
        
        return {
            "next": "execute_parallel" if parallel_groups else "execute"
        }
        
    except Exception as e:
        logger.error(f"Error in plan_task_execution: {str(e)}")
        return {
            "error": f"Failed to plan execution: {str(e)}",
            "next": "error_recovery"
        }

def build_task_graph(state: State, action_result: Dict[str, Any]) -> Dict[str, Task]:
    """Build task dependency graph"""
    tasks = {}
    
    # Create main task
    action = action_result["current_action"]
    action_type = config.VALID_ACTIONS[action]
    main_task = create_task(
        task_id=action,
        task_type=action_type,
        state={"context": action_result.get("action_context", {})}
    )
    tasks[main_task.id] = main_task
    
    # Check for potential parallel tasks based on page context
    page_context = state.get("page_context")
    if isinstance(page_context, PageContext):
        # Content analysis can run in parallel with navigation
        if page_context.has_article or page_context.has_headlines:
            tasks["analyze_content"] = create_task(
                task_id="analyze_content",
                task_type="reading",
                can_parallel=True
            )
        
        # Structure analysis can run in parallel
        if page_context.has_main:
            tasks["analyze_structure"] = create_task(
                task_id="analyze_structure",
                task_type="reading",
                can_parallel=True
            )
        
        # Dynamic content handling
        if page_context.dynamic_content:
            tasks["handle_dynamic"] = create_task(
                task_id="handle_dynamic",
                task_type="interaction",
                dependencies=[main_task.id]
            )
    
    return tasks

def find_parallel_tasks(task_graph: Dict[str, Task]) -> List[List[str]]:
    """Find tasks that can be executed in parallel"""
    parallel_groups = []
    visited = set()
    
    for task_id, task in task_graph.items():
        if task_id in visited or not task.can_parallel:
            continue
            
        # Find other parallel tasks at same level
        parallel_group = [task_id]
        for other_id, other_task in task_graph.items():
            if other_id in visited or not other_task.can_parallel:
                continue
                
            # Check if tasks can run in parallel (no dependencies between them)
            if not (set(task.dependencies) & set(other_task.dependencies)):
                parallel_group.append(other_id)
                
        if len(parallel_group) > 1:
            parallel_groups.append(parallel_group)
            visited.update(parallel_group)
            
    return parallel_groups

def create_execution_plan(
    task_graph: Dict[str, Task],
    parallel_groups: List[List[str]]
) -> List[Union[str, List[str]]]:
    """Create optimal execution plan"""
    plan = []
    executed = set()
    
    while len(executed) < len(task_graph):
        # Find ready tasks (all dependencies satisfied)
        ready_tasks = []
        for task_id, task in task_graph.items():
            if task_id in executed:
                continue
                
            if all(dep in executed for dep in task.dependencies):
                ready_tasks.append(task_id)
        
        # Check if any ready tasks are in parallel groups
        for group in parallel_groups:
            if all(task in ready_tasks for task in group):
                plan.append(group)
                executed.update(group)
                ready_tasks = [t for t in ready_tasks if t not in group]
        
        # Add remaining ready tasks sequentially
        for task in ready_tasks:
            plan.append(task)
            executed.add(task)
            
    return plan

def prepare_action(state: State) -> Dict[str, Any]:
    """Prepare for action execution, handling setup needs"""
    try:
        # Handle dynamic content
        page_context = state.get("page_context")
        if isinstance(page_context, PageContext) and page_context.type in ["news", "article"]:
            # Wait for dynamic content
            state["driver"].implicitly_wait(2)
            
        # Predict needed interactions
        predictions = predict_needed_interactions(state)
        
        return {
            "predictions": predictions,
            "next": "execute"
        }
        
    except Exception as e:
        logger.error(f"Error in prepare_action: {str(e)}")
        return {
            "error": f"Failed to prepare action: {str(e)}",
            "next": "error_recovery"
        }

def execute_parallel_tasks(state: State) -> Dict[str, Any]:
    """Execute tasks that can run in parallel"""
    try:
        # Get next group of tasks to execute
        current_plan = state["execution_plan"]
        if not current_plan:
            return {"next": END}
            
        next_tasks = current_plan[0]
        if isinstance(next_tasks, list):
            # Execute parallel tasks
            results = {}
            for task_id in next_tasks:
                task = state["tasks"][task_id]
                try:
                    # Execute task
                    action_func = actions.get_action(VALID_ACTIONS[task.type])
                    result = action_func(state)
                    
                    # Update task status
                    state["task_status"][task_id] = create_task_status(
                        status="completed",
                        start_time=time.time(),
                        end_time=time.time()
                    )
                    
                    results[task_id] = result
                except Exception as e:
                    logger.error(f"Error executing task {task_id}: {str(e)}")
                    state["task_status"][task_id] = create_task_status(
                        status="failed",
                        error=str(e),
                        start_time=time.time(),
                        end_time=time.time()
                    )
                    results[task_id] = {"error": str(e)}
            
            # Remove executed group from plan
            state["execution_plan"] = current_plan[1:]
            
            # Check results
            if any(r.get("error") for r in results.values()):
                return {
                    "error": "Some parallel tasks failed",
                    "results": results,
                    "next": "error_recovery"
                }
                
            return {
                "results": results,
                "next": "execute_parallel" if state["execution_plan"] else END
            }
        else:
            # Single task execution
            task_id = next_tasks
            task = state["tasks"][task_id]
            
            try:
                # Execute task
                action_func = actions.get_action(VALID_ACTIONS[task.type])
                result = action_func(state)
                
                # Update task status
                state["task_status"][task_id] = create_task_status(
                    status="completed",
                    start_time=time.time(),
                    end_time=time.time()
                )
                
                # Remove executed task from plan
                state["execution_plan"] = current_plan[1:]
                
                # Include any messages from the action result
                return {
                    "result": result,
                    "messages": result.get("messages", []),
                    "next": "execute_parallel" if state["execution_plan"] else END
                }
                
            except Exception as e:
                logger.error(f"Error executing task {task_id}: {str(e)}")
                state["task_status"][task_id] = create_task_status(
                    status="failed",
                    error=str(e),
                    start_time=time.time(),
                    end_time=time.time()
                )
                return {
                    "error": f"Failed to execute {task_id}: {str(e)}",
                    "next": "error_recovery"
                }
                
    except Exception as e:
        logger.error(f"Error in execute_parallel_tasks: {str(e)}")
        return {
            "error": f"Failed to execute parallel tasks: {str(e)}",
            "next": "error_recovery"
        }

def predict_needed_interactions(state: State) -> Dict[str, Any]:
    """Predict interactions that might be needed"""
    predictions = {
        "needs_scroll": False,
        "needs_click": False,
        "needs_wait": False,
        "potential_popups": False
    }
    
    page_context = state.get("page_context")
    if not isinstance(page_context, PageContext):
        return predictions
        
    # Predict based on page type
    if page_context.type == "news":
        predictions["needs_scroll"] = True
        predictions["potential_popups"] = True
    elif page_context.type == "article":
        predictions["needs_scroll"] = True
    elif page_context.type == "form":
        predictions["needs_click"] = True
        
    # Predict based on structure
    if page_context.has_nav:
        predictions["needs_click"] = True
        
    return predictions

def reflect_on_execution(state: State) -> Dict[str, Any]:
    """Enhanced reflection with learning and adaptation"""
    history = state.get("execution_history", [])
    if not history:
        return {"next": END}
        
    prompt = f"""Reflect on these execution attempts:
    User request: "{state['messages'][-1]['content']}"
    Execution history: {history}
    
    Current state:
    - Page type: {state.get('page_type')}
    - Page context: {state.get('page_context')}
    - Headlines found: {'Yes' if state.get('headlines') else 'No'}
    - Last element found: {'Yes' if state.get('last_found_element') else 'No'}
    - Current action: {state.get('current_action')}
    - Action context: {state.get('action_context')}
    - Error: {state.get('error')}
    - Predictions: {state.get('predictions')}
    
    Analyze what went wrong and suggest a recovery strategy. Consider:
    1. Was this the right action for the user's intent?
    2. Are there alternative approaches we could try?
    3. Do we need more context or information?
    4. Should we break this down into smaller steps?
    5. Were our predictions accurate?
    6. What can we learn for future interactions?
    
    Return JSON with:
    - analysis: Brief explanation of what went wrong
    - strategy: One of ["retry", "alternative", "clarify", "decompose", "abort"]
    - suggested_action: Alternative action to try if strategy is "alternative"
    - sub_tasks: List of smaller tasks if strategy is "decompose"
    - clarification_needed: What to ask user if strategy is "clarify"
    - confidence: Confidence in suggested strategy (0-1)
    - learnings: What we learned for future predictions
    - prediction_adjustments: How to adjust our predictions"""
    
    response = llm.invoke(prompt)
    reflection = json.loads(response.content)
    
    # Update prediction model with learnings
    if reflection.get("learnings"):
        # Store learnings for future predictions
        state.setdefault("learned_patterns", []).append(reflection["learnings"])
        
    # Handle different reflection strategies
    if reflection["strategy"] == "retry":
        return {
            "attempts": state["attempts"],
            "next": "prepare"  # Go through preparation again
        }
    elif reflection["strategy"] == "alternative" and reflection["confidence"] > 0.7:
        return {
            "current_action": reflection["suggested_action"],
            "attempts": 0,
            "next": "prepare"
        }
    elif reflection["strategy"] == "decompose":
        # Store sub-tasks and execute first one
        sub_tasks = reflection["sub_tasks"]
        if sub_tasks:
            return {
                "sub_tasks": sub_tasks[1:],  # Store remaining tasks
                "task_dependencies": build_task_dependencies(sub_tasks),
                "messages": [{"role": "user", "content": sub_tasks[0]}],
                "attempts": 0,
                "next": "analyze"  # Start fresh with new task
            }
    
    # If all else fails or low confidence
    return {
        "messages": [{
            "role": "assistant",
            "content": "I'm having trouble completing this task. Could you try rephrasing your request?"
        }],
        "next": END
    }

def build_task_dependencies(tasks: List[str]) -> Dict[str, List[str]]:
    """Build dependency graph for tasks"""
    dependencies = {}
    for i, task in enumerate(tasks):
        # Simple sequential dependencies for now
        dependencies[task] = [tasks[i-1]] if i > 0 else []
    return dependencies

def build_workflow() -> StateGraph:
    """Build enhanced workflow graph with parallel execution support"""
    workflow = StateGraph(State)
    
    # Add core nodes
    workflow.add_node("analyze", analyze_context)           # Analyze page context
    workflow.add_node("plan", plan_task_execution)         # Enhanced task planning
    workflow.add_node("prepare", prepare_action)           # Prepare for execution
    workflow.add_node("execute_parallel", execute_parallel_tasks)  # Task execution (both single and parallel)
    workflow.add_node("reflect", reflect_on_execution)     # Enhanced reflection
    workflow.add_node("error_recovery", lambda state: handle_error_with_llm(state.get("error"), state))
    
    # Add base edges
    workflow.add_edge("analyze", "plan")
    workflow.add_edge("plan", "prepare")
    
    # Add conditional edges from prepare node
    workflow.add_conditional_edges(
        "prepare",
        lambda x: x.get("next", "execute_parallel"),
        {
            "execute": "execute_parallel",  # Both 'execute' and 'execute_parallel' go to the same node
            "execute_parallel": "execute_parallel",
            "error_recovery": "error_recovery"
        }
    )
    
    # Add conditional edges from execute_parallel node
    workflow.add_conditional_edges(
        "execute_parallel",
        lambda x: (
            "error_recovery" if x.get("error")
            else "reflect" if x.get("attempts", 0) > 1
            else "execute_parallel" if x.get("next") == "execute_parallel"
            else END
        ),
        {
            "error_recovery": "error_recovery",
            "reflect": "reflect",
            "execute_parallel": "execute_parallel",
            END: END
        }
    )
    
    # Add conditional edges from reflection node
    workflow.add_conditional_edges(
        "reflect",
        lambda x: (
            "analyze" if x.get("next") == "analyze"
            else "plan" if x.get("next") == "plan"
            else "prepare" if x.get("next") == "prepare"
            else END
        ),
        {
            "analyze": "analyze",
            "plan": "plan",
            "prepare": "prepare",
            END: END
        }
    )
    
    # Add conditional edges from error recovery node
    workflow.add_conditional_edges(
        "error_recovery",
        lambda x: (
            "analyze" if x.get("strategy") in ["decompose", "clarify"]
            else "prepare" if x.get("strategy") in ["retry", "alternative"]
            else END
        ),
        {
            "analyze": "analyze",
            "prepare": "prepare",
            END: END
        }
    )
    
    # Set entry point
    workflow.set_entry_point("analyze")
    
    return workflow.compile()

def process_user_input(graph: StateGraph, state: State) -> None:
    """Process user input with enhanced logging and monitoring"""
    user_input = state['messages'][-1]['content']
    state_id = str(id(state))
    
    with logger.action_context("process_input", state_id, 
                             input=user_input) as context:
        try:
            for event in graph.stream(state):
                if event is None:
                    continue
                
                logger.debug("Processing event", 
                           context={"event": event, "state_id": state_id})
                
                # Track state before update
                old_state = {
                    "action": state.get("current_action"),
                    "page_context": state.get("page_context"),
                    "predictions": state.get("predictions")
                }
                
                # Process event updates
                for key, value in event.items():
                    if isinstance(value, dict):
                        # Update state first
                        for field, field_value in value.items():
                            if field not in ["messages", "next"]:
                                state[field] = field_value
                                
                                # Log state transitions
                                if field in ["current_action", "page_context", "predictions"]:
                                    logger.log_state_transition(
                                        from_state=str(old_state.get(field)),
                                        to_state=str(field_value),
                                        context={
                                            "field": field,
                                            "state_id": state_id
                                        }
                                    )
                        
                        # Print messages after state is updated
                        if "messages" in value:
                            for msg in value["messages"]:
                                if isinstance(msg, dict) and msg.get("role") == "assistant":
                                    print(f"\n{msg['content']}")
                
                # Log predictions if available
                if "predictions" in event:
                    predictions = event["predictions"]
                    actual = {
                        "needs_scroll": state.get("page_context", {}).get("scroll_position", 0) > 0,
                        "needs_wait": state.get("page_context", {}).get("dynamic_content", False),
                        "potential_popups": False  # Will be updated if popup detected
                    }
                    logger.log_prediction(predictions, actual)
                
                # Update context with latest state (convert complex objects to dicts/strings)
                if state.get("page_context"):
                    context.page_context = state.get("page_context", {})
                context.element_context = str(state.get("element_context"))
                context.predictions = str(state.get("predictions"))
                
        except Exception as e:
            logger.log_error(f"Error in process_user_input: {str(e)}", {
                "state_id": state_id,
                "input": user_input
            })
            raise

def main() -> None:
    """Enhanced main application entry point with structured logging"""
    with logger.action_context("application_startup", "main") as context:
        logger.info("Starting Natural Language Screen Reader")
        
        try:
            # Initialize browser
            driver = setup_browser()
            logger.info("Browser initialized successfully")
            
            # Print usage instructions
            print(USAGE_EXAMPLES)
            print("\nType 'exit' to quit")
            
            # Initialize workflow
            graph = build_workflow()
            logger.info("Workflow initialized", 
                       context={"graph_nodes": list(graph.nodes.keys())})
            
            # Main interaction loop
            interaction_count = 0
            while True:
                interaction_id = f"interaction_{interaction_count}"
                
                try:
                    # Get user input
                    user_input = input("\nWhat would you like me to do? ").strip()
                    if user_input.lower() in ["exit", "quit", "q"]:
                        break
                    
                    with logger.action_context("user_interaction", interaction_id,
                                             input=user_input) as interaction_context:
                        # Create new state for each interaction
                        state = create_initial_state(driver, user_input)
                        
                        # Process the input
                        process_user_input(graph, state)
                        
                        # Update metrics
                        interaction_count += 1
                        
                except KeyboardInterrupt:
                    logger.info("Operation cancelled by user", 
                              context={"interaction_id": interaction_id})
                    print("\nOperation cancelled by user")
                    continue
                except ReaderError as e:
                    logger.log_error(str(e), {
                        "interaction_id": interaction_id,
                        "error_type": "ReaderError"
                    })
                    print(f"\n{str(e)}")
                    continue
                except Exception as e:
                    # Just print the error message, avoid logging here
                    print(f"\nAn unexpected error occurred. Please try again.")
                    continue
                    
        except Exception as e:
            logger.log_error(str(e), {
                "error_type": "FatalError",
                "startup_context": asdict(context)
            })
            print(f"\nFatal error: {str(e)}")
            
        finally:
            print("\nClosing browser...")
            cleanup_browser(driver)
            logger.info("Application shutdown complete")

if __name__ == "__main__":
    main()


================================================
File: /src/__init__.py
================================================
"""Web Reader - A natural language screen reader for web content"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from . import actions
from . import utils
from . import browser
from . import config
from . import state

__all__ = ["actions", "utils", "browser", "config", "state"]


================================================
File: /src/state.py
================================================
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
from typing import List, Dict, Optional, Any, Union

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
class Task:
    """Structured task representation"""
    id: str
    type: str  # navigation, interaction, reading, etc.
    dependencies: List[str]
    can_parallel: bool
    state: Dict[str, Any]
    recovery_strategy: Optional[str]

@dataclass
class TaskStatus:
    """Task execution status tracking"""
    status: str  # pending, running, completed, failed
    start_time: float
    end_time: Optional[float]
    error: Optional[str]
    attempts: int
    recovery_plan: Optional[List[str]]

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
    """Enhanced state object with rich context and parallel task support"""
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
    
    # Enhanced task management
    tasks: Dict[str, Task]
    task_status: Dict[str, TaskStatus]
    parallel_groups: List[List[str]]
    active_tasks: set
    execution_plan: List[Union[str, List[str]]]
    
    # Execution tracking
    execution_history: List[Dict[str, Any]]
    error: str | None
    strategy: str | None
    recovery_attempts: Dict[str, int]
def create_initial_state(driver: webdriver.Chrome, user_input: str) -> State:
    """Create enhanced initial state with rich context and task management"""
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
        
        # Enhanced task management
        "tasks": {},
        "task_status": {},
        "parallel_groups": [],
        "active_tasks": set(),
        "execution_plan": [],
        
        # Execution tracking
        "execution_history": [],
        "error": None,
        "strategy": None,
        "recovery_attempts": {}
    })

def create_task(
    task_id: str,
    task_type: str,
    dependencies: List[str] = None,
    can_parallel: bool = False,
    state: Dict[str, Any] = None,
    recovery_strategy: Optional[str] = None
) -> Task:
    """Create a new task with the specified parameters"""
    return Task(
        id=task_id,
        type=task_type,
        dependencies=dependencies or [],
        can_parallel=can_parallel,
        state=state or {},
        recovery_strategy=recovery_strategy
    )

def create_task_status(
    status: str = "pending",
    start_time: float = 0,
    end_time: Optional[float] = None,
    error: Optional[str] = None,
    attempts: int = 0,
    recovery_plan: Optional[List[str]] = None
) -> TaskStatus:
    """Create a new task status object"""
    return TaskStatus(
        status=status,
        start_time=start_time,
        end_time=end_time,
        error=error,
        attempts=attempts,
        recovery_plan=recovery_plan
    )


================================================
File: /src/browser.py
================================================
"""Browser management for the screen reader application"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from typing import List
import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import BROWSER_OPTIONS, FOCUSABLE_SELECTORS
from src.utils.logging import logger

def setup_browser() -> webdriver.Chrome:
    """Initialize and configure headless Chrome browser"""
    logger.debug("Initializing browser")
    chrome_options = Options()
    
    # Required options for Chromium
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Fix for DevToolsActivePort issue
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    # Basic options
    if BROWSER_OPTIONS["headless"]:
        chrome_options.add_argument("--headless=new")
    
    # Window configuration
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Performance options
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    
    # Create and configure driver
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)  # Set page load timeout
    
    logger.info("Browser initialized successfully")
    return driver

def get_focusable_elements(driver: webdriver.Chrome) -> List[webdriver.remote.webelement.WebElement]:
    """Get all focusable elements on the page"""
    elements = driver.find_elements(By.CSS_SELECTOR, ", ".join(FOCUSABLE_SELECTORS))
    return [e for e in elements if e.is_displayed()]

def scroll_element_into_view(driver: webdriver.Chrome, element: webdriver.remote.webelement.WebElement) -> None:
    """Scroll an element into view and wait for it to be visible"""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

def safe_click(driver: webdriver.Chrome, element: webdriver.remote.webelement.WebElement) -> None:
    """Safely click an element with proper scrolling and waiting"""
    scroll_element_into_view(driver, element)
    element.click()

def cleanup_browser(driver: webdriver.Chrome) -> None:
    """Clean up browser resources"""
    try:
        driver.quit()
        logger.info("Browser closed successfully")
    except Exception as e:
        logger.error(f"Error closing browser: {str(e)}")


================================================
File: /src/actions/interaction.py
================================================
"""Enhanced element interaction with predictive behavior"""

import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from langgraph.graph import END
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from .. import browser
from ..state import State, ElementContext, ActionPrediction, PageContext
from ..utils.errors import ElementNotFoundError, InteractionError
from ..utils.logging import logger
from . import register_action
from .reading import ActionResult, create_result, analyze_page_structure as analyze_content_structure

@dataclass
class ElementOutput:
    """Enhanced output for element interactions"""
    tag_name: str
    text: str
    role: str
    is_clickable: bool = False
    is_visible: bool = False
    href: Optional[str] = None
    location: Optional[Dict[str, int]] = None
    attributes: Dict[str, str] = None
    context: Dict[str, Any] = None

def get_element_output(element: WebElement, driver) -> ElementOutput:
    """Create enhanced output from WebElement"""
    tag_name = element.tag_name
    text = element.text or element.get_attribute("value") or element.get_attribute("placeholder")
    role = element.get_attribute("role") or tag_name
    href = element.get_attribute("href")
    onclick = element.get_attribute("onclick")
    
    # Get element visibility and location
    is_visible = element.is_displayed()
    try:
        location = element.location
        size = element.size
        center = {
            "x": location["x"] + size["width"] / 2,
            "y": location["y"] + size["height"] / 2
        }
    except:
        location = None
        center = None
    
    # Get clickability
    is_clickable = (
        tag_name in ["a", "button"] or
        href is not None or
        onclick is not None or
        role in ["button", "link"]
    )
    
    # Get rich context
    context = {
        "parent": element.find_element(By.XPATH, "..").tag_name,
        "children": len(element.find_elements(By.XPATH, "./*")),
        "siblings": len(element.find_elements(By.XPATH, "../*")),
        "in_viewport": is_in_viewport(driver, element),
        "tab_index": element.get_attribute("tabindex"),
        "aria": {
            "label": element.get_attribute("aria-label"),
            "expanded": element.get_attribute("aria-expanded"),
            "selected": element.get_attribute("aria-selected"),
            "hidden": element.get_attribute("aria-hidden")
        }
    }
    
    return ElementOutput(
        tag_name=tag_name,
        text=text,
        role=role,
        is_clickable=is_clickable,
        is_visible=is_visible,
        href=href,
        location={"center": center, "rect": {"x": location["x"], "y": location["y"], "width": size["width"], "height": size["height"]}} if location else None,
        attributes={
            "role": role,
            "href": href,
            "onclick": onclick,
            "class": element.get_attribute("class"),
            "id": element.get_attribute("id"),
            "name": element.get_attribute("name")
        },
        context=context
    )

def is_in_viewport(driver, element) -> bool:
    """Check if element is in viewport"""
    return driver.execute_script("""
        var rect = arguments[0].getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    """, element)

def predict_interaction_needs(element: WebElement, page_context: PageContext) -> ActionPrediction:
    """Predict needed interactions for element"""
    predictions = ActionPrediction(
        needs_scroll=False,
        needs_click=False,
        needs_wait=False,
        potential_popups=False,
        confidence=0.8,
        reasoning=""
    )
    
    # Predict scroll needs
    if not is_in_viewport(element.parent.parent, element):
        predictions.needs_scroll = True
        predictions.reasoning += "Element is outside viewport. "
    
    # Predict click needs
    if element.get_attribute("role") in ["button", "link", "menuitem"]:
        predictions.needs_click = True
        predictions.reasoning += "Element has interactive role. "
    
    # Predict wait needs
    if element.get_attribute("href") or element.get_attribute("onclick"):
        predictions.needs_wait = True
        predictions.reasoning += "Element triggers navigation/action. "
    
    # Predict popups
    if page_context.type in ["news", "article"] and element.get_attribute("href"):
        predictions.potential_popups = True
        predictions.reasoning += "News sites often have subscription popups. "
    
    return predictions

@register_action("next_element")
def next_element(state: State) -> ActionResult:
    """Enhanced element navigation with predictions"""
    logger.debug("Entering next_element action")
    
    try:
        # Get or update focusable elements
        if "focusable_elements" not in state:
            elements = browser.get_focusable_elements(state["driver"])
            if not elements:
                return create_result(error="No focusable elements found on the page")
                
            current_index = -1
        else:
            elements = state["focusable_elements"]
            current_index = state["current_element_index"]
            
        # Move to next element
        next_index = (current_index + 1) % len(elements)
        element = elements[next_index]
        
        # Predict needed interactions
        predictions = predict_interaction_needs(element, state["page_context"])
        
        # Handle predictions
        if predictions.needs_scroll:
            browser.scroll_element_into_view(state["driver"], element)
            time.sleep(0.5)  # Allow time for scrolling
            
        # Get enhanced element details
        output = get_element_output(element, state["driver"])
        
        # Create rich element context
        element_context = ElementContext(
            tag_name=output.tag_name,
            role=output.role,
            text=output.text,
            is_clickable=output.is_clickable,
            is_visible=output.is_visible,
            location=output.location,
            attributes=output.attributes
        )
        
        return create_result(
            output=output,
            state_updates={
                "focusable_elements": elements,
                "current_element_index": next_index,
                "last_found_element": element,
                "element_context": element_context,
                "predictions": predictions
            },
            messages=[
                f"Moved to {output.role}: {output.text}" + 
                (f" (clickable)" if output.is_clickable else "") +
                (f" [not visible]" if not output.is_visible else "")
            ]
        )
        
    except Exception as e:
        logger.error(f"Error moving to next element: {str(e)}")
        return create_result(error=f"An error occurred while moving to the next element: {str(e)}")

@register_action("prev_element")
def prev_element(state: State) -> ActionResult:
    """Enhanced previous element navigation"""
    logger.debug("Entering prev_element action")
    
    try:
        # Get or update focusable elements
        if "focusable_elements" not in state:
            elements = browser.get_focusable_elements(state["driver"])
            if not elements:
                return create_result(error="No focusable elements found on the page")
                
            current_index = 0
        else:
            elements = state["focusable_elements"]
            current_index = state["current_element_index"]
            
        # Move to previous element
        prev_index = (current_index - 1) % len(elements)
        element = elements[prev_index]
        
        # Predict needed interactions
        predictions = predict_interaction_needs(element, state["page_context"])
        
        # Handle predictions
        if predictions.needs_scroll:
            browser.scroll_element_into_view(state["driver"], element)
            time.sleep(0.5)  # Allow time for scrolling
            
        # Get enhanced element details
        output = get_element_output(element, state["driver"])
        
        # Create rich element context
        element_context = ElementContext(
            tag_name=output.tag_name,
            role=output.role,
            text=output.text,
            is_clickable=output.is_clickable,
            is_visible=output.is_visible,
            location=output.location,
            attributes=output.attributes
        )
        
        return create_result(
            output=output,
            state_updates={
                "focusable_elements": elements,
                "current_element_index": prev_index,
                "last_found_element": element,
                "element_context": element_context,
                "predictions": predictions
            },
            messages=[
                f"Moved to {output.role}: {output.text}" + 
                (f" (clickable)" if output.is_clickable else "") +
                (f" [not visible]" if not output.is_visible else "")
            ]
        )
        
    except Exception as e:
        logger.error(f"Error moving to previous element: {str(e)}")
        return create_result(error=f"An error occurred while moving to the previous element: {str(e)}")

@register_action("check_element")
def check_element(state: State) -> ActionResult:
    """Enhanced element property checking"""
    logger.debug("Entering check_element action")
    
    try:
        element = state.get("last_found_element")
        if not element:
            return create_result(error="No recently found element to check")
            
        # Get enhanced element details
        output = get_element_output(element, state["driver"])
        
        # Build detailed message
        messages = []
        messages.append(f"Element type: {output.role} ({output.tag_name})")
        messages.append(f"Text content: {output.text}")
        messages.append(f"Clickable: {'Yes' if output.is_clickable else 'No'}")
        messages.append(f"Visible: {'Yes' if output.is_visible else 'No'}")
        
        if output.location:
            messages.append(f"Position: {output.location['center']}")
            
        if output.context["aria"]["label"]:
            messages.append(f"ARIA label: {output.context['aria']['label']}")
            
        if output.href:
            messages.append(f"Link target: {output.href}")
            
        # Create rich element context
        element_context = ElementContext(
            tag_name=output.tag_name,
            role=output.role,
            text=output.text,
            is_clickable=output.is_clickable,
            is_visible=output.is_visible,
            location=output.location,
            attributes=output.attributes
        )
        
        return create_result(
            output=output,
            state_updates={"element_context": element_context},
            messages=["\n".join(messages)]
        )
        
    except Exception as e:
        logger.error(f"Error checking element: {str(e)}")
        return create_result(error=f"An error occurred while checking the element: {str(e)}")

@register_action("navigate")
def navigate(state: State) -> ActionResult:
    """Enhanced navigation with dynamic content handling"""
    logger.debug("Entering navigate action")
    url = state.get("action_context", "").strip()
    
    if not url:
        return create_result(error="Please specify a URL to navigate to")
        
    try:
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Navigate to URL
        state["driver"].get(url)
        
        # Wait for initial load
        try:
            WebDriverWait(state["driver"], 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except:
            pass
            
        # Analyze page structure
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        structure = analyze_content_structure(soup)
        
        # Predict page behavior
        predictions = ActionPrediction(
            needs_scroll=bool(structure["main_content"]),
            needs_click=bool(structure["interactive_elements"]),
            needs_wait=True,
            potential_popups=url.endswith((".com", ".org", ".net")),  # Common news sites
            confidence=0.8,
            reasoning="Initial page load predictions"
        )
        
        # Update page context
        page_context = PageContext(
            type="unknown",  # Will be determined by content analysis
            has_main=structure["main_content"],
            has_nav=structure["navigation"],
            has_article=False,  # Will be determined by content analysis
            has_headlines=False,  # Will be determined by content analysis
            has_forms=bool(structure["forms"]),
            dynamic_content=True,  # Assume dynamic for initial load
            scroll_position=0,
            viewport_height=state["driver"].execute_script("return window.innerHeight"),
            total_height=state["driver"].execute_script("return document.documentElement.scrollHeight")
        )
        
        return create_result(
            output=url,
            state_updates={
                "current_element_index": -1,
                "focusable_elements": [],
                "last_found_element": None,
                "page_context": page_context,
                "predictions": predictions,
                "element_context": None
            },
            messages=[
                f"Navigated to {url}. The page is loading and being analyzed. " +
                ("You may need to handle popups. " if predictions.potential_popups else "") +
                "Would you like me to read the content?"
            ]
        )
        
    except Exception as e:
        logger.error(f"Error navigating to URL: {str(e)}")
        return create_result(error=f"Failed to navigate to {url}: {str(e)}")

@register_action("click_element")
def click_element(state: State) -> ActionResult:
    """Enhanced element clicking with predictions and dynamic content handling"""
    logger.debug("Entering click_element action")
    element_desc = state.get("action_context", "").lower()
    
    if not element_desc:
        return create_result(error="Please specify what you want to click")
    
    try:
        # Clean up element description
        element_desc = element_desc.strip().lower()
        
        # Define enhanced search strategies
        strategies = [
            # Exact matches with context
            (By.LINK_TEXT, element_desc),
            (By.XPATH, f"//*[@data-testid='{element_desc}']//a[1]"),
            (By.XPATH, f"//*[@data-navid='{element_desc}']//a[1]"),
            (By.XPATH, f"//button[translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
            (By.XPATH, f"//*[@role='button' and translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{element_desc}']"),
            
            # ARIA and accessibility matches
            (By.XPATH, f"//*[@aria-label='{element_desc}']"),
            (By.XPATH, f"//*[@title='{element_desc}']"),
            (By.XPATH, f"//*[@alt='{element_desc}']"),
            
            # Partial matches with context
            (By.PARTIAL_LINK_TEXT, element_desc),
            (By.XPATH, f"//*[contains(@data-testid, '{element_desc}')]//a[1]"),
            (By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{element_desc}')]"),
            (By.XPATH, f"//*[@role='button' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{element_desc}')]"),
            (By.XPATH, f"//nav//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{element_desc}')]"),
            
            # Context-based matches
            (By.XPATH, f"//*[contains(@class, 'button') and contains(., '{element_desc}')]"),
            (By.XPATH, f"//*[contains(@class, 'btn') and contains(., '{element_desc}')]"),
            (By.XPATH, f"//*[contains(@class, 'nav') and contains(., '{element_desc}')]")
        ]
        
        # Try each strategy
        found_elements = []
        for by, value in strategies:
            try:
                elements = state["driver"].find_elements(by, value)
                for element in elements:
                    if element.is_displayed():
                        # Get enhanced element details
                        output = get_element_output(element, state["driver"])
                        found_elements.append((element, output))
            except:
                continue
                
        if found_elements:
            # Sort by visibility and clickability
            found_elements.sort(key=lambda x: (
                x[1].is_visible,
                x[1].is_clickable,
                len(x[1].text or "") > 0
            ), reverse=True)
            
            element, output = found_elements[0]
            
            # Predict interaction needs
            predictions = predict_interaction_needs(element, state["page_context"])
            
            # Handle predictions
            if predictions.needs_scroll:
                browser.scroll_element_into_view(state["driver"], element)
                time.sleep(0.5)
                
            # Click the element
            browser.safe_click(state["driver"], element)
            
            # Wait for updates if needed
            if predictions.needs_wait:
                try:
                    WebDriverWait(state["driver"], 3).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except:
                    pass
                    
            # Create rich element context
            element_context = ElementContext(
                tag_name=output.tag_name,
                role=output.role,
                text=output.text,
                is_clickable=output.is_clickable,
                is_visible=output.is_visible,
                location=output.location,
                attributes=output.attributes
            )
            
            # Update page context
            page_context = state["page_context"]
            page_context.scroll_position = state["driver"].execute_script("return window.pageYOffset")
            
            return create_result(
                output=output,
                state_updates={
                    "last_found_element": element,
                    "current_element_index": -1,
                    "focusable_elements": [],
                    "element_context": element_context,
                    "page_context": page_context,
                    "predictions": predictions
                },
                messages=[
                    f"Clicked element: '{output.text or element_desc}'. " +
                    ("Waiting for page update. " if predictions.needs_wait else "") +
                    ("Watch for popups. " if predictions.potential_popups else "") +
                    "Would you like me to read the updated content?"
                ]
            )
            
        # If no elements found, provide detailed error
        return create_result(
            error=f"Could not find clickable element matching '{element_desc}'. Try using the exact text as shown on the page or describe the element's location (e.g., 'in the navigation menu')."
        )
        
    except Exception as e:
        logger.error(f"Error clicking element: {str(e)}")
        if "no such element" in str(e).lower():
            return create_result(error=f"Could not find element: {str(e)}")
        else:
            return create_result(error=f"Failed to click element: {str(e)}")


================================================
File: /src/actions/__init__.py
================================================
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


================================================
File: /src/actions/base.py
================================================
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


================================================
File: /src/actions/reading.py
================================================
"""Enhanced content reading actions with dynamic content handling"""

import time
from typing import Dict, Any, TypedDict, Union, List, Optional
from dataclasses import dataclass
from langgraph.graph import END
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..state import State, PageContext, ElementContext, ActionPrediction, Task, TaskStatus, create_task_status
from ..utils.logging import logger
from ..utils.errors import create_error_response
from . import register_action

@dataclass
class ReadPageOutput:
    """Enhanced output for read_page action"""
    content: str
    sections: List[Dict[str, str]]  # List of named sections
    summary: Optional[str]
    truncated: bool = False
    dynamic_content: bool = False

@dataclass
class HeadingOutput:
    """Enhanced output for list_headings action"""
    headings: List[Dict[str, Any]]  # Include structure and context
    level: str
    hierarchy: Dict[str, List[str]]  # Heading hierarchy

@dataclass
class HeadlineOutput:
    """Enhanced output for list_headlines action"""
    text: str
    url: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None
    category: Optional[str] = None

class ActionResult(TypedDict):
    """Action result container"""
    output: Union[ReadPageOutput, HeadingOutput, List[HeadlineOutput], None]
    state_updates: Dict[str, Any]
    messages: List[Dict[str, str]]
    next: str
    error: Optional[str]

def create_result(
    output: Any = None,
    state_updates: Dict[str, Any] = None,
    messages: List[str] = None,
    next_node: str = END,
    error: Optional[str] = None
) -> ActionResult:
    """Create action result"""
    return ActionResult(
        output=output,
        state_updates=state_updates or {},
        messages=[{"role": "assistant", "content": msg} for msg in (messages or [])],
        next=next_node,
        error=error
    )

class WaitStrategy:
    """Enhanced waiting for dynamic content"""
    @staticmethod
    def wait_for_content(driver, strategy: str, target: str = None):
        """
        Wait for content using specified strategy
        
        Strategies:
        - idle: Wait for network idle
        - selector: Wait for specific element
        - text: Wait for text to appear
        """
        try:
            if strategy == "idle":
                WebDriverWait(driver, 5).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            elif strategy == "selector" and target:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, target))
                )
            elif strategy == "text" and target:
                WebDriverWait(driver, 5).until(
                    EC.text_to_be_present_in_element((By.TAG_NAME, "body"), target)
                )
            
            # Additional check for accessibility elements
            WebDriverWait(driver, 3).until(
                lambda d: d.find_element(By.CSS_SELECTOR, '[role="main"], main, [role="article"], article')
            )
            
        except Exception as e:
            logger.error(f"Wait strategy {strategy} failed: {str(e)}")
            # Fallback to basic load check
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )

def handle_dynamic_content(state: State, soup: BeautifulSoup) -> BeautifulSoup:
    """Enhanced dynamic content handling"""
    if state.get("predictions", {}).get("needs_wait"):
        # First try waiting for network idle
        WaitStrategy.wait_for_content(state["driver"], "idle")
        
        # Then wait for main content based on page type
        if state["page_context"].type == "article":
            WaitStrategy.wait_for_content(state["driver"], "selector", "article, [role='article']")
        elif state["page_context"].type == "news":
            WaitStrategy.wait_for_content(state["driver"], "selector", ".article, .story, .post")
        
        # Update soup with new content
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
    
    return soup

def extract_page_content(driver, soup: BeautifulSoup, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced content extraction with structured output
    
    Features:
    - Content type-specific extraction
    - Semantic relationship mapping
    - Accessibility metadata
    """
    content = {
        "type": analysis["type"],
        "metadata": {
            "title": driver.title,
            "url": driver.current_url,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "accessibility": {
            "landmarks": [],
            "headings": [],
            "aria_labels": [],
            "tab_order": []
        },
        "content": {
            "main": None,
            "sections": [],
            "navigation": None,
            "interactive_elements": []
        }
    }
    
    # Extract landmarks
    for element in soup.find_all(attrs={"role": True}):
        content["accessibility"]["landmarks"].append({
            "role": element["role"],
            "label": element.get("aria-label", ""),
            "text": element.get_text()[:100]
        })
    
    # Extract headings with hierarchy
    headings = []
    current_section = None
    for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        for heading in soup.find_all(tag):
            heading_data = {
                "level": int(tag[1]),
                "text": heading.get_text(),
                "id": heading.get("id", ""),
                "parent": current_section
            }
            if tag == "h1":
                current_section = heading_data
            headings.append(heading_data)
    content["accessibility"]["headings"] = headings
    
    # Extract tab order
    focusable = soup.find_all(["a", "button", "input", "select", "textarea", "[tabindex]"])
    for i, element in enumerate(focusable):
        content["accessibility"]["tab_order"].append({
            "index": i + 1,
            "type": element.name,
            "text": element.get_text() or element.get("placeholder", ""),
            "aria_label": element.get("aria-label", "")
        })
    
    # Extract main content based on page type
    if analysis["type"] == "article":
        article = soup.find("article") or soup.find(attrs={"role": "article"})
        if article:
            content["content"]["main"] = {
                "title": article.find(["h1", "h2"]).get_text() if article.find(["h1", "h2"]) else "",
                "text": article.get_text(),
                "sections": []
            }
            # Break into sections
            for section in article.find_all(["section", "div"], class_=lambda x: x and "section" in x):
                content["content"]["sections"].append({
                    "title": section.find(["h1", "h2", "h3"]).get_text() if section.find(["h1", "h2", "h3"]) else "",
                    "text": section.get_text(),
                    "type": section.get("class", [""])[0]
                })
    
    elif analysis["type"] == "news":
        # Extract headlines and articles
        content["content"]["articles"] = []
        for article in soup.find_all(["article"], class_=lambda x: x and "article" in str(x)):
            content["content"]["articles"].append({
                "headline": article.find(["h1", "h2", "h3"]).get_text() if article.find(["h1", "h2", "h3"]) else "",
                "summary": article.get_text()[:200],
                "link": article.find("a")["href"] if article.find("a") else None
            })
    
    # Extract interactive elements
    for element in soup.find_all(["button", "a", "input", "select"]):
        content["content"]["interactive_elements"].append({
            "type": element.name,
            "text": element.get_text() or element.get("placeholder", ""),
            "aria_label": element.get("aria-label", ""),
            "is_visible": bool(element.get("style", "").find("display: none") == -1),
            "location": element.get("id", "") or element.get("class", [""])[0]
        })
    
    return content

def extract_section_content(section: BeautifulSoup) -> Dict[str, str]:
    """Extract content from a page section with enhanced metadata"""
    heading = section.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    return {
        "title": heading.get_text(strip=True) if heading else "",
        "content": section.get_text(separator="\n", strip=True),
        "type": section.name or section.get("role", "section"),
        "class": " ".join(section.get("class", [])),
        "aria_label": section.get("aria-label", ""),
        "id": section.get("id", ""),
        "has_interactive": bool(section.find_all(["button", "a", "input", "select"])),
        "subsections": [
            {
                "title": subsec.find(["h1", "h2", "h3", "h4", "h5", "h6"]).get_text(strip=True) if subsec.find(["h1", "h2", "h3", "h4", "h5", "h6"]) else "",
                "content": subsec.get_text(separator="\n", strip=True)
            }
            for subsec in section.find_all(["section", "div"], recursive=False)
            if "section" in str(subsec.get("class", []))
        ]
    }

def analyze_page_structure(driver, soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Enhanced page analysis with structured output
    
    Features:
    - Semantic structure detection
    - Content type classification
    - Accessibility evaluation
    - Navigation suggestions
    """
    # Extract key elements and metadata
    title = driver.title
    main_content = soup.find("main") or soup.find(attrs={"role": "main"})
    navigation = soup.find("nav") or soup.find(attrs={"role": "navigation"})
    landmarks = soup.find_all(attrs={"role": True})
    
    # Analyze semantic structure
    structure = {
        "main_content": bool(main_content),
        "navigation": bool(navigation),
        "sidebar": bool(soup.find("aside") or soup.find(attrs={"role": "complementary"})),
        "footer": bool(soup.find("footer") or soup.find(attrs={"role": "contentinfo"})),
        "header": bool(soup.find("header") or soup.find(attrs={"role": "banner"})),
        "forms": len(soup.find_all("form")),
        "interactive_elements": len(soup.find_all(["button", "input", "select", "textarea"])),
        "landmarks": [{"role": l["role"], "label": l.get("aria-label", ""), "text": l.get_text()[:100]} for l in landmarks],
        "has_dynamic_content": bool(
            soup.find_all("script", src=True) or
            soup.find_all(["[x-data]", "[v-if]", "react-root"])
        )
    }
    
    # Detect content type
    content_type = "unknown"
    if soup.find("article") or soup.find(attrs={"role": "article"}):
        content_type = "article"
    elif len(soup.find_all(["h1", "h2", "h3"], class_=lambda x: x and any(c in str(x).lower() for c in ["headline", "title"]))) > 3:
        content_type = "news"
    elif structure["forms"] > 0:
        content_type = "form"
    elif soup.find("table") or soup.find(attrs={"role": "grid"}):
        content_type = "data"
    
    # Evaluate accessibility
    accessibility_score = 0
    accessibility_notes = []
    
    # Check landmarks
    if structure["main_content"]:
        accessibility_score += 20
    else:
        accessibility_notes.append("Missing main content landmark")
        
    if structure["navigation"]:
        accessibility_score += 10
    
    # Check headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    if headings:
        accessibility_score += 20
        if not soup.find("h1"):
            accessibility_notes.append("Missing H1 heading")
    else:
        accessibility_notes.append("No headings found")
    
    # Check images
    images = soup.find_all("img")
    images_with_alt = [img for img in images if img.get("alt")]
    if images:
        alt_ratio = len(images_with_alt) / len(images)
        accessibility_score += int(alt_ratio * 20)
        if alt_ratio < 1:
            accessibility_notes.append(f"{len(images) - len(images_with_alt)} images missing alt text")
    
    # Check forms
    forms = soup.find_all("form")
    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        labels = form.find_all("label")
        if len(inputs) > len(labels):
            accessibility_notes.append("Some form fields missing labels")
            break
    
    # Check ARIA
    elements_with_aria = soup.find_all(lambda tag: any(attr for attr in tag.attrs if attr.startswith("aria-")))
    if elements_with_aria:
        accessibility_score += 10
    
    # Generate navigation suggestions based on content type and structure
    suggestions = []
    if content_type == "article":
        suggestions.extend([
            "read article content",
            "list headings for structure",
            "navigate to comments section"
        ])
    elif content_type == "news":
        suggestions.extend([
            "list headlines",
            "read top story",
            "find latest news"
        ])
    elif content_type == "form":
        suggestions.extend([
            "list form fields",
            "navigate to submit button",
            "check required fields"
        ])
    
    if structure["navigation"]:
        suggestions.append("explore navigation menu")
    if structure["landmarks"]:
        suggestions.append("list page landmarks")
    
    return {
        "type": content_type,
        "semantic_structure": structure,
        "accessibility": {
            "score": accessibility_score,
            "notes": accessibility_notes
        },
        "suggested_actions": suggestions,
        "title": title,
        "url": driver.current_url
    }

@register_action("read_page")
def read_page(state: State) -> ActionResult:
    """Enhanced page reading with structure analysis"""
    logger.debug("Entering read_page action")
    
    try:
        logger.debug("Getting page source")
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
        
        # Enhanced page analysis
        analysis = analyze_page_structure(state["driver"], soup)
        headlines = extract_headlines(soup) if analysis["type"] == "news" else None
        
        # Find main content area
        main_content = soup.find("main") or soup.find(attrs={"role": "main"}) or soup
        
        # Extract sections
        sections = []
        for section in main_content.find_all(["article", "section", "div"], class_=lambda x: x and any(c in str(x) for c in ["content", "article", "post"])):
            sections.append(extract_section_content(section))
        
        # Clean and extract text
        for tag in soup.find_all(["script", "style", "nav", "footer"]):
            tag.decompose()
            
        text = main_content.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)
        
        # Generate summary if content is long
        summary = None
        if len(content) > 1000:
            summary = content[:1000] + "...\n\n(Content truncated. Use 'read next section' to continue reading.)"
            
        output = ReadPageOutput(
            content=content[:1000] if len(content) > 1000 else content,
            sections=sections,
            summary=summary,
            truncated=len(content) > 1000,
            dynamic_content=bool(state.get("predictions", {}).get("needs_wait"))
        )
        
        # Update state with rich context
        state_updates = {
            "page_context": PageContext(
                type=analysis["type"],
                has_main=analysis["semantic_structure"]["main_content"],
                has_nav=analysis["semantic_structure"]["navigation"],
                has_article=bool(sections),
                has_headlines=bool(headlines),
                has_forms=bool(analysis["semantic_structure"]["forms"]),
                dynamic_content=analysis["semantic_structure"]["has_dynamic_content"],
                scroll_position=0,
                viewport_height=state["driver"].execute_script("return window.innerHeight"),
                total_height=state["driver"].execute_script("return document.documentElement.scrollHeight")
            )
        }
        
        # Format enhanced message with accessibility info and suggestions
        message_parts = []
        message_parts.append(f"Here's what I found on this {analysis['type']} page:\n")
        
        # Add accessibility information
        message_parts.append(f"Accessibility Score: {analysis['accessibility']['score']}/100")
        if analysis['accessibility']['notes']:
            message_parts.append("Accessibility Notes:")
            for note in analysis['accessibility']['notes']:
                message_parts.append(f"- {note}")
        message_parts.append("")  # Add spacing
        
        # Add content summary
        if summary:
            message_parts.append(summary)
            message_parts.append("")
        
        # Add section information
        if sections:
            message_parts.append(f"The page contains {len(sections)} main sections. Use 'read section [number]' to read a specific section.")
        
        # Add headline information
        if headlines:
            message_parts.append(f"\nI found {len(headlines)} headlines. Use 'list headlines' to see them.")
        
        # Add navigation suggestions
        if analysis['suggested_actions']:
            message_parts.append("\nSuggested actions:")
            for action in analysis['suggested_actions']:
                message_parts.append(f"- {action}")
            
        return create_result(
            output=output,
            state_updates=state_updates,
            messages=["\n".join(message_parts)]
        )
        
    except Exception as e:
        logger.error(f"Error reading page: {str(e)}")
        return create_result(error=f"An error occurred while reading the page: {str(e)}")

@register_action("list_headings")
def list_headings(state: State) -> ActionResult:
    """Enhanced heading listing with hierarchy analysis"""
    logger.debug("Entering list_headings action")
    
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
        
        headings = []
        hierarchy = {"h1": [], "h2": {}, "h3": {}, "h4": {}, "h5": {}, "h6": {}}
        current = {"h1": None, "h2": None, "h3": None, "h4": None, "h5": None, "h6": None}
        
        # Find all heading tags with context
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            for heading in soup.find_all(tag):
                text = heading.get_text().strip()
                if text:
                    # Get heading context
                    parent = heading.find_parent(["section", "article", "main", "div"])
                    context = {
                        "section": parent.name if parent else None,
                        "section_class": parent["class"] if parent and "class" in parent.attrs else None,
                        "id": heading.get("id"),
                        "classes": heading.get("class"),
                        "aria_label": heading.get("aria-label")
                    }
                    
                    # Add to flat list
                    headings.append({
                        "text": text,
                        "level": tag,
                        "context": context
                    })
                    
                    # Update hierarchy
                    if tag == "h1":
                        hierarchy["h1"].append(text)
                        current["h1"] = text
                        # Reset lower levels
                        for level in ["h2", "h3", "h4", "h5", "h6"]:
                            current[level] = None
                    else:
                        # Find parent heading
                        parent_level = f"h{int(tag[1])-1}"
                        if current[parent_level]:
                            if parent_level == "h1":
                                if not hierarchy["h2"].get(current["h1"]):
                                    hierarchy["h2"][current["h1"]] = []
                                hierarchy["h2"][current["h1"]].append(text)
                            else:
                                parent_dict = hierarchy[tag]
                                parent_key = current[parent_level]
                                if not parent_dict.get(parent_key):
                                    parent_dict[parent_key] = []
                                parent_dict[parent_key].append(text)
                            current[tag] = text
        
        if headings:
            # Format hierarchical display
            content = []
            for h1 in hierarchy["h1"]:
                content.append(f"# {h1}")
                if h1 in hierarchy["h2"]:
                    for h2 in hierarchy["h2"][h1]:
                        content.append(f"  ## {h2}")
                        if h2 in hierarchy["h3"]:
                            for h3 in hierarchy["h3"][h2]:
                                content.append(f"    ### {h3}")
                                
            output = HeadingOutput(
                headings=headings,
                level="page",
                hierarchy=hierarchy
            )
            
            return create_result(
                output=output,
                state_updates={
                    "page_context": PageContext(
                        **{**state["page_context"].__dict__,
                           "has_headlines": True}
                    )
                },
                messages=[f"Found these headings:\n\n" + "\n".join(content)]
            )
        
        return create_result(
            output=HeadingOutput([], "none", {}),
            error="No headings found on this page"
        )
        
    except Exception as e:
        logger.error(f"Error listing headings: {str(e)}")
        return create_result(error=f"An error occurred while listing headings: {str(e)}")

def extract_headlines(soup: BeautifulSoup) -> List[HeadlineOutput]:
    """Extract headlines with metadata"""
    headlines = []
    main_content = soup.find('main') or soup.find('div', {'role': 'main'}) or soup
    
    # Common navigation/utility words to filter out
    nav_words = {'menu', 'navigation', 'search', 'subscribe', 'sign in', 'log in', 'section'}
    
    for element in main_content.find_all(['h1', 'h2', 'h3', 'a']):
        # Get text and metadata
        text = element.get_text().strip()
        href = element.get('href', '')
        timestamp = element.find(class_=lambda x: x and any(t in str(x).lower() for t in ['time', 'date', 'published'])).get_text() if element.find(class_=lambda x: x and any(t in str(x).lower() for t in ['time', 'date', 'published'])) else None
        category = element.find(class_=lambda x: x and any(tag in str(x).lower() for tag in ['category', 'tag', 'topic'])).get_text() if element.find(class_=lambda x: x and any(tag in str(x).lower() for tag in ['category', 'tag', 'topic'])) else None
        
        # Clean up text
        text = ' '.join(text.split())
        if 'min read' in text:
            text = text.split('min read')[0].strip()
        
        # Skip if empty or too short
        if not text or len(text) < 20:
            continue
            
        # Skip navigation elements
        if any(word in text.lower() for word in nav_words):
            continue
        
        # Get full URL if relative
        if href and not href.startswith('http'):
            href = 'https://www.nytimes.com' + href if href.startswith('/') else href
        
        # Skip duplicate headlines
        if text not in [h.text for h in headlines]:
            headlines.append(HeadlineOutput(
                text=text,
                url=href,
                source=element.find(class_=lambda x: x and 'source' in str(x).lower()).get_text() if element.find(class_=lambda x: x and 'source' in str(x).lower()) else None,
                timestamp=timestamp.get_text() if timestamp else None,
                category=category.get_text() if category else None
            ))
            
        # Limit to reasonable number
        if len(headlines) >= 15:
            break
            
    return headlines

@register_action("list_headlines")
def list_headlines(state: State) -> ActionResult:
    """Enhanced headline listing with metadata"""
    logger.debug("Entering list_headlines action")
    
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
            
        # Get page context
        page_context = state.get("page_context")
        if not isinstance(page_context, PageContext):
            page_context = PageContext(**page_context)
            
        # Extract headlines
        headlines = extract_headlines(soup)
        
        if headlines:
            # Format numbered list with metadata
            content = []
            for i, h in enumerate(headlines):
                headline = f"{i+1}. {h.text}"
                if h.category:
                    headline += f" [{h.category}]"
                if h.timestamp:
                    headline += f" ({h.timestamp})"
                content.append(headline)
                
            content = "\n".join(content)
            content += "\n\nSay 'go to headline [number]' to read an article."
            
            return create_result(
                output=headlines,
                state_updates={
                    "headlines": headlines,
                    "page_context": PageContext(
                        **{**state["page_context"].__dict__,
                           "has_headlines": True}
                    )
                },
                messages=[f"Found these news headlines:\n\n{content}"]
            )
        
        return create_result(
            output=[],
            error="No news headlines found on this page"
        )
        
    except Exception as e:
        logger.error(f"Error listing headlines: {str(e)}")
        return create_result(error=f"An error occurred while listing headlines: {str(e)}")

@register_action("read_section")
def read_section(state: State) -> ActionResult:
    """Read the current or specified section of content"""
    logger.debug("Entering read_section action")
    
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
            
        # Find main content area
        main_content = soup.find("main") or soup.find(attrs={"role": "main"}) or soup
        
        # Extract sections
        sections = []
        for section in main_content.find_all(["article", "section", "div"], class_=lambda x: x and any(c in str(x) for c in ["content", "article", "post"])):
            sections.append(extract_section_content(section))
            
        if not sections:
            # If no explicit sections, treat main content as one section
            sections = [extract_section_content(main_content)]
            
        if sections:
            # Format content
            content = []
            for i, section in enumerate(sections):
                if section["title"]:
                    content.append(f"Section {i+1}: {section['title']}")
                content.append(section["content"])
                content.append("")  # Add spacing between sections
                
            return create_result(
                output=sections,
                messages=["\n".join(content)]
            )
            
        return create_result(
            output=[],
            error="No readable sections found on this page"
        )
        
    except Exception as e:
        logger.error(f"Error reading section: {str(e)}")
        return create_result(error=f"An error occurred while reading the section: {str(e)}")

@register_action("goto_headline")
def goto_headline(state: State) -> ActionResult:
    """Enhanced headline navigation with content preparation"""
    logger.debug("Entering goto_headline action")
    
    try:
        # Get headline number from context
        context = state.get("action_context", "")
        try:
            num = int(''.join(filter(str.isdigit, context))) - 1
        except ValueError:
            return create_result(error="Please specify a headline number")
            
        # Get stored headlines
        headlines = state.get("headlines", [])
        if not headlines:
            return create_result(error="No headlines available. Try listing headlines first")
            
        # Validate headline number
        if num < 0 or num >= len(headlines):
            return create_result(error=f"Invalid headline number. Please choose 1-{len(headlines)}")
            
        # Get URL for selected headline
        headline = headlines[num]
        if not headline.url:
            return create_result(error="Sorry, that headline doesn't have a link")
            
        # Navigate to the URL
        state["driver"].get(headline.url)
        
        # Wait for article content
        try:
            WebDriverWait(state["driver"], 3).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except Exception:
            logger.debug("No article tag found, continuing anyway")
            
        # Analyze new page context with enhanced analysis
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        analysis = analyze_page_structure(state["driver"], soup)
        
        return create_result(
            output=headline,
            state_updates={
                "current_element_index": -1,
                "focusable_elements": [],
                "last_found_element": None,
                "page_context": PageContext(
                    type=analysis["type"],
                    has_main=analysis["semantic_structure"]["main_content"],
                    has_nav=analysis["semantic_structure"]["navigation"],
                    has_article=True,
                    has_headlines=False,
                    has_forms=bool(analysis["semantic_structure"]["forms"]),
                    dynamic_content=analysis["semantic_structure"]["has_dynamic_content"],
                    scroll_position=0,
                    viewport_height=state["driver"].execute_script("return window.innerHeight"),
                    total_height=state["driver"].execute_script("return document.documentElement.scrollHeight")
                ),
                "predictions": ActionPrediction(
                    needs_scroll=True,
                    needs_click=False,
                    needs_wait=True,
                    potential_popups=True,
                    confidence=0.9,
                    reasoning="Article pages often have dynamic content and may need scrolling"
                )
            },
            messages=[
                f"Navigating to article: {headline.text}. The page is loading and being analyzed. You can use 'read content' to start reading the article."
            ]
        )
    except Exception as e:
        logger.error(f"Error in goto_headline: {str(e)}")
        return create_result(error=f"An error occurred while navigating to the headline: {str(e)}")


================================================
File: /src/actions/navigation.py
================================================
"""URL navigation actions for the screen reader application"""

import time
import json
from typing import Dict, Any
from langgraph.graph import END
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from .. import browser
from ..state import State, PageContext
from .base import register_action, create_result
from ..utils.errors import NavigationError, create_error_response
from ..utils.logging import logger
import src.config as config

def get_page_analysis(driver) -> Dict[str, Any]:
    """Get LLM analysis of page type and content"""
    try:
        # Get page content
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Remove scripts and styles
        for tag in soup.find_all(["script", "style"]):
            tag.decompose()
        
        # Get text content
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines[:50])  # First 50 lines for analysis
        
        # Get page metadata
        title = driver.title
        url = driver.current_url
        
        # Prepare prompt for LLM
        prompt = f"""Analyze this webpage and determine its type and key content.
        
        Page Details:
        URL: {url}
        Title: {title}
        Content Preview:
        {content}
        
        Respond with a JSON object containing these exact fields:
        - action: "read" (always use this value)
        - confidence: a number between 0 and 1
        - context: brief description of key content
        - page_type: one of: "news", "search", "video", "article", "social"
        
        Example response:
        {{
            "action": "read",
            "confidence": 0.9,
            "context": "News homepage with breaking news and top stories",
            "page_type": "news"
        }}
        """
        
        try:
            # Get LLM analysis
            response = config.llm.invoke(prompt)
            logger.debug(f"Raw LLM response: {response}")
            
            # Default response if analysis fails
            default_response = {
                "action": "read",
                "confidence": 0.5,
                "context": "News website homepage",
                "page_type": "news"
            }
            
            # Try to parse response if it's a string
            if isinstance(response, str):
                try:
                    # Clean up the string to make it valid JSON
                    cleaned = response.replace("'", '"').strip()
                    if not cleaned.startswith('{'): 
                        cleaned = cleaned[cleaned.find('{'):cleaned.rfind('}')+1]
                    response = json.loads(cleaned)
                except:
                    logger.debug(f"Could not parse LLM response as JSON: {response}")
                    return default_response
            
            # Validate response has required fields
            if (isinstance(response, dict) and 
                all(k in response for k in ['action', 'confidence', 'context', 'page_type'])):
                return response
            else:
                logger.debug(f"Invalid LLM response format: {response}")
                return default_response
                
        except Exception as e:
            logger.debug(f"Error processing LLM response: {str(e)}")
            return default_response
            
    except Exception as e:
        logger.debug(f"Error analyzing page: {str(e)}")
        return None

def wait_for_page_load(driver) -> bool:
    """Wait for page load with proper timeout"""
    try:
        # Wait for document ready state
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        logger.debug("Document ready state complete")
        
        # Wait for any dynamic content
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            pass
            
        return True
        
    except Exception as e:
        logger.error(f"Timeout waiting for page load: {str(e)}")
        return False

# Navigation functionality moved to interaction.py


================================================
File: /src/actions/landmarks.py
================================================
"""Landmark and section-related actions for the screen reader application"""

from typing import Dict, Any, List, Tuple
from langgraph.graph import END
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from .. import browser
from ..state import State
from ..config import LANDMARK_ROLES, LANDMARK_TAGS, SECTION_CLASSES
from ..utils.logging import logger
from ..utils.errors import create_error_response
from . import register_action

def get_landmarks_and_anchors(driver: webdriver.Chrome) -> List[Tuple[WebElement, str]]:
    """Get all ARIA landmarks and anchor points"""
    logger.debug("Getting landmarks and anchors")
    landmarks = []
    
    try:
        # Find main content
        try:
            main = driver.find_element(By.TAG_NAME, "main")
            if main.is_displayed():
                text = main.text.strip()
                if text:
                    landmarks.append((main, f"main: {text[:100]}"))
        except:
            pass
        
        # Find standard HTML5 landmark tags
        for tag in LANDMARK_TAGS:
            try:
                elements = driver.find_elements(By.TAG_NAME, tag)
                for elem in elements:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text:
                            landmarks.append((elem, f"{tag}: {text[:100]}"))
            except:
                continue
        
        # Find elements with ARIA roles
        for role in LANDMARK_ROLES:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, f"[role='{role}']")
                for elem in elements:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text:
                            landmarks.append((elem, f"{role}: {text[:100]}"))
            except:
                continue
        
        return landmarks
        
    except Exception as e:
        logger.error(f"Error getting landmarks: {str(e)}")
        return []

@register_action("goto_landmark")
def goto_landmark(state: State) -> Dict[str, Any]:
    """Navigate to a specific landmark"""
    logger.debug("Entering goto_landmark action")
    target = state.get("action_context", "").lower()
    
    if not target:
        return create_error_response("Please specify which section you want to go to.")
    
    landmarks = get_landmarks_and_anchors(state["driver"])
    
    for element, desc in landmarks:
        if target in desc.lower():
            # Scroll to landmark
            browser.scroll_element_into_view(state["driver"], element)
            time.sleep(0.1)  # Reduced wait time
            
            # Get content
            text = element.text.strip()
            preview = text[:200] + "..." if len(text) > 200 else text
            state["last_found_element"] = element
            
            return {
                "messages": [{"role": "assistant", "content": f"Moved to {desc}. Content preview:\n\n{preview}"}],
                "next": END
            }
    
    return create_error_response(f"Could not find landmark or section matching '{target}'")

@register_action("list_landmarks")
def list_landmarks(state: State) -> Dict[str, Any]:
    """List all landmarks and sections"""
    logger.debug("Entering list_landmarks action")
    try:
        logger.debug("Starting landmark search")
        driver = state["driver"]
        
        # Quick check for main content
        try:
            main = driver.find_element(By.TAG_NAME, "main")
            logger.debug(f"Quick check - main element found: {main.is_displayed()}")
        except:
            logger.debug("Quick check - no main element found")
        
        # Get all landmarks
        landmarks = get_landmarks_and_anchors(driver)
        logger.debug(f"Found {len(landmarks)} landmarks")
        
        if landmarks:
            content = "\n".join(desc for _, desc in landmarks)
            logger.debug("Successfully compiled landmark descriptions")
            return {
                "messages": [{"role": "assistant", "content": f"Found these landmarks and sections:\n\n{content}"}],
                "next": END
            }
        else:
            logger.debug("No landmarks found")
            return create_error_response("No landmarks or major sections found on this page.")
            
    except Exception as e:
        logger.error(f"Error in list_landmarks: {str(e)}")
        return create_error_response("An error occurred while listing landmarks. Please try again.")

@register_action("read_section")
def read_section(state: State) -> Dict[str, Any]:
    """Read the current section content"""
    logger.debug("Entering read_section action")
    
    if "current_element_index" not in state or not state.get("focusable_elements"):
        return create_error_response(
            "Please navigate to a section or element first using next/previous element or goto landmark."
        )
    
    try:
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
                "next": END
            }
        else:
            return create_error_response("No readable content found in current section.")
            
    except Exception as e:
        logger.error(f"Error in read_section: {str(e)}")
        return create_error_response("An error occurred while reading the section. Please try again.")


================================================
File: /src/utils/__init__.py
================================================
"""Utility modules for the Web Reader application"""

from . import errors
from . import logging

__all__ = ["errors", "logging"]


================================================
File: /src/utils/errors.py
================================================
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


================================================
File: /src/utils/logging.py
================================================
"""Enhanced logging system with structured logging and context tracking"""

import logging
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager

@dataclass
class LogContext:
    """Context information for logging"""
    action: str
    state_id: str
    timestamp: float
    duration: Optional[float] = None
    predictions: Optional[Dict[str, Any]] = None
    page_context: Optional[Dict[str, Any]] = None
    element_context: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    input: Optional[str] = None

class StructuredLogger:
    """Enhanced logger with context tracking and structured output"""
    
    def __init__(self, name: str):
        self.name = name
        self.context_stack: List[LogContext] = []
        self._setup_logging()
        
    def _setup_logging(self) -> None:
        """Configure logging with specialized handlers"""
        # Create logs directory structure
        os.makedirs('logs/actions', exist_ok=True)
        os.makedirs('logs/predictions', exist_ok=True)
        os.makedirs('logs/performance', exist_ok=True)
        os.makedirs('logs/errors', exist_ok=True)
        
        # Create base logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        
        # JSON formatter for structured logging
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage()
                }
                
                # Add context if available
                if hasattr(record, 'context'):
                    # Convert dataclass objects to dictionaries
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dataclass_fields__'):
                                context[key] = asdict(value)
                            elif hasattr(value, '__dict__'):
                                context[key] = value.__dict__
                    log_data['context'] = context
                    
                return json.dumps(log_data)
        
        # Specialized formatters
        class ActionFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dataclass_fields__'):
                                context[key] = asdict(value)
                            elif hasattr(value, '__dict__'):
                                context[key] = value.__dict__
                    action_data = {
                        "timestamp": self.formatTime(record),
                        "action": context.get("action"),
                        "duration": context.get("duration"),
                        "state_id": context.get("state_id")
                    }
                    return json.dumps(action_data)
                return super().format(record)

        class PredictionFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dataclass_fields__'):
                                context[key] = asdict(value)
                            elif hasattr(value, '__dict__'):
                                context[key] = value.__dict__
                    pred_data = {
                        "timestamp": self.formatTime(record),
                        "action": context.get("action"),
                        "predictions": context.get("predictions")
                    }
                    return json.dumps(pred_data)
                return super().format(record)

        class PerformanceFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dict__'):
                                context[key] = asdict(value)
                    perf_data = {
                        "timestamp": self.formatTime(record),
                        "action": context.get("action"),
                        "duration": context.get("duration")
                    }
                    return json.dumps(perf_data)
                return super().format(record)

        class ErrorFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dict__'):
                                context[key] = asdict(value)
                    error_data = {
                        "timestamp": self.formatTime(record),
                        "error_message": context.get("error_message"),
                        "action": context.get("action_context", {}).get("action")
                    }
                    return json.dumps(error_data)
                return super().format(record)

        # Configure handlers with specialized formatters
        handlers = [
            # Main debug log - keeps full context
            (logging.FileHandler('logs/debug.log', mode='w', encoding='utf-8'),
             logging.DEBUG,
             JsonFormatter()),
             
            # Action tracking - minimal context
            (logging.FileHandler('logs/actions/actions.log', mode='w', encoding='utf-8'),
             logging.INFO,
             ActionFormatter()),
             
            # Prediction monitoring - predictions only
            (logging.FileHandler('logs/predictions/predictions.log', mode='w', encoding='utf-8'),
             logging.DEBUG,
             PredictionFormatter()),
             
            # Performance metrics - timing only
            (logging.FileHandler('logs/performance/performance.log', mode='w', encoding='utf-8'),
             logging.INFO,
             PerformanceFormatter()),
             
            # Error tracking - error context only
            (logging.FileHandler('logs/errors/errors.log', mode='w', encoding='utf-8'),
             logging.ERROR,
             ErrorFormatter()),
             
            # Console output (human readable)
            (logging.StreamHandler(),
             logging.INFO,
             logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S'))
        ]
        
        for handler, level, formatter in handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    @contextmanager
    def action_context(self, action: str, state_id: str, **kwargs):
        """Context manager for tracking action execution"""
        context = LogContext(
            action=action,
            state_id=state_id,
            timestamp=time.time(),
            **kwargs
        )
        self.context_stack.append(context)
        
        try:
            yield context
        except Exception:
            # Don't log errors in context manager
            raise
        else:
            context.duration = time.time() - context.timestamp
            self._log_action_complete(context)
        finally:
            self.context_stack.pop()
    
    def _log_action_complete(self, context: LogContext) -> None:
        """Log action completion with metrics"""
        log_data = asdict(context)
        
        # Log action completion
        self.logger.info(
            f"Action complete: {context.action}",
            extra={"context": log_data}
        )
        
        # Log performance metrics
        if context.duration is not None:
            self.logger.info(
                f"Performance metrics for {context.action}",
                extra={
                    "context": {
                        "action": context.action,
                        "duration": context.duration,
                        "timestamp": context.timestamp
                    }
                }
            )
        
        # Log prediction accuracy if available
        if context.predictions:
            self.logger.debug(
                f"Prediction analysis for {context.action}",
                extra={
                    "context": {
                        "action": context.action,
                        "predictions": context.predictions
                    }
                }
            )
    
    def log_state_transition(self, from_state: str, to_state: str, context: Dict[str, Any]) -> None:
        """Log state transitions with context"""
        self.logger.info(
            f"State transition: {from_state} -> {to_state}",
            extra={"context": context}
        )
    
    def log_prediction(self, prediction: Dict[str, Any], actual: Dict[str, Any]) -> None:
        """Log and analyze prediction accuracy"""
        self.logger.debug(
            "Prediction analysis",
            extra={
                "context": {
                    "prediction": prediction,
                    "actual": actual,
                    "timestamp": time.time()
                }
            }
        )
    
    def log_error(self, error: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log errors with rich context"""
        current_context = self.context_stack[-1] if self.context_stack else None
        
        error_context = {
            "error_message": error,
            "timestamp": time.time(),
            "action_context": asdict(current_context) if current_context else None,
            "additional_context": context
        }
        
        # Log to error file with context
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler) and 'errors.log' in handler.baseFilename:
                handler.emit(
                    self.logger.makeRecord(
                        self.name,
                        logging.ERROR,
                        "(unknown file)", 0,
                        error,
                        None, None,
                        extra={"context": error_context}
                    )
                )
        
        # Log to console without context to avoid exc_info conflict
        self.logger.error(f"Error: {error}")
    
    def debug(self, msg: str, **kwargs) -> None:
        self.logger.debug(msg, extra=kwargs)
    
    def info(self, msg: str, **kwargs) -> None:
        self.logger.info(msg, extra=kwargs)
    
    def warning(self, msg: str, **kwargs) -> None:
        self.logger.warning(msg, extra=kwargs)
    
    def error(self, msg: str, **kwargs) -> None:
        self.logger.error(msg, extra=kwargs)
    
    def critical(self, msg: str, **kwargs) -> None:
        self.logger.critical(msg, extra=kwargs)

# Create and configure the enhanced logger
logger = StructuredLogger('screen_reader')


================================================
File: /src/utils/error_recovery.py
================================================
"""LLM-based error recovery system for the screen reader application"""

import json
from typing import Dict, Any
from langgraph.graph import END

from src.state import State
from src.config import llm, VALID_ACTIONS
from src.utils.errors import create_error_response
from src.utils.logging import logger

def generate_error_recovery_prompt(error: Exception, state: State, failed_action: str) -> str:
    """Generate prompt for LLM to analyze error and suggest recovery"""
    history = state.get("execution_history", [])
    sub_tasks = state.get("sub_tasks", [])
    completed = state.get("completed_tasks", [])
    
    return f"""
    An error occurred while executing action '{failed_action}'.
    Error: {str(error)}
    
    Current state:
    - Page context: {state.get('page_context')}
    - Current action: {state.get('current_action')}
    - Action context: {state.get('action_context')}
    - Attempts: {state.get('attempts', 0)}
    - Remaining sub-tasks: {sub_tasks}
    - Completed tasks: {completed}
    
    User request: {state['messages'][-1].content if state['messages'] else 'No message'}
    Execution history: {history}
    
    Analyze the error and suggest a recovery strategy. Consider:
    1. Task complexity - Should we break this into smaller steps?
    2. Dependencies - Are we missing required information or actions?
    3. Alternative approaches - Is there a better way to achieve the goal?
    4. Context needs - Do we need more information from the user?
    
    Return JSON with:
    - diagnosis: Brief analysis of what went wrong
    - strategy: One of ["retry", "alternative", "clarify", "decompose", "abort"]
    - sub_tasks: List of smaller tasks if strategy is "decompose"
    - dependencies: Dictionary mapping tasks to their dependencies
    - suggested_action: Alternative action from {list(VALID_ACTIONS.keys())} if strategy is "alternative"
    - confidence: Confidence in suggested strategy (0-1)
    - needed_context: Additional information needed if strategy is "clarify"
    - user_message: Clear explanation for the user
    """
def handle_error_with_llm(error: Exception, state: State) -> Dict[str, Any]:
    """Use LLM to analyze error and suggest recovery steps"""
    try:
        # Get recovery suggestion from LLM
        prompt = generate_error_recovery_prompt(error, state, state['current_action'])
        response = llm.invoke(prompt)
        
        try:
            recovery = json.loads(response.content)
            logger.debug(f"Error recovery suggestion: {json.dumps(recovery, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding LLM response: {str(e)}")
            return create_error_response(
                f"I encountered an error while trying to recover. Could you try rephrasing your request? Error: {str(e)}"
            )
        
        # Update state with recovery strategy
        state_updates = {
            "strategy": recovery["strategy"],
            "error": None  # Clear error since we're handling it
        }
        
        if recovery["strategy"] == "decompose":
            # Set up task decomposition
            state_updates.update({
                "sub_tasks": recovery["sub_tasks"],
                "task_dependencies": recovery["dependencies"],
                "completed_tasks": [],
                "attempts": 0
            })
            
        elif recovery["strategy"] == "alternative":
            # Try alternative approach
            state_updates.update({
                "current_action": recovery["suggested_action"],
                "action_context": recovery["needed_context"],
                "attempts": 0
            })
            
        elif recovery["strategy"] == "clarify":
            # Need more information from user
            return {
                "messages": [{"role": "assistant", "content": recovery["needed_context"]}],
                "strategy": "clarify",
                "next": END
            }
            
        # Add explanation message
        return {
            "messages": [{"role": "assistant", "content": recovery["user_message"]}],
            **state_updates,
            "next": "plan" if recovery["strategy"] in ["decompose", "clarify"] else "execute"
        }
            
    except Exception as e:
        logger.error(f"Error in error recovery: {str(e)}")
        return create_error_response(
            "I encountered an error while trying to recover. Could you try rephrasing your request?"
        )


