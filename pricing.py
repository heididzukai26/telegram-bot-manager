"""
File: pricing.py
Description: Updated to optimize parsing, add confirmation workflows for price lists, and improve user-friendly messages.
"""

def parse_price_list(data):
    """
    Optimized function to parse a price list from raw data.
    
    Args:
        data (str): Raw textual price data.
    
    Returns:
        list of dict: Processed price list represented as dictionaries.
    """
    lines = data.splitlines()
    prices = []

    for line in lines:
        if not line.strip():  # skip empty lines
            continue
        try:
            item, price = map(str.strip, line.split(','))
            prices.append({"item": item, "price": float(price)})
        except ValueError as ve:
            print(f"Skipping invalid line: '{line}' -> {ve}")
    
    return prices

def confirm_price_list(prices):
    """
    Function to confirm with the user before finalizing the price list.
    
    Args:
        prices (list of dict): List of price items to confirm.
    
    Returns:
        bool: True if the user confirms, False otherwise.
    """
    print("Please confirm the following price list:")
    for item in prices:
        print(f"- {item['item']}: ${item['price']:.2f}")

    confirmation = input("Do you confirm this price list? (yes/no): ").strip().lower()
    return confirmation == 'yes'

def show_user_friendly_message(message):
    """
    Display a user-friendly informational message.

    Args:
        message (str): Message to display.
    
    Returns:
        None
    """
    border = "=" * len(message)
    print(f"\n{border}\n{message}\n{border}\n")

if __name__ == "__main__":
    raw_data = """
    Coffee, 3.5
    Tea, 2.75
    Sandwich, 5.25
    """

    price_list = parse_price_list(raw_data)
    if confirm_price_list(price_list):
        show_user_friendly_message("Price list confirmed and saved.")
    else:
        show_user_friendly_message("Price list not confirmed. Please review and try again.")