# Building a Quantum-Vulnerable Bitcoin Wallet Monitoring System

## Understanding the quantum threat landscape

The quantum computing threat to Bitcoin is real but not immediate. Research indicates that **4-6.5 million BTC** (worth over $700 billion) are currently vulnerable to quantum attacks through Shor's algorithm. These vulnerable funds exist in two main categories: ~2 million BTC in P2PK addresses with directly exposed public keys, and ~2.5 million BTC in reused P2PKH addresses where public keys have been revealed through previous transactions.

Current quantum computers like Google's Willow (105 qubits) are far from the estimated 1,000-13 million fault-tolerant qubits needed to break Bitcoin's elliptic curve cryptography. However, the threat timeline suggests practical quantum attacks could emerge in the 2030s, making proactive monitoring essential.

## Technical approach to identifying vulnerable addresses

### P2PK address detection

P2PK addresses directly expose public keys in their scriptPubKey, making them immediately vulnerable. Here's how to identify them programmatically:

```python
def identify_p2pk_addresses(transaction_output):
    script = transaction_output.scriptPubKey
    # Check for uncompressed (65 bytes) or compressed (33 bytes) public keys
    if (len(script) == 67 and script[0] == 0x41 and script[66] == 0xAC) or \
       (len(script) == 35 and script[0] == 0x21 and script[34] == 0xAC):
        return True
    return False
```

These addresses primarily come from early Bitcoin mining (2009-2010) and include many Satoshi-era coins that have never moved.

### P2PKH reuse vulnerability detection

P2PKH addresses become vulnerable when reused after the first spend exposes their public key:

```python
def detect_reused_p2pkh_addresses(blockchain_data):
    reused_addresses = {}
    for tx in blockchain_data.transactions:
        for input in tx.inputs:
            address = input.previous_output.address
            if address in reused_addresses:
                reused_addresses[address]['exposed'] = True
                reused_addresses[address]['count'] += 1
    return reused_addresses
```

## Blockchain API selection and integration

After comparing major blockchain APIs, I recommend a multi-provider approach for reliability:

**Primary: BlockCypher** - Best webhook system with 99.99% uptime
- Free tier: 3 requests/second, 100 requests/hour
- Excellent for real-time monitoring via webhooks
- Premium plans from $119/month for production use

**Secondary: Blockchair** - Advanced analytics and batch operations
- Free tier: 1,000 requests/day
- Supports batch address queries with space/+ separation
- Premium plans from $25/month

**Tertiary: Blockchain.info** - Reliable backup with WebSocket support
- Free tier with ~10 requests/minute
- Good for basic balance checks and redundancy

Here's an implementation example:

```python
class BitcoinAddressMonitor:
    def __init__(self):
        self.apis = {
            'blockchair': {
                'base_url': 'https://api.blockchair.com/bitcoin',
                'rate_limit': 5  # requests per second
            },
            'blockcypher': {
                'base_url': 'https://api.blockcypher.com/v1/btc/main',
                'rate_limit': 3
            }
        }
    
    async def monitor_addresses_batch(self, addresses):
        # Use Blockchair for efficient batch processing
        address_str = '+'.join(addresses)
        url = f"{self.apis['blockchair']['base_url']}/addresses/balances"
        params = {'addresses': address_str}
        
        response = await self.session.get(url, params=params)
        return response.json()
```

## Python architecture and core libraries

The system should use an event-driven architecture with async processing for efficiency:

**Essential Libraries:**
- `bitcoinlib` - Comprehensive Bitcoin library with wallet management
- `asyncio` + `aiohttp` - Async HTTP operations for API calls
- `SQLAlchemy` + `asyncpg` - Database ORM with async PostgreSQL support
- `APScheduler` - Task scheduling for periodic monitoring
- `structlog` - Structured logging for production systems

