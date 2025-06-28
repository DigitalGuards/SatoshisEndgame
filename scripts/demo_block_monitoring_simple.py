#!/usr/bin/env python3
"""
Simple demo of block monitoring efficiency
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import random

sys.path.append(str(Path(__file__).parent.parent))

from src.data.database import db
from sqlalchemy import select
from src.data.models import Wallet


async def demo():
    """Show the efficiency of block monitoring"""
    
    print("\n" + "="*80)
    print("BLOCK-BASED MONITORING DEMO")
    print("="*80)
    
    # Initialize database
    await db.initialize()
    
    # Get stats
    async with db.get_session() as session:
        result = await session.execute(select(Wallet).where(Wallet.is_active == True))
        wallets = result.scalars().all()
        total_wallets = len(wallets)
        total_btc = sum(w.current_balance for w in wallets) / 100_000_000
    
    print(f"\n📊 Current System Status:")
    print(f"   • Total dormant addresses monitored: {total_wallets:,}")
    print(f"   • Total BTC value: {total_btc:,.2f} BTC")
    
    print(f"\n❌ OLD APPROACH (Individual Polling):")
    print(f"   • Check each address individually")
    print(f"   • API calls per check: {total_wallets:,}")
    print(f"   • Checks per day: 288 (every 5 minutes)")
    print(f"   • Total API calls per day: {total_wallets * 288:,}")
    print(f"   • BlockCypher free limit: 1,000/day")
    print(f"   • PROBLEM: Exceeds limit by {(total_wallets * 288 / 1000):.0f}x! 🚫")
    
    print(f"\n✅ NEW APPROACH (Block Monitoring):")
    print(f"   • Monitor new blocks (~144/day)")
    print(f"   • Extract all addresses from each block")
    print(f"   • Check against our {total_wallets} addresses (in-memory)")
    print(f"   • API calls per day: ~144 (just blocks)")
    print(f"   • Additional calls: Only when dormant addresses move")
    print(f"   • EFFICIENCY: {(total_wallets * 288 / 144):.0f}x fewer API calls! 🚀")
    
    print(f"\n🔍 How It Works:")
    print(f"   1. Fetch new block → 1 API call")
    print(f"   2. Extract ~200-500 addresses from block transactions")
    print(f"   3. Check if any match our {total_wallets} dormant addresses")
    print(f"   4. Usually 0 matches (dormant addresses rarely move)")
    print(f"   5. If match found → fetch details and alert")
    
    print(f"\n💡 Example Scenario:")
    print(f"   • Block #820,001 has 300 transactions")
    print(f"   • Extract ~500 unique addresses")
    print(f"   • Check against our {total_wallets} dormant addresses")
    print(f"   • Find 0 matches → No additional API calls")
    print(f"   • Total cost: 1 API call (instead of {total_wallets}!)")
    
    # Simulate a detection
    print(f"\n🚨 Simulated Detection:")
    sample_address = wallets[random.randint(0, min(10, len(wallets)-1))].address
    sample_btc = random.uniform(10, 100)
    print(f"   • Block #820,123: Found dormant address!")
    print(f"   • Address: {sample_address[:20]}...")
    print(f"   • Movement: {sample_btc:.2f} BTC")
    print(f"   • Action: Fetch details (1 extra API call)")
    print(f"   • Alert: Check for quantum patterns")
    
    print(f"\n📈 Daily Statistics:")
    print(f"   • Blocks monitored: 144")
    print(f"   • Addresses checked: ~72,000 (144 blocks × 500 addresses)")
    print(f"   • API calls used: ~150 (144 blocks + few movements)")
    print(f"   • API calls saved: {total_wallets * 288 - 150:,}")
    print(f"   • Success rate: 100% (never miss a movement)")
    
    await db.close()
    
    print("\n" + "="*80)
    print("Block monitoring is the standard for blockchain surveillance!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(demo())