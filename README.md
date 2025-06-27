# 🛡️ SatoshisEndgame

> **Real-time monitoring system for quantum-vulnerable Bitcoin addresses**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Discord](https://img.shields.io/badge/alerts-Discord-7289da.svg)](https://discord.com)

SatoshisEndgame monitors Bitcoin's quantum-vulnerable addresses and detects patterns that could indicate quantum computing attacks. The system tracks ~4.5 million BTC ($400B+) at risk from future quantum computers.

## 🚨 The Quantum Threat

Current quantum computers are far from breaking Bitcoin's encryption, but the threat is real:

- **~2M BTC** in P2PK addresses with directly exposed public keys
- **~2.5M BTC** in reused P2PKH addresses where public keys are revealed
- **Satoshi's coins** (1M+ BTC) are particularly vulnerable

When quantum computers become powerful enough, these funds could be stolen in minutes.

## 🎯 Key Features

- **🔍 Multi-Source Monitoring** - Redundant blockchain APIs with automatic fallback
- **⚡ Real-time Detection** - Pattern recognition for quantum emergency scenarios
- **💬 Discord Alerts** - Instant notifications for suspicious activities
- **📊 Risk Scoring** - Prioritizes monitoring based on balance, dormancy, and vulnerability
- **🗄️ Time-Series Database** - Efficient storage with PostgreSQL/TimescaleDB
- **🚀 Async Architecture** - High-performance concurrent monitoring

## 📸 Screenshots

### Discord Alert Example
<img src="https://github.com/DigitalGuards/SatoshisEndgame/assets/placeholder/discord-alert.png" alt="Discord Alert" width="600">

*Example of a critical quantum emergency alert*

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 13+ (optional, SQLite works for testing)
- Discord webhook URL

### 30-Second Setup

```bash
# Clone the repository
git clone https://github.com/DigitalGuards/SatoshisEndgame.git
cd SatoshisEndgame

# Run quick setup
./quickstart.sh

# Initialize database
python -m src.cli init-db

# Load sample vulnerable addresses
python -m src.utils.init_data

# Start monitoring
python -m src.cli monitor
```

## 🔧 Configuration

Create a `.env` file (see `.env.example`):

```env
# Database (SQLite for testing, PostgreSQL for production)
DATABASE_URL=sqlite+aiosqlite:///satoshis_endgame.db

# Discord webhook for alerts
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE

# Optional API keys for higher rate limits
BLOCKCYPHER_API_KEY=
BLOCKCHAIR_API_KEY=

# Monitoring thresholds
MIN_BALANCE_THRESHOLD_BTC=10
DORMANCY_THRESHOLD_DAYS=365
```

## 📡 Detection Patterns

SatoshisEndgame monitors for several quantum emergency indicators:

### 1. Dormant Wallet Surge
Multiple long-dormant wallets (5+ years inactive) suddenly moving within a short time window.

### 2. Coordinated Movements
Similar transaction amounts and timing patterns across multiple vulnerable addresses.

### 3. High-Value Concentration
Large amounts (100+ BTC) moving from vulnerable addresses to new destinations.

### 4. Statistical Anomalies
Unusual patterns detected through Z-score analysis of transaction frequencies.

## 🏗️ Architecture

```
src/
├── core/               # Blockchain APIs and vulnerability detection
│   ├── blockchain.py   # Multi-provider blockchain interface
│   └── address_manager.py # Address vulnerability detection
├── services/           # Core services
│   ├── monitoring_service.py # Main monitoring orchestrator
│   ├── notification_service.py # Discord webhook integration
│   └── quantum_detector.py # Emergency pattern detection
├── data/              # Database layer
│   ├── models.py      # SQLAlchemy models
│   └── database.py    # Async database manager
└── cli.py             # Command-line interface
```

## 🔨 Command Line Interface

```bash
# Monitor vulnerable addresses
python -m src.cli monitor

# Check system status
python -m src.cli status

# Test quantum detection algorithms
python -m src.cli test-detection

# Check if an address is vulnerable
python -m src.cli check-address 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

## 🔌 API Providers

The system uses multiple blockchain APIs for redundancy:

| Provider | Free Tier | Rate Limit | Best For |
|----------|-----------|------------|----------|
| BlockCypher | ✅ | 3 req/sec | Webhooks & real-time |
| Blockchair | ✅ | 1k req/day | Batch operations |
| Blockchain.info | ✅ | ~10 req/min | Basic queries |

## 🛡️ Security Considerations

- Never stores private keys or wallet secrets
- Hashes sensitive data in logs
- Uses environment variables for configuration
- Implements rate limiting to respect API limits
- Supports read-only blockchain access

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Format code
black src/
ruff src/
```

## 📊 Database Schema

The system uses these main tables:

- **wallets** - Tracked vulnerable addresses
- **transactions** - Monitored transaction history
- **alerts** - Generated alerts and notifications
- **wallet_snapshots** - Periodic state snapshots for analysis

## 🚦 Monitoring Dashboard (Coming Soon)

Future plans include a web dashboard showing:
- Real-time vulnerable address activity
- Historical patterns and trends
- Risk heat maps
- Alert history

## 📚 Research Background

This project is based on research showing that approximately 4-6.5 million BTC are vulnerable to quantum attacks:

- [Deloitte: Quantum computers and the Bitcoin blockchain](https://www2.deloitte.com/nl/nl/pages/innovatie/artikelen/quantum-computers-and-the-bitcoin-blockchain.html)
- [Bitcoin Post-Quantum](https://bitcoinpq.org/)
- [Quantum Resistant Ledger](https://www.theqrl.org/)

## ⚠️ Disclaimer

This tool is for research and monitoring purposes only. It:
- Does NOT provide investment or trading advice
- Cannot prevent quantum attacks
- Should not be relied upon as the sole security measure
- Is not affiliated with Bitcoin Core or any exchange

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- QRL community for quantum threat awareness
- Bitcoin developers for transparency in the protocol
- All researchers working on post-quantum cryptography

---

<p align="center">
Built with ❤️ for the Bitcoin community<br>
<em>Preparing for the post-quantum future</em>
</p>