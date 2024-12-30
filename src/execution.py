"""Task execution and prediction logic for the screen reader application.

This module handles the analysis and preparation phases of web page interaction,
serving as a bridge between the workflow engine and concrete actions.

Key Components:
    - Page Analysis: Deep analysis of web page structure and content
    - Action Preparation: Setup and prediction for action execution
    - Interaction Prediction: Anticipates needed interactions based on page type

Core Functions:
    - analyze_context: Performs comprehensive page analysis using LLM
    - prepare_action: Prepares state for action execution
    - predict_needed_interactions: Predicts required interactions based on page type

The module is designed to:
    - Provide rich context for decision making
    - Enable predictive interaction handling
    - Support accessibility-aware analysis
    - Facilitate dynamic content handling

Dependencies:
    - page_analyzer.py: Provides detailed page structure analysis
    - state.py: Defines state and context structures
    - browser.py: Provides browser automation capabilities
"""

from typing import Dict, Any, List
import json
import asyncio

__all__ = ['analyze_context', 'prepare_action', 'predict_needed_interactions']
from bs4 import BeautifulSoup
from langchain.schema import HumanMessage
from langchain.schema.runnable import RunnableConfig, ConfigurableField
from .config import llm, VALID_ACTIONS, ActionResponse
from .state import State, PageContext, PageStructure, PageAnalysis
from .utils.logging import logger
from pydantic import ValidationError

