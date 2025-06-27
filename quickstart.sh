#!/bin/bash

echo "SatoshisEndgame Quick Start"
echo "=========================="

# Check Python version
python3 --version >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Database configuration (SQLite for testing, no setup needed)
DATABASE_URL=sqlite+aiosqlite:///satoshis_endgame.db

# Discord webhook
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1388084376629153842/edZJIw8DYAC3aE96WrJWExZoqTD6YH5yubgXPmjEskLp7_1RWgr0-INudO7dYjT-P8_P

# API Keys (optional - system will work without them)
BLOCKCYPHER_API_KEY=
BLOCKCHAIR_API_KEY=

# Monitoring settings
BATCH_SIZE=20
DORMANCY_THRESHOLD_DAYS=365
MIN_BALANCE_THRESHOLD_BTC=10
ALERT_COOLDOWN_MINUTES=30

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=plain
EOF
fi

echo "Setup complete! You can now run:"
echo "  python -m src.cli init-db    # Initialize database"
echo "  python -m src.cli monitor     # Start monitoring"
echo "  python -m src.cli status      # Check system status"