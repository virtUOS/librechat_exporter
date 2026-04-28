"""
LibreChat Metrics Exporter
Syncs metrics data from MongoDB to MariaDB with retention management.
"""
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from contextlib import contextmanager
import argparse
import os

import pymongo
import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Application configuration"""
    
    def __init__(self):
        load_dotenv()
        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/")
        self.mongodb_database = os.getenv("MONGODB_DATABASE", "librechat")
        self.mysql_host = os.getenv("MYSQL_HOST", "mariadb")
        self.mysql_user = os.getenv("MYSQL_USER", "metrics")
        self.mysql_password = os.getenv("MYSQL_PASSWORD", "metrics")
        self.mysql_database = os.getenv("MYSQL_DATABASE", "metrics")
        self.mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
        self.default_lookback_days = 30

        # Retry settings for MySQL/MariaDB (can be overridden via env vars)
        self.mysql_max_retries = int(os.getenv("MYSQL_MAX_RETRIES", "5"))
        self.mysql_retry_delay = int(os.getenv("MYSQL_RETRY_DELAY", "5"))  # seconds


# ============================================================================
# Database Managers
# ============================================================================

class MongoDBManager:
    """Manages MongoDB connections and queries"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self.db = None
    
    def connect(self):
        """Establish MongoDB connection"""
        try:
            self.client = pymongo.MongoClient(
                self.config.mongodb_uri,
                readPreference=os.getenv('MONGO_READ_PREFERENCE', 'secondaryPreferred'),
            )
            self.client.admin.command('ping')
            self.db = self.client[self.config.mongodb_database]
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def get_all_data(self, start_date, end_date):
        """Get all messages and conversations for the entire date range"""
        start_time = datetime.combine(start_date, datetime.min.time())
        end_time = datetime.combine(end_date, datetime.max.time())
        
        logger.info(f"Fetching all data from {start_time} to {end_time}...")
        
        messages = list(self.db.messages.find({
            'createdAt': {'$gte': start_time, '$lte': end_time}
        }))
        
        conversations = list(self.db.conversations.find({
            'createdAt': {'$gte': start_time, '$lte': end_time}
        }))
        
        logger.info(f"Fetched {len(messages)} messages and {len(conversations)} conversations")
        
        return {
            'messages': messages,
            'conversations': conversations
        }
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()


