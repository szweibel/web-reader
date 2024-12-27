# Web Reader: A Guide for LLMs

This document helps you understand the Web Reader application's architecture and how to make decisions about actions and workflows.

## Core Concept

You are part of a screen reader that helps users navigate web content through natural language. Your role is to:
1. Understand user commands
2. Analyze page content and structure
3. Choose appropriate actions
4. Provide clear feedback

## Langgraph Patterns

The application follows key langgraph patterns for robust and maintainable workflows:

### 1. Plan-and-Execute Pattern
```python
# Workflow follows determine -> execute -> reflect pattern
determine_next_action -> execute_action -> reflect_on_execution
```

Key aspects:
- Actions have clear success/failure indicators
- State updates are atomic and explicit
- Validation through structured types
- Error handling with recovery paths

### 2. Reflection Pattern
```python
# Reflection triggered by multiple attempts
if state["attempts"] > 1:
    return {"next": "reflect"}
```

Benefits:
- Self-correcting behavior
- Learning from failures
- Strategy revision
- Better error recovery

### 3. Action Results Pattern
```python
@dataclass
class ActionResult:
    output: Any  # Structured output type
    state_updates: Dict[str, Any]  # Explicit state changes
    messages: List[Dict[str, str]]  # User feedback
    next: str  # Next node
    error: Optional[str]  # Error context
```

Best practices:
- Use structured outputs
- Make state updates explicit
- Provide rich error context
- Enable validation

## Graph Architecture

The application uses a directed graph with reflection capabilities:

```
[determine_next] ──────▶ [execute] ──────▶ [reflect] ──────▶ [END]
       ▲                    │                  │
       │                    │                  │
       └────────────────────┴──────────────────┘
```

### Nodes

1. **determine_next**
   - Entry point for commands
   - Uses LLM for action selection
   - Validates confidence
   - Tracks attempts

2. **execute**
   - Runs selected action
   - Returns structured output
   - Updates state explicitly
   - Handles errors gracefully

3. **reflect**
   - Evaluates execution success
   - Suggests strategy changes
   - Tracks execution history
   - Triggers retries if needed

### State Management

The state object uses TypedDict for type safety:
```python
class State(TypedDict):
    # Core state
    messages: Annotated[list, add_messages]
    driver: webdriver.Chrome
    
    # Browser state
    current_element_index: int
    focusable_elements: list
    last_found_element: WebElement | None
    
    # Action state
    current_action: str | None
    action_context: str
    attempts: int
    
    # Execution tracking
    execution_history: list[dict]
    error: str | None
```

## Action Implementation

Actions follow a consistent pattern:

```python
@dataclass
class ActionOutput:
    """Structured output for actions"""
    output: T  # Generic type parameter
    error: str | None = None

@register_action("action_name")
def some_action(state: State) -> ActionResult:
    """Action implementation"""
    try:
        # Action logic here
        return create_result(
            output=output,
            state_updates={...},
            messages=[...],
            next=next_node
        )
    except Exception as e:
        return create_result(error=str(e))
```

Best practices:
1. Use dataclasses for structured outputs
2. Return explicit state updates
3. Provide clear error context
4. Enable validation and testing

## Decision Making

### 1. Action Selection
- Track attempt count
- Use confidence thresholds
- Consider page context
- Enable reflection after failures

### 2. Error Handling
- Provide structured error info
- Enable recovery strategies
- Track recovery attempts
- Use reflection for retries

### 3. State Updates
- Make changes explicit
- Use atomic updates
- Validate state changes
- Track execution history

## Common Patterns

1. **Multiple Attempts**
   ```python
   if state["attempts"] > 1:
       # Try alternative strategy
       return reflect_on_execution(state)
   ```

2. **State Updates**
   ```python
   return create_result(
       output=output,
       state_updates={
           "key": "value",
           "attempts": state["attempts"] + 1
       }
   )
   ```

3. **Error Recovery**
   ```python
   if error:
       return create_result(
           error=str(error),
           next="error_recovery"
       )
   ```

Remember:
- Follow langgraph patterns
- Use structured types
- Make state changes explicit
- Enable validation and testing
- Handle errors gracefully
- Use reflection for improvement
