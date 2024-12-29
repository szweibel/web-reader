# Par Scrape Analysis: Lessons for Web Reader

## Overview

While par_scrape is a data extraction tool and our web reader is a natural language screen reader, there are some valuable patterns we can learn from their implementation while staying true to our core mission of accessibility and conversation-based web navigation.

## Key Differences

### Our Web Reader
- **Purpose**: Natural language screen reader for accessibility
- **Model**: Local LLM (Ollama/llama3.2) for privacy and speed
- **Focus**: Conversation-based web navigation and understanding
- **Output**: Natural language responses and interactions
- **Architecture**: LangGraph-based workflow with rich state management

### Par Scrape
- **Purpose**: Web scraping and data extraction
- **Model**: Cloud APIs (OpenAI, Anthropic, etc.)
- **Focus**: Data collection and formatting
- **Output**: Structured data (JSON, CSV, Excel)
- **Architecture**: Command-line tool with format conversion

## Valuable Patterns to Adopt

### 1. Enhanced Page Analysis
```python
def analyze_page_structure(driver) -> dict:
    """
    Enhanced page analysis with structured JSON output from local LLM
    
    Features:
    - Semantic structure detection
    - Content type classification
    - Accessibility evaluation
    - Navigation suggestions
    """
    # Get page content
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Extract key elements and metadata
    title = driver.title
    main_content = soup.find("main") or soup.find(attrs={"role": "main"})
    navigation = soup.find("nav") or soup.find(attrs={"role": "navigation"})
    landmarks = soup.find_all(attrs={"role": True})
    
    # Prepare context for LLM
    context = {
        "title": title,
        "url": driver.current_url,
        "landmarks": [{"role": l["role"], "text": l.get_text()[:100]} for l in landmarks],
        "main_content_preview": main_content.get_text()[:500] if main_content else "",
        "navigation_items": [l.get_text() for l in navigation.find_all("a")] if navigation else []
    }
    
    # LLM prompt for structured analysis
    prompt = f"""Analyze this webpage structure and content:

Page Context:
{json.dumps(context, indent=2)}

Respond with a JSON object containing:
1. page_type: Primary type (article, news, search, form, etc.)
2. semantic_structure: Key structural elements found
3. accessibility_score: 0-100 rating with explanation
4. suggested_actions: List of relevant user actions
5. content_summary: Brief natural language summary

Example response:
{{
    "page_type": "article",
    "semantic_structure": {{
        "has_main": true,
        "has_nav": true,
        "has_landmarks": ["banner", "main", "navigation"],
        "content_sections": ["header", "article", "comments"]
    }},
    "accessibility_score": 85,
    "accessibility_notes": "Good landmark structure, but some images lack alt text",
    "suggested_actions": [
        "read article content",
        "navigate to comments section",
        "check related articles"
    ],
    "content_summary": "Long-form article about AI technology with reader comments"
}}"""

    # Get structured analysis from local LLM
    try:
        response = llm.invoke(prompt)
        analysis = json.loads(response)
        
        # Add dynamic content detection
        analysis["has_dynamic_content"] = bool(
            soup.find_all("script", src=True) or
            soup.find_all(["[x-data]", "[v-if]", "react-root"])
        )
        
        return analysis
        
    except Exception as e:
        logger.error(f"Page analysis failed: {str(e)}")
        return {
            "page_type": "unknown",
            "error": str(e)
        }
```

### 2. Structured Content Extraction
```python
def extract_page_content(driver, analysis: dict) -> dict:
    """
    Enhanced content extraction with structured output
    
    Features:
    - Content type-specific extraction
    - Semantic relationship mapping
    - Accessibility metadata
    """
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Base structure
    content = {
        "type": analysis["page_type"],
        "metadata": {
            "title": driver.title,
            "url": driver.current_url,
            "timestamp": datetime.now().isoformat()
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
    
    # Extract main content based on page type
    if analysis["page_type"] == "article":
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
    
    elif analysis["page_type"] == "news":
        # Extract headlines and articles
        content["content"]["articles"] = []
        for article in soup.find_all(["article", class_=lambda x: x and "article" in str(x)]):
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
```

