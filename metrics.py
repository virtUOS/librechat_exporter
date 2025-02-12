import json
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily
from prometheus_client.registry import Collector
from prometheus_client.twisted import MetricsResource
from pymongo import MongoClient
from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import Site

load_dotenv()

# Set up logging
loglevel = os.getenv("LOGGING_LEVEL", "info").upper()
logging.basicConfig(level=loglevel)
logger = logging.getLogger(__name__)


class LibreChatMetricsCollector(Collector):
    """
    A custom Prometheus collector that gathers metrics from the LibreChat MongoDB database.
    """

    def __init__(self, mongodb):
        """
        Initialize the MongoDB client and set up initial state.
        """
        self.db = mongodb
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

    def collect_message_count(self):
        """
        Collect number of sent messages stored in the database.
        """
        try:
            total_messages = self.messages_collection.estimated_document_count()
            logger.debug("Messages count: %s", total_messages)
            yield GaugeMetricFamily(
                "librechat_messages",
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
            yield GaugeMetricFamily(
                "librechat_error_messages",
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
            yield GaugeMetricFamily(
                "librechat_input_tokens",
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
            yield GaugeMetricFamily(
                "librechat_output_tokens",
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
            yield GaugeMetricFamily(
                "librechat_conversations",
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
            metric = GaugeMetricFamily(
                "librechat_messages_per_model",
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
            metric = GaugeMetricFamily(
                "librechat_errors_per_model",
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
            metric = GaugeMetricFamily(
                "librechat_input_tokens_per_model",
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
            metric = GaugeMetricFamily(
                "librechat_output_tokens_per_model",
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

    def collect_registerd_user_count(self):
        """
        Collect number of registered users.
        """
        try:
            user_count = self.db["users"].estimated_document_count()
            logger.debug("Number of registered users: %s", user_count)
            yield GaugeMetricFamily(
                "librechat_registered_users",
                "Number of registered users",
                value=user_count,
            )
        except Exception as e:
            logger.exception("Error collecting number of registered users: %s", e)

    def collect_uploaded_file_count(self):
        """
        Collect number of uploaded files.
        """
        try:
            file_count = self.db["files"].estimated_document_count()
            yield GaugeMetricFamily(
                "librechat_uploaded_files",
                "Number of uploaded files",
                value=file_count,
            )
        except Exception as e:
            logger.exception("Error collecting uploaded files: %s", e)


class InfinityResource(Resource):
    isLeaf = True
    stat_types = ("daily", "weekly", "monthly", "yearly")

    def __init__(self, mongodb):
        """
        Initialize the MongoDB client and set up initial state.
        """
        self.messages = mongodb["messages"]

        # Load stored statistics
        try:
            statistics_file = os.getenv("STATISTICS_FILE", "statistics.json")
            with open(statistics_file, "rb") as f:
                logger.info("Loading cached statistics from %s", statistics_file)
                self.statistics = json.load(f)
        except FileNotFoundError:
            logger.debug("No cached statistics exist")
            self.statistics = {t: [] for t in self.stat_types}

        # Initial update of statistics
        self.update_statistics()

        self.save_cache()

    def save_cache(self):
        statistics_file = os.getenv("STATISTICS_FILE", "statistics.json")
        logger.info("Saving statistics to %s", statistics_file)
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            json.dump(self.statistics, temp)
            temp_file = temp.name
        logger.debug("Moving %s to %s", temp_file, statistics_file)
        shutil.move(temp_file, statistics_file)

    def next_step(self, date, stat_type):
        if stat_type == "yearly":
            return datetime(year=date.year + 1, month=1, day=1)
        elif stat_type == "monthly":
            date = date.replace(day=15) + timedelta(days=30)
            return datetime(year=date.year, month=date.month, day=1)
        elif stat_type == "weekly":
            date = date + timedelta(days=7 - date.weekday())
            return datetime(year=date.year, month=date.month, day=date.day)
        elif stat_type == "daily":
            date = date + timedelta(days=1)
            return datetime(year=date.year, month=date.month, day=date.day)
        raise Exception(f"Unknown stat type: {stat_type}")

    def statistics_start(self, stat_type):
        stats = self.statistics.get(stat_type)
        if stats:
            latest = stats[-1].get("date")
            date = datetime.fromisoformat(latest)
            return self.next_step(date, stat_type)
        else:
            self.statistics[stat_type] = []
            # Get oldest message to use this as a start point for getting daily statistics
            start = datetime.today()
            for message in self.messages.find().sort("createdAt", 1).limit(1):
                start = message["createdAt"]
            if stat_type == "yearly":
                return datetime(year=start.year, month=1, day=1)
            elif stat_type == "monthly":
                return datetime(year=start.year, month=start.month, day=1)
            elif stat_type == "weekly":
                start = start - timedelta(days=start.weekday())
                return datetime(year=start.year, month=start.month, day=start.day)
            return datetime(year=start.year, month=start.month, day=start.day)

    def update_statistics(self):
        for stat_type in self.stat_types:
            today = datetime.today()
            start = self.statistics_start(stat_type)
            end = self.next_step(start, stat_type)
            stats = self.statistics[stat_type]
            while end < today:
                logger.info("Getting %s users from %s", stat_type, start)
                count = self.user_count(start, end)
                stats.append({"date": start.date().isoformat(), "user": count})
                start = end
                end = self.next_step(end, stat_type)
        logger.debug("Statistics %s", self.statistics)

    def user_count(self, start, end):
        return len(
            self.messages.distinct("user", {"createdAt": {"$gte": start, "$lt": end}})
        )

    def render_GET(self, request):
        # Update statistics if necessary
        self.update_statistics()

        # Get time frame parameters
        begin_ts = float(request.args.get(b"from", [0])[0]) / 1000.0
        begin = datetime.fromtimestamp(begin_ts)
        end_ts = float(request.args.get(b"to", [time.time() * 1000.0])[0]) / 1000.0
        end = datetime.fromtimestamp(end_ts)
        logger.info("from: %s -> %s", begin, end)

        # Set the response code and content type
        request.setHeader(b"Content-Type", b"application/json")
        request.setResponseCode(200)  # HTTP status code

        # Return the response as JSON
        return json.dumps(self.statistics).encode("utf-8")


if __name__ == "__main__":
    # Get MongoDB URI and initialize database connection
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/")
    mongodb = MongoClient(mongodb_uri)["LibreChat"]

    port = 8000

    # Start the Prometheus exporter
    collector = LibreChatMetricsCollector(mongodb)
    REGISTRY.register(collector)
    logger.info("Starting server on port %i", port)

    root = Resource()
    metrics = MetricsResource()
    root.putChild(b"", metrics)
    root.putChild(b"metrics", metrics)
    root.putChild(b"infinity", InfinityResource(mongodb))

    reactor.listenTCP(port, Site(root))
    reactor.run()
