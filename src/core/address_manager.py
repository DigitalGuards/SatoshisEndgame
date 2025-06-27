import re
from typing import List, Set, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

import structlog
from bitcoinlib.keys import Key
from bitcoinlib.scripts import Script

from src.config import settings

logger = structlog.get_logger()


@dataclass
class VulnerableAddress:
    address: str
    vulnerability_type: str  # 'P2PK' or 'REUSED_P2PKH'
    balance: int
    last_activity: Optional[datetime]
    dormancy_days: int
    risk_score: float
    public_key: Optional[str] = None


class AddressVulnerabilityDetector:
    """Detects quantum-vulnerable Bitcoin addresses"""
    
    def __init__(self):
        self.logger = logger.bind(component="vulnerability_detector")
        self.dormancy_threshold = timedelta(days=settings.dormancy_threshold_days)
        self.min_balance_satoshis = int(settings.min_balance_threshold_btc * 100_000_000)
    
    def is_p2pk_script(self, script_hex: str) -> bool:
        """
        Check if a script is Pay-to-Public-Key (P2PK)
        P2PK format: <pubkey> OP_CHECKSIG
        """
        try:
            script_bytes = bytes.fromhex(script_hex)
            
            # Uncompressed public key: 65 bytes (0x41 prefix) + OP_CHECKSIG (0xAC)
            if len(script_bytes) == 67 and script_bytes[0] == 0x41 and script_bytes[66] == 0xAC:
                return True
            
            # Compressed public key: 33 bytes (0x21 prefix) + OP_CHECKSIG (0xAC)
            if len(script_bytes) == 35 and script_bytes[0] == 0x21 and script_bytes[34] == 0xAC:
                return True
                
            return False
        except Exception as e:
            self.logger.debug("Failed to parse script", error=str(e))
            return False
    
    def extract_public_key_from_p2pk(self, script_hex: str) -> Optional[str]:
        """Extract public key from P2PK script"""
        try:
            script_bytes = bytes.fromhex(script_hex)
            
            # Uncompressed public key
            if len(script_bytes) == 67 and script_bytes[0] == 0x41:
                return script_bytes[1:66].hex()
            
            # Compressed public key
            if len(script_bytes) == 35 and script_bytes[0] == 0x21:
                return script_bytes[1:34].hex()
                
            return None
        except Exception:
            return None
    
    def is_address_vulnerable(self, address: str, script_hex: Optional[str] = None,
                            has_spent: bool = False) -> Tuple[bool, str]:
        """
        Check if an address is vulnerable to quantum attack
        Returns: (is_vulnerable, vulnerability_type)
        """
        # Check P2PK vulnerability
        if script_hex and self.is_p2pk_script(script_hex):
            return True, "P2PK"
        
        # Check P2PKH reuse vulnerability
        if self._is_p2pkh_address(address) and has_spent:
            return True, "REUSED_P2PKH"
            
        return False, ""
    
    def _is_p2pkh_address(self, address: str) -> bool:
        """Check if address is P2PKH format (starts with 1)"""
        return address.startswith('1') and len(address) >= 26 and len(address) <= 35
    
    def calculate_risk_score(self, balance: int, dormancy_days: int, 
                           vulnerability_type: str) -> float:
        """
        Calculate risk score from 0-100 based on multiple factors
        """
        score = 0.0
        
        # Balance factor (up to 40 points)
        if balance > 0:
            btc_amount = balance / 100_000_000
            if btc_amount >= 1000:
                score += 40
            elif btc_amount >= 100:
                score += 30
            elif btc_amount >= 10:
                score += 20
            else:
                score += 10
        
        # Dormancy factor (up to 30 points)
        if dormancy_days > 3650:  # 10+ years
            score += 30
        elif dormancy_days > 1825:  # 5+ years
            score += 25
        elif dormancy_days > 730:  # 2+ years
            score += 20
        elif dormancy_days > 365:  # 1+ year
            score += 15
        else:
            score += 5
        
        # Vulnerability type factor (up to 30 points)
        if vulnerability_type == "P2PK":
            score += 30  # Direct exposure
        elif vulnerability_type == "REUSED_P2PKH":
            score += 20  # Indirect exposure
        
        return min(score, 100.0)
    
    def filter_monitored_addresses(self, addresses: List[VulnerableAddress]) -> List[VulnerableAddress]:
        """Filter addresses based on monitoring criteria"""
        monitored = []
        
        for addr in addresses:
            # Check minimum balance
            if addr.balance < self.min_balance_satoshis:
                continue
                
            # Check dormancy
            if addr.dormancy_days < settings.dormancy_threshold_days:
                continue
                
            monitored.append(addr)
        
        # Sort by risk score
        monitored.sort(key=lambda x: x.risk_score, reverse=True)
        
        return monitored
    
    def detect_satoshi_era_addresses(self, addresses: List[VulnerableAddress]) -> List[VulnerableAddress]:
        """
        Identify potential Satoshi-era addresses based on patterns
        """
        satoshi_era = []
        
        for addr in addresses:
            # Check if P2PK (common in early blocks)
            if addr.vulnerability_type != "P2PK":
                continue
                
            # Check if dormant since 2010-2011
            if addr.last_activity and addr.last_activity.year > 2011:
                continue
                
            # Check for round BTC amounts (common in early mining)
            btc_amount = addr.balance / 100_000_000
            if btc_amount == 50.0 or btc_amount == 25.0:
                satoshi_era.append(addr)
        
        return satoshi_era


class AddressTracker:
    """Tracks and manages vulnerable addresses"""
    
    def __init__(self):
        self.vulnerable_addresses: Set[str] = set()
        self.detector = AddressVulnerabilityDetector()
        self.logger = logger.bind(component="address_tracker")
    
    def add_vulnerable_address(self, address: str, vulnerability_type: str):
        """Add a vulnerable address to tracking"""
        self.vulnerable_addresses.add(address)
        self.logger.info(
            "Added vulnerable address",
            address=address[:10] + "...",
            type=vulnerability_type,
            total_tracked=len(self.vulnerable_addresses)
        )
    
    def remove_address(self, address: str):
        """Remove an address from tracking (e.g., if balance becomes 0)"""
        if address in self.vulnerable_addresses:
            self.vulnerable_addresses.remove(address)
            self.logger.info(
                "Removed address from tracking",
                address=address[:10] + "...",
                remaining=len(self.vulnerable_addresses)
            )
    
    def get_tracked_addresses(self) -> List[str]:
        """Get list of currently tracked addresses"""
        return list(self.vulnerable_addresses)
    
    def is_tracked(self, address: str) -> bool:
        """Check if an address is being tracked"""
        return address in self.vulnerable_addresses
    
    def get_statistics(self) -> dict:
        """Get tracking statistics"""
        return {
            'total_tracked': len(self.vulnerable_addresses),
            'addresses': list(self.vulnerable_addresses)[:10],  # First 10 for preview
            'last_update': datetime.utcnow().isoformat()
        }