### 3. Dynamic Content Handling
```python
class WaitStrategy:
    """Enhanced waiting for dynamic content"""
    @staticmethod
    async def wait_for_content(driver, strategy: str, target: str = None):
        """
        Wait for content using specified strategy
        
        Strategies:
        - idle: Wait for network idle
        - selector: Wait for specific element
        - text: Wait for text to appear
        - pause: Manual confirmation
        """
        try:
            if strategy == "idle":
                await driver.wait_for_load_state("networkidle")
            elif strategy == "selector" and target:
                await driver.wait_for_selector(target)
            elif strategy == "text" and target:
                await driver.wait_for_text(target)
            
            # Additional check for accessibility elements
            await driver.wait_for_selector('[role="main"], main, [role="article"], article')
            
        except Exception as e:
            logger.error(f"Wait strategy {strategy} failed: {str(e)}")
            # Fallback to basic load check
            await driver.wait_for_load_state("domcontentloaded")
```

### 4. Natural Language Enhancement
```python
def generate_page_description(analysis: dict, content: dict) -> str:
    """
    Generate natural language description of page content
    using structured analysis results
    """
    description = []
    
    # Page type and overview
    description.append(f"This appears to be a {analysis['page_type']} page.")
    if analysis['content_summary']:
        description.append(analysis['content_summary'])
        
    # Accessibility information
    description.append(f"\nAccessibility Overview:")
    description.append(f"- Accessibility score: {analysis['accessibility_score']}/100")
    description.append(f"- {analysis['accessibility_notes']}")
    
    # Navigation options
    if analysis['suggested_actions']:
        description.append("\nYou can:")
        for action in analysis['suggested_actions']:
            description.append(f"- {action}")
            
    # Content structure
    if content['accessibility']['landmarks']:
        description.append("\nThe page has these main areas:")
        for landmark in content['accessibility']['landmarks']:
            description.append(f"- {landmark['role']}: {landmark['label'] or landmark['text']}")
            
    # Interactive elements
    if content['content']['interactive_elements']:
        description.append("\nInteractive elements include:")
        for element in content['content']['interactive_elements'][:5]:  # Top 5 for brevity
            description.append(f"- {element['text'] or element['aria_label']}")
            
    return "\n".join(description)
```

## Integration Strategy

1. Enhanced Analysis
- Use structured JSON for page analysis
- Implement content type detection
- Add accessibility scoring
- Track semantic relationships

2. Natural Language Generation
- Convert structured data to conversational responses
- Prioritize accessibility information
- Provide context-aware navigation suggestions
- Maintain natural dialogue flow

3. Improved Interaction
- Better dynamic content handling
- Enhanced error recovery
- Robust element interaction
- Keyboard navigation support

## Implementation Plan

1. Phase 1: Enhanced Analysis
- Implement structured page analysis
- Add content type-specific extraction
- Improve accessibility metadata collection
- Add semantic relationship mapping

2. Phase 2: Natural Language
- Enhance conversational responses
- Add context-aware suggestions
- Improve accessibility reporting
- Implement structured data conversion

3. Phase 3: Interaction
- Add robust element handling
- Implement dynamic content detection
- Enhance keyboard navigation
- Improve error recovery

## Conclusion

While par_scrape is focused on data extraction, we can learn from their structured JSON approach to enhance our accessibility-focused screen reader. By combining their systematic page analysis with our natural language interface, we can provide better understanding and navigation while maintaining our core mission.

Key Takeaways:
- Use structured JSON for better page understanding
- Keep natural language as our primary interface
- Enhance accessibility analysis and reporting
- Maintain local LLM processing for privacy
- Focus on user understanding and navigation
