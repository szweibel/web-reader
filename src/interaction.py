"""User interaction handling and application lifecycle management.

This module serves as the entry point and interaction manager for the screen reader,
handling user input/output and coordinating the overall application flow.

Key Components:
    - Application Lifecycle: Startup, shutdown, and browser management
    - User Interaction: Input processing and output formatting
    - State Management: Per-interaction state creation and tracking
    - Logging: Structured logging of interactions and events

Core Functions:
    - main: Application entry point and lifecycle manager
    - process_user_input: Handles user input processing and state updates

The module is designed to:
    - Provide a clean user interface
    - Handle graceful startup/shutdown
    - Manage browser lifecycle
    - Enable structured logging
    - Coordinate workflow execution

Dependencies:
    - workflow.py: Provides the core workflow engine
    - browser.py: Handles browser automation
    - state.py: Manages application state
    - config.py: Provides configuration and examples
"""

from dataclasses import asdict
import json
import asyncio

__all__ = ['main', 'process_user_input']
from typing import Dict, Any
from langgraph.graph import StateGraph

from .state import State, create_initial_state
from .utils.logging import logger
from .utils.errors import ReaderActionError
from .browser import setup_browser, cleanup_browser
from .workflow import build_workflow
from .config import USAGE_EXAMPLES

async def process_user_input(graph: StateGraph, state: State) -> None:
    """Process user input with enhanced logging and monitoring"""
    # Get user input safely
    messages = state.get('messages', [])
    if not messages:
        logger.error("No messages in state")
        return
        
    try:
        last_message = messages[-1]
        user_input = last_message.get('content') if isinstance(last_message, dict) else str(last_message)
    except (IndexError, AttributeError) as e:
        logger.error(f"Error getting message content: {str(e)}")
        return
        
    state_id = str(id(state))
    with logger.action_context("process_input", state_id, input=user_input) as context:
        try:
            # Run the graph asynchronously
            result = await graph.ainvoke(state)
            logger.debug("Graph execution result", 
                       context={
                           "result": json.dumps(result, default=str),
                           "result_type": type(result).__name__,
                           "state_id": state_id
                       })
            
            # Track state before update
            old_state = {
                "action": state.get("current_action"),
                "page_context": state.get("page_context"),
                "predictions": state.get("predictions")
            }
            
            # Process result updates
            if isinstance(result, dict):
                # Update state directly from result fields
                for field, field_value in result.items():
                    if field not in ["messages", "next"]:
                        logger.debug(f"Updating state from result: {field}", extra={
                            "field": field,
                            "old_value": state.get(field),
                            "new_value": field_value,
                            "state_id": state_id
                        })
                        # Handle state updates directly
                        state[field] = field_value
                                
                        # Log state transitions
                        if field in ["action", "page_context", "predictions"]:
                            logger.log_state_transition(
                                from_state=str(old_state.get(field)),
                                to_state=str(field_value),
                                context={
                                    "field": field,
                                    "state_id": state_id
                                }
                            )
                        
                # Print messages after state is updated
                if "messages" in result:
                    for msg in result["messages"]:
                        if isinstance(msg, dict) and msg.get("role") == "assistant":
                            print(f"\n{msg['content']}")
            
                # Log predictions if available
                if "predictions" in result:
                    predictions = result["predictions"]
                    actual = {
                        "needs_scroll": state.get("page_context", {}).get("scroll_position", 0) > 0,
                        "needs_wait": state.get("page_context", {}).get("dynamic_content", False),
                        "potential_popups": False  # Will be updated if popup detected
                    }
                    logger.log_prediction(predictions, actual)
                
                # Update context with latest state
                if state.get("page_context"):
                    context.page_context = state.get("page_context", {})
                context.element_context = str(state.get("element_context"))
                context.predictions = str(state.get("predictions"))
        except Exception as e:
            logger.log_error(f"Error in process_user_input: {str(e)}", {
                "state_id": state_id,
                "input": user_input
            })
            raise

async def main() -> None:
    """Enhanced main application entry point with structured logging"""
    with logger.action_context("application_startup", "main") as context:
        logger.info("Starting Natural Language Screen Reader")
        driver = None
        
        try:
            # Initialize browser
            driver = setup_browser()
            logger.info("Browser initialized successfully")
            
            # Print usage instructions
            print(USAGE_EXAMPLES)
            print("\nType 'exit' to quit")
            
            # Initialize workflow
            graph = build_workflow()
            logger.info("Workflow initialized", 
                       context={"graph_nodes": list(graph.nodes.keys())})
            
            # Main interaction loop
            interaction_count = 0
            while True:
                interaction_id = f"interaction_{interaction_count}"
                
                try:
                    # Get user input
                    user_input = input("\nWhat would you like me to do? ").strip()
                    if user_input.lower() in ["exit", "quit", "q"]:
                        break
                    
                    with logger.action_context("user_interaction", interaction_id,
                                             input=user_input) as interaction_context:
                        # Create new state for each interaction
                        state = create_initial_state(driver, user_input)
                        state["messages"] = [{"role": "user", "content": user_input}]
                        
                        # Process the input
                        await process_user_input(graph, state)
                        
                        # Update metrics
                        interaction_count += 1
                        
                except KeyboardInterrupt:
                    logger.info("Operation cancelled by user", 
                              context={"interaction_id": interaction_id})
                    print("\nOperation cancelled by user")
                    continue
                except ReaderActionError as e:
                    logger.log_error(str(e), {
                        "interaction_id": interaction_id,
                        "error_type": "ReaderError"
                    })
                    print(f"\n{str(e)}")
                    continue
                except Exception as e:
                    # Just print the error message, avoid logging here
                    print(f"\nAn unexpected error occurred. Please try again.")
                    continue
                    
        except Exception as e:
            logger.log_error(str(e), {
                "error_type": "FatalError",
                "startup_context": asdict(context)
            })
            print(f"\nFatal error: {str(e)}")
            
        finally:
            if driver:
                print("\nClosing browser...")
                cleanup_browser(driver)
            logger.info("Application shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
