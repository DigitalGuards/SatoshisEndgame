"""Test script to diagnose BitInfoCharts scraper issues"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger()


async def analyze_page_structure():
    """Analyze the HTML structure of BitInfoCharts page to debug parsing issues"""
    
    url = "https://bitinfocharts.com/top-100-dormant_8y-bitcoin-addresses.html"
    
    async with aiohttp.ClientSession() as session:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            html = await response.text()
            
    soup = BeautifulSoup(html, 'html.parser')
    
    print("=== PAGE STRUCTURE ANALYSIS ===\n")
    
    # Find all tables
    all_tables = soup.find_all('table')
    print(f"Total tables found: {len(all_tables)}")
    
    # Analyze each table
    for i, table in enumerate(all_tables):
        print(f"\n--- Table {i + 1} ---")
        
        # Check table classes
        classes = table.get('class', [])
        print(f"Classes: {classes}")
        
        # Count rows
        all_rows = table.find_all('tr')
        print(f"Total rows: {len(all_rows)}")
        
        # Check for tbody
        tbody = table.find('tbody')
        if tbody:
            tbody_rows = tbody.find_all('tr')
            print(f"Rows in tbody: {len(tbody_rows)}")
        
        # Analyze first few rows
        print("\nFirst 3 rows structure:")
        for j, row in enumerate(all_rows[:3]):
            cells = row.find_all(['td', 'th'])
            print(f"  Row {j + 1}: {len(cells)} cells")
            
            # Show first cell content to identify header rows
            if cells:
                first_cell = cells[0].text.strip()[:30]
                print(f"    First cell: '{first_cell}'")
                
        # Check if this might be our data table
        if len(all_rows) > 50:
            print("\n*** This could be our data table! ***")
            
            # Count data rows (rows with td elements)
            data_rows = [row for row in all_rows if row.find_all('td') and len(row.find_all('td')) >= 10]
            print(f"Data rows with 10+ cells: {len(data_rows)}")
            
            # Sample a data row
            if data_rows:
                sample_row = data_rows[0]
                cells = sample_row.find_all('td')
                print(f"\nSample row structure ({len(cells)} cells):")
                for k, cell in enumerate(cells):
                    cell_text = cell.text.strip()[:40]
                    # Check for links
                    links = cell.find_all('a')
                    link_info = f" [{len(links)} link(s)]" if links else ""
                    print(f"  Cell {k + 1}: '{cell_text}'{link_info}")
                    
                    # Show link hrefs for address cell
                    if k == 1 and links:
                        for link in links:
                            print(f"    Link text: '{link.text.strip()}'")
                            print(f"    Link href: '{link.get('href', 'N/A')}'")
    
    # Also check for specific div containers that might wrap the table
    print("\n=== CHECKING FOR TABLE CONTAINERS ===")
    
    # Look for divs with specific classes that might contain our table
    for class_name in ['table-responsive', 'content', 'main-content', 'container']:
        divs = soup.find_all('div', class_=class_name)
        if divs:
            print(f"\nFound {len(divs)} div(s) with class '{class_name}'")
            for div in divs:
                tables_in_div = div.find_all('table')
                if tables_in_div:
                    print(f"  Contains {len(tables_in_div)} table(s)")


async def test_scraper_on_single_page():
    """Test the actual scraper on a single page"""
    from bitinfocharts_scraper import BitInfoChartsScraper
    
    print("\n\n=== TESTING SCRAPER ===\n")
    
    async with BitInfoChartsScraper() as scraper:
        addresses = await scraper.scrape_dormant_addresses(pages=1)
        
        print(f"Scraped {len(addresses)} addresses")
        
        if addresses:
            print("\nFirst 5 addresses:")
            for addr in addresses[:5]:
                print(f"  Rank {addr['rank']}: {addr['address']} - {addr['balance_btc']} BTC")
                if addr.get('wallet_label'):
                    print(f"    Label: {addr['wallet_label']}")
                    
            print("\nLast 5 addresses:")
            for addr in addresses[-5:]:
                print(f"  Rank {addr['rank']}: {addr['address']} - {addr['balance_btc']} BTC")
                if addr.get('wallet_label'):
                    print(f"    Label: {addr['wallet_label']}")


async def main():
    """Run all diagnostic tests"""
    print("BitInfoCharts Scraper Diagnostic Tool\n")
    
    # First analyze page structure
    await analyze_page_structure()
    
    # Then test the scraper
    await test_scraper_on_single_page()


if __name__ == "__main__":
    asyncio.run(main())