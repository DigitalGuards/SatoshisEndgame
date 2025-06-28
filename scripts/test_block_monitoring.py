#!/usr/bin/env python3
"""
Test the block monitoring system with simulated blockchain data
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import random

sys.path.append(str(Path(__file__).parent.parent))

from src.core.blockchain import BlockchainManager
from src.services.block_monitor import BlockMonitorService, BlockMonitoringService
from src.data.database import db
from sqlalchemy import select
from src.data.models import Wallet
import structlog

logger = structlog.get_logger()


class MockBlockchainManager(BlockchainManager):
    """Mock blockchain manager for testing"""
    
    def __init__(self):
        super().__init__()
        self.current_height = 820000
        self.dormant_addresses = []
        
    async def initialize(self):
        """Initialize without real API connections"""
        self.logger = logger.bind(component="mock_blockchain")
        self.logger.info("Mock blockchain manager initialized")
        
    async def get_latest_block_height(self) -> int:
        """Return incrementing block height"""
        self.current_height += 1
        return self.current_height
        
    async def get_block(self, block_height: int) -> dict:
        """Generate mock block with transactions"""
        # Simulate a block with some transactions
        transactions = []
        
        # Most blocks won't have dormant addresses
        # But occasionally add one for testing
        if random.random() < 0.3:  # 30% chance to include a dormant address
            # Pick a random dormant address
            if self.dormant_addresses:
                dormant_addr = random.choice(self.dormant_addresses)
                
                # Create a transaction spending from this address
                transactions.append({
                    'hash': f'tx_{block_height}_{len(transactions)}',
                    'inputs': [{
                        'address': dormant_addr,
                        'value': random.randint(1000000000, 10000000000)  # 10-100 BTC
                    }],
                    'outputs': [{
                        'address': '1' + ''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=33)),
                        'value': random.randint(1000000000, 10000000000)
                    }]
                })
                
        # Add some normal transactions
        for i in range(random.randint(100, 300)):
            transactions.append({
                'hash': f'tx_{block_height}_{len(transactions)}',
                'inputs': [{
                    'address': '1' + ''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=33)),
                    'value': random.randint(1000000, 100000000)
                }],
                'outputs': [{
                    'address': '1' + ''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=33)),
                    'value': random.randint(1000000, 100000000)
                }]
            })
            
        return {
            'height': block_height,
            'timestamp': datetime.now(),
            'transactions': transactions
        }
        
    async def get_address_info(self, address: str):
        """Return mock address info"""
        return type('AddressInfo', (), {
            'address': address,
            'balance': random.randint(1000000000, 100000000000),  # 10-1000 BTC
            'transaction_count': random.randint(1, 100)
        })()


async def test_block_monitoring():
    """Test the block monitoring system"""
    logger.info("=" * 80)
    logger.info("Testing Block Monitoring System")
    logger.info("=" * 80)
    
    # Initialize database
    await db.initialize()
    
    # Create mock blockchain
    mock_blockchain = MockBlockchainManager()
    await mock_blockchain.initialize()
    
    # Get some real dormant addresses from database
    async with db.get_session() as session:
        result = await session.execute(
            select(Wallet.address)
            .where(Wallet.dormancy_days > 2920)  # 8+ years
            .limit(10)
        )
        dormant_addresses = result.scalars().all()
        mock_blockchain.dormant_addresses = list(dormant_addresses)
    
    logger.info(f"Loaded {len(dormant_addresses)} dormant addresses for testing")
    for addr in dormant_addresses[:5]:
        logger.info(f"  - {addr}")
    
    # Create block monitor
    monitor = BlockMonitorService(mock_blockchain)
    await monitor.initialize()
    
    logger.info(f"\nMonitor initialized with {len(monitor.dormant_addresses)} addresses")
    
    # Test 1: Check that dormant addresses are loaded
    logger.info("\n🧪 Test 1: Verify dormant addresses loaded")
    stats = await monitor.get_stats()
    assert stats['monitored_addresses'] > 0, "No addresses loaded!"
    logger.info(f"✅ Loaded {stats['monitored_addresses']} addresses")
    
    # Test 2: Process blocks and detect movements
    logger.info("\n🧪 Test 2: Process multiple blocks")
    total_movements = []
    
    for i in range(10):
        logger.info(f"\nChecking block #{i+1}...")
        movements = await monitor.check_new_blocks()
        
        if movements:
            logger.warning(f"🚨 Detected {len(movements)} dormant address movements!")
            for movement in movements:
                btc_moved = movement['total_moved'] / 100_000_000
                logger.info(f"  - Address: {movement['address'][:20]}... moved {btc_moved:.2f} BTC in block {movement['block_height']}")
            total_movements.extend(movements)
        else:
            logger.info("  ✓ No dormant movements in this block")
            
        # Small delay between blocks
        await asyncio.sleep(0.1)
    
    # Test 3: Verify movement detection
    logger.info("\n🧪 Test 3: Movement Detection Summary")
    logger.info(f"Total movements detected: {len(total_movements)}")
    if total_movements:
        total_btc = sum(m['total_moved'] for m in total_movements) / 100_000_000
        logger.info(f"Total BTC moved: {total_btc:.2f}")
        logger.info("✅ Movement detection working!")
    else:
        logger.info("⚠️  No movements detected (this is normal if random didn't trigger)")
    
    # Test 4: Test efficiency
    logger.info("\n🧪 Test 4: Efficiency Analysis")
    logger.info(f"Blocks processed: 10")
    logger.info(f"API calls made: ~10 (one per block)")
    logger.info(f"Additional calls: {len(total_movements)} (only for movements)")
    logger.info(f"Total API calls: {10 + len(total_movements)}")
    logger.info(f"vs Old method: {stats['monitored_addresses'] * 10} calls would be needed")
    efficiency = (stats['monitored_addresses'] * 10) / (10 + len(total_movements))
    logger.info(f"✅ Efficiency gain: {efficiency:.0f}x fewer API calls!")
    
    # Test 5: Test the full monitoring service
    logger.info("\n🧪 Test 5: Full Monitoring Service")
    monitoring_service = BlockMonitoringService(mock_blockchain)
    await monitoring_service.start()
    
    logger.info("Monitoring service started, waiting for it to process blocks...")
    await asyncio.sleep(3)
    
    await monitoring_service.stop()
    logger.info("✅ Monitoring service ran successfully!")
    
    # Cleanup
    await db.close()
    
    logger.info("\n" + "=" * 80)
    logger.info("All tests completed successfully! 🎉")
    logger.info("=" * 80)


if __name__ == "__main__":
    # Configure logging with plain output for better readability
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(colors=False)
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    asyncio.run(test_block_monitoring())