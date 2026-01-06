"""
Comprehensive test suite for orders.py module.

Tests cover:
- Edge cases (missing CP, missing order type)
- Photo delivery logic
- Worker reply validation
- Order processing
- Race condition handling
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from orders import Order, WorkerReply, OrderManager


class TestOrderEdgeCases:
    """Test edge cases in order handling."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh OrderManager for each test."""
        return OrderManager()
    
    @pytest.mark.asyncio
    async def test_handle_order_missing_cp_value(self, manager):
        """Test handling order with missing CP value."""
        order_text = """
        test@example.com
        This is an order without CP value
        safe_fast
        """
        
        success, message, order = await manager.handle_order(
            "order_001",
            order_text,
            validate=False
        )
        
        assert not success
        assert "CP" in message or "مقدار" in message
        assert order is None
        assert "order_001" not in manager.orders
    
    @pytest.mark.asyncio
    async def test_handle_order_missing_order_type(self, manager):
        """Test handling order with missing order type."""
        order_text = """
        test@example.com
        This is an order
        Need 100 items but no type specified
        """
        
        success, message, order = await manager.handle_order(
            "order_002",
            order_text,
            validate=False
        )
        
        assert not success
        assert "type" in message.lower() or "نوع" in message
        assert order is None
        assert "order_002" not in manager.orders
    
    @pytest.mark.asyncio
    async def test_handle_order_duplicate_id(self, manager):
        """Test handling duplicate order IDs."""
        order_text = """
        test@example.com
        Order with 100 unsafe
        Valid order text
        """
        
        # First order should succeed
        success1, message1, order1 = await manager.handle_order(
            "order_003",
            order_text,
            validate=False
        )
        assert success1
        assert order1 is not None
        
        # Duplicate should fail
        success2, message2, order2 = await manager.handle_order(
            "order_003",
            order_text,
            validate=False
        )
        assert not success2
        assert "already exists" in message2.lower() or "duplicate" in message2.lower()
        assert order2 is None
    
    @pytest.mark.asyncio
    async def test_handle_order_with_fallback_type_detection(self, manager):
        """Test order type detection using fallback method."""
        order_text = """
        test@example.com
        Need 50 fund
        This is a fund order
        """
        
        success, message, order = await manager.handle_order(
            "order_004",
            order_text,
            validate=False
        )
        
        # Should succeed using fallback extraction
        assert success
        assert order is not None
        assert order.order_type == "fund"
    
    @pytest.mark.asyncio
    async def test_handle_order_valid(self, manager):
        """Test handling valid order."""
        order_text = """
        test@example.com
        Need 100 unsafe
        Valid order text
        """
        
        success, message, order = await manager.handle_order(
            "order_005",
            order_text,
            validate=False
        )
        
        assert success
        assert order is not None
        assert order.order_id == "order_005"
        assert order.cp_amount == 100
        assert order.order_type == "unsafe"
        assert order.status == "pending"


