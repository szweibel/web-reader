# Module Architecture

```mermaid
graph TD
    %% Core Modules
    I[interaction.py] --> W[workflow.py]
    I --> B[browser.py]
    I --> S[state.py]
    
    %% Workflow Dependencies
    W --> E[execution.py]
    W --> A[actions/*]
    W --> ER[utils/error_recovery.py]
    
    %% Execution Dependencies
    E --> PA[analysis/page_analyzer.py]
    E --> S
    E --> B
    
    %% Action Dependencies
    A --> S
    A --> B
    
    %% Analysis Dependencies
    PA --> B
    PA --> S

    %% Shared Dependencies
    W --> S
    E --> S
    
    %% Module Responsibilities
    subgraph "Core Application Flow"
        I[interaction.py]
        style I fill:#f9f,stroke:#333
        W[workflow.py]
        style W fill:#bbf,stroke:#333
    end
    
    subgraph "Page Understanding"
        E[execution.py]
        style E fill:#bfb,stroke:#333
        PA[analysis/page_analyzer.py]
        style PA fill:#bfb,stroke:#333
    end
    
    subgraph "Web Interaction"
        A[actions/*]
        style A fill:#fbb,stroke:#333
        B[browser.py]
        style B fill:#fbb,stroke:#333
    end
    
    subgraph "Support Systems"
        S[state.py]
        style S fill:#ff9,stroke:#333
        ER[utils/error_recovery.py]
        style ER fill:#ff9,stroke:#333
    end

%% Module Descriptions
classDef default fill:#fff,stroke:#333,stroke-width:2px;
```

## Module Responsibilities

### Core Application Flow
- **interaction.py**: Application entry point, user I/O, lifecycle management
- **workflow.py**: Workflow engine, task orchestration, parallel execution

### Page Understanding
- **execution.py**: Page analysis, action preparation, interaction prediction
- **analysis/page_analyzer.py**: Structured page analysis, accessibility evaluation

### Web Interaction
- **actions/**: Concrete web interaction implementations
- **browser.py**: Browser automation and control

### Support Systems
- **state.py**: Application state management, task tracking
- **utils/error_recovery.py**: LLM-based error recovery and adaptation

## Key Design Principles

1. **Separation of Concerns**
   - Clear module boundaries with focused responsibilities
   - Minimal circular dependencies
   - Hierarchical organization

2. **Extensibility**
   - Modular action system
   - Pluggable analysis components
   - Flexible workflow engine

3. **Robustness**
   - Comprehensive error handling
   - State isolation per interaction
   - Graceful degradation

4. **Accessibility Focus**
   - Rich page analysis
   - Semantic understanding
   - Adaptive interaction

5. **Learning & Adaptation**
   - Pattern recognition
   - Error recovery
   - Predictive interaction
