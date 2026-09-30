# LibreChat Metrics Exporter

This tool collects and exposes various metrics from [LibreChat](https://www.librechat.ai) for monitoring via Prometheus or other tools compatible with the OpenMetrics format.

![librechat-metrics-active-users](https://github.com/user-attachments/assets/b7829936-25d8-46b9-8a9a-f54e7d685e64)


## Overview

The script connects to the MongoDB database used by LibreChat, aggregates relevant data, and exposes the metrics on an HTTP server that Prometheus can scrape.

## Features

- Collects metrics such as:
  - **Unique users per day, week, and month**
  - **Message and conversation counts**
  - **Token usage (input/output) per model**
  - **Error tracking per model** (requests rejected before generation and failures during generation)
  - **Active users and conversations**
  - **Chat rating metrics** (thumbs up/down, feedback tags, model performance)
  - **Tool usage metrics** (tool calls, success rates, per-model/endpoint breakdown, calls and failures per MCP server)
  - **Real-time activity monitoring** (5-minute windows)
  - **Usage per model over rolling windows** (e.g. 1d/7d/30d): unique users, answers, stopped answers, tokens of chat and background requests, prompt-cache tokens and credits charged, optionally split into local and external models
  - **Balance metrics**: users who ran out of credits or are close to it, and requests rejected before generation by reason
  - **Feature metrics**: memories, agents, skills, projects, shared links, MCP servers, agent API keys, temporary chats, scheduled runs, logged-in and new users
- **Chat Rating Analytics**:
  - Track user satisfaction with thumbs up/down ratings
  - Analyze model performance and quality feedback
  - Monitor rating trends and feedback reasons
  - Compare model ratings and user preferences
- **Tool Usage Analytics**:
  - Track tool/plugin usage across your LibreChat instance
  - Monitor tool success and failure rates
  - Analyze which models use which tools
  - Identify popular tools and usage patterns
  - Real-time tool activity monitoring
- Exposes metrics for Prometheus to scrape
- Designed to run continuously, collecting metrics at regular intervals
- Full backward compatibility with older LibreChat versions

## Prerequisites

- **Python 3.6** or higher
- Access to the **LibreChat MongoDB** database
- **Prometheus** installed and configured to scrape the metrics endpoint

## Setup Instructions

### 1. Clone the Repository

Clone the repository containing the script:

```bash
git clone https://github.com/yourusername/librechat-metrics.git
cd librechat-metrics
```

### 2. Install Dependencies

Use environment (strongly recommended!)

```sh
python -m venv venv
source venv/bin/activate
```

Install the required Python packages using pip:

```sh
pip install -r requirements.txt
```

### 3. Configure the Environment Variables

You can change the default configuration via environment variables.
You can either set then directly, or add them to the `.env` file.
Available configurations are:

```sh
# LibreChat web interface URL for health check (optional)
# When set, exposes the `librechat_status_code` metric with the HTTP status code
# returned by a HEAD request (-1 if the server is unreachable)
# Example: LIBRECHAT_URL=http://api:3000
LIBRECHAT_URL=

# Configure database connection
MONGODB_URI=mongodb://mongodb:27017/

# Configure log level
LOGGING_LEVEL=info

# Configure log format
LOGGING_FORMAT="%(asctime)s - %(levelname)s - %(message)s"

# Specify Mongo Database - Optional. Defaults to "LibreChat"
MONGODB_DATABASE=librechat

# Timezone for daily/weekly/monthly metric boundaries - Optional. Defaults to "UTC".
# Accepts an IANA timezone name (e.g. Asia/Tokyo, Europe/Berlin) so the
# daily/weekly/monthly unique-user metrics reset at local midnight instead of
# UTC midnight. An invalid value logs a warning and falls back to UTC.
METRICS_TIMEZONE=UTC

# ===== Performance Optimization =====
# Background cache enabled (recommended for large databases)
# When enabled, metrics are collected in a background thread and cached
# This prevents slow HTTP responses and Prometheus scrape timeouts
METRICS_CACHE_ENABLED=true

# Cache time-to-live in seconds (how often metrics are refreshed)
# Lower values = more up-to-date metrics but more MongoDB load
# Higher values = less MongoDB load but slightly stale metrics
# Recommended: 60 seconds for most deployments
METRICS_CACHE_TTL=60

# ===== Metric Group Toggles =====
# Enable/disable specific metric groups to optimize performance
# All metrics are enabled by default. Set to "false" to disable a group.

# Basic metrics: message counts, error counts, conversation counts
ENABLE_BASIC_METRICS=true

# Token metrics: input/output token tracking (can be expensive for large databases)
ENABLE_TOKEN_METRICS=true

# User metrics: active users, registered users, daily/weekly/monthly unique users
ENABLE_USER_METRICS=true

# Model metrics: per-model message counts, tokens, and errors (can be expensive)
ENABLE_MODEL_METRICS=true

# Time window metrics: 5-minute activity windows (can be expensive for large databases)
ENABLE_TIME_WINDOW_METRICS=true

# Rating metrics: user feedback, thumbs up/down, rating tags (can be expensive)
ENABLE_RATING_METRICS=true

# Tool metrics: tool usage statistics and success rates (can be expensive)
ENABLE_TOOL_METRICS=true

# File metrics: uploaded file counts
ENABLE_FILE_METRICS=true

# Usage window metrics: unique users, answers and tokens per model over rolling windows
ENABLE_USAGE_WINDOW_METRICS=true

# Balance metrics: users per balance state (exhausted, low, ok)
ENABLE_BALANCE_METRICS=true

# Feature metrics: memories, agents, skills, projects, shared links, MCP servers,
# agent API keys and temporary chats. Refreshed every USAGE_METRICS_TTL seconds.
ENABLE_FEATURE_METRICS=true

# ===== Usage Window Metrics =====
# Rolling windows (units: h, d). Keep the longest within your data retention:
# deleted chats drop out of the counts.
USAGE_WINDOWS=1d,7d,30d

# How often the usage window and feature metrics are recomputed, in seconds. The
# usage window metrics scan up to the longest window, so they refresh less often
# than the other metrics.
USAGE_METRICS_TTL=900

# Optional, case-insensitive regex (Python syntax) for models run by a third party.
# Matching models get class="external", all others class="local", and the
# librechat_window_users_by_model_class metric is exposed. Unset: class="unclassified".
EXTERNAL_MODEL_REGEX=gemini|claude|gpt
```

#### Performance Optimization for Large Databases

For large LibreChat databases, some metric groups can cause slow scraping times. You can disable expensive metric groups to improve performance:

**Most expensive metrics** (consider disabling these first):
- `ENABLE_RATING_METRICS=false` - Rating aggregations can be slow with many rated messages
- `ENABLE_TOOL_METRICS=false` - Tool usage aggregations can be slow with many tool calls
- `ENABLE_TIME_WINDOW_METRICS=false` - 5-minute window queries scan recent data frequently

**Moderately expensive metrics**:
- `ENABLE_TOKEN_METRICS=false` - Token aggregations can be slow with many messages
- `ENABLE_MODEL_METRICS=false` - Per-model breakdowns require additional grouping

**Example configuration for large databases** (keeps only essential metrics):
```sh
ENABLE_BASIC_METRICS=true          # Keep basic message/conversation counts
ENABLE_TOKEN_METRICS=true          # Keep token tracking for cost analysis
ENABLE_USER_METRICS=true           # Keep user activity metrics
ENABLE_MODEL_METRICS=false         # Disable per-model breakdowns
ENABLE_TIME_WINDOW_METRICS=false   # Disable 5-minute windows
ENABLE_RATING_METRICS=false        # Disable rating metrics
ENABLE_TOOL_METRICS=false          # Disable tool metrics
ENABLE_FILE_METRICS=true           # Keep file counts
ENABLE_BALANCE_METRICS=true        # Keep balance states (one pass over balances)
ENABLE_FEATURE_METRICS=true        # Keep feature counts (mostly small collections)
```

### 4. Run the Script

Start the metrics collection script:

```sh
python metrics.py
```

The script will start an HTTP server to expose the metrics.

### 5. Configure Prometheus

Add the following job to your Prometheus configuration file (prometheus.yml):scrape_configs:

```yaml
- job_name: 'librechat_metrics'
  scrape_interval: 60s
  static_configs:
    - targets:
        - 'localhost:8000'
```

Reload Prometheus to apply the new configuration.

## Docker Deployment

A Dockerfile is included for containerized deployment.

If you want to run the script inside the mongodb librechat container, you can add something like this to the librechat docker compose:

```yaml
metrics:
  image: ghcr.io/virtuos/librechat_exporter:main
  networks:
    - librechat
  depends_on:
    - mongodb
  ports:
    - "8000:8000"  # Expose port for Prometheus
  environment:
    - MONGODB_URI=mongodb://mongodb:27017/
    - LOGGING_LEVEL=info
  restart: unless-stopped
```

Make sure the networks attribute is the same as your mongodb container.

## Kubernetes / Helm

A Helm chart is provided under [`charts/librechat-exporter`](charts/librechat-exporter)
for deploying the exporter to Kubernetes. It ships a Deployment and Service and
can optionally create a Prometheus Operator `ServiceMonitor`.

```sh
helm install librechat-exporter ./charts/librechat-exporter \
  --set mongodb.uri="mongodb://my-mongo:27017/" \
  --set serviceMonitor.enabled=true
```

See the [chart README](charts/librechat-exporter/README.md) for the full list of
values.

## Metrics

The exporter provides the following metrics specific to LibreChat:

```sh
# HELP librechat_messages_total Number of sent messages stored in the database
# TYPE librechat_messages_total counter
librechat_messages_total 9.0

# HELP librechat_error_messages_total Number of error messages stored in the database
# TYPE librechat_error_messages_total counter
librechat_error_messages_total 0.0

# HELP librechat_input_tokens_total Number of input tokens processed
# TYPE librechat_input_tokens_total counter
librechat_input_tokens_total 0.0

# HELP librechat_output_tokens_total Total number of output tokens generated
# TYPE librechat_output_tokens_total counter
librechat_output_tokens_total 0.0

# HELP librechat_conversations_total Number of started conversations stored in the database
# TYPE librechat_conversations_total counter
librechat_conversations_total 0.0

# HELP librechat_messages_per_model_total Number of messages per model
# TYPE librechat_messages_per_model_total counter
librechat_messages_per_model_total{model="unknown"} 9.0

# HELP librechat_errors_per_model_total Number of error messages per model
# TYPE librechat_errors_per_model_total counter

# HELP librechat_input_tokens_per_model_total Number of input tokens per model
# TYPE librechat_input_tokens_per_model_total counter

# HELP librechat_output_tokens_per_model_total Number of output tokens per model
# TYPE librechat_output_tokens_per_model_total counter

# HELP librechat_active_users Number of active users in the last 5 minutes
# TYPE librechat_active_users gauge
librechat_active_users 2.0

# HELP librechat_active_conversations Number of active conversations in the last 5 minutes
# TYPE librechat_active_conversations gauge
librechat_active_conversations 0.0

# HELP librechat_uploaded_files_total Number of uploaded files
# TYPE librechat_uploaded_files_total counter
librechat_uploaded_files_total 1.0

# HELP librechat_registered_users_total Number of registered users
# TYPE librechat_registered_users_total counter
librechat_registered_users_total 1.0

# HELP librechat_daily_unique_users Number of unique users active in the current day
# TYPE librechat_daily_unique_users gauge
librechat_daily_unique_users 2.0

# HELP librechat_weekly_unique_users Number of unique users active in the current week (starting from Monday)
# TYPE librechat_weekly_unique_users gauge
librechat_weekly_unique_users 3.0

# HELP librechat_monthly_unique_users Number of unique users active in the current month
# TYPE librechat_monthly_unique_users gauge
librechat_monthly_unique_users 4.0

# HELP librechat_messages_5m Number of messages sent in the last 5 minutes
# TYPE librechat_messages_5m gauge
librechat_messages_5m 5.0

# HELP librechat_messages_per_model_5m Number of messages per model in the last 5 minutes
# TYPE librechat_messages_per_model_5m gauge
librechat_messages_per_model_5m{model="gpt-4"} 3.0

# HELP librechat_input_tokens_5m Number of input tokens used in the last 5 minutes
# TYPE librechat_input_tokens_5m gauge
librechat_input_tokens_5m 100.0

# HELP librechat_output_tokens_5m Number of output tokens generated in the last 5 minutes
# TYPE librechat_output_tokens_5m gauge
librechat_output_tokens_5m 200.0

# HELP librechat_model_input_tokens_5m Input tokens per model in the last 5 minutes
# TYPE librechat_model_input_tokens_5m gauge
librechat_model_input_tokens_5m{model="gpt-4"} 50.0

# HELP librechat_model_output_tokens_5m Output tokens per model in the last 5 minutes
# TYPE librechat_model_output_tokens_5m gauge
librechat_model_output_tokens_5m{model="gpt-4"} 100.0

# HELP librechat_thumbs_up_total Total number of thumbs up ratings
# TYPE librechat_thumbs_up_total gauge
librechat_thumbs_up_total 15.0

# HELP librechat_thumbs_down_total Total number of thumbs down ratings
# TYPE librechat_thumbs_down_total gauge
librechat_thumbs_down_total 3.0

# HELP librechat_thumbs_up_per_model Number of thumbs up ratings per model
# TYPE librechat_thumbs_up_per_model gauge
librechat_thumbs_up_per_model{model="gpt-4"} 8.0
librechat_thumbs_up_per_model{model="claude-3"} 7.0

# HELP librechat_thumbs_down_per_model Number of thumbs down ratings per model
# TYPE librechat_thumbs_down_per_model gauge
librechat_thumbs_down_per_model{model="gpt-4"} 1.0
librechat_thumbs_down_per_model{model="claude-3"} 2.0

# HELP librechat_rating_ratio_per_model Percentage of positive ratings per model (0-100)
# TYPE librechat_rating_ratio_per_model gauge
librechat_rating_ratio_per_model{model="gpt-4"} 88.9
librechat_rating_ratio_per_model{model="claude-3"} 77.8

# HELP librechat_rating_counts_per_tag Number of ratings per feedback tag and rating direction
# TYPE librechat_rating_counts_per_tag gauge
librechat_rating_counts_per_tag{tag="accurate_reliable",rating="thumbsUp"} 8.0
librechat_rating_counts_per_tag{tag="clear_well_written",rating="thumbsUp"} 6.0
librechat_rating_counts_per_tag{tag="not_matched",rating="thumbsDown"} 4.0

# HELP librechat_overall_rating_ratio Overall percentage of positive ratings (0-100)
# TYPE librechat_overall_rating_ratio gauge
librechat_overall_rating_ratio 83.3

# HELP librechat_thumbs_up_5m Number of thumbs up ratings in the last 5 minutes
# TYPE librechat_thumbs_up_5m gauge
librechat_thumbs_up_5m 2.0

# HELP librechat_thumbs_down_5m Number of thumbs down ratings in the last 5 minutes
# TYPE librechat_thumbs_down_5m gauge
librechat_thumbs_down_5m 0.0

# HELP librechat_rated_messages_total Total number of messages that have ratings
# TYPE librechat_rated_messages_total gauge
librechat_rated_messages_total 18.0

# HELP librechat_model_tag_thumbs_up Number of thumbs up ratings per model and tag combination
# TYPE librechat_model_tag_thumbs_up gauge
librechat_model_tag_thumbs_up{model="gpt-4",tag="accurate_reliable"} 5.0
librechat_model_tag_thumbs_up{model="claude-3",tag="creative_solution"} 3.0

# HELP librechat_model_tag_thumbs_down Number of thumbs down ratings per model and tag combination
# TYPE librechat_model_tag_thumbs_down gauge
librechat_model_tag_thumbs_down{model="gpt-4",tag="not_helpful"} 1.0
# HELP librechat_tool_calls_total Total number of tool calls made
# TYPE librechat_tool_calls_total gauge
librechat_tool_calls_total 240.0

# HELP librechat_tool_calls_per_tool Number of calls per tool type
# TYPE librechat_tool_calls_per_tool gauge
librechat_tool_calls_per_tool{tool_name="web_search"} 193.0
librechat_tool_calls_per_tool{tool_name="file_search"} 43.0
librechat_tool_calls_per_tool{tool_name="code_interpreter"} 15.0

# HELP librechat_tool_calls_per_model Number of tool calls per model and tool combination
# TYPE librechat_tool_calls_per_model gauge
librechat_tool_calls_per_model{model="gpt-4",tool_name="web_search"} 120.0
librechat_tool_calls_per_model{model="gpt-4",tool_name="code_interpreter"} 15.0
librechat_tool_calls_per_model{model="claude-3",tool_name="web_search"} 73.0
librechat_tool_calls_per_model{model="gpt-4",tool_name="file_search"} 43.0

# HELP librechat_tool_calls_per_endpoint Number of tool calls per endpoint and tool combination
# TYPE librechat_tool_calls_per_endpoint gauge
librechat_tool_calls_per_endpoint{endpoint="openAI",tool_name="web_search"} 147.0
librechat_tool_calls_per_endpoint{endpoint="openAI",tool_name="file_search"} 37.0
librechat_tool_calls_per_endpoint{endpoint="agents",tool_name="file_search"} 4.0

# HELP librechat_tool_call_errors_total Total number of failed tool calls
# TYPE librechat_tool_call_errors_total counter
librechat_tool_call_errors_total 12.0

# HELP librechat_tool_call_errors_per_tool_total Number of failed tool calls per tool
# TYPE librechat_tool_call_errors_per_tool_total counter
librechat_tool_call_errors_per_tool_total{tool_name="web_search"} 10.0
librechat_tool_call_errors_per_tool_total{tool_name="code_interpreter"} 2.0

# HELP librechat_tool_success_rate_per_tool Success rate percentage per tool (0-100)
# TYPE librechat_tool_success_rate_per_tool gauge
librechat_tool_success_rate_per_tool{tool_name="web_search"} 94.8
librechat_tool_success_rate_per_tool{tool_name="file_search"} 100.0
librechat_tool_success_rate_per_tool{tool_name="code_interpreter"} 86.7

# HELP librechat_tool_calls_5m Number of tool calls in the last 5 minutes
# TYPE librechat_tool_calls_5m gauge
librechat_tool_calls_5m 5.0

# HELP librechat_tool_calls_per_tool_5m Number of tool calls per tool in the last 5 minutes
# TYPE librechat_tool_calls_per_tool_5m gauge
librechat_tool_calls_per_tool_5m{tool_name="web_search"} 3.0
librechat_tool_calls_per_tool_5m{tool_name="file_search"} 2.0

# HELP librechat_tool_call_errors_5m Number of failed tool calls in the last 5 minutes
# TYPE librechat_tool_call_errors_5m gauge
librechat_tool_call_errors_5m 0.0

# HELP librechat_messages_with_tools_total Total number of messages containing tool calls
# TYPE librechat_messages_with_tools_total gauge
librechat_messages_with_tools_total 92.0

# HELP librechat_active_tool_users Number of unique users using tools in the last 5 minutes
# TYPE librechat_active_tool_users gauge
librechat_active_tool_users 2.0

# HELP librechat_mcp_tool_calls_per_server Number of MCP tool calls per MCP server
# TYPE librechat_mcp_tool_calls_per_server gauge
librechat_mcp_tool_calls_per_server{server="github"} 42.0

# HELP librechat_mcp_tool_call_errors_per_server Number of failed MCP tool calls per MCP server
# TYPE librechat_mcp_tool_call_errors_per_server gauge
librechat_mcp_tool_call_errors_per_server{server="github"} 3.0

# HELP librechat_logged_in_users Number of users with a login session that has not expired
# TYPE librechat_logged_in_users gauge
librechat_logged_in_users 298.0

# HELP librechat_window_unique_users Number of unique users with at least one chat request in the rolling window
# TYPE librechat_window_unique_users gauge
librechat_window_unique_users{window="7d"} 412.0

# HELP librechat_window_users_by_model_class Number of unique users in the rolling window by the model classes they used
# TYPE librechat_window_users_by_model_class gauge
librechat_window_users_by_model_class{usage="local_only",window="7d"} 150.0
librechat_window_users_by_model_class{usage="external_only",window="7d"} 101.0
librechat_window_users_by_model_class{usage="both",window="7d"} 161.0

# HELP librechat_window_answers_per_model Number of assistant answers (without errors) per model in the rolling window
# TYPE librechat_window_answers_per_model gauge
librechat_window_answers_per_model{class="local",model="Qwen/Qwen3.5-122B-A10B-FP8",window="7d"} 318.0
librechat_window_answers_per_model{class="external",model="gemini-3.8-flash",window="7d"} 725.0

# HELP librechat_window_tokens_per_model Number of tokens of chat requests per model in the rolling window
# TYPE librechat_window_tokens_per_model gauge
librechat_window_tokens_per_model{class="local",model="Qwen/Qwen3.5-122B-A10B-FP8",type="input",window="7d"} 1.4e+07
librechat_window_tokens_per_model{class="local",model="Qwen/Qwen3.5-122B-A10B-FP8",type="output",window="7d"} 9.1e+05

# HELP librechat_window_cache_tokens_per_model Number of input tokens of chat requests read from or written to the prompt cache per model in the rolling window
# TYPE librechat_window_cache_tokens_per_model gauge
librechat_window_cache_tokens_per_model{class="external",model="claude-haiku-4-5",type="read",window="7d"} 1.1e+07
librechat_window_cache_tokens_per_model{class="external",model="claude-haiku-4-5",type="write",window="7d"} 5.8e+06

# HELP librechat_window_credits_per_model Credits charged per model, transaction context and token type in the rolling window (1,000,000 credits = 1 USD)
# TYPE librechat_window_credits_per_model gauge
librechat_window_credits_per_model{class="external",context="message",model="gemini-3.8-flash",type="input",window="7d"} 3.9e+07
librechat_window_credits_per_model{class="external",context="title",model="gemini-3.5-flash-lite",type="input",window="7d"} 5.1e+05

# HELP librechat_window_background_tokens_per_model Number of tokens of background requests (title generation, summarization, image generation, ...) per model and transaction context in the rolling window
# TYPE librechat_window_background_tokens_per_model gauge
librechat_window_background_tokens_per_model{class="external",context="title",model="gemini-3.5-flash-lite",type="input",window="7d"} 6.2e+05
librechat_window_background_tokens_per_model{class="external",context="summarization",model="gemini-3.8-flash",type="input",window="7d"} 1.1e+06

# HELP librechat_window_unfinished_answers_per_model Number of assistant answers (without errors) per model in the rolling window that were stopped before they finished
# TYPE librechat_window_unfinished_answers_per_model gauge
librechat_window_unfinished_answers_per_model{class="external",model="gemini-3.8-flash",window="7d"} 12.0

# HELP librechat_window_rejected_requests Number of requests rejected before generation per reason in the rolling window
# TYPE librechat_window_rejected_requests gauge
librechat_window_rejected_requests{reason="token_balance",window="7d"} 7.0
librechat_window_rejected_requests{reason="illegal_model_request",window="7d"} 4.0

# HELP librechat_window_new_users Number of users who registered in the rolling window
# TYPE librechat_window_new_users gauge
librechat_window_new_users{window="7d"} 35.0

# HELP librechat_window_agent_api_keys_used Number of agent API keys last used in the rolling window
# TYPE librechat_window_agent_api_keys_used gauge
librechat_window_agent_api_keys_used{window="7d"} 4.0

# HELP librechat_window_schedule_runs Number of scheduled chat runs per status in the rolling window
# TYPE librechat_window_schedule_runs gauge
librechat_window_schedule_runs{status="success",window="7d"} 20.0
librechat_window_schedule_runs{status="error",window="7d"} 1.0

# HELP librechat_balance_users Number of users per balance state (exhausted, low, ok)
# TYPE librechat_balance_users gauge
librechat_balance_users{state="exhausted"} 23.0
librechat_balance_users{state="low"} 60.0
librechat_balance_users{state="ok"} 1217.0

# HELP librechat_memory_entries_total Number of memory entries saved for users
# TYPE librechat_memory_entries_total gauge
librechat_memory_entries_total 4374.0

# HELP librechat_memory_users Number of users with at least one memory entry
# TYPE librechat_memory_users gauge
librechat_memory_users 453.0

# HELP librechat_agents_total Number of agents per category
# TYPE librechat_agents_total gauge
librechat_agents_total{category="general"} 81.0
librechat_agents_total{category="uncategorized"} 3.0

# HELP librechat_skills_total Number of skills
# TYPE librechat_skills_total gauge
librechat_skills_total 13.0

# HELP librechat_chat_projects_total Number of chat projects
# TYPE librechat_chat_projects_total gauge
librechat_chat_projects_total 62.0

# HELP librechat_shared_links_total Number of shared conversation links
# TYPE librechat_shared_links_total gauge
librechat_shared_links_total 16.0

# HELP librechat_mcp_servers_total Number of MCP servers added in LibreChat (not librechat.yaml)
# TYPE librechat_mcp_servers_total gauge
librechat_mcp_servers_total 16.0

# HELP librechat_agent_api_keys_total Number of agent API keys
# TYPE librechat_agent_api_keys_total gauge
librechat_agent_api_keys_total 23.0

# HELP librechat_temporary_conversations Number of temporary conversations stored in the database
# TYPE librechat_temporary_conversations gauge
librechat_temporary_conversations 27.0
```

### Usage window metrics

The `librechat_window_*` metrics count what happened in each rolling window
(`USAGE_WINDOWS`) instead of over the whole database, so they don't drop when
old chats are deleted and a share over time is a plain ratio:

- Users, tokens and credits come from the `transactions` collection, which
  records the model that actually ran, for agents too. Users and tokens count
  chat requests only: the contexts `message`, `incomplete` and, from LibreChat
  v0.8.8, `abort` (stopped turns) and `subagent`. Title generation,
  summarization, memory and image generation are left out; their tokens are in
  `librechat_window_background_tokens_per_model`, with the context as a label.
  LibreChat records transactions unless `transactions.enabled` is `false`.
- `librechat_window_credits_per_model` covers every charged request, with the
  transaction `context` as a label, so background tasks such as title
  generation and summarization show up there. Credits are what LibreChat
  charged against user balances at its configured rates (1,000,000 credits =
  1 USD), not a provider invoice. Credit refills are not counted.
- `librechat_window_cache_tokens_per_model` splits the input tokens of chat
  requests that were read from (`type="read"`) or written to (`type="write"`)
  the provider's prompt cache. They are part of the input tokens.
- Answers come from the `messages` collection (assistant messages without
  errors). An agent's answers carry the agent id and are counted under the
  agent's current model. `librechat_window_unfinished_answers_per_model`
  counts the answers that were stopped before they finished.
- `librechat_window_rejected_requests` counts requests LibreChat refused before
  generating an answer, by the reason it recorded: `token_balance` (not enough
  credits), `illegal_model_request` (model not allowed), and so on. Other
  messages flagged as errors, such as failed answers from endpoints outside
  the agents flow in older LibreChat versions, count as `other`.
- `librechat_window_new_users` counts registrations,
  `librechat_window_agent_api_keys_used` agent API keys last used, and
  `librechat_window_schedule_runs` scheduled chat runs by status (LibreChat
  v0.8.8+).
- A user counts as `both` when they used at least one local and one external
  model in the window. The three `usage` values add up to
  `librechat_window_unique_users`.
- Input tokens include the chat history and system prompt resent with every
  request, unlike `librechat_input_tokens_per_model_total`, which counts only
  the user's own message.

Share of users who used external models in the last 7 days:

```promql
sum by (instance) (librechat_window_users_by_model_class{window="7d", usage=~"external_only|both"})
  / on (instance) librechat_window_unique_users{window="7d"}
```

Share of answers from local models:

```promql
sum by (instance) (librechat_window_answers_per_model{window="7d", class="local"})
  / on (instance) sum by (instance) (librechat_window_answers_per_model{window="7d"})
```

Credits charged in the last 30 days, in USD, per model:

```promql
sum by (instance, model) (librechat_window_credits_per_model{window="30d"}) / 1e6
```

Share of input tokens served from the prompt cache per model:

```promql
librechat_window_cache_tokens_per_model{window="7d", type="read"}
  / ignoring (type) librechat_window_tokens_per_model{window="7d", type="input"}
```

Requests rejected for lack of credits in the last day:

```promql
librechat_window_rejected_requests{window="1d", reason="token_balance"}
```

### Balance metrics

`librechat_balance_users` counts users by the credits left in their balance
(`balances` collection, used when LibreChat's `balance.enabled` is `true`):

- `exhausted`: no credits left.
- `low`: below 10% of the user's refill amount. Users without a refill amount
  are never `low`.
- `ok`: everyone else.

The three states add up to the number of balances.

### Tool errors

A tool call counts as failed when its output is an error in one of the forms
LibreChat and MCP servers report: `Error processing tool ...`,
`Error: ... tool call failed: ...`, `Error: ... Please fix your mistakes.` or
`Error calling tool ...`. An output that only mentions an error, such as a
search result about error handling, does not count.

`librechat_mcp_tool_calls_per_server` and
`librechat_mcp_tool_call_errors_per_server` group the calls of MCP tools, which
LibreChat names `<tool>_mcp_<server>`, by server. A tool name a model made up
can show up as its own server.

### Feature metrics

Counts of the features people use: memory entries and the users who have them,
agents per category, skills, chat projects, shared links, MCP servers added in
LibreChat (servers configured in `librechat.yaml` are not stored in the
database), agent API keys and temporary chats. `librechat_logged_in_users`
counts users with a login session that has not expired; it is part of the user
metrics.

The feature metrics are refreshed every `USAGE_METRICS_TTL` seconds. A
collection that the LibreChat version doesn't have, such as `skills` before
skills existed, yields no metric rather than a 0.

## Development

For development, start a MongoDB:

```sh
# Using Docker
docker run -d -p 127.0.0.1:27017:27017 --name mongo mongo
# Using Podman
podman run -d -p 127.0.0.1:27017:27017 --name mongo mongo
```

Create a virtual environment and install the dependencies:

```sh
python -m venv venv
. ./venv/bin/activate
pip install -r requirements.txt
```

Run the metrics exporter:

```sh
python metrics.py
```

Query the metrics endpoint:

```sh
curl -sf http://localhost:8000
```

### Grafana Dashboard (Prometheus)

A starter Grafana dashboard for the real-time Prometheus metrics is provided at [prometheus-dev/Grafana-Dashboard-template.json](prometheus-dev/Grafana-Dashboard-template.json). It covers the main features: users (active / daily / weekly / monthly unique), messages and tokens (totals and 5m rates, per model), ratings (thumbs up/down, per-model rating ratio) and tool usage (calls, errors, success rate per tool).

To import it, open Grafana → **Dashboards** → **New** → **Import**, upload the JSON, and select your Prometheus datasource when prompted.

## Historical Metrics Analysis

In addition to real-time metrics monitoring, this tool supports historical analysis of LibreChat metrics using MariaDB and Grafana.

### Prerequisites for Historical Analysis

- **MariaDB** or MySQL server (supplied via docker in this repo)
- **Grafana** for visualization (supplied via docker in this repo)
- **Python 3.6+** with pymongo and mysql-connector-python (supplied via requirements.txt)

### Setup for Historical Analysis

#### 1. Clone the Repository

Clone the repository and navigate to the historic-analysis directory:

```bash
git clone https://github.com/yourusername/librechat-metrics.git
cd librechat-metrics/historic-analysis
```

#### 2. Start the Docker Containers

The historical analysis uses Docker Compose to set up MariaDB and Grafana:

```bash
docker-compose up -d
```

This will start:
- MariaDB database on port 3306
- Grafana on port 3000

Note: There is a commented-out PHPMyAdmin service in the docker-compose.yml file that you can enable for database management if needed.

#### 3. Install Python Dependencies

Refer to [Install Dependencies](#2-install-dependencies) section above for setting up the Python virtual environment.

### Exporting Metrics from MongoDB to MariaDB

The `export_metrics.py` script extracts historical data from MongoDB and loads it into MariaDB for analysis:

#### Basic Usage

```bash
# Default: Incremental sync of past 30 days
python export_metrics.py

# Specific date range
python export_metrics.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD

# Lookback period
python export_metrics.py --days N
```

#### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--start-date YYYY-MM-DD` | Start date for metrics export | N days ago (based on `--days`) |
| `--end-date YYYY-MM-DD` | End date for metrics export | Yesterday |
| `--days N` | Number of days to look back | 30 |
| `--force` | Re-process all dates, even if data exists | False |
| `--cleanup` | Delete all data outside the specified date range | False |
| `--verbose` / `-v` | Enable detailed debug logging | False |

**Note:** `--start-date` and `--end-date` must be used together.

#### Examples

```bash
# Initial sync - export metrics from January 1, 2024 to April 30, 2024
python export_metrics.py --start-date 2024-01-01 --end-date 2024-04-30

# Incremental sync - only process missing dates from last 90 days
python export_metrics.py --days 90

# Force re-sync - re-process last 30 days even if data exists
python export_metrics.py --days 30 --force

# Maintain rolling 30-day window - sync and delete data outside this range
python export_metrics.py --days 30 --cleanup

# Debug mode - see detailed processing information
python export_metrics.py --days 7 --verbose
```
#### Sync Behavior

**Incremental Sync (Default):**
The script only processes dates that are missing from MariaDB, making it efficient for daily updates.

**Force Sync (`--force`):**
Re-calculates metrics for all dates in the range, even if data already exists. Use this when:
- Fixing data inconsistencies
- After changing metric calculation logic
- Recovering from errors

**Cleanup Mode (`--cleanup`):**
Deletes all data outside the specified date range. Useful for:
- Maintaining a rolling retention window
- Limiting database growth
- **Warning:** This permanently deletes data outside your range

### What Gets Exported

The script will:
1. Connect to MongoDB and MariaDB
2. Check which dates already have data (unless `--force` is used)
3. Calculate daily metrics for each day in the specified range
4. Calculate weekly metrics (on Sundays)
5. Calculate monthly metrics (on the last day of each month)
6. Optionally delete data outside the date range (if `--cleanup` is used)

The metrics include:
- Unique users per day/week/month
- Total messages and conversations
- Message counts by model
- Token usage by model (input and output)
- Error counts by model

### Migration Notes

If you were running a previous version of the export script, you should run
`python export_metrics.py --force --cleanup` once to rebuild your data.

**Before re-syncing, create the new `daily_tokens_by_user` table** (only
required if your MariaDB volume was initialized by an older `init.sql`):

```sql
CREATE TABLE IF NOT EXISTS daily_tokens_by_user (
    date DATE,
    user VARCHAR(255),
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    PRIMARY KEY (date, user)
);
```

Key changes that require a re-sync:

- New daily_tokens_by_user table — per-user input/output token totals per day, enabling top-user leaderboards and per-user cost attribution in Grafana.
- daily_messages_by_model no longer includes user-sent messages — it now counts only assistant/model responses, giving a more accurate picture of model usage.
- Input token attribution now accounts for regenerations: if a user message was regenerated N times, input tokens are counted N× (once per AI reply), matching actual provider billing. Previous versions counted input tokens only once regardless of regenerations.
- Daily unique user counts may shift slightly due to refined counting logic.

#### Grafana Dashboard
The dashboard template has been updated to include the new per-user token
panels. Re-import the provided dashboard JSON (or add the panels manually)
to get:

- Updated model input and output pannels
- Top 10 users by total tokens (time series) — who's driving usage day over day.
- user token count — per-user input / output / total tokens for the selected time range.


### Viewing Metrics in Grafana

#### 1. Access Grafana

Once the containers are running, access Grafana at:
```
http://localhost:3000
```

Default login credentials:
- Username: admin
- Password: admin

#### 2. Configure MariaDB Data Source

1. Navigate to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **MySQL**
4. Configure the connection:
   - Host: `mariadb:3306`
   - Database: `metrics`
   - User: `metrics`
   - Password: `metrics`
   - SSL Mode: `disable`
5. Click **Save & Test**

#### 3. Import the Dashboard

1. Navigate to **Create** → **Import**
2. Click **Upload JSON file** and select the `Grafana-Dashboard-template.json` file
3. Click **Import**

The dashboard provides visualizations for:
- Messages and tokens per user over time
- Daily unique users
- Weekly unique users
- Monthly unique users

### Customizing the Analysis

#### Database Schema

The MariaDB schema is defined in `mariadb-init/init.sql` and includes tables for:
- Daily user metrics
- Daily message metrics
- Daily messages by model
- Daily tokens by model
- Daily errors by model
- Weekly user metrics
- Monthly user metrics

You can modify this file to add additional metrics tables before starting the containers. When you start first time, it will create all needed tables.

#### Grafana Dashboard

The dashboard template (`Grafana-Dashboard-template.json`) can be customized within Grafana's interface to add new panels or modify existing ones based on your specific needs.
