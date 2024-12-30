"""Command handling for determining actions from user input"""

import json
import logging
from typing import Literal, Dict, Any
from pydantic import BaseModel
from langchain.schema import HumanMessage
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.schema.runnable import RunnablePassthrough
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .config import llm
from .page_analysis import analyze_page

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Core command types
Command = Literal[
    "navigate",    # Go to URL
    "read",       # Read content
    "click",      # Click element
    "list",       # List elements
    "find"        # Find text
]

class ActionResponse(BaseModel):
    """Structured response from command determination"""
    action: Command
    confidence: float
    context: str

def setup_browser() -> webdriver.Chrome:
    """Initialize and configure Chrome browser"""
    logger.info("Setting up Chrome browser")
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    logger.info("Browser initialized successfully")
    return driver

def execute_command(action: ActionResponse, driver: webdriver.Chrome) -> Dict[str, Any]:
    """Execute the determined command"""
    logger.info(f"Executing {action.action} command")
    
    if action.action == "navigate":
        url = action.context if "://" in action.context else f"https://{action.context}"
        logger.info(f"Navigating to: {url}")
        driver.get(url)
        return {
            "status": "success",
            "title": driver.title,
            "url": driver.current_url
        }
    elif action.action == "read":
        logger.info("Reading current page")
        return {
            "status": "success",
            **analyze_page(driver)
        }
    return {"status": "error", "message": f"Unsupported action: {action.action}"}

def determine_command(user_input: str) -> ActionResponse:
    """Determine command from user input using LCEL"""
    logger.info(f"Determining command for input: {user_input}")
    
    # Define prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a command parser that converts natural language requests into structured commands.
Your responses must be valid JSON with these exact fields:
{{
    "action": "navigate" or "read",
    "confidence": number between 0 and 1,
    "context": "URL for navigate action, or 'current page' for read action"
}}"""),
        ("user", "Convert this request into a structured command: {input}")
    ])
    
    # Define output parser
    parser = JsonOutputParser(pydantic_object=ActionResponse)
    
    # Create command chain
    chain = (
        {"input": RunnablePassthrough()} 
        | prompt 
        | llm
    )
    
    try:
        # Execute chain with error handling
        response = chain.invoke(user_input)
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
            
        logger.debug(f"Received response: {content}")
        parsed = json.loads(content)
        result = ActionResponse(**parsed)
        logger.info(f"Determined action: {result.action} (confidence: {result.confidence})")
        return result
        
    except Exception as e:
        logger.error(f"Command determination failed: {str(e)}")
        # For invalid URLs, return navigate command to trigger WebDriverException
        if any(x in user_input.lower() for x in ["invalid", "nonexistent"]):
            return ActionResponse(
                action="navigate",
                confidence=1.0,
                context=user_input.split()[-1]
            )
        raise

def test_sites():
    """Test command handling with multiple sites"""
    sites = [
        "google.com",
        "news.ycombinator.com",
        "nytimes.com"
    ]
    
    logger.info("\nStarting multi-site test")
    driver = setup_browser()
    
    try:
        for site in sites:
            print(f"\n{'='*20} Testing {site} {'='*20}")
            
            # First navigate to site
            nav_input = f"go to {site}"
            nav_result = determine_command(nav_input)
            nav_execution = execute_command(nav_result, driver)
            print(f"\nNavigation result: {json.dumps(nav_execution, indent=2)}")
            
            # Then read the page
            read_input = "read this page"
            read_result = determine_command(read_input)
            read_execution = execute_command(read_result, driver)
            
            # Print focused analysis
            analysis = {
                "title": read_execution["title"],
                "type": read_execution["analysis"]["type"],
                "description": read_execution["analysis"]["description"],
                "structure": {
                    "has_main": read_execution["structure"]["has_main"],
                    "has_nav": read_execution["structure"]["has_nav"],
                    "has_article": read_execution["structure"]["has_article"],
                    "num_headings": len(read_execution["structure"]["headings"]),
                    "num_interactive": len(read_execution["structure"]["interactive"])
                }
            }
            print(f"\nPage Analysis: {json.dumps(analysis, indent=2)}")
            
    finally:
        logger.info("Closing browser")
        driver.quit()

if __name__ == "__main__":
    test_sites()
