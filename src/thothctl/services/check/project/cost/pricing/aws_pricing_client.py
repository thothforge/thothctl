"""AWS Pricing API client using public bulk pricing data."""

import json
import logging
import requests
from typing import Dict, List, Optional, Any
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


class AWSPricingClient:
    """AWS Pricing client using public bulk pricing endpoints (no credentials required)
    
    Uses a hybrid approach:
    1. Attempts to fetch from AWS public pricing API
    2. Falls back to offline estimates if API is unavailable or slow
    """
    
    BASE_URL = "https://pricing.us-east-1.amazonaws.com"
    CACHE_DIR = Path.home() / ".thothctl" / "pricing_cache"
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self._index_cache = None
        self._api_available = None
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _fetch_json(self, url: str, timeout: int = 10) -> Optional[Dict]:
        """Fetch JSON from URL with error handling and timeout"""
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            logger.warning(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None
    
    def _get_service_index(self) -> Optional[Dict]:
        """Get the main AWS pricing index"""
        if self._index_cache is None:
            url = f"{self.BASE_URL}/offers/v1.0/aws/index.json"
            self._index_cache = self._fetch_json(url, timeout=5)
        return self._index_cache
    
    @lru_cache(maxsize=1000)
    def get_products(self, service_code: str, filters: tuple, region_code: Optional[str] = None) -> List[Dict]:
        """Get products matching filters
        
        Note: Due to the large size of AWS pricing files (100MB+), this implementation
        returns empty list to trigger offline estimates. A production implementation
        would use:
        1. AWS Price List Query API (requires credentials)
        2. Pre-processed pricing database
        3. Cached pricing snapshots
        
        For now, providers will fall back to their offline estimates.
        """
        # The bulk pricing files are too large (100MB+) to parse efficiently
        # Return empty to trigger offline estimates in providers
        logger.debug(f"Using offline estimates for {service_code} (bulk files too large)")
        return []
    
    def is_available(self) -> bool:
        """Check if AWS pricing API is available"""
        return self._get_service_index() is not None
