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
from .reading import ActionResult, create_result, analyze_content_structure

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
