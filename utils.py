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

def extract_amount(text: str) -> int:
    """
    Extract CP amount from order text using stricter detection rules.
    
    This function applies stricter rules to detect CP values:
    - Looks for numeric values followed by CP-related keywords
    - Supports both English and Persian keywords
    - Handles various number formats (with commas, spaces, etc.)
    - Returns 0 if no valid CP amount is found
    
    Args:
        text: Order text containing CP amount
        
    Returns:
        CP amount as integer, or 0 if not found
        
    Examples:
        >>> extract_amount("Need 5000 CP unsafe")
        5000
        >>> extract_amount("1000 cp fund order")
        1000
        >>> extract_amount("Order without amount")
        0
    """
    if not text or not isinstance(text, str):
        return 0
    
    # Normalize text
    normalized = text.lower().strip()
    
    # Remove commas from numbers (e.g., "1,000" -> "1000")
    normalized = re.sub(r'(\d+),(\d+)', r'\1\2', normalized)
    
    # Pattern 1: Number followed by CP keyword (e.g., "5000 cp", "1000cp")
    # Supports: cp, سی پی, سی‌پی, c.p, c p
    cp_patterns = [
        r'(\d+)\s*(?:cp|سی\s*پی|سی‌پی|c\.?p)\b',
        # Pattern 2: Number followed by order type keywords
        r'(\d+)\s*(?:unsafe|آنسیف|انسیف|زمانبر)',
        r'(\d+)\s*(?:fund|فاند|صندوق)',
        r'(\d+)\s*(?:safe|سیف|fast|فست|سریع)',
        r'(\d+)\s*(?:slow|اسلو|آهسته)',
        # Pattern 3: "CP: 5000" or "CP = 5000" or "CP 5000"
        r'(?:cp|سی\s*پی)\s*[:=]?\s*(\d+)',
        # Pattern 4: "need 5000" or "نیاز به 5000"
        r'(?:need|نیاز)\s+(?:به\s+)?(\d+)',
    ]
    
    for pattern in cp_patterns:
        match = re.search(pattern, normalized)
        if match:
            amount = int(match.group(1))
            # Apply validation: CP amount should be reasonable (between 100 and 1,000,000)
            if 100 <= amount <= 1000000:
                return amount
    
    # Fallback: Look for any number in reasonable range if it's the only significant number
    all_numbers = re.findall(r'\b(\d{3,7})\b', normalized)
    valid_numbers = [int(n) for n in all_numbers if 100 <= int(n) <= 1000000]
    
    # If there's exactly one valid number, it's likely the CP amount
    if len(valid_numbers) == 1:
        return valid_numbers[0]
    
    return 0


def extract_cp_and_type(order_text: str) -> Tuple[int, Optional[str], str]:
    """
    Extract both CP amount and order type simultaneously from order text.
    
    This function provides comprehensive extraction of order details with
    proper error handling and validation. It uses stricter rules for CP
    detection and comprehensive keyword matching for order types.
    
    Args:
        order_text: Text containing the order information
        
    Returns:
        Tuple containing:
            - cp_amount (int): CP amount or 0 if not found
            - order_type (str or None): Order type ('unsafe', 'fund', 'safe_fast', 'safe_slow') or None
            - error_message (str): Error message if either CP or type is missing, empty string otherwise
            
    Examples:
        >>> extract_cp_and_type("Need 5000 CP unsafe order")
        (5000, 'unsafe', '')
        >>> extract_cp_and_type("Order without details")
        (0, None, '❌ مقدار CP در متن سفارش مشخص نشده است.\\n❌ نوع سفارش شناسایی نشد...')
    """
    if not order_text or not isinstance(order_text, str):
        return 0, None, "❌ متن سفارش نامعتبر است."
    
    # Extract CP amount using the stricter extract_amount function
    cp_amount = extract_amount(order_text)
    
    # Extract order type using the comprehensive extract_order_type function
    order_type = extract_order_type(order_text)
    
    # Build error message if needed
    error_parts = []
    if cp_amount == 0:
        error_parts.append("❌ مقدار CP در متن سفارش مشخص نشده است.")
    if not order_type:
        error_parts.append(
            "❌ نوع سفارش شناسایی نشد. لطفاً یکی از `unsafe`, `fund`, `safe_fast`, یا `safe_slow` را مشخص کنید."
        )
    
    error_message = "\n".join(error_parts)
    
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
    Detect order type from order text using comprehensive keyword matching.
    
    This function supports both English and Persian keywords for order type detection.
    The detection follows a priority order to handle ambiguous cases correctly.
    
    Supported order types:
        - unsafe: High-risk orders (keywords: unsafe, unsaf, آنسیف, انسیف, زمانبر, خطرناک)
        - fund: Fund orders / safe 95% (keywords: fund, فاند, صندوق, 95%, safe 95, safe95, safe_95)
        - safe_slow: Safe slow orders (keywords: slow, اسلو, آهسته, safe slow, سیف اسلو, safe_slow)
        - safe_fast: Safe fast orders (keywords: safe, سیف, fast, فست, سریع, safe fast, سیف فست, safe_fast)
    
    Args:
        text: Order text to analyze
        
    Returns:
        Order type string ('unsafe', 'fund', 'safe_slow', 'safe_fast') or None if not detected
        
    Examples:
        >>> extract_order_type("Need 5000 CP unsafe")
        'unsafe'
        >>> extract_order_type("5000 fund order")
        'fund'
        >>> extract_order_type("Order with no type")
        None
        
    Note:
        Detection follows priority: unsafe > fund > safe_slow > safe_fast
        This prevents misclassification when multiple keywords are present.
    """
    if not text or not isinstance(text, str):
        return None
    
    # Normalize text to lowercase for case-insensitive matching
    t = text.lower()

    # Priority 1: Unsafe orders (highest priority to avoid confusion)
    unsafe_keywords = ["unsafe", "unsaf", "آنسیف", "انسیف", "زمانبر", "خطرناک"]
    if any(k in t for k in unsafe_keywords):
        return "unsafe"

    # Priority 2: Fund / safe 95% orders
    fund_keywords = ["fund", "فاند", "صندوق", "95%", "safe 95", "safe95", "safe_95", "fund(safe 95"]
    if any(k in t for k in fund_keywords):
        return "fund"

    # Priority 3: Safe slow (explicit combinations take precedence)
    if ("safe slow" in t) or ("سیف اسلو" in t) or ("safe_slow" in t):
        return "safe_slow"
    # Check for both slow and safe keywords present
    if (("slow" in t or "اسلو" in t or "آهسته" in t) and ("safe" in t or "سیف" in t)):
        return "safe_slow"

    # Priority 4: Safe fast (explicit combinations)
    if ("safe fast" in t) or ("سیف فست" in t) or ("safe_fast" in t):
        return "safe_fast"
    # Check for both fast and safe keywords present
    if (("fast" in t or "فست" in t or "سریع" in t) and ("safe" in t or "سیف" in t)):
        return "safe_fast"
    
    # Check for standalone safe (defaults to safe_fast)
    if "safe" in t or "سیف" in t:
        return "safe_fast"

    return None