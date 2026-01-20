import os
import logging
import webbrowser
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

from thothctl.services.dashboard.data_loader import DashboardDataLoader
from thothctl.version import __version__

logger = logging.getLogger(__name__)

class DashboardService:
    """Service for managing the ThothCTL dashboard web application."""
    
    def __init__(self, port: int = 8080, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.app = FastAPI(title="ThothCTL Dashboard", version=__version__)
        self.data_loader = DashboardDataLoader()
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes for the dashboard."""
        
        @self.app.get("/minimal", response_class=HTMLResponse)
        async def minimal_test():
            """Minimal test page to isolate JavaScript issues."""
            return '''<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <h1>Minimal Test Page</h1>
    <div id="test">Loading...</div>
    <script>
        console.log('Script started');
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM loaded');
            document.getElementById('test').innerHTML = 'JavaScript Working!';
        });
        console.log('Script ended');
    </script>
</body>
</html>'''
        
        @self.app.get("/debug", response_class=HTMLResponse)
        async def debug_page():
            """Debug test page."""
            try:
                with open('/home/labvel/projects/tools/ThothForge/thothctl/debug_dashboard.html') as f:
                    return f.read()
            except FileNotFoundError:
                return "<html><body><h1>Debug file not found</h1></body></html>"
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Main dashboard page."""
            return self._get_dashboard_template()
        
        @self.app.get("/api/test")
        async def api_test():
            return {"status": "API working", "time": time.time()}
        
        @self.app.get("/api/inventory")
        async def api_inventory():
            """API endpoint for inventory data."""
            logger.info("Inventory API called")
            try:
                result = self.data_loader.get_inventory_data()
                logger.info(f"Inventory result: {type(result)}")
                return result
            except Exception as e:
                logger.error(f"Inventory API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/scan-results")
        async def api_scan_results():
            """API endpoint for scan results."""
            logger.info("Scan results API called")
            try:
                result = self.data_loader.get_scan_results()
                logger.info(f"Scan results result: {type(result)}")
                return result
            except Exception as e:
                logger.error(f"Scan results API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/cost-analysis")
        async def api_cost_analysis():
            """API endpoint for cost analysis."""
            logger.info("Cost analysis API called")
            try:
                result = self.data_loader.get_cost_analysis()
                logger.info(f"Cost analysis result: {type(result)}")
                return result
            except Exception as e:
                logger.error(f"Cost analysis API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/blast-radius")
        async def api_blast_radius():
            """API endpoint for blast radius analysis."""
            logger.info("Blast radius API called")
            try:
                result = self.data_loader.get_blast_radius()
                logger.info(f"Blast radius result: {type(result)}")
                return result
            except Exception as e:
                logger.error(f"Blast radius API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/refresh")
        async def api_refresh():
            """API endpoint to refresh all data."""
            logger.info("Refresh API called")
            try:
                self.data_loader.cache.clear()
                return {"status": "success", "message": "Data refreshed"}
            except Exception as e:
                logger.error(f"Refresh API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def _get_dashboard_template(self) -> str:
        """Get the dashboard HTML template."""
        template_path = Path(__file__).parent.parent.parent / "utils" / "common" / "templates" / "dashboard.html"
        
        try:
            with open(template_path) as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Dashboard template not found: {template_path}")
            return "<html><body><h1>Dashboard template missing</h1></body></html>"
    
    def run(self, debug: bool = False, open_browser: bool = True):
        """Run the dashboard web application."""
        try:
            # Display professional banner
            self._display_banner(debug)
            
            if open_browser:
                def open_browser_delayed():
                    time.sleep(1.5)
                    webbrowser.open(f'http://{self.host}:{self.port}')
                
                threading.Thread(target=open_browser_delayed, daemon=True).start()
            
            # Run FastAPI with uvicorn
            uvicorn.run(
                self.app, 
                host=self.host, 
                port=self.port, 
                log_level="info" if debug else "warning",
                access_log=debug
            )
        except Exception as e:
            logger.error(f"Error starting dashboard: {e}")
            raise
    
    def _display_banner(self, debug: bool = False):
        """Display professional ThothCTL banner."""
        from ...utils.banner import get_banner
        
        mode = "DEBUG" if debug else "PRODUCTION"
        mode_color = "\033[93m" if debug else "\033[92m"  # Yellow for debug, Green for prod
        reset_color = "\033[0m"
        cyan = "\033[96m"
        bold = "\033[1m"
        
        banner = f"""{get_banner()}
   
   🚀 {bold}Dashboard v{__version__}{reset_color} - {mode_color}{mode} Mode{reset_color}
   🌐 URL: {cyan}http://{self.host}:{self.port}{reset_color}

{bold}{cyan}🎯 Dashboard Features:{reset_color}
   • 📦 Infrastructure Inventory (SBOM) with version tracking
   • 🔒 Security scan results from Checkov, Trivy & more  
   • 💰 AWS cost analysis with optimization recommendations
   • ⚠️  Blast radius assessment for change impact analysis
   • 🌙 Dark mode, export options & responsive design

{bold}{mode_color}⚡ {mode} Mode Active{reset_color} - {'Enhanced debugging & hot reload enabled' if debug else 'Optimized for production performance'}
"""
        
        print(banner)
        logger.info(f"ThothCTL Dashboard starting on http://{self.host}:{self.port} ({mode} mode)")