class TestWorkerReplyValidation:
    """Test worker reply validation logic."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh OrderManager for each test."""
        return OrderManager()
    
    @pytest.fixture
    def sample_order(self, manager):
        """Create a sample order for testing."""
        order = Order(
            order_id="test_order",
            text="test@example.com\n100 unsafe\nTest order",
            cp_amount=100,
            order_type="unsafe",
            reply_message_id=12345
        )
        manager.orders["test_order"] = order
        return order
    
    def test_valid_worker_reply(self, manager, sample_order):
        """Test validation of a valid worker reply."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="Here are the photos you requested",
            photos=["photo1.jpg"]
        )
        
        assert manager.is_valid_worker_reply(reply, sample_order)
    
    def test_reply_wrong_message_id(self, manager, sample_order):
        """Test rejection of reply to wrong message."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=99999,  # Wrong message ID
            text="Here are the photos",
            photos=["photo1.jpg"]
        )
        
        assert not manager.is_valid_worker_reply(reply, sample_order)
    
    def test_reply_too_old(self, manager, sample_order):
        """Test rejection of old replies."""
        old_timestamp = datetime.now() - timedelta(hours=25)
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="Here are the photos",
            timestamp=old_timestamp
        )
        
        assert not manager.is_valid_worker_reply(reply, sample_order)
    
    def test_reply_no_content(self, manager, sample_order):
        """Test rejection of empty replies."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="",
            photos=[]
        )
        
        assert not manager.is_valid_worker_reply(reply, sample_order)
    
    def test_reply_too_short(self, manager, sample_order):
        """Test rejection of very short replies."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="ok",
            photos=[]
        )
        
        assert not manager.is_valid_worker_reply(reply, sample_order)
    
    def test_reply_false_positive_patterns(self, manager, sample_order):
        """Test rejection of common false positive messages."""
        false_positives = ["ok", "yes", "no", "thanks", "hi", "hello", "bye"]
        
        for text in false_positives:
            reply = WorkerReply(
                user_id=99999,
                message_id=67890,
                reply_to_message_id=12345,
                text=text,
                photos=[]
            )
            assert not manager.is_valid_worker_reply(reply, sample_order)
    
    def test_reply_already_processing(self, manager, sample_order):
        """Test rejection of already-processing replies."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="Here are the photos",
            photos=["photo1.jpg"]
        )
        
        # Mark as processing
        manager.processing_replies.add(67890)
        
        assert not manager.is_valid_worker_reply(reply, sample_order)


class TestPhotoCollection:
    """Test photo collection logic with race condition handling."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh OrderManager for each test."""
        return OrderManager()
    
    @pytest.fixture
    def sample_order(self, manager):
        """Create a sample order for testing."""
        order = Order(
            order_id="photo_test_order",
            text="test@example.com\n100 unsafe\nTest order",
            cp_amount=100,
            order_type="unsafe"
        )
        manager.orders["photo_test_order"] = order
        return order
    
    @pytest.mark.asyncio
    async def test_collect_photos_success(self, manager, sample_order):
        """Test successful photo collection."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="Photos attached",
            photos=["photo1.jpg", "photo2.jpg"]
        )
        
        success, photos = await manager.collect_worker_photos(
            "photo_test_order",
            reply,
            max_retries=1
        )
        
        assert success
        assert len(photos) == 2
        assert len(sample_order.photos) == 2
    
    @pytest.mark.asyncio
    async def test_collect_photos_no_photos(self, manager, sample_order):
        """Test photo collection when no photos are present."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="No photos here",
            photos=[]
        )
        
        success, photos = await manager.collect_worker_photos(
            "photo_test_order",
            reply,
            max_retries=1
        )
        
        assert not success
        assert len(photos) == 0
    
    @pytest.mark.asyncio
    async def test_collect_photos_deduplicate(self, manager, sample_order):
        """Test photo deduplication."""
        # Add initial photos
        sample_order.photos = ["photo1.jpg", "photo2.jpg"]
        
        # Try to add duplicate and new photo
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="More photos",
            photos=["photo2.jpg", "photo3.jpg"]  # photo2 is duplicate
        )
        
        success, photos = await manager.collect_worker_photos(
            "photo_test_order",
            reply,
            max_retries=1
        )
        
        assert success
        assert len(photos) == 1  # Only photo3 is new
        assert "photo3.jpg" in photos
        assert len(sample_order.photos) == 3  # Total of 3 photos
    
    @pytest.mark.asyncio
    async def test_collect_photos_race_condition(self, manager, sample_order):
        """Test that locks prevent race conditions."""
        reply1 = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="Photos 1",
            photos=["photo1.jpg"]
        )
        
        reply2 = WorkerReply(
            user_id=88888,
            message_id=67891,
            reply_to_message_id=12345,
            text="Photos 2",
            photos=["photo2.jpg"]
        )
        
        # Collect photos concurrently
        results = await asyncio.gather(
            manager.collect_worker_photos("photo_test_order", reply1, max_retries=1),
            manager.collect_worker_photos("photo_test_order", reply2, max_retries=1)
        )
        
        # Both should succeed
        assert results[0][0]  # First collection success
        assert results[1][0]  # Second collection success
        
        # Total photos should be 2 (no race condition issues)
        assert len(sample_order.photos) == 2
    
    @pytest.mark.asyncio
    async def test_collect_photos_order_not_found(self, manager):
        """Test photo collection for non-existent order."""
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="Photos",
            photos=["photo1.jpg"]
        )
        
        success, photos = await manager.collect_worker_photos(
            "nonexistent_order",
            reply,
            max_retries=1
        )
        
        assert not success
        assert len(photos) == 0


