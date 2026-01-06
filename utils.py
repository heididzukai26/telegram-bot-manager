"""
Utility functions for order processing and admin management. 

Includes:
- Admin role verification
- Currency formatting
- Order validation and type extraction
"""

import re
import os
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# ==================== CONFIG ====================

OWNER_ID = int(os.getenv("OWNER_ID", "5006165880"))

# Order type keywords mapping
ORDER_TYPES = {
    "unsafe": ["unsafe", "آنسیف", "زمانبر", "خطرناک"],
    "fund": ["fund", "فاند", "95%", "safe 95", "صندوق"],
    "safe_slow": ["slow", "اسلو", "سیف اسلو", "آهسته"],
    "safe_fast": ["safe", "سیف", "fast", "فست", "سریع"],
}

# Regex patterns
EMAIL_PATTERN = r"[a-zA-Z0-9_. +-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+"

# ==================== ADMIN MANAGEMENT ====================

def is_admin(user_id: int, chat_id: Optional[int] = None) -> bool:
    """
    Check if user is an admin. 

    Checks:
    1. Is the owner (OWNER_ID)
    2. Is in ADMIN_IDS environment variable
    3. Is in admin group (ADMIN_GROUP_ID)

    Args:
        user_id:  Telegram user ID
        chat_id: (Optional) Telegram chat ID

    Returns:
        True if user is admin, False otherwise
    """
    # Check if owner
    if user_id == OWNER_ID:
        return True

    # Check if in admin list
    try:
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [
            int(i.strip()) for i in admin_ids_str.split(",") 
            if i.strip()
        ]
        if user_id in admin_ids:
            return True
    except ValueError as e:
        logger.error(f"❌ Invalid ADMIN_IDS format: {e}")

    # Check if in admin group
    if chat_id:
        admin_group_id = os.getenv("ADMIN_GROUP_ID")
        if admin_group_id and str(chat_id) == str(admin_group_id):
            return True

    return False

# ==================== ORDER VALIDATION ====================

def extract_cp_and_type(order_text: str) -> tuple:
    """
    Extract CP amount and order type from the text.

    Args:
        order_text (str): Text containing the order.

    Returns:
        tuple: A tuple containing (cp_amount, order_type, error_message).
               cp_amount: int (or 0 if not found),
               order_type: str (or None if not found),
               error_message: str (empty if no error).
    """
    # Normalize and clean up the text
    order_text = order_text.lower().strip()

    # Step 1: Look for the CP amount using 'unsafe' or general numbers
    cp_match = re.search(r'(\d+)\s*(unsafe|safe_fast|safe_slow|fund)', order_text)
    cp_amount = int(cp_match.group(1)) if cp_match else 0

    # Step 2: Look for the order type explicitly
    type_match = re.search(r'\b(unsafe|safe_fast|safe_slow|fund)\b', order_text)
    order_type = type_match.group(1) if type_match else None

    # Error handling if no CP or order type detected
    error_message = ""
    if cp_amount == 0:
        error_message = "❌ مقدار CP در متن سفارش مشخص نشده است."
    if not order_type:
        error_message += (
            "\n❌ نوع سفارش شناسایی نشد. لطفاً یکی از `unsafe`, `fund`, `safe_fast`, یا `safe_slow` را مشخص کنید."
        )

    return cp_amount, order_type, error_message

def is_valid_order(text: str) -> bool:
    """
    Validate if text is a proper order. 

    Requirements:
    - At least 3 lines
    - Contains an email address
    - Contains a numeric amount

    Args: 
        text: Order text

    Returns:
        True if valid order format

    Examples:
        >>> is_valid_order("user@example.com\\n\\nNeed 50 items")
        True
        >>> is_valid_order("Short text")
        False
    """
    if not text or not isinstance(text, str):
        return False

    # Check minimum line count
    lines = text.strip().split('\n')
    if len(lines) < 3:
        logger.debug(f"❌ Order too short: {len(lines)} lines")
        return False

    # Check for email
    has_email = bool(re.search(EMAIL_PATTERN, text))
    if not has_email:
        logger.debug(f"❌ Order missing email address")
        return False

    # Check for valid CP amount or type
    cp, order_type, error = extract_cp_and_type(text)
    if cp == 0 or not order_type:
        logger.debug(f"❌ Order missing CP or type. Error: {error}")
        return False

    return True

# ==================== ORDER TYPE EXTRACTION ====================

def extract_order_type(text: str) -> Optional[str]:
    """
    Detect order type from order text.

    Supported types:
      - fund  (Fund / safe 95%)
      - unsafe
      - safe_fast
      - safe_slow

    Returns:
        One of the above strings, or None if type cannot be confidently detected.
    """
    t = (text or "").lower()

    # 1) Unsafe
    if any(k in t for k in ["unsafe", "unsaf", "آنسیف", "انسیف", "زمانبر"]):
        return "unsafe"

    # 2) Fund / safe 95%
    if any(k in t for k in ["fund", "فاند", "95%", "safe 95", "safe95", "safe_95", "fund(safe 95"]):
        return "fund"

    # 3) Safe slow (explicit)
    if ("safe slow" in t) or ("سیف اسلو" in t) or ("safe_slow" in t):
        return "safe_slow"
    if (("slow" in t or "اسلو" in t) and ("safe" in t or "سیف" in t)):
        return "safe_slow"

    # 4) Safe fast (explicit)
    if ("safe fast" in t) or ("سیف فست" in t) or ("safe_fast" in t):
        return "safe_fast"
    if (("fast" in t or "فست" in t) and ("safe" in t or "سیف" in t)):
        return "safe_fast"

    return None

"""