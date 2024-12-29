"""Enhanced content reading actions with dynamic content handling"""

import time
from typing import Dict, Any, TypedDict, Union, List, Optional
from dataclasses import dataclass
from langgraph.graph import END
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..state import State, PageContext, ElementContext, ActionPrediction, Task, TaskStatus, create_task_status
from ..utils.logging import logger
from ..utils.errors import create_error_response
from . import register_action

@dataclass
class ReadPageOutput:
    """Enhanced output for read_page action"""
    content: str
    sections: List[Dict[str, str]]  # List of named sections
    summary: Optional[str]
    truncated: bool = False
    dynamic_content: bool = False

@dataclass
class HeadingOutput:
    """Enhanced output for list_headings action"""
    headings: List[Dict[str, Any]]  # Include structure and context
    level: str
    hierarchy: Dict[str, List[str]]  # Heading hierarchy

@dataclass
class HeadlineOutput:
    """Enhanced output for list_headlines action"""
    text: str
    url: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None
    category: Optional[str] = None

class ActionResult(TypedDict):
    """Action result container"""
    output: Union[ReadPageOutput, HeadingOutput, List[HeadlineOutput], None]
    state_updates: Dict[str, Any]
    messages: List[Dict[str, str]]
    next: str
    error: Optional[str]

def create_result(
    output: Any = None,
    state_updates: Dict[str, Any] = None,
    messages: List[str] = None,
    next_node: str = END,
    error: Optional[str] = None
) -> ActionResult:
    """Create action result"""
    return ActionResult(
        output=output,
        state_updates=state_updates or {},
        messages=[{"role": "assistant", "content": msg} for msg in (messages or [])],
        next=next_node,
        error=error
    )

class WaitStrategy:
    """Enhanced waiting for dynamic content"""
    @staticmethod
    def wait_for_content(driver, strategy: str, target: str = None):
        """
        Wait for content using specified strategy
        
        Strategies:
        - idle: Wait for network idle
        - selector: Wait for specific element
        - text: Wait for text to appear
        """
        try:
            if strategy == "idle":
                WebDriverWait(driver, 5).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            elif strategy == "selector" and target:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, target))
                )
            elif strategy == "text" and target:
                WebDriverWait(driver, 5).until(
                    EC.text_to_be_present_in_element((By.TAG_NAME, "body"), target)
                )
            
            # Additional check for accessibility elements
            WebDriverWait(driver, 3).until(
                lambda d: d.find_element(By.CSS_SELECTOR, '[role="main"], main, [role="article"], article')
            )
            
        except Exception as e:
            logger.error(f"Wait strategy {strategy} failed: {str(e)}")
            # Fallback to basic load check
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )

def handle_dynamic_content(state: State, soup: BeautifulSoup) -> BeautifulSoup:
    """Enhanced dynamic content handling"""
    if state.get("predictions", {}).get("needs_wait"):
        # First try waiting for network idle
        WaitStrategy.wait_for_content(state["driver"], "idle")
        
        # Then wait for main content based on page type
        if state["page_context"].type == "article":
            WaitStrategy.wait_for_content(state["driver"], "selector", "article, [role='article']")
        elif state["page_context"].type == "news":
            WaitStrategy.wait_for_content(state["driver"], "selector", ".article, .story, .post")
        
        # Update soup with new content
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
    
    return soup

