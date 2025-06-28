#!/bin/bash

# SatoshisEndgame restart script
# Clears database and restarts monitoring with fresh state

echo "🔄 Restarting SatoshisEndgame monitoring system..."

# Stop any running monitor process
echo "⏹️  Stopping existing monitor process..."
pkill -f "python -m src.cli monitor" 2>/dev/null || true
sleep 1

# Remove existing database
echo "🗑️  Removing existing database..."
rm -f satoshis_endgame.db

# Initialize fresh database
echo "🔧 Initializing fresh database..."
./venv/bin/python -m src.cli init-db

# Load sample vulnerable addresses
echo "📥 Loading vulnerable addresses..."
./venv/bin/python -m src.utils.init_data

# Show status
echo ""
echo "📊 System status:"
./venv/bin/python -m src.cli status

# Start monitoring
echo ""
echo "🚀 Starting monitor..."
./venv/bin/python -m src.cli monitor