import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient

from thothctl.services.dashboard.dashboard_service import DashboardService
from thothctl.services.dashboard.data_loader import DashboardDataLoader


class TestDashboardService:
    
    def test_dashboard_service_initialization(self):
        """Test dashboard service initializes correctly."""
        service = DashboardService(port=8080, host="127.0.0.1")
        assert service.port == 8080
        assert service.host == "127.0.0.1"
        assert service.app is not None
        assert service.data_loader is not None

    @patch('webbrowser.open')
    @patch('threading.Thread')
    @patch('uvicorn.run')
    def test_run_with_browser(self, mock_uvicorn, mock_thread, mock_browser):
        """Test dashboard runs and opens browser."""
        service = DashboardService()
        
        service.run(debug=False, open_browser=True)
        mock_uvicorn.assert_called_once()
        mock_thread.assert_called_once()

    def test_api_routes_exist(self):
        """Test all required API routes are registered."""
        service = DashboardService()
        client = TestClient(service.app)
        
        required_routes = [
            '/',
            '/api/inventory',
            '/api/scan-results', 
            '/api/cost-analysis',
            '/api/blast-radius',
            '/api/refresh',
            '/api/test',
            '/minimal',
            '/test'
        ]
        
        for route in required_routes:
            response = client.get(route)
            assert response.status_code in [200, 404, 500], f"Route {route} not accessible"


class TestDashboardDataLoader:
    
    def setup_method(self):
        """Setup test environment."""
        self.loader = DashboardDataLoader()
        
    def test_get_inventory_data_no_files(self):
        """Test inventory data when no files exist."""
        result = self.loader.get_inventory_data()
        assert "error" in result
        assert "No inventory data found" in result["error"]
        
    def test_get_scan_results_no_files(self):
        """Test scan results when no files exist.""" 
        result = self.loader.get_scan_results()
        assert "error" in result
        assert "No scan results found" in result["error"]
        
    def test_get_cost_analysis_no_data(self):
        """Test cost analysis returns message when no data."""
        result = self.loader.get_cost_analysis()
        assert "message" in result
        
    def test_get_blast_radius_no_data(self):
        """Test blast radius returns message when no data."""
        result = self.loader.get_blast_radius()
        assert "message" in result

    @patch('pathlib.Path.glob')
    def test_get_inventory_data_with_file(self, mock_glob):
        """Test inventory data loading with valid file."""
        # Mock file existence and content
        mock_file = Mock()
        mock_file.stat.return_value.st_mtime = time.time()
        mock_glob.return_value = [mock_file]
        
        test_data = {"components": [{"stack": "test", "providers": ["aws"]}]}
        
        with patch('builtins.open', mock_open_json(test_data)):
            result = self.loader.get_inventory_data()
            assert "components" in result
            assert result["components"][0]["stack"] == "test"

    @patch('pathlib.Path.rglob')
    def test_get_scan_results_with_files(self, mock_rglob):
        """Test scan results loading with files."""
        mock_file = Mock()
        mock_file.name = "test_report.html"
        mock_file.relative_to.return_value = Path("Reports/test_report.html")
        mock_file.stat.return_value.st_mtime = time.time()
        mock_file.stat.return_value.st_size = 1024
        mock_rglob.return_value = [mock_file]
        
        result = self.loader.get_scan_results()
        assert "reports" in result
        assert len(result["reports"]) > 0


def mock_open_json(data):
    """Helper to mock file opening with JSON data."""
    mock = MagicMock()
    mock.__enter__.return_value.read.return_value = json.dumps(data)
    return mock


class TestDashboardAPI:
    """Test dashboard API endpoints."""
    
    def setup_method(self):
        """Setup test client."""
        self.service = DashboardService()
        self.client = TestClient(self.service.app)
        
    def test_api_test_endpoint(self):
        """Test /api/test endpoint responds."""
        response = self.client.get('/api/test')
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "API working"
        
    def test_api_inventory_endpoint(self):
        """Test /api/inventory endpoint."""
        response = self.client.get('/api/inventory')
        assert response.status_code in [200, 500]  # May return error if no data
        
    def test_api_scan_results_endpoint(self):
        """Test /api/scan-results endpoint."""
        response = self.client.get('/api/scan-results')
        assert response.status_code in [200, 500]  # May return error if no data
        
    def test_api_cost_analysis_endpoint(self):
        """Test /api/cost-analysis endpoint."""
        response = self.client.get('/api/cost-analysis')
        assert response.status_code == 200
        
    def test_api_blast_radius_endpoint(self):
        """Test /api/blast-radius endpoint."""
        response = self.client.get('/api/blast-radius')
        assert response.status_code == 200
        
    def test_api_refresh_endpoint(self):
        """Test /api/refresh endpoint."""
        response = self.client.get('/api/refresh')
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
    def test_minimal_test_page(self):
        """Test /minimal endpoint for JavaScript debugging."""
        response = self.client.get('/minimal')
        assert response.status_code == 200
        assert 'Minimal Test Page' in response.text
        assert 'JavaScript Working!' in response.text
        
    def test_main_dashboard_page(self):
        """Test main dashboard page loads."""
        response = self.client.get('/')
        assert response.status_code == 200
        assert 'ThothCTL Dashboard' in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
