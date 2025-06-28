#!/usr/bin/env python3
"""
Demo script to show how block-based monitoring works
Much more efficient than polling individual addresses
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.core.blockchain import BlockchainManager
from src.services.block_monitor import BlockMonitorService
from src.data.database import db
import structlog

logger = structlog.get_logger()


async def demo_block_monitoring():
    """Demonstrate block-based monitoring approach"""
    
    # Initialize components
    blockchain = BlockchainManager()
    await blockchain.initialize()
    await db.initialize()
    
    # Create block monitor
    monitor = BlockMonitorService(blockchain)
    await monitor.initialize()
    
    logger.info("=" * 60)
    logger.info("Block-Based Monitoring Demo")
    logger.info("=" * 60)
    
    # Show efficiency comparison
    stats = await monitor.get_stats()
    logger.info(f"Monitoring {stats['monitored_addresses']} dormant addresses")
    
    logger.info("\n🔴 OLD APPROACH (Individual polling):")
    logger.info(f"  - API calls needed: {stats['monitored_addresses']} every 5 minutes")
    logger.info(f"  - Daily API calls: {stats['monitored_addresses'] * 12 * 24:,}")
    logger.info(f"  - Problem: Exceeds API limits!")
    
    logger.info("\n🟢 NEW APPROACH (Block monitoring):")
    logger.info(f"  - API calls needed: 1 every ~10 minutes (new blocks)")
    logger.info(f"  - Daily API calls: ~144")
    logger.info(f"  - Additional calls: Only when dormant addresses move")
    logger.info(f"  - Efficiency gain: {(stats['monitored_addresses'] * 12 * 24) / 144:.0f}x fewer API calls!")
    
    # Simulate checking for new blocks
    logger.info("\n📦 Simulating block monitoring...")
    
    # In a real scenario, this would check actual new blocks
    logger.info("Checking for new blocks...")
    movements = await monitor.check_new_blocks()
    
    if movements:
        logger.warning(f"Found {len(movements)} dormant address movements!")
        for movement in movements[:5]:  # Show first 5
            logger.info(
                f"  - {movement['address'][:10]}... moved {movement['total_moved'] / 100_000_000:.2f} BTC"
            )
    else:
        logger.info("No dormant address movements detected in recent blocks")
    
    # Show how it works
    logger.info("\n🔍 How it works:")
    logger.info("1. Monitor gets new block (~every 10 minutes)")
    logger.info("2. Extract all addresses from block transactions")
    logger.info("3. Check if any match our 943 dormant addresses (fast in-memory lookup)")
    logger.info("4. Only fetch details for matches (rare)")
    logger.info("5. Send alerts if quantum-like patterns detected")
    
    await blockchain.close()
    await db.close()


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
    
    asyncio.run(demo_block_monitoring())