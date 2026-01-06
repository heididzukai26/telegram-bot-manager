"""
Unit tests for main.py - Telegram Bot Manager

Tests cover:
- Input validation for orders
- Command handlers
- Error handling
- Order processing
- Inline menu creation
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    validate_order_input,
    format_order_summary,
    create_main_menu,
    create_order_type_menu,
    start_command,
    help_command,
    order_command,
    status_command,
    handle_text_message,
    handle_callback_query,
    active_orders,
)


class TestOrderValidation(unittest.TestCase):
    """Test order input validation."""
    
    def setUp(self):
        """Clear active orders before each test."""
        active_orders.clear()
    
    def test_validate_order_input_valid(self):
        """Test validation of valid order."""
        order_text = """user@example.com
Need 100 CP
Order type: safe_fast"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
        self.assertIsNotNone(order_data)
        self.assertEqual(order_data["cp_amount"], 100)
        self.assertEqual(order_data["order_type"], "safe_fast")
    
    def test_validate_order_input_empty(self):
        """Test validation with empty input."""
        is_valid, error, order_data = validate_order_input("")
        
        self.assertFalse(is_valid)
        self.assertIn("empty", error.lower())
        self.assertIsNone(order_data)
    
    def test_validate_order_input_none(self):
        """Test validation with None input."""
        is_valid, error, order_data = validate_order_input(None)
        
        self.assertFalse(is_valid)
        self.assertIn("empty", error.lower())
        self.assertIsNone(order_data)
    
    def test_validate_order_input_too_short(self):
        """Test validation with insufficient lines."""
        order_text = "user@example.com"
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertFalse(is_valid)
        self.assertIn("format", error.lower())
        self.assertIsNone(order_data)
    
    def test_validate_order_input_no_email(self):
        """Test validation without email address."""
        order_text = """Need 100 CP
Order type: safe_fast
Some other details"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertFalse(is_valid)
        self.assertIsNone(order_data)
    
    def test_validate_order_input_no_cp_amount(self):
        """Test validation without CP amount."""
        order_text = """user@example.com
Need some CP
Order type: safe_fast"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertFalse(is_valid)
        self.assertIsNone(order_data)
    
    def test_validate_order_input_invalid_type(self):
        """Test validation with invalid order type."""
        order_text = """user@example.com
Need 100 CP
Order type: invalid_type"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertFalse(is_valid)
        self.assertIsNone(order_data)
    
    def test_validate_order_input_zero_cp(self):
        """Test validation with zero CP amount."""
        # This should fail at CP extraction level
        order_text = """user@example.com
Need 0 safe_fast
Some details"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertFalse(is_valid)
    
    def test_validate_order_input_unsafe_type(self):
        """Test validation with unsafe order type."""
        order_text = """user@example.com
Need 50 CP
Order type: unsafe"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertTrue(is_valid)
        self.assertEqual(order_data["order_type"], "unsafe")
    
    def test_validate_order_input_fund_type(self):
        """Test validation with fund order type."""
        order_text = """user@example.com
Need 200 CP
Order type: fund"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertTrue(is_valid)
        self.assertEqual(order_data["order_type"], "fund")


class TestOrderFormatting(unittest.TestCase):
    """Test order data formatting."""
    
    def test_format_order_summary_basic(self):
        """Test basic order summary formatting."""
        order_data = {
            "cp_amount": 100,
            "order_type": "safe_fast",
            "status": "pending"
        }
        
        summary = format_order_summary(order_data)
        
        self.assertIn("100", summary)
        self.assertIn("Safe Fast", summary)
        self.assertIn("Pending", summary)
    
    def test_format_order_summary_unsafe(self):
        """Test formatting with unsafe type."""
        order_data = {
            "cp_amount": 500,
            "order_type": "unsafe",
            "status": "completed"
        }
        
        summary = format_order_summary(order_data)
        
        self.assertIn("500", summary)
        self.assertIn("Unsafe", summary)
        self.assertIn("Completed", summary)
    
    def test_format_order_summary_fund(self):
        """Test formatting with fund type."""
        order_data = {
            "cp_amount": 1000,
            "order_type": "fund",
            "status": "processing"
        }
        
        summary = format_order_summary(order_data)
        
        self.assertIn("1000", summary)
        self.assertIn("Fund", summary)


