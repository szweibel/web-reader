"""Workflow management and execution for the screen reader application."""

from typing import Dict, Any
import json
from langgraph.graph import StateGraph, END

from .state import State
from .utils.logging import logger
from .utils.error_recovery import handle_error_with_llm
from . import actions
from .analysis.page_analyzer import analyze_page_structure

def build_workflow() -> StateGraph:
    """Build workflow graph with synchronous execution"""
    workflow = StateGraph(State)
    
    # Add core nodes
    workflow.add_node("analyze", analyze_page_structure)  # Page analysis
    workflow.add_node("plan", plan_execution)            # Plan execution
    workflow.add_node("execute", execute_action)         # Execute action
    workflow.add_node("error", handle_error)            # Error handling
    
    # Add edges
    workflow.add_edge("analyze", "plan")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("analyze", "error")
    workflow.add_edge("plan", "error")
    workflow.add_edge("execute", "error")
    workflow.add_edge("execute", END)
    workflow.add_edge("error", END)
    
    # Set entry point
    workflow.set_entry_point("analyze")
    
    return workflow.compile()

def plan_execution(state: State) -> Dict[str, Any]:
    """Plan task execution"""
    try:
        logger.debug("Starting plan_execution")
        # Log input state
        logger.debug("Input state:", extra={
            "messages": str(state.get("messages")),
            "current_action": state.get("current_action"),
            "page_context": str(state.get("page_context"))
        })
        
        # Get action from user input
        logger.debug("Determining action")
        action_result = actions.determine_action(state)
        logger.debug("Action determination result:", extra={
            "raw_result": str(action_result),
            "type": type(action_result).__name__
        })
        
        if not action_result:
            logger.error("No action result returned")
            return {
                "errors": ["Failed to determine action - no result"],
                "next": "error"
            }
            
        if isinstance(action_result, dict) and action_result.get("error"):
            logger.error(f"Action determination error: {action_result['error']}")
            return {
                "errors": [action_result["error"]],
                "next": "error"
            }
            
        # Log successful determination
        logger.debug("Action successfully determined:", extra={
            "action": action_result.get("action"),
            "confidence": action_result.get("confidence"),
            "context": action_result.get("context")
        })
        
        # Add action to state
        return {
            "current_action": action_result.get("action"),
            "action_context": action_result.get("context"),
            "next": "execute"
        }
        
    except Exception as e:
        logger.error(f"Error in plan_execution: {str(e)}", 
                    extra={
                        "exception_type": type(e).__name__,
                        "state": str(state)
                    })
        return {
            "errors": [f"Failed to plan execution: {str(e)}"],
            "next": "error"
        }

def execute_action(state: State) -> Dict[str, Any]:
    """Execute the determined action"""
    action = state.get("current_action")
    if not action:
        logger.error("No action specified in state")
        return {
            "errors": ["No action specified"],
            "next": "error"
        }
        
    try:
        logger.debug(f"Executing action: {action}", extra={
            "action": action,
            "context": state.get("action_context"),
            "state": str(state)
        })
        
        # Get action handler
        action_func = actions.get_action(action)
        if not action_func:
            logger.error(f"Unknown action: {action}")
            return {
                "errors": [f"Unknown action: {action}"],
                "next": "error"
            }
            
        # Execute action
        logger.debug(f"Calling action handler for: {action}")
        result = action_func(state)
        logger.debug("Action execution result:", extra={
            "result": str(result),
            "type": type(result).__name__
        })
        
        # Track execution
        state["execution_history"].append({
            "action": action,
            "context": state.get("action_context"),
            "result": str(result)
        })
        
        # If result is an ActionResult, extract its dict representation
        if hasattr(result, '__dict__'):
            result = result.__dict__
            
        logger.debug("Action completed successfully")
        return {
            **result,
            "next": END
        }
        
    except Exception as e:
        logger.error(f"Error executing action {action}: {str(e)}", 
                    extra={
                        "exception_type": type(e).__name__,
                        "traceback": e.__traceback__
                    })
        return {
            "errors": [f"Failed to execute {action}: {str(e)}"],
            "next": "error"
        }

def handle_error(state: State) -> Dict[str, Any]:
    """Handle errors and provide recovery options"""
    error = state.get("errors", ["Unknown error"])[-1]
    logger.error(f"Handling error: {error}", extra={
        "state": str(state),
        "history": str(state.get("execution_history", []))
    })
    
    # Use error recovery with LLM
    try:
        recovery_result = handle_error_with_llm(error, state)
        logger.debug("Error recovery result:", extra={
            "result": str(recovery_result)
        })
        
        # Always end after error handling
        return {
            **recovery_result,
            "next": END
        }
    except Exception as e:
        logger.error(f"Error in error handling: {str(e)}")
        return {
            "messages": [{
                "role": "assistant", 
                "content": "I encountered an error while trying to recover. Please try again."
            }],
            "next": END
        }