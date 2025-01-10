# LibreChat Metrics

This script is designed to collect and expose various metrics from the [LibreChat](https://www.librechat.ai/) application for monitoring and analysis using Prometheus.

## Overview

The script connects to the MongoDB database used by LibreChat, aggregates relevant data, and exposes the metrics on an HTTP server that Prometheus can scrape.

## Features

- Collects metrics such as:
  - **Unique users per day**
  - **Average and standard deviation of users per day**
  - **Average and standard deviation of messages per user**
  - **Messages per model per day**
  - **Average and standard deviation of messages per model per day**
- Exposes metrics for Prometheus to scrape
- Designed to run continuously, collecting metrics at regular intervals

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

Install the required Python packages using pip:

```pip install -r requirements.txt```

### 3. Configure the Environment Variables

If you want to change the default database connection string `mongodb://mongodb:27017/` or the default port for Prometheus to scrape `8000`, you can create a `.env` file and set up the mongo database connection string from your environment:

```
MONGODB_URI=mongodb://mongodb:27017/
```

### 4. Run the Script

Start the metrics collection script:

```python metrics.py```
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
  image: ghcr.io/virtuos/librechatmetrics:main
  networks:
    - librechat
  depends_on:
    - mongodb
  ports:
    - "8000:8000"  # Expose port for Prometheus
  environment:
    - MONGODB_URI=mongodb://mongodb:27017/
  restart: unless-stopped
```

Make sure the networks attribute is the same as your mongodb container.

## Metrics

The exporter provides the following metrics specific to LibreChat:

```
# HELP librechat_total_messages Total number of messages sent
# TYPE librechat_total_messages gauge
librechat_total_messages 0.0
# HELP librechat_total_errors Total number of error messages
# TYPE librechat_total_errors gauge
librechat_total_errors 0.0
# HELP librechat_total_input_tokens Total number of input tokens processed
# TYPE librechat_total_input_tokens gauge
librechat_total_input_tokens 0.0
# HELP librechat_total_output_tokens Total number of output tokens generated
# TYPE librechat_total_output_tokens gauge
librechat_total_output_tokens 0.0
# HELP librechat_total_conversations Total number of conversations started
# TYPE librechat_total_conversations gauge
librechat_total_conversations 0.0
# HELP librechat_messages_per_model_total Total number of messages per model
# TYPE librechat_messages_per_model_total gauge
librechat_messages_per_model_total{model="gpt-4o"} 1.0
# HELP librechat_errors_per_model_total Total number of errors per model
# TYPE librechat_errors_per_model_total gauge
# HELP librechat_input_tokens_per_model_total Total input tokens per model
# TYPE librechat_input_tokens_per_model_total gauge
# HELP librechat_output_tokens_per_model_total Total output tokens per model
# TYPE librechat_output_tokens_per_model_total gauge
# HELP librechat_active_users Current number of active users
# TYPE librechat_active_users gauge
librechat_active_users 0.0
# HELP librechat_active_conversations Current number of active conversations
# TYPE librechat_active_conversations gauge
librechat_active_conversations 0.0
# HELP librechat_unique_users_yesterday Number of unique users active yesterday
# TYPE librechat_unique_users_yesterday gauge
librechat_unique_users_yesterday 0.0
```
