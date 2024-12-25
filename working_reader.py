#!/usr/bin/env python3
import json
from typing import Annotated, TypedDict
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_ollama import ChatOllama
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import time

class State(TypedDict):
    messages: Annotated[list, add_messages]
    driver: webdriver.Chrome
    current_element_index: int
    focusable_elements: list

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
    landmarks = []
    
    # Find elements with ARIA roles
    for role in ["banner", "complementary", "contentinfo", "form", "main", "navigation", "region", "search"]:
        elements = driver.find_elements(By.CSS_SELECTOR, f"[role='{role}']")
        for elem in elements:
            if elem.is_displayed():
                text = elem.text.strip()
                if text:
                    landmarks.append((elem, f"{role}: {text[:100]}"))
    
    # Find elements with standard HTML5 landmark tags
    for tag in ["header", "nav", "main", "aside", "footer", "form", "section"]:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for elem in elements:
            if elem.is_displayed():
                text = elem.text.strip()
                if text:
                    landmarks.append((elem, f"{tag}: {text[:100]}"))
    
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

def process_command(state: State):
    """Process user command and execute appropriate action"""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""

    action_prompt = f"""Analyze this user message and determine the next action: "{last_message}"
    
    Available actions and their use cases:
    NAVIGATE - Go to website/URL (e.g., "go to", "open", "visit")
    READ - Read page content (e.g., "read", "what does it say")
    CLICK - Click elements (e.g., "click", "press", "select")
    FIND - Search text (e.g., "find", "search", "locate")
    LIST_HEADINGS - Show headings (e.g., "show headings", "what are the headings")
    NEXT_ELEMENT - Next element (e.g., "next", "forward")
    PREV_ELEMENT - Previous element (e.g., "previous", "back") 
    GOTO_LANDMARK - Go to section (e.g., "go to main", "jump to nav")
    LIST_LANDMARKS - Show landmarks (e.g., "list landmarks", "show sections")
    READ_SECTION - Read current section (e.g., "read this part")

    Return JSON with:
    - action: The action to take
    - confidence: How confident (0-1)
    - context: Any extracted context needed (e.g., URL, text to click)"""

    try:
        # Get LLM response
        response = llm.invoke([{
            "role": "system",
            "content": """You are a screen reader assistant. Always respond with a valid JSON object containing:
            - action: One of the allowed actions (NAVIGATE, READ, etc.)
            - confidence: A number between 0 and 1
            - context: Any relevant context for the action
            Example: {"action": "NAVIGATE", "confidence": 0.95, "context": "google.com"}"""
        }, {
            "role": "user", 
            "content": action_prompt
        }]).content.strip()
        print(f"\nDebug - Raw LLM response: {response}")
        
        # Clean up response to ensure valid JSON
        response = response.replace("'", '"').replace('\n', ' ')
        if not response.startswith('{'):
            response = '{' + response.split('{', 1)[1]
        if not response.endswith('}'):
            response = response.rsplit('}', 1)[0] + '}'
        
        # Parse and validate response
        result = json.loads(response)
        print(f"\nDebug - Parsed result: {json.dumps(result, indent=2)}")
        
        action = result.get("action", "").upper()
        confidence = result.get("confidence", 0)
        context = result.get("context", "")
        
        if not action or confidence < 0.7:
            return {
                "messages": [("assistant", "I'm not sure what action you want to take. Could you rephrase your request?")]
            }
        
        # Execute the action
        if action == "NAVIGATE":
            url = context
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            try:
                state["driver"].get(url)
                time.sleep(2)
                return {
                    "messages": [("assistant", f"Navigated to {url}. Would you like me to read the page content?")]
                }
            except Exception as e:
                return {
                    "messages": [("assistant", f"Failed to navigate to {url}. Please try a different URL.")]
                }
                
        elif action == "READ":
            soup = BeautifulSoup(state["driver"].page_source, "html.parser")
            for tag in soup.find_all(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            content = "\n".join(lines)
            content = content[:1000] + "..." if len(content) > 1000 else content
            return {
                "messages": [("assistant", f"Here's what I found on the page:\n\n{content}")]
            }
            
        elif action == "CLICK":
            element_desc = context
            strategies = [
                (By.LINK_TEXT, element_desc),
                (By.XPATH, f"//a[normalize-space()='{element_desc}']"),
                (By.XPATH, f"//button[normalize-space()='{element_desc}']"),
                (By.XPATH, f"//*[@role='button' and normalize-space()='{element_desc}']"),
                (By.XPATH, f"//*[@role='link' and normalize-space()='{element_desc}']"),
                (By.PARTIAL_LINK_TEXT, element_desc),
                (By.XPATH, f"//*[contains(normalize-space(), '{element_desc}') and (@onclick or @role='button' or @role='link' or name()='a' or name()='button')]")
            ]
            
            for by, value in strategies:
                try:
                    elements = state["driver"].find_elements(by, value)
                    visible_elements = [e for e in elements if e.is_displayed()]
                    if visible_elements:
                        element = visible_elements[0]
                        state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        time.sleep(0.5)
                        element.click()
                        time.sleep(1)
                        return {
                            "messages": [("assistant", f"Clicked element: '{element.text or element_desc}'. Would you like me to read the updated content?")]
                        }
                except Exception as e:
                    continue
            
            return {
                "messages": [("assistant", f"Could not find clickable element matching '{element_desc}'. Try using the exact text as shown on the page.")]
            }
            
        elif action == "FIND":
            search_text = context
            strategies = [
                (By.XPATH, f"//*[contains(text(), '{search_text}')]"),
                (By.ID, search_text),
                (By.CLASS_NAME, search_text),
                (By.NAME, search_text)
            ]
            
            for by, value in strategies:
                try:
                    element = state["driver"].find_element(by, value)
                    return {
                        "messages": [("assistant", f"Found content: {element.text}")]
                    }
                except:
                    continue
            
            return {
                "messages": [("assistant", f"Could not find content matching '{search_text}'")]
            }
            
        elif action == "LIST_HEADINGS":
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
                    "messages": [("assistant", f"Found these headings:\n\n{content}")]
                }
            else:
                return {
                    "messages": [("assistant", "No headings found on this page.")]
                }
            
        elif action == "NEXT_ELEMENT":
            if "focusable_elements" not in state:
                state["focusable_elements"] = get_focusable_elements(state["driver"])
                state["current_element_index"] = -1
            
            if not state["focusable_elements"]:
                return {
                    "messages": [("assistant", "No focusable elements found on the page.")]
                }
            
            state["current_element_index"] = (state["current_element_index"] + 1) % len(state["focusable_elements"])
            element = state["focusable_elements"][state["current_element_index"]]
            
            state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            
            tag_name = element.tag_name
            text = element.text or element.get_attribute("value") or element.get_attribute("placeholder")
            role = element.get_attribute("role") or tag_name
            
            return {
                "messages": [("assistant", f"Moved to {role}: {text}")]
            }
            
        elif action == "PREV_ELEMENT":
            if "focusable_elements" not in state:
                state["focusable_elements"] = get_focusable_elements(state["driver"])
                state["current_element_index"] = 0
            
            if not state["focusable_elements"]:
                return {
                    "messages": [("assistant", "No focusable elements found on the page.")]
                }
            
            state["current_element_index"] = (state["current_element_index"] - 1) % len(state["focusable_elements"])
            element = state["focusable_elements"][state["current_element_index"]]
            
            state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            
            tag_name = element.tag_name
            text = element.text or element.get_attribute("value") or element.get_attribute("placeholder")
            role = element.get_attribute("role") or tag_name
            
            return {
                "messages": [("assistant", f"Moved to {role}: {text}")]
            }
            
        elif action == "LIST_LANDMARKS":
            landmarks = get_landmarks_and_anchors(state["driver"])
            if landmarks:
                content = "\n".join(desc for _, desc in landmarks)
                return {
                    "messages": [("assistant", f"Found these landmarks and sections:\n\n{content}")]
                }
            else:
                return {
                    "messages": [("assistant", "No landmarks or major sections found on this page.")]
                }
                
        elif action == "GOTO_LANDMARK":
            target = context
            landmarks = get_landmarks_and_anchors(state["driver"])
            for element, desc in landmarks:
                if target.lower() in desc.lower():
                    state["driver"].execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    time.sleep(0.5)
                    text = element.text.strip()
                    preview = text[:200] + "..." if len(text) > 200 else text
                    return {
                        "messages": [("assistant", f"Moved to {desc}. Content preview:\n\n{preview}")]
                    }
            
            return {
                "messages": [("assistant", f"Could not find landmark or section matching '{target}'")]
            }
            
        elif action == "READ_SECTION":
            if "current_element_index" not in state or not state.get("focusable_elements"):
                return {
                    "messages": [("assistant", "Please navigate to a section or element first using next/previous element or goto landmark.")]
                }
            
            element = state["focusable_elements"][state["current_element_index"]]
            text = element.text.strip()
            if not text:
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
                    "messages": [("assistant", f"Content of current section:\n\n{preview}")]
                }
            else:
                return {
                    "messages": [("assistant", "No readable content found in current section.")]
                }
        
        return {
            "messages": [("assistant", "I'm not sure how to handle that action. Please try a different command.")]
        }
        
    except Exception as e:
        print(f"\nDebug - Error: {str(e)}")
        return {
            "messages": [("assistant", "I encountered an error processing your request. Please try again.")]
        }

# Build the graph
graph_builder = StateGraph(State)
graph_builder.add_node("process", process_command)
graph_builder.set_entry_point("process")

# Compile the graph
graph = graph_builder.compile()

def main():
    print("Initializing browser...")
    driver = setup_browser()
    
    try:
        print("\nNatural Language Screen Reader")
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
            user_input = input("\nWhat would you like me to do? ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                break
                
            try:
                for event in graph.stream({
                    "messages": [("user", user_input)],
                    "driver": driver,
                    "current_element_index": -1,
                    "focusable_elements": []
                }):
                    if event is None:
                        continue
                    for key, value in event.items():
                        if isinstance(value, dict) and "messages" in value:
                            for msg in value["messages"]:
                                if isinstance(msg, tuple) and len(msg) == 2:
                                    role, content = msg
                                    if role == "assistant" and content:
                                        print(f"\n{content}")
            except Exception as e:
                print(f"\nError processing command: {str(e)}")
                
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()