class TestMenuCreation(unittest.TestCase):
    """Test inline menu creation."""
    
    def test_create_main_menu(self):
        """Test main menu creation."""
        menu = create_main_menu()
        
        self.assertIsNotNone(menu)
        self.assertEqual(len(menu.inline_keyboard), 3)
        # Check button texts
        buttons_text = [btn.text for row in menu.inline_keyboard for btn in row]
        self.assertIn("📝 Submit Order", buttons_text)
        self.assertIn("📊 Order Status", buttons_text)
        self.assertIn("❓ Help", buttons_text)
    
    def test_create_order_type_menu(self):
        """Test order type menu creation."""
        menu = create_order_type_menu()
        
        self.assertIsNotNone(menu)
        self.assertEqual(len(menu.inline_keyboard), 5)
        # Check button texts
        buttons_text = [btn.text for row in menu.inline_keyboard for btn in row]
        self.assertIn("⚡ Unsafe", buttons_text)
        self.assertIn("💰 Fund (Safe 95%)", buttons_text)
        self.assertIn("🚀 Safe Fast", buttons_text)
        self.assertIn("🐢 Safe Slow", buttons_text)
        self.assertIn("🔙 Back", buttons_text)


class TestCommandHandlers(unittest.TestCase):
    """Test command handler functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        active_orders.clear()
    
    @patch('main.logger')
    async def test_start_command_success(self, mock_logger):
        """Test /start command with valid user."""
        # Create mock update and context
        update = Mock()
        update.effective_user = Mock(id=12345, username="testuser", first_name="Test")
        update.message = AsyncMock()
        context = Mock()
        
        await start_command(update, context)
        
        # Verify message was sent
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        self.assertIn("Welcome", call_args[0][0])
    
    @patch('main.logger')
    async def test_start_command_error(self, mock_logger):
        """Test /start command with error."""
        update = Mock()
        update.effective_user = Mock(id=12345, username="testuser", first_name="Test")
        update.message = AsyncMock()
        update.message.reply_text.side_effect = [Exception("Test error"), None]
        context = Mock()
        
        await start_command(update, context)
        
        # Verify error was logged
        mock_logger.error.assert_called()
    
    @patch('main.logger')
    async def test_help_command_message(self, mock_logger):
        """Test /help command via message."""
        update = Mock()
        update.effective_user = Mock(id=12345)
        update.message = AsyncMock()
        update.callback_query = None
        context = Mock()
        
        await help_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        self.assertIn("Help", call_args[0][0])
    
    @patch('main.logger')
    async def test_order_command(self, mock_logger):
        """Test /order command."""
        update = Mock()
        update.effective_user = Mock(id=12345)
        update.message = AsyncMock()
        context = Mock()
        
        await order_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        self.assertIn("Submit", call_args[0][0])
    
    @patch('main.logger')
    async def test_status_command_no_orders(self, mock_logger):
        """Test /status command with no orders."""
        update = Mock()
        update.effective_user = Mock(id=12345)
        update.message = AsyncMock()
        update.callback_query = None
        context = Mock()
        
        await status_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        self.assertIn("no active orders", call_args[0][0])
    
    @patch('main.logger')
    async def test_status_command_with_orders(self, mock_logger):
        """Test /status command with existing orders."""
        # Add a test order
        active_orders["12345_1"] = {
            "user_id": 12345,
            "cp_amount": 100,
            "order_type": "safe_fast",
            "status": "pending"
        }
        
        update = Mock()
        update.effective_user = Mock(id=12345)
        update.message = AsyncMock()
        update.callback_query = None
        context = Mock()
        
        await status_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        self.assertIn("Active Orders", call_args[0][0])
        self.assertIn("12345_1", call_args[0][0])


class TestMessageHandler(unittest.TestCase):
    """Test text message handler."""
    
    def setUp(self):
        """Set up test fixtures."""
        active_orders.clear()
    
    @patch('main.logger')
    @patch('main.ADMIN_GROUP_ID', None)
    async def test_handle_valid_order(self, mock_logger):
        """Test handling valid order message."""
        update = Mock()
        update.effective_user = Mock(id=12345, username="testuser", first_name="Test")
        update.message = AsyncMock()
        update.message.text = """user@example.com
