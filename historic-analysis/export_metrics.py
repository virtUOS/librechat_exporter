import mysql.connector
from datetime import datetime, timedelta
import pymongo
from collections import defaultdict
import argparse
import sys

# Database connections
try:
    mongo_client = pymongo.MongoClient(
        "mongodb://localhost:27017/",
        readPreference='secondary',  # Prefer reading from secondary node
    )
    # Test the connection
    mongo_client.admin.command('ping')
    print("Successfully connected to MongoDB in read-only mode")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    sys.exit(1)

mongo_db = mongo_client["LibreChat"]

mysql_config = {
    'host': 'localhost',
    'user': 'metrics',
    'password': 'metrics',
    'database': 'metrics',
    'port': 3306
}

def get_mysql_connection():
    return mysql.connector.connect(**mysql_config)

def calculate_daily_metrics(date):
    """Calculate metrics for a specific date"""
    print(f"\nProcessing daily metrics for {date}")
    start_time = datetime.combine(date, datetime.min.time())
    end_time = datetime.combine(date, datetime.max.time())
    
    # Get messages for the day
    messages = list(mongo_db.messages.find({
        'createdAt': {'$gte': start_time, '$lte': end_time}
    }))
    
    # Get conversations for the day
    conversations = list(mongo_db.conversations.find({
        'createdAt': {'$gte': start_time, '$lte': end_time}
    }))
    
    print(f"Found {len(messages)} messages and {len(conversations)} conversations for {date}")
    
    # Calculate metrics
    unique_users = len(set(msg.get('user') for msg in messages))
    total_messages = len(messages)
    total_conversations = len(conversations)
    
    print(f"Metrics for {date}:")
    print(f"- Unique users: {unique_users}")
    print(f"- Total messages: {total_messages}")
    print(f"- Total conversations: {total_conversations}")
    
    # Calculate model-specific metrics
    messages_by_model = defaultdict(int)
    tokens_by_model = defaultdict(lambda: {'input': 0, 'output': 0})
    errors_by_model = defaultdict(int)
    
    for msg in messages:
        # Always use 'unknown' if model is None or not present
        model = msg.get('model') or 'unknown'
        messages_by_model[model] += 1
        
        # Token counts - handle both dictionary and integer values
        if 'tokenCount' in msg:
            token_count = msg['tokenCount']
            if isinstance(token_count, dict):
                tokens_by_model[model]['input'] += token_count.get('prompt', 0)
                tokens_by_model[model]['output'] += token_count.get('completion', 0)
            elif isinstance(token_count, int):
                # If it's a single number, assume it's the total token count
                tokens_by_model[model]['input'] += token_count // 2  # Split evenly between input and output
                tokens_by_model[model]['output'] += token_count // 2
        
        # Error counts
        if msg.get('error'):
            errors_by_model[model] += 1
    
    # Store metrics in MySQL
    conn = get_mysql_connection()
    cursor = conn.cursor()
    
    try:
        print(f"Storing daily metrics in MySQL for {date}")
        # Store daily users
        cursor.execute("""
            INSERT INTO daily_users (date, unique_users)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
            unique_users = VALUES(unique_users)
        """, (date, unique_users))
        
        # Store daily messages
        cursor.execute("""
            INSERT INTO daily_messages (date, total_messages, total_conversations)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
            total_messages = VALUES(total_messages),
            total_conversations = VALUES(total_conversations)
        """, (date, total_messages, total_conversations))
        
        # Store messages by model
        for model, count in messages_by_model.items():
            cursor.execute("""
                INSERT INTO daily_messages_by_model (date, model, message_count)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                message_count = VALUES(message_count)
            """, (date, model, count))
        
        # Store tokens by model
        for model, tokens in tokens_by_model.items():
            cursor.execute("""
                INSERT INTO daily_tokens_by_model (date, model, input_tokens, output_tokens)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                input_tokens = VALUES(input_tokens),
                output_tokens = VALUES(output_tokens)
            """, (date, model, tokens['input'], tokens['output']))
        
        # Store errors by model
        for model, count in errors_by_model.items():
            cursor.execute("""
                INSERT INTO daily_errors_by_model (date, model, error_count)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                error_count = VALUES(error_count)
            """, (date, model, count))
        
        conn.commit()
        print(f"Successfully stored daily metrics for {date}")
    except Exception as e:
        print(f"Error storing metrics for {date}: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def calculate_weekly_metrics(week_start):
    """Calculate weekly aggregated metrics"""
    # Skip if date is in the future
    if week_start > datetime.now().date():
        print(f"Skipping weekly metrics for future date: {week_start}")
        return
        
    week_end = week_start + timedelta(days=6)
    
    # Convert dates to datetime objects for MongoDB
    start_time = datetime.combine(week_start, datetime.min.time())
    end_time = datetime.combine(week_end, datetime.max.time())
    
    # Get all messages for the week
    messages = list(mongo_db.messages.find({
        'createdAt': {'$gte': start_time, '$lte': end_time}
    }))
    
    # Calculate unique users for the week
    unique_users = len(set(msg.get('user') for msg in messages))
    
    # Store in MySQL
    conn = get_mysql_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO weekly_users (week_start, unique_users)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
            unique_users = VALUES(unique_users)
        """, (week_start, unique_users))
        
        conn.commit()
    except Exception as e:
        print(f"Error storing weekly metrics for {week_start}: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def calculate_monthly_metrics(month_start):
    """Calculate monthly aggregated metrics"""
    # Skip if date is in the future
    if month_start > datetime.now().date():
        print(f"Skipping monthly metrics for future date: {month_start}")
        return
        
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = next_month - timedelta(days=1)
    
    # Convert dates to datetime objects for MongoDB
    start_time = datetime.combine(month_start, datetime.min.time())
    end_time = datetime.combine(month_end, datetime.max.time())
    
    # Get all messages for the month
    messages = list(mongo_db.messages.find({
        'createdAt': {'$gte': start_time, '$lte': end_time}
    }))
    
    # Calculate unique users for the month
    unique_users = len(set(msg.get('user') for msg in messages))
    
    # Store in MySQL
    conn = get_mysql_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO monthly_users (month_start, unique_users)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
            unique_users = VALUES(unique_users)
        """, (month_start, unique_users))
        
        conn.commit()
    except Exception as e:
        print(f"Error storing monthly metrics for {month_start}: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def parse_date(date_str):
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format")

def clear_metrics_tables():
    """Clear all metrics tables before inserting new data"""
    conn = get_mysql_connection()
    cursor = conn.cursor()
    
    try:
        # Clear all metrics tables
        tables = [
            'daily_users',
            'daily_messages',
            'daily_messages_by_model',
            'daily_tokens_by_model',
            'daily_errors_by_model',
            'weekly_users',
            'monthly_users'
        ]
        
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table}")
        
        conn.commit()
        print("Successfully cleared all metrics tables")
    except Exception as e:
        print(f"Error clearing metrics tables: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Calculate historical metrics for LibreChat')
    parser.add_argument('start_date', type=str, help='Start date in YYYY-MM-DD format')
    parser.add_argument('end_date', type=str, help='End date in YYYY-MM-DD format')
    
    args = parser.parse_args()
    
    try:
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)
        
        if start_date > end_date:
            raise ValueError("Start date must be before end date")
        
        # Clear all metrics tables before starting
        clear_metrics_tables()
        
        current_date = start_date
        while current_date <= end_date:
            print(f"Calculating metrics for {current_date}")
            calculate_daily_metrics(current_date)
            
            # Calculate weekly metrics on Sundays
            if current_date.weekday() == 6:
                week_start = current_date - timedelta(days=6)
                calculate_weekly_metrics(week_start)
            
            # Calculate monthly metrics on the last day of each month
            if current_date.month != (current_date + timedelta(days=1)).month:
                month_start = current_date.replace(day=1)
                calculate_monthly_metrics(month_start)
            
            current_date += timedelta(days=1)
            
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    main() 