import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from prometheus_client.core import REGISTRY, GaugeMetricFamily, CounterMetricFamily
from prometheus_client.registry import Collector
from prometheus_client.twisted import MetricsResource
from pymongo import MongoClient
from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import Site

load_dotenv()

# Set up logging
loglevel = os.getenv("LOGGING_LEVEL", "info").upper()
logformat = os.getenv("LOGGING_FORMAT", "%(asctime)s - %(levelname)s - %(message)s")
logging.basicConfig(format=logformat, level=loglevel)
logger = logging.getLogger(__name__)
logger.debug("Set log level to %s", logging.getLevelName(logger.getEffectiveLevel()))


class LibreChatMetricsCollector(Collector):
    """
    A custom Prometheus collector that gathers metrics from the LibreChat MongoDB database.
    """

    def __init__(self, mongodb_uri):
        """
        Initialize the MongoDB client and set up initial state.
        """
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[os.getenv("MONGODB_DATABASE", "LibreChat")]
        self.messages_collection = self.db["messages"]

    def collect(self):
        """
        Collect metrics and yield Prometheus metrics.
        """
        yield from self.collect_message_count()
        yield from self.collect_error_message_count()
        yield from self.collect_input_token_count()
        yield from self.collect_output_token_count()
        yield from self.collect_conversation_count()
        yield from self.collect_message_count_per_model()
        yield from self.collect_error_count_per_model()
        yield from self.collect_input_token_count_per_model()
        yield from self.collect_output_token_count_per_model()
        yield from self.collect_active_user_count()
        yield from self.collect_active_conversation_count()
        yield from self.collect_uploaded_file_count()
        yield from self.collect_registerd_user_count()
        # Adding new time-based metrics
        yield from self.collect_daily_unique_users()
        yield from self.collect_weekly_unique_users()
        yield from self.collect_monthly_unique_users()
        yield from self.collect_messages_5m()
        yield from self.collect_messages_per_model_5m()
        yield from self.collect_token_counts_5m()

    def collect_message_count(self):
        """
        Collect number of sent messages stored in the database.
        """
        try:
            total_messages = self.messages_collection.estimated_document_count()
            logger.debug("Messages count: %s", total_messages)
            yield CounterMetricFamily(
                "librechat_messages_total",
                "Number of sent messages stored in the database",
                value=total_messages,
            )
        except Exception as e:
            logger.exception("Error collecting message count: %s", e)

    def collect_error_message_count(self):
        """
        Collect number of error messages in the database.
        """
        try:
            total_errors = self.messages_collection.count_documents({"error": True})
            logger.debug("Error message count: %s", total_errors)
            yield CounterMetricFamily(
                "librechat_error_messages_total",
                "Number of error messages stored in the database",
                value=total_errors,
            )
        except Exception as e:
            logger.exception("Error collecting error message count: %s", e)

    def collect_input_token_count(self):
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
            logger.debug("Total input tokens: %s", total_input_tokens)
            yield CounterMetricFamily(
                "librechat_input_tokens_total",
                "Number of input tokens processed",
                value=total_input_tokens,
            )
        except Exception as e:
            logger.exception("Error collecting total input tokens: %s", e)

    def collect_output_token_count(self):
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
            logger.debug("Total output tokens: %s", total_output_tokens)
            yield CounterMetricFamily(
                "librechat_output_tokens_total",
                "Total number of output tokens generated",
                value=total_output_tokens,
            )
        except Exception as e:
            logger.exception("Error collecting total output tokens: %s", e)

    def collect_conversation_count(self):
        """
        Collect number of started conversations stored in the database.
        """
        try:
            total_conversations = self.db["conversations"].estimated_document_count()
            logger.debug("Total conversations: %s", total_conversations)
            yield CounterMetricFamily(
                "librechat_conversations_total",
                "Number of started conversations stored in the database",
                value=total_conversations,
            )
        except Exception as e:
            logger.exception("Error collecting conversation count: %s", e)

    def collect_message_count_per_model(self):
        """
        Collect number of messages per model.
        """
        try:
            pipeline = [
                {"$match": {"sender": {"$ne": "User"}}},
                {"$group": {"_id": "$model", "messageCount": {"$sum": 1}}},
            ]
            results = self.messages_collection.aggregate(pipeline)
            metric = CounterMetricFamily(
                "librechat_messages_per_model_total",
                "Number of messages per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] or "unknown"
                count = result["messageCount"]
                metric.add_metric([model], count)
                logger.debug("Number of message count for model %s: %s", model, count)
            yield metric
        except Exception as e:
            logger.exception("Error collecting messages count per model: %s", e)

    def collect_error_count_per_model(self):
        """
        Collect number of error messages per model.
        """
        try:
            pipeline = [
                {"$match": {"error": True}},
                {"$group": {"_id": "$model", "errorCount": {"$sum": 1}}},
            ]
            results = self.messages_collection.aggregate(pipeline)
            metric = CounterMetricFamily(
                "librechat_errors_per_model_total",
                "Number of error messages per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] or "unknown"
                error_count = result["errorCount"]
                metric.add_metric([model], error_count)
                logger.debug(
                    "Number of error messages for model %s: %s", model, error_count
                )
            yield metric
        except Exception as e:
            logger.exception("Error collecting error messages per model: %s", e)

    def collect_input_token_count_per_model(self):
        """
        Collect number of input tokens per model.
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
            results = self.messages_collection.aggregate(pipeline)
            metric = CounterMetricFamily(
                "librechat_input_tokens_per_model_total",
                "Number of input tokens per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] or "unknown"
                tokens = result["totalInputTokens"]
                metric.add_metric([model], tokens)
                logger.debug("Input tokens for model %s: %s", model, tokens)
            yield metric
        except Exception as e:
            logger.exception("Error collecting number of input tokens per model", e)

    def collect_output_token_count_per_model(self):
        """
        Collect number of output tokens per model.
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
            results = self.messages_collection.aggregate(pipeline)
            metric = CounterMetricFamily(
                "librechat_output_tokens_per_model_total",
                "Number of output tokens per model",
                labels=["model"],
            )
            for result in results:
                model = result["_id"] or "unknown"
                tokens = result["totalOutputTokens"]
                metric.add_metric([model], tokens)
                logger.debug("Output tokens for model %s: %s", model, tokens)
            yield metric
        except Exception as e:
            logger.exception("Error collecting number of output tokens per model", e)

    def collect_active_user_count(self):
        """
        Collect number of users active within last 5 minutes.
        """
        try:
            five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            active_users = len(
                self.messages_collection.distinct(
                    "user", {"createdAt": {"$gte": five_minutes_ago}}
                )
            )
            logger.debug("Number of active users: %s", active_users)
            yield GaugeMetricFamily(
                "librechat_active_users",
                "Number of active users",
                value=active_users,
            )
        except Exception as e:
            logger.exception("Error collecting number of active users: %s", e)

    def collect_active_conversation_count(self):
        """
        Collect number of conversations active within last 5 minutes.
        """
        try:
            five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            active_conversations = len(
                self.messages_collection.distinct(
                    "conversationId", {"createdAt": {"$gte": five_minutes_ago}}
                )
            )
            logger.debug("Number of active conversations: %s", active_conversations)
            yield GaugeMetricFamily(
                "librechat_active_conversations",
                "Number of active conversations",
                value=active_conversations,
            )
        except Exception as e:
            logger.exception("Error collecting number of active conversations: %s", e)

    def collect_uploaded_file_count(self):
        """
        Collect number of uploaded files.
        """
        try:
            file_count = self.db["files"].estimated_document_count()
            yield CounterMetricFamily(
                "librechat_uploaded_files_total",
                "Number of uploaded files",
                value=file_count,
            )
        except Exception as e:
            logger.exception("Error collecting uploaded files: %s", e)

    def collect_registerd_user_count(self):
        """
        Collect number of registered users.
        """
        try:
            user_count = self.db["users"].estimated_document_count()
            logger.debug("Number of registered users: %s", user_count)
            yield CounterMetricFamily(
                "librechat_registered_users_total",
                "Number of registered users",
                value=user_count,
            )
        except Exception as e:
            logger.exception("Error collecting number of registered users: %s", e)

    def collect_daily_unique_users(self):
        """
        Collect number of unique users active in the current day.
        """
        try:
            start_of_day = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            unique_users = len(
                self.messages_collection.distinct(
                    "user", {"createdAt": {"$gte": start_of_day}}
                )
            )
            logger.debug("Daily unique users: %s", unique_users)
            yield GaugeMetricFamily(
                "librechat_daily_unique_users",
                "Number of unique users active in the current day",
                value=unique_users,
            )
        except Exception as e:
            logger.exception("Error collecting daily unique users: %s", e)

    def collect_weekly_unique_users(self):
        """
        Collect number of unique users active in the current week (starting from Monday).
        """
        try:
            now = datetime.now(timezone.utc)
            # Calculate days since Monday (0=Monday, 1=Tuesday, etc.)
            days_since_monday = now.weekday()
            # Get the start of current week (Monday 00:00:00)
            start_of_week = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            unique_users = len(
                self.messages_collection.distinct(
                    "user", {"createdAt": {"$gte": start_of_week}}
                )
            )
            logger.debug("Weekly unique users: %s", unique_users)
            yield GaugeMetricFamily(
                "librechat_weekly_unique_users",
                "Number of unique users active in the current week (starting from Monday)",
                value=unique_users,
            )
        except Exception as e:
            logger.exception("Error collecting weekly unique users: %s", e)

    def collect_monthly_unique_users(self):
        """
        Collect number of unique users active in the current month.
        """
        try:
            now = datetime.now(timezone.utc)
            # Get the start of current month (1st day 00:00:00)
            start_of_month = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            
            unique_users = len(
                self.messages_collection.distinct(
                    "user", {"createdAt": {"$gte": start_of_month}}
                )
            )
            logger.debug("Monthly unique users: %s", unique_users)
            yield GaugeMetricFamily(
                "librechat_monthly_unique_users",
                "Number of unique users active in the current month",
                value=unique_users,
            )
        except Exception as e:
            logger.exception("Error collecting monthly unique users: %s", e)

    def collect_messages_5m(self):
        """
        Collect message counts for the last 5 minutes.
        """
        try:
            now = datetime.now(timezone.utc)
            five_minutes_ago = now - timedelta(minutes=5)

            # 5-minute message count
            five_min_count = self.messages_collection.count_documents(
                {"createdAt": {"$gte": five_minutes_ago}}
            )
            yield GaugeMetricFamily(
                "librechat_messages_5m",
                "Number of messages sent in the last 5 minutes",
                value=five_min_count,
            )
            logger.debug("Messages in last 5 minutes: %s", five_min_count)

        except Exception as e:
            logger.exception("Error collecting messages per time period: %s", e)

    def collect_messages_per_model_5m(self):
        """
        Collect message counts per model for the last 5 minutes.
        """
        try:
            now = datetime.now(timezone.utc)
            five_minutes_ago = now - timedelta(minutes=5)

            # 5-minute messages per model
            pipeline_5m = [
                {
                    "$match": {
                        "sender": {"$ne": "User"},
                        "createdAt": {"$gte": five_minutes_ago},
                    }
                },
                {"$group": {"_id": "$model", "count": {"$sum": 1}}},
            ]
            results_5m = self.messages_collection.aggregate(pipeline_5m)
            metric_5m = GaugeMetricFamily(
                "librechat_messages_per_model_5m",
                "Number of messages per model in the last 5 minutes",
                labels=["model"],
            )
            for result in results_5m:
                model = result["_id"] or "unknown"
                count = result["count"]
                metric_5m.add_metric([model], count)
                logger.debug("Messages in last 5 minutes for model %s: %s", model, count)
            yield metric_5m

        except Exception as e:
            logger.exception("Error collecting messages per model per time period: %s", e)

    def collect_token_counts_5m(self):
        """
        Collect token counts for the last 5 minutes.
        """
        try:
            now = datetime.now(timezone.utc)
            five_minutes_ago = now - timedelta(minutes=5)

            # 5-minute input tokens
            pipeline_input_5m = [
                {
                    "$match": {
                        "sender": "User",
                        "tokenCount": {"$exists": True, "$ne": None},
                        "createdAt": {"$gte": five_minutes_ago},
                    }
                },
                {"$group": {"_id": None, "totalTokens": {"$sum": "$tokenCount"}}},
            ]
            results_input_5m = list(self.messages_collection.aggregate(pipeline_input_5m))
            input_tokens_5m = results_input_5m[0]["totalTokens"] if results_input_5m else 0
            yield GaugeMetricFamily(
                "librechat_input_tokens_5m",
                "Number of input tokens used in the last 5 minutes",
                value=input_tokens_5m,
            )
            logger.debug("Input tokens in last 5 minutes: %s", input_tokens_5m)

            # 5-minute output tokens
            pipeline_output_5m = [
                {
                    "$match": {
                        "sender": {"$ne": "User"},
                        "tokenCount": {"$exists": True, "$ne": None},
                        "createdAt": {"$gte": five_minutes_ago},
                    }
                },
                {"$group": {"_id": None, "totalTokens": {"$sum": "$tokenCount"}}},
            ]
            results_output_5m = list(self.messages_collection.aggregate(pipeline_output_5m))
            output_tokens_5m = results_output_5m[0]["totalTokens"] if results_output_5m else 0
            yield GaugeMetricFamily(
                "librechat_output_tokens_5m",
                "Number of output tokens generated in the last 5 minutes",
                value=output_tokens_5m,
            )
            logger.debug("Output tokens in last 5 minutes: %s", output_tokens_5m)

            # Per-model token counts (5m)
            pipeline_model_tokens_5m = [
                {
                    "$match": {
                        "tokenCount": {"$exists": True, "$ne": None},
                        "model": {"$exists": True, "$ne": None},
                        "createdAt": {"$gte": five_minutes_ago},
                    }
                },
                {
                    "$group": {
                        "_id": {"model": "$model", "sender": "$sender"},
                        "totalTokens": {"$sum": "$tokenCount"},
                    }
                },
            ]
            results_model_tokens_5m = self.messages_collection.aggregate(pipeline_model_tokens_5m)
            
            input_metric_5m = GaugeMetricFamily(
                "librechat_model_input_tokens_5m",
                "Input tokens per model in the last 5 minutes",
                labels=["model"],
            )
            
            output_metric_5m = GaugeMetricFamily(
                "librechat_model_output_tokens_5m",
                "Output tokens per model in the last 5 minutes",
                labels=["model"],
            )
            
            model_tokens_map = {}
            for result in results_model_tokens_5m:
                model = result["_id"]["model"] or "unknown"
                sender_type = result["_id"]["sender"]
                tokens = result["totalTokens"]
                
                if model not in model_tokens_map:
                    model_tokens_map[model] = {"input": 0, "output": 0}
                
                if sender_type == "User":
                    model_tokens_map[model]["input"] += tokens
                else:
                    model_tokens_map[model]["output"] += tokens
            
            for model, counts in model_tokens_map.items():
                input_metric_5m.add_metric([model], counts["input"])
                output_metric_5m.add_metric([model], counts["output"])
                logger.debug(
                    "Model %s tokens in last 5 minutes: input=%s, output=%s",
                    model, counts["input"], counts["output"]
                )
            
            yield input_metric_5m
            yield output_metric_5m

        except Exception as e:
            logger.exception("Error collecting token counts per time period: %s", e)


if __name__ == "__main__":
    # Get MongoDB URI and Prometheus port from environment variables
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/")

    port = 8000

    # Start the Prometheus exporter
    collector = LibreChatMetricsCollector(mongodb_uri)
    REGISTRY.register(collector)
    logger.info("Starting server on port %i", port)

    root = Resource()
    metrics = MetricsResource()
    root.putChild(b"", metrics)
    root.putChild(b"metrics", metrics)

    reactor.listenTCP(port, Site(root))
    reactor.run()
