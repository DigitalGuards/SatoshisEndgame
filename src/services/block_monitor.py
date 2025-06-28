"""
Block-based monitoring service for efficient dormant address tracking
Instead of polling each address, we monitor blocks and check for our addresses
"""

import asyncio
from typing import List, Set, Dict, Optional
from datetime import datetime
import structlog
from sqlalchemy import select

from src.core.blockchain import BlockchainManager
from src.data.database import db
from src.data.models import Wallet, Transaction
from src.config import settings

logger = structlog.get_logger()


class BlockMonitorService:
    """Monitors blockchain blocks for dormant address activity"""
    
    def __init__(self, blockchain_manager: BlockchainManager):
        self.blockchain = blockchain_manager
        self.dormant_addresses: Set[str] = set()
        self.last_block_height: Optional[int] = None
        self.logger = logger.bind(component="block_monitor")
        
    async def initialize(self):
        """Load dormant addresses from database into memory"""
        self.logger.info("Initializing block monitor")
        
        async with db.get_session() as session:
            # Load all monitored addresses into memory for fast lookup
            result = await session.execute(
                select(Wallet.address).where(Wallet.is_active == True)
            )
            addresses = result.scalars().all()
            self.dormant_addresses = set(addresses)
            
        self.logger.info(f"Loaded {len(self.dormant_addresses)} addresses to monitor")
        
        # Get current block height
        try:
            self.last_block_height = await self.blockchain.get_latest_block_height()
            self.logger.info(f"Starting from block height: {self.last_block_height}")
        except Exception as e:
            self.logger.error("Failed to get initial block height", error=str(e))
            
    async def check_new_blocks(self) -> List[Dict]:
        """Check for new blocks and scan for dormant addresses"""
        movements = []
        
        try:
            # Get current block height
            current_height = await self.blockchain.get_latest_block_height()
            
            if not self.last_block_height:
                self.last_block_height = current_height
                return movements
                
            # Process any new blocks
            if current_height > self.last_block_height:
                self.logger.info(
                    "New blocks detected",
                    from_height=self.last_block_height,
                    to_height=current_height,
                    new_blocks=current_height - self.last_block_height
                )
                
                # Process each new block
                for height in range(self.last_block_height + 1, current_height + 1):
                    block_movements = await self._process_block(height)
                    movements.extend(block_movements)
                    
                self.last_block_height = current_height
                
        except Exception as e:
            self.logger.error("Error checking new blocks", error=str(e))
            
        return movements
        
    async def _process_block(self, block_height: int) -> List[Dict]:
        """Process a single block for dormant address activity"""
        movements = []
        
        try:
            # Get block data
            block = await self.blockchain.get_block(block_height)
            if not block:
                return movements
                
            self.logger.debug(f"Processing block {block_height}", 
                            tx_count=len(block.get('transactions', [])))
            
            # Extract all addresses from transactions
            block_addresses = self._extract_addresses_from_block(block)
            
            # Find intersection with our dormant addresses
            active_dormant = block_addresses & self.dormant_addresses
            
            if active_dormant:
                self.logger.warning(
                    "🚨 Dormant address activity detected!",
                    block=block_height,
                    addresses=list(active_dormant)[:5],  # Show first 5
                    total_found=len(active_dormant)
                )
                
                # Get detailed info for each active address
                for address in active_dormant:
                    try:
                        movement = await self._analyze_address_movement(
                            address, 
                            block,
                            block_height
                        )
                        if movement:
                            movements.append(movement)
                    except Exception as e:
                        self.logger.error(
                            "Error analyzing address movement",
                            address=address[:10] + "...",
                            error=str(e)
                        )
                        
        except Exception as e:
            self.logger.error(f"Error processing block {block_height}", error=str(e))
            
        return movements
        
    def _extract_addresses_from_block(self, block: Dict) -> Set[str]:
        """Extract all unique addresses from a block's transactions"""
        addresses = set()
        
        for tx in block.get('transactions', []):
            # Extract input addresses (spending from)
            for inp in tx.get('inputs', []):
                if inp.get('address'):
                    addresses.add(inp['address'])
                    
            # Extract output addresses (sending to)
            for out in tx.get('outputs', []):
                if out.get('address'):
                    addresses.add(out['address'])
                    
        return addresses
        
    async def _analyze_address_movement(
        self, 
        address: str, 
        block: Dict,
        block_height: int
    ) -> Optional[Dict]:
        """Analyze the movement of a dormant address"""
        try:
            # Get current address info
            address_info = await self.blockchain.get_address_info(address)
            if not address_info:
                return None
                
            # Find relevant transactions in the block
            relevant_txs = []
            for tx in block.get('transactions', []):
                # Check if address is in inputs (spending)
                for inp in tx.get('inputs', []):
                    if inp.get('address') == address:
                        relevant_txs.append({
                            'tx_id': tx['hash'],
                            'type': 'spend',
                            'amount': inp.get('value', 0),
                            'timestamp': block.get('timestamp', datetime.now())
                        })
                        
                # Check if address is in outputs (receiving)
                for out in tx.get('outputs', []):
                    if out.get('address') == address:
                        relevant_txs.append({
                            'tx_id': tx['hash'],
                            'type': 'receive',
                            'amount': out.get('value', 0),
                            'timestamp': block.get('timestamp', datetime.now())
                        })
                        
            if relevant_txs:
                return {
                    'address': address,
                    'block_height': block_height,
                    'previous_balance': address_info.balance,
                    'transactions': relevant_txs,
                    'total_moved': sum(tx['amount'] for tx in relevant_txs if tx['type'] == 'spend'),
                    'timestamp': block.get('timestamp', datetime.now())
                }
                
        except Exception as e:
            self.logger.error(f"Error analyzing address {address[:10]}...", error=str(e))
            
        return None
        
    async def update_monitored_addresses(self, new_addresses: List[str]):
        """Update the set of monitored addresses"""
        before_count = len(self.dormant_addresses)
        self.dormant_addresses.update(new_addresses)
        added = len(self.dormant_addresses) - before_count
        
        if added > 0:
            self.logger.info(f"Added {added} new addresses to monitor")
            
    async def remove_monitored_addresses(self, addresses: List[str]):
        """Remove addresses from monitoring"""
        before_count = len(self.dormant_addresses)
        self.dormant_addresses.difference_update(addresses)
        removed = before_count - len(self.dormant_addresses)
        
        if removed > 0:
            self.logger.info(f"Removed {removed} addresses from monitoring")
            
    async def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        return {
            'monitored_addresses': len(self.dormant_addresses),
            'last_block_height': self.last_block_height,
            'monitoring_active': self.last_block_height is not None
        }


