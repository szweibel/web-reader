#!/usr/bin/env python3
"""Main entry point for the screen reader application"""

import sys
import json
from typing import Dict, Any, List, Tuple
from dataclasses import asdict
from bs4 import BeautifulSoup
from langgraph.graph import StateGraph, END
from src.state import State, PageContext, create_initial_state
from src.browser import setup_browser, cleanup_browser
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
from bs4 import BeautifulSoup

def analyze_context(state: State) -> Dict[str, Any]:
    """Analyze page context and user intent using LLM"""
    try:
        # Get page source and URL
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        url = state["driver"].current_url
        
        # Extract key elements for analysis
        title = soup.title.string if soup.title else ""
        headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text().strip()]
        meta_desc = soup.find("meta", {"name": "description"})
        description = meta_desc.get("content", "") if meta_desc else ""
        
        # Find potential main content areas
        main_candidates = []
        
        # Check explicit main tag
        main_tag = soup.find("main")
        if main_tag:
            main_candidates.append(("main tag", main_tag))
            
        # Check role="main"
        role_main = soup.find(attrs={"role": "main"})
        if role_main:
            main_candidates.append(("role=main", role_main))
            
        # Check common content IDs/classes
        content_patterns = {
            "id": ["content", "main", "article", "post", "story", "body"],
            "class": ["content", "main", "article", "post", "story", "body", "entry", "text"]
        }
        
        for attr, patterns in content_patterns.items():
            for pattern in patterns:
                if attr == "id":
                    content_by_attr = soup.find(id=lambda x: x and pattern in x.lower())
                else:
                    content_by_attr = soup.find(class_=lambda x: x and pattern in x.lower())
                if content_by_attr:
                    main_candidates.append((f"{attr}={pattern}", content_by_attr))
                
        # Check article tags and sections with significant content
        for tag in ["article", "section", "div"]:
            elements = soup.find_all(tag)
            for element in elements:
                # Skip if likely navigation/sidebar/footer
                if any(cls in str(element.get("class", [])).lower() for cls in ["nav", "menu", "sidebar", "footer", "header", "ad"]):
                    continue
                    
                # Check content significance
                text_length = len(element.get_text(strip=True))
                paragraphs = len(element.find_all("p"))
                if text_length > 500 or paragraphs > 2:  # Significant content threshold
                    main_candidates.append((f"content-rich {tag}", element))
            
        # Analyze content density and quality of candidates
        main_content_analysis = []
        for candidate_type, element in main_candidates:
            # Get text content excluding scripts and styles
            element_copy = BeautifulSoup(str(element), "html.parser")  # Create a copy to modify
            for script in element_copy.find_all(["script", "style"]):
                script.decompose()
            text = element_copy.get_text(strip=True)
            
            # Count meaningful elements
            links = len(element.find_all("a"))
            images = len(element.find_all("img"))
            paragraphs = len(element.find_all("p"))
            headings = len(element.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
            lists = len(element.find_all(["ul", "ol"]))
            
            # Calculate content-to-noise ratio
            noise_elements = len(element.find_all(class_=lambda x: x and any(p in str(x).lower() for p in ["ad", "promo", "banner", "widget", "sidebar"])))
            content_elements = paragraphs + headings + lists
            
            # Check semantic structure
            has_article_structure = bool(element.find("article"))
            has_section_structure = bool(element.find("section"))
            has_semantic_headings = bool(element.find(["h1", "h2", "h3"]))
            
            main_content_analysis.append({
                "type": candidate_type,
                "text_length": len(text),
                "links": links,
                "images": images,
                "paragraphs": paragraphs,
                "headings": headings,
                "lists": lists,
                "content_elements": content_elements,
                "noise_elements": noise_elements,
                "content_to_noise_ratio": content_elements / (noise_elements + 1),
                "semantic_structure": {
                    "has_article": has_article_structure,
                    "has_section": has_section_structure,
                    "has_semantic_headings": has_semantic_headings
                }
            })
        
        # Prepare context for LLM analysis
        try:
            main_content_analysis_json = json.dumps(main_content_analysis, indent=2)
        except Exception as e:
            logger.error(f"Error serializing main_content_analysis to JSON: {str(e)}")
            main_content_analysis_json = "Error serializing main_content_analysis to JSON"
            
        prompt = f"""Analyze this webpage and determine its type and structure:

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

def plan_execution(state: State) -> Dict[str, Any]:
    """Plan task execution"""
    try:
        # Get action from user input
        action_result = determine_action(state)
        logger.debug(f"Action determination result: {action_result}")
        
        # Track attempt count
        state["attempts"] = state.get("attempts", 0) + 1
        
        # If multiple attempts, trigger reflection
        if state["attempts"] > 1:
            return {"next": "reflect"}
            
        # Ensure we have a valid action result
        if not action_result or action_result.get("error"):
            return {
                "error": action_result.get("error") if action_result else "Failed to determine action",
                "next": "error_recovery"
            }
            
        return action_result
        
    except Exception as e:
        logger.error(f"Error in plan_execution: {str(e)}")
        return {
            "error": f"Failed to plan execution: {str(e)}",
            "next": "error_recovery"
        }

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

def execute_action(state: State) -> Dict[str, Any]:
    """Execute the determined action"""
    action = state.get("current_action")
    if not action or action not in VALID_ACTIONS:
        return {"next": END}
        
    try:
        # Execute action
        action_func = actions.get_action(VALID_ACTIONS[action])
        result = action_func(state)
        
        # Track execution history
        state["execution_history"].append({
            "action": action,
            "context": state.get("action_context"),
            "result": result
        })
        
        # If result is an ActionResult, extract its dict representation
        if hasattr(result, '__dict__'):
            result = result.__dict__
            
        return result
        
    except Exception as e:
        logger.error(f"Error executing action {action}: {str(e)}")
        return {
            "error": f"Failed to execute {action}: {str(e)}",
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
    elif reflection["strategy"] == "clarify":
        return {
            "messages": [{
                "role": "assistant", 
                "content": reflection["clarification_needed"]
            }],
            "next": END
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
    """Build enhanced workflow graph with granular control"""
    workflow = StateGraph(State)
    
    # Add core nodes
    workflow.add_node("analyze", analyze_context)      # Analyze page context
    workflow.add_node("plan", plan_execution)         # Plan execution
    workflow.add_node("prepare", prepare_action)      # Prepare for execution
    workflow.add_node("execute", execute_action)      # Execute action
    workflow.add_node("reflect", reflect_on_execution)  # Enhanced reflection
    # Wrap error handler to match node signature
    workflow.add_node("error_recovery", lambda state: handle_error_with_llm(state.get("error"), state))  # Error handling
    
    # Add base edges
    workflow.add_edge("analyze", "plan")
    workflow.add_edge("plan", "prepare")
    workflow.add_edge("prepare", "execute")
    
    # Add conditional edges from execute node
    workflow.add_conditional_edges(
        "execute",
        lambda x: (
            "error_recovery" if x.get("error")
            else "reflect" if x.get("attempts", 0) > 1
            else END
        ),
        {
            "error_recovery": "error_recovery",
            "reflect": "reflect",
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
    
    with logger.action_context("process_input", state_id, 
                             input=user_input) as context:
        try:
            for event in graph.stream(state):
                if event is None:
                    continue
                
                logger.debug("Processing event", 
                           context={"event": event, "state_id": state_id})
                
                # Track state before update
                old_state = {
                    "action": state.get("current_action"),
                    "page_context": state.get("page_context"),
                    "predictions": state.get("predictions")
                }
                
                # Process event updates
                for key, value in event.items():
                    if isinstance(value, dict):
                        # Update state first
                        for field, field_value in value.items():
                            if field not in ["messages", "next"]:
                                state[field] = field_value
                                
                                # Log state transitions
                                if field in ["current_action", "page_context", "predictions"]:
                                    logger.log_state_transition(
                                        from_state=str(old_state.get(field)),
                                        to_state=str(field_value),
                                        context={
                                            "field": field,
                                            "state_id": state_id
                                        }
                                    )
                        
                        # Print messages after state is updated
                        if "messages" in value:
                            for msg in value["messages"]:
                                if isinstance(msg, dict) and msg.get("role") == "assistant":
                                    print(f"\n{msg['content']}")
                
                # Log predictions if available
                if "predictions" in event:
                    predictions = event["predictions"]
                    actual = {
                        "needs_scroll": state.get("page_context", {}).get("scroll_position", 0) > 0,
                        "needs_wait": state.get("page_context", {}).get("dynamic_content", False),
                        "potential_popups": False  # Will be updated if popup detected
                    }
                    logger.log_prediction(predictions, actual)
                
                # Update context with latest state (convert complex objects to dicts/strings)
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

def main() -> None:
    """Enhanced main application entry point with structured logging"""
    with logger.action_context("application_startup", "main") as context:
        logger.info("Starting Natural Language Screen Reader")
        
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
                        
                        # Process the input
                        process_user_input(graph, state)
                        
                        # Update metrics
                        interaction_count += 1
                        
                except KeyboardInterrupt:
                    logger.info("Operation cancelled by user", 
                              context={"interaction_id": interaction_id})
                    print("\nOperation cancelled by user")
                    continue
                except ReaderError as e:
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
            print("\nClosing browser...")
            cleanup_browser(driver)
            logger.info("Application shutdown complete")

if __name__ == "__main__":
    main()
