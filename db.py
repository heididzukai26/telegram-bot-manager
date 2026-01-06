# Example updated content for db.py
import logging
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

# Setting up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, database_url):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("Database engine created.")

    def execute_query(self, query, params=None):
        session = self.Session()
        try:
            result = session.execute(query, params or {})
            session.commit()
            logger.info("Query executed successfully.")
            return result
        except exc.SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
            logger.info("Session closed.")

    def fetch_all(self, query, params=None):
        session = self.Session()
        try:
            logger.info("Fetching all results.")
            return session.execute(query, params or {}).fetchall()
        except exc.SQLAlchemyError as e:
            logger.error(f"Error fetching data: {e}")
            raise
        finally:
            session.close()

# Note: Replace 'sqlite:///example.db' with your actual database URL.
db_manager = DatabaseManager("sqlite:///example.db")