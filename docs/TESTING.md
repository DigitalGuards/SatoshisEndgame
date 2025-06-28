# Testing SatoshisEndgame

## Quick Start (No API Keys Required)

1. **Run the quick start script:**
```bash
./quickstart.sh
```

2. **Initialize the database:**
```bash
python -m src.cli init-db
```

3. **Load sample vulnerable addresses:**
```bash
python -m src.utils.init_data
```

4. **Test Discord webhook:**
```bash
./test_webhook.sh
```

5. **Start monitoring:**
```bash
python -m src.cli monitor
```

## Available Commands

### Check system status:
```bash
python -m src.cli status
```

### Test quantum emergency detection:
```bash
python -m src.cli test-detection
```

### Check if an address is vulnerable:
```bash
python -m src.cli check-address 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

## Working Without API Keys

The system can work without API keys using these free blockchain APIs:
- **Blockchain.info**: Basic queries, ~10 requests/minute
- **BlockCypher**: 3 requests/second on free tier
- **Blockchair**: 1,000 requests/day free

The system will automatically use whichever APIs are available.

## Testing Emergency Patterns

To trigger test alerts, the system looks for:
1. **5+ dormant wallets** (inactive >1 year) moving within 30 minutes
2. **Statistical anomalies** in transaction patterns
3. **High-value movements** from vulnerable addresses

## Monitoring Output

The system will show:
- Number of addresses being monitored
- Recent activities detected
- Emergency patterns identified
- Discord alerts sent

## Troubleshooting

### Database Issues
If using PostgreSQL and getting connection errors, switch to SQLite:
```bash
# In .env file:
DATABASE_URL=sqlite+aiosqlite:///satoshis_endgame.db
```

### API Rate Limits
If hitting rate limits, reduce batch size in .env:
```bash
BATCH_SIZE=10
```

## Next Steps

1. **Get API Keys** (optional but recommended):
   - BlockCypher: https://www.blockcypher.com/
   - Blockchair: https://blockchair.com/api

2. **Set up PostgreSQL** for production:
   - Install PostgreSQL 13+
   - Install TimescaleDB extension
   - Update DATABASE_URL in .env

3. **Import real vulnerable addresses**:
   - Scan blockchain for P2PK outputs
   - Identify reused P2PKH addresses
   - Import to database

## Security Notes

- The test webhook URL is public - use your own for production
- Never commit .env files with real API keys
- Consider running on a dedicated server for 24/7 monitoring