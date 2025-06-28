import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.blockchain import BlockchainManager
from src.core.address_manager import AddressVulnerabilityDetector, VulnerableAddress
from src.data.database import db
from src.data.models import Wallet, Transaction, Alert, WalletSnapshot
from src.services.notification_service import DiscordNotificationService, NotificationAlert
from src.services.quantum_detector import QuantumEmergencyDetector, WalletActivity

logger = structlog.get_logger()


class MonitoringService:
    """Main monitoring service that orchestrates all components"""
    
    def __init__(self):
        self.blockchain_manager = BlockchainManager()
        self.vulnerability_detector = AddressVulnerabilityDetector()
        self.quantum_detector = QuantumEmergencyDetector()
        self.discord_service = DiscordNotificationService()
        self.scheduler = AsyncIOScheduler()
        self.logger = logger.bind(component="monitoring_service")
        
        # Tracking state
        self.monitored_addresses: Set[str] = set()
        self.last_check_time: Dict[str, datetime] = {}
        self.is_running = False
    
    async def initialize(self):
        """Initialize all services"""
        self.logger.info("Initializing monitoring service")
        
        # Initialize blockchain manager
        await self.blockchain_manager.initialize()
        
        # Initialize database
        await db.initialize()
        
        # Load monitored addresses from database
        await self._load_monitored_addresses()
        
        # Send startup notification
        await self.discord_service.send_startup_notification()
        
        # Schedule monitoring tasks
        self._schedule_tasks()
        
        self.logger.info(
            "Monitoring service initialized",
            monitored_addresses=len(self.monitored_addresses)
        )
    
    async def _load_monitored_addresses(self):
        """Load vulnerable addresses from database"""
        async with db.get_session() as session:
            result = await session.execute(
                select(Wallet).where(
                    and_(
                        Wallet.is_vulnerable == True,
                        Wallet.is_active == True,
                        Wallet.current_balance >= self.vulnerability_detector.min_balance_satoshis
                    )
                )
            )
            wallets = result.scalars().all()
            
            self.monitored_addresses = {wallet.address for wallet in wallets}
            self.logger.info(f"Loaded {len(self.monitored_addresses)} addresses for monitoring")
    
    def _schedule_tasks(self):
        """Schedule periodic monitoring tasks"""
        # Main monitoring task - check all addresses
        self.scheduler.add_job(
            self.monitor_all_addresses,
            IntervalTrigger(minutes=5),
            id="monitor_addresses",
            name="Monitor all addresses",
            misfire_grace_time=60
        )
        
        # Quick check for high-risk addresses
        self.scheduler.add_job(
            self.quick_check_high_risk,
            IntervalTrigger(minutes=1),
            id="quick_check",
            name="Quick check high-risk addresses",
            misfire_grace_time=30
        )
        
        # Database cleanup and maintenance
        self.scheduler.add_job(
            self.database_maintenance,
            IntervalTrigger(hours=6),
            id="db_maintenance",
            name="Database maintenance",
            misfire_grace_time=300
        )
        
        # Wallet snapshot for analysis
        self.scheduler.add_job(
            self.create_wallet_snapshots,
            IntervalTrigger(hours=1),
            id="wallet_snapshots",
            name="Create wallet snapshots",
            misfire_grace_time=300
        )
    
    async def start(self):
        """Start the monitoring service"""
        if self.is_running:
            self.logger.warning("Monitoring service already running")
            return
        
        self.is_running = True
        self.scheduler.start()
        self.logger.info("Monitoring service started")
        
        # Run initial check
        await self.monitor_all_addresses()
    
    async def stop(self):
        """Stop the monitoring service"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.scheduler.shutdown()
        await self.blockchain_manager.close()
        await db.close()
        self.logger.info("Monitoring service stopped")
    
    async def monitor_all_addresses(self):
        """Main monitoring task - check all addresses"""
        start_time = datetime.utcnow()
        self.logger.info("Starting address monitoring cycle")
        
        try:
            # Process addresses in batches
            addresses = list(self.monitored_addresses)
            recent_activities = []
            
            for i in range(0, len(addresses), settings.batch_size):
                batch = addresses[i:i + settings.batch_size]
                
                # Get current state from blockchain
                address_infos = await self.blockchain_manager.get_addresses_batch(batch)
                
                # Check for changes and anomalies
                for info in address_infos:
                    if info:
                        activity = await self._process_address_update(info)
                        if activity:
                            recent_activities.append(activity)
            
            # Analyze for quantum emergency patterns
            if recent_activities:
                patterns = self.quantum_detector.analyze_recent_activity(recent_activities)
                
                for pattern in patterns:
                    if pattern.severity in ["HIGH", "CRITICAL"]:
                        await self._handle_emergency_pattern(pattern)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(
                "Address monitoring cycle completed",
                duration_seconds=elapsed,
                addresses_checked=len(addresses),
                activities_detected=len(recent_activities)
            )
            
        except Exception as e:
            self.logger.error("Error in monitoring cycle", error=str(e))
    
    async def _process_address_update(self, address_info) -> Optional[WalletActivity]:
        """Process updates for a single address"""
        async with db.get_session() as session:
            # Get wallet from database
            result = await session.execute(
                select(Wallet).where(Wallet.address == address_info.address)
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                # New vulnerable address discovered
                wallet = await self._create_wallet_record(session, address_info)
            
            # Check for balance changes
            if wallet.current_balance != address_info.balance:
                # Significant change detected
                change_amount = address_info.balance - wallet.current_balance
                
                # Create transaction record
                transaction = Transaction(
                    wallet_id=wallet.id,
                    wallet_address=wallet.address,
                    txhash="pending",  # Will be updated with actual txhash
                    block_time=datetime.utcnow(),
                    amount=abs(change_amount),
                    tx_type="out" if change_amount < 0 else "in",
                    is_anomalous=self._is_anomalous_transaction(wallet, change_amount),
                    extra_data={}
                )
                session.add(transaction)
                
                # Update wallet
                old_balance = wallet.current_balance
                wallet.current_balance = address_info.balance
                wallet.last_activity = datetime.utcnow()
                wallet.transaction_count = address_info.transaction_count
                
                # Calculate dormancy
                if wallet.last_activity:
                    dormancy_days = (datetime.utcnow() - wallet.last_activity).days
                else:
                    dormancy_days = 0
                
                await session.commit()
                
                # Return activity for pattern analysis
                return WalletActivity(
                    address=wallet.address,
                    transaction_time=datetime.utcnow(),
                    amount=abs(change_amount),
                    balance=address_info.balance,
                    dormancy_days=dormancy_days,
                    last_activity_before=wallet.last_activity,
                    vulnerability_type=wallet.vulnerability_type or ""
                )
            
            return None
    
    async def _create_wallet_record(self, session: AsyncSession, address_info) -> Wallet:
        """Create new wallet record in database"""
        is_vulnerable, vuln_type = self.vulnerability_detector.is_address_vulnerable(
            address_info.address
        )
        
        wallet = Wallet(
            address=address_info.address,
            wallet_type="P2PKH" if address_info.address.startswith("1") else "OTHER",
            vulnerability_type=vuln_type if is_vulnerable else None,
            is_vulnerable=is_vulnerable,
            current_balance=address_info.balance,
            last_activity=address_info.last_activity,
            transaction_count=address_info.transaction_count,
            risk_score=self.vulnerability_detector.calculate_risk_score(
                address_info.balance,
                0,  # New wallet, no dormancy
                vuln_type
            )
        )
        
        session.add(wallet)
        await session.commit()
        
        return wallet
    
    def _is_anomalous_transaction(self, wallet: Wallet, change_amount: int) -> bool:
        """Determine if transaction is anomalous"""
        # Large value movement
        if abs(change_amount) > 100 * 100_000_000:  # 100+ BTC
            return True
        
        # Dormant wallet becoming active
        if wallet.dormancy_days > 365:
            return True
        
        # Complete balance drain
        if change_amount < 0 and wallet.current_balance == 0:
            return True
        
        return False
    
    async def _handle_emergency_pattern(self, pattern):
        """Handle detected emergency pattern"""
        self.logger.warning(
            "Emergency pattern detected",
            pattern_type=pattern.pattern_type,
            severity=pattern.severity,
            affected_wallets=len(pattern.affected_wallets)
        )
        
        # Create alert in database
        async with db.get_session() as session:
            alert = Alert(
                alert_type=pattern.pattern_type,
                severity=pattern.severity,
                title=f"Quantum Emergency: {pattern.pattern_type.replace('_', ' ').title()}",
                description=f"Pattern detected affecting {len(pattern.affected_wallets)} wallets",
                affected_wallets=pattern.affected_wallets,
                total_value=pattern.total_value,
                pattern_detected=pattern.pattern_type
            )
            session.add(alert)
            await session.commit()
        
        # Send Discord notification
        if pattern.pattern_type == "dormant_wallet_surge":
            # Get wallet details for notification
            wallet_details = []
            async with db.get_session() as session:
                for address in pattern.affected_wallets[:10]:  # Limit to 10
                    result = await session.execute(
                        select(Wallet).where(Wallet.address == address)
                    )
                    wallet = result.scalar_one_or_none()
                    if wallet:
                        wallet_details.append({
                            'address': wallet.address,
                            'balance': wallet.current_balance,
                            'dormancy_days': wallet.dormancy_days
                        })
            
            await self.discord_service.send_quantum_emergency_alert(wallet_details)
        else:
            # Generic alert
            alert = NotificationAlert(
                alert_type=pattern.pattern_type,
                severity=pattern.severity,
                title=f"Pattern Detected: {pattern.pattern_type.replace('_', ' ').title()}",
                description=f"Unusual activity pattern detected affecting {len(pattern.affected_wallets)} wallets",
                wallet_addresses=pattern.affected_wallets,
                total_value=pattern.total_value,
                pattern=pattern.pattern_type,
                metadata=pattern.metadata
            )
            await self.discord_service.send_alert(alert)
    
    async def quick_check_high_risk(self):
        """Quick check for highest risk addresses"""
        async with db.get_session() as session:
            # Get top 20 highest risk addresses
            result = await session.execute(
                select(Wallet).where(
                    and_(
                        Wallet.is_vulnerable == True,
                        Wallet.is_active == True,
                        Wallet.risk_score >= 70
                    )
                ).order_by(Wallet.risk_score.desc()).limit(20)
            )
            high_risk_wallets = result.scalars().all()
            
            if high_risk_wallets:
                addresses = [w.address for w in high_risk_wallets]
                
                # Quick balance check
                address_infos = await self.blockchain_manager.get_addresses_batch(addresses)
                
                for info in address_infos:
                    if info:
                        wallet = next((w for w in high_risk_wallets if w.address == info.address), None)
                        if wallet and wallet.current_balance != info.balance:
                            # High risk wallet has activity!
                            self.logger.warning(
                                "High risk wallet activity detected",
                                address=wallet.address[:10] + "...",
                                old_balance=wallet.current_balance,
                                new_balance=info.balance
                            )
                            
                            # Process immediately
                            activity = await self._process_address_update(info)
                            if activity:
                                # Check for emergency patterns with just this activity
                                patterns = self.quantum_detector.analyze_recent_activity([activity])
                                for pattern in patterns:
                                    await self._handle_emergency_pattern(pattern)
    
    async def database_maintenance(self):
        """Perform database maintenance tasks"""
        self.logger.info("Starting database maintenance")
        
        async with db.get_session() as session:
            # Remove inactive wallets with zero balance
            await session.execute(
                select(Wallet).where(
                    and_(
                        Wallet.current_balance == 0,
                        Wallet.last_activity < datetime.utcnow() - timedelta(days=30)
                    )
                ).update({"is_active": False})
            )
            
            # Clean up old alerts
            await session.execute(
                select(Alert).where(
                    Alert.created_at < datetime.utcnow() - timedelta(days=90)
                ).delete()
            )
            
            await session.commit()
        
        self.logger.info("Database maintenance completed")
    
    async def create_wallet_snapshots(self):
        """Create periodic snapshots of wallet states"""
        snapshot_time = datetime.utcnow()
        
        async with db.get_session() as session:
            # Get active wallets
            result = await session.execute(
                select(Wallet).where(
                    and_(
                        Wallet.is_active == True,
                        Wallet.current_balance > 0
                    )
                )
            )
            wallets = result.scalars().all()
            
            for wallet in wallets:
                # Calculate metrics
                tx_count_24h = await self._get_transaction_count(
                    session, wallet.id, timedelta(hours=24)
                )
                tx_count_7d = await self._get_transaction_count(
                    session, wallet.id, timedelta(days=7)
                )
                
                snapshot = WalletSnapshot(
                    wallet_address=wallet.address,
                    snapshot_time=snapshot_time,
                    balance=wallet.current_balance,
                    tx_count_24h=tx_count_24h,
                    tx_count_7d=tx_count_7d,
                    risk_score=wallet.risk_score
                )
                session.add(snapshot)
            
            await session.commit()
            
        self.logger.info(f"Created snapshots for {len(wallets)} wallets")
    
    async def _get_transaction_count(self, session: AsyncSession, wallet_id: int, 
                                   time_period: timedelta) -> int:
        """Get transaction count for a wallet in time period"""
        result = await session.execute(
            select(Transaction).where(
                and_(
                    Transaction.wallet_id == wallet_id,
                    Transaction.block_time >= datetime.utcnow() - time_period
                )
            ).count()
        )
        return result.scalar() or 0