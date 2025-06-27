#!/bin/bash

WEBHOOK_URL="https://discord.com/api/webhooks/1388084376629153842/edZJIw8DYAC3aE96WrJWExZoqTD6YH5yubgXPmjEskLp7_1RWgr0-INudO7dYjT-P8_P"

echo "Sending test alert to Discord..."

curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d @- << EOF
{
  "content": null,
  "embeds": [{
    "title": "🚨 Quantum Emergency Detection Test",
    "description": "**SatoshisEndgame Alert System Active**\\n\\nThis is a test of the quantum vulnerability monitoring system. In a real emergency, this would indicate multiple dormant Bitcoin wallets becoming active simultaneously.",
    "color": 16711680,
    "fields": [
      {
        "name": "Pattern Detected",
        "value": "Dormant Wallet Surge",
        "inline": true
      },
      {
        "name": "Affected Wallets",
        "value": "6",
        "inline": true
      },
      {
        "name": "Total Value",
        "value": "2,500 BTC",
        "inline": true
      },
      {
        "name": "Sample Addresses",
        "value": "\`1A1zP1eP5Q...DivfNa\` (Genesis)\\n\`12c6DSiU4R...BrzjrJX\` (10y dormant)\\n\`1HLoD9E4SD...J3Zb1\` (12y dormant)",
        "inline": false
      }
    ],
    "footer": {
      "text": "SatoshisEndgame v0.1.0 - Monitoring System"
    },
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
  }]
}
EOF

echo -e "\n✓ Test complete!"