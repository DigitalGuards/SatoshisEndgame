import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field

import structlog

from src.config import settings
from src.data.models import Transaction, Wallet

logger = structlog.get_logger()


@dataclass
class EmergencyPattern:
    """Detected emergency pattern"""
    pattern_type: str
    severity: str
    confidence: float
    affected_wallets: List[str]
    total_value: int
    time_window: timedelta
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalletActivity:
    """Recent wallet activity data"""
    address: str
    transaction_time: datetime
    amount: int
    balance: int
    dormancy_days: int
    last_activity_before: Optional[datetime]
    vulnerability_type: str


class QuantumEmergencyDetector:
    """Detects patterns indicating potential quantum computing attacks"""
    
    def __init__(self):
        self.logger = logger.bind(component="quantum_detector")
        self.dormancy_threshold = timedelta(days=settings.dormancy_threshold_days)
        self.emergency_window = timedelta(minutes=settings.emergency_time_window_minutes)
        self.min_wallets_threshold = settings.min_dormant_wallets_for_alert
        
        # Statistical thresholds
        self.zscore_threshold = 3.0
        self.volume_spike_multiplier = 10.0
        
    def analyze_recent_activity(self, activities: List[WalletActivity]) -> List[EmergencyPattern]:
        """Analyze recent activities for emergency patterns"""
        patterns = []
        
        # Check for dormant wallet surge
        dormant_pattern = self._detect_dormant_wallet_surge(activities)
        if dormant_pattern:
            patterns.append(dormant_pattern)
        
        # Check for coordinated movements
        coordinated_pattern = self._detect_coordinated_movements(activities)
        if coordinated_pattern:
            patterns.append(coordinated_pattern)
        
        # Check for value concentration
        concentration_pattern = self._detect_value_concentration(activities)
        if concentration_pattern:
            patterns.append(concentration_pattern)
        
        # Check for statistical anomalies
        anomaly_patterns = self._detect_statistical_anomalies(activities)
        patterns.extend(anomaly_patterns)
        
        return patterns
    
    def _detect_dormant_wallet_surge(self, activities: List[WalletActivity]) -> Optional[EmergencyPattern]:
        """Detect multiple dormant wallets becoming active"""
        dormant_activities = [
            act for act in activities
            if act.dormancy_days >= self.dormancy_threshold.days
        ]
        
        if len(dormant_activities) < self.min_wallets_threshold:
            return None
        
        # Group by time window
        time_groups = self._group_by_time_window(dormant_activities)
        
        for window_start, group_activities in time_groups.items():
            if len(group_activities) >= self.min_wallets_threshold:
                # Calculate pattern metrics
                avg_dormancy = np.mean([act.dormancy_days for act in group_activities])
                total_value = sum(act.balance for act in group_activities)
                
                # Determine severity based on wallet count and value
                severity = self._calculate_severity(
                    wallet_count=len(group_activities),
                    total_value_btc=total_value / 100_000_000,
                    avg_dormancy_years=avg_dormancy / 365
                )
                
                return EmergencyPattern(
                    pattern_type="dormant_wallet_surge",
                    severity=severity,
                    confidence=min(0.95, len(group_activities) / 10),  # Higher count = higher confidence
                    affected_wallets=[act.address for act in group_activities],
                    total_value=total_value,
                    time_window=self.emergency_window,
                    metadata={
                        "average_dormancy_years": avg_dormancy / 365,
                        "oldest_wallet_years": max(act.dormancy_days for act in group_activities) / 365,
                        "time_cluster_start": window_start.isoformat(),
                        "p2pk_count": sum(1 for act in group_activities if act.vulnerability_type == "P2PK")
                    }
                )
        
        return None
    
    def _detect_coordinated_movements(self, activities: List[WalletActivity]) -> Optional[EmergencyPattern]:
        """Detect coordinated wallet movements (similar amounts, timing)"""
        if len(activities) < 3:
            return None
        
        # Group by similar time windows
        time_groups = self._group_by_time_window(activities, window_minutes=10)
        
        for window_start, group_activities in time_groups.items():
            if len(group_activities) < 3:
                continue
            
            # Check for similar transaction amounts
            amounts = [act.amount for act in group_activities]
            amount_variance = np.var(amounts) / (np.mean(amounts) ** 2) if np.mean(amounts) > 0 else float('inf')
            
            # Low variance in amounts suggests coordination
            if amount_variance < 0.1 and len(group_activities) >= 5:
                total_value = sum(act.balance for act in group_activities)
                
                return EmergencyPattern(
                    pattern_type="coordinated_movement",
                    severity="HIGH",
                    confidence=0.8,
                    affected_wallets=[act.address for act in group_activities],
                    total_value=total_value,
                    time_window=timedelta(minutes=10),
                    metadata={
                        "amount_variance": amount_variance,
                        "average_amount_btc": np.mean(amounts) / 100_000_000,
                        "wallet_count": len(group_activities)
                    }
                )
        
        return None
    
    def _detect_value_concentration(self, activities: List[WalletActivity]) -> Optional[EmergencyPattern]:
        """Detect multiple high-value wallets moving to similar destinations"""
        high_value_threshold = 100 * 100_000_000  # 100 BTC
        
        high_value_activities = [
            act for act in activities
            if act.balance >= high_value_threshold
        ]
        
        if len(high_value_activities) < 3:
            return None
        
        # Check if activities are within emergency window
        time_span = max(act.transaction_time for act in high_value_activities) - \
                   min(act.transaction_time for act in high_value_activities)
        
        if time_span <= self.emergency_window:
            total_value = sum(act.balance for act in high_value_activities)
            
            return EmergencyPattern(
                pattern_type="high_value_concentration",
                severity="CRITICAL",
                confidence=0.9,
                affected_wallets=[act.address for act in high_value_activities],
                total_value=total_value,
                time_window=time_span,
                metadata={
                    "average_value_btc": total_value / len(high_value_activities) / 100_000_000,
                    "largest_wallet_btc": max(act.balance for act in high_value_activities) / 100_000_000,
                    "time_span_minutes": time_span.total_seconds() / 60
                }
            )
        
        return None
    
    def _detect_statistical_anomalies(self, activities: List[WalletActivity]) -> List[EmergencyPattern]:
        """Detect statistical anomalies in transaction patterns"""
        patterns = []
        
        # Group by wallet for individual anomaly detection
        wallet_activities = defaultdict(list)
        for act in activities:
            wallet_activities[act.address].append(act)
        
        for wallet_address, wallet_acts in wallet_activities.items():
            if len(wallet_acts) < 2:
                continue
            
            # Calculate transaction frequency anomaly
            if len(wallet_acts) >= 5:
                time_diffs = []
                sorted_acts = sorted(wallet_acts, key=lambda x: x.transaction_time)
                for i in range(1, len(sorted_acts)):
                    diff = (sorted_acts[i].transaction_time - sorted_acts[i-1].transaction_time).total_seconds()
                    time_diffs.append(diff)
                
                if time_diffs:
                    mean_diff = np.mean(time_diffs)
                    std_diff = np.std(time_diffs)
                    
                    # Check for sudden burst of activity
                    if std_diff > 0 and mean_diff < 300:  # Less than 5 minutes average
                        zscore = (300 - mean_diff) / std_diff
                        
                        if zscore > self.zscore_threshold:
                            patterns.append(EmergencyPattern(
                                pattern_type="transaction_burst",
                                severity="MEDIUM",
                                confidence=min(0.9, zscore / 5),
                                affected_wallets=[wallet_address],
                                total_value=wallet_acts[0].balance,
                                time_window=timedelta(seconds=mean_diff * len(wallet_acts)),
                                metadata={
                                    "transaction_count": len(wallet_acts),
                                    "average_interval_seconds": mean_diff,
                                    "zscore": zscore
                                }
                            ))
        
        return patterns
    
    def _group_by_time_window(self, activities: List[WalletActivity], 
                            window_minutes: Optional[int] = None) -> Dict[datetime, List[WalletActivity]]:
        """Group activities by time windows"""
        window = timedelta(minutes=window_minutes or self.emergency_window.total_seconds() / 60)
        groups = defaultdict(list)
        
        for act in activities:
            # Round down to nearest window
            window_start = act.transaction_time - timedelta(
                minutes=act.transaction_time.minute % window.total_seconds() / 60,
                seconds=act.transaction_time.second,
                microseconds=act.transaction_time.microsecond
            )
            groups[window_start].append(act)
        
        return dict(groups)
    
    def _calculate_severity(self, wallet_count: int, total_value_btc: float, 
                          avg_dormancy_years: float) -> str:
        """Calculate pattern severity based on multiple factors"""
        score = 0
        
        # Wallet count factor
        if wallet_count >= 20:
            score += 40
        elif wallet_count >= 10:
            score += 30
        elif wallet_count >= 5:
            score += 20
        else:
            score += 10
        
        # Value factor
        if total_value_btc >= 10000:
            score += 40
        elif total_value_btc >= 1000:
            score += 30
        elif total_value_btc >= 100:
            score += 20
        else:
            score += 10
        
        # Dormancy factor
        if avg_dormancy_years >= 10:
            score += 20
        elif avg_dormancy_years >= 5:
            score += 15
        elif avg_dormancy_years >= 2:
            score += 10
        else:
            score += 5
        
        # Map score to severity
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        else:
            return "LOW"
    
    def calculate_market_impact(self, activities: List[WalletActivity]) -> Dict[str, Any]:
        """Estimate potential market impact of detected activities"""
        total_btc = sum(act.balance for act in activities) / 100_000_000
        
        # Simple impact model based on historical data
        # Assumes linear impact for simplicity
        price_impact_percent = min(20, total_btc / 1000)  # 1000 BTC = 1% impact, capped at 20%
        
        return {
            "total_btc_at_risk": total_btc,
            "estimated_price_impact_percent": price_impact_percent,
            "market_cap_impact_usd": total_btc * 50000 * price_impact_percent / 100,  # Assuming $50k BTC
            "confidence": "medium" if len(activities) >= 10 else "low"
        }