def extract_page_content(driver, soup: BeautifulSoup, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced content extraction with structured output
    
    Features:
    - Content type-specific extraction
    - Semantic relationship mapping
    - Accessibility metadata
    """
    content = {
        "type": analysis["type"],
        "metadata": {
            "title": driver.title,
            "url": driver.current_url,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "accessibility": {
            "landmarks": [],
            "headings": [],
            "aria_labels": [],
            "tab_order": []
        },
        "content": {
            "main": None,
            "sections": [],
            "navigation": None,
            "interactive_elements": []
        }
    }
    
    # Extract landmarks
    for element in soup.find_all(attrs={"role": True}):
        content["accessibility"]["landmarks"].append({
            "role": element["role"],
            "label": element.get("aria-label", ""),
            "text": element.get_text()[:100]
        })
    
    # Extract headings with hierarchy
    headings = []
    current_section = None
    for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        for heading in soup.find_all(tag):
            heading_data = {
                "level": int(tag[1]),
                "text": heading.get_text(),
                "id": heading.get("id", ""),
                "parent": current_section
            }
            if tag == "h1":
                current_section = heading_data
            headings.append(heading_data)
    content["accessibility"]["headings"] = headings
    
    # Extract tab order
    focusable = soup.find_all(["a", "button", "input", "select", "textarea", "[tabindex]"])
    for i, element in enumerate(focusable):
        content["accessibility"]["tab_order"].append({
            "index": i + 1,
            "type": element.name,
            "text": element.get_text() or element.get("placeholder", ""),
            "aria_label": element.get("aria-label", "")
        })
    
    # Extract main content based on page type
    if analysis["type"] == "article":
        article = soup.find("article") or soup.find(attrs={"role": "article"})
        if article:
            content["content"]["main"] = {
                "title": article.find(["h1", "h2"]).get_text() if article.find(["h1", "h2"]) else "",
                "text": article.get_text(),
                "sections": []
            }
            # Break into sections
            for section in article.find_all(["section", "div"], class_=lambda x: x and "section" in x):
                content["content"]["sections"].append({
                    "title": section.find(["h1", "h2", "h3"]).get_text() if section.find(["h1", "h2", "h3"]) else "",
                    "text": section.get_text(),
                    "type": section.get("class", [""])[0]
                })
    
    elif analysis["type"] == "news":
        # Extract headlines and articles
        content["content"]["articles"] = []
        for article in soup.find_all(["article"], class_=lambda x: x and "article" in str(x)):
            content["content"]["articles"].append({
                "headline": article.find(["h1", "h2", "h3"]).get_text() if article.find(["h1", "h2", "h3"]) else "",
                "summary": article.get_text()[:200],
                "link": article.find("a")["href"] if article.find("a") else None
            })
    
    # Extract interactive elements
    for element in soup.find_all(["button", "a", "input", "select"]):
        content["content"]["interactive_elements"].append({
            "type": element.name,
            "text": element.get_text() or element.get("placeholder", ""),
            "aria_label": element.get("aria-label", ""),
            "is_visible": bool(element.get("style", "").find("display: none") == -1),
            "location": element.get("id", "") or element.get("class", [""])[0]
        })
    
    return content

def extract_section_content(section: BeautifulSoup) -> Dict[str, str]:
    """Extract content from a page section with enhanced metadata"""
    heading = section.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    return {
        "title": heading.get_text(strip=True) if heading else "",
        "content": section.get_text(separator="\n", strip=True),
        "type": section.name or section.get("role", "section"),
        "class": " ".join(section.get("class", [])),
        "aria_label": section.get("aria-label", ""),
        "id": section.get("id", ""),
        "has_interactive": bool(section.find_all(["button", "a", "input", "select"])),
        "subsections": [
            {
                "title": subsec.find(["h1", "h2", "h3", "h4", "h5", "h6"]).get_text(strip=True) if subsec.find(["h1", "h2", "h3", "h4", "h5", "h6"]) else "",
                "content": subsec.get_text(separator="\n", strip=True)
            }
            for subsec in section.find_all(["section", "div"], recursive=False)
            if "section" in str(subsec.get("class", []))
        ]
    }

def analyze_page_structure(driver, soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Enhanced page analysis with structured output
    
    Features:
    - Semantic structure detection
    - Content type classification
    - Accessibility evaluation
    - Navigation suggestions
    """
    # Extract key elements and metadata
    title = driver.title
    main_content = soup.find("main") or soup.find(attrs={"role": "main"})
    navigation = soup.find("nav") or soup.find(attrs={"role": "navigation"})
    landmarks = soup.find_all(attrs={"role": True})
    
    # Analyze semantic structure
    structure = {
        "main_content": bool(main_content),
        "navigation": bool(navigation),
        "sidebar": bool(soup.find("aside") or soup.find(attrs={"role": "complementary"})),
        "footer": bool(soup.find("footer") or soup.find(attrs={"role": "contentinfo"})),
        "header": bool(soup.find("header") or soup.find(attrs={"role": "banner"})),
        "forms": len(soup.find_all("form")),
        "interactive_elements": len(soup.find_all(["button", "input", "select", "textarea"])),
        "landmarks": [{"role": l["role"], "label": l.get("aria-label", ""), "text": l.get_text()[:100]} for l in landmarks],
        "has_dynamic_content": bool(
            soup.find_all("script", src=True) or
            soup.find_all(["[x-data]", "[v-if]", "react-root"])
        )
    }
    
    # Detect content type
    content_type = "unknown"
    if soup.find("article") or soup.find(attrs={"role": "article"}):
        content_type = "article"
    elif len(soup.find_all(["h1", "h2", "h3"], class_=lambda x: x and any(c in str(x).lower() for c in ["headline", "title"]))) > 3:
        content_type = "news"
    elif structure["forms"] > 0:
        content_type = "form"
    elif soup.find("table") or soup.find(attrs={"role": "grid"}):
        content_type = "data"
    
    # Evaluate accessibility
    accessibility_score = 0
    accessibility_notes = []
    
    # Check landmarks
    if structure["main_content"]:
        accessibility_score += 20
    else:
        accessibility_notes.append("Missing main content landmark")
        
    if structure["navigation"]:
        accessibility_score += 10
    
    # Check headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    if headings:
        accessibility_score += 20
        if not soup.find("h1"):
            accessibility_notes.append("Missing H1 heading")
    else:
        accessibility_notes.append("No headings found")
    
    # Check images
    images = soup.find_all("img")
    images_with_alt = [img for img in images if img.get("alt")]
    if images:
        alt_ratio = len(images_with_alt) / len(images)
        accessibility_score += int(alt_ratio * 20)
        if alt_ratio < 1:
            accessibility_notes.append(f"{len(images) - len(images_with_alt)} images missing alt text")
    
    # Check forms
    forms = soup.find_all("form")
    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        labels = form.find_all("label")
        if len(inputs) > len(labels):
            accessibility_notes.append("Some form fields missing labels")
            break
    
    # Check ARIA
    elements_with_aria = soup.find_all(lambda tag: any(attr for attr in tag.attrs if attr.startswith("aria-")))
    if elements_with_aria:
        accessibility_score += 10
    
    # Generate navigation suggestions based on content type and structure
    suggestions = []
    if content_type == "article":
        suggestions.extend([
            "read article content",
            "list headings for structure",
            "navigate to comments section"
        ])
    elif content_type == "news":
        suggestions.extend([
            "list headlines",
            "read top story",
            "find latest news"
        ])
    elif content_type == "form":
        suggestions.extend([
            "list form fields",
            "navigate to submit button",
            "check required fields"
        ])
    
    if structure["navigation"]:
        suggestions.append("explore navigation menu")
    if structure["landmarks"]:
        suggestions.append("list page landmarks")
    
    return {
        "type": content_type,
        "semantic_structure": structure,
        "accessibility": {
            "score": accessibility_score,
            "notes": accessibility_notes
        },
        "suggested_actions": suggestions,
        "title": title,
        "url": driver.current_url
    }

@register_action("read_page")
def read_page(state: State) -> ActionResult:
    """Enhanced page reading with structure analysis"""
    logger.debug("Entering read_page action")
    
    try:
        logger.debug("Getting page source")
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
        
        # Enhanced page analysis
        analysis = analyze_page_structure(state["driver"], soup)
        headlines = extract_headlines(soup) if analysis["type"] == "news" else None
        
        # Find main content area
        main_content = soup.find("main") or soup.find(attrs={"role": "main"}) or soup
        
        # Extract sections
        sections = []
        for section in main_content.find_all(["article", "section", "div"], class_=lambda x: x and any(c in str(x) for c in ["content", "article", "post"])):
            sections.append(extract_section_content(section))
        
        # Clean and extract text
        for tag in soup.find_all(["script", "style", "nav", "footer"]):
            tag.decompose()
            
        text = main_content.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)
        
        # Generate summary if content is long
        summary = None
        if len(content) > 1000:
            summary = content[:1000] + "...\n\n(Content truncated. Use 'read next section' to continue reading.)"
            
        output = ReadPageOutput(
            content=content[:1000] if len(content) > 1000 else content,
            sections=sections,
            summary=summary,
            truncated=len(content) > 1000,
            dynamic_content=bool(state.get("predictions", {}).get("needs_wait"))
        )
        
        # Update state with rich context
        state_updates = {
            "page_context": PageContext(
                type=analysis["type"],
                has_main=analysis["semantic_structure"]["main_content"],
                has_nav=analysis["semantic_structure"]["navigation"],
                has_article=bool(sections),
                has_headlines=bool(headlines),
                has_forms=bool(analysis["semantic_structure"]["forms"]),
                dynamic_content=analysis["semantic_structure"]["has_dynamic_content"],
                scroll_position=0,
                viewport_height=state["driver"].execute_script("return window.innerHeight"),
                total_height=state["driver"].execute_script("return document.documentElement.scrollHeight")
            )
        }
        
        # Format enhanced message with accessibility info and suggestions
        message_parts = []
        message_parts.append(f"Here's what I found on this {analysis['type']} page:\n")
        
        # Add accessibility information
        message_parts.append(f"Accessibility Score: {analysis['accessibility']['score']}/100")
        if analysis['accessibility']['notes']:
            message_parts.append("Accessibility Notes:")
            for note in analysis['accessibility']['notes']:
                message_parts.append(f"- {note}")
        message_parts.append("")  # Add spacing
        
        # Add content summary
        if summary:
            message_parts.append(summary)
            message_parts.append("")
        
        # Add section information
        if sections:
            message_parts.append(f"The page contains {len(sections)} main sections. Use 'read section [number]' to read a specific section.")
        
        # Add headline information
        if headlines:
            message_parts.append(f"\nI found {len(headlines)} headlines. Use 'list headlines' to see them.")
        
        # Add navigation suggestions
        if analysis['suggested_actions']:
            message_parts.append("\nSuggested actions:")
            for action in analysis['suggested_actions']:
                message_parts.append(f"- {action}")
            
        return create_result(
            output=output,
            state_updates=state_updates,
            messages=["\n".join(message_parts)]
        )
        
    except Exception as e:
        logger.error(f"Error reading page: {str(e)}")
        return create_result(error=f"An error occurred while reading the page: {str(e)}")

