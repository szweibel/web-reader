"""Simple LLM invocation test"""
from langchain.schema import HumanMessage
from config import llm

def test_llm():
    """Test basic LLM functionality"""
    # First test simple prompt
    simple_prompt = HumanMessage(content="""Here is a simple user request: "go to google.com"

Return a JSON response in this exact format:
{
    "action": "navigate",
    "confidence": 0.95,
    "context": "google.com"
}""")

    print("\nTesting simple prompt:")
    print("Sending prompt to LLM:", simple_prompt.content)
    response = llm.invoke([simple_prompt])
    print("\nRaw LLM response:", response)
    print("\nResponse content:", response.content)

    # Now test complex prompt
    complex_prompt = HumanMessage(content="""Analyze this user message and determine the next action: "go to google.com"
    
    Available actions and their use cases:
    - navigate: Go to website/URL (e.g., "go to", "open", "visit")
    - read: Read page content (e.g., "what does it say", "where am I")
    - click: Click elements (e.g., "click", "press", "select")
    - check: Check element properties (e.g., "is this clickable", "is that a link")
    - list_headings: Show headings (e.g., "show headings", "what are the headings")
    - list_headlines: Show news headlines (e.g., "read headlines", "list headlines", "show news")
    - goto_headline: Go to a specific headline (e.g., "go to headline 1", "read article 3")
    - find: Search text (e.g., "find", "search", "locate")
    - next: Next element (e.g., "next", "forward")
    - prev: Previous element (e.g., "previous", "back") 
    - goto: Go to section (e.g., "go to main", "jump to nav")
    - list_landmarks: Show landmarks (e.g., "list landmarks", "show sections")
    - read_section: Read current section (e.g., "read this part", "read current section")

    IMPORTANT: For "read headlines" command, use list_headlines action, not read action.

    Return JSON with:
    - action: One of the exact action names listed above
    - confidence: How confident (0-1)
    - context: Any extracted context needed (e.g., URL, text to click)
    - next_action: Optional, if there's a follow-up action in the command
    - next_context: Optional, context for the follow-up action
    
    Example for single action: {"action": "navigate", "confidence": 0.95, "context": "google.com"}
    Example for compound action: {"action": "navigate", "confidence": 0.95, "context": "nytimes.com", "next_action": "list_headlines", "next_context": ""}""")

    print("\nTesting complex prompt:")
    print("Sending prompt to LLM:", complex_prompt.content)
    response = llm.invoke([complex_prompt])
    print("\nRaw LLM response:", response)
    print("\nResponse content:", response.content)

if __name__ == "__main__":
    test_llm()