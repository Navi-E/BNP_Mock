CREATE TABLE IF NOT EXISTS accounts (
    account_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    account_type VARCHAR(50),
    country VARCHAR(3),
    currency VARCHAR(3),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    sender_id VARCHAR(50) NOT NULL,
    receiver_id VARCHAR(50) NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount >= 0),
    currency VARCHAR(3) NOT NULL,
    transaction_type VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,

    CONSTRAINT fk_sender
        FOREIGN KEY (sender_id) REFERENCES accounts(account_id),

    CONSTRAINT fk_receiver
        FOREIGN KEY (receiver_id) REFERENCES accounts(account_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_sender
    ON transactions(sender_id);

CREATE INDEX IF NOT EXISTS idx_transactions_receiver
    ON transactions(receiver_id);

CREATE INDEX IF NOT EXISTS idx_transactions_timestamp
    ON transactions(timestamp);

CREATE INDEX IF NOT EXISTS idx_transactions_status
    ON transactions(status);