class BlockMonitoringService:
    """Main service that coordinates block monitoring"""
    
    def __init__(self, blockchain_manager: BlockchainManager):
        self.block_monitor = BlockMonitorService(blockchain_manager)
        self.blockchain = blockchain_manager
        self.logger = logger.bind(component="block_monitoring")
        self._running = False
        
    async def start(self):
        """Start the block monitoring service"""
        self.logger.info("Starting block monitoring service")
        
        # Initialize block monitor
        await self.block_monitor.initialize()
        
        self._running = True
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
    async def stop(self):
        """Stop the monitoring service"""
        self.logger.info("Stopping block monitoring service")
        self._running = False
        
    async def _monitoring_loop(self):
        """Main monitoring loop that checks for new blocks"""
        check_interval = 30  # Check every 30 seconds for new blocks
        
        while self._running:
            try:
                # Check for new blocks
                movements = await self.block_monitor.check_new_blocks()
                
                if movements:
                    self.logger.warning(
                        f"Detected {len(movements)} dormant address movements!",
                        total_btc_moved=sum(m['total_moved'] for m in movements) / 100_000_000
                    )
                    
                    # Process movements (save to DB, send alerts, etc.)
                    await self._process_movements(movements)
                    
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=str(e))
                
            # Wait before next check
            await asyncio.sleep(check_interval)
            
    async def _process_movements(self, movements: List[Dict]):
        """Process detected movements"""
        async with db.get_session() as session:
            for movement in movements:
                try:
                    # Update wallet status
                    result = await session.execute(
                        select(Wallet).where(Wallet.address == movement['address'])
                    )
                    wallet = result.scalar_one_or_none()
                    
                    if wallet:
                        wallet.last_activity = movement['timestamp']
                        wallet.has_moved = True
                        
                        # Create transaction records
                        for tx in movement['transactions']:
                            transaction = Transaction(
                                wallet_id=wallet.id,
                                wallet_address=wallet.address,
                                txhash=tx['tx_id'],
                                block_time=tx['timestamp'],
                                block_height=movement['block_height'],
                                amount=tx['amount'],
                                tx_type='outgoing' if tx['type'] == 'spend' else 'incoming'
                            )
                            session.add(transaction)
                            
                        self.logger.info(
                            "Updated wallet movement",
                            address=movement['address'][:10] + "...",
                            btc_moved=movement['total_moved'] / 100_000_000
                        )
                        
                except Exception as e:
                    self.logger.error(
                        "Error processing movement",
                        address=movement['address'][:10] + "...",
                        error=str(e)
                    )
                    
            await session.commit()