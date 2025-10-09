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
        self._rating_cache = None

    def collect(self):
        """
        Collect metrics and yield Prometheus metrics.
        """
        # Clear rating cache at start of each collection
        self._rating_cache = None

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
        yield from self.collect_registered_user_count()
        # Adding new time-based metrics
        yield from self.collect_daily_unique_users()
        yield from self.collect_weekly_unique_users()
        yield from self.collect_monthly_unique_users()
        yield from self.collect_messages_5m()
        yield from self.collect_messages_per_model_5m()
        yield from self.collect_token_counts_5m()
        yield from self.collect_error_message_count_5m()
        yield from self.collect_error_count_per_model_5m()
        # Adding new rating metrics - OPTIMIZED: Single query fetches all rating data
        yield from self.collect_rating_counts()
        yield from self.collect_rating_counts_per_model()
        yield from self.collect_rating_counts_per_tag()
        yield from self.collect_rating_ratio()
        yield from self.collect_rating_counts_5m()
        yield from self.collect_rated_message_count()
        yield from self.collect_model_tag_combinations()

    def collect_message_count(self):
        """
        Collect number of sent messages stored in the database.
        """
        try:
            total_messages = self.messages_collection.estimated_document_count()
            logger.debug("Messages count: %s", total_messages)
            yield GaugeMetricFamily(
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
            yield GaugeMetricFamily(
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
            yield GaugeMetricFamily(
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
            yield GaugeMetricFamily(
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
            metric = GaugeMetricFamily(
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
            metric = GaugeMetricFamily(
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
            metric = GaugeMetricFamily(
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
            yield GaugeMetricFamily(
                "librechat_uploaded_files_total",
                "Number of uploaded files",
                value=file_count,
            )
        except Exception as e:
            logger.exception("Error collecting uploaded files: %s", e)

    def collect_registered_user_count(self):
        """
        Collect number of registered users.
        """
        try:
            user_count = self.db["users"].estimated_document_count()
            logger.debug("Number of registered users: %s", user_count)
            yield GaugeMetricFamily(
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

    def collect_error_message_count_5m(self):
        """
        Collect number of error messages in the last 5 minutes.
        """
        try:
            now = datetime.now(timezone.utc)
            five_minutes_ago = now - timedelta(minutes=5)

            error_count_5m = self.messages_collection.count_documents(
                {"error": True, "createdAt": {"$gte": five_minutes_ago}}
            )
            yield GaugeMetricFamily(
                "librechat_error_messages_5m",
                "Number of error messages in the last 5 minutes",
                value=error_count_5m,
            )
            logger.debug("Error messages in last 5 minutes: %s", error_count_5m)
        except Exception as e:
            logger.exception("Error collecting error message count in last 5 minutes: %s", e)

    def collect_error_count_per_model_5m(self):
        """
        Collect number of error messages per model in the last 5 minutes.
        """
        try:
            now = datetime.now(timezone.utc)
            five_minutes_ago = now - timedelta(minutes=5)

            pipeline_5m = [
                {
                    "$match": {
                        "error": True,
                        "createdAt": {"$gte": five_minutes_ago},
                        "model": {"$exists": True, "$ne": None},
                    }
                },
                {"$group": {"_id": "$model", "errorCount": {"$sum": 1}}},
            ]
            results_5m = self.messages_collection.aggregate(pipeline_5m)
            metric_5m = GaugeMetricFamily(
                "librechat_errors_per_model_5m",
                "Number of error messages per model in the last 5 minutes",
                labels=["model"],
            )
            for result in results_5m:
                model = result["_id"] or "unknown"
                error_count = result["errorCount"]
                metric_5m.add_metric([model], error_count)
                logger.debug(
                    "Error messages in last 5 minutes for model %s: %s", model, error_count
                )
            yield metric_5m
        except Exception as e:
            logger.exception("Error collecting error messages per model in last 5 minutes: %s", e)

    def _fetch_all_rating_metrics(self):
        """
        OPTIMIZATION: Fetch all rating metrics in a single MongoDB aggregation query.
        This reduces database calls from ~10 to 1, significantly improving performance.
        """
        try:
            five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)

            # Single $facet aggregation to get all rating data at once
            pipeline = [
                {
                    "$facet": {
                        # Total counts
                        "total_ratings": [
                            {"$match": {"feedback.rating": {"$in": ["thumbsUp", "thumbsDown"]}}},
                            {
                                "$group": {
                                    "_id": "$feedback.rating",
                                    "count": {"$sum": 1}
                                }
                            }
                        ],
                        # Per-model ratings
                        "per_model": [
                            {
                                "$match": {
                                    "feedback.rating": {"$in": ["thumbsUp", "thumbsDown"]},
                                    "model": {"$exists": True, "$ne": None}
                                }
                            },
                            {
                                "$group": {
                                    "_id": {"model": "$model", "rating": "$feedback.rating"},
                                    "count": {"$sum": 1}
                                }
                            }
                        ],
                        # Per-tag ratings
                        "per_tag": [
                            {
                                "$match": {
                                    "feedback.tag": {"$exists": True, "$ne": None}
                                }
                            },
                            {
                                "$group": {
                                    "_id": "$feedback.tag",
                                    "count": {"$sum": 1}
                                }
                            }
                        ],
                        # Model-tag combinations
                        "model_tag_combos": [
                            {
                                "$match": {
                                    "feedback.tag": {"$exists": True, "$ne": None},
                                    "feedback.rating": {"$exists": True, "$ne": None},
                                    "model": {"$exists": True, "$ne": None}
                                }
                            },
                            {
                                "$group": {
                                    "_id": {
                                        "model": "$model",
                                        "tag": "$feedback.tag",
                                        "rating": "$feedback.rating"
                                    },
                                    "count": {"$sum": 1}
                                }
                            }
                        ],
                        # 5-minute ratings
                        "ratings_5m": [
                            {
                                "$match": {
                                    "feedback.rating": {"$in": ["thumbsUp", "thumbsDown"]},
                                    "updatedAt": {"$gte": five_minutes_ago}
                                }
                            },
                            {
                                "$group": {
                                    "_id": "$feedback.rating",
                                    "count": {"$sum": 1}
                                }
                            }
                        ],
                        # Total rated messages
                        "rated_count": [
                            {
                                "$match": {
                                    "feedback": {"$exists": True, "$ne": None}
                                }
                            },
                            {
                                "$group": {
                                    "_id": None,
                                    "count": {"$sum": 1}
                                }
                            }
                        ]
                    }
                }
            ]

            results = list(self.messages_collection.aggregate(pipeline))[0]

            # Process results into cache
            cache = {
                'total_thumbs_up': 0,
                'total_thumbs_down': 0,
                'per_model': {},
                'per_tag': {},
                'model_tag_combos': {},
                'thumbs_up_5m': 0,
                'thumbs_down_5m': 0,
                'rated_count': 0
            }

            # Total ratings
            for item in results['total_ratings']:
                if item['_id'] == 'thumbsUp':
                    cache['total_thumbs_up'] = item['count']
                elif item['_id'] == 'thumbsDown':
                    cache['total_thumbs_down'] = item['count']

            # Per-model ratings
            for item in results['per_model']:
                model = item['_id']['model'] or 'unknown'
                rating = item['_id']['rating']
                if model not in cache['per_model']:
                    cache['per_model'][model] = {'thumbsUp': 0, 'thumbsDown': 0, 'total': 0}
                cache['per_model'][model][rating] = item['count']
                cache['per_model'][model]['total'] += item['count']

            # Per-tag ratings
            for item in results['per_tag']:
                tag = item['_id'] or 'unknown'
                cache['per_tag'][tag] = item['count']

            # Model-tag combinations
            for item in results['model_tag_combos']:
                model = item['_id']['model'] or 'unknown'
                tag = item['_id']['tag'] or 'unknown'
                rating = item['_id']['rating']
                key = (model, tag, rating)
                cache['model_tag_combos'][key] = item['count']

            # 5-minute ratings
            for item in results['ratings_5m']:
                if item['_id'] == 'thumbsUp':
                    cache['thumbs_up_5m'] = item['count']
                elif item['_id'] == 'thumbsDown':
                    cache['thumbs_down_5m'] = item['count']

            # Rated count
            if results['rated_count']:
                cache['rated_count'] = results['rated_count'][0]['count']

            self._rating_cache = cache
            logger.debug("Rating metrics cached: %d models, %d tags, %d combos",
                         len(cache['per_model']), len(cache['per_tag']), len(cache['model_tag_combos']))

        except Exception as e:
            logger.exception("Error fetching rating metrics: %s", e)
            # Initialize empty cache on error
            self._rating_cache = {
                'total_thumbs_up': 0,
                'total_thumbs_down': 0,
                'per_model': {},
                'per_tag': {},
                'model_tag_combos': {},
                'thumbs_up_5m': 0,
                'thumbs_down_5m': 0,
                'rated_count': 0
            }

    def collect_rating_counts(self):
        """
        Collect total number of thumbs up and thumbs down ratings.
        OPTIMIZED: Uses cached data from _fetch_all_rating_metrics
        """
        try:
            if not hasattr(self, '_rating_cache') or self._rating_cache is None:
                self._fetch_all_rating_metrics()

            data = self._rating_cache
            thumbs_up_count = data['total_thumbs_up']
            thumbs_down_count = data['total_thumbs_down']

            logger.debug("Total thumbs up: %s", thumbs_up_count)
            logger.debug("Total thumbs down: %s", thumbs_down_count)

            yield GaugeMetricFamily(
                "librechat_thumbs_up_total",
                "Total number of thumbs up ratings",
                value=thumbs_up_count,
            )
            yield GaugeMetricFamily(
                "librechat_thumbs_down_total",
                "Total number of thumbs down ratings",
                value=thumbs_down_count,
            )
        except Exception as e:
            logger.exception("Error collecting rating counts: %s", e)

    def collect_rating_counts_per_model(self):
        """
        Collect rating counts per model.
        OPTIMIZED: Uses cached data from _fetch_all_rating_metrics
        """
        try:
            if self._rating_cache is None:
                self._fetch_all_rating_metrics()

            data = self._rating_cache['per_model']

            metric_up = GaugeMetricFamily(
                "librechat_thumbs_up_per_model",
                "Number of thumbs up ratings per model",
                labels=["model"],
            )
            metric_down = GaugeMetricFamily(
                "librechat_thumbs_down_per_model",
                "Number of thumbs down ratings per model",
                labels=["model"],
            )
            metric_ratio = GaugeMetricFamily(
                "librechat_rating_ratio_per_model",
                "Percentage of positive ratings per model (0-100)",
                labels=["model"],
            )

            for model, counts in data.items():
                thumbs_up = counts.get('thumbsUp', 0)
                thumbs_down = counts.get('thumbsDown', 0)
                total = counts.get('total', 0)

                metric_up.add_metric([model], thumbs_up)
                metric_down.add_metric([model], thumbs_down)

                ratio = (thumbs_up / total * 100) if total > 0 else 0
                metric_ratio.add_metric([model], ratio)

                logger.debug("Thumbs up for model %s: %s", model, thumbs_up)
                logger.debug("Thumbs down for model %s: %s", model, thumbs_down)
                logger.debug("Rating ratio for model %s: %.2f%% (%d/%d)", model, ratio, thumbs_up, total)

            yield metric_up
            yield metric_down
            yield metric_ratio

        except Exception as e:
            logger.exception("Error collecting rating counts per model: %s", e)

    def collect_rating_counts_per_tag(self):
        """
        Collect rating counts per feedback tag.
        OPTIMIZED: Uses cached data from _fetch_all_rating_metrics
        """
        try:
            if self._rating_cache is None:
                self._fetch_all_rating_metrics()

            data = self._rating_cache['per_tag']

            metric = GaugeMetricFamily(
                "librechat_rating_counts_per_tag",
                "Number of ratings per feedback tag",
                labels=["tag"],
            )

            for tag, count in data.items():
                metric.add_metric([tag], count)
                logger.debug("Rating count for tag %s: %s", tag, count)

            yield metric
        except Exception as e:
            logger.exception("Error collecting rating counts per tag: %s", e)

    def collect_rating_ratio(self):
        """
        Collect overall rating ratio (percentage of positive ratings).
        OPTIMIZED: Uses cached data from _fetch_all_rating_metrics
        """
        try:
            if self._rating_cache is None:
                self._fetch_all_rating_metrics()

            thumbs_up = self._rating_cache['total_thumbs_up']
            thumbs_down = self._rating_cache['total_thumbs_down']
            total = thumbs_up + thumbs_down

            ratio = (thumbs_up / total * 100) if total > 0 else 0
            logger.debug("Overall rating ratio: %.2f%% (%d/%d)", ratio, thumbs_up, total)

            yield GaugeMetricFamily(
                "librechat_overall_rating_ratio",
                "Overall percentage of positive ratings (0-100)",
                value=ratio,
            )
        except Exception as e:
            logger.exception("Error collecting overall rating ratio: %s", e)

    def collect_rating_counts_5m(self):
        """
        Collect rating counts in the last 5 minutes.
        OPTIMIZED: Uses cached data from _fetch_all_rating_metrics
        """
        try:
            if self._rating_cache is None:
                self._fetch_all_rating_metrics()

            thumbs_up_5m = self._rating_cache['thumbs_up_5m']
            thumbs_down_5m = self._rating_cache['thumbs_down_5m']

            logger.debug("Thumbs up in last 5 minutes: %s", thumbs_up_5m)
            logger.debug("Thumbs down in last 5 minutes: %s", thumbs_down_5m)

            yield GaugeMetricFamily(
                "librechat_thumbs_up_5m",
                "Number of thumbs up ratings in the last 5 minutes",
                value=thumbs_up_5m,
            )
            yield GaugeMetricFamily(
                "librechat_thumbs_down_5m",
                "Number of thumbs down ratings in the last 5 minutes",
                value=thumbs_down_5m,
            )
        except Exception as e:
            logger.exception("Error collecting rating counts in last 5 minutes: %s", e)

    def collect_rated_message_count(self):
        """
        Collect total number of messages that have ratings.
        OPTIMIZED: Uses cached data from _fetch_all_rating_metrics
        """
        try:
            if self._rating_cache is None:
                self._fetch_all_rating_metrics()

            rated_count = self._rating_cache['rated_count']
            logger.debug("Total rated messages: %s", rated_count)

            yield GaugeMetricFamily(
                "librechat_rated_messages_total",
                "Total number of messages that have ratings",
                value=rated_count,
            )
        except Exception as e:
            logger.exception("Error collecting rated message count: %s", e)

    def collect_model_tag_combinations(self):
        """
        Collect rating counts for model and tag combinations.
        OPTIMIZED: Uses cached data from _fetch_all_rating_metrics
        """
        try:
            if self._rating_cache is None:
                self._fetch_all_rating_metrics()

            data = self._rating_cache['model_tag_combos']

            # Separate metrics for thumbs up and thumbs down
            metric_up = GaugeMetricFamily(
                "librechat_model_tag_thumbs_up",
                "Number of thumbs up ratings per model and tag combination",
                labels=["model", "tag"],
            )
            metric_down = GaugeMetricFamily(
                "librechat_model_tag_thumbs_down",
                "Number of thumbs down ratings per model and tag combination",
                labels=["model", "tag"],
            )

            for (model, tag, rating), count in data.items():
                if rating == "thumbsUp":
                    metric_up.add_metric([model, tag], count)
                    logger.debug("Thumbs up for model %s, tag %s: %s", model, tag, count)
                elif rating == "thumbsDown":
                    metric_down.add_metric([model, tag], count)
                    logger.debug("Thumbs down for model %s, tag %s: %s", model, tag, count)

            yield metric_up
            yield metric_down
        except Exception as e:
            logger.exception("Error collecting model tag combinations: %s", e)


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
