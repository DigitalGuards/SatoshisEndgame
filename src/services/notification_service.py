import asyncio
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import aiohttp
import structlog
from discord_webhook import AsyncDiscordWebhook, DiscordEmbed

from src.config import settings
from src.data.models import Alert

logger = structlog.get_logger()


@dataclass
class NotificationAlert:
    """Alert data for notifications"""
    alert_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    title: str
    description: str
    wallet_addresses: List[str]
    total_value: int  # satoshis
    pattern: Optional[str] = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


class RateLimiter:
    """Discord webhook rate limiter"""
    
    def __init__(self, max_requests_per_minute: int = 30):
        self.max_requests = max_requests_per_minute
        self.request_times = deque(maxlen=max_requests_per_minute)
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        async with self.lock:
            now = time.time()
            
            # Remove old requests outside the time window
            minute_ago = now - 60
            while self.request_times and self.request_times[0] < minute_ago:
                self.request_times.popleft()
            
            # Check if we need to wait
            if len(self.request_times) >= self.max_requests:
                oldest_request = self.request_times[0]
                wait_time = 60 - (now - oldest_request) + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.time()
            
            self.request_times.append(now)


class DiscordNotificationService:
    """Handles Discord webhook notifications"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.discord_webhook_url
        self.rate_limiter = RateLimiter()
        self.logger = logger.bind(component="discord_notifications")
        
        # Alert deduplication
        self.recent_alerts: Dict[str, datetime] = {}
        self.cooldown_period = timedelta(minutes=settings.alert_cooldown_minutes)
        
        # Color scheme for different severities
        self.color_map = {
            'LOW': 0x00ff00,      # Green
            'MEDIUM': 0xffff00,   # Yellow
            'HIGH': 0xff8000,     # Orange
            'CRITICAL': 0xff0000  # Red
        }
    
    def _should_send_alert(self, alert: NotificationAlert) -> bool:
        """Check if alert should be sent (deduplication)"""
        # Create unique key for this alert type
        alert_key = f"{alert.alert_type}:{alert.pattern}:{len(alert.wallet_addresses)}"
        
        # Check if we've sent a similar alert recently
        if alert_key in self.recent_alerts:
            time_since_last = datetime.utcnow() - self.recent_alerts[alert_key]
            if time_since_last < self.cooldown_period:
                self.logger.debug(
                    "Alert suppressed due to cooldown",
                    alert_type=alert.alert_type,
                    time_remaining=(self.cooldown_period - time_since_last).seconds
                )
                return False
        
        # Update last sent time
        self.recent_alerts[alert_key] = datetime.utcnow()
        return True
    
    def _create_embed(self, alert: NotificationAlert) -> DiscordEmbed:
        """Create Discord embed for alert"""
        color = self.color_map.get(alert.severity, 0x808080)
        
        # Create embed with severity-based styling
        embed = DiscordEmbed(
            title=f"🚨 {alert.title}",
            description=alert.description,
            color=color,
            timestamp=alert.timestamp
        )
        
        # Add severity indicator
        severity_emojis = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🟠',
            'CRITICAL': '🔴'
        }
        embed.add_embed_field(
            name="Severity",
            value=f"{severity_emojis.get(alert.severity, '⚪')} {alert.severity}",
            inline=True
        )
        
        # Add affected wallets count
        embed.add_embed_field(
            name="Affected Wallets",
            value=str(len(alert.wallet_addresses)),
            inline=True
        )
        
        # Add total value in BTC
        btc_value = alert.total_value / 100_000_000
        embed.add_embed_field(
            name="Total Value",
            value=f"{btc_value:,.8f} BTC",
            inline=True
        )
        
        # Add pattern if detected
        if alert.pattern:
            embed.add_embed_field(
                name="Pattern Detected",
                value=alert.pattern,
                inline=False
            )
        
        # Add sample addresses (up to 5)
        if alert.wallet_addresses:
            sample_addresses = alert.wallet_addresses[:5]
            address_list = "\n".join([f"`{addr[:10]}...{addr[-6:]}`" for addr in sample_addresses])
            if len(alert.wallet_addresses) > 5:
                address_list += f"\n*... and {len(alert.wallet_addresses) - 5} more*"
            
            embed.add_embed_field(
                name="Sample Addresses",
                value=address_list,
                inline=False
            )
        
        # Add metadata if present
        if alert.metadata:
            for key, value in list(alert.metadata.items())[:3]:  # Limit to 3 fields
                embed.add_embed_field(
                    name=key.replace('_', ' ').title(),
                    value=str(value),
                    inline=True
                )
        
        # Add footer
        embed.set_footer(text="SatoshisEndgame Quantum Monitoring System")
        
        return embed
    
    async def send_alert(self, alert: NotificationAlert) -> bool:
        """Send alert to Discord webhook"""
        try:
            # Check deduplication
            if not self._should_send_alert(alert):
                return False
            
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Create webhook
            webhook = AsyncDiscordWebhook(
                url=self.webhook_url,
                rate_limit_retry=True
            )
            
            # Add embed
            embed = self._create_embed(alert)
            webhook.add_embed(embed)
            
            # Send webhook
            response = await webhook.execute()
            
            if response.status_code == 204:
                self.logger.info(
                    "Discord alert sent successfully",
                    alert_type=alert.alert_type,
                    severity=alert.severity
                )
                return True
            else:
                self.logger.error(
                    "Failed to send Discord alert",
                    status_code=response.status_code,
                    response=response.text
                )
                return False
                
        except Exception as e:
            self.logger.error(
                "Error sending Discord alert",
                error=str(e),
                alert_type=alert.alert_type
            )
            return False
    
    async def send_startup_notification(self):
        """Send a notification when the system starts"""
        alert = NotificationAlert(
            alert_type="system_startup",
            severity="LOW",
            title="System Started",
            description="SatoshisEndgame monitoring system has been initialized and is now actively monitoring quantum-vulnerable Bitcoin addresses.",
            wallet_addresses=[],
            total_value=0,
            metadata={
                "version": "1.0.0",
                "monitored_addresses": "Loading...",
                "start_time": datetime.utcnow().isoformat()
            }
        )
        await self.send_alert(alert)
    
    async def send_quantum_emergency_alert(self, dormant_wallets: List[Dict[str, Any]]):
        """Send critical alert for potential quantum emergency"""
        total_btc = sum(w['balance'] for w in dormant_wallets) / 100_000_000
        
        alert = NotificationAlert(
            alert_type="quantum_emergency",
            severity="CRITICAL",
            title="⚠️ QUANTUM EMERGENCY DETECTED",
            description=(
                f"Multiple dormant wallets have become active simultaneously. "
                f"This pattern could indicate a quantum computing breakthrough or coordinated attack. "
                f"Total value at risk: {total_btc:,.2f} BTC"
            ),
            wallet_addresses=[w['address'] for w in dormant_wallets],
            total_value=sum(w['balance'] for w in dormant_wallets),
            pattern="dormant_wallet_surge",
            metadata={
                "average_dormancy_years": sum(w['dormancy_days'] for w in dormant_wallets) / len(dormant_wallets) / 365,
                "time_window": f"{settings.emergency_time_window_minutes} minutes",
                "oldest_wallet_years": max(w['dormancy_days'] for w in dormant_wallets) / 365
            }
        )
        await self.send_alert(alert)
    
    async def send_anomaly_alert(self, wallet_address: str, anomaly_type: str, 
                                details: Dict[str, Any]):
        """Send alert for detected anomalies"""
        severity = "HIGH" if anomaly_type == "statistical_anomaly" else "MEDIUM"
        
        alert = NotificationAlert(
            alert_type="wallet_anomaly",
            severity=severity,
            title=f"Anomaly Detected: {anomaly_type.replace('_', ' ').title()}",
            description=f"Unusual activity detected for wallet {wallet_address[:10]}...{wallet_address[-6:]}",
            wallet_addresses=[wallet_address],
            total_value=details.get('balance', 0),
            pattern=anomaly_type,
            metadata=details
        )
        await self.send_alert(alert)
    
    async def send_test_alert(self):
        """Send a test alert to verify webhook configuration"""
        alert = NotificationAlert(
            alert_type="test",
            severity="LOW",
            title="Test Alert",
            description="This is a test alert to verify Discord webhook configuration.",
            wallet_addresses=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],  # Genesis block
            total_value=5000000000,  # 50 BTC
            metadata={"test": True, "timestamp": datetime.utcnow().isoformat()}
        )
        return await self.send_alert(alert)