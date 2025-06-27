#!/usr/bin/env python3
"""Simple Discord webhook test without dependencies"""

import json
import urllib.request
import urllib.error
from datetime import datetime

def send_discord_webhook(webhook_url, title, description, color=0xff0000):
    """Send a simple Discord webhook message"""
    
    # Create embed
    embed = {
        "title": f"🚨 {title}",
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "fields": [
            {
                "name": "Severity",
                "value": "🔴 CRITICAL",
                "inline": True
            },
            {
                "name": "Affected Wallets",
                "value": "3",
                "inline": True
            },
            {
                "name": "Total Value",
                "value": "2,500.00000000 BTC",
                "inline": True
            }
        ],
        "footer": {
            "text": "SatoshisEndgame Quantum Monitoring System"
        }
    }
    
    # Create payload
    payload = {
        "embeds": [embed]
    }
    
    # Convert to JSON
    data = json.dumps(payload).encode('utf-8')
    
    # Create request
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        response = urllib.request.urlopen(req)
        return response.status == 204
    except urllib.error.URLError as e:
        print(f"Error: {e}")
        return False

def main():
    webhook_url = "https://discord.com/api/webhooks/1388084376629153842/edZJIw8DYAC3aE96WrJWExZoqTD6YH5yubgXPmjEskLp7_1RWgr0-INudO7dYjT-P8_P"
    
    print("Sending test alert to Discord...")
    
    success = send_discord_webhook(
        webhook_url,
        "TEST: Quantum Emergency Detected",
        "This is a test alert from SatoshisEndgame. Multiple dormant Bitcoin wallets have shown simultaneous activity:\n\n"
        "• `1A1zP1eP5Q...DivfNa` (Genesis block)\n"
        "• `12c6DSiU4R...BrzjrJX` (Early miner)\n"
        "• `1HLoD9E4SD...Y51J3Zb1` (Dormant 10+ years)\n\n"
        "This pattern could indicate a quantum computing breakthrough or coordinated attack.",
        color=0xff0000  # Red for critical
    )
    
    if success:
        print("✓ Test alert sent successfully!")
        
        # Send follow-up info message
        import time
        time.sleep(2)
        
        send_discord_webhook(
            webhook_url,
            "System Test Complete",
            "SatoshisEndgame is configured correctly and ready to monitor quantum-vulnerable Bitcoin addresses.",
            color=0x00ff00  # Green for info
        )
        print("✓ Info message sent!")
    else:
        print("✗ Failed to send test alert")

if __name__ == "__main__":
    main()