Need 100 CP
Order type: safe_fast"""
        context = Mock()
        context.bot = AsyncMock()
        
        await handle_text_message(update, context)
        
        # Verify confirmation message was sent
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        self.assertIn("Successfully", call_args[0][0])
        
        # Verify order was stored
        self.assertEqual(len(active_orders), 1)
    
    @patch('main.logger')
    async def test_handle_invalid_order(self, mock_logger):
        """Test handling invalid order message."""
        update = Mock()
        update.effective_user = Mock(id=12345, username="testuser")
        update.message = AsyncMock()
        update.message.text = "Invalid order"
        context = Mock()
        
        await handle_text_message(update, context)
        
        # Verify error message was sent
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        self.assertIn("❌", call_args[0][0])
        
        # Verify no order was stored
        self.assertEqual(len(active_orders), 0)
    
    @patch('main.logger')
    @patch('main.ADMIN_GROUP_ID', '999999')
    async def test_handle_order_with_admin_notification(self, mock_logger):
        """Test order handling with admin notification."""
        update = Mock()
        update.effective_user = Mock(id=12345, username="testuser", first_name="Test")
        update.message = AsyncMock()
        update.message.text = """user@example.com
Need 200 unsafe
Additional details"""
        context = Mock()
        context.bot = AsyncMock()
        
        await handle_text_message(update, context)
        
        # Verify order confirmation
        update.message.reply_text.assert_called_once()
        
        # Verify admin notification was attempted
        context.bot.send_message.assert_called_once()


class TestCallbackHandler(unittest.TestCase):
    """Test callback query handler."""
    
    @patch('main.logger')
    async def test_main_menu_callback(self, mock_logger):
        """Test main menu callback."""
        update = Mock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "main_menu"
        update.callback_query.from_user = Mock(id=12345)
        context = Mock()
        
        await handle_callback_query(update, context)
        
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args
        self.assertIn("Main Menu", call_args[0][0])
    
    @patch('main.logger')
    async def test_submit_order_callback(self, mock_logger):
        """Test submit order callback."""
        update = Mock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "submit_order"
        update.callback_query.from_user = Mock(id=12345)
        context = Mock()
        
        await handle_callback_query(update, context)
        
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()
    
    @patch('main.logger')
    async def test_order_type_callback(self, mock_logger):
        """Test order type selection callback."""
        update = Mock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "type_safe_fast"
        update.callback_query.from_user = Mock(id=12345)
        context = Mock()
        context.user_data = {}
        
        await handle_callback_query(update, context)
        
        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once()
        # Verify order type was stored in context
        self.assertEqual(context.user_data["selected_order_type"], "safe_fast")
    
    @patch('main.logger')
    async def test_unknown_callback(self, mock_logger):
        """Test unknown callback data."""
        update = Mock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "unknown_action"
        update.callback_query.from_user = Mock(id=12345)
        context = Mock()
        
        await handle_callback_query(update, context)
        
        update.callback_query.answer.assert_called()
        call_args = update.callback_query.answer.call_args
        self.assertIn("Unknown", call_args[0][0])


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios."""
    
    def test_validate_order_with_special_characters(self):
        """Test order validation with special characters."""
        order_text = """user+test@example.com
Need 100 CP
Order type: safe_fast
Special chars: !@#$%"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        self.assertTrue(is_valid)
    
    def test_validate_order_with_unicode(self):
        """Test order validation with unicode characters."""
        order_text = """user@example.com
سفارش 100 CP
Order type: fund"""
        
        is_valid, error, order_data = validate_order_input(order_text)
        
        # Should still be valid as it has email, CP, and type
        self.assertTrue(is_valid)
    
    def test_format_order_with_underscores(self):
        """Test that underscores in order types are replaced."""
        order_data = {
            "cp_amount": 50,
            "order_type": "safe_slow",
            "status": "pending"
        }
        
        summary = format_order_summary(order_data)
        
        # Check that underscore is replaced with space
        self.assertIn("Safe Slow", summary)
        self.assertNotIn("safe_slow", summary)


# Run tests
if __name__ == "__main__":
    unittest.main()