@register_action("list_headings")
def list_headings(state: State) -> ActionResult:
    """Enhanced heading listing with hierarchy analysis"""
    logger.debug("Entering list_headings action")
    
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
        
        headings = []
        hierarchy = {"h1": [], "h2": {}, "h3": {}, "h4": {}, "h5": {}, "h6": {}}
        current = {"h1": None, "h2": None, "h3": None, "h4": None, "h5": None, "h6": None}
        
        # Find all heading tags with context
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            for heading in soup.find_all(tag):
                text = heading.get_text().strip()
                if text:
                    # Get heading context
                    parent = heading.find_parent(["section", "article", "main", "div"])
                    context = {
                        "section": parent.name if parent else None,
                        "section_class": parent["class"] if parent and "class" in parent.attrs else None,
                        "id": heading.get("id"),
                        "classes": heading.get("class"),
                        "aria_label": heading.get("aria-label")
                    }
                    
                    # Add to flat list
                    headings.append({
                        "text": text,
                        "level": tag,
                        "context": context
                    })
                    
                    # Update hierarchy
                    if tag == "h1":
                        hierarchy["h1"].append(text)
                        current["h1"] = text
                        # Reset lower levels
                        for level in ["h2", "h3", "h4", "h5", "h6"]:
                            current[level] = None
                    else:
                        # Find parent heading
                        parent_level = f"h{int(tag[1])-1}"
                        if current[parent_level]:
                            if parent_level == "h1":
                                if not hierarchy["h2"].get(current["h1"]):
                                    hierarchy["h2"][current["h1"]] = []
                                hierarchy["h2"][current["h1"]].append(text)
                            else:
                                parent_dict = hierarchy[tag]
                                parent_key = current[parent_level]
                                if not parent_dict.get(parent_key):
                                    parent_dict[parent_key] = []
                                parent_dict[parent_key].append(text)
                            current[tag] = text
        
        if headings:
            # Format hierarchical display
            content = []
            for h1 in hierarchy["h1"]:
                content.append(f"# {h1}")
                if h1 in hierarchy["h2"]:
                    for h2 in hierarchy["h2"][h1]:
                        content.append(f"  ## {h2}")
                        if h2 in hierarchy["h3"]:
                            for h3 in hierarchy["h3"][h2]:
                                content.append(f"    ### {h3}")
                                
            output = HeadingOutput(
                headings=headings,
                level="page",
                hierarchy=hierarchy
            )
            
            return create_result(
                output=output,
                state_updates={
                    "page_context": PageContext(
                        **{**state["page_context"].__dict__,
                           "has_headlines": True}
                    )
                },
                messages=[f"Found these headings:\n\n" + "\n".join(content)]
            )
        
        return create_result(
            output=HeadingOutput([], "none", {}),
            error="No headings found on this page"
        )
        
    except Exception as e:
        logger.error(f"Error listing headings: {str(e)}")
        return create_result(error=f"An error occurred while listing headings: {str(e)}")

