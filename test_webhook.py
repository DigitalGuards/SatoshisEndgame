#!/usr/bin/env python3
"""Quick test script for Discord webhook"""

import asyncio
from datetime import datetime
from src.services.notification_service import DiscordNotificationService, NotificationAlert

async def test_webhook():
    # Use the provided webhook URL
    webhook_url = "https://discord.com/api/webhooks/1388084376629153842/edZJIw8DYAC3aE96WrJWExZoqTD6YH5yubgXPmjEskLp7_1RWgr0-INudO7dYjT-P8_P"
    
    discord_service = DiscordNotificationService(webhook_url)
    
    print("Sending test alert to Discord...")
    
    # Create test alert
    alert = NotificationAlert(
        alert_type="quantum_emergency",
        severity="CRITICAL",
        title="TEST: Quantum Emergency Detected",
        description=(
            "This is a test alert from SatoshisEndgame. "
            "Multiple dormant wallets have shown simultaneous activity, "
            "potentially indicating a quantum computing breakthrough."
        ),
        wallet_addresses=[
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi's genesis address
            "12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX",  # Another early address
            "1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1",  # Another early address
        ],
        total_value=250_000_000_000,  # 2500 BTC
        pattern="dormant_wallet_surge",
        metadata={
            "average_dormancy_years": 12.5,
            "oldest_wallet_years": 15,
            "time_window": "30 minutes",
            "confidence": 0.95
        }
    )
    
    success = await discord_service.send_alert(alert)
    
    if success:
        print("✓ Test alert sent successfully!")
    else:
        print("✗ Failed to send test alert")
    
    # Send a follow-up low severity alert
    await asyncio.sleep(2)
    
    info_alert = NotificationAlert(
        alert_type="system_test",
        severity="LOW",
        title="System Test Complete",
        description="SatoshisEndgame monitoring system is configured correctly.",
        wallet_addresses=[],
        total_value=0,
        metadata={
            "test_time": datetime.utcnow().isoformat(),
            "version": "0.1.0"
        }
    )
    
    await discord_service.send_alert(info_alert)

if __name__ == "__main__":
    asyncio.run(test_webhook())