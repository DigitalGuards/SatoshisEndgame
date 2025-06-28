"""Improved BitInfoCharts scraper with better HTML parsing"""

import asyncio
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import aiohttp
from bs4 import BeautifulSoup, Tag
import structlog

logger = structlog.get_logger()


class BitInfoChartsScraperV2:
    """Improved scraper for BitInfoCharts with robust HTML parsing"""
    
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        async with self.session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.text()
            
    def extract_address_from_cell(self, cell: Tag) -> Tuple[Optional[str], Optional[str]]:
        """Extract Bitcoin address and wallet label from table cell"""
        address = None
        wallet_label = None
        
        # Find all links in the cell
        links = cell.find_all('a')
        
        if not links:
            # Sometimes address might be plain text
            cell_text = cell.text.strip()
            if re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$', cell_text):
                return cell_text, None
            return None, None
        
        # Process links to find address and label
        for link in links:
            link_text = link.text.strip()
            href = link.get('href', '')
            
            # Check if this is a Bitcoin address
            if re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$', link_text):
                address = link_text
            # Check if href points to an address page
            elif '/bitcoin/address/' in href:
                # Extract address from href
                match = re.search(r'/bitcoin/address/([13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})', href)
                if match:
                    address = match.group(1)
                    # This link text might be the wallet label
                    if link_text != address:
                        wallet_label = link_text
            # This might be a wallet label
            elif not address and link_text:
                wallet_label = link_text
        
        return address, wallet_label
    
    def parse_number(self, text: str) -> Optional[float]:
        """Parse number from text, handling commas and units"""
        # Remove any BTC suffix
        text = text.replace(' BTC', '').strip()
        # Remove commas
        text = text.replace(',', '')
        # Try to extract number
        match = re.search(r'([-+]?\d*\.?\d+)', text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
    
    def parse_address_row(self, row: Tag) -> Optional[Dict]:
        """Parse a single table row containing address data"""
        try:
            cells = row.find_all('td')
            
            # BitInfoCharts tables typically have 10-11 columns
            if len(cells) < 10:
                return None
            
            # Parse rank
            rank_text = cells[0].text.strip()
            if not rank_text.isdigit():
                return None
            rank = int(rank_text)
            
            # Extract address and wallet label
            address, wallet_label = self.extract_address_from_cell(cells[1])
            if not address:
                return None
            
            # Parse balance
            balance_btc = self.parse_number(cells[2].text)
            if balance_btc is None:
                return None
            
            # Parse percentage
            percentage = self.parse_number(cells[3].text.replace('%', ''))
            
            # Parse transaction data
            first_in = cells[4].text.strip().replace(' UTC', '')
            last_in = cells[5].text.strip().replace(' UTC', '')
            ins = cells[6].text.strip()
            first_out = cells[7].text.strip().replace(' UTC', '')
            last_out = cells[8].text.strip().replace(' UTC', '')
            outs = cells[9].text.strip()
            
            # Determine last activity
            if last_out and last_out != '-' and last_out != '':
                last_activity = last_out
            elif last_in and last_in != '-' and last_in != '':
                last_activity = last_in
            else:
                last_activity = first_in
            
            return {
                'rank': rank,
                'address': address,
                'wallet_label': wallet_label,
                'balance_btc': balance_btc,
                'percentage_supply': percentage if percentage else 0.0,
                'first_in': first_in,
                'last_in': last_in,
                'ins': ins,
                'first_out': first_out,
                'last_out': last_out,
                'outs': outs,
                'last_activity': last_activity
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse row: {e}")
            return None
    
    def find_data_table(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the main data table in the page"""
        
        # Strategy 1: Look for table by analyzing content
        all_tables = soup.find_all('table')
        
        for table in all_tables:
            # Count rows that look like data rows
            data_row_count = 0
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 10:
                    # Check if first cell contains a number (rank)
                    first_cell = cells[0].text.strip()
                    if first_cell.isdigit():
                        data_row_count += 1
            
            # If we found a table with many data rows, this is likely our table
            if data_row_count >= 50:
                logger.info(f"Found data table with {data_row_count} data rows")
                return table
        
        # Strategy 2: Look for largest table
        if all_tables:
            largest_table = max(all_tables, key=lambda t: len(t.find_all('tr')))
            row_count = len(largest_table.find_all('tr'))
            if row_count > 50:
                logger.info(f"Using largest table with {row_count} rows")
                return largest_table
        
        return None
    
    async def scrape_dormant_addresses(self, pages: int = 1) -> List[Dict]:
        """Scrape dormant addresses from BitInfoCharts"""
        all_addresses = []
        
        for page in range(1, pages + 1):
            try:
                # Construct URL
                if page == 1:
                    url = self.DORMANT_URL
                else:
                    url = self.DORMANT_URL.replace('.html', f'-{page}.html')
                
                logger.info(f"Fetching page {page}: {url}")
                html = await self.fetch_page(url)
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find the data table
                data_table = self.find_data_table(soup)
                
                if not data_table:
                    logger.warning(f"Could not find data table on page {page}")
                    continue
                
                # Extract all rows
                rows = data_table.find_all('tr')
                
                # Parse each row
                page_addresses = []
                for row in rows:
                    # Skip header rows
                    if row.find('th'):
                        continue
                        
                    address_data = self.parse_address_row(row)
                    if address_data:
                        page_addresses.append(address_data)
                
                logger.info(f"Page {page}: Successfully parsed {len(page_addresses)} addresses")
                all_addresses.extend(page_addresses)
                
                # Respectful delay
                if page < pages:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error scraping page {page}: {e}")
                continue
        
        logger.info(f"Total addresses scraped: {len(all_addresses)}")
        return all_addresses
    
    async def scrape_and_save(self, output_file: str = "data/scraped_dormant_addresses_v2.csv", pages: int = 5):
        """Scrape addresses and save to CSV file"""
        import csv
        from pathlib import Path
        
        addresses = await self.scrape_dormant_addresses(pages=pages)
        
        if not addresses:
            logger.warning("No addresses scraped")
            return
        
        # Ensure directory exists
        Path(output_file).parent.mkdir(exist_ok=True)
        
        # Define fieldnames
        fieldnames = [
            'rank', 'address', 'wallet_label', 'balance_btc', 'percentage_supply',
            'first_in', 'last_in', 'ins', 'first_out', 'last_out', 'outs', 'last_activity'
        ]
        
        # Write CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(addresses)
        
        logger.info(f"Saved {len(addresses)} addresses to {output_file}")
        
        # Print summary
        print(f"\nScraping Summary:")
        print(f"- Total addresses: {len(addresses)}")
        print(f"- Pages scraped: {pages}")
        print(f"- Average per page: {len(addresses) / pages:.1f}")
        print(f"- Output file: {output_file}")


async def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Improved BitInfoCharts scraper")
    parser.add_argument("--pages", type=int, default=5, help="Number of pages to scrape")
    parser.add_argument("--output", type=str, default="data/scraped_dormant_addresses_v2.csv", help="Output file")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    import logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async with BitInfoChartsScraperV2() as scraper:
        await scraper.scrape_and_save(output_file=args.output, pages=args.pages)


if __name__ == "__main__":
    asyncio.run(main())