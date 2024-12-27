"""Enhanced logging system with structured logging and context tracking"""

import logging
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager

@dataclass
class LogContext:
    """Context information for logging"""
    action: str
    state_id: str
    timestamp: float
    duration: Optional[float] = None
    predictions: Optional[Dict[str, Any]] = None
    page_context: Optional[Dict[str, Any]] = None
    element_context: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    input: Optional[str] = None

class StructuredLogger:
    """Enhanced logger with context tracking and structured output"""
    
    def __init__(self, name: str):
        self.name = name
        self.context_stack: List[LogContext] = []
        self._setup_logging()
        
    def _setup_logging(self) -> None:
        """Configure logging with specialized handlers"""
        # Create logs directory structure
        os.makedirs('logs/actions', exist_ok=True)
        os.makedirs('logs/predictions', exist_ok=True)
        os.makedirs('logs/performance', exist_ok=True)
        os.makedirs('logs/errors', exist_ok=True)
        
        # Create base logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        
        # JSON formatter for structured logging
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage()
                }
                
                # Add context if available
                if hasattr(record, 'context'):
                    # Convert dataclass objects to dictionaries
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dataclass_fields__'):
                                context[key] = asdict(value)
                            elif hasattr(value, '__dict__'):
                                context[key] = value.__dict__
                    log_data['context'] = context
                    
                return json.dumps(log_data)
        
        # Specialized formatters
        class ActionFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dataclass_fields__'):
                                context[key] = asdict(value)
                            elif hasattr(value, '__dict__'):
                                context[key] = value.__dict__
                    action_data = {
                        "timestamp": self.formatTime(record),
                        "action": context.get("action"),
                        "duration": context.get("duration"),
                        "state_id": context.get("state_id")
                    }
                    return json.dumps(action_data)
                return super().format(record)

        class PredictionFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dataclass_fields__'):
                                context[key] = asdict(value)
                            elif hasattr(value, '__dict__'):
                                context[key] = value.__dict__
                    pred_data = {
                        "timestamp": self.formatTime(record),
                        "action": context.get("action"),
                        "predictions": context.get("predictions")
                    }
                    return json.dumps(pred_data)
                return super().format(record)

        class PerformanceFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dict__'):
                                context[key] = asdict(value)
                    perf_data = {
                        "timestamp": self.formatTime(record),
                        "action": context.get("action"),
                        "duration": context.get("duration")
                    }
                    return json.dumps(perf_data)
                return super().format(record)

        class ErrorFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, 'context'):
                    context = record.context
                    if isinstance(context, dict):
                        for key, value in context.items():
                            if hasattr(value, '__dict__'):
                                context[key] = asdict(value)
                    error_data = {
                        "timestamp": self.formatTime(record),
                        "error_message": context.get("error_message"),
                        "action": context.get("action_context", {}).get("action")
                    }
                    return json.dumps(error_data)
                return super().format(record)

        # Configure handlers with specialized formatters
        handlers = [
            # Main debug log - keeps full context
            (logging.FileHandler('logs/debug.log', mode='w', encoding='utf-8'),
             logging.DEBUG,
             JsonFormatter()),
             
            # Action tracking - minimal context
            (logging.FileHandler('logs/actions/actions.log', mode='w', encoding='utf-8'),
             logging.INFO,
             ActionFormatter()),
             
            # Prediction monitoring - predictions only
            (logging.FileHandler('logs/predictions/predictions.log', mode='w', encoding='utf-8'),
             logging.DEBUG,
             PredictionFormatter()),
             
            # Performance metrics - timing only
            (logging.FileHandler('logs/performance/performance.log', mode='w', encoding='utf-8'),
             logging.INFO,
             PerformanceFormatter()),
             
            # Error tracking - error context only
            (logging.FileHandler('logs/errors/errors.log', mode='w', encoding='utf-8'),
             logging.ERROR,
             ErrorFormatter()),
             
            # Console output (human readable)
            (logging.StreamHandler(),
             logging.INFO,
             logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S'))
        ]
        
        for handler, level, formatter in handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    @contextmanager
    def action_context(self, action: str, state_id: str, **kwargs):
        """Context manager for tracking action execution"""
        context = LogContext(
            action=action,
            state_id=state_id,
            timestamp=time.time(),
            **kwargs
        )
        self.context_stack.append(context)
        
        try:
            yield context
        except Exception:
            # Don't log errors in context manager
            raise
        else:
            context.duration = time.time() - context.timestamp
            self._log_action_complete(context)
        finally:
            self.context_stack.pop()
    
    def _log_action_complete(self, context: LogContext) -> None:
        """Log action completion with metrics"""
        log_data = asdict(context)
        
        # Log action completion
        self.logger.info(
            f"Action complete: {context.action}",
            extra={"context": log_data}
        )
        
        # Log performance metrics
        if context.duration is not None:
            self.logger.info(
                f"Performance metrics for {context.action}",
                extra={
                    "context": {
                        "action": context.action,
                        "duration": context.duration,
                        "timestamp": context.timestamp
                    }
                }
            )
        
        # Log prediction accuracy if available
        if context.predictions:
            self.logger.debug(
                f"Prediction analysis for {context.action}",
                extra={
                    "context": {
                        "action": context.action,
                        "predictions": context.predictions
                    }
                }
            )
    
    def log_state_transition(self, from_state: str, to_state: str, context: Dict[str, Any]) -> None:
        """Log state transitions with context"""
        self.logger.info(
            f"State transition: {from_state} -> {to_state}",
            extra={"context": context}
        )
    
    def log_prediction(self, prediction: Dict[str, Any], actual: Dict[str, Any]) -> None:
        """Log and analyze prediction accuracy"""
        self.logger.debug(
            "Prediction analysis",
            extra={
                "context": {
                    "prediction": prediction,
                    "actual": actual,
                    "timestamp": time.time()
                }
            }
        )
    
    def log_error(self, error: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log errors with rich context"""
        current_context = self.context_stack[-1] if self.context_stack else None
        
        error_context = {
            "error_message": error,
            "timestamp": time.time(),
            "action_context": asdict(current_context) if current_context else None,
            "additional_context": context
        }
        
        # Log to error file with context
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler) and 'errors.log' in handler.baseFilename:
                handler.emit(
                    self.logger.makeRecord(
                        self.name,
                        logging.ERROR,
                        "(unknown file)", 0,
                        error,
                        None, None,
                        extra={"context": error_context}
                    )
                )
        
        # Log to console without context to avoid exc_info conflict
        self.logger.error(f"Error: {error}")
    
    def debug(self, msg: str, **kwargs) -> None:
        self.logger.debug(msg, extra=kwargs)
    
    def info(self, msg: str, **kwargs) -> None:
        self.logger.info(msg, extra=kwargs)
    
    def warning(self, msg: str, **kwargs) -> None:
        self.logger.warning(msg, extra=kwargs)
    
    def error(self, msg: str, **kwargs) -> None:
        self.logger.error(msg, extra=kwargs)
    
    def critical(self, msg: str, **kwargs) -> None:
        self.logger.critical(msg, extra=kwargs)

# Create and configure the enhanced logger
logger = StructuredLogger('screen_reader')