class TestPhotoDelivery:
    """Test photo delivery with network delay handling."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh OrderManager for each test."""
        return OrderManager()
    
    @pytest.fixture
    def sample_order(self, manager):
        """Create a sample order with photos."""
        order = Order(
            order_id="delivery_test_order",
            text="test@example.com\n100 unsafe\nTest order",
            cp_amount=100,
            order_type="unsafe",
            photos=["photo1.jpg", "photo2.jpg", "photo3.jpg"]
        )
        manager.orders["delivery_test_order"] = order
        return order
    
    @pytest.mark.asyncio
    async def test_deliver_photos_success(self, manager, sample_order):
        """Test successful photo delivery."""
        send_photo_mock = AsyncMock()
        
        success, message = await manager.deliver_photos(
            "delivery_test_order",
            12345,
            send_photo_mock,
            network_timeout=5.0,
            max_retries=1
        )
        
        assert success
        assert "3" in message  # All 3 photos
        assert send_photo_mock.call_count == 3
    
    @pytest.mark.asyncio
    async def test_deliver_photos_no_photos(self, manager):
        """Test photo delivery when no photos exist."""
        order = Order(
            order_id="no_photos_order",
            text="test@example.com\n100 unsafe\nTest order",
            cp_amount=100,
            order_type="unsafe",
            photos=[]
        )
        manager.orders["no_photos_order"] = order
        
        send_photo_mock = AsyncMock()
        
        success, message = await manager.deliver_photos(
            "no_photos_order",
            12345,
            send_photo_mock,
            max_retries=1
        )
        
        assert not success
        assert "no photos" in message.lower()
        assert send_photo_mock.call_count == 0
    
    @pytest.mark.asyncio
    async def test_deliver_photos_network_timeout(self, manager, sample_order):
        """Test photo delivery with network timeout."""
        send_photo_mock = AsyncMock(side_effect=asyncio.TimeoutError())
        
        success, message = await manager.deliver_photos(
            "delivery_test_order",
            12345,
            send_photo_mock,
            network_timeout=1.0,
            retry_on_failure=False,
            max_retries=1
        )
        
        assert not success
        assert "failed" in message.lower()
    
    @pytest.mark.asyncio
    async def test_deliver_photos_partial_success(self, manager, sample_order):
        """Test photo delivery with partial failures."""
        # First photo succeeds, second fails, third succeeds
        send_photo_mock = AsyncMock(
            side_effect=[None, Exception("Network error"), None]
        )
        
        success, message = await manager.deliver_photos(
            "delivery_test_order",
            12345,
            send_photo_mock,
            network_timeout=5.0,
            retry_on_failure=False,
            max_retries=1
        )
        
        # Should report partial success
        assert success  # At least some photos delivered
        assert "2/3" in message or "2 photos" in message.lower()
    
    @pytest.mark.asyncio
    async def test_deliver_photos_retry_on_failure(self, manager, sample_order):
        """Test photo delivery with retry on failure."""
        # Fail first time, succeed second time
        call_count = {"count": 0}
        
        async def send_photo_with_retry(chat_id, photo):
            call_count["count"] += 1
            if call_count["count"] <= 3:  # Fail first 3 attempts (one per photo)
                raise Exception("Network error")
            # Succeed on retries
            return None
        
        send_photo_mock = AsyncMock(side_effect=send_photo_with_retry)
        
        success, message = await manager.deliver_photos(
            "delivery_test_order",
            12345,
            send_photo_mock,
            network_timeout=5.0,
            retry_on_failure=True,
            max_retries=2
        )
        
        assert success
        # Should have retried and succeeded
        assert send_photo_mock.call_count > 3
    
    @pytest.mark.asyncio
    async def test_deliver_photos_order_not_found(self, manager):
        """Test photo delivery for non-existent order."""
        send_photo_mock = AsyncMock()
        
        success, message = await manager.deliver_photos(
            "nonexistent_order",
            12345,
            send_photo_mock,
            max_retries=1
        )
        
        assert not success
        assert "not found" in message.lower()


class TestOrderProcessing:
    """Test complete order processing workflow."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh OrderManager for each test."""
        return OrderManager()
    
    @pytest.mark.asyncio
    async def test_process_worker_reply_success(self, manager):
        """Test processing valid worker reply."""
        # Create order
        order_text = """
        test@example.com
        Need 100 unsafe
        Test order
        """
        await manager.handle_order("process_order_001", order_text, validate=False)
        
        order = manager.orders["process_order_001"]
        order.reply_message_id = 12345
        
        # Create reply
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="Working on it",
            photos=["photo1.jpg"]
        )
        
        success, message = await manager.process_worker_reply("process_order_001", reply)
        
        assert success
        assert order.worker_id == 99999
        assert len(order.photos) == 1
    
    @pytest.mark.asyncio
    async def test_process_worker_reply_invalid(self, manager):
        """Test processing invalid worker reply."""
        # Create order
        order_text = """
        test@example.com
        Need 100 unsafe
        Test order
        """
        await manager.handle_order("process_order_002", order_text, validate=False)
        
        order = manager.orders["process_order_002"]
        order.reply_message_id = 12345
        
        # Create invalid reply (too short)
        reply = WorkerReply(
            user_id=99999,
            message_id=67890,
            reply_to_message_id=12345,
            text="ok",  # Too short, false positive
            photos=[]
        )
        
        success, message = await manager.process_worker_reply("process_order_002", reply)
        
        assert not success
        assert "invalid" in message.lower()
    
    @pytest.mark.asyncio
    async def test_get_order_status(self, manager):
        """Test getting order status."""
        # Create order
        order_text = """
        test@example.com
        Need 100 unsafe
        Test order
        """
        await manager.handle_order("status_order_001", order_text, validate=False)
        
        status = manager.get_order_status("status_order_001")
        
        assert status is not None
        assert status["order_id"] == "status_order_001"
        assert status["cp_amount"] == 100
        assert status["order_type"] == "unsafe"
        assert status["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_get_order_status_not_found(self, manager):
        """Test getting status for non-existent order."""
        status = manager.get_order_status("nonexistent_order")
        
        assert status is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