**Project Structure:**
```
bitcoin_monitor/
├── src/
│   ├── core/
│   │   ├── blockchain.py      # Blockchain interface
│   │   ├── address_manager.py # Address management
│   │   └── transaction_parser.py
│   ├── services/
│   │   ├── monitoring_service.py
│   │   ├── notification_service.py
│   │   └── api_service.py
│   ├── data/
│   │   ├── models.py          # Database models
│   │   └── repositories.py    # Data access layer
│   └── config/
│       └── settings.py
```

## Database design with TimescaleDB

TimescaleDB (PostgreSQL extension) provides the best balance of SQL compatibility and time-series performance:

```sql
-- Core wallet tracking schema
CREATE TABLE wallets (
    wallet_id SERIAL PRIMARY KEY,
    address VARCHAR(62) UNIQUE NOT NULL,
    wallet_type VARCHAR(20) NOT NULL,
    is_vulnerable BOOLEAN DEFAULT TRUE,
    last_activity TIMESTAMPTZ,
    current_balance BIGINT DEFAULT 0,
    metadata JSONB
);

-- Transaction monitoring with time-series optimization
CREATE TABLE transactions (
    tx_id BIGSERIAL,
    txhash VARCHAR(64) NOT NULL,
    block_time TIMESTAMPTZ NOT NULL,
    wallet_address VARCHAR(62) NOT NULL,
    amount BIGINT NOT NULL,
    tx_type VARCHAR(10) NOT NULL,
    is_anomalous BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (tx_id, block_time)
);

-- Convert to hypertable for TimescaleDB
SELECT create_hypertable('transactions', 'block_time');

-- Wallet state snapshots for pattern analysis
CREATE TABLE wallet_states (
    wallet_address VARCHAR(62),
    snapshot_time TIMESTAMPTZ NOT NULL,
    balance BIGINT,
    tx_count_24h INTEGER,
    PRIMARY KEY (wallet_address, snapshot_time)
);
```

## Discord webhook implementation

Here's a robust Discord notification system with rate limiting:

```python
class DiscordWebhookManager:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.request_times = []
        self.max_requests_per_minute = 30  # Discord limit
        
    def create_embed(self, alert):
        color_map = {
            'LOW': 0x00ff00,      # Green
            'MEDIUM': 0xffff00,   # Yellow  
            'HIGH': 0xff8000,     # Orange
            'CRITICAL': 0xff0000  # Red
        }
        
        embed = {
            "title": f"🚨 {alert.title}",
            "description": alert.description,
            "color": color_map.get(alert.severity, 0x808080),
            "timestamp": alert.timestamp.isoformat(),
            "fields": [
                {
                    "name": "Affected Wallets",
                    "value": str(len(alert.wallet_addresses)),
                    "inline": True
                },
                {
                    "name": "Total Value",
                    "value": f"{alert.total_value/100000000:.8f} BTC",
                    "inline": True
                }
            ]
        }
        return embed
    
    async def send_alert(self, alert):
        # Check rate limiting
        wait_time = self.check_rate_limit()
        if wait_time:
            await asyncio.sleep(wait_time)
            
        payload = {"embeds": [self.create_embed(alert)]}
        
        async with aiohttp.ClientSession() as session:
            response = await session.post(self.webhook_url, json=payload)
            return response.status == 204
```

## Alert logic for quantum emergency patterns

### Multiple dormant wallets moving simultaneously

This is the most concerning pattern suggesting potential quantum attack:

```python
class QuantumEmergencyDetector:
    def __init__(self):
        self.dormancy_threshold = timedelta(days=365)
        self.activity_window = timedelta(minutes=30)
        self.min_wallets_threshold = 5
        
    def detect_dormant_wallet_surge(self, recent_activities):
        dormant_activities = []
        
        for activity in recent_activities:
            time_since_last = datetime.now() - activity.last_activity
            if time_since_last > self.dormancy_threshold:
                dormant_activities.append(activity)
        
        if len(dormant_activities) >= self.min_wallets_threshold:
            # Check if activities are clustered in time
            activity_times = [act.transaction_time for act in dormant_activities]
            time_spread = max(activity_times) - min(activity_times)
            
            if time_spread <= self.activity_window:
                return {
                    "alert": True,
                    "severity": "CRITICAL",
                    "wallet_count": len(dormant_activities),
                    "pattern": "dormant_wallet_surge"
                }
```

