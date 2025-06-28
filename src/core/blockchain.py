import asyncio
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
import structlog
from aiohttp import ClientSession

from src.config import settings

logger = structlog.get_logger()


@dataclass
class AddressInfo:
    address: str
    balance: int  # satoshis
    transaction_count: int
    last_activity: Optional[datetime] = None
    is_p2pk: bool = False
    is_reused_p2pkh: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Transaction:
    txid: str
    block_time: datetime
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    total_value: int  # satoshis


class BlockchainAPIError(Exception):
    """Base exception for blockchain API errors"""
    pass


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: float):
        self.rate = rate
        self.tokens = rate
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1:
                sleep_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class BlockchainAPI(ABC):
    """Abstract base class for blockchain APIs"""
    
    def __init__(self, session: ClientSession, rate_limit: float):
        self.session = session
        self.rate_limiter = RateLimiter(rate_limit)
    
    @abstractmethod
    async def get_address_info(self, address: str) -> AddressInfo:
        """Get information about a single address"""
        pass
    
    @abstractmethod
    async def get_addresses_batch(self, addresses: List[str]) -> List[AddressInfo]:
        """Get information about multiple addresses"""
        pass
    
    @abstractmethod
    async def get_recent_transactions(self, address: str, limit: int = 10) -> List[Transaction]:
        """Get recent transactions for an address"""
        pass


class BlockchairAPI(BlockchainAPI):
    """Blockchair API implementation"""
    
    def __init__(self, session: ClientSession):
        super().__init__(session, settings.blockchair_rate_limit)
        self.base_url = "https://api.blockchair.com/bitcoin"
        self.api_key = settings.blockchair_api_key
    
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        await self.rate_limiter.acquire()
        
        # Rate limiting is handled by the rate limiter above
        
        if params is None:
            params = {}
        if self.api_key:
            params['key'] = self.api_key
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise BlockchainAPIError(f"Blockchair API error: {response.status} - {error_text}")
        except Exception as e:
            logger.error("Blockchair API request failed", endpoint=endpoint, error=str(e))
            raise BlockchainAPIError(f"Request failed: {str(e)}")
    
    async def get_address_info(self, address: str) -> AddressInfo:
        data = await self._make_request(f"/dashboards/address/{address}")
        
        addr_data = data.get('data', {}).get(address, {}).get('address', {})
        
        return AddressInfo(
            address=address,
            balance=addr_data.get('balance', 0),
            transaction_count=addr_data.get('transaction_count', 0),
            last_activity=self._parse_timestamp(addr_data.get('last_seen')),
            metadata={
                'received': addr_data.get('received', 0),
                'spent': addr_data.get('spent', 0),
                'unspent_output_count': addr_data.get('unspent_output_count', 0)
            }
        )
    
    async def get_addresses_batch(self, addresses: List[str]) -> List[AddressInfo]:
        # Blockchair supports up to 100 addresses per request
        batch_size = 100
        results = []
        
        for i in range(0, len(addresses), batch_size):
            batch = addresses[i:i + batch_size]
            addresses_str = ','.join(batch)
            
            data = await self._make_request(f"/dashboards/addresses/{addresses_str}")
            
            for addr, info in data.get('data', {}).items():
                addr_data = info.get('address', {})
                results.append(AddressInfo(
                    address=addr,
                    balance=addr_data.get('balance', 0),
                    transaction_count=addr_data.get('transaction_count', 0),
                    last_activity=self._parse_timestamp(addr_data.get('last_seen')),
                    metadata={
                        'received': addr_data.get('received', 0),
                        'spent': addr_data.get('spent', 0)
                    }
                ))
        
        return results
    
    async def get_recent_transactions(self, address: str, limit: int = 10) -> List[Transaction]:
        params = {'limit': limit}
        data = await self._make_request(f"/dashboards/address/{address}/transactions", params)
        
        transactions = []
        for tx_data in data.get('data', {}).get(address, {}).get('transactions', []):
            transactions.append(Transaction(
                txid=tx_data.get('hash'),
                block_time=self._parse_timestamp(tx_data.get('time')),
                inputs=[],  # Simplified for now
                outputs=[],  # Simplified for now
                total_value=tx_data.get('balance_change', 0)
            ))
        
        return transactions
    
    def _parse_timestamp(self, timestamp: Optional[str]) -> Optional[datetime]:
        if not timestamp:
            return None
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            return None


