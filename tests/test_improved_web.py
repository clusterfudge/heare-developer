import unittest
from unittest.mock import MagicMock, patch

from heare.developer.tools.improved_web import safe_fetch_headless


class TestImprovedWeb(unittest.TestCase):
    
    @patch("heare.developer.tools.improved_web.sync_playwright")
    @patch("heare.developer.tools.improved_web._call_anthropic_with_retry")
    def test_safe_fetch_headless_with_js(self, mock_anthropic, mock_playwright):
        # Mock context
        mock_context = MagicMock()
        
        # Setup mock for playwright
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body><div>Test content</div></body></html>"
        
        mock_browser_context = MagicMock()
        mock_browser_context.new_page.return_value = mock_page
        
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_browser_context
        
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        
        mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
        
        # Setup mock for Anthropic API response
        mock_message = MagicMock()
        mock_message.content = [MagicMock()]
        mock_message.content[0].text = "safe"
        mock_anthropic.return_value = mock_message
        
        # Call the function
        result = safe_fetch_headless(mock_context, "https://example.com", render_js=True)
        
        # Assertions
        mock_playwright.assert_called_once()
        mock_page.goto.assert_called_once_with("https://example.com")
        mock_page.wait_for_load_state.assert_called_once_with("networkidle")
        mock_page.content.assert_called_once()
        mock_anthropic.assert_called_once()
        
        # Should contain the converted markdown content
        self.assertIn("Test content", result)
    
    @patch("httpx.Client")
    @patch("heare.developer.tools.improved_web._call_anthropic_with_retry")
    def test_safe_fetch_headless_without_js(self, mock_anthropic, mock_httpx):
        # Mock context
        mock_context = MagicMock()
        
        # Setup mock for httpx
        mock_response = MagicMock()
        mock_response.text = "<html><body><div>Test content without JS</div></body></html>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_httpx.return_value = mock_client
        
        # Setup mock for Anthropic API response
        mock_message = MagicMock()
        mock_message.content = [MagicMock()]
        mock_message.content[0].text = "safe"
        mock_anthropic.return_value = mock_message
        
        # Call the function
        result = safe_fetch_headless(mock_context, "https://example.com", render_js=False)
        
        # Assertions
        mock_httpx.assert_called_once()
        mock_client.__enter__.return_value.get.assert_called_once_with("https://example.com")
        mock_anthropic.assert_called_once()
        
        # Should contain the converted markdown content
        self.assertIn("Test content without JS", result)
    
    @patch("heare.developer.tools.improved_web.sync_playwright")
    @patch("heare.developer.tools.improved_web._call_anthropic_with_retry")
    def test_safe_fetch_headless_content_only(self, mock_anthropic, mock_playwright):
        # Mock context
        mock_context = MagicMock()
        
        # Setup mock for playwright
        mock_page = MagicMock()
        mock_page.content.return_value = """
        <html>
            <body>
                <header>Header content</header>
                <nav>Navigation</nav>
                <main>
                    <article>Main article content</article>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        
        mock_browser_context = MagicMock()
        mock_browser_context.new_page.return_value = mock_page
        
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_browser_context
        
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        
        mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
        
        # Setup mock for Anthropic API responses
        mock_safety_message = MagicMock()
        mock_safety_message.content = [MagicMock()]
        mock_safety_message.content[0].text = "safe"
        
        mock_content_message = MagicMock()
        mock_content_message.content = [MagicMock()]
        mock_content_message.content[0].text = "Main article content"
        
        # Configure the mock to return different values for different calls
        mock_anthropic.side_effect = [mock_safety_message, mock_content_message]
        
        # Call the function
        result = safe_fetch_headless(mock_context, "https://example.com", content_only=True)
        
        # Check that the result contains only the main content
        self.assertEqual(result, "Main article content")


if __name__ == "__main__":
    unittest.main()