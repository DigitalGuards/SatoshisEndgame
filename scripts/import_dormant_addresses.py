#!/usr/bin/env python3
"""
Import scraped dormant addresses into the SatoshisEndgame database
"""

import asyncio
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import structlog
from sqlalchemy import select

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config import settings
from src.core.address_manager import AddressVulnerabilityDetector
from src.data.database import db
from src.data.models import Wallet

logger = structlog.get_logger()


async def import_dormant_addresses(csv_file: str = "data/truly_dormant_addresses.csv"):
    """Import dormant addresses from CSV file"""
    logger.info("Starting dormant address import", file=csv_file)
    
    # Initialize database
    await db.initialize()
    
    csv_path = Path(csv_file)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return
    
    detector = AddressVulnerabilityDetector()
    imported_count = 0
    skipped_count = 0
    updated_count = 0
    
    async with db.get_session() as session:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    address = row['address']
                    balance_btc = float(row['balance_btc'])
                    dormancy_years = float(row['dormancy_years'])
                    
                    # Skip if balance too low (configurable threshold)
                    if balance_btc < settings.min_balance_threshold_btc:
                        skipped_count += 1
                        continue
                    
                    # Check if address already exists
                    result = await session.execute(
                        select(Wallet).where(Wallet.address == address)
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        # Update existing record with scraped data
                        existing.current_balance = int(balance_btc * 100_000_000)  # Convert to satoshis
                        existing.dormancy_days = int(dormancy_years * 365.25)
                        
                        # Recalculate risk score with real data
                        existing.risk_score = detector.calculate_risk_score(
                            existing.current_balance,
                            existing.dormancy_days,
                            existing.vulnerability_type or "DORMANT"
                        )
                        
                        # Parse last activity date
                        if row['last_activity'] and row['last_activity'] != 'None':
                            existing.last_activity = datetime.fromisoformat(row['last_activity'])
                        
                        updated_count += 1
                        logger.debug(f"Updated existing address", 
                                   address=address[:10] + "...",
                                   balance_btc=balance_btc)
                    else:
                        # Determine vulnerability type
                        is_vulnerable, vuln_type = detector.is_address_vulnerable(address)
                        
                        # For dormant addresses, we consider them vulnerable
                        if dormancy_years >= 8:
                            is_vulnerable = True
                            vuln_type = vuln_type or "DORMANT_8Y"
                        
                        # Create new wallet record
                        wallet = Wallet(
                            address=address,
                            wallet_type="P2PKH" if address.startswith("1") else "P2SH",
                            vulnerability_type=vuln_type,
                            is_vulnerable=is_vulnerable,
                            is_active=True,
                            current_balance=int(balance_btc * 100_000_000),  # Convert to satoshis
                            dormancy_days=int(dormancy_years * 365.25),
                            risk_score=detector.calculate_risk_score(
                                int(balance_btc * 100_000_000),
                                int(dormancy_years * 365.25),
                                vuln_type or "DORMANT"
                            ),
                            metadata={
                                'source': 'bitinfocharts',
                                'percentage_supply': row['percentage_supply'],
                                'first_in': row['first_in'],
                                'last_in': row['last_in'],
                                'ins_count': row['ins_count'],
                                'first_out': row.get('first_out', ''),
                                'last_out': row.get('last_out', ''),
                                'outs_count': row.get('outs_count', '0'),
                                'has_never_spent': row.get('has_never_spent', 'False')
                            }
                        )
                        
                        # Parse last activity date
                        if row['last_activity'] and row['last_activity'] != 'None':
                            wallet.last_activity = datetime.fromisoformat(row['last_activity'])
                        
                        session.add(wallet)
                        imported_count += 1
                        
                        if imported_count % 100 == 0:
                            logger.info(f"Progress: {imported_count} imported")
                            await session.commit()
                
                except Exception as e:
                    logger.error(f"Error importing address", 
                               address=row.get('address', 'unknown'),
                               error=str(e))
                    continue
        
        # Final commit
        await session.commit()
    
    await db.close()
    
    # Summary
    logger.info("Import completed")
    logger.info(f"  Imported: {imported_count} new addresses")
    logger.info(f"  Updated: {updated_count} existing addresses")
    logger.info(f"  Skipped: {skipped_count} (balance below {settings.min_balance_threshold_btc} BTC)")
    
    return {
        'imported': imported_count,
        'updated': updated_count,
        'skipped': skipped_count
    }


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import dormant Bitcoin addresses')
    parser.add_argument('--csv', default='data/truly_dormant_addresses.csv',
                       help='Path to CSV file (default: data/truly_dormant_addresses.csv)')
    parser.add_argument('--min-balance', type=float, default=None,
                       help='Override minimum balance threshold in BTC')
    
    args = parser.parse_args()
    
    # Override settings if specified
    if args.min_balance is not None:
        settings.min_balance_threshold_btc = args.min_balance
        logger.info(f"Using minimum balance threshold: {args.min_balance} BTC")
    
    # Run import
    results = await import_dormant_addresses(args.csv)
    
    if results:
        print(f"\nImport Summary:")
        print(f"  New addresses: {results['imported']}")
        print(f"  Updated addresses: {results['updated']}")
        print(f"  Skipped (low balance): {results['skipped']}")


if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    asyncio.run(main())