from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, JSON, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Wallet(Base):
    """Tracked Bitcoin wallet"""
    __tablename__ = 'wallets'
    
    id = Column(Integer, primary_key=True)
    address = Column(String(62), unique=True, nullable=False, index=True)
    wallet_type = Column(String(20), nullable=False)  # P2PK, P2PKH, etc.
    vulnerability_type = Column(String(20))  # P2PK, REUSED_P2PKH
    is_vulnerable = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # Balance and activity
    current_balance = Column(BigInteger, default=0)  # in satoshis
    last_activity = Column(DateTime(timezone=True))
    first_seen = Column(DateTime(timezone=True))
    transaction_count = Column(Integer, default=0)
    
    # Risk assessment
    risk_score = Column(Float, default=0.0)
    dormancy_days = Column(Integer, default=0)
    
    # Metadata
    public_key = Column(String(130))  # Hex encoded public key if known
    metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="wallet")
    alerts = relationship("Alert", back_populates="wallet")
    
    __table_args__ = (
        Index('idx_wallet_balance', 'current_balance'),
        Index('idx_wallet_risk', 'risk_score'),
        Index('idx_wallet_dormancy', 'dormancy_days'),
        Index('idx_wallet_vulnerable', 'is_vulnerable', 'is_active'),
    )


class Transaction(Base):
    """Monitored transactions"""
    __tablename__ = 'transactions'
    
    id = Column(BigInteger, primary_key=True)
    txhash = Column(String(64), nullable=False, index=True)
    block_time = Column(DateTime(timezone=True), nullable=False, index=True)
    block_height = Column(Integer)
    
    # Wallet reference
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    wallet_address = Column(String(62), nullable=False, index=True)
    
    # Transaction details
    amount = Column(BigInteger, nullable=False)  # satoshis
    tx_type = Column(String(10), nullable=False)  # 'in' or 'out'
    fee = Column(BigInteger)
    
    # Analysis flags
    is_anomalous = Column(Boolean, default=False)
    anomaly_reason = Column(String(100))
    
    # Metadata
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")
    
    __table_args__ = (
        UniqueConstraint('txhash', 'wallet_address', name='uq_tx_wallet'),
        Index('idx_tx_anomalous', 'is_anomalous', 'block_time'),
        Index('idx_tx_wallet_time', 'wallet_id', 'block_time'),
    )


class Alert(Base):
    """System alerts and notifications"""
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    alert_type = Column(String(50), nullable=False)  # quantum_emergency, dormant_movement, etc.
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Alert details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    
    # Related wallet (optional)
    wallet_id = Column(Integer, ForeignKey('wallets.id'))
    wallet_address = Column(String(62))
    
    # Alert metadata
    affected_wallets = Column(JSON, default=list)  # List of affected addresses
    total_value = Column(BigInteger, default=0)  # Total BTC value affected
    pattern_detected = Column(String(100))
    
    # Notification status
    discord_sent = Column(Boolean, default=False)
    discord_sent_at = Column(DateTime(timezone=True))
    discord_message_id = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))
    
    # Relationships
    wallet = relationship("Wallet", back_populates="alerts")
    
    __table_args__ = (
        Index('idx_alert_created', 'created_at'),
        Index('idx_alert_severity', 'severity', 'created_at'),
        Index('idx_alert_type', 'alert_type', 'created_at'),
    )


class WalletSnapshot(Base):
    """Periodic wallet state snapshots for analysis"""
    __tablename__ = 'wallet_snapshots'
    
    id = Column(BigInteger, primary_key=True)
    wallet_address = Column(String(62), nullable=False, index=True)
    snapshot_time = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Snapshot data
    balance = Column(BigInteger, nullable=False)
    tx_count_24h = Column(Integer, default=0)
    tx_count_7d = Column(Integer, default=0)
    volume_24h = Column(BigInteger, default=0)
    volume_7d = Column(BigInteger, default=0)
    
    # Analysis metrics
    balance_change_24h = Column(BigInteger, default=0)
    balance_change_7d = Column(BigInteger, default=0)
    risk_score = Column(Float, default=0.0)
    
    __table_args__ = (
        UniqueConstraint('wallet_address', 'snapshot_time', name='uq_wallet_snapshot'),
        Index('idx_snapshot_time', 'snapshot_time'),
        Index('idx_snapshot_wallet_time', 'wallet_address', 'snapshot_time'),
    )


class SystemMetric(Base):
    """System performance and monitoring metrics"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_type = Column(String(50))  # counter, gauge, histogram
    
    # Context
    component = Column(String(50))  # api, database, monitoring, etc.
    metadata = Column(JSON, default=dict)
    
    # Timestamp
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_metric_name_time', 'metric_name', 'recorded_at'),
        Index('idx_metric_component', 'component', 'recorded_at'),
    )