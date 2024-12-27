"""LLM-based error recovery system for the screen reader application"""

import json
from typing import Dict, Any
from langgraph.graph import END

from src.state import State
from src.config import llm, VALID_ACTIONS
from src.utils.errors import create_error_response
from src.utils.logging import logger

def generate_error_recovery_prompt(error: Exception, state: State, failed_action: str) -> str:
    """Generate prompt for LLM to analyze error and suggest recovery"""
    history = state.get("execution_history", [])
    sub_tasks = state.get("sub_tasks", [])
    completed = state.get("completed_tasks", [])
    
    return f"""
    An error occurred while executing action '{failed_action}'.
    Error: {str(error)}
    
    Current state:
    - Page context: {state.get('page_context')}
    - Current action: {state.get('current_action')}
    - Action context: {state.get('action_context')}
    - Attempts: {state.get('attempts', 0)}
    - Remaining sub-tasks: {sub_tasks}
    - Completed tasks: {completed}
    
    User request: {state['messages'][-1]['content'] if state['messages'] else 'No message'}
    Execution history: {history}
    
    Analyze the error and suggest a recovery strategy. Consider:
    1. Task complexity - Should we break this into smaller steps?
    2. Dependencies - Are we missing required information or actions?
    3. Alternative approaches - Is there a better way to achieve the goal?
    4. Context needs - Do we need more information from the user?
    
    Return JSON with:
    - diagnosis: Brief analysis of what went wrong
    - strategy: One of ["retry", "alternative", "clarify", "decompose", "abort"]
    - sub_tasks: List of smaller tasks if strategy is "decompose"
    - dependencies: Dictionary mapping tasks to their dependencies
    - suggested_action: Alternative action from {list(VALID_ACTIONS.keys())} if strategy is "alternative"
    - confidence: Confidence in suggested strategy (0-1)
    - needed_context: Additional information needed if strategy is "clarify"
    - user_message: Clear explanation for the user
    """
def handle_error_with_llm(error: Exception, state: State) -> Dict[str, Any]:
    """Use LLM to analyze error and suggest recovery steps"""
    try:
        # Get recovery suggestion from LLM
        prompt = generate_error_recovery_prompt(error, state, state['current_action'])
        response = llm.invoke(prompt)
        
        try:
            recovery = json.loads(response.content)
            logger.debug(f"Error recovery suggestion: {json.dumps(recovery, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding LLM response: {str(e)}")
            return create_error_response(
                f"I encountered an error while trying to recover. Could you try rephrasing your request? Error: {str(e)}"
            )
        
        # Update state with recovery strategy
        state_updates = {
            "strategy": recovery["strategy"],
            "error": None  # Clear error since we're handling it
        }
        
        if recovery["strategy"] == "decompose":
            # Set up task decomposition
            state_updates.update({
                "sub_tasks": recovery["sub_tasks"],
                "task_dependencies": recovery["dependencies"],
                "completed_tasks": [],
                "attempts": 0
            })
            
        elif recovery["strategy"] == "alternative":
            # Try alternative approach
            state_updates.update({
                "current_action": recovery["suggested_action"],
                "action_context": recovery["needed_context"],
                "attempts": 0
            })
            
        elif recovery["strategy"] == "clarify":
            # Need more information from user
            return {
                "messages": [{"role": "assistant", "content": recovery["needed_context"]}],
                "strategy": "clarify",
                "next": END
            }
            
        # Add explanation message
        return {
            "messages": [{"role": "assistant", "content": recovery["user_message"]}],
            **state_updates,
            "next": "plan" if recovery["strategy"] in ["decompose", "clarify"] else "execute"
        }
            
    except Exception as e:
        logger.error(f"Error in error recovery: {str(e)}")
        return create_error_response(
            "I encountered an error while trying to recover. Could you try rephrasing your request?"
        )
