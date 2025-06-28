# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SatoshisEndgame is a real-time monitoring system for quantum-vulnerable Bitcoin addresses. It detects patterns that could indicate quantum computing attacks by monitoring ~4.5M BTC at risk from P2PK addresses and reused P2PKH addresses.

## Development Commands

### Setup and Running
```bash
# Quick setup (creates venv, installs deps, creates .env)
./quickstart.sh

# Initialize database (SQLite for dev, PostgreSQL for prod)
python -m src.cli init-db

# Load real dormant addresses from BitInfoCharts (943 addresses, 1.3M BTC)
python -m src.scrapers.bitinfocharts_scraper_v2 --pages 10
python -m scripts.import_bitinfocharts --min-balance 100

# Start monitoring daemon
python -m src.cli monitor

# Test Discord webhook
./test_webhook.sh

# Full restart with fresh database
./restart.sh
```

### Code Quality
```bash
# Format code
black src/
ruff src/

# Type checking
mypy src/

# Run tests (when implemented)
pytest tests/
```

### CLI Commands
```bash
# Check system status
python -m src.cli status

# Test quantum detection algorithms
python -m src.cli test-detection

# Check if address is vulnerable
python -m src.cli check-address <address>

# Drop database (careful!)
python -m src.cli drop-db
```

## Recent Improvements

### Block-Based Monitoring (Major Architecture Change)
- Switched from individual address polling to block monitoring
- 1,886x more efficient (144 vs 271,584 API calls/day)
- Loads all dormant addresses into memory for fast lookup
- Monitors new blocks and extracts addresses from transactions
- Only makes API calls when dormant addresses actually move

### Real Dormant Addresses
- Scraped 943 real dormant addresses from BitInfoCharts
- Total value monitored: 1.3 million BTC
- Addresses haven't moved in 8+ years
- Includes famous addresses like MtGox hack wallets

### API Request Logging
- All successful API requests now show balance information
- Request timing and statistics tracked
- Shows which API is being used (primary vs fallback)
- Monitoring cycle completion shows total requests and success rate

### Service Management
- `service.sh` script for systemd integration
- `restart.sh` for quick database reset and restart
- Portable service files with no hardcoded paths

## High-Level Architecture

### Async/Await Flow
The entire system is built on Python's asyncio for concurrent operations:

1. **Database Operations**: All DB access uses async SQLAlchemy sessions via context managers
2. **API Calls**: Blockchain APIs are called concurrently with aiohttp
3. **Monitoring Loop**: The main daemon runs scheduled async tasks via APScheduler
4. **Pattern Detection**: Multiple patterns are analyzed concurrently

### Service Orchestration
`MonitoringService` is the central orchestrator that:
- Initializes all components (blockchain APIs, database, Discord service)
- Schedules periodic tasks with different intervals:
  - `monitor_all_addresses`: 5 minutes - full address scan
  - `quick_check_high_risk`: 1 minute - priority addresses only
  - `database_maintenance`: 6 hours - cleanup tasks
  - `create_wallet_snapshots`: 1 hour - state persistence
- Coordinates pattern detection and alert sending

### Blockchain API Fallback Mechanism
`BlockchainManager` implements a multi-provider strategy:
```python
# Priority order: Blockchair → BlockCypher → Blockchain.info
for api in self.apis:
    try:
        return await api.get_address_info(address)
    except BlockchainAPIError:
        continue  # Try next API
```

Each API has:
- Individual rate limiters (token bucket algorithm)
- Specific error handling
- Optimized methods (e.g., Blockchair supports batch queries)

### Pattern Detection Flow
`QuantumEmergencyDetector` analyzes activities for 4 patterns:

1. **Dormant Wallet Surge**: Groups activities by time windows, checks dormancy
2. **Coordinated Movements**: Analyzes transaction amount variance
3. **Value Concentration**: Detects high-value movements in short timeframes
4. **Statistical Anomalies**: Z-score analysis on transaction frequencies

Severity calculation is composite:
- Wallet count factor (up to 40 points)
- Total value factor (up to 40 points)  
- Dormancy factor (up to 20 points)
- Maps to: CRITICAL (80+), HIGH (60+), MEDIUM (40+), LOW

### Database Interaction Patterns
The system uses async SQLAlchemy with these patterns:

1. **Session Management**: Always use `async with db.get_session()` 
2. **Bulk Operations**: Prefer batch inserts/updates for efficiency
3. **Indexed Queries**: Heavy use of composite indexes for time-series queries
4. **Transaction Safety**: Auto-rollback on exceptions

Key tables:
- `wallets`: Core tracking with vulnerability metadata
- `transactions`: Time-series data for pattern analysis
- `alerts`: Notification history with deduplication
- `wallet_snapshots`: Periodic state for trend analysis

### Alert Flow
1. Pattern detected → `EmergencyPattern` created
2. Pattern evaluated → `_handle_emergency_pattern` called
3. Database alert created → Persistent record
4. Discord notification sent → Rate-limited with deduplication
5. Cooldown applied → Prevents alert spam

## Key Architectural Decisions

### Block Monitoring vs Individual Polling
The system now uses **block-based monitoring** for efficiency:
- **Old approach**: 943 addresses × 288 checks/day = 271,584 API calls (exceeds limits!)
- **New approach**: ~144 blocks/day = 144 API calls (1,886x more efficient!)

How it works:
1. Monitor new blocks (~every 10 minutes)
2. Extract all addresses from block transactions
3. Check against our 943 dormant addresses (fast in-memory)
4. Only fetch details for matches (rare)

Benefits:
- Stays within API free tier limits
- Never misses a transaction
- Scales to millions of addresses
- Real-time detection (within minutes)

### Async-First Design
Everything is async to handle:
- Monitoring thousands of addresses concurrently
- Multiple API providers with different rate limits
- Database operations without blocking
- Discord webhooks without delaying detection

### Modular Service Architecture
Services are loosely coupled:
- `BlockchainManager`: Only knows about APIs
- `QuantumEmergencyDetector`: Pure pattern analysis
- `DiscordNotificationService`: Just sends webhooks
- `MonitoringService`: Orchestrates but doesn't implement logic

### Defensive Programming
- All API calls wrapped in try/except with fallback
- Rate limiting on client side (not just server)
- Database sessions always use context managers
- Configuration validation with Pydantic

### Privacy and Security
- Addresses truncated in logs (`address[:10]...`)
- No private keys ever handled
- Read-only blockchain access
- Environment variables for sensitive config

## Configuration Management

Settings use Pydantic with validation:
- Type checking on all config values
- Default values for optional settings
- Validation for webhook URLs, thresholds
- Support for both .env files and environment variables

## Testing Considerations

When testing changes:
1. Use SQLite locally (no PostgreSQL needed)
2. Test webhook included in repo
3. Sample addresses in `data/vulnerable_addresses.txt`
4. Can trigger patterns with `test-detection` command
5. API rate limits are client-side enforced