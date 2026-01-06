# Telegram Bot Manager - Setup and Usage Guide

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export TELEGRAM_BOT_TOKEN="your-bot-token-here"
export OWNER_ID="your-telegram-user-id"
export ADMIN_IDS="comma,separated,admin,ids"  # Optional
```

3. Run the bot:
```bash
python main.py
```

## Available Commands

### /start
Welcome message and command list.

### /addsource - Add Worker Source Group
Adds a worker source group to the 'worker_groups' table.

**Usage:**
```
/addsource <group_id> <type> [amount]
```

**Examples:**
```
/addsource -1001234567890 safe_fast
/addsource -1001234567890 safe_fast 100
/addsource -1001234567890 fund 500
```

**Valid Types:**
- `safe_fast` - Fast and safe orders
- `fund` - Fund orders (95%)
- `unsafe` - Unsafe/time-consuming orders
- `safe_slow` - Slow but safe orders

**Requirements:**
- User must be an admin (OWNER_ID or in ADMIN_IDS)
- Group ID must be a valid Telegram group ID (negative number for groups)

### /addgroup - Register Customer Group
Registers the current Telegram group as a 'customer group' in the database.

**Usage:**
```
/addgroup
```

**Examples:**
Use this command in the group chat you want to register:
```
/addgroup
```

**Requirements:**
- User must be an admin (OWNER_ID or in ADMIN_IDS)
- Command must be used in a group chat (not private chat)

## Database Schema

### worker_groups Table
Stores worker source groups that can be assigned orders.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| group_id | BigInteger | Telegram group ID |
| group_type | String | Type of worker group |
| amount | Integer | Optional amount |
| added_at | DateTime | When the group was added |
| added_by | BigInteger | User ID who added it |

### customer_groups Table
Stores registered customer groups.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| group_id | BigInteger | Telegram group ID (unique) |
| group_name | String | Group name/title |
| added_at | DateTime | When the group was added |
| added_by | BigInteger | User ID who added it |

## Configuration

### Environment Variables

- `TELEGRAM_BOT_TOKEN` (required): Your Telegram bot token from @BotFather
- `OWNER_ID` (required): Telegram user ID of the bot owner (always has admin rights)
- `ADMIN_IDS` (optional): Comma-separated list of additional admin user IDs
- `DATABASE_URL` (optional): Database connection string (defaults to `sqlite:///telegram_bot.db`)

## Troubleshooting

### Bot doesn't respond
- Check that TELEGRAM_BOT_TOKEN is set correctly
- Verify the bot is running without errors
- Make sure the bot has permissions in the group

### Permission denied for commands
- Verify your user ID is set as OWNER_ID or in ADMIN_IDS
- Check the bot logs for permission check failures

### Database errors
- Ensure the bot has write permissions in the directory
- Check DATABASE_URL if using a custom database
