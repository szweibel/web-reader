# LangGraph API Guide for LLMs

This guide explains the LangGraph API in a format optimized for LLM understanding and reference. Each section includes context, examples, and best practices.

## Core Concepts

### State Management

The foundation of LangGraph is typed state management using TypedDict:

```python
from typing import List, Annotated, TypedDict
from langgraph.graph.message import add_messages

class State(TypedDict):
    """
    State container for graph execution
    
    Key Concepts:
    - Use TypedDict for type safety
    - Annotated fields get special handling
    - Only include necessary state
    """
    # Messages field with automatic update handling
    messages: Annotated[list, add_messages]
    
    # Core state fields
    current_node: str  # Current position in graph
    input: str        # User/system input
    output: dict      # Node processing results
    
    # Optional tracking fields
    history: list     # Execution history
    errors: list      # Error tracking
```

Best Practices:
1. Keep state minimal and focused
2. Use type hints consistently
3. Document field purposes
4. Consider state persistence needs

### Graph Construction

Graphs are built using StateGraph with nodes and edges:

```python
from langgraph.graph import StateGraph, END

def build_workflow() -> StateGraph:
    """
    Construct processing workflow
    
    Key Concepts:
    - StateGraph enforces type safety
    - Nodes represent processing steps
    - Edges define execution flow
    - Conditional edges enable dynamic routing
    """
    # Initialize with state type
    workflow = StateGraph(State)
    
    # Add processing nodes
    workflow.add_node("process_input", process_input_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("generate_response", generate_response_node)
    
    # Add basic edges
    workflow.add_edge("process_input", "analyze")
    workflow.add_edge("analyze", "generate_response")
    
    # Add conditional edge
    workflow.add_conditional_edges(
        "generate_response",
        lambda x: "analyze" if needs_refinement(x) else END,
        ["analyze", END]
    )
    
    return workflow.compile()
```

Best Practices:
1. Use meaningful node names
2. Keep node functions focused
3. Consider error paths
4. Document routing logic

### Node Functions

Nodes are functions that process state and return updates:

```python
async def process_node(state: State) -> dict:
    """
    Process state and return updates
    
    Key Concepts:
    - Async for non-blocking operations
    - Return only changed fields
    - Handle errors gracefully
    - Document state requirements
    
    Args:
        state: Current graph state
        
    Returns:
        dict: Updated state fields
    """
    try:
        # Extract needed state
        current_data = state.get("input")
        if not current_data:
            return {"error": "Missing input data"}
            
        # Process data
        result = await process_data(current_data)
        
        # Return updates
        return {
            "output": result,
            "history": state.get("history", []) + ["processed_input"]
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "history": state.get("history", []) + ["error"]
        }
```

Best Practices:
1. Use type hints
2. Document requirements
3. Handle errors explicitly
4. Return minimal updates

## Advanced Patterns

### 1. State Routing

Control flow based on state conditions:

```python
def route_state(state: State) -> str:
    """
    Route to next node based on state
    
    Key Concepts:
    - Check state conditions
    - Return next node name
    - Handle edge cases
    - Document routing logic
    """
    # Check for errors
    if state.get("error"):
        return "error_handler"
        
    # Check completion
    if state.get("output", {}).get("complete"):
        return END
        
    # Check refinement needs
    if needs_refinement(state):
        return "refine"
        
    # Default path
    return "next_step"
```

### 2. Parallel Processing

Handle multiple operations efficiently:

```python
async def parallel_node(state: State) -> dict:
    """
    Process multiple operations in parallel
    
    Key Concepts:
    - Use asyncio.gather
    - Handle partial failures
    - Combine results efficiently
    """
    # Setup operations
    operations = [
        process_a(state),
        process_b(state),
        process_c(state)
    ]
    
    # Execute in parallel
    results = await asyncio.gather(*operations, return_exceptions=True)
    
    # Combine results
    return {
        "output": combine_results(results),
        "errors": [str(r) for r in results if isinstance(r, Exception)]
    }
```

### 3. Error Recovery

Handle and recover from errors:

```python
async def error_handler(state: State) -> dict:
    """
    Handle and recover from errors
    
    Key Concepts:
    - Analyze error context
    - Attempt recovery
    - Track recovery attempts
    - Provide feedback
    """
    error = state.get("error")
    attempts = state.get("recovery_attempts", 0)
    
    if attempts >= 3:
        return {"status": "failed", "next": END}
        
    recovery_result = await attempt_recovery(error)
    
    return {
        "error": None if recovery_result else error,
        "recovery_attempts": attempts + 1,
        "history": state.get("history", []) + [f"recovery_attempt_{attempts}"]
    }
```

## Best Practices Summary

1. State Management
   - Use TypedDict consistently
   - Keep state minimal
   - Document field purposes
   - Consider persistence

2. Graph Construction
   - Clear node naming
   - Focused node functions
   - Error handling paths
   - Documented routing

3. Node Implementation
   - Type hints
   - Error handling
   - Minimal updates
   - Clear documentation

4. Performance
   - Parallel when possible
   - Efficient state updates
   - Resource cleanup
   - Monitoring hooks

## Common Patterns

### 1. Input Processing
```python
async def process_input(state: State) -> dict:
    """Standard input processing pattern"""
    input_data = state.get("input")
    processed = await validate_and_clean(input_data)
    return {"processed_input": processed}
```

### 2. Analysis
```python
async def analyze(state: State) -> dict:
    """Standard analysis pattern"""
    data = state.get("processed_input")
    analysis = await analyze_data(data)
    return {"analysis": analysis}
```

### 3. Response Generation
```python
async def generate_response(state: State) -> dict:
    """Standard response generation pattern"""
    analysis = state.get("analysis")
    response = await generate(analysis)
    return {
        "response": response,
        "complete": True
    }
```

## Usage in Web Reader Context

Our web reader uses these patterns for:

1. Command Processing
```python
async def process_command(state: State) -> dict:
    """Process natural language commands"""
    command = state.get("input")
    action = await determine_action(command)
    return {"action": action}
```

2. Web Interaction
```python
async def interact_with_page(state: State) -> dict:
    """Handle web page interaction"""
    action = state.get("action")
    result = await execute_action(action)
    return {"result": result}
```

3. Response Generation
```python
async def generate_feedback(state: State) -> dict:
    """Generate natural language feedback"""
    result = state.get("result")
    feedback = await create_feedback(result)
    return {"messages": [{"role": "assistant", "content": feedback}]}
```

This documentation is designed to be easily understood and referenced by LLMs while providing comprehensive coverage of LangGraph API usage patterns.
