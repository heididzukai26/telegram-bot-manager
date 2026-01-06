"""
Telegram Bot Manager - Main Application

This module implements the Telegram bot with command handlers for managing worker and customer groups.

Key Features:
1. /addsource - Add worker source groups to database with type and optional amount
2. /addgroup - Register Telegram groups as customer groups
3. Admin permission checking for all sensitive commands
4. Robust error handling and user feedback
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from db import db_manager
from utils import is_admin

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Welcome to Telegram Bot Manager! 🤖\n\n"
        "Available commands:\n"
        "/addsource - Add a worker source group\n"
        "/addgroup - Register this group as a customer group\n"
    )

async def addsource_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /addsource command.
    
    Adds a worker source group to the 'worker_groups' table.
    
    Usage: /addsource <group_id> <type> [amount]
    Example: /addsource -1001234567890 safe_fast 100
    
    Types: safe_fast, fund, unsafe, safe_slow
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check admin permission
    if not is_admin(user_id, chat_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    # Parse arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Invalid format.\n\n"
            "Usage: /addsource <group_id> <type> [amount]\n"
            "Example: /addsource -1001234567890 safe_fast 100\n\n"
            "Valid types: safe_fast, fund, unsafe, safe_slow"
        )
        return
    
    try:
        group_id = int(context.args[0])
        group_type = context.args[1].lower()
        amount = None
        
        # Validate group type
        valid_types = ['safe_fast', 'fund', 'unsafe', 'safe_slow']
        if group_type not in valid_types:
            await update.message.reply_text(
                f"❌ Invalid group type: {group_type}\n"
                f"Valid types: {', '.join(valid_types)}"
            )
            return
        
        # Parse optional amount
        if len(context.args) >= 3:
            try:
                amount = int(context.args[2])
            except ValueError:
                await update.message.reply_text("❌ Amount must be a number.")
                return
        
        # Add to database
        db_manager.add_worker_group(
            group_id=group_id,
            group_type=group_type,
            amount=amount,
            added_by=user_id
        )
        
        # Success message
        response = f"✅ Worker source group added successfully!\n\n"
        response += f"Group ID: {group_id}\n"
        response += f"Type: {group_type}\n"
        if amount:
            response += f"Amount: {amount}\n"
        
        await update.message.reply_text(response)
        logger.info(f"User {user_id} added worker group {group_id} (type: {group_type})")
        
    except ValueError:
        await update.message.reply_text("❌ Group ID must be a valid number.")
    except Exception as e:
        logger.error(f"Error in /addsource command: {e}")
        await update.message.reply_text(f"❌ Error adding worker source group: {str(e)}")

async def addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /addgroup command.
    
    Registers the current Telegram group as a 'customer group' in the database.
    This command should be used in the group chat that needs to be registered.
    
    Usage: /addgroup
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat = update.effective_chat
    
    # Check admin permission
    if not is_admin(user_id, chat_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    # Check if this is a group chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "❌ This command can only be used in group chats.\n"
            "Please use it in the group you want to register."
        )
        return
    
    try:
        # Get group information
        group_id = chat_id
        group_name = chat.title or "Unknown Group"
        
        # Add to database
        customer_group = db_manager.add_customer_group(
            group_id=group_id,
            group_name=group_name,
            added_by=user_id
        )
        
        # Success message
        response = f"✅ Customer group registered successfully!\n\n"
        response += f"Group Name: {group_name}\n"
        response += f"Group ID: {group_id}\n"
        
        await update.message.reply_text(response)
        logger.info(f"User {user_id} registered customer group {group_id} ({group_name})")
        
    except Exception as e:
        logger.error(f"Error in /addgroup command: {e}")
        await update.message.reply_text(f"❌ Error registering customer group: {str(e)}")

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")

# ==================== MAIN APPLICATION ====================

def main():
    """Start the bot."""
    # Get bot token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("addsource", addsource_command))
    application.add_handler(CommandHandler("addgroup", addgroup_command))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting bot...")
    print("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()