"""Web Reader - A natural language screen reader for web content"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from . import actions
from . import utils
from . import browser
from . import config
from . import state

__all__ = ["actions", "utils", "browser", "config", "state"]
