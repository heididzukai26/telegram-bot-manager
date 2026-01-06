# Improved orders.py Script

# imports
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_order(order_id, worker_reply_callback):
    """
    Process an order and handle its reply by a worker.

    Args:
        order_id (str): Unique identifier for the order.
        worker_reply_callback (function): Callback function used by worker to reply.
    """
    logging.info(f"Processing order: {order_id}")

    try:
        # Simulate order processing
        result = f"Order {order_id} processed successfully."
        logging.info(result)

        # Reply using the worker callback
        worker_reply_callback(order_id, result)
        logging.info(f"Reply for {order_id} sent successfully.")
    except Exception as e:
        error_message = f"Error while processing order {order_id}: {str(e)}"
        logging.error(error_message)
        worker_reply_callback(order_id, error_message)


def worker_reply(order_id, message):
    """
    Simulates a worker's reply to an order.

    Args:
        order_id (str): Unique identifier for the order.
        message (str): Message to be sent back to the user.
    """
    logging.info(f"Worker reply for {order_id}: {message}")


# Example of usage
if __name__ == "__main__":
    order_id_example = "12345"
    process_order(order_id_example, worker_reply)