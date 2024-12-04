from pymongo import MongoClient
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LibreChatMetricsCollector:
    """
    A custom Prometheus collector that gathers metrics from the LibreChat MongoDB database.
    """

    def __init__(self, mongodb_uri):
        """
        Initialize the MongoDB client and set up initial state.
        """
        self.client = MongoClient(mongodb_uri)
        self.db = self.client["LibreChat"]
        self.messages_collection = self.db["messages"]
        self.conversations_collection = self.db["conversations"]
        self.last_run_date = None  # To track daily unique users

    def collect(self):
        """
        Collect metrics and yield Prometheus metrics.
        """
        yield from self.collect_total_messages()
        yield from self.collect_total_errors()
        yield from self.collect_total_input_tokens()
        yield from self.collect_total_output_tokens()
        yield from self.collect_total_conversations()
        yield from self.collect_messages_per_model()
        yield from self.collect_errors_per_model()
        yield from self.collect_input_tokens_per_model()
        yield from self.collect_output_tokens_per_model()
        yield from self.collect_active_users()
        yield from self.collect_active_conversations()
        yield from self.collect_daily_unique_users()

    def collect_total_messages(self):
        """
        Collect total number of messages sent.
        """
        try:
            total_messages = self.messages_collection.count_documents({})
            metric = GaugeMetricFamily(
                "librechat_total_messages",
                "Total number of messages sent",
                value=total_messages,
            )
            yield metric
            logger.debug(f"Total messages: {total_messages}")
        except Exception as e:
            logger.error(f"Error collecting total messages: {e}", exc_info=True)

    def collect_total_errors(self):
        """
        Collect total number of error messages.
        """
        try:
            total_errors = self.messages_collection.count_documents({"error": True})
            metric = GaugeMetricFamily(
                "librechat_total_errors",
                "Total number of error messages",
                value=total_errors,
            )
            yield metric
            logger.debug(f"Total errors: {total_errors}")
        except Exception as e:
            logger.error(f"Error collecting total errors: {e}", exc_info=True)

    def collect_total_input_tokens(self):
        """
        Collect total number of input tokens processed.
        """
        try:
            pipeline = [
                {
                    "$match": {
                        "sender": "User",
                        "tokenCount": {"$exists": True, "$ne": None},
                    }
                },
                {"$group": {"_id": None, "totalInputTokens": {"$sum": "$tokenCount"}}},
            ]
            results = list(self.messages_collection.aggregate(pipeline))
            total_input_tokens = results[0]["totalInputTokens"] if results else 0
            metric = GaugeMetricFamily(
                "librechat_total_input_tokens",
                "Total number of input tokens processed",
                value=total_input_tokens,
            )
            yield metric
            logger.debug(f"Total input tokens: {total_input_tokens}")
        except Exception as e:
            logger.error(f"Error collecting total input tokens: {e}", exc_info=True)

    def collect_total_output_tokens(self):
        """
        Collect total number of output tokens generated.
        """
        try:
            pipeline = [
                {
                    "$match": {
                        "sender": {"$ne": "User"},
                        "tokenCount": {"$exists": True, "$ne": None},
                    }
                },
                {"$group": {"_id": None, "totalOutputTokens": {"$sum": "$tokenCount"}}},
            ]
            results = list(self.messages_collection.aggregate(pipeline))
            total_output_tokens = results[0]["totalOutputTokens"] if results else 0
            metric = GaugeMetricFamily(
                "librechat_total_output_tokens",
                "Total number of output tokens generated",
                value=total_output_tokens,
            )
            yield metric
            logger.debug(f"Total output tokens: {total_output_tokens}")
        except Exception as e:
            logger.error(f"Error collecting total output tokens: {e}", exc_info=True)

    def collect_total_conversations(self):
        """
        Collect total number of conversations started.
        """
        try:
            total_conversations = self.conversations_collection.count_documents({})
            metric = GaugeMetricFamily(
                "librechat_total_conversations",
                "Total number of conversations started",
                value=total_conversations,
            )
            yield metric
            logger.debug(f"Total conversations: {total_conversations}")
        except Exception as e:
            logger.error(f"Error collecting total conversations: {e}", exc_info=True)

    def collect_messages_per_model(self):
        """
        Collect total number of messages per model.
        """
        try:
            pipeline = [
                {"$match": {"sender": {"$ne": "User"}}},
                {"$group": {"_id": "$model", "messageCount": {"$sum": 1}}},
            ]
            results = list(self.messages_collection.aggregate(pipeline))
            metric = GaugeMetricFamily(
                "librechat_messages_per_model_total",
                "Total number of messages per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] if result["_id"] else "Unknown"
                count = result["messageCount"]
                metric.add_metric([model], count)
                logger.debug(f"Messages for model {model}: {count}")
            yield metric
        except Exception as e:
            logger.error(f"Error collecting messages per model: {e}", exc_info=True)

    def collect_errors_per_model(self):
        """
        Collect total number of errors per model.
        """
        try:
            pipeline = [
                {"$match": {"error": True}},
                {"$group": {"_id": "$model", "errorCount": {"$sum": 1}}},
            ]
            results = list(self.messages_collection.aggregate(pipeline))
            metric = GaugeMetricFamily(
                "librechat_errors_per_model_total",
                "Total number of errors per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] if result["_id"] else "Unknown"
                error_count = result["errorCount"]
                metric.add_metric([model], error_count)
                logger.debug(f"Errors for model {model}: {error_count}")
            yield metric
        except Exception as e:
            logger.error(f"Error collecting errors per model: {e}", exc_info=True)

    def collect_input_tokens_per_model(self):
        """
        Collect total input tokens per model.
        """
        try:
            pipeline = [
                {
                    "$match": {
                        "sender": "User",
                        "tokenCount": {"$exists": True, "$ne": None},
                        "model": {"$exists": True, "$ne": None},
                    }
                },
                {
                    "$group": {
                        "_id": "$model",
                        "totalInputTokens": {"$sum": "$tokenCount"},
                    }
                },
            ]
            results = list(self.messages_collection.aggregate(pipeline))
            metric = GaugeMetricFamily(
                "librechat_input_tokens_per_model_total",
                "Total input tokens per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] if result["_id"] else "Unknown"
                tokens = result["totalInputTokens"]
                metric.add_metric([model], tokens)
                logger.debug(f"Input tokens for model {model}: {tokens}")
            yield metric
        except Exception as e:
            logger.error(f"Error collecting input tokens per model: {e}", exc_info=True)

    def collect_output_tokens_per_model(self):
        """
        Collect total output tokens per model.
        """
        try:
            pipeline = [
                {
                    "$match": {
                        "sender": {"$ne": "User"},
                        "tokenCount": {"$exists": True, "$ne": None},
                        "model": {"$exists": True, "$ne": None},
                    }
                },
                {
                    "$group": {
                        "_id": "$model",
                        "totalOutputTokens": {"$sum": "$tokenCount"},
                    }
                },
            ]
            results = list(self.messages_collection.aggregate(pipeline))
            metric = GaugeMetricFamily(
                "librechat_output_tokens_per_model_total",
                "Total output tokens per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] if result["_id"] else "Unknown"
                tokens = result["totalOutputTokens"]
                metric.add_metric([model], tokens)
                logger.debug(f"Output tokens for model {model}: {tokens}")
            yield metric
        except Exception as e:
            logger.error(
                f"Error collecting output tokens per model: {e}", exc_info=True
            )

    def collect_active_users(self):
        """
        Collect current number of active users (active within last 5 minutes).
        """
        try:
            five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            active_users = self.messages_collection.distinct(
                "user", {"createdAt": {"$gte": five_minutes_ago}}
            )
            active_user_count = len(active_users)
            metric = GaugeMetricFamily(
                "librechat_active_users",
                "Current number of active users",
                value=active_user_count,
            )
            yield metric
            logger.debug(f"Active users: {active_user_count}")
        except Exception as e:
            logger.error(f"Error collecting active users: {e}", exc_info=True)

    def collect_active_conversations(self):
        """
        Collect current number of active conversations (active within last 5 minutes).
        """
        try:
            five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            active_conversations = self.messages_collection.distinct(
                "conversationId", {"createdAt": {"$gte": five_minutes_ago}}
            )
            active_conversation_count = len(active_conversations)
            metric = GaugeMetricFamily(
                "librechat_active_conversations",
                "Current number of active conversations",
                value=active_conversation_count,
            )
            yield metric
            logger.debug(f"Active conversations: {active_conversation_count}")
        except Exception as e:
            logger.error(f"Error collecting active conversations: {e}", exc_info=True)

    def collect_daily_unique_users(self):
        """
        Collect number of unique users active yesterday.
        This metric is collected once per day, but yielded on every scrape.
        """
        try:
            current_date = datetime.now(timezone.utc).date()
            if self.last_run_date != current_date:
                # Calculate the date range for yesterday
                yesterday = current_date - timedelta(days=1)
                start_time = datetime.combine(
                    yesterday, datetime.min.time(), tzinfo=timezone.utc
                )
                end_time = datetime.combine(
                    current_date, datetime.min.time(), tzinfo=timezone.utc
                )
                # Query for unique users active yesterday
                unique_users = self.messages_collection.distinct(
                    "user", {"createdAt": {"$gte": start_time, "$lt": end_time}}
                )
                unique_user_count = len(unique_users)
                self.last_unique_users_yesterday = unique_user_count
                # Update last_run_date
                self.last_run_date = current_date
                logger.debug(f"Updated unique users yesterday: {unique_user_count}")
            else:
                # Use the last calculated value
                unique_user_count = getattr(self, "last_unique_users_yesterday", 0)
                logger.debug(
                    f"Using cached unique users yesterday: {unique_user_count}"
                )
            # Yield the metric with the current value
            metric = GaugeMetricFamily(
                "librechat_unique_users_yesterday",
                "Number of unique users active yesterday",
                value=unique_user_count,
            )
            yield metric
        except Exception as e:
            logger.error(f"Error collecting daily unique users: {e}", exc_info=True)


def signal_handler(sig, frame):
    """
    Handle termination signals to allow for graceful shutdown.
    """
    logger.info("Shutting down gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    # Get MongoDB URI and Prometheus port from environment variables
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/")
    prometheus_port = int(os.getenv("PROMETHEUS_PORT", "8000"))

    # Handle shutdown signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the Prometheus exporter
    collector = LibreChatMetricsCollector(mongodb_uri)
    REGISTRY.register(collector)
    start_http_server(prometheus_port)
    logger.info(f"Metrics server is running on port {prometheus_port}.")

    # Keep the application running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down.")
        sys.exit(0)
