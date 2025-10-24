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
  - **Error tracking per model**
  - **Active users and conversations**
  - **Chat rating metrics** (thumbs up/down, feedback tags, model performance)
  - **Tool usage metrics** (tool calls, success rates, per-model/endpoint breakdown)
  - **Real-time activity monitoring** (5-minute windows)
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
# Configure database connection
MONGODB_URI=mongodb://mongodb:27017/

# Configure log level
LOGGING_LEVEL=info

# Configure log format
LOGGING_FORMAT="%(asctime)s - %(levelname)s - %(message)s"

# Specify Mongo Database - Optional. Defaults to "LibreChat"
MONGODB_DATABASE=librechat

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

# HELP librechat_rating_counts_per_tag Number of ratings per feedback tag
# TYPE librechat_rating_counts_per_tag gauge
librechat_rating_counts_per_tag{tag="accurate_reliable"} 8.0
librechat_rating_counts_per_tag{tag="helpful"} 6.0
librechat_rating_counts_per_tag{tag="creative"} 4.0

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
librechat_model_tag_thumbs_up{model="claude-3",tag="creative"} 3.0

# HELP librechat_model_tag_thumbs_down Number of thumbs down ratings per model and tag combination
# TYPE librechat_model_tag_thumbs_down gauge
librechat_model_tag_thumbs_down{model="gpt-4",tag="unhelpful"} 1.0
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
```

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

```bash
python export_metrics.py YYYY-MM-DD YYYY-MM-DD
```

Replace the date arguments with the start and end dates for your analysis period.

Example:
```bash
# Export metrics from January 1, 2024 to April 30, 2024
python export_metrics.py 2024-01-01 2024-04-30
```

The script will:
1. Clear existing metrics tables in MariaDB
2. Calculate daily metrics for each day in the specified range
3. Calculate weekly metrics (on Sundays)
4. Calculate monthly metrics (on the last day of each month)

The metrics include:
- Unique users per day/week/month
- Total messages and conversations
- Message counts by model
- Token usage by model
- Error counts by model

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
