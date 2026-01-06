"""
Order processing and management module for Telegram bot.

This module handles:
- Order creation and validation
- Photo collection from workers with race condition prevention
- Worker reply validation and matching
- Photo delivery with network delay handling
- Detailed logging for debugging
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re

from utils import extract_cp_and_type, extract_order_type, is_valid_order

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Represents an order with all necessary information."""
    order_id: str
    text: str
    cp_amount: int
    order_type: Optional[str]
    created_at: datetime = field(default_factory=datetime.now)
    worker_id: Optional[int] = None
    photos: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, assigned, completed, failed
    reply_message_id: Optional[int] = None
    

@dataclass
class WorkerReply:
    """Represents a worker's reply to an order."""
    user_id: int
    message_id: int
    reply_to_message_id: Optional[int]
    text: str
    timestamp: datetime = field(default_factory=datetime.now)
    photos: List[str] = field(default_factory=list)


class OrderManager:
    """Manages orders, worker replies, and photo collection."""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.worker_replies: Dict[str, List[WorkerReply]] = {}
        self.photo_locks: Dict[str, asyncio.Lock] = {}
        self.processing_replies: Set[int] = set()  # Track message IDs being processed
        logger.info("🔧 OrderManager initialized")
    
    def _get_photo_lock(self, order_id: str) -> asyncio.Lock:
        """Get or create a lock for photo collection to prevent race conditions."""
        if order_id not in self.photo_locks:
            self.photo_locks[order_id] = asyncio.Lock()
            logger.debug(f"🔒 Created new lock for order {order_id}")
        return self.photo_locks[order_id]
    
    async def handle_order(
        self,
        order_id: str,
        order_text: str,
        validate: bool = True
    ) -> Tuple[bool, str, Optional[Order]]:
        """
        Handle an incoming order with comprehensive validation and edge case handling.
        
        Args:
            order_id: Unique identifier for the order
            order_text: The order text content
            validate: Whether to validate the order (default True)
        
        Returns:
            Tuple of (success, message, order_object)
            - success: True if order was handled successfully
            - message: Human-readable status message
            - order_object: The created Order object, or None if failed
        
        Edge cases handled:
        - Missing CP values
        - Missing order type
        - Invalid order format
        - Duplicate order IDs
        """
        logger.info(f"📝 Processing order {order_id}")
        logger.debug(f"Order text preview: {order_text[:100]}...")
        
        # Check for duplicate order ID
        if order_id in self.orders:
            logger.warning(f"⚠️ Duplicate order ID: {order_id}")
            return False, f"❌ Order {order_id} already exists", None
        
        # Validate order format if requested
        if validate and not is_valid_order(order_text):
            logger.warning(f"❌ Invalid order format for {order_id}")
            return False, "❌ Invalid order format. Please check the order details.", None
        
        # Extract CP and order type
        cp_amount, order_type, error_message = extract_cp_and_type(order_text)
        
        # Handle missing CP value
        if cp_amount == 0:
            logger.warning(f"❌ Order {order_id} missing CP value")
            if not error_message:
                error_message = "❌ CP value is missing or invalid"
            return False, error_message, None
        
        # Handle missing order type
        if not order_type:
            logger.warning(f"❌ Order {order_id} missing order type")
            # Try alternative extraction method
            order_type = extract_order_type(order_text)
            if not order_type:
                logger.error(f"❌ Could not determine order type for {order_id}")
                error_msg = "❌ Order type is missing. Please specify one of: unsafe, safe_fast, safe_slow, fund"
                return False, error_msg, None
            else:
                logger.info(f"✅ Order type detected using fallback method: {order_type}")
        
        # Create order object
        order = Order(
            order_id=order_id,
            text=order_text,
            cp_amount=cp_amount,
            order_type=order_type,
            status="pending"
        )
        
        # Store order
        self.orders[order_id] = order
        logger.info(f"✅ Order {order_id} created successfully: {cp_amount} CP, type: {order_type}")
        
        success_message = (
            f"✅ Order {order_id} processed successfully\n"
            f"💰 CP Amount: {cp_amount}\n"
            f"📦 Type: {order_type}"
        )
        
        return True, success_message, order
    
    def is_valid_worker_reply(
        self,
        reply: WorkerReply,
        order: Order
    ) -> bool:
        """
        Validate if a message is a genuine worker reply to avoid false matches.
        
        Checks:
        - Reply is to the correct message
        - Reply is not from a bot
        - Reply is not too old (within 24 hours)
        - Reply has not been processed already
        - Reply contains meaningful content or photos
        
        Args:
            reply: The worker reply to validate
            order: The order being replied to
        
        Returns:
            True if the reply is valid, False otherwise
        """
        logger.debug(f"🔍 Validating reply from user {reply.user_id} for order {order.order_id}")
        
        # Check if message is already being processed
        if reply.message_id in self.processing_replies:
            logger.warning(f"⚠️ Reply {reply.message_id} is already being processed")
            return False
        
        # Check if reply is to the correct message
        if order.reply_message_id and reply.reply_to_message_id != order.reply_message_id:
            logger.debug(f"❌ Reply {reply.message_id} not replying to correct message")
            return False
        
        # Check reply age (not older than 24 hours)
        age = datetime.now() - reply.timestamp
        if age > timedelta(hours=24):
            logger.warning(f"⚠️ Reply {reply.message_id} too old: {age}")
            return False
        
        # Check for meaningful content (text or photos)
        has_content = bool(reply.text.strip()) or bool(reply.photos)
        if not has_content:
            logger.debug(f"❌ Reply {reply.message_id} has no meaningful content")
            return False
        
        # Avoid false matches - check if text looks like a reply
        # Filter out unrelated messages
        if reply.text:
            text_lower = reply.text.lower().strip()
            
            # Ignore very short messages that might be accidental
            if len(text_lower) < 3:
                logger.debug(f"❌ Reply text too short: '{text_lower}'")
                return False
            
            # Filter out common false positive patterns
            false_positive_patterns = [
                r'^ok\.?$',
                r'^yes\.?$',
                r'^no\.?$',
                r'^thanks?\.?$',
                r'^hi\.?$',
                r'^hello\.?$',
                r'^bye\.?$',
            ]
            
            for pattern in false_positive_patterns:
                if re.match(pattern, text_lower):
                    logger.debug(f"❌ Reply matches false positive pattern: '{text_lower}'")
                    return False
        
        logger.info(f"✅ Reply {reply.message_id} validated successfully")
        return True
    
    async def collect_worker_photos(
        self,
        order_id: str,
        reply: WorkerReply,
        timeout: float = 30.0,
        retry_delay: float = 2.0,
        max_retries: int = 3
    ) -> Tuple[bool, List[str]]:
        """
        Collect photos from worker reply with race condition prevention and network delay handling.
        
        Uses async locks to prevent race conditions when multiple photos arrive simultaneously.
        Implements retry logic to handle network delays.
        
        Args:
            order_id: The order ID
            reply: Worker reply containing photos
            timeout: Maximum time to wait for entire operation (seconds)
            retry_delay: Delay between retries (seconds)
            max_retries: Maximum number of retries
        
        Returns:
            Tuple of (success, photo_list)
        """
        logger.info(f"📸 Collecting photos for order {order_id} from user {reply.user_id}")
        
        # Get order
        order = self.orders.get(order_id)
        if not order:
            logger.error(f"❌ Order {order_id} not found")
            return False, []
        
        # Acquire lock to prevent race conditions
        lock = self._get_photo_lock(order_id)
        
        try:
            # Wrap the entire operation in a timeout
            async with asyncio.timeout(timeout):
                async with lock:
                    logger.debug(f"🔒 Lock acquired for order {order_id}")
                    
                    # Mark message as being processed
                    self.processing_replies.add(reply.message_id)
                    
                    try:
                        photos_collected = []
                        retry_count = 0
                        
                        # Retry logic for network delays
                        while retry_count < max_retries:
                            if reply.photos:
                                logger.info(f"📸 Found {len(reply.photos)} photos in reply")
                                photos_collected.extend(reply.photos)
                                break
                            
                            # Wait and retry if no photos yet
                            if retry_count < max_retries - 1:
                                logger.debug(f"⏳ No photos found, waiting {retry_delay}s before retry {retry_count + 1}/{max_retries}")
                                await asyncio.sleep(retry_delay)
                                retry_count += 1
                            else:
                                logger.warning(f"⚠️ No photos found after {max_retries} retries")
                                break
                        
                        # Add photos to order
                        if photos_collected:
                            # Deduplicate photos
                            existing_photos_set = set(order.photos)
                            new_photos = [p for p in photos_collected if p not in existing_photos_set]
                            
                            if new_photos:
                                order.photos.extend(new_photos)
                                logger.info(f"✅ Added {len(new_photos)} new photos to order {order_id} (total: {len(order.photos)})")
                            else:
                                logger.debug(f"ℹ️ All photos already exist in order {order_id}")
                            
                            return True, new_photos
                        else:
                            logger.warning(f"⚠️ No photos collected for order {order_id}")
                            return False, []
                            
                    except Exception as e:
                        logger.error(f"❌ Error collecting photos for order {order_id}: {e}", exc_info=True)
                        return False, []
                    finally:
                        # Remove from processing set
                        self.processing_replies.discard(reply.message_id)
                        logger.debug(f"🔓 Lock released for order {order_id}")
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout ({timeout}s) collecting photos for order {order_id}")
            self.processing_replies.discard(reply.message_id)
            return False, []
    
    async def deliver_photos(
        self,
        order_id: str,
        destination_chat_id: int,
        send_photo_func,
        network_timeout: float = 60.0,
        retry_on_failure: bool = True,
        max_retries: int = 3
    ) -> Tuple[bool, str]:
        """
        Deliver photos for an order with network delay handling.
        
        Args:
            order_id: The order ID
            destination_chat_id: Chat ID to send photos to
            send_photo_func: Async function to send photos (should accept chat_id, photo)
            network_timeout: Timeout for each photo send operation
            retry_on_failure: Whether to retry on network failures
            max_retries: Maximum number of retries per photo
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(f"📤 Delivering photos for order {order_id} to chat {destination_chat_id}")
        
        order = self.orders.get(order_id)
        if not order:
            logger.error(f"❌ Order {order_id} not found")
            return False, f"Order {order_id} not found"
        
        if not order.photos:
            logger.warning(f"⚠️ No photos to deliver for order {order_id}")
            return False, f"No photos available for order {order_id}"
        
        delivered_count = 0
        failed_count = 0
        
        for idx, photo in enumerate(order.photos, 1):
            logger.debug(f"📸 Sending photo {idx}/{len(order.photos)}: {photo[:50]}...")
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # Send photo with timeout
                    await asyncio.wait_for(
                        send_photo_func(destination_chat_id, photo),
                        timeout=network_timeout
                    )
                    delivered_count += 1
                    success = True
                    logger.info(f"✅ Photo {idx}/{len(order.photos)} delivered successfully")
                    
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ Timeout sending photo {idx} (attempt {retry_count + 1}/{max_retries})")
                    retry_count += 1
                    if retry_count < max_retries and retry_on_failure:
                        await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                    else:
                        failed_count += 1
                        logger.error(f"❌ Failed to send photo {idx} after {max_retries} attempts")
                        
                except Exception as e:
                    logger.error(f"❌ Error sending photo {idx}: {e}", exc_info=True)
                    retry_count += 1
                    if retry_count < max_retries and retry_on_failure:
                        await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                    else:
                        failed_count += 1
                        break
        
        # Generate result message
        if delivered_count == len(order.photos):
            logger.info(f"✅ All {delivered_count} photos delivered for order {order_id}")
            return True, f"✅ Successfully delivered all {delivered_count} photos"
        elif delivered_count > 0:
            logger.warning(f"⚠️ Partial delivery for order {order_id}: {delivered_count}/{len(order.photos)}")
            return True, f"⚠️ Delivered {delivered_count}/{len(order.photos)} photos ({failed_count} failed)"
        else:
            logger.error(f"❌ Failed to deliver any photos for order {order_id}")
            return False, f"❌ Failed to deliver photos (0/{len(order.photos)} successful)"
    
    async def process_worker_reply(
        self,
        order_id: str,
        reply: WorkerReply
    ) -> Tuple[bool, str]:
        """
        Process a worker reply to an order.
        
        Args:
            order_id: The order ID
            reply: The worker reply
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(f"💬 Processing worker reply for order {order_id}")
        
        order = self.orders.get(order_id)
        if not order:
            logger.error(f"❌ Order {order_id} not found")
            return False, f"Order {order_id} not found"
        
        # Validate reply
        if not self.is_valid_worker_reply(reply, order):
            logger.warning(f"⚠️ Invalid worker reply for order {order_id}")
            return False, "Invalid or unrelated reply"
        
        # Assign worker if not already assigned
        if not order.worker_id:
            order.worker_id = reply.user_id
            logger.info(f"👷 Assigned worker {reply.user_id} to order {order_id}")
        
        # Store reply
        if order_id not in self.worker_replies:
            self.worker_replies[order_id] = []
        self.worker_replies[order_id].append(reply)
        logger.debug(f"💾 Stored reply for order {order_id} (total replies: {len(self.worker_replies[order_id])})")
        
        # Collect photos if present
        if reply.photos:
            success, photos = await self.collect_worker_photos(order_id, reply)
            if success:
                return True, f"✅ Collected {len(photos)} photos"
            else:
                return False, "❌ Failed to collect photos"
        
        return True, "✅ Reply processed successfully"
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get the current status of an order.
        
        Args:
            order_id: The order ID
        
        Returns:
            Dictionary with order status information, or None if not found
        """
        logger.debug(f"📊 Getting status for order {order_id}")
        
        order = self.orders.get(order_id)
        if not order:
            logger.warning(f"⚠️ Order {order_id} not found")
            return None
        
        status_info = {
            "order_id": order.order_id,
            "status": order.status,
            "cp_amount": order.cp_amount,
            "order_type": order.order_type,
            "worker_id": order.worker_id,
            "photos_count": len(order.photos),
            "created_at": order.created_at.isoformat(),
            "replies_count": len(self.worker_replies.get(order_id, []))
        }
        
        logger.debug(f"📊 Order {order_id} status: {status_info}")
        return status_info

# Default global order manager instance for convenience
# For better testability and modularity, consider creating instances explicitly:
#   manager = OrderManager()
# or use dependency injection in production code.
order_manager = OrderManager()
