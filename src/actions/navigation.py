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