def extract_headlines(soup: BeautifulSoup) -> List[HeadlineOutput]:
    """Extract headlines with metadata"""
    headlines = []
    main_content = soup.find('main') or soup.find('div', {'role': 'main'}) or soup
    
    # Common navigation/utility words to filter out
    nav_words = {'menu', 'navigation', 'search', 'subscribe', 'sign in', 'log in', 'section'}
    
    for element in main_content.find_all(['h1', 'h2', 'h3', 'a']):
        # Get text and metadata
        text = element.get_text().strip()
        href = element.get('href', '')
        timestamp = element.find(class_=lambda x: x and any(t in str(x).lower() for t in ['time', 'date', 'published'])).get_text() if element.find(class_=lambda x: x and any(t in str(x).lower() for t in ['time', 'date', 'published'])) else None
        category = element.find(class_=lambda x: x and any(tag in str(x).lower() for tag in ['category', 'tag', 'topic'])).get_text() if element.find(class_=lambda x: x and any(tag in str(x).lower() for tag in ['category', 'tag', 'topic'])) else None
        
        # Clean up text
        text = ' '.join(text.split())
        if 'min read' in text:
            text = text.split('min read')[0].strip()
        
        # Skip if empty or too short
        if not text or len(text) < 20:
            continue
            
        # Skip navigation elements
        if any(word in text.lower() for word in nav_words):
            continue
        
        # Get full URL if relative
        if href and not href.startswith('http'):
            href = 'https://www.nytimes.com' + href if href.startswith('/') else href
        
        # Skip duplicate headlines
        if text not in [h.text for h in headlines]:
            headlines.append(HeadlineOutput(
                text=text,
                url=href,
                source=element.find(class_=lambda x: x and 'source' in str(x).lower()).get_text() if element.find(class_=lambda x: x and 'source' in str(x).lower()) else None,
                timestamp=timestamp.get_text() if timestamp else None,
                category=category.get_text() if category else None
            ))
            
        # Limit to reasonable number
        if len(headlines) >= 15:
            break
            
    return headlines

