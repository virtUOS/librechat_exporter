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
  image: ghcr.io/virtuos/librechatmetrics:main
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
# HELP librechat_messages Number of sent messages stored in the database
# TYPE librechat_messages gauge
librechat_messages 9.0
# HELP librechat_error_messages Number of error messages stored in the database
# TYPE librechat_error_messages gauge
librechat_error_messages 0.0
# HELP librechat_input_tokens Number of input tokens processed
# TYPE librechat_input_tokens gauge
librechat_input_tokens 0.0
# HELP librechat_output_tokens Total number of output tokens generated
# TYPE librechat_output_tokens gauge
librechat_output_tokens 0.0
# HELP librechat_conversations Number of started conversations stored in the database
# TYPE librechat_conversations gauge
librechat_conversations 0.0
# HELP librechat_messages_per_model Number of messages per model
# TYPE librechat_messages_per_model gauge
librechat_messages_per_model{model="unknown"} 9.0
# HELP librechat_errors_per_model Number of error messages per model
# TYPE librechat_errors_per_model gauge
# HELP librechat_input_tokens_per_model Number of input tokens per model
# TYPE librechat_input_tokens_per_model gauge
# HELP librechat_output_tokens_per_model Number of output tokens per model
# TYPE librechat_output_tokens_per_model gauge
# HELP librechat_active_users Number of active users
# TYPE librechat_active_users gauge
librechat_active_users 2.0
# HELP librechat_active_conversations Number of active conversations
# TYPE librechat_active_conversations gauge
librechat_active_conversations 0.0
# HELP librechat_uploaded_files Number of uploaded files
# TYPE librechat_uploaded_files gauge
librechat_uploaded_files 1.0
# HELP librechat_registered_users Number of registered users
# TYPE librechat_registered_users gauge
librechat_registered_users 1.0
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