class BlockCypherAPI(BlockchainAPI):
    """BlockCypher API implementation"""
    
    def __init__(self, session: ClientSession):
        super().__init__(session, settings.blockcypher_rate_limit)
        self.base_url = "https://api.blockcypher.com/v1/btc/main"
        self.api_key = settings.blockcypher_api_key
    
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        await self.rate_limiter.acquire()
        
        # Rate limiting is handled by the rate limiter above
        
        if params is None:
            params = {}
        if self.api_key:
            params['token'] = self.api_key
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise BlockchainAPIError(f"BlockCypher API error: {response.status} - {error_text}")
        except Exception as e:
            logger.error("BlockCypher API request failed", endpoint=endpoint, error=str(e))
            raise BlockchainAPIError(f"Request failed: {str(e)}")
    
    async def get_address_info(self, address: str) -> AddressInfo:
        data = await self._make_request(f"/addrs/{address}")
        
        return AddressInfo(
            address=address,
            balance=data.get('balance', 0),
            transaction_count=data.get('n_tx', 0),
            last_activity=None,  # BlockCypher doesn't provide this directly
            metadata={
                'total_received': data.get('total_received', 0),
                'total_sent': data.get('total_sent', 0),
                'unconfirmed_balance': data.get('unconfirmed_balance', 0)
            }
        )
    
    async def get_addresses_batch(self, addresses: List[str]) -> List[AddressInfo]:
        # BlockCypher doesn't support batch address queries in free tier
        # Process sequentially with rate limiting
        results = []
        for address in addresses:
            try:
                info = await self.get_address_info(address)
                results.append(info)
            except BlockchainAPIError as e:
                logger.error("Failed to get address info", address=address, error=str(e))
                
        return results
    
    async def get_recent_transactions(self, address: str, limit: int = 10) -> List[Transaction]:
        params = {'limit': limit}
        data = await self._make_request(f"/addrs/{address}", params)
        
        transactions = []
        for tx_ref in data.get('txrefs', [])[:limit]:
            transactions.append(Transaction(
                txid=tx_ref.get('tx_hash'),
                block_time=datetime.fromisoformat(tx_ref.get('confirmed', '').replace('Z', '+00:00')),
                inputs=[],  # Simplified
                outputs=[],  # Simplified
                total_value=tx_ref.get('value', 0)
            ))
        
        return transactions


