"""BitInfoCharts scraper for dormant Bitcoin addresses"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger()


class BitInfoChartsScraper:
    """Scrape dormant Bitcoin addresses from BitInfoCharts"""
    
    BASE_URL = "https://bitinfocharts.com"
    DORMANT_URL = f"{BASE_URL}/top-100-dormant_8y-bitcoin-addresses.html"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def fetch_page(self, url: str) -> str:
        """Fetch HTML content from URL"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async with context manager.")
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with self.session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.text()
            
    def parse_address_row(self, row) -> Optional[Dict]:
        """Parse a single table row containing address data"""
        try:
            cells = row.find_all('td')
            if len(cells) < 10:  # Expected columns
                return None
                
            # Extract data from cells
            rank = cells[0].text.strip()
            
            # Address cell may contain wallet label and address
            address_cell = cells[1]
            
            # Find all links in the address cell
            address_links = address_cell.find_all('a')
            
            # The actual address is usually the last link
            address = None
            wallet_label = None
            
            if address_links:
                # Check each link for Bitcoin address pattern
                for link in address_links:
                    link_text = link.text.strip()
                    # Bitcoin addresses start with 1, 3, or bc1
                    if re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$', link_text):
                        address = link_text
                        break
                        
                # If we found an address and there's another link, it might be the wallet label
                if address and len(address_links) > 1:
                    wallet_label = address_links[0].text.strip() if address_links[0].text.strip() != address else None
            
            if not address:
                return None
                
            # Parse balance (remove commas and "BTC" suffix)
            balance_text = cells[2].text.strip()
            balance_match = re.search(r'([\d,]+\.?\d*)', balance_text)
            if not balance_match:
                return None
            balance_btc = float(balance_match.group(1).replace(',', ''))
            
            # Parse percentage
            percentage_text = cells[3].text.strip()
            percentage_match = re.search(r'([\d.]+)', percentage_text)
            percentage = float(percentage_match.group(1)) if percentage_match else 0.0
            
            # Parse dates and transaction counts
            first_in = cells[4].text.strip()
            last_in = cells[5].text.strip()
            ins = cells[6].text.strip()
            first_out = cells[7].text.strip()
            last_out = cells[8].text.strip()
            outs = cells[9].text.strip()
            
            # Clean up date strings (remove "UTC" suffix if present)
            first_in = first_in.replace(' UTC', '').strip()
            last_in = last_in.replace(' UTC', '').strip()
            first_out = first_out.replace(' UTC', '').strip()
            last_out = last_out.replace(' UTC', '').strip()
            
            # Calculate dormancy (use last_out if available, otherwise last_in)
            last_activity = last_out if last_out and last_out != '-' else last_in
            
            return {
                'rank': int(rank),
                'address': address,
                'wallet_label': wallet_label,
                'balance_btc': balance_btc,
                'percentage_supply': percentage,
                'first_in': first_in,
                'last_in': last_in,
                'ins': ins,
                'first_out': first_out,
                'last_out': last_out,
                'outs': outs,
                'last_activity': last_activity
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse row: {e}, row text: {row.text[:100]}")
            return None
            
    async def scrape_dormant_addresses(self, pages: int = 1) -> List[Dict]:
        """Scrape dormant addresses from BitInfoCharts
        
        Args:
            pages: Number of pages to scrape (each page has 100 addresses)
            
        Returns:
            List of address dictionaries with balance and dormancy info
        """
        all_addresses = []
        
        for page in range(1, pages + 1):
            try:
                # Construct URL for specific page
                if page == 1:
                    url = self.DORMANT_URL
                else:
                    # BitInfoCharts uses format: .../top-100-dormant_8y-bitcoin-addresses-2.html
                    url = self.DORMANT_URL.replace('.html', f'-{page}.html')
                    
                logger.info(f"Fetching page {page}: {url}")
                html = await self.fetch_page(url)
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find the main table containing addresses
                # BitInfoCharts uses different table structures, try multiple approaches
                
                # Method 1: Look for table with specific class combinations
                main_table = None
                for table_class in ['table table-condensed', 'table', 'maintable']:
                    tables = soup.find_all('table', class_=table_class)
                    if tables:
                        # Look for the table with the most rows
                        for table in tables:
                            row_count = len(table.find_all('tr'))
                            if row_count > 50:  # Should have at least 50+ rows for 100 addresses
                                main_table = table
                                break
                        if main_table:
                            break
                
                # Method 2: If no table found by class, look for any table with many rows
                if not main_table:
                    all_tables = soup.find_all('table')
                    for table in all_tables:
                        rows = table.find_all('tr')
                        # Check if this looks like our data table (50+ rows, 10+ columns)
                        if len(rows) > 50:
                            sample_row = rows[1] if len(rows) > 1 else rows[0]
                            cells = sample_row.find_all(['td', 'th'])
                            if len(cells) >= 10:
                                main_table = table
                                break
                
                # Method 3: Look for table inside specific containers
                if not main_table:
                    for container_class in ['table-responsive', 'content', 'main-content']:
                        containers = soup.find_all('div', class_=container_class)
                        for container in containers:
                            tables = container.find_all('table')
                            for table in tables:
                                rows = table.find_all('tr')
                                if len(rows) > 50:
                                    main_table = table
                                    break
                            if main_table:
                                break
                
                if not main_table:
                    logger.warning(f"No suitable table found on page {page}")
                    continue
                
                # Find all data rows
                rows = []
                
                # Try to find tbody first
                tbody = main_table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                else:
                    # Get all rows and filter out header rows
                    all_rows = main_table.find_all('tr')
                    for row in all_rows:
                        # Skip rows that look like headers (contain th elements)
                        if row.find('th'):
                            continue
                        # Skip rows with too few cells
                        if len(row.find_all('td')) >= 10:
                            rows.append(row)
                    
                logger.info(f"Found {len(rows)} data rows on page {page}")
                
                page_addresses = []
                for idx, row in enumerate(rows):
                    address_data = self.parse_address_row(row)
                    if address_data:
                        page_addresses.append(address_data)
                    else:
                        # Log failed parse for debugging
                        if idx < 5:  # Only log first few failures
                            logger.debug(f"Failed to parse row {idx + 1} on page {page}")
                        
                logger.info(f"Page {page}: Parsed {len(page_addresses)} addresses from {len(rows)} rows")
                all_addresses.extend(page_addresses)
                
                # Add delay between requests to be respectful
                if page < pages:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error scraping page {page}: {e}")
                continue
                
        return all_addresses
        
    async def scrape_and_save(self, output_file: str = "data/scraped_dormant_addresses.csv", pages: int = 5):
        """Scrape addresses and save to CSV file"""
        import csv
        from pathlib import Path
        
        addresses = await self.scrape_dormant_addresses(pages=pages)
        
        if not addresses:
            logger.warning("No addresses scraped")
            return
            
        # Ensure data directory exists
        Path(output_file).parent.mkdir(exist_ok=True)
        
        # Define fieldnames in specific order
        fieldnames = [
            'rank', 'address', 'wallet_label', 'balance_btc', 'percentage_supply',
            'first_in', 'last_in', 'ins', 'first_out', 'last_out', 'outs', 'last_activity'
        ]
        
        # Write to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(addresses)
                
        logger.info(f"Saved {len(addresses)} addresses to {output_file}")
        

async def main():
    """Command-line interface for BitInfoCharts scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape dormant Bitcoin addresses from BitInfoCharts")
    parser.add_argument(
        "--pages", 
        type=int, 
        default=5, 
        help="Number of pages to scrape (each page has 100 addresses)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="data/scraped_dormant_addresses.csv",
        help="Output CSV file path"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    import logging
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    async with BitInfoChartsScraper() as scraper:
        await scraper.scrape_and_save(output_file=args.output, pages=args.pages)
        
        # Also print summary statistics
        print(f"\nScraping complete! Check {args.output} for results.")
        print(f"Attempted to scrape {args.pages} pages (up to {args.pages * 100} addresses)")


if __name__ == "__main__":
    asyncio.run(main())