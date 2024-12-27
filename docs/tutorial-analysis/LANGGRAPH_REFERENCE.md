# LangGraph Reference Guide

This guide incorporates the official LangGraph reference documentation (from https://langchain-ai.github.io/langgraph/reference/graphs/), adapted for our web reader context with practical examples.

## Graph Types

### StateGraph

The primary graph type for managing stateful workflows:

```python
from langgraph.graph import StateGraph, END

# Basic graph creation
graph = StateGraph(State)  # State is our TypedDict

# Adding nodes
graph.add_node("process", process_fn)
graph.add_node("analyze", analyze_fn)

# Adding edges
graph.add_edge("process", "analyze")
graph.add_edge("analyze", END)

# Compiling
workflow = graph.compile()
```

Key Features:
- Type-safe state management
- Explicit edge definitions
- Conditional routing
- State validation

### Graph

Base graph class for simpler workflows:

```python
from langgraph.graph import Graph

# Create basic graph
graph = Graph()

# Add nodes with functions
graph.add_node("start", start_fn)
graph.add_node("end", end_fn)

# Connect nodes
graph.add_edge("start", "end")
```

Use Cases:
- Simple linear workflows
- Stateless processing
- Quick prototypes

## Node Types

### 1. Function Nodes
```python
def process_node(state: State) -> dict:
    """Basic function node"""
    return {"result": process(state)}

# Add to graph
graph.add_node("process", process_node)
```

### 2. Runnable Nodes
```python
from langgraph.pregel import Runnable

class AnalyzeNode(Runnable):
    """Runnable node with lifecycle"""
    
    def __init__(self):
        self.initialized = False
    
    async def initialize(self):
        """Setup resources"""
        self.initialized = True
    
    async def invoke(self, state: State) -> dict:
        """Process state"""
        return {"analysis": analyze(state)}
    
    async def cleanup(self):
        """Cleanup resources"""
        self.initialized = False

# Add to graph
graph.add_node("analyze", AnalyzeNode())
```

### 3. Channel Nodes
```python
from langgraph.channels import Channel

class UpdateChannel(Channel):
    """Channel for state updates"""
    
    async def send(self, message: dict):
        """Send update"""
        await process_update(message)
    
    async def receive(self) -> dict:
        """Receive update"""
        return await get_update()

# Add to graph
graph.add_node("update", UpdateChannel())
```

## Edge Types

### 1. Direct Edges
```python
# Simple connection
graph.add_edge("node1", "node2")
```

### 2. Conditional Edges
```python
def route_state(state: State) -> str:
    """Route based on state"""
    if state.get("error"):
        return "error_handler"
    return "next_step"

# Add conditional routing
graph.add_conditional_edges(
    "process",
    route_state,
    ["error_handler", "next_step"]
)
```

### 3. Branch Edges
```python
def branch_condition(state: State) -> List[str]:
    """Return multiple next nodes"""
    branches = []
    if needs_analysis(state):
        branches.append("analyze")
    if needs_validation(state):
        branches.append("validate")
    return branches

# Add branching
graph.add_branch_edges(
    "start",
    branch_condition,
    ["analyze", "validate"]
)
```

## State Management

### 1. State Updates
```python
def update_state(state: State) -> dict:
    """Return only changed fields"""
    return {
        "field1": new_value1,
        "field2": new_value2
    }
```

### 2. State Validation
```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ValidatedState(TypedDict):
    """State with validation"""
    messages: Annotated[list, add_messages]
    count: Annotated[int, "Must be positive"]
    status: Annotated[str, ["pending", "complete"]]
```

## Web Reader Examples

### 1. Navigation Graph
```python
def build_navigation_graph() -> StateGraph:
    """Build web navigation workflow"""
    graph = StateGraph(State)
    
    # Add core nodes
    graph.add_node("analyze_page", analyze_page_node)
    graph.add_node("handle_dynamic", handle_dynamic_node)
    graph.add_node("interact", interaction_node)
    
    # Add conditional routing
    def route_navigation(state: State) -> str:
        if state.get("has_dynamic_content"):
            return "handle_dynamic"
        if state.get("needs_interaction"):
            return "interact"
        return END
    
    # Add edges
    graph.add_edge("analyze_page", route_navigation)
    graph.add_edge("handle_dynamic", "interact")
    graph.add_edge("interact", END)
    
    return graph.compile()
```

### 2. Content Processing Graph
```python
def build_content_graph() -> StateGraph:
    """Build content processing workflow"""
    graph = StateGraph(State)
    
    # Add processing nodes
    graph.add_node("extract_content", extract_content_node)
    graph.add_node("analyze_structure", analyze_structure_node)
    graph.add_node("generate_summary", generate_summary_node)
    
    # Add branching
    def branch_processing(state: State) -> List[str]:
        branches = ["analyze_structure"]
        if state.get("needs_summary"):
            branches.append("generate_summary")
        return branches
    
    # Add edges
    graph.add_edge("extract_content", branch_processing)
    graph.add_edges_from([
        ("analyze_structure", END),
        ("generate_summary", END)
    ])
    
    return graph.compile()
```

### 3. Interaction Graph
```python
def build_interaction_graph() -> StateGraph:
    """Build user interaction workflow"""
    graph = StateGraph(State)
    
    # Add interaction nodes
    graph.add_node("process_command", process_command_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("generate_feedback", generate_feedback_node)
    
    # Add error handling
    graph.add_node("handle_error", handle_error_node)
    
    # Add conditional routing
    def route_interaction(state: State) -> str:
        if state.get("error"):
            return "handle_error"
        if state.get("needs_feedback"):
            return "generate_feedback"
        return END
    
    # Add edges
    graph.add_edge("process_command", "execute_action")
    graph.add_conditional_edges(
        "execute_action",
        route_interaction,
        ["handle_error", "generate_feedback", END]
    )
    graph.add_edge("handle_error", "generate_feedback")
    graph.add_edge("generate_feedback", END)
    
    return graph.compile()
```

## Best Practices

1. Graph Design
   - Keep nodes focused and single-purpose
   - Use clear naming conventions
   - Document routing logic
   - Handle errors explicitly

2. State Management
   - Use TypedDict for type safety
   - Return minimal state updates
   - Validate state transitions
   - Track state history when needed

3. Error Handling
   - Add dedicated error nodes
   - Implement recovery strategies
   - Log error context
   - Provide user feedback

4. Performance
   - Use async nodes for I/O
   - Implement proper cleanup
   - Consider parallel processing
   - Monitor state size

This reference guide combines official LangGraph documentation with practical examples from our web reader implementation, providing a comprehensive resource for both understanding and using LangGraph effectively.
