-- Drop and recreate database
DROP DATABASE IF EXISTS metrics;
CREATE DATABASE metrics;
CREATE USER IF NOT EXISTS 'metrics'@'%' IDENTIFIED BY 'metrics';
GRANT ALL PRIVILEGES ON metrics.* TO 'metrics'@'%';
FLUSH PRIVILEGES;

-- Switch to metrics database
USE metrics;

-- Table for daily user metrics
CREATE TABLE daily_users (
    date DATE PRIMARY KEY,
    unique_users INT NOT NULL
);

-- Table for daily message metrics
CREATE TABLE daily_messages (
    date DATE PRIMARY KEY,
    total_messages INT NOT NULL,
    total_conversations INT NOT NULL
);

-- Table for daily messages by model
CREATE TABLE daily_messages_by_model (
    date DATE,
    model VARCHAR(255),
    message_count INT NOT NULL,
    PRIMARY KEY (date, model)
);

-- Table for daily tokens by model
CREATE TABLE daily_tokens_by_model (
    date DATE,
    model VARCHAR(255),
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    PRIMARY KEY (date, model)
);

-- Table for daily errors by model
CREATE TABLE daily_errors_by_model (
    date DATE,
    model VARCHAR(255),
    error_count INT NOT NULL,
    PRIMARY KEY (date, model)
);

-- Table for weekly user metrics
CREATE TABLE weekly_users (
    week_start DATE PRIMARY KEY,
    unique_users INT NOT NULL
);

-- Table for monthly user metrics
CREATE TABLE monthly_users (
    month_start DATE PRIMARY KEY,
    unique_users INT NOT NULL
); 