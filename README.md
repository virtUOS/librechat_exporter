# LibreChat Metrics Exporter

This tool collects and exposes various metrics from [LibreChat](https://www.librechat.ai) for monitoring via Prometheus or other tools compatible with the OpenMetrics format.

![librechat-metrics-active-users](https://github.com/user-attachments/assets/b7829936-25d8-46b9-8a9a-f54e7d685e64)


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