@register_action("list_headlines")
def list_headlines(state: State) -> ActionResult:
    """Enhanced headline listing with metadata"""
    logger.debug("Entering list_headlines action")
    
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
            
        # Get page context
        page_context = state.get("page_context")
        if not isinstance(page_context, PageContext):
            page_context = PageContext(**page_context)
            
        # Extract headlines
        headlines = extract_headlines(soup)
        
        if headlines:
            # Format numbered list with metadata
            content = []
            for i, h in enumerate(headlines):
                headline = f"{i+1}. {h.text}"
                if h.category:
                    headline += f" [{h.category}]"
                if h.timestamp:
                    headline += f" ({h.timestamp})"
                content.append(headline)
                
            content = "\n".join(content)
            content += "\n\nSay 'go to headline [number]' to read an article."
            
            return create_result(
                output=headlines,
                state_updates={
                    "headlines": headlines,
                    "page_context": PageContext(
                        **{**state["page_context"].__dict__,
                           "has_headlines": True}
                    )
                },
                messages=[f"Found these news headlines:\n\n{content}"]
            )
        
        return create_result(
            output=[],
            error="No news headlines found on this page"
        )
        
    except Exception as e:
        logger.error(f"Error listing headlines: {str(e)}")
        return create_result(error=f"An error occurred while listing headlines: {str(e)}")

