"""Configuration settings for the web reader application"""

from langchain_ollama import ChatOllama

# Configure LLM for consistent JSON responses
llm = ChatOllama(
    model="llama3.2",
    format="json",
    temperature=0,
    prefix="""You are a command parser that converts natural language requests into structured commands.
    Your responses must be valid JSON in this exact format:
    {
        "action": "navigate" or "read",
        "confidence": number between 0 and 1,
        "context": "URL for navigate, or 'current page' for read"
    }
    Keep responses focused and structured."""
)
