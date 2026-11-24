-- =====================================================================
-- Schema for the SIMULATED M-Pesa analytics project (SQLite)
-- All data in this project is randomly generated. It is NOT Safaricom data.
-- =====================================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS _fraud_truth;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS merchants;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS customers;

-- One row per registered mobile-money customer
CREATE TABLE customers (
    customer_id        TEXT PRIMARY KEY,                 -- e.g. C00042
    registration_date  TEXT NOT NULL,                    -- YYYY-MM-DD
    county             TEXT NOT NULL,
    age_group          TEXT NOT NULL,                    -- 18-24, 25-34, 35-44, 45-54, 55+
    account_type       TEXT NOT NULL
                       CHECK (account_type IN ('individual', 'business'))
);

-- Cash-in / cash-out points
CREATE TABLE agents (
    agent_id           TEXT PRIMARY KEY,                 -- e.g. A0007
    county             TEXT NOT NULL
);

-- Paybill businesses (billers) and Till merchants (shops)
CREATE TABLE merchants (
    merchant_id        TEXT PRIMARY KEY,                 -- e.g. M0012
    merchant_kind      TEXT NOT NULL
                       CHECK (merchant_kind IN ('paybill', 'till')),
    category           TEXT NOT NULL,                    -- Electricity, Supermarket, ...
    county             TEXT NOT NULL                     -- 'National' for paybill billers
);

-- One row per transaction attempt, initiated by customer_id
-- counterparty_id is POLYMORPHIC: it points to customers, agents or merchants
-- depending on counterparty_type, so it cannot carry a single foreign key.
-- (Good interview talking point: how would you model this differently?)
CREATE TABLE transactions (
    txn_id             TEXT PRIMARY KEY,                 -- e.g. TX0000123
    txn_ts             TEXT NOT NULL,                    -- 'YYYY-MM-DD HH:MM:SS' (EAT)
    customer_id        TEXT NOT NULL REFERENCES customers (customer_id),
    txn_type           TEXT NOT NULL
                       CHECK (txn_type IN ('send_money', 'withdraw', 'deposit',
                                           'buy_goods', 'paybill', 'airtime')),
    amount             INTEGER NOT NULL CHECK (amount > 0),   -- KES
    fee                INTEGER NOT NULL DEFAULT 0,            -- KES, illustrative tariff
    status             TEXT NOT NULL
                       CHECK (status IN ('SUCCESS', 'FAILED', 'REVERSED')),
    counterparty_type  TEXT
                       CHECK (counterparty_type IN ('customer', 'agent', 'merchant')),
    counterparty_id    TEXT                              -- NULL for airtime
);

CREATE INDEX idx_txn_ts        ON transactions (txn_ts);
CREATE INDEX idx_txn_customer  ON transactions (customer_id, txn_ts);
CREATE INDEX idx_txn_type      ON transactions (txn_type);
CREATE INDEX idx_txn_cparty    ON transactions (counterparty_type, counterparty_id);

-- Answer key for the fraud exercise. DON'T LOOK until you've built your own flags!
-- Only the injected fraud is listed; every other transaction is treated as legitimate.
CREATE TABLE _fraud_truth (
    txn_id             TEXT PRIMARY KEY REFERENCES transactions (txn_id),
    pattern            TEXT NOT NULL                     -- 'burst' or 'takeover'
);
