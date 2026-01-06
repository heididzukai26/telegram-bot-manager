#!/usr/bin/env python3
"""
Telegram Bot Manager - Main Bot Application

This bot manages orders, worker coordination, and team communication.
Features:
- Order management with inline menus
- Input validation for incomplete/malformed orders
- Admin controls
- Worker reply tracking
- Comprehensive error handling and logging
"""

import os
import logging
import time
from typing import Optional, Dict, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from utils import (
    is_admin,
    is_valid_order,
    extract_cp_and_type,
    extract_order_type,
)

# ==================== LOGGING SETUP ====================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")
WORKER_GROUP_ID = os.getenv("WORKER_GROUP_ID")

# Store active orders (in production, use a database)
active_orders: Dict[str, Dict[str, Any]] = {}

# ==================== HELPER FUNCTIONS ====================

def create_main_menu() -> InlineKeyboardMarkup:
    """Create the main menu inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("📝 Submit Order", callback_data="submit_order")],
        [InlineKeyboardButton("📊 Order Status", callback_data="check_status")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_order_type_menu() -> InlineKeyboardMarkup:
    """Create order type selection menu."""
    keyboard = [
        [InlineKeyboardButton("⚡ Unsafe", callback_data="type_unsafe")],
        [InlineKeyboardButton("💰 Fund (Safe 95%)", callback_data="type_fund")],
        [InlineKeyboardButton("🚀 Safe Fast", callback_data="type_safe_fast")],
        [InlineKeyboardButton("🐢 Safe Slow", callback_data="type_safe_slow")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def validate_order_input(order_text: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validate order input and extract order details.
    
    Args:
        order_text: The order text to validate
        
    Returns:
        tuple: (is_valid, error_message, order_data)
            - is_valid: True if order is valid
            - error_message: Error description if invalid, empty if valid
            - order_data: Dictionary with extracted order info if valid
    """
    if not order_text or not isinstance(order_text, str):
        return False, "❌ Order text is empty or invalid.", None
    
    # Check if it's a valid order format
    if not is_valid_order(order_text):
        return False, (
            "❌ Invalid order format. Please ensure:\n"
            "• Order has at least 3 lines\n"
            "• Includes an email address\n"
            "• Specifies CP amount and order type\n"
            "• Order type is one of: unsafe, fund, safe_fast, safe_slow"
        ), None
    
    # Extract CP and order type
    cp_amount, order_type, error = extract_cp_and_type(order_text)
    
    if error:
        return False, error, None
    
    # Additional validation
    if cp_amount <= 0:
        return False, "❌ CP amount must be greater than 0.", None
    
    order_data = {
        "text": order_text,
        "cp_amount": cp_amount,
        "order_type": order_type,
        "status": "pending"
    }
    
    return True, "", order_data


def format_order_summary(order_data: Dict[str, Any]) -> str:
    """
    Format order data for display.
    
    Args:
        order_data: Dictionary containing order information
        
    Returns:
        Formatted string with order details
    """
    cp_amount = order_data.get('cp_amount', 0)
    order_type = order_data.get('order_type', 'unknown')
    status = order_data.get('status', 'unknown')
    
    return (
        f"📋 **Order Summary**\n\n"
        f"💎 CP Amount: {cp_amount}\n"
        f"📦 Order Type: {order_type.replace('_', ' ').title()}\n"
        f"📌 Status: {status.title()}\n"
    )


# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command - show welcome message and main menu.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started the bot")
        
        welcome_text = (
            f"👋 Welcome {user.first_name}!\n\n"
            f"I'm your order management bot. I can help you:\n"
            f"• Submit and track orders\n"
            f"• Check order status\n"
            f"• Get help and support\n\n"
            f"Choose an option below to get started:"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=create_main_menu(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in start_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred. Please try again later."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command - display help information.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        logger.info(f"Help command called by user {update.effective_user.id}")
        
        help_text = (
            "📚 **Help & Instructions**\n\n"
            "**Commands:**\n"
            "/start - Start the bot and show main menu\n"
            "/help - Show this help message\n"
            "/order - Submit a new order\n"
            "/status - Check order status\n\n"
            "**Order Format:**\n"
            "Your order should include:\n"
            "• Email address\n"
            "• CP amount (e.g., 50, 100, 500)\n"
            "• Order type: unsafe, fund, safe_fast, or safe_slow\n"
            "• At least 3 lines of text\n\n"
            "**Example:**\n"
            "user@example.com\n"
            "Need 100 CP\n"
            "Order type: safe_fast\n\n"
            "Use the inline buttons for easy navigation!"
        )
        
        if update.message:
            await update.message.reply_text(help_text, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in help_command: {e}", exc_info=True)
        error_msg = "❌ Could not display help information."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)


async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /order command - initiate order submission.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        user_id = update.effective_user.id
        logger.info(f"Order command called by user {user_id}")
        
        order_text = (
            "📝 **Submit New Order**\n\n"
            "Please choose your order type, or send your order details directly:\n\n"
            "Your message should include:\n"
            "• Email address\n"
            "• CP amount\n"
            "• Order type\n"
        )
        
        await update.message.reply_text(
            order_text,
            reply_markup=create_order_type_menu(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in order_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Could not process order command. Please try again."
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /status command - check order status.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        user_id = update.effective_user.id
        logger.info(f"Status command called by user {user_id}")
        
        # Find user's orders
        user_orders = {
            order_id: order
            for order_id, order in active_orders.items()
            if order.get("user_id") == user_id
        }
        
        if not user_orders:
            status_text = "📊 You have no active orders."
        else:
            status_text = f"📊 **Your Active Orders** ({len(user_orders)}):\n\n"
            for order_id, order in user_orders.items():
                status_text += (
                    f"Order #{order_id}\n"
                    f"{format_order_summary(order)}\n"
                )
        
        if update.message:
            await update.message.reply_text(status_text, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                status_text,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in status_command: {e}", exc_info=True)
        error_msg = "❌ Could not retrieve order status."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)


# ==================== MESSAGE HANDLERS ====================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming text messages (potential orders).
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        user = update.effective_user
        message_text = update.message.text
        
        logger.info(f"Text message from user {user.id}: {message_text[:50]}...")
        
        # Validate the order
        is_valid, error_message, order_data = validate_order_input(message_text)
        
        if not is_valid:
            logger.warning(f"Invalid order from user {user.id}: {error_message}")
            await update.message.reply_text(
                f"{error_message}\n\n"
                f"Need help? Use /help to see order format requirements.",
                parse_mode="Markdown"
            )
            return
        
        # Generate order ID using timestamp for uniqueness
        order_id = f"{user.id}_{int(time.time() * 1000)}"
        order_data["user_id"] = user.id
        order_data["username"] = user.username or user.first_name
        
        # Store order
        active_orders[order_id] = order_data
        
        logger.info(f"Order {order_id} created successfully for user {user.id}")
        
        # Send confirmation
        confirmation = (
            f"✅ **Order Submitted Successfully!**\n\n"
            f"Order ID: #{order_id}\n"
            f"{format_order_summary(order_data)}\n"
            f"We'll process your order shortly!"
        )
        
        await update.message.reply_text(confirmation, parse_mode="Markdown")
        
        # Notify admin group if configured
        if ADMIN_GROUP_ID:
            admin_notification = (
                f"🔔 **New Order Received**\n\n"
                f"Order ID: #{order_id}\n"
                f"User: {order_data['username']}\n"
                f"{format_order_summary(order_data)}"
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_GROUP_ID,
                    text=admin_notification,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin group: {e}")
                
    except Exception as e:
        logger.error(f"Error in handle_text_message: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An unexpected error occurred while processing your order. "
            "Please try again or contact support."
        )


# ==================== CALLBACK HANDLERS ====================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle inline keyboard button callbacks.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        logger.info(f"Callback query from user {query.from_user.id}: {data}")
        
        # Main menu
        if data == "main_menu":
            await query.edit_message_text(
                "🏠 **Main Menu**\n\nChoose an option:",
                reply_markup=create_main_menu(),
                parse_mode="Markdown"
            )
        
        # Submit order
        elif data == "submit_order":
            await query.edit_message_text(
                "📝 **Submit New Order**\n\n"
                "Choose your order type or send order details directly:",
                reply_markup=create_order_type_menu(),
                parse_mode="Markdown"
            )
        
        # Check status
        elif data == "check_status":
            await status_command(update, context)
        
        # Help
        elif data == "help":
            await help_command(update, context)
        
        # Order type selection
        elif data.startswith("type_"):
            order_type = data.replace("type_", "")
            await query.edit_message_text(
                f"📦 You selected: **{order_type.replace('_', ' ').title()}**\n\n"
                f"Please send your order details including:\n"
                f"• Email address\n"
                f"• CP amount\n"
                f"• Any additional information\n\n"
                f"The order type '{order_type}' will be used.",
                parse_mode="Markdown"
            )
            # Store selected type in user context
            context.user_data["selected_order_type"] = order_type
        
        else:
            logger.warning(f"Unknown callback data: {data}")
            await query.answer("❌ Unknown action", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in handle_callback_query: {e}", exc_info=True)
        try:
            await query.answer(
                "❌ An error occurred. Please try again.",
                show_alert=True
            )
        except:
            pass


# ==================== ADMIN HANDLERS ====================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /admin command - show admin panel (admin only).
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not is_admin(user_id, chat_id):
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")
            await update.message.reply_text("❌ Unauthorized. Admin access only.")
            return
        
        logger.info(f"Admin command called by user {user_id}")
        
        admin_text = (
            f"🔐 **Admin Panel**\n\n"
            f"📊 Total active orders: {len(active_orders)}\n\n"
            f"Commands:\n"
            f"/orders - View all orders\n"
            f"/clear - Clear completed orders\n"
        )
        
        await update.message.reply_text(admin_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in admin_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Admin panel error.")


async def list_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /orders command - list all orders (admin only).
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not is_admin(user_id, chat_id):
            logger.warning(f"Unauthorized orders access attempt by user {user_id}")
            await update.message.reply_text("❌ Unauthorized. Admin access only.")
            return
        
        logger.info(f"List orders command called by admin {user_id}")
        
        if not active_orders:
            await update.message.reply_text("📊 No active orders.")
            return
        
        orders_text = f"📊 **All Active Orders** ({len(active_orders)}):\n\n"
        for order_id, order in active_orders.items():
            orders_text += (
                f"🆔 Order #{order_id}\n"
                f"👤 User: {order.get('username', 'Unknown')}\n"
                f"{format_order_summary(order)}\n"
            )
        
        await update.message.reply_text(orders_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in list_orders_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Could not list orders.")


# ==================== ERROR HANDLER ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors that occur during bot operation.
    
    Args:
        update: Telegram update object
        context: Bot context with error information
    """
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)
    
    # Notify user if possible
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An unexpected error occurred. Our team has been notified. "
                "Please try again later or contact support."
            )
        except Exception as e:
            logger.error(f"Could not send error message to user: {e}")


# ==================== MAIN FUNCTION ====================

def main() -> None:
    """
    Main function to start the bot.
    """
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        raise ValueError("BOT_TOKEN must be set in environment variables")
    
    logger.info("Starting Telegram Bot Manager...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("order", order_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("orders", list_orders_command))
    
    # Register message handlers
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    
    # Register callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    logger.info("Bot handlers registered successfully")
    logger.info("Bot is now running. Press Ctrl+C to stop.")
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
