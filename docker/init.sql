-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Core OHLCV hypertable
CREATE TABLE IF NOT EXISTS ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    timeframe   TEXT        NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    vwap        DOUBLE PRECISION,
    trade_count INTEGER
);
SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_time ON ohlcv (symbol, timeframe, time DESC);

-- Indicator signal cache
CREATE TABLE IF NOT EXISTS indicator_signals (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    timeframe   TEXT        NOT NULL,
    indicator   TEXT        NOT NULL,
    signal      INTEGER,
    value       DOUBLE PRECISION,
    params      JSONB
);
SELECT create_hypertable('indicator_signals', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_ind ON indicator_signals (symbol, indicator, time DESC);

-- Bot performance log
CREATE TABLE IF NOT EXISTS bot_performance (
    time        TIMESTAMPTZ NOT NULL,
    bot_name    TEXT        NOT NULL,
    symbol      TEXT,
    exchange    TEXT,
    pnl         DOUBLE PRECISION,
    trades      INTEGER,
    win_rate    DOUBLE PRECISION,
    drawdown    DOUBLE PRECISION,
    sharpe      DOUBLE PRECISION
);
SELECT create_hypertable('bot_performance', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_botperf_name ON bot_performance (bot_name, time DESC);

-- Dominant cycle cache
CREATE TABLE IF NOT EXISTS dominant_cycles (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    timeframe   TEXT        NOT NULL,
    method      TEXT,
    period      DOUBLE PRECISION,
    power       DOUBLE PRECISION,
    composite   DOUBLE PRECISION
);
SELECT create_hypertable('dominant_cycles', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_cycles_symbol ON dominant_cycles (symbol, timeframe, time DESC);

-- Continuous Aggregates: 1m -> 5m -> 1h -> 1d
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS time,
    symbol,
    '5m' AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(vwap * volume) / NULLIF(sum(volume), 0) AS vwap,
    sum(trade_count) AS trade_count
FROM ohlcv
WHERE timeframe = '1m'
GROUP BY time_bucket('5 minutes', time), symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS time,
    symbol,
    '1h' AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(vwap * volume) / NULLIF(sum(volume), 0) AS vwap,
    sum(trade_count) AS trade_count
FROM ohlcv
WHERE timeframe = '1m'
GROUP BY time_bucket('1 hour', time), symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS time,
    symbol,
    '1d' AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(vwap * volume) / NULLIF(sum(volume), 0) AS vwap,
    sum(trade_count) AS trade_count
FROM ohlcv
WHERE timeframe = '1m'
GROUP BY time_bucket('1 day', time), symbol
WITH NO DATA;

-- Refresh policies
SELECT add_continuous_aggregate_policy('ohlcv_5m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('ohlcv_1h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('ohlcv_1d',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Compression policy on ohlcv (compress data older than 7 days)
ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists => TRUE);

-- Add unique constraint for upsert (needed for ON CONFLICT)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlcv_unique ON ohlcv (time, symbol, timeframe);

-- Upsert helper function
CREATE OR REPLACE FUNCTION upsert_ohlcv(
    p_time TIMESTAMPTZ,
    p_symbol TEXT,
    p_timeframe TEXT,
    p_open DOUBLE PRECISION,
    p_high DOUBLE PRECISION,
    p_low DOUBLE PRECISION,
    p_close DOUBLE PRECISION,
    p_volume DOUBLE PRECISION,
    p_vwap DOUBLE PRECISION DEFAULT NULL,
    p_trade_count INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume, vwap, trade_count)
    VALUES (p_time, p_symbol, p_timeframe, p_open, p_high, p_low, p_close, p_volume, p_vwap, p_trade_count)
    ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume,
        vwap = EXCLUDED.vwap,
        trade_count = EXCLUDED.trade_count;
EXCEPTION WHEN unique_violation THEN
    -- Handle race condition gracefully
    NULL;
END;
$$ LANGUAGE plpgsql;
