"""Test navigation and content reading across different types of websites"""

import unittest
import json
import logging
from typing import Dict, Any
from selenium.common.exceptions import WebDriverException

from .command import determine_command, execute_command, setup_browser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestWebNavigation(unittest.TestCase):
    """Test suite for web navigation and content reading"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize browser for all tests"""
        cls.driver = setup_browser()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up browser after all tests"""
        cls.driver.quit()
        
    def execute_and_verify(self, command: str) -> Dict[str, Any]:
        """Helper to execute command and verify response"""
        action = determine_command(command)
        self.assertGreater(action.confidence, 0.7, "Low confidence in command determination")
        result = execute_command(action, self.driver)
        self.assertEqual(result["status"], "success", "Command execution failed")
        return result
        
    def test_news_site_navigation(self):
        """Test navigation and reading on a news site"""
        logger.info("Testing news site navigation")
        
        # Navigate to site
        result = self.execute_and_verify("go to news.ycombinator.com")
        self.assertIn("Hacker News", result["title"])
        
        # Read content
        result = self.execute_and_verify("read the page")
        self.assertIn("content", result)
        self.assertTrue(len(result["content"]["headlines"]) > 0)
        
    def test_search_site_navigation(self):
        """Test navigation and reading on a search engine"""
        logger.info("Testing search site navigation")
        
        # Navigate to site
        result = self.execute_and_verify("visit duckduckgo.com")
        self.assertIn("DuckDuckGo", result["title"])
        
        # Read content
        result = self.execute_and_verify("read this page")
        self.assertIn("content", result)
        
    def test_docs_site_navigation(self):
        """Test navigation and reading on a documentation site"""
        logger.info("Testing documentation site navigation")
        
        # Navigate to site
        result = self.execute_and_verify("go to docs.python.org")
        self.assertIn("Documentation", result["title"])  # Python docs title contains "Documentation"
        
        # Read content
        result = self.execute_and_verify("read the current page")
        self.assertIn("content", result)
        self.assertTrue(len(result["content"]["sections"]) > 0)
        
    def test_invalid_navigation(self):
        """Test handling of invalid URLs"""
        logger.info("Testing invalid URL handling")
        
        # First verify we get a navigate command even for invalid URLs
        action = determine_command("go to invalid.nonexistent.url")
        self.assertEqual(action.action, "navigate")
        self.assertEqual(action.context, "invalid.nonexistent.url")
        
        # Then verify it raises WebDriverException when executed
        with self.assertRaises(WebDriverException):
            execute_command(action, self.driver)
            
    def test_complex_navigation_sequence(self):
        """Test a sequence of navigation and reading commands"""
        logger.info("Testing complex navigation sequence")
        
        # Start with Wikipedia
        result = self.execute_and_verify("navigate to wikipedia.org")
        self.assertIn("Wikipedia", result["title"])
        
        # Read the page
        result = self.execute_and_verify("read this page")
        self.assertIn("content", result)
        
        # Go to Python docs
        result = self.execute_and_verify("visit docs.python.org")
        self.assertIn("Documentation", result["title"])  # Python docs title contains "Documentation"
        
        # Read again
        result = self.execute_and_verify("read the page")
        self.assertIn("content", result)
        self.assertTrue(len(result["content"]["sections"]) > 0)

def run_tests():
    """Run test suite with detailed logging"""
    logger.info("Starting navigation tests")
    try:
        unittest.main(argv=[''], verbosity=2, exit=False)
    except Exception as e:
        logger.error(f"Test execution failed: {str(e)}")
    logger.info("Navigation tests completed")

if __name__ == "__main__":
    run_tests()
