# SatoshisEndgame Scripts

## Dormant Address Collection

### 1. Scraping Dormant Addresses

The `scrape_dormant_addresses.py` script collects dormant Bitcoin addresses from BitInfoCharts:

```bash
# Scrape 1000 addresses (10 pages x 100 addresses/page)
./venv/bin/python scripts/scrape_dormant_addresses.py

# Output: data/dormant_addresses.csv
```

Features:
- Scrapes addresses that haven't moved in 8+ years
- Collects balance, dormancy period, and transaction history
- Saves to CSV format with all metadata
- Rate-limited to be respectful to the server

### 2. Importing to Database

The `import_dormant_addresses.py` script loads scraped addresses into the monitoring database:

```bash
# Import with default settings (10 BTC minimum)
./venv/bin/python scripts/import_dormant_addresses.py

# Import all addresses (no minimum balance)
./venv/bin/python scripts/import_dormant_addresses.py --min-balance 0

# Import from custom CSV
./venv/bin/python scripts/import_dormant_addresses.py --csv path/to/addresses.csv
```

Features:
- Skips addresses below configurable balance threshold
- Updates existing addresses with new data
- Calculates risk scores based on balance and dormancy
- Preserves metadata from scraping

## Workflow

1. **Scrape addresses**: Run the scraper to collect dormant addresses
2. **Review CSV**: Check `data/dormant_addresses.csv` for collected data
3. **Import to database**: Load addresses for monitoring
4. **Start monitoring**: Run `./venv/bin/python -m src.cli monitor`

The monitoring system will then:
- Track these high-value dormant addresses
- Alert on any balance changes
- Detect coordinated movements (potential quantum attack)
- Calculate risk scores based on dormancy and balance