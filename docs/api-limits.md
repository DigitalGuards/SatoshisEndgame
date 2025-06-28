# API Limits and Monitoring Strategy

## BlockCypher Free Tier Limits

- **1,000** requests per day
- **100** requests per hour  
- **3** requests per second

## Problem

With 1,000+ dormant addresses to monitor:
- Checking every 5 minutes = 288,000 requests/day (288x over limit!)
- Checking hourly = 24,000 requests/day (24x over limit!)

## Solution: Tiered Risk-Based Monitoring

We prioritize addresses based on risk score:

### Tier 1: Critical (95+ risk score)
- **50 addresses** maximum
- Check **every hour** (24 checks/day)
- 1,200 requests/day

### Tier 2: High (80-94 risk score)  
- **200 addresses** maximum
- Check **every 4 hours** (6 checks/day)
- 1,200 requests/day

### Tier 3: Medium (60-79 risk score)
- **600 addresses** maximum
- Check **once daily** (1 check/day)
- 600 requests/day

**Total: 3,000 requests/day** (uses 300% of daily limit across 3 days)

## Risk Score Calculation

Risk score (0-100) based on:
- **Balance** (up to 40 points): Higher balance = higher risk
- **Dormancy** (up to 40 points): Longer dormancy = higher risk  
- **Vulnerability type** (up to 20 points): P2PK > Reused P2PKH > Dormant

## Configuration

Edit `.env` to adjust limits:

```bash
# Maximum addresses per tier
CRITICAL_TIER_SIZE=50
HIGH_TIER_SIZE=200
MEDIUM_TIER_SIZE=600
```

## Recommendations

1. **For comprehensive monitoring**: Get a paid BlockCypher plan or use Blockchair with API key
2. **For free tier**: Focus on highest-risk addresses only
3. **Alternative**: Set up your own Bitcoin node for unlimited queries

## Usage

```bash
# Analyze your addresses and get recommendations
./venv/bin/python scripts/optimize_monitoring.py

# Import only high-risk addresses (80+ risk score)
./venv/bin/python scripts/import_dormant_addresses.py --min-balance 50
```