@register_action("read_section")
def read_section(state: State) -> ActionResult:
    """Read the current or specified section of content"""
    logger.debug("Entering read_section action")
    
    try:
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        
        # Handle dynamic content if needed
        if state.get("predictions", {}).get("needs_wait"):
            soup = handle_dynamic_content(state, soup)
            
        # Find main content area
        main_content = soup.find("main") or soup.find(attrs={"role": "main"}) or soup
        
        # Extract sections
        sections = []
        for section in main_content.find_all(["article", "section", "div"], class_=lambda x: x and any(c in str(x) for c in ["content", "article", "post"])):
            sections.append(extract_section_content(section))
            
        if not sections:
            # If no explicit sections, treat main content as one section
            sections = [extract_section_content(main_content)]
            
        if sections:
            # Format content
            content = []
            for i, section in enumerate(sections):
                if section["title"]:
                    content.append(f"Section {i+1}: {section['title']}")
                content.append(section["content"])
                content.append("")  # Add spacing between sections
                
            return create_result(
                output=sections,
                messages=["\n".join(content)]
            )
            
        return create_result(
            output=[],
            error="No readable sections found on this page"
        )
        
    except Exception as e:
        logger.error(f"Error reading section: {str(e)}")
        return create_result(error=f"An error occurred while reading the section: {str(e)}")

@register_action("goto_headline")
def goto_headline(state: State) -> ActionResult:
    """Enhanced headline navigation with content preparation"""
    logger.debug("Entering goto_headline action")
    
    try:
        # Get headline number from context
        context = state.get("action_context", "")
        try:
            num = int(''.join(filter(str.isdigit, context))) - 1
        except ValueError:
            return create_result(error="Please specify a headline number")
            
        # Get stored headlines
        headlines = state.get("headlines", [])
        if not headlines:
            return create_result(error="No headlines available. Try listing headlines first")
            
        # Validate headline number
        if num < 0 or num >= len(headlines):
            return create_result(error=f"Invalid headline number. Please choose 1-{len(headlines)}")
            
        # Get URL for selected headline
        headline = headlines[num]
        if not headline.url:
            return create_result(error="Sorry, that headline doesn't have a link")
            
        # Navigate to the URL
        state["driver"].get(headline.url)
        
        # Wait for article content
        try:
            WebDriverWait(state["driver"], 3).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except Exception:
            logger.debug("No article tag found, continuing anyway")
            
        # Analyze new page context with enhanced analysis
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        analysis = analyze_page_structure(state["driver"], soup)
        
        return create_result(
            output=headline,
            state_updates={
                "current_element_index": -1,
                "focusable_elements": [],
                "last_found_element": None,
                "page_context": PageContext(
                    type=analysis["type"],
                    has_main=analysis["semantic_structure"]["main_content"],
                    has_nav=analysis["semantic_structure"]["navigation"],
                    has_article=True,
                    has_headlines=False,
                    has_forms=bool(analysis["semantic_structure"]["forms"]),
                    dynamic_content=analysis["semantic_structure"]["has_dynamic_content"],
                    scroll_position=0,
                    viewport_height=state["driver"].execute_script("return window.innerHeight"),
                    total_height=state["driver"].execute_script("return document.documentElement.scrollHeight")
                ),
                "predictions": ActionPrediction(
                    needs_scroll=True,
                    needs_click=False,
                    needs_wait=True,
                    potential_popups=True,
                    confidence=0.9,
                    reasoning="Article pages often have dynamic content and may need scrolling"
                )
            },
            messages=[
                f"Navigating to article: {headline.text}. The page is loading and being analyzed. You can use 'read content' to start reading the article."
            ]
        )
    except Exception as e:
        logger.error(f"Error in goto_headline: {str(e)}")
        return create_result(error=f"An error occurred while navigating to the headline: {str(e)}")
