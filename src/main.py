#!/usr/bin/env python3
"""Main entry point for the screen reader application"""

import sys
import json
import time
from typing import Dict, Any, List, Tuple, Union
from dataclasses import asdict
from bs4 import BeautifulSoup
from langgraph.graph import StateGraph, END
from src.state import State, PageContext, create_initial_state, Task, TaskStatus, create_task, create_task_status
from src.browser import setup_browser, cleanup_browser
import src.config as config
from src.config import VALID_ACTIONS, USAGE_EXAMPLES, llm
from src.utils.logging import logger
from src.utils.errors import ReaderActionError as ReaderError
from src.utils.error_recovery import handle_error_with_llm
from src import actions
from src.config import LLMPageAnalysis

# Import action registry first
from src.actions import determine_action

import json
from typing import Dict, Any
from dataclasses import asdict
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema import HumanMessage

from .state import State, create_initial_state
from .browser import setup_browser, cleanup_browser
from .utils.logging import logger
from .utils.errors import ReaderActionError as ReaderError
from .workflow import build_workflow
from .config import USAGE_EXAMPLES

        ... (rest of the prompt)
"""
        # Return analysis result
        return {
                "page_context": PageContext(
                    type="unknown",
                    has_main=bool(main_tag or role_main),
                    has_nav=bool(soup.find("nav")),
                    has_article=bool(soup.find("article")),
                    has_headlines=bool(headings),
                    has_forms=bool(soup.find("form")),
                    dynamic_content=False,
                    scroll_position=0,
                    viewport_height=0,
                    total_height=0
                ),
                "title": title,
                "headings": headings,
                "description": description,
                "main_content_analysis": main_content_analysis,
                "main_content_analysis_json": main_content_analysis_json,
                "url": url,
                "prompt": prompt
            }
    except Exception as e:
        logger.error(f"Error analyzing context: {str(e)}")
        return {"error": str(e)}

def plan_task_execution(state: State) -> Dict[str, Any]:
    """Enhanced task planning with parallel execution support"""
    try:
        # Get initial action from user input
        action_result = determine_action(state)
        logger.debug(f"Action determination result: {action_result}")
        
        if not action_result or action_result.get("error"):
            return {
                "error": action_result.get("error") if action_result else "Failed to determine action",
                "next": "error_recovery"
            }
        
        # Create task graph
        task_graph = build_task_graph(state, action_result)
        
        # Find parallel execution opportunities
        parallel_groups = find_parallel_tasks(task_graph)
        
        # Create execution plan
        execution_plan = create_execution_plan(task_graph, parallel_groups)
        
        # Update state with task information
        state["tasks"] = task_graph
        state["parallel_groups"] = parallel_groups
        state["execution_plan"] = execution_plan
        state["active_tasks"] = set()
        
        return {
            "next": "execute_parallel" if parallel_groups else "execute"
        }
        
    except Exception as e:
        logger.error(f"Error in plan_task_execution: {str(e)}")
        return {
            "error": f"Failed to plan execution: {str(e)}",
            "next": "error_recovery"
        }

def build_task_graph(state: State, action_result: Dict[str, Any]) -> Dict[str, Task]:
    """Build task dependency graph"""
    tasks = {}
    
    # Create main task
    action = action_result["current_action"]
    action_type = config.VALID_ACTIONS[action]
    main_task = create_task(
        task_id=action,
        task_type=action_type,
        state={"context": action_result.get("action_context", {})}
    )
    tasks[main_task.id] = main_task
    
    # Check for potential parallel tasks based on page context
    page_context = state.get("page_context")
    if isinstance(page_context, PageContext):
        # Content analysis can run in parallel with navigation
        if page_context.has_article or page_context.has_headlines:
            tasks["analyze_content"] = create_task(
                task_id="analyze_content",
                task_type="reading",
                can_parallel=True
            )
        
        # Structure analysis can run in parallel
        if page_context.has_main:
            tasks["analyze_structure"] = create_task(
                task_id="analyze_structure",
                task_type="reading",
                can_parallel=True
            )
        
        # Dynamic content handling
        if page_context.dynamic_content:
            tasks["handle_dynamic"] = create_task(
                task_id="handle_dynamic",
                task_type="interaction",
                dependencies=[main_task.id]
            )
    
    return tasks

def find_parallel_tasks(task_graph: Dict[str, Task]) -> List[List[str]]:
    """Find tasks that can be executed in parallel"""
    parallel_groups = []
    visited = set()
    
    for task_id, task in task_graph.items():
        if task_id in visited or not task.can_parallel:
            continue
            
        # Find other parallel tasks at same level
        parallel_group = [task_id]
        for other_id, other_task in task_graph.items():
            if other_id in visited or not other_task.can_parallel:
                continue
                
            # Check if tasks can run in parallel (no dependencies between them)
            if not (set(task.dependencies) & set(other_task.dependencies)):
                parallel_group.append(other_id)
                
        if len(parallel_group) > 1:
            parallel_groups.append(parallel_group)
            visited.update(parallel_group)
            
    return parallel_groups

def create_execution_plan(
    task_graph: Dict[str, Task],
    parallel_groups: List[List[str]]
) -> List[Union[str, List[str]]]:
    """Create optimal execution plan"""
    plan = []
    executed = set()
    
    while len(executed) < len(task_graph):
        # Find ready tasks (all dependencies satisfied)
        ready_tasks = []
        for task_id, task in task_graph.items():
            if task_id in executed:
                continue
                
            if all(dep in executed for dep in task.dependencies):
                ready_tasks.append(task_id)
        
        # Check if any ready tasks are in parallel groups
        for group in parallel_groups:
            if all(task in ready_tasks for task in group):
                plan.append(group)
                executed.update(group)
                ready_tasks = [t for t in ready_tasks if t not in group]
        
        # Add remaining ready tasks sequentially
        for task in ready_tasks:
            plan.append(task)
            executed.add(task)
            
    return plan

def prepare_action(state: State) -> Dict[str, Any]:
    """Prepare for action execution, handling setup needs"""
    try:
        # Handle dynamic content
        page_context = state.get("page_context")
        if isinstance(page_context, PageContext) and page_context.type in ["news", "article"]:
            # Wait for dynamic content
            state["driver"].implicitly_wait(2)
            
        # Predict needed interactions
        predictions = predict_needed_interactions(state)
        
        return {
            "predictions": predictions,
            "next": "execute"
        }
        
    except Exception as e:
        logger.error(f"Error in prepare_action: {str(e)}")
        return {
            "error": f"Failed to prepare action: {str(e)}",
            "next": "error_recovery"
        }

def execute_parallel_tasks(state: State) -> Dict[str, Any]:
    """Execute tasks that can run in parallel"""
    try:
        # Get next group of tasks to execute
        current_plan = state["execution_plan"]
        if not current_plan:
            return {"next": END}
            
        next_tasks = current_plan[0]
        if isinstance(next_tasks, list):
            # Execute parallel tasks
            results = {}
            for task_id in next_tasks:
                task = state["tasks"][task_id]
                try:
                    # Execute task
                    action_func = actions.get_action(VALID_ACTIONS[task.type])
                    result = action_func(state)
                    
                    # Update task status
                    state["task_status"][task_id] = create_task_status(
                        status="completed",
                        start_time=time.time(),
                        end_time=time.time()
                    )
                    
                    results[task_id] = result
                except Exception as e:
                    logger.error(f"Error executing task {task_id}: {str(e)}")
                    state["task_status"][task_id] = create_task_status(
                        status="failed",
                        error=str(e),
                        start_time=time.time(),
                        end_time=time.time()
                    )
                    results[task_id] = {"error": str(e)}
            
            # Remove executed group from plan
            state["execution_plan"] = current_plan[1:]
            
            # Check results
            if any(r.get("error") for r in results.values()):
                return {
                    "error": "Some parallel tasks failed",
                    "results": results,
                    "next": "error_recovery"
                }
                
            return {
                "results": results,
                "next": "execute_parallel" if state["execution_plan"] else END
            }
        else:
            # Single task execution
            task_id = next_tasks
            task = state["tasks"][task_id]
            
            try:
                # Execute task
                action_func = actions.get_action(VALID_ACTIONS[task.type])
                result = action_func(state)
                
                # Update task status
                state["task_status"][task_id] = create_task_status(
                    status="completed",
                    start_time=time.time(),
                    end_time=time.time()
                )
                
                # Remove executed task from plan
                state["execution_plan"] = current_plan[1:]
                
                # Include any messages from the action result
                return {
                    "result": result,
                    "messages": result.get("messages", []),
                    "next": "execute_parallel" if state["execution_plan"] else END
                }
                
            except Exception as e:
                logger.error(f"Error executing task {task_id}: {str(e)}")
                state["task_status"][task_id] = create_task_status(
                    status="failed",
                    error=str(e),
                    start_time=time.time(),
                    end_time=time.time()
                )
                return {
                    "error": f"Failed to execute {task_id}: {str(e)}",
                    "next": "error_recovery"
                }
                
    except Exception as e:
        logger.error(f"Error in execute_parallel_tasks: {str(e)}")
        return {
            "error": f"Failed to execute parallel tasks: {str(e)}",
            "next": "error_recovery"
        }

def predict_needed_interactions(state: State) -> Dict[str, Any]:
    """Predict interactions that might be needed"""
    predictions = {
        "needs_scroll": False,
        "needs_click": False,
        "needs_wait": False,
        "potential_popups": False
    }
    
    page_context = state.get("page_context")
    if not isinstance(page_context, PageContext):
        return predictions
        
    # Predict based on page type
    if page_context.type == "news":
        predictions["needs_scroll"] = True
        predictions["potential_popups"] = True
    elif page_context.type == "article":
        predictions["needs_scroll"] = True
    elif page_context.type == "form":
        predictions["needs_click"] = True
        
    # Predict based on structure
    if page_context.has_nav:
        predictions["needs_click"] = True
        
    return predictions

def reflect_on_execution(state: State) -> Dict[str, Any]:
    """Enhanced reflection with learning and adaptation"""
    history = state.get("execution_history", [])
    if not history:
        return {"next": END}
        
    prompt = f"""Reflect on these execution attempts:
    User request: "{state['messages'][-1]['content']}"
    Execution history: {history}
    
    Current state:
    - Page type: {state.get('page_type')}
    - Page context: {state.get('page_context')}
    - Headlines found: {'Yes' if state.get('headlines') else 'No'}
    - Last element found: {'Yes' if state.get('last_found_element') else 'No'}
    - Current action: {state.get('current_action')}
    - Action context: {state.get('action_context')}
    - Error: {state.get('error')}
    - Predictions: {state.get('predictions')}
    
    Analyze what went wrong and suggest a recovery strategy. Consider:
    1. Was this the right action for the user's intent?
    2. Are there alternative approaches we could try?
    3. Do we need more context or information?
    4. Should we break this down into smaller steps?
    5. Were our predictions accurate?
    6. What can we learn for future interactions?
    
    Return JSON with:
    - analysis: Brief explanation of what went wrong
    - strategy: One of ["retry", "alternative", "clarify", "decompose", "abort"]
    - suggested_action: Alternative action to try if strategy is "alternative"
    - sub_tasks: List of smaller tasks if strategy is "decompose"
    - clarification_needed: What to ask user if strategy is "clarify"
    - confidence: Confidence in suggested strategy (0-1)
    - learnings: What we learned for future predictions
    - prediction_adjustments: How to adjust our predictions"""
    
    response = llm.invoke(prompt)
    reflection = json.loads(response.content)
    
    # Update prediction model with learnings
    if reflection.get("learnings"):
        # Store learnings for future predictions
        state.setdefault("learned_patterns", []).append(reflection["learnings"])
        
    # Handle different reflection strategies
    if reflection["strategy"] == "retry":
        return {
            "attempts": state["attempts"],
            "next": "prepare"  # Go through preparation again
        }
    elif reflection["strategy"] == "alternative" and reflection["confidence"] > 0.7:
        return {
            "current_action": reflection["suggested_action"],
            "attempts": 0,
            "next": "prepare"
        }
    elif reflection["strategy"] == "decompose":
        # Store sub-tasks and execute first one
        sub_tasks = reflection["sub_tasks"]
        if sub_tasks:
            return {
                "sub_tasks": sub_tasks[1:],  # Store remaining tasks
                "task_dependencies": build_task_dependencies(sub_tasks),
                "messages": [{"role": "user", "content": sub_tasks[0]}],
                "attempts": 0,
                "next": "analyze"  # Start fresh with new task
            }
    
    # If all else fails or low confidence
    return {
        "messages": [{
            "role": "assistant",
            "content": "I'm having trouble completing this task. Could you try rephrasing your request?"
        }],
        "next": END
    }

def build_task_dependencies(tasks: List[str]) -> Dict[str, List[str]]:
    """Build dependency graph for tasks"""
    dependencies = {}
    for i, task in enumerate(tasks):
        # Simple sequential dependencies for now
        dependencies[task] = [tasks[i-1]] if i > 0 else []
    return dependencies

def build_workflow() -> StateGraph:
    """Build enhanced workflow graph with parallel execution support"""
    workflow = StateGraph(State)
    
    # Add core nodes
    workflow.add_node("analyze", analyze_context)           # Analyze page context
    workflow.add_node("plan", plan_task_execution)         # Enhanced task planning
    workflow.add_node("prepare", prepare_action)           # Prepare for execution
    workflow.add_node("execute_parallel", execute_parallel_tasks)  # Task execution (both single and parallel)
    workflow.add_node("reflect", reflect_on_execution)     # Enhanced reflection
    workflow.add_node("error_recovery", lambda state: handle_error_with_llm(state.get("error"), state))
    
    # Add base edges
    workflow.add_edge("analyze", "plan")
    workflow.add_edge("plan", "prepare")
    
    # Add conditional edges from prepare node
    workflow.add_conditional_edges(
        "prepare",
        lambda x: x.get("next", "execute_parallel"),
        {
            "execute": "execute_parallel",  # Both 'execute' and 'execute_parallel' go to the same node
            "execute_parallel": "execute_parallel",
            "error_recovery": "error_recovery"
        }
    )
    
    # Add conditional edges from execute_parallel node
    workflow.add_conditional_edges(
        "execute_parallel",
        lambda x: (
            "error_recovery" if x.get("error")
            else "reflect" if x.get("attempts", 0) > 1
            else "execute_parallel" if x.get("next") == "execute_parallel"
            else END
        ),
        {
            "error_recovery": "error_recovery",
            "reflect": "reflect",
            "execute_parallel": "execute_parallel",
            END: END
        }
    )
    
    # Add conditional edges from reflection node
    workflow.add_conditional_edges(
        "reflect",
        lambda x: (
            "analyze" if x.get("next") == "analyze"
            else "plan" if x.get("next") == "plan"
            else "prepare" if x.get("next") == "prepare"
            else END
        ),
        {
            "analyze": "analyze",
            "plan": "plan",
            "prepare": "prepare",
            END: END
        }
    )
    
    # Add conditional edges from error recovery node
    workflow.add_conditional_edges(
        "error_recovery",
        lambda x: (
            "analyze" if x.get("strategy") in ["decompose", "clarify"]
            else "prepare" if x.get("strategy") in ["retry", "alternative"]
            else END
        ),
        {
            "analyze": "analyze",
            "prepare": "prepare",
            END: END
        }
    )
    
    # Set entry point
    workflow.set_entry_point("analyze")
    
    return workflow.compile()

def process_user_input(graph: StateGraph, state: State) -> None:
    """Process user input with enhanced logging and monitoring"""
    user_input = state['messages'][-1]['content']
    state_id = str(id(state))
    
    with logger.action_context("process_input", state_id, input=user_input) as context:
        try:
            # Execute workflow graph
            result = graph.invoke(state)
            
            logger.debug("Graph execution result", 
                       context={
                           "state_id": state_id,
                           "result": str(result)
                       })
            
            # Track state changes
            old_state = {
                "action": state.get("current_action"),
                "page_context": state.get("page_context")
            }
            
            # Handle result updates
            if isinstance(result, dict):
                # Update state fields
                for field, value in result.items():
                    if field not in ["messages", "next"]:
                        logger.debug(f"Updating state: {field}", extra={
                            "field": field,
                            "old_value": state.get(field),
                            "new_value": value,
                            "state_id": state_id
                        })
                        state[field] = value
                
                # Handle messages
                if "messages" in result:
                    for msg in result["messages"]:
                        if isinstance(msg, dict) and msg.get("role") == "assistant":
                            print(f"\n{msg['content']}")
                
                # Update context
                if state.get("page_context"):
                    context.page_context = state.get("page_context")
                context.element_context = str(state.get("element_context"))
                
        except Exception as e:
            logger.error(f"Error in process_user_input: {str(e)}", extra={
                "state_id": state_id,
                "input": user_input
            })
            raise

def main() -> None:
    """Main application entry point"""
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
            
            # Build LCEL workflow
            graph = build_workflow()
            logger.info("LCEL workflow initialized")
            
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
                        # Create new state
                        logger.debug("Creating initial state", extra={"user_input": user_input})
                        state = create_initial_state(driver, user_input)
                        logger.debug("Setting messages", extra={"message": str(HumanMessage(content=user_input))})
                        state["messages"] = [HumanMessage(content=user_input)]
                        
                        # Log state before processing
                        logger.debug("Processing user input", extra={
                            "input": user_input,
                            "state": {
                                "messages": [str(m) for m in state["messages"]],
                                "current_action": state.get("current_action"),
                                "action_context": state.get("action_context")
                            }
                        })
                        
                        # Process input through workflow
                        try:
                            process_user_input(graph, state)
                        except Exception as e:
                            logger.error(f"Error in process_user_input: {str(e)}", extra={
                                "error_type": type(e).__name__,
                                "traceback": str(e.__traceback__)
                            })
                            raise
                        
                        # Update metrics
                        interaction_count += 1
                        
                except KeyboardInterrupt:
                    logger.info("Operation cancelled by user")
                    print("\nOperation cancelled by user")
                    continue
                except ReaderError as e:
                    logger.error(str(e))
                    print(f"\n{str(e)}")
                    continue
                except Exception as e:
                    print(f"\nAn unexpected error occurred. Please try again.")
                    continue
                    
        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")
            print(f"\nFatal error: {str(e)}")
            
        finally:
            if driver:
                print("\nClosing browser...")
                cleanup_browser(driver)
            logger.info("Application shutdown complete")

if __name__ == "__main__":
    main()