async def analyze_context(state: State) -> Dict[str, Any]:
    """Analyze page context and user intent using LLM"""
    logger.info("Starting analyze_context")
    try:
        # Get user input from messages
        messages = state.get('messages', [])
        if not messages:
            logger.error("No messages in state")
            return {
                "errors": ["No input message found"],
                "next": "error_recovery"
            }
            
        # Get last message content safely
        try:
            last_message = messages[-1]
            if isinstance(last_message, dict):
                user_input = last_message.get('content', '')
            elif hasattr(last_message, 'content'):  # HumanMessage object
                user_input = last_message.content
            else:
                user_input = str(last_message)
        except (IndexError, AttributeError) as e:
            logger.error(f"Error getting message content: {str(e)}")
            return {
                "errors": ["Failed to get message content"],
                "next": "error_recovery"
            }
            
        user_input = str(user_input).lower()
        logger.info(f"Analyzing user input: {user_input}")

        # Prepare prompt for command analysis
        prompt = """Analyze this user command and determine the appropriate action.

        Command: {}

        Rules:
        1. Website Navigation:
           - If the command starts with "go to" AND contains a website name (e.g., "wired.com", "nytimes.com"):
             {{
                 "action": "navigate",
                 "confidence": 0.95,
                 "context": "the website name"
             }}
           - The website name should be extracted exactly as given (e.g., "wired.com" not just "wired")

        2. Other Navigation:
           - If the command starts with "go to" but refers to a section/element:
             {{
                 "action": "goto",
                 "confidence": 0.8,
                 "context": "the section/element name"
             }}

        3. Reading:
           - For reading content:
             {{
                 "action": "read",
                 "confidence": 0.8,
                 "context": "what to read"
             }}

        Available actions:
        - navigate: ONLY for website URLs
        - goto: For sections/elements
        - read: For reading content
        - click: For clicking elements
        - find: For finding specific text
        - list_headings: For listing page structure
        - list_headlines: For news article headlines

        Return a JSON object with these fields:
        - action: One of the available actions
        - confidence: Number between 0 and 1
        - context: Any relevant context (like URL for navigation)
        """.format(user_input)

        # Get LLM analysis
        logger.info("Getting LLM analysis")
        llm_response = await llm.ainvoke([HumanMessage(content=prompt)])
        logger.debug(f"LLM response: {llm_response}")
        
        # Get page structure
        logger.info("Getting page structure")
        soup = BeautifulSoup(state["driver"].page_source, "html.parser")
        page_structure = PageStructure(
            meta={"title": state["driver"].title},
            semantics={
                "main": bool(soup.find("main")),
                "navigation": bool(soup.find("nav")),
                "article": bool(soup.find("article"))
            },
            hierarchy={
                "h1": [h1.text for h1 in soup.find_all("h1")]
            },
            interactive={
                "forms": [{"id": form.get("id")} for form in soup.find_all("form")]
            },
            patterns={
                "code_blocks": len(soup.find_all("code"))
            },
            commerce={"products": [], "cart": None},
            documentation={"code_samples": []},
            social={"posts": []},
            application={"dashboard": None}
        )
        
        # Get page type
        page_type = PageAnalysis(
            type="generic",
            confidence=0.8,
            evidence=[],
            main_sections=[],
            navigation_paths=[],
            interactive_elements=[],
            special_features=[],
            accessibility_score=80,
            assistance_needed=[]
        )
        
        try:
            # Parse LLM response
            if isinstance(llm_response, dict):
                # Already JSON
                parsed_response = llm_response
            else:
                # Extract JSON from text response
                response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
                logger.debug(f"Processing text response: {response_text}")
                
                try:
                    # Attempt to parse entire response as JSON first
                    parsed_response = json.loads(response_text)
                except json.JSONDecodeError:
                    # If that fails, try to extract JSON object from text
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = response_text[start:end]
                        try:
                            parsed_response = json.loads(json_str)
                        except json.JSONDecodeError:
                            raise ValueError("Failed to parse JSON from response")
                    else:
                        raise ValueError("No JSON object found in response")
            
            logger.debug(f"Parsed response: {json.dumps(parsed_response)}")
            
            # Validate response using ActionResponse model
            try:
                validated_response = ActionResponse(
                    action=parsed_response.get("action", "read"),
                    confidence=float(parsed_response.get("confidence", 0.5)),
                    context=parsed_response.get("context", user_input),
                    next_action=parsed_response.get("next_action"),
                    next_context=parsed_response.get("next_context")
                )
                
                # Convert to dict and normalize action
                command_analysis = validated_response.dict()
                if command_analysis["action"] in VALID_ACTIONS:
                    command_analysis["action"] = VALID_ACTIONS[command_analysis["action"]]
                else:
                    logger.error(f"Invalid action: {command_analysis['action']}")
                    command_analysis["action"] = VALID_ACTIONS["read"]
                    command_analysis["confidence"] = 0.5
            except ValidationError as e:
                logger.error(f"Failed to validate response: {str(e)}")
                command_analysis = {
                    "action": VALID_ACTIONS["read"],
                    "confidence": 0.5,
                    "context": user_input
                }
                
            logger.info(f"Command analysis completed: {json.dumps(command_analysis)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            command_analysis = {
                "action": "read",
                "confidence": 0.5,
                "context": user_input
            }


        # Determine suggested actions based on command and content
        suggested_actions = []
        if command_analysis["action"] == "navigate":
            suggested_actions.extend(["read_page", "list_headings"])
        
        # Create page context
        page_context = PageContext(
            type=page_type.type,
            url=state["driver"].current_url,
            title=page_structure.meta["title"],
            has_main=page_structure.semantics["main"],
            has_nav=page_structure.semantics["navigation"],
            has_article=page_structure.semantics["article"],
            has_headlines=bool(page_structure.hierarchy["h1"]),
            has_forms=bool(page_structure.interactive["forms"]),
            dynamic_content=bool(page_structure.patterns["code_blocks"]),
            content_type=page_type.type,
            content_subtype=None,
            scroll_position=0,
            viewport_height=state["driver"].execute_script("return window.innerHeight"),
            total_height=state["driver"].execute_script("return document.documentElement.scrollHeight"),
            structure=page_structure,
            analysis=page_type,
            suggested_actions=suggested_actions,
            navigation_paths=[],
            accessibility_notes=[]
        )
        
        # Log analysis result
        logger.debug("Analyze Context Result:", extra={
            "command_analysis": command_analysis,
            "command_analysis_type": type(command_analysis).__name__
        })
        
        # Return state updates and next step
        return {
            "command_analysis": command_analysis,
            "current_action": command_analysis["action"],
            "action_context": command_analysis["context"],
            "page_context": page_context,
            "next": "execute"
        }
        
    except Exception as e:
        logger.error(f"Error analyzing context: {str(e)}")
        return {
            "errors": [str(e)],
            "next": "error_recovery"
        }

