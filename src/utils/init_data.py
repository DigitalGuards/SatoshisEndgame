"""Initialize database with known vulnerable addresses"""

import asyncio
import csv
from pathlib import Path

import structlog
from sqlalchemy import select

from src.config import settings
from src.core.address_manager import AddressVulnerabilityDetector
from src.data.database import db
from src.data.models import Wallet

logger = structlog.get_logger()


async def load_vulnerable_addresses():
    """Load vulnerable addresses from CSV file"""
    csv_path = Path("data/vulnerable_addresses.txt")
    
    if not csv_path.exists():
        logger.warning("Vulnerable addresses file not found", path=str(csv_path))
        return []
    
    addresses = []
    with open(csv_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split(',')
            if len(parts) >= 2:
                addresses.append({
                    'address': parts[0].strip(),
                    'vulnerability_type': parts[1].strip(),
                    'notes': parts[2].strip() if len(parts) > 2 else ''
                })
    
    return addresses


async def initialize_sample_data():
    """Initialize database with sample vulnerable addresses"""
    logger.info("Initializing sample data")
    
    # Initialize database
    await db.initialize()
    await db.create_tables()
    
    # Load addresses
    addresses = await load_vulnerable_addresses()
    
    if not addresses:
        logger.warning("No addresses to load")
        return
    
    detector = AddressVulnerabilityDetector()
    
    async with db.get_session() as session:
        added = 0
        for addr_info in addresses:
            # Check if already exists
            result = await session.execute(
                select(Wallet).where(Wallet.address == addr_info['address'])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.debug("Address already exists", address=addr_info['address'])
                continue
            
            # Create wallet record
            wallet = Wallet(
                address=addr_info['address'],
                wallet_type="P2PK" if addr_info['vulnerability_type'] == "P2PK" else "P2PKH",
                vulnerability_type=addr_info['vulnerability_type'],
                is_vulnerable=True,
                is_active=True,
                current_balance=5000000000,  # 50 BTC placeholder
                risk_score=detector.calculate_risk_score(
                    5000000000,
                    3650,  # 10 years dormant
                    addr_info['vulnerability_type']
                ),
                dormancy_days=3650,
                metadata={'notes': addr_info['notes']}
            )
            
            session.add(wallet)
            added += 1
        
        await session.commit()
        
    logger.info(f"Added {added} vulnerable addresses to database")
    await db.close()


if __name__ == "__main__":
    asyncio.run(initialize_sample_data())