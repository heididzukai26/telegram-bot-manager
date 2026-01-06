# Example updated content for db.py
import logging
import os
from sqlalchemy import create_engine, exc, Column, Integer, String, BigInteger, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Setting up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

# ==================== TABLE DEFINITIONS ====================

class WorkerGroup(Base):
    """Worker source groups table for storing worker group information."""
    __tablename__ = 'worker_groups'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, nullable=False)  # Telegram group ID
    group_type = Column(String(50), nullable=False)  # e.g., 'safe_fast', 'fund', 'unsafe', 'safe_slow'
    amount = Column(Integer, nullable=True)  # Optional amount
    added_at = Column(DateTime, default=datetime.utcnow)
    added_by = Column(BigInteger, nullable=True)  # User ID who added this group

class CustomerGroup(Base):
    """Customer groups table for storing registered customer group information."""
    __tablename__ = 'customer_groups'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, unique=True, nullable=False)  # Telegram group ID
    group_name = Column(String(255), nullable=True)  # Group name/title
    added_at = Column(DateTime, default=datetime.utcnow)
    added_by = Column(BigInteger, nullable=True)  # User ID who added this group

# ==================== DATABASE MANAGER ====================

class DatabaseManager:
    def __init__(self, database_url=None):
        if database_url is None:
            database_url = os.getenv("DATABASE_URL", "sqlite:///telegram_bot.db")
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("Database engine created.")
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created/verified.")

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

    # ==================== WORKER GROUPS METHODS ====================

    def add_worker_group(self, group_id, group_type, amount=None, added_by=None):
        """
        Add a worker source group to the database.
        
        Args:
            group_id: Telegram group ID
            group_type: Type of worker group (e.g., 'safe_fast', 'fund', 'unsafe', 'safe_slow')
            amount: Optional amount associated with the group
            added_by: User ID who is adding this group
            
        Returns:
            dict: Dictionary with worker group information
        """
        session = self.Session()
        try:
            worker_group = WorkerGroup(
                group_id=group_id,
                group_type=group_type,
                amount=amount,
                added_by=added_by
            )
            session.add(worker_group)
            session.commit()
            
            # Get data before closing session
            result = {
                'id': worker_group.id,
                'group_id': worker_group.group_id,
                'group_type': worker_group.group_type,
                'amount': worker_group.amount,
                'added_by': worker_group.added_by,
                'added_at': worker_group.added_at
            }
            
            logger.info(f"Worker group added: group_id={group_id}, type={group_type}")
            return result
        except exc.SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error adding worker group: {e}")
            raise
        finally:
            session.close()

    def get_worker_groups(self, group_type=None):
        """
        Get worker groups, optionally filtered by type.
        
        Args:
            group_type: Optional filter by group type
            
        Returns:
            List of WorkerGroup objects
        """
        session = self.Session()
        try:
            query = session.query(WorkerGroup)
            if group_type:
                query = query.filter(WorkerGroup.group_type == group_type)
            return query.all()
        except exc.SQLAlchemyError as e:
            logger.error(f"Error fetching worker groups: {e}")
            raise
        finally:
            session.close()

    # ==================== CUSTOMER GROUPS METHODS ====================

    def add_customer_group(self, group_id, group_name=None, added_by=None):
        """
        Add a customer group to the database.
        
        Args:
            group_id: Telegram group ID
            group_name: Name/title of the group
            added_by: User ID who is adding this group
            
        Returns:
            dict: Dictionary with customer group information
        """
        session = self.Session()
        try:
            # Check if group already exists
            existing = session.query(CustomerGroup).filter(
                CustomerGroup.group_id == group_id
            ).first()
            
            if existing:
                logger.warning(f"Customer group already exists: group_id={group_id}")
                result = {
                    'id': existing.id,
                    'group_id': existing.group_id,
                    'group_name': existing.group_name,
                    'added_by': existing.added_by,
                    'added_at': existing.added_at
                }
                return result
            
            customer_group = CustomerGroup(
                group_id=group_id,
                group_name=group_name,
                added_by=added_by
            )
            session.add(customer_group)
            session.commit()
            
            # Get data before closing session
            result = {
                'id': customer_group.id,
                'group_id': customer_group.group_id,
                'group_name': customer_group.group_name,
                'added_by': customer_group.added_by,
                'added_at': customer_group.added_at
            }
            
            logger.info(f"Customer group added: group_id={group_id}, name={group_name}")
            return result
        except exc.SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error adding customer group: {e}")
            raise
        finally:
            session.close()

    def get_customer_groups(self):
        """
        Get all customer groups.
        
        Returns:
            List of CustomerGroup objects
        """
        session = self.Session()
        try:
            return session.query(CustomerGroup).all()
        except exc.SQLAlchemyError as e:
            logger.error(f"Error fetching customer groups: {e}")
            raise
        finally:
            session.close()

# Note: Replace 'sqlite:///telegram_bot.db' with your actual database URL via DATABASE_URL env var.
db_manager = DatabaseManager()