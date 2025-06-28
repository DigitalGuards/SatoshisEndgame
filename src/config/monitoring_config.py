"""
Monitoring configuration for API limit management
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class MonitoringTier(BaseModel):
    """Configuration for a monitoring tier"""
    name: str
    risk_score_min: float
    risk_score_max: Optional[float] = None
    max_addresses: int
    check_interval_minutes: int
    

class APILimits(BaseModel):
    """API rate limits"""
    requests_per_day: int
    requests_per_hour: int
    requests_per_second: float


class MonitoringStrategy(BaseModel):
    """Complete monitoring strategy configuration"""
    name: str = "tiered_risk_based"
    api_limits: APILimits = APILimits(
        requests_per_day=1000,
        requests_per_hour=100,
        requests_per_second=3
    )
    monitoring_tiers: List[MonitoringTier] = [
        MonitoringTier(
            name="critical",
            risk_score_min=95,
            max_addresses=50,
            check_interval_minutes=60  # Every hour
        ),
        MonitoringTier(
            name="high",
            risk_score_min=80,
            risk_score_max=94,
            max_addresses=200,
            check_interval_minutes=240  # Every 4 hours
        ),
        MonitoringTier(
            name="medium", 
            risk_score_min=60,
            risk_score_max=79,
            max_addresses=600,
            check_interval_minutes=1440  # Once daily
        )
    ]
    
    def get_tier_for_score(self, risk_score: float) -> Optional[MonitoringTier]:
        """Get the appropriate tier for a risk score"""
        for tier in self.monitoring_tiers:
            if risk_score >= tier.risk_score_min:
                if tier.risk_score_max is None or risk_score <= tier.risk_score_max:
                    return tier
        return None
    
    def calculate_daily_requests(self) -> int:
        """Calculate total daily API requests"""
        total = 0
        for tier in self.monitoring_tiers:
            checks_per_day = (24 * 60) / tier.check_interval_minutes
            total += tier.max_addresses * checks_per_day
        return int(total)
    
    def is_within_limits(self) -> bool:
        """Check if strategy is within API limits"""
        return self.calculate_daily_requests() <= self.api_limits.requests_per_day


# Default monitoring strategy
default_strategy = MonitoringStrategy()