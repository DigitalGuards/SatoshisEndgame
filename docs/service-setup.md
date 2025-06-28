# Service Setup Guide

## Overview

SatoshisEndgame can be run as a systemd service for production deployments. This provides:
- Automatic startup on system boot
- Automatic restart on crashes
- Proper logging to system journal
- Process management

## Installation

1. First, ensure the project is set up:
```bash
./quickstart.sh
```

2. Install the service (requires sudo):
```bash
sudo ./service.sh install
```

3. Start the service:
```bash
sudo ./service.sh start
```

4. Enable automatic startup on boot:
```bash
sudo ./service.sh enable
```

## Service Management

### Basic Commands

```bash
# Check service status
./service.sh status

# View live logs
./service.sh logs

# Restart the service
sudo ./service.sh restart

# Stop the service
sudo ./service.sh stop
```

### Uninstalling

To completely remove the service:
```bash
sudo ./service.sh uninstall
```

## How It Works

The service management uses:
- A template file (`satoshis-endgame.service.template`) that contains placeholders
- The `service.sh` script that generates the actual service file with correct paths
- No hardcoded paths - everything is relative to where you cloned the repository

## Troubleshooting

If the service fails to start:
1. Check logs: `./service.sh logs`
2. Ensure database is initialized: `./venv/bin/python -m src.cli init-db`
3. Verify your `.env` file exists and has valid API keys
4. Check Discord webhook URL is correct

## Security Notes

The service runs with:
- `NoNewPrivileges=true` - Prevents privilege escalation
- `PrivateTmp=true` - Isolated temporary files
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=read-only` - Home directory is read-only except for the project directory