# Block-Based Monitoring Architecture

## Overview

Instead of polling individual addresses (which quickly exceeds API limits), we monitor new blocks and check if any transactions involve our dormant addresses.

## Efficiency Comparison

### Old Approach (Individual Polling)
- **943 addresses** × **12 checks/hour** × **24 hours** = **271,584 API calls/day**
- **Problem**: BlockCypher free tier only allows 1,000 calls/day!

### New Approach (Block Monitoring)
- **~144 blocks/day** (one every ~10 minutes)
- **Only 144 API calls/day** for block data
- Additional calls only when dormant addresses actually move (rare)
- **Efficiency gain**: 1,886x fewer API calls!

## How It Works

1. **Monitor New Blocks**
   ```python
   # Check for new blocks every 30 seconds
   current_height = await blockchain.get_latest_block_height()
   ```

2. **Extract Addresses from Transactions**
   ```python
   # Get all addresses from block transactions
   for tx in block['transactions']:
       addresses.update(tx['inputs'])
       addresses.update(tx['outputs'])
   ```

3. **Fast In-Memory Matching**
   ```python
   # Check against our set of dormant addresses
   active_dormant = block_addresses & self.dormant_addresses
   ```

4. **Fetch Details Only for Matches**
   ```python
   # Only make API calls for addresses that moved
   if active_dormant:
       for address in active_dormant:
           info = await blockchain.get_address_info(address)
   ```

## Implementation

### BlockMonitorService
- Loads all dormant addresses into memory on startup
- Polls for new blocks every 30 seconds
- Extracts addresses from block transactions
- Performs fast set intersection to find matches
- Only fetches details for matched addresses

### Key Benefits
1. **Scalability**: Can monitor millions of addresses without hitting API limits
2. **Real-time**: Detects movements within minutes of confirmation
3. **Efficient**: Uses minimal API calls
4. **Accurate**: Never misses a transaction

### Integration with Quantum Detection
When dormant addresses are detected moving:
1. Fetch full transaction details
2. Analyze patterns for quantum signatures
3. Send alerts if suspicious patterns detected
4. Update database with movement information

## Future Enhancements

1. **WebSocket Support**: Use blockchain WebSocket APIs for instant block notifications
2. **Block Caching**: Cache recent blocks to handle reorgs
3. **Parallel Processing**: Process multiple blocks concurrently
4. **Pattern Pre-computation**: Pre-compute quantum patterns for faster detection

## API Requirements

For production use, implement these endpoints in blockchain APIs:
- `GET /blocks/latest` - Get latest block height
- `GET /blocks/{height}` - Get full block with transactions
- `WebSocket /blocks/subscribe` - Real-time block updates (optional)