async def prepare_action(state: State) -> Dict[str, Any]:
    """Prepare for action execution, handling setup needs"""
    try:
        # For navigation actions, we don't need existing page context
        if state.get("current_action") == "navigate":
            return {"next": "execute"}

        # For other actions, validate page context
        page_context = state.get("page_context")
        if not isinstance(page_context, PageContext):
            logger.error("Invalid or missing page context")
            return {
                "errors": ["Missing page context"],
                "next": "error_recovery"
            }
            
        # Handle dynamic content
        if page_context.type in ["news", "article"]:
            state["driver"].implicitly_wait(2)
            
        # Get predictions and analysis
        predictions = predict_needed_interactions(state)
        page_analysis = {
            "type": page_context.content_type,
            "dynamic": page_context.dynamic_content,
            "structure_score": page_context.analysis.accessibility_score
        }
        
        # Return state updates and next step
        return {
            "predictions": predictions,
            "page_analysis": page_analysis,
            "next": "execute"
        }
        
    except Exception as e:
        logger.error(f"Error in prepare_action: {str(e)}")
        return {
            "errors": [f"Failed to prepare action: {str(e)}"],
            "next": "error_recovery"
        }

def predict_needed_interactions(state: State) -> Dict[str, Any]:
    """Predict interactions that might be needed based on rich page analysis"""
    predictions = {
        "needs_scroll": False,
        "needs_click": False,
        "needs_wait": False,
        "potential_popups": False,
        "confidence": 0.8,
        "reasoning": []
    }
    
    page_context = state.get("page_context")
    if not isinstance(page_context, PageContext):
        return predictions
    
    # Predict scrolling needs
    if page_context.total_height > page_context.viewport_height * 1.5:
        predictions["needs_scroll"] = True
        predictions["reasoning"].append("Page is longer than viewport")
    
    # Predict clicks based on content type
    if page_context.content_type == "ecommerce":
        if page_context.structure.commerce["products"]:
            predictions["needs_click"] = True
            predictions["reasoning"].append("Product listings likely need interaction")
        if page_context.structure.commerce["cart"]:
            predictions["potential_popups"] = True
            predictions["reasoning"].append("Shopping cart might trigger overlays")
            
    elif page_context.content_type == "documentation":
        if page_context.structure.documentation["code_samples"]:
            predictions["needs_click"] = True
            predictions["reasoning"].append("Code samples might have copy buttons")
            
    elif page_context.content_type == "social":
        if page_context.structure.social["posts"]:
            predictions["needs_scroll"] = True
            predictions["needs_wait"] = True
            predictions["reasoning"].extend(["Social feed might load dynamically", "Content likely continues on scroll"])
            
    elif page_context.content_type == "application":
        if page_context.structure.application["dashboard"]:
            predictions["needs_wait"] = True
            predictions["reasoning"].append("Dashboard might load data dynamically")
    
    # General predictions
    # Check for forms
    if page_context.structure.interactive["forms"]:
        predictions["needs_click"] = True
        predictions["reasoning"].append("Form elements require interaction")
        
    if page_context.structure.patterns["code_blocks"] > 0:
        predictions["needs_wait"] = True
        predictions["reasoning"].append("Dynamic content might need loading time")
        
    if page_context.analysis.accessibility_score < 70:
        predictions["needs_wait"] = True
        predictions["reasoning"].append("Poor accessibility might need extra processing time")
    
    # Adjust confidence based on evidence
    evidence_count = len(predictions["reasoning"])
    if evidence_count > 3:
        predictions["confidence"] = 0.9
    elif evidence_count > 1:
        predictions["confidence"] = 0.8
    else:
        predictions["confidence"] = 0.7
    
    return predictions

def build_task_dependencies(tasks: List[str]) -> Dict[str, List[str]]:
    """Build dependency graph for tasks"""
    dependencies = {}
    for i, task in enumerate(tasks):
        # Simple sequential dependencies for now
        dependencies[task] = [tasks[i-1]] if i > 0 else []
    return dependencies
