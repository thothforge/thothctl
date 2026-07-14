import pytest
import time
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from thothctl.services.dashboard.dashboard_service import DashboardService


class TestDashboardLoadingFix:
    """Test dashboard loading and error handling."""

    def setup_method(self):
        """Setup test client."""
        self.service = DashboardService()
        self.client = TestClient(self.service.app)

    def test_dashboard_html_contains_timeout_protection(self):
        """Test that dashboard HTML contains timeout/async loading protection."""
        response = self.client.get('/')
        html_content = response.text

        # Check for timeout protection in JavaScript
        assert 'setTimeout' in html_content

    def test_dashboard_html_contains_error_boundaries(self):
        """Test that dashboard HTML contains proper error boundaries."""
        response = self.client.get('/')
        html_content = response.text

        # Check for error handling
        assert 'try {' in html_content
        assert 'catch' in html_content

    def test_dashboard_html_contains_async_loading(self):
        """Test that dashboard uses async data loading."""
        response = self.client.get('/')
        html_content = response.text

        # Check for async data fetching
        assert 'fetch' in html_content
        assert 'async' in html_content

    def test_api_endpoints_respond_quickly(self):
        """Test that API endpoints respond within reasonable time."""
        endpoints = ['/api/inventory', '/api/scan-results',
                     '/api/cost-analysis', '/api/blast-radius', '/api/refresh']

        for endpoint in endpoints:
            start_time = time.time()
            response = self.client.get(endpoint)
            end_time = time.time()

            # Should respond within 2 seconds
            assert (end_time - start_time) < 2.0, f"Endpoint {endpoint} took too long"
            assert response.status_code in [200, 500]  # Either success or controlled error

    def test_api_test_endpoint(self):
        """Test that /api/test endpoint responds correctly."""
        response = self.client.get('/api/test')
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @patch('thothctl.services.dashboard.data_loader.DashboardDataLoader.get_inventory_data')
    def test_dashboard_handles_slow_api(self, mock_inventory):
        """Test dashboard handles slow API responses gracefully."""
        # Mock slow response
        def slow_response():
            time.sleep(0.5)
            return {"error": "Slow response"}

        mock_inventory.side_effect = slow_response

        # API should still respond
        response = self.client.get('/api/inventory')
        assert response.status_code in [200, 500]

    def test_dashboard_javascript_syntax_valid(self):
        """Test that dashboard JavaScript has valid syntax (balanced brackets)."""
        response = self.client.get('/')
        html_content = response.text

        # Find all script blocks and check bracket balance
        import re
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html_content, re.DOTALL)

        for script in scripts:
            if len(script) > 50:  # Only check substantial scripts
                assert script.count('{') == script.count('}'), "Unbalanced curly braces in JS"
                assert script.count('(') == script.count(')'), "Unbalanced parentheses in JS"
                assert script.count('[') == script.count(']'), "Unbalanced square brackets in JS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
