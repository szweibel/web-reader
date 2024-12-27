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
