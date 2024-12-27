"""Configuration settings and constants for the screen reader application"""

from langchain_ollama import ChatOllama
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