class MariaDBManager:
    """Manages MariaDB/MySQL connections and operations"""
    
    DAILY_TABLES = [
        'daily_users',
        'daily_messages',
        'daily_messages_by_model',
        'daily_tokens_by_model',
        'daily_errors_by_model'
    ]
    
    WEEKLY_TABLES = ['weekly_users']
    MONTHLY_TABLES = ['monthly_users']
    
    def __init__(self, config):
        self.config = config
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None

        attempt = 0
        max_retries = self.config.mysql_max_retries
        retry_delay = self.config.mysql_retry_delay
        while attempt <= max_retries:
            try:
                conn = mysql.connector.connect(
                    host=self.config.mysql_host,
                    user=self.config.mysql_user,
                    password=self.config.mysql_password,
                    database=self.config.mysql_database,
                    port=self.config.mysql_port
                )
                logger.info("Connected to MariaDB/MySQL")
                break
            except MySQLError as e:
                attempt += 1
                if attempt > max_retries:
                    logger.error(
                        f"Failed to connect to MariaDB/MySQL after "
                        f"{max_retries} attempts: {e}"
                    )
                    raise
                logger.warning(
                    f"MariaDB/MySQL not ready yet (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)

        try:
            yield conn
        finally:
            if conn and conn.is_connected():
                conn.close()
                
    
    def get_existing_dates(self, start_date, end_date):
        """Get all dates that already have data in MariaDB"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT date FROM daily_users
                WHERE date BETWEEN %s AND %s
                ORDER BY date
            """, (start_date, end_date))
            return {row[0] for row in cursor.fetchall()}
    

    def clear_date_range(self, start_date, end_date):
        """Clear data for dates being re-processed"""
        logger.info(f"Clearing data for re-processing: {start_date} to {end_date}")
        deleted_counts = {}
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Daily tables
                for table in self.DAILY_TABLES:
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE date >= %s AND date <= %s
                    """, (start_date, end_date))
                    deleted_counts[table] = cursor.rowcount
                
                # Weekly tables
                for table in self.WEEKLY_TABLES:
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE week_start >= %s AND week_start <= %s
                    """, (start_date, end_date))
                    deleted_counts[table] = cursor.rowcount
                
                # Monthly tables
                for table in self.MONTHLY_TABLES:
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE month_start >= %s AND month_start <= %s
                    """, (start_date, end_date))
                    deleted_counts[table] = cursor.rowcount
                
                conn.commit()
                return deleted_counts
                
            except Exception:
                conn.rollback()
                raise
            
    def delete_outside_range(self, start_date, end_date):
        """Delete data outside the specified date range"""
        deleted_counts = {}
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Daily tables
                for table in self.DAILY_TABLES:
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE date < %s OR date > %s
                    """, (start_date, end_date))
                    deleted_counts[table] = cursor.rowcount
                
                # Weekly tables
                for table in self.WEEKLY_TABLES:
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE week_start < %s OR week_start > %s
                    """, (start_date, end_date))
                    deleted_counts[table] = cursor.rowcount
                
                # Monthly tables
                for table in self.MONTHLY_TABLES:
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE month_start < %s OR month_start > %s
                    """, (start_date, end_date))
                    deleted_counts[table] = cursor.rowcount
                
                conn.commit()
                return deleted_counts
                
            except Exception:
                conn.rollback()
                raise

    
    def store_daily_metrics(self, date, metrics):
        """Store daily metrics in database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Daily users
                cursor.execute("""
                    INSERT INTO daily_users (date, unique_users)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE unique_users = VALUES(unique_users)
                """, (date, metrics['unique_users']))
                
                # Daily messages
                cursor.execute("""
                    INSERT INTO daily_messages (date, total_messages, total_conversations)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        total_messages = VALUES(total_messages),
                        total_conversations = VALUES(total_conversations)
                """, (date, metrics['total_messages'], metrics['total_conversations']))
                
                # Messages by model
                for model, count in metrics['messages_by_model'].items():
                    cursor.execute("""
                        INSERT INTO daily_messages_by_model (date, model, message_count)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE message_count = VALUES(message_count)
                    """, (date, model, count))
                
                # Tokens by model
                for model, tokens in metrics['tokens_by_model'].items():
                    cursor.execute("""
                        INSERT INTO daily_tokens_by_model (date, model, input_tokens, output_tokens)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            input_tokens = VALUES(input_tokens),
                            output_tokens = VALUES(output_tokens)
                    """, (date, model, tokens['input'], tokens['output']))
                
                # Errors by model
                for model, count in metrics['errors_by_model'].items():
                    cursor.execute("""
                        INSERT INTO daily_errors_by_model (date, model, error_count)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE error_count = VALUES(error_count)
                    """, (date, model, count))
                
                conn.commit()
                
            except Exception:
                conn.rollback()
                raise
    
    def store_weekly_metrics(self, week_start, unique_users):
        """Store weekly metrics in database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO weekly_users (week_start, unique_users)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE unique_users = VALUES(unique_users)
                """, (week_start, unique_users))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def store_monthly_metrics(self, month_start, unique_users):
        """Store monthly metrics in database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO monthly_users (month_start, unique_users)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE unique_users = VALUES(unique_users)
                """, (month_start, unique_users))
                conn.commit()
            except Exception:
                conn.rollback()
                raise


# ============================================================================
# Data Filtering
# ============================================================================

class DataFilter:
    """Filters pre-loaded data by date"""
    
    @staticmethod
    def filter_by_date(items, target_date):
        """Filter items by a specific date"""
        return DataFilter.filter_by_date_range(items, target_date, target_date)
    
    @staticmethod
    def filter_by_date_range(items, start_date, end_date):
        """Filter items by date range"""
        start_time = datetime.combine(start_date, datetime.min.time())
        end_time = datetime.combine(end_date, datetime.max.time())
        return [
            item for item in items
            if item.get('createdAt') and start_time <= item['createdAt'] <= end_time
        ]


# ============================================================================
# Metrics Calculation
# ============================================================================

class MetricsCalculator:
    """Calculates metrics from raw data"""
    
    @staticmethod
    def calculate_daily_metrics(messages, conversations, allmessages):
        """Calculate daily metrics from messages and conversations"""
        unique_users = MetricsCalculator.calculate_unique_users(messages)
        total_messages = len(messages)
        total_conversations = len(conversations)
        
        messages_by_model = defaultdict(int)
        tokens_by_model = defaultdict(lambda: {'input': 0, 'output': 0})
        errors_by_model = defaultdict(int)

        # Build a parentMessageId → [ai_response, ...] index once,
        # so user-message token attribution is O(1) per lookup
        # instead of O(len(allmessages)) per user message.
        ai_responses_by_parent = defaultdict(list)
        for msg in allmessages:
            if (not msg.get('isCreatedByUser')
                    and msg.get('model')
                    and msg.get('parentMessageId')):
                ai_responses_by_parent[msg['parentMessageId']].append(msg)

        for message in messages:
            model_name = message.get('model') or 'unknown'

            # Token counts
            if 'tokenCount' in message:
                token_count = message.get('tokenCount', 0)

                if isinstance(token_count, dict):  # DEPRECATED?
                    tokens_by_model[model_name]['input'] += token_count.get('prompt', 0)
                    tokens_by_model[model_name]['output'] += token_count.get('completion', 0)

                elif message.get('isCreatedByUser'):
                    user_msg_id = message.get('messageId')
                    if user_msg_id:
                        # Attribute input tokens to each model that responded.
                        # Input tokens are counted once per AI reply, so N
                        # regenerations multiply input token cost N×.  This is
                        # intentional: every regeneration incurs a real API call
                        # and thus a real input-token charge.
                        for ai_msg in ai_responses_by_parent.get(user_msg_id, ()):
                            ai_model = ai_msg['model']
                            tokens_by_model[ai_model]['input'] += token_count

                elif message.get('model'):
                    tokens_by_model[model_name]['output'] += token_count
                    messages_by_model[model_name] += 1
            
            # Error counts
            if message.get('error'):
                errors_by_model[model_name] += 1

        return {
            'unique_users': unique_users,
            'total_messages': total_messages,
            'total_conversations': total_conversations,
            'messages_by_model': dict(messages_by_model),
            'tokens_by_model': dict(tokens_by_model),
            'errors_by_model': dict(errors_by_model)
        }
    
    @staticmethod
    def calculate_unique_users(messages):
        """Calculate unique users from messages"""
        return len({msg.get('user') for msg in messages if msg.get('isCreatedByUser')})


# ============================================================================
# Date Range Utilities
# ============================================================================

class DateUtils:
    """Utilities for working with dates"""
    
    @staticmethod
    def get_date_list(start_date, end_date):
        """Generate list of dates between start and end (inclusive)"""
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates
    
    @staticmethod
    def get_missing_dates(all_dates, existing_dates):
        """Get dates that are missing from existing dates"""
        return [date for date in all_dates if date not in existing_dates]
    
    @staticmethod
    def is_week_end(date):
        """Check if date is end of week (Sunday)"""
        return date.weekday() == 6
    
    @staticmethod
    def is_month_end(date):
        """Check if date is end of month"""
        next_day = date + timedelta(days=1)
        return date.month != next_day.month
    
    @staticmethod
    def get_week_start(date):
        """Get the Monday of the week containing this date"""
        return date - timedelta(days=date.weekday())
    
    @staticmethod
    def get_month_start(date):
        """Get the first day of the month containing this date"""
        return date.replace(day=1)


# ============================================================================
# Main Application
# ============================================================================

class MetricsExporter:
    """Main application for exporting metrics"""
    
    def __init__(self, config):
        self.config = config
        self.mongo = MongoDBManager(config)
        self.maria = MariaDBManager(config)
        self.calculator = MetricsCalculator()
        self.date_utils = DateUtils()
        self.filter = DataFilter()
        
        # Cache for all data
        self.all_data = None
    
    def process_daily_metrics(self, date, all_messages, all_conversations):
        """Process metrics for a single day using pre-loaded data"""
        logger.info(f"Processing daily metrics for {date}")
        
        # Filter data for this specific date
        messages = self.filter.filter_by_date(all_messages, date)
        conversations = self.filter.filter_by_date(all_conversations, date)
        
        logger.info(f"Found {len(messages)} messages, {len(conversations)} conversations")
        
        # Calculate metrics
        metrics = self.calculator.calculate_daily_metrics(messages, conversations, all_messages)
        
        logger.info(f"Metrics: {metrics['unique_users']} users, "
                   f"{metrics['total_messages']} messages, "
                   f"{metrics['total_conversations']} conversations")
        
        # Store in database
        self.maria.store_daily_metrics(date, metrics)
        logger.info(f"Stored daily metrics for {date}")
    
    def process_weekly_metrics(self, week_end, all_messages):
        """Process weekly metrics ending on given date"""
        if week_end > datetime.now().date():
            logger.debug(f"Skipping future date: {week_end}")
            return
        
        week_start = week_end - timedelta(days=6)
        logger.info(f"Processing weekly metrics for week {week_start} to {week_end}")
        
        # Filter messages for the week
        messages = self.filter.filter_by_date_range(all_messages, week_start, week_end)
        unique_users = self.calculator.calculate_unique_users(messages)
        
        self.maria.store_weekly_metrics(week_start, unique_users)
        logger.info(f"Stored weekly metrics: {unique_users} users")
    
    def process_monthly_metrics(self, month_end, all_messages):
        """Process monthly metrics for month ending on given date"""
        if month_end > datetime.now().date():
            logger.debug(f"Skipping future date: {month_end}")
            return
        
        month_start = self.date_utils.get_month_start(month_end)
        logger.info(f"Processing monthly metrics for {month_start.strftime('%B %Y')}")
        
        # Filter messages for the month
        messages = self.filter.filter_by_date_range(all_messages, month_start, month_end)
        unique_users = self.calculator.calculate_unique_users(messages)
        
        self.maria.store_monthly_metrics(month_start, unique_users)
        logger.info(f"Stored monthly metrics: {unique_users} users")
    
    def cleanup_data(self, start_date, end_date):
        """Clean up data outside retention window"""
        logger.info(f"Cleaning up data outside {start_date} to {end_date}")
        
        # Clean outside range
        deleted_counts = self.maria.delete_outside_range(start_date, end_date)
        total_deleted = sum(deleted_counts.values())
        
        if total_deleted > 0:
            logger.info(f"Cleaned up {total_deleted} records:")
            for table, count in deleted_counts.items():
                if count > 0:
                    logger.info(f"  - {table}: {count} records")
        else:
            logger.info("No data found outside retention window")
    
    def sync(self, start_date, end_date, force=False, cleanup=False):
        """Sync metrics for date range"""
        
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Retention window: {(end_date - start_date).days + 1} days")
        
        # Cleanup if requested
        if cleanup:
            self.cleanup_data(start_date, end_date)
        
        # Determine which dates to process
        all_dates = self.date_utils.get_date_list(start_date, end_date)
        
        if force:
            logger.info("Force mode: re-syncing all dates")
            self.maria.clear_date_range(start_date, end_date)
            dates_to_process = all_dates
        else:
            logger.info("Checking for missing dates...")
            existing_dates = self.maria.get_existing_dates(start_date, end_date)
            dates_to_process = self.date_utils.get_missing_dates(all_dates, existing_dates)
        
        if not dates_to_process:
            logger.info("No missing dates. All data is up to date!")
            return
        
        logger.info(f"Processing {len(dates_to_process)} dates:")
        for date in dates_to_process[:5]:
            logger.info(f"  - {date}")
        if len(dates_to_process) > 5:
            logger.info(f"  ... and {len(dates_to_process) - 5} more")
        
        # *** Fetch all data once ***
        logger.info(f"\n{'='*60}")
        logger.info("Fetching all data from MongoDB...")
        all_data = self.mongo.get_all_data(start_date, end_date)
        all_messages = all_data['messages']
        all_conversations = all_data['conversations']
        logger.info("Data loaded into memory. Processing dates...")
        logger.info(f"{'='*60}\n")
        
        # Process each date using the pre-loaded data
        for i, date in enumerate(dates_to_process, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Progress: {i}/{len(dates_to_process)}")
            
            try:
                self.process_daily_metrics(date, all_messages, all_conversations)
                
                # Weekly metrics on Sundays
                if self.date_utils.is_week_end(date):
                    self.process_weekly_metrics(date, all_messages)
                
                # Monthly metrics on last day of month
                if self.date_utils.is_month_end(date):
                    self.process_monthly_metrics(date, all_messages)
                    
            except Exception as e:
                logger.error(f"Error processing {date}: {e}")
                continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Successfully processed {len(dates_to_process)} dates")
    
    def run(self, start_date, end_date, force=False, cleanup=False):
        """Main entry point - connects to DB and runs sync"""
        try:
            self.mongo.connect()
            self.sync(start_date, end_date, force=force, cleanup=cleanup)
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
        finally:
            self.mongo.close()


# ============================================================================
# CLI Interface
# ============================================================================

def parse_date(date_str):
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='LibreChat Metrics Exporter - Sync metrics from MongoDB to MariaDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
                Examples:
                # Sync past 30 days (default)
                python export_metrics.py
                
                # Sync past 90 days with cleanup
                python export_metrics.py --days 90 --cleanup
                
                # Sync specific date range
                python export_metrics.py --start-date 2026-01-01 --end-date 2026-01-31
                
                # Force re-sync all dates
                python export_metrics.py --force --cleanup
                
                Cron Examples:
                # Daily sync at 2 AM, keep 30 days
                0 2 * * * cd /path && python3 export_metrics.py --days 30 --cleanup
                
                # Hourly incremental sync (last 2 days)
                0 * * * * cd /path && python3 export_metrics.py --days 2
                """
        )
    
    parser.add_argument('--start-date', type=str, metavar='YYYY-MM-DD',
                       help='Start date (default: N days ago)')
    parser.add_argument('--end-date', type=str, metavar='YYYY-MM-DD',
                       help='End date (default: yesterday)')
    parser.add_argument('--days', type=int, default=30, metavar='N',
                       help='Number of days to look back (default: 30)')
    parser.add_argument('--cleanup', action='store_true',
                       help='Delete all data outside the date range')
    parser.add_argument('--force', action='store_true',
                       help='Force re-sync even if data already exists')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load configuration
        config = Config()
        
        # Determine date range
        if args.start_date and args.end_date:
            start_date = parse_date(args.start_date)
            end_date = parse_date(args.end_date)
        elif args.start_date or args.end_date:
            raise ValueError("Both --start-date and --end-date must be provided together")
        else:
            # Default: past N days, excluding today (incomplete data)
            end_date = datetime.now().date() - timedelta(days=1)
            start_date = end_date - timedelta(days=args.days - 1)
        
        if start_date > end_date:
            raise ValueError("Start date must be before or equal to end date")
        
        # Run exporter
        exporter = MetricsExporter(config)
        exporter.run(start_date, end_date, force=args.force, cleanup=args.cleanup)
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()