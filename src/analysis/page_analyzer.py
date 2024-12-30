"""LLM-driven page analysis and interpretation"""

import json
from typing import Dict, Any
from dataclasses import asdict
from bs4 import BeautifulSoup
from langchain.schema.runnable import RunnableConfig

from ..utils.logging import logger
from ..config import llm, LLMPageAnalysis
from ..state import PageContext, State

def analyze_page_structure(state: State) -> Dict[str, Any]:
    """Analyze current page structure and return rich analysis"""
    try:
        # Get page source and create soup
        driver = state["driver"]
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Basic page info
        title = driver.title
        url = driver.current_url
        
        # Extract key elements
        main_content = soup.find("main") or soup.find(attrs={"role": "main"})
        navigation = soup.find("nav") or soup.find(attrs={"role": "navigation"})
        article = soup.find("article")
        landmarks = soup.find_all(attrs={"role": True})
        
        # Check for dynamic content indicators
        has_dynamic = bool(
            soup.find_all("script", src=True) or
            soup.find_all(["[x-data]", "[v-if]", "react-root"])
        )
        
        # Extract semantic structure
        semantic_structure = {
            "has_main": bool(main_content),
            "has_nav": bool(navigation),
            "has_article": bool(article),
            "has_landmarks": [{"role": l["role"], "text": l.get_text()[:100]} for l in landmarks],
            "content_sections": []
        }
        
        # Find main content sections
        content_sections = []
        if main_content:
            for section in main_content.find_all(["section", "div"], class_=lambda x: x and "section" in x):
                content_sections.append({
                    "title": section.find(["h1", "h2", "h3"]).get_text() if section.find(["h1", "h2", "h3"]) else "",
                    "text": section.get_text()[:200],
                    "type": section.get("class", [""])[0]
                })
        semantic_structure["content_sections"] = content_sections

        # Prepare prompt for LLM analysis
        prompt = f"""Analyze this webpage structure:
        
        Page Title: {title}
        URL: {url}
        Semantic Structure: {semantic_structure}
        
        Return a JSON object with:
        1. type: Primary page type (article|news|search|form|etc)
        2. has_main: Whether page has main content area
        3. has_nav: Whether page has navigation
        4. has_article: Whether page contains article content
        5. has_headlines: Whether page contains news headlines
        6. has_forms: Whether page contains forms
        7. reasoning: Brief explanation of classification
        """

        # Get LLM analysis
        config = RunnableConfig(max_retries=2)
        response = llm.invoke(prompt, config=config)
        analysis = LLMPageAnalysis.parse_raw(response.content)
        
        # Create page context
        page_context = PageContext(
            type=analysis.type,
            has_main=analysis.has_main,
            has_nav=analysis.has_nav, 
            has_article=analysis.has_article,
            has_headlines=analysis.has_headlines,
            has_forms=analysis.has_forms,
            dynamic_content=has_dynamic,
            scroll_position=0,
            viewport_height=driver.execute_script("return window.innerHeight"),
            total_height=driver.execute_script("return document.documentElement.scrollHeight")
        )

        # Return complete analysis
        return {
            "page_context": page_context,
            "semantic_structure": semantic_structure,
            "raw_analysis": analysis.model_dump(),
            "next": "plan"  # Direct integration with workflow
        }

    except Exception as e:
        logger.error(f"Error analyzing page structure: {str(e)}")
        return {
            "errors": [str(e)],
            "next": "error_recovery"
        }

def get_page_landmarks(state: State) -> list:
    """Get ARIA landmarks from the page"""
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        landmarks = []
        
        for element in soup.find_all(attrs={"role": True}):
            landmarks.append({
                "role": element["role"],
                "text": element.get_text()[:100].strip(),
                "label": element.get("aria-label", "")
            })
            
        return landmarks
    except Exception as e:
        logger.error(f"Error getting landmarks: {str(e)}")
        return []

def get_page_headings(state: State) -> list:
    """Get heading structure of the page"""
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        headings = []
        
        for level in range(1, 7):
            for heading in soup.find_all(f"h{level}"):
                headings.append({
                    "level": level,
                    "text": heading.get_text().strip(),
                    "id": heading.get("id", "")
                })
                
        return headings
    except Exception as e:
        logger.error(f"Error getting headings: {str(e)}")
        return []

def get_interactive_elements(state: State) -> list:
    """Get interactive elements from the page"""
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        elements = []
        
        for tag in ["button", "a", "input", "select"]:
            for element in soup.find_all(tag):
                elements.append({
                    "type": tag,
                    "text": element.get_text().strip() or element.get("placeholder", ""),
                    "label": element.get("aria-label", ""),
                    "role": element.get("role", tag)
                })
                
        return elements
    except Exception as e:
        logger.error(f"Error getting interactive elements: {str(e)}")
        return []

def _safe_find(soup: BeautifulSoup, selector: str) -> Any:
    """Safely find an element in BeautifulSoup"""
    try:
        return soup.select_one(selector)
    except:
        return None
