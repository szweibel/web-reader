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