### Statistical anomaly detection

Use Z-score analysis to detect unusual transaction patterns:

```python
def detect_volume_anomalies(self, wallet_address, historical_data):
    volumes = [d['volume'] for d in historical_data[-144:]]  # 24 hours
    
    volume_mean = np.mean(volumes[:-1])
    volume_std = np.std(volumes[:-1])
    current_volume = volumes[-1]
    
    volume_zscore = (current_volume - volume_mean) / (volume_std + 1e-8)
    
    if abs(volume_zscore) > 3.0:
        return {
            "alert": True,
            "severity": "HIGH" if abs(volume_zscore) > 4.0 else "MEDIUM",
            "pattern": "statistical_anomaly",
            "zscore": volume_zscore
        }
```

## Tracking dormant wallets

Focus on wallets that haven't moved in years, as these are prime targets:

```python
# SQL query to identify dormant vulnerable wallets
WITH dormant_wallets AS (
    SELECT address, last_activity, current_balance
    FROM wallets 
    WHERE last_activity < NOW() - INTERVAL '5 years'
    AND is_vulnerable = TRUE
    AND current_balance > 1000000000  -- 10+ BTC
)
SELECT * FROM dormant_wallets
ORDER BY current_balance DESC;
```

## Complete monitoring system implementation

Here's a production-ready monitoring daemon:

```python
class BitcoinMonitoringSystem:
    def __init__(self, config):
        self.config = config
        self.db_pool = None
        self.scheduler = AsyncIOScheduler()
        self.discord = DiscordWebhookManager(config.discord_webhook)
        
    async def monitor_all_addresses(self):
        addresses = await self.get_monitored_addresses()
        
        # Process in batches for efficiency
        for batch in chunks(addresses, self.config.batch_size):
            results = await self.check_address_batch(batch)
            
            for change in results:
                if self.is_quantum_emergency(change):
                    await self.discord.send_alert(
                        self.create_critical_alert(change)
                    )
    
    def is_quantum_emergency(self, changes):
        # Multiple dormant wallets moving
        if len(changes) >= 5:
            dormant_count = sum(1 for c in changes 
                              if c['dormancy_days'] > 365)
            if dormant_count >= 3:
                return True
        
        # Large value movements
        total_value = sum(c['amount'] for c in changes)
        if total_value > 10000000000:  # 100+ BTC
            return True
            
        return False
```

## Performance optimization strategies

1. **Batch Processing**: Process addresses in groups of 50-100 to minimize API calls
2. **Caching**: Use Redis to cache address data with dynamic TTL based on activity
3. **Rate Limiting**: Implement client-side rate limiting to respect API limits
4. **Connection Pooling**: Maintain persistent connections for database and API calls

## Security and privacy considerations

- Never store private keys or sensitive wallet information
- Hash address data in logs for privacy
- Use environment variables for API keys and webhooks
- Implement proper access controls for the monitoring dashboard
- Consider running the system on a dedicated server with firewall rules

## Getting started

1. **Set up infrastructure**: Deploy PostgreSQL with TimescaleDB extension
2. **Configure APIs**: Register for BlockCypher and Blockchair API keys
3. **Initialize database**: Run schema creation scripts
4. **Import historical data**: Scan early blocks for P2PK addresses
5. **Start monitoring**: Deploy the monitoring daemon with supervisor/systemd
6. **Configure alerts**: Set up Discord webhook and alert thresholds

This system provides comprehensive monitoring for quantum-vulnerable Bitcoin wallets, enabling early detection of potential quantum computing attacks while maintaining performance and reliability at scale.
