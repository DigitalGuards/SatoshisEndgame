# BitInfoCharts Scrapers

This directory contains scrapers for extracting dormant Bitcoin addresses from BitInfoCharts.

## Features

- Scrapes dormant Bitcoin addresses (8+ years inactive) from BitInfoCharts
- Handles multiple pages (100 addresses per page)
- Extracts wallet labels when available
- Robust HTML parsing with multiple fallback strategies
- Respectful rate limiting between requests

## Usage

### Basic Usage

```bash
# Scrape first 5 pages (500 addresses)
python -m src.scrapers.bitinfocharts_scraper

# Or use the improved v2 scraper
python -m src.scrapers.bitinfocharts_scraper_v2
```

### Command Line Options

```bash
# Scrape 10 pages
python -m src.scrapers.bitinfocharts_scraper_v2 --pages 10

# Custom output file
python -m src.scrapers.bitinfocharts_scraper_v2 --output data/my_addresses.csv

# Enable debug logging
python -m src.scrapers.bitinfocharts_scraper_v2 --debug
```

### Programmatic Usage

```python
import asyncio
from src.scrapers import BitInfoChartsScraperV2

async def scrape_addresses():
    async with BitInfoChartsScraperV2() as scraper:
        addresses = await scraper.scrape_dormant_addresses(pages=3)
        
        for addr in addresses[:5]:
            print(f"{addr['rank']}: {addr['address']} - {addr['balance_btc']} BTC")
            
asyncio.run(scrape_addresses())
```

## Output Format

The scraper outputs CSV files with the following columns:

- `rank`: Position in the dormant addresses list
- `address`: Bitcoin address
- `wallet_label`: Optional label (e.g., "Mt. Gox", "Silk Road") 
- `balance_btc`: Current balance in BTC
- `percentage_supply`: Percentage of total Bitcoin supply
- `first_in`: Date of first incoming transaction
- `last_in`: Date of last incoming transaction
- `ins`: Number of incoming transactions
- `first_out`: Date of first outgoing transaction
- `last_out`: Date of last outgoing transaction
- `outs`: Number of outgoing transactions
- `last_activity`: Most recent activity date

## Troubleshooting

If the scraper is not finding all 100 addresses per page:

1. **Use the v2 scraper**: It has improved HTML parsing logic
2. **Enable debug mode**: `--debug` flag shows detailed parsing information
3. **Run the test script**: `python -m src.scrapers.test_scraper` analyzes page structure
4. **Check for changes**: BitInfoCharts may have updated their HTML structure

## Implementation Notes

### Why Two Versions?

- `bitinfocharts_scraper.py`: Original implementation with standard parsing
- `bitinfocharts_scraper_v2.py`: Improved version with:
  - Better table detection logic
  - More robust address extraction
  - Enhanced error handling
  - Detailed logging

### Key Challenges Addressed

1. **Dynamic HTML Structure**: Tables may have different classes or no classes
2. **Mixed Content**: Address cells may contain wallet labels and links
3. **Data Validation**: Ensures only valid Bitcoin addresses are extracted
4. **Rate Limiting**: Respectful delays between page requests

### Table Detection Strategy

The v2 scraper uses multiple strategies to find the data table:

1. **Content Analysis**: Looks for tables with many rows containing numeric ranks
2. **Size Heuristic**: Falls back to the largest table if needed
3. **Row Validation**: Ensures rows have the expected column structure

This multi-strategy approach ensures reliability even if BitInfoCharts changes their HTML structure.