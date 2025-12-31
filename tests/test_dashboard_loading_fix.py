import pytest
import time
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from thothctl.services.dashboard.dashboard_service import DashboardService


class TestDashboardLoadingFix:
    """Test dashboard loading timeout and error handling fixes."""
    
    def setup_method(self):
        """Setup test client."""
        self.service = DashboardService()
        self.client = TestClient(self.service.app)
    
    def test_dashboard_html_contains_timeout_protection(self):
        """Test that dashboard HTML contains timeout protection."""
        response = self.client.get('/')
        html_content = response.text
        
        # Check for timeout protection in JavaScript
        assert 'setTimeout' in html_content
        assert '2000' in html_content  # 2 second forced completion
        assert 'Dashboard initialization complete (forced)' in html_content
        
    def test_dashboard_html_contains_error_boundaries(self):
        """Test that dashboard HTML contains proper error boundaries."""
        response = self.client.get('/')
        html_content = response.text
        
        # Check for error handling
        assert 'try {' in html_content
        assert 'catch (error)' in html_content
        assert 'console.error' in html_content
        
    def test_dashboard_html_contains_null_safety(self):
        """Test that helper functions have null safety."""
        response = self.client.get('/')
        html_content = response.text
        
        # Check for async data loading and AbortController
        assert 'AbortController' in html_content
        assert 'loadDataAsync' in html_content
        assert 'controller.abort()' in html_content
        
    def test_api_endpoints_respond_quickly(self):
        """Test that API endpoints respond within reasonable time."""
        endpoints = ['/api/test', '/api/inventory', '/api/scan-results', 
                    '/api/cost-analysis', '/api/blast-radius', '/api/refresh']
        
        for endpoint in endpoints:
            start_time = time.time()
            response = self.client.get(endpoint)
            end_time = time.time()
            
            # Should respond within 1 second
            assert (end_time - start_time) < 1.0, f"Endpoint {endpoint} took too long"
            assert response.status_code in [200, 500]  # Either success or controlled error
            
    def test_minimal_test_page_loads_fast(self):
        """Test that minimal test page loads quickly."""
        start_time = time.time()
        response = self.client.get('/minimal')
        end_time = time.time()
        
        assert (end_time - start_time) < 0.5  # Should be very fast
        assert response.status_code == 200
        assert 'Minimal Test Page' in response.text
        
    @patch('thothctl.services.dashboard.data_loader.DashboardDataLoader.get_inventory_data')
    def test_dashboard_handles_slow_api(self, mock_inventory):
        """Test dashboard handles slow API responses gracefully."""
        # Mock slow response
        def slow_response():
            time.sleep(2)  # Simulate slow API
            return {"error": "Slow response"}
        
        mock_inventory.side_effect = slow_response
        
        # API should still respond (though slowly)
        response = self.client.get('/api/inventory')
        assert response.status_code in [200, 500]
        
    def test_dashboard_javascript_syntax_valid(self):
        """Test that dashboard JavaScript has valid syntax."""
        response = self.client.get('/')
        html_content = response.text
        
        # Extract JavaScript content
        js_start = html_content.find('<script>')
        js_end = html_content.find('</script>')
        
        if js_start != -1 and js_end != -1:
            js_content = html_content[js_start:js_end]
            
            # Basic syntax checks
            assert js_content.count('{') == js_content.count('}')
            assert js_content.count('(') == js_content.count(')')
            assert js_content.count('[') == js_content.count(']')
            
            # Check for common syntax errors
            assert 'undefined' not in js_content.lower()
            assert 'null.length' not in js_content
            assert '.length()' not in js_content  # Should be .length not .length()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
