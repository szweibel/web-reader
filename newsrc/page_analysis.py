"""Page analysis functionality for extracting structured content using LangGraph nodes"""

from typing import Dict, Any, List, Tuple, TypedDict
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from langchain.schema import HumanMessage
from langgraph.graph import StateGraph
from langchain.schema.runnable import RunnableLambda

from .config import llm
from .logging_config import logger

logger = logger.getChild(__name__)

class PageContent(TypedDict):
    """Content elements for natural language interaction"""
    headlines: List[str]  # News headlines or main content titles
    sections: List[Dict[str, str]]  # Content sections with text
    navigation: List[str]  # Navigation options
    main_content: str  # Primary content text

class PageState(TypedDict):
    """Current state of page analysis"""
    url: str
    title: str 
    content: PageContent
    suggested_actions: List[str]

class GraphState(TypedDict):
    state: PageState
    driver: webdriver.Chrome

def extract_content(state: GraphState) -> GraphState:
    """Extract readable content from page"""
    logger.info(f"Extracting content from: {state['state']['url']}")
    driver = state['driver']
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Find main content areas
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    
    # Extract headlines using semantic analysis
    headlines = []
    
    # Look for elements that semantically represent headlines
    headline_candidates = []
    
    # Find elements that match headline patterns
    for element in soup.find_all(['a', 'div', 'span', 'p', 'h1', 'h2', 'h3']):
        # Check if element has headline characteristics
        is_headline = False
        text = element.get_text(strip=True)
        
        if text and len(text) > 20:  # Meaningful content length
            # Check semantic indicators
            if (
                # Semantic HTML
                element.name in ['h1', 'h2', 'h3'] or
                # ARIA roles
                element.get('role') in ['heading', 'article'] or
                # Classes/IDs suggesting headlines
                any(c in str(element.get('class', [])).lower() for c in ['title', 'headline', 'heading']) or
                # Parent element suggests news/article context
                any(p.get('role') in ['article', 'main'] for p in element.parents) or
                # Link with substantial text (common for news headlines)
                (element.name == 'a' and len(text) > 30 and element.find_parent(['article', 'main']))
            ):
                is_headline = True
        
        if is_headline:
            headline_candidates.append(element)
    
    # Process candidates to extract headlines
    for candidate in headline_candidates:
        text = candidate.get_text(strip=True)
        if text and len(text) > 20:  # Filter out short text that's unlikely to be headlines
            # Remove duplicates while preserving order
            if text not in headlines:
                headlines.append(text)
            
    # Find content sections
    sections = []
    for section in soup.find_all(['article', 'section', 'div']):
        if len(section.get_text(strip=True)) > 100:  # Meaningful content
            sections.append({
                "title": section.find(['h1', 'h2', 'h3', 'h4'])
                    .get_text(strip=True) if section.find(['h1', 'h2', 'h3', 'h4']) 
                    else "",
                "text": section.get_text(strip=True)
            })
    
    # Get navigation options
    navigation = [
        link.get_text(strip=True) 
        for link in soup.find_all('a') 
        if link.get_text(strip=True)
    ]
    
    state['state']['content'] = {
        "headlines": headlines[:10],  # Most relevant headlines
        "sections": sections[:5],     # Main content sections
        "navigation": navigation[:10], # Key navigation options
        "main_content": main.get_text(strip=True) if main else ""
    }
    
    return state

def analyze_content(state: GraphState) -> GraphState:
    """Analyze content and suggest natural language actions"""
    logger.info("Analyzing page content for natural interaction")
    content = state['state']['content']
    
    prompt = HumanMessage(content=f"""Analyze this web page content for a screen reader user:
URL: {state['state']['url']}
Title: {state['state']['title']}
Content: {json.dumps(content, indent=2)}

Return a JSON response with:
{{
    "page_description": "1-2 sentence overview of the page",
    "suggested_actions": [
        "natural language suggestions like 'Read the first headline'",
        "or 'Check the main article'"
    ],
    "reading_order": [
        "ordered list of what to read first"
    ]
}}""")
    
    response = llm.invoke([prompt])
    state['state']['analysis'] = json.loads(response.content if hasattr(response, 'content') else str(response))
    return state

def analyze_page(driver: webdriver.Chrome) -> Dict[str, Any]:
    """Coordinate page analysis workflow using LangGraph nodes"""
    logger.info(f"Starting content analysis of: {driver.current_url}")
    
    # Initialize state
    initial_state: GraphState = {
        "state": {
            "url": driver.current_url,
            "title": driver.title,
            "content": {},
            "suggested_actions": []
        },
        "driver": driver
    }
    
    # Build graph with state schema
    workflow = StateGraph(state_schema=GraphState)
    
    # Add nodes using RunnableLambda
    workflow.add_node("extract", RunnableLambda(extract_content))
    workflow.add_node("analyze", RunnableLambda(analyze_content))
    
    # Define edges
    workflow.add_edge("extract", "analyze")
    
    # Set entry and exit points
    workflow.set_entry_point("extract")
    workflow.set_finish_point("analyze")
    
    # Execute graph
    app = workflow.compile()
    logger.info("Executing content analysis workflow")
    final_state = app.invoke(initial_state)
    
    return final_state["state"]
