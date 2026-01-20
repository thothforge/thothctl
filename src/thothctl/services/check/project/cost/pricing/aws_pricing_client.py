"""AWS Pricing API client with caching."""

import json
import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache

logger = logging.getLogger(__name__)


class AWSPricingClient:
    """Centralized AWS Pricing API client with caching"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of boto3 client
        
        Note: AWS Pricing API requires valid AWS credentials even though
        it's a read-only public API. Configure credentials via:
        - AWS CLI: aws configure
        - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
        - IAM role (for EC2/Lambda)
        """
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('pricing', region_name='us-east-1')
            except Exception as e:
                logger.warning(f"Failed to initialize AWS pricing client: {e}")
                logger.info("AWS Pricing API requires credentials. Configure with: aws configure")
                raise
        return self._client
    
    @lru_cache(maxsize=1000)
    def get_products(self, service_code: str, filters: tuple) -> List[Dict]:
        """Get products with caching"""
        try:
            response = self.client.get_products(
                ServiceCode=service_code,
                Filters=list(filters)
            )
            return [json.loads(price) for price in response['PriceList']]
        except Exception as e:
            logger.error(f"Failed to get products for {service_code}: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if AWS pricing API is available"""
        try:
            self.client.describe_services(MaxResults=1)
            return True
        except Exception:
            return False