class BlockchainManager:
    """Manages multiple blockchain API providers with fallback"""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.apis: List[BlockchainAPI] = []
        self.logger = logger.bind(component="blockchain_manager")
        self.request_counts = {"successful": 0, "failed": 0, "total": 0}
        self.preferred_api: Optional[str] = None
    
    async def initialize(self):
        """Initialize HTTP session and API clients"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'SatoshisEndgame/1.0'}
        )
        
        # Initialize APIs - prioritize ones with API keys
        blockchair = BlockchairAPI(self.session)
        blockcypher = BlockCypherAPI(self.session)
        
        # Order APIs based on whether they have keys
        if settings.blockcypher_api_key and not settings.blockchair_api_key:
            # BlockCypher has key, Blockchair doesn't - use BlockCypher first
            self.apis = [blockcypher, blockchair]
        elif settings.blockchair_api_key and not settings.blockcypher_api_key:
            # Blockchair has key, BlockCypher doesn't - use Blockchair first
            self.apis = [blockchair, blockcypher]
        else:
            # Both have keys or neither has keys - default order
            self.apis = [blockchair, blockcypher]
        
        api_status = []
        for api in self.apis:
            api_name = api.__class__.__name__
            has_key = False
            if isinstance(api, BlockchairAPI):
                has_key = bool(api.api_key)
            elif isinstance(api, BlockCypherAPI):
                has_key = bool(api.api_key)
            api_status.append(f"{api_name}({'with key' if has_key else 'no key'})")
        
        self.logger.info(
            "Blockchain manager initialized",
            api_count=len(self.apis),
            apis=" → ".join(api_status)
        )
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    async def get_address_info(self, address: str) -> Optional[AddressInfo]:
        """Get address info with automatic fallback"""
        for i, api in enumerate(self.apis):
            api_name = api.__class__.__name__
            try:
                self.logger.info(f"Fetching address info using {api_name}", address=address[:10] + "...")
                result = await api.get_address_info(address)
                if i > 0:
                    self.logger.info(f"Successfully fetched using fallback API: {api_name}")
                else:
                    self.logger.info(
                        f"✓ API Success",
                        api=api_name,
                        address=address[:10] + "...",
                        balance_btc=round(result.balance / 100_000_000, 8)
                    )
                self.request_counts["successful"] += 1
                return result
            except BlockchainAPIError as e:
                self.logger.warning(
                    f"API failed ({i+1}/{len(self.apis)}), trying next",
                    api=api_name,
                    error=str(e),
                    address=address[:10] + "..."
                )
                continue
        
        self.logger.error("All APIs failed for address", address=address[:10] + "...")
        self.request_counts["failed"] += 1
        return None
    
    async def get_addresses_batch(self, addresses: List[str]) -> List[AddressInfo]:
        """Get batch address info with automatic fallback"""
        import time
        for i, api in enumerate(self.apis):
            api_name = api.__class__.__name__
            try:
                start_time = time.time()
                self.logger.info(f"Fetching batch using {api_name}", batch_size=len(addresses))
                result = await api.get_addresses_batch(addresses)
                elapsed = time.time() - start_time
                if i > 0:
                    self.logger.info(f"Successfully fetched batch using fallback API: {api_name}", count=len(result), elapsed_seconds=round(elapsed, 2))
                else:
                    self.logger.info(
                        f"Successfully fetched batch",
                        api=api_name,
                        batch_size=len(addresses),
                        results=len(result),
                        total_btc=sum(r.balance for r in result) / 100_000_000,
                        elapsed_seconds=round(elapsed, 2)
                    )
                self.request_counts["successful"] += len(addresses)
                return result
            except BlockchainAPIError as e:
                self.logger.warning(
                    f"API failed for batch ({i+1}/{len(self.apis)}), trying next",
                    api=api_name,
                    error=str(e),
                    batch_size=len(addresses)
                )
                continue
        
        self.logger.error("All APIs failed for batch", batch_size=len(addresses))
        self.request_counts["failed"] += len(addresses)
        return []
    
    async def get_recent_transactions(self, address: str, limit: int = 10) -> List[Transaction]:
        """Get recent transactions with automatic fallback"""
        for api in self.apis:
            try:
                return await api.get_recent_transactions(address, limit)
            except BlockchainAPIError as e:
                self.logger.warning(
                    "API failed for transactions, trying next",
                    api=api.__class__.__name__,
                    error=str(e)
                )
                continue
        
        self.logger.error("All APIs failed for transactions", address=address)
        return []
    
    def get_request_stats(self) -> Dict[str, Any]:
        """Get API request statistics"""
        total = self.request_counts["successful"] + self.request_counts["failed"]
        success_rate = (self.request_counts["successful"] / total * 100) if total > 0 else 0
        
        return {
            "total_requests": total,
            "successful": self.request_counts["successful"],
            "failed": self.request_counts["failed"],
            "success_rate": round(success_rate, 2),
            "primary_api": self.apis[0].__class__.__name__ if self.apis else "None",
            "fallback_apis": [api.__class__.__name__ for api in self.apis[1:]] if len(self.apis) > 1 else []
        }
        
    async def get_latest_block_height(self) -> Optional[int]:
        """Get the latest block height"""
        for api in self.apis:
            try:
                # For now, we'll use a simple approach
                # In production, you'd implement proper block API endpoints
                # This is a placeholder that gets recent activity
                return 820000  # Placeholder - implement real API calls
            except Exception as e:
                self.logger.debug(f"API {api.__class__.__name__} failed to get block height", error=str(e))
                continue
                
        return None
        
    async def get_block(self, block_height: int) -> Optional[Dict]:
        """Get block data by height"""
        for api in self.apis:
            try:
                # Placeholder implementation
                # In production, you'd call actual block APIs
                return {
                    "height": block_height,
                    "timestamp": datetime.now(),
                    "transactions": []  # Would contain actual transaction data
                }
            except Exception as e:
                self.logger.debug(f"API {api.__class__.__name__} failed to get block", error=str(e))
                continue
                
        return None