from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_ollama import ChatOllama
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from bs4 import BeautifulSoup
import json
import time

# State Management
class State(TypedDict):
    messages: Annotated[list, add_messages]
    driver: webdriver.Chrome
    current_element_index: int
    focusable_elements: list
    context: str
    action: str
    confidence: float

# Browser Setup
def setup_browser() -> webdriver.Chrome:
    """Initialize headless Chrome browser"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-pipe")
    return webdriver.Chrome(options=chrome_options)

# Element Helpers
def get_focusable_elements(driver: webdriver.Chrome) -> List[WebElement]:
    """Get all focusable elements on the page"""
    focusable_selectors = [
        "a[href]", "button", "input", "select", "textarea",
        "[tabindex]:not([tabindex='-1'])", "[contenteditable='true']",
        "[role='button']", "[role='link']", "[role='menuitem']"
    ]
    elements = driver.find_elements(By.CSS_SELECTOR, ", ".join(focusable_selectors))
    return [e for e in elements if e.is_displayed()]

def get_landmarks_and_anchors(driver: webdriver.Chrome) -> List[tuple]:
    """Get all ARIA landmarks and anchor points"""
    landmarks = []
    
    # Find elements with ARIA roles
    for role in ["banner", "complementary", "contentinfo", "form", "main", "navigation", "region", "search"]:
        elements = driver.find_elements(By.XPATH, f"//*[@role='{role}']")
        for element in elements:
            desc = element.get_attribute("aria-label") or element.get_attribute("aria-labelledby") or role
            landmarks.append((element, desc))
    
    # Find elements with standard HTML5 landmark tags
    for tag in ["header", "nav", "main", "aside", "footer", "form", "section"]:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for element in elements:
            landmarks.append((element, tag))
    
    return landmarks

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

# Action Handlers
def determine_action(state: State) -> dict:
    """Determine which action to take based on user input"""
    messages = state["messages"]
    last_message = messages[-1][1] if messages else ""

    action_prompt = f"""Analyze this user message and determine the next action: "{last_message}"
    
    Available actions and their use cases:
    NAVIGATE - Go to website/URL (e.g., "go to", "open", "visit")
    READ - Read page content (e.g., "read", "what does it say")
    CLICK - Click elements (e.g., "click", "press", "select")
    TYPE - Enter text (e.g., "type", "enter", "input")
    FIND - Search text (e.g., "find", "search", "locate")
    LIST_HEADINGS - Show headings (e.g., "show headings", "what are the headings")
    NEXT_ELEMENT - Next element (e.g., "next", "forward")
    PREV_ELEMENT - Previous element (e.g., "previous", "back") 
    GOTO_LANDMARK - Go to section (e.g., "go to main", "jump to nav")
    LIST_LANDMARKS - Show landmarks (e.g., "list landmarks", "show sections")
    READ_SECTION - Read current section (e.g., "read this part")
    CHECK_ELEMENT - Check element properties (e.g., "is this clickable", "is that a link")

    Return JSON with:
    - action: The action to take
    - confidence: How confident (0-1)
    - context: Any extracted context needed (e.g., URL, text to click)"""

    try:
        response = llm.invoke([{"role": "user", "content": action_prompt}])
        action_data = json.loads(str(response))
        state["action"] = action_data.get("action")
        state["confidence"] = action_data.get("confidence", 0)
        state["context"] = action_data.get("context", "")
        
        if state["confidence"] < 0.7:
            return {
                "messages": [("assistant", "I'm not sure what action you want to take. Could you rephrase your request?")],
                "next": None
            }
            
        return {"next": state["action"].lower()}
    except Exception as e:
        return {
            "messages": [("assistant", f"Error determining action: {str(e)}")],
            "next": None
        }

def navigate(state: State) -> dict:
    """Navigate to a URL"""
    url = state["context"]
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    try:
        state["driver"].get(url)
        time.sleep(2)  # Wait for page load
        state["focusable_elements"] = get_focusable_elements(state["driver"])
        state["current_element_index"] = -1
        return {
            "messages": [("assistant", f"Navigated to {url}. Would you like me to read the page content?")],
            "next": "continue_check"
        }
    except Exception as e:
        return {
            "messages": [("assistant", f"Failed to navigate to {url}: {str(e)}")],
            "next": None
        }

def read_page(state: State) -> dict:
    """Read the current page content"""
    soup = BeautifulSoup(state["driver"].page_source, "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    content = "\n".join(lines)
    content = content[:1000] + "..." if len(content) > 1000 else content
    
    return {
        "messages": [("assistant", f"Here's what I found on the page:\n\n{content}")],
        "next": "continue_check"
    }

def click_element(state: State) -> dict:
    """Click an element on the page"""
    element_desc = state["context"]
    
    strategies = [
        (By.LINK_TEXT, element_desc),
        (By.XPATH, f"//button[contains(text(), '{element_desc}')]"),
        (By.XPATH, f"//*[@role='button' and contains(text(), '{element_desc}')]"),
        (By.XPATH, f"//*[contains(text(), '{element_desc}') and (@onclick or @role='button')]")
    ]
    
    for by, value in strategies:
        try:
            element = state["driver"].find_element(by, value)
            if element.is_displayed():
                state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5)
                element.click()
                time.sleep(1)
                return {
                    "messages": [("assistant", f"Clicked element: '{element.text or element_desc}'. Would you like me to read the updated content?")],
                    "next": "continue_check"
                }
        except:
            continue
    
    return {
        "messages": [("assistant", f"Could not find clickable element matching '{element_desc}'")],
        "next": None
    }

def next_element(state: State) -> dict:
    """Move to next focusable element"""
    if not state["focusable_elements"]:
        state["focusable_elements"] = get_focusable_elements(state["driver"])
        state["current_element_index"] = -1
    
    if not state["focusable_elements"]:
        return {
            "messages": [("assistant", "No focusable elements found on the page.")],
            "next": None
        }
    
    state["current_element_index"] = (state["current_element_index"] + 1) % len(state["focusable_elements"])
    element = state["focusable_elements"][state["current_element_index"]]
    
    state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    
    tag = element.tag_name
    text = element.text or element.get_attribute("value") or element.get_attribute("placeholder")
    role = element.get_attribute("role") or tag
    
    return {
        "messages": [("assistant", f"Moved to {role}: {text}")],
        "next": "continue_check"
    }

def prev_element(state: State) -> dict:
    """Move to previous focusable element"""
    if not state["focusable_elements"]:
        state["focusable_elements"] = get_focusable_elements(state["driver"])
        state["current_element_index"] = 0
    
    if not state["focusable_elements"]:
        return {
            "messages": [("assistant", "No focusable elements found on the page.")],
            "next": None
        }
    
    state["current_element_index"] = (state["current_element_index"] - 1) % len(state["focusable_elements"])
    element = state["focusable_elements"][state["current_element_index"]]
    
    state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    
    tag = element.tag_name
    text = element.text or element.get_attribute("value") or element.get_attribute("placeholder")
    role = element.get_attribute("role") or tag
    
    return {
        "messages": [("assistant", f"Moved to {role}: {text}")],
        "next": "continue_check"
    }

def list_landmarks(state: State) -> dict:
    """List all landmarks and sections"""
    landmarks = get_landmarks_and_anchors(state["driver"])
    if landmarks:
        content = "\n".join(f"- {desc}" for _, desc in landmarks)
        return {
            "messages": [("assistant", f"Found these landmarks and sections:\n\n{content}")],
            "next": "continue_check"
        }
    else:
        return {
            "messages": [("assistant", "No landmarks or major sections found on this page.")],
            "next": None
        }

def goto_landmark(state: State) -> dict:
    """Navigate to a specific landmark"""
    target = state["context"].lower()
    landmarks = get_landmarks_and_anchors(state["driver"])
    
    for element, desc in landmarks:
        if target in desc.lower():
            state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            
            text = element.text.strip()
            preview = text[:200] + "..." if len(text) > 200 else text
            
            return {
                "messages": [("assistant", f"Moved to {desc}. Content preview:\n\n{preview}")],
                "next": "continue_check"
            }
    
    return {
        "messages": [("assistant", f"Could not find landmark or section matching '{target}'")],
        "next": None
    }

def list_headings(state: State) -> dict:
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
            "messages": [("assistant", f"Found these headings:\n\n{content}")],
            "next": "continue_check"
        }
    else:
        return {
            "messages": [("assistant", "No headings found on this page.")],
            "next": None
        }

def should_continue(state: State) -> dict:
    """Determine if we should continue processing"""
    messages = state.get("messages", [])
    if not messages:
        return {"next": None}
        
    last_message = messages[-1][1] if messages else ""
    
    if "Found these landmarks" in last_message:
        return {
            "messages": [("assistant", "Which section would you like to go to? You can say 'go to [section name]'")],
            "next": "determine_action"
        }
    
    if "Content preview:" in last_message:
        return {
            "messages": [("assistant", "Would you like me to read this section? Say 'read section' to view the content.")],
            "next": "determine_action"
        }
    
    if "Here's what I found" in last_message:
        return {
            "messages": [("assistant", "You can say 'next element' to move forward, 'previous element' to go back, or 'list landmarks' to see all sections.")],
            "next": "determine_action"
        }
    
    return {"next": None}

# Build the graph
def build_graph() -> StateGraph:
    graph_builder = StateGraph(State)
    
    # Add nodes
    graph_builder.add_node("determine_action", determine_action)
    graph_builder.add_node("navigate", navigate)
    graph_builder.add_node("read_page", read_page)
    graph_builder.add_node("click_element", click_element)
    graph_builder.add_node("next_element", next_element)
    graph_builder.add_node("prev_element", prev_element)
    graph_builder.add_node("list_landmarks", list_landmarks)
    graph_builder.add_node("goto_landmark", goto_landmark)
    graph_builder.add_node("list_headings", list_headings)
    graph_builder.add_node("continue_check", should_continue)
    
    # Add edges
    actions = ["navigate", "read_page", "click_element", "next_element", 
              "prev_element", "list_landmarks", "goto_landmark", "list_headings"]
              
    for action in actions:
        graph_builder.add_edge("determine_action", action)
        graph_builder.add_edge(action, "continue_check")
    
    graph_builder.add_edge("continue_check", "determine_action")
    
    # Set entry point
    graph_builder.set_entry_point("determine_action")
    
    return graph_builder.compile()

def main():
    print("Initializing browser...")
    driver = setup_browser()
    graph = build_graph()

    try:
        print("\nNatural Language Screen Reader")
        print("You can give commands like:")
        print("- 'Go to example.com'")
        print("- 'Read the current page'")
        print("- 'Click the login button'")
        print("- 'Move to next element'")
        print("- 'Go to previous element'")
        print("- 'List all landmarks'")
        print("- 'Go to main content'")
        print("- 'Show headings'")
        print("\nType 'exit' to quit")
        
        while True:
            user_input = input("\nWhat would you like me to do? ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                break
            
            state = {
                "messages": [("user", user_input)],
                "driver": driver,
                "current_element_index": -1,
                "focusable_elements": [],
                "action": "",
                "confidence": 0.0,
                "context": ""
            }
            
            try:
                for event in graph.stream(state):
                    for step_name, step_value in event.items():
                        if "messages" in step_value and step_value["messages"]:
                            for msg in step_value["messages"]:
                                if isinstance(msg, tuple) and len(msg) == 2:
                                    role, content = msg
                                    if role == "assistant":
                                        print(f"\n{content}")
            except Exception as e:
                print(f"\nError: {str(e)}")
                
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()
