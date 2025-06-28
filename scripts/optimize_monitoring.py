#!/usr/bin/env python3
"""
Optimize monitoring strategy for BlockCypher API limits
Free tier: 1000 requests/day, 100 requests/hour, 3 requests/second
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

import structlog
from sqlalchemy import select, and_, func

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config import settings
from src.data.database import db
from src.data.models import Wallet

logger = structlog.get_logger()


class MonitoringOptimizer:
    """Optimize address monitoring for API limits"""
    
    def __init__(self):
        self.daily_limit = 1000
        self.hourly_limit = 100
        self.requests_per_second = 3
        
    async def calculate_optimal_strategy(self, total_addresses: int) -> Dict:
        """Calculate optimal monitoring strategy based on limits"""
        
        strategies = []
        
        # Strategy 1: Monitor only highest-risk addresses
        if total_addresses > self.daily_limit:
            max_monitored = int(self.daily_limit * 0.8)  # Keep 20% buffer
            check_interval_minutes = 24 * 60  # Once per day
            
            strategies.append({
                'name': 'High-Risk Only',
                'max_addresses': max_monitored,
                'check_interval_minutes': check_interval_minutes,
                'selection_criteria': 'risk_score',
                'requests_per_day': max_monitored,
                'description': f'Monitor top {max_monitored} addresses by risk score, check once daily'
            })
        
        # Strategy 2: Tiered monitoring based on risk
        tier1_addresses = min(50, int(self.hourly_limit * 0.5))  # Critical addresses
        tier2_addresses = min(200, int(self.daily_limit * 0.3))  # High risk
        tier3_addresses = min(600, int(self.daily_limit * 0.5))  # Medium risk
        
        strategies.append({
            'name': 'Tiered Risk-Based',
            'tiers': [
                {
                    'name': 'Critical (95+ risk score)',
                    'max_addresses': tier1_addresses,
                    'check_interval_minutes': 60,  # Every hour
                    'requests_per_day': tier1_addresses * 24
                },
                {
                    'name': 'High (80-94 risk score)',
                    'max_addresses': tier2_addresses,
                    'check_interval_minutes': 240,  # Every 4 hours
                    'requests_per_day': tier2_addresses * 6
                },
                {
                    'name': 'Medium (60-79 risk score)',
                    'max_addresses': tier3_addresses,
                    'check_interval_minutes': 1440,  # Once daily
                    'requests_per_day': tier3_addresses
                }
            ],
            'total_requests_per_day': tier1_addresses * 24 + tier2_addresses * 6 + tier3_addresses,
            'description': 'Different check frequencies based on risk level'
        })
        
        # Strategy 3: Round-robin monitoring
        if total_addresses <= self.daily_limit * 7:  # Can check all weekly
            batches = 7
            batch_size = total_addresses // batches
            
            strategies.append({
                'name': 'Weekly Round-Robin',
                'batch_size': batch_size,
                'batches': batches,
                'check_interval_days': 7,
                'requests_per_day': batch_size,
                'description': f'Check {batch_size} addresses daily, full rotation every 7 days'
            })
        
        return strategies
    
    async def analyze_current_addresses(self) -> Dict:
        """Analyze current addresses in database"""
        await db.initialize()
        
        async with db.get_session() as session:
            # Total addresses
            total_count = await session.scalar(
                select(func.count(Wallet.id)).where(
                    and_(Wallet.is_vulnerable == True, Wallet.is_active == True)
                )
            )
            
            # Risk score distribution
            risk_distribution = await session.execute(
                select(
                    func.case(
                        (Wallet.risk_score >= 95, 'Critical'),
                        (Wallet.risk_score >= 80, 'High'),
                        (Wallet.risk_score >= 60, 'Medium'),
                        else_='Low'
                    ).label('risk_level'),
                    func.count(Wallet.id).label('count'),
                    func.sum(Wallet.current_balance).label('total_balance')
                ).where(
                    and_(Wallet.is_vulnerable == True, Wallet.is_active == True)
                ).group_by('risk_level')
            )
            
            distribution = {row.risk_level: {
                'count': row.count,
                'total_btc': row.total_balance / 100_000_000 if row.total_balance else 0
            } for row in risk_distribution}
            
            # High-value addresses (100+ BTC)
            high_value_count = await session.scalar(
                select(func.count(Wallet.id)).where(
                    and_(
                        Wallet.is_vulnerable == True,
                        Wallet.is_active == True,
                        Wallet.current_balance >= 100 * 100_000_000
                    )
                )
            )
            
            # Dormancy analysis
            dormancy_stats = await session.execute(
                select(
                    func.avg(Wallet.dormancy_days).label('avg_dormancy'),
                    func.max(Wallet.dormancy_days).label('max_dormancy'),
                    func.count(Wallet.id).filter(Wallet.dormancy_days >= 3650).label('decade_dormant')
                ).where(
                    and_(Wallet.is_vulnerable == True, Wallet.is_active == True)
                )
            )
            dormancy = dormancy_stats.one()
        
        await db.close()
        
        return {
            'total_addresses': total_count,
            'risk_distribution': distribution,
            'high_value_count': high_value_count,
            'dormancy_stats': {
                'avg_years': dormancy.avg_dormancy / 365.25 if dormancy.avg_dormancy else 0,
                'max_years': dormancy.max_dormancy / 365.25 if dormancy.max_dormancy else 0,
                'decade_dormant_count': dormancy.decade_dormant
            }
        }
    
    async def create_monitoring_config(self, strategy_name: str) -> Dict:
        """Create monitoring configuration file based on strategy"""
        config = {
            'strategy': strategy_name,
            'created_at': datetime.utcnow().isoformat(),
            'blockcypher_limits': {
                'daily': self.daily_limit,
                'hourly': self.hourly_limit,
                'per_second': self.requests_per_second
            }
        }
        
        if strategy_name == 'tiered':
            config['monitoring_tiers'] = {
                'critical': {
                    'risk_score_min': 95,
                    'max_addresses': 50,
                    'check_interval_minutes': 60
                },
                'high': {
                    'risk_score_min': 80,
                    'risk_score_max': 94,
                    'max_addresses': 200,
                    'check_interval_minutes': 240
                },
                'medium': {
                    'risk_score_min': 60,
                    'risk_score_max': 79,
                    'max_addresses': 600,
                    'check_interval_minutes': 1440
                }
            }
        
        return config


async def main():
    """Main analysis function"""
    optimizer = MonitoringOptimizer()
    
    # Analyze current addresses
    logger.info("Analyzing current address database...")
    analysis = await optimizer.analyze_current_addresses()
    
    print("\n" + "="*60)
    print("CURRENT DATABASE ANALYSIS")
    print("="*60)
    print(f"Total vulnerable addresses: {analysis['total_addresses']}")
    print(f"High-value addresses (100+ BTC): {analysis['high_value_count']}")
    print(f"\nRisk Distribution:")
    for level, data in analysis['risk_distribution'].items():
        print(f"  {level}: {data['count']} addresses ({data['total_btc']:.2f} BTC)")
    print(f"\nDormancy Stats:")
    print(f"  Average: {analysis['dormancy_stats']['avg_years']:.1f} years")
    print(f"  Maximum: {analysis['dormancy_stats']['max_years']:.1f} years")
    print(f"  10+ years dormant: {analysis['dormancy_stats']['decade_dormant_count']}")
    
    # Calculate optimal strategies
    strategies = await optimizer.calculate_optimal_strategy(analysis['total_addresses'])
    
    print("\n" + "="*60)
    print("RECOMMENDED MONITORING STRATEGIES")
    print("="*60)
    
    for i, strategy in enumerate(strategies, 1):
        print(f"\n{i}. {strategy['name']}")
        print(f"   {strategy['description']}")
        
        if 'tiers' in strategy:
            print("   Tiers:")
            for tier in strategy['tiers']:
                print(f"     - {tier['name']}: {tier['max_addresses']} addresses, "
                      f"check every {tier['check_interval_minutes']} minutes "
                      f"({tier['requests_per_day']} requests/day)")
            print(f"   Total requests/day: {strategy['total_requests_per_day']}")
        else:
            if 'requests_per_day' in strategy:
                print(f"   Requests per day: {strategy['requests_per_day']}")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    print("1. Use Tiered Risk-Based monitoring for optimal coverage")
    print("2. Focus on addresses with:")
    print("   - High risk scores (80+)")
    print("   - Large balances (100+ BTC)")
    print("   - Long dormancy (10+ years)")
    print("3. Consider getting a paid BlockCypher plan for comprehensive monitoring")
    print("4. Alternatively, use Blockchair with an API key (higher limits)")
    
    # Calculate required API calls for full monitoring
    if analysis['total_addresses'] > 0:
        hourly_full = analysis['total_addresses'] * 12  # Every 5 minutes
        daily_full = hourly_full * 24
        
        print(f"\nFull monitoring would require:")
        print(f"  {hourly_full:,} requests/hour")
        print(f"  {daily_full:,} requests/day")
        print(f"  This is {daily_full / optimizer.daily_limit:.0f}x the free tier limit!")


if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    asyncio.run(main())