import pandas as pd
import numpy as np
import networkx as nx
import joblib
import os

from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ACCOUNTS_PATH = os.path.join(
    BASE_DIR,
    "dataset",
    "accounts.csv"
)

TRANSACTIONS_PATH = os.path.join(
    BASE_DIR,
    "dataset",
    "transactions.csv"
)

accounts_df = pd.read_csv(ACCOUNTS_PATH)
transactions_df = pd.read_csv(TRANSACTIONS_PATH)

print("Accounts Dataset:")
print(accounts_df)

print("\nTransactions Dataset:")
print(transactions_df)

print("\nAccounts shape:", accounts_df.shape)
print("Transactions shape:", transactions_df.shape)

# Generate synthetic transactions

np.random.seed(42)

normal_pairs = [
    ("A001", "A002"),
    ("A002", "A003"),
    ("A003", "A006"),
    ("A006", "A007"),
    ("A007", "A009"),
    ("A009", "A010")
]

synthetic_transactions = []

# Generate 180 normal transactions
for i in range(11, 191):

    sender, receiver = normal_pairs[
        np.random.randint(len(normal_pairs))
    ]

    amount = round(
        np.random.uniform(500, 5000),
        2
    )

    hour = np.random.randint(8, 20)
    minute = np.random.randint(0, 60)

    timestamp = (
        f"2026-09-01 "
        f"{hour:02d}:{minute:02d}"
    )

    synthetic_transactions.append([
        f"T{i:03d}",
        sender,
        receiver,
        amount,
        "INR",
        "TRANSFER",
        timestamp,
        "SUCCESS"
    ])


# Suspicious transactions
suspicious_transactions = [
    ("A001", "A004", 95000, "SGD", "INTERNATIONAL", "2026-09-01 14:00"),
    ("A004", "A005", 93000, "AED", "INTERNATIONAL", "2026-09-01 14:03"),
    ("A005", "A008", 92000, "USD", "INTERNATIONAL", "2026-09-01 14:06"),
    ("A008", "A001", 90000, "INR", "INTERNATIONAL", "2026-09-01 14:09"),

    ("A009", "A002", 4900, "INR", "TRANSFER", "2026-09-01 15:00"),
    ("A009", "A003", 4850, "INR", "TRANSFER", "2026-09-01 15:02"),
    ("A009", "A002", 4700, "INR", "TRANSFER", "2026-09-01 15:04"),
    ("A009", "A003", 4600, "INR", "TRANSFER", "2026-09-01 15:06"),

    ("A002", "A006", 18000, "INR", "TRANSFER", "2026-09-01 16:00"),
    ("A006", "A007", 17500, "INR", "TRANSFER", "2026-09-01 16:02")
]


# Add suspicious transactions as T191-T200
for index, transaction in enumerate(
    suspicious_transactions,
    start=191
):

    sender, receiver, amount, currency, transaction_type, timestamp = transaction

    synthetic_transactions.append([
        f"T{index:03d}",
        sender,
        receiver,
        amount,
        currency,
        transaction_type,
        timestamp,
        "SUCCESS"
    ])


# Convert synthetic data into DataFrame
synthetic_df = pd.DataFrame(
    synthetic_transactions,
    columns=transactions_df.columns
)


# Combine original and synthetic transactions
transactions_df = pd.concat(
    [
        transactions_df,
        synthetic_df
    ],
    ignore_index=True
)


print("\nAfter synthetic data generation:")
print("Total transactions:", len(transactions_df))
print("Transactions shape:", transactions_df.shape)


# Financial and behavioral features

# Convert timestamp to datetime
transactions_df["timestamp"] = pd.to_datetime(
    transactions_df["timestamp"]
)

# Make sure amount is numeric
transactions_df["amount"] = pd.to_numeric(
    transactions_df["amount"]
)

# Sender transaction velocity
transactions_df["sender_transaction_count"] = (
    transactions_df
    .groupby("sender_id")["transaction_id"]
    .transform("count")
)

# Receiver transaction count
transactions_df["receiver_transaction_count"] = (
    transactions_df
    .groupby("receiver_id")["transaction_id"]
    .transform("count")
)

# Get country of each account
account_country = accounts_df.set_index(
    "account_id"
)["country"]

# Map sender and receiver countries
transactions_df["sender_country"] = (
    transactions_df["sender_id"].map(account_country)
)

transactions_df["receiver_country"] = (
    transactions_df["receiver_id"].map(account_country)
)

# Cross-border transaction indicator
transactions_df["cross_border"] = (
    transactions_df["sender_country"] !=
    transactions_df["receiver_country"]
).astype(int)

# Structuring indicator
# Detect transactions close to but below ₹5,000
transactions_df["structuring_flag"] = (
    (transactions_df["amount"] >= 4500) &
    (transactions_df["amount"] < 5000)
).astype(int)

print("\nFinancial and behavioral features created.")

print(
    transactions_df[
        [
            "transaction_id",
            "amount",
            "sender_transaction_count",
            "receiver_transaction_count",
            "cross_border",
            "structuring_flag"
        ]
    ].head(10)
)

# Time-based and rapid transaction features

# Sort transactions chronologically
transactions_df = transactions_df.sort_values(
    "timestamp"
).reset_index(drop=True)

# Calculate time since the sender's previous transaction
transactions_df["time_since_previous_sender_txn"] = (
    transactions_df
    .groupby("sender_id")["timestamp"]
    .diff()
    .dt.total_seconds()
    .div(60)
)

# First transaction of each sender has no previous transaction
transactions_df["time_since_previous_sender_txn"] = (
    transactions_df["time_since_previous_sender_txn"]
    .fillna(999999)
)

# Flag transactions occurring within 5 minutes
transactions_df["rapid_transaction_flag"] = (
    transactions_df["time_since_previous_sender_txn"] <= 5
).astype(int)

print("\nTime-based features created.")

print(
    transactions_df[
        [
            "transaction_id",
            "sender_id",
            "timestamp",
            "time_since_previous_sender_txn",
            "rapid_transaction_flag"
        ]
    ].head(20)
)

print(
    "\nRapid transactions detected:",
    transactions_df["rapid_transaction_flag"].sum()
)

# Dynamic graph features

WINDOW_MINUTES = 15

transactions_df["sender_in_degree"] = 0
transactions_df["sender_out_degree"] = 0
transactions_df["receiver_in_degree"] = 0
transactions_df["receiver_out_degree"] = 0

transactions_df["sender_pagerank"] = 0.0
transactions_df["receiver_pagerank"] = 0.0

transactions_df["sender_betweenness"] = 0.0
transactions_df["receiver_betweenness"] = 0.0

transactions_df["sender_cycle_participation"] = 0
transactions_df["receiver_cycle_participation"] = 0


for index, row in transactions_df.iterrows():

    current_time = row["timestamp"]

    window_start = (
        current_time -
        pd.Timedelta(minutes=WINDOW_MINUTES)
    )

    # Transactions inside the current time window
    window_df = transactions_df[
        (transactions_df["timestamp"] >= window_start) &
        (transactions_df["timestamp"] <= current_time)
    ]

    # Create directed transaction graph
    G = nx.DiGraph()

    # Add all accounts as graph nodes
    for account_id in accounts_df["account_id"]:
        G.add_node(account_id)

    # Add transaction relationships
    for _, txn in window_df.iterrows():

        G.add_edge(
            txn["sender_id"],
            txn["receiver_id"]
        )

    # Degree features
    in_degree = dict(G.in_degree())
    out_degree = dict(G.out_degree())

    transactions_df.at[
        index,
        "sender_in_degree"
    ] = in_degree.get(row["sender_id"], 0)

    transactions_df.at[
        index,
        "sender_out_degree"
    ] = out_degree.get(row["sender_id"], 0)

    transactions_df.at[
        index,
        "receiver_in_degree"
    ] = in_degree.get(row["receiver_id"], 0)

    transactions_df.at[
        index,
        "receiver_out_degree"
    ] = out_degree.get(row["receiver_id"], 0)

    # PageRank
    pagerank_scores = nx.pagerank(G)

    transactions_df.at[
        index,
        "sender_pagerank"
    ] = pagerank_scores.get(
        row["sender_id"], 0
    )

    transactions_df.at[
        index,
        "receiver_pagerank"
    ] = pagerank_scores.get(
        row["receiver_id"], 0
    )

    # Betweenness centrality
    betweenness_scores = nx.betweenness_centrality(G)

    transactions_df.at[
        index,
        "sender_betweenness"
    ] = betweenness_scores.get(
        row["sender_id"], 0
    )

    transactions_df.at[
        index,
        "receiver_betweenness"
    ] = betweenness_scores.get(
        row["receiver_id"], 0
    )

    # Detect directed cycles
    strongly_connected_components = list(
        nx.strongly_connected_components(G)
    )

    circular_accounts = set()

    for component in strongly_connected_components:

        if len(component) > 1:
            circular_accounts.update(component)

    transactions_df.at[
        index,
        "sender_cycle_participation"
    ] = int(
        row["sender_id"] in circular_accounts
    )

    transactions_df.at[
        index,
        "receiver_cycle_participation"
    ] = int(
        row["receiver_id"] in circular_accounts
    )


print("\nDynamic graph features created.")

print(
    transactions_df[
        [
            "transaction_id",
            "sender_id",
            "receiver_id",
            "sender_in_degree",
            "sender_out_degree",
            "sender_pagerank",
            "sender_betweenness",
            "sender_cycle_participation"
        ]
    ].head(20)
)

# Additional behavioral features

# Sender in-degree to out-degree ratio
transactions_df["sender_in_out_degree_ratio"] = (
    transactions_df["sender_in_degree"] /
    transactions_df["sender_out_degree"].replace(0, 1)
)

# Receiver in-degree to out-degree ratio
transactions_df["receiver_in_out_degree_ratio"] = (
    transactions_df["receiver_in_degree"] /
    transactions_df["receiver_out_degree"].replace(0, 1)
)

# Dwell-time latency
# Time until the sender's next transaction
transactions_df["dwell_time_latency"] = (
    transactions_df
    .groupby("sender_id")["timestamp"]
    .shift(-1)
    - transactions_df["timestamp"]
).dt.total_seconds().div(60)

transactions_df["dwell_time_latency"] = (
    transactions_df["dwell_time_latency"]
    .fillna(999999)
)

# Balance retention proxy
# The accounts dataset does not contain actual account balances.
# Therefore, this is an estimated retention measure based on
# cumulative inflow and outflow.

inflow = (
    transactions_df
    .groupby("receiver_id")["amount"]
    .cumsum()
)

outflow = (
    transactions_df
    .groupby("sender_id")["amount"]
    .cumsum()
)

transactions_df["balance_retention_rate"] = (
    (inflow - outflow).clip(lower=0) /
    inflow.replace(0, np.nan)
)

transactions_df["balance_retention_rate"] = (
    transactions_df["balance_retention_rate"]
    .fillna(0)
    .clip(0, 1)
)

print("\nAdditional behavioral features created.")

print(
    transactions_df[
        [
            "transaction_id",
            "sender_in_out_degree_ratio",
            "receiver_in_out_degree_ratio",
            "dwell_time_latency",
            "balance_retention_rate"
        ]
    ].head(20)
)
# Isolation Forest anomaly detection

features = [
    "amount",
    "sender_transaction_count",
    "receiver_transaction_count",
    "cross_border",
    "structuring_flag",
    "time_since_previous_sender_txn",
    "rapid_transaction_flag",
    "sender_in_degree",
    "sender_out_degree",
    "receiver_in_degree",
    "receiver_out_degree",
    "sender_pagerank",
    "receiver_pagerank",
    "sender_betweenness",
    "receiver_betweenness",
    "sender_cycle_participation",
    "receiver_cycle_participation",
    "sender_in_out_degree_ratio",
    "receiver_in_out_degree_ratio",
    "dwell_time_latency",
    "balance_retention_rate"
]

X = transactions_df[features].fillna(0)

isolation_forest = IsolationForest(
    n_estimators=100,
    contamination=0.05,
    random_state=42
)

isolation_forest.fit(X)

transactions_df["anomaly_prediction"] = (
    isolation_forest.predict(X)
)

transactions_df["anomaly_score"] = (
    isolation_forest.decision_function(X)
)

transactions_df["is_anomaly"] = (
    transactions_df["anomaly_prediction"] == -1
).astype(int)

print("\nIsolation Forest completed.")

print(
    transactions_df[
        [
            "transaction_id",
            "anomaly_score",
            "is_anomaly"
        ]
    ].head(20)
)

print(
    "\nAnomalies detected:",
    transactions_df["is_anomaly"].sum()
)

# Random Forest supervised classification

# Create AML labels
transactions_df["known_aml_label"] = 0

known_suspicious_transactions = [
    "T005",
    "T006",
    "T007",
    "T008",
    "T009",
    "T010",
    "T191",
    "T192",
    "T193",
    "T194",
    "T195",
    "T196",
    "T197",
    "T198",
    "T199",
    "T200"
]

transactions_df.loc[
    transactions_df["transaction_id"].isin(
        known_suspicious_transactions
    ),
    "known_aml_label"
] = 1


# Feature matrix and target
X = transactions_df[features].fillna(0)
y = transactions_df["known_aml_label"]


# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    stratify=y,
    random_state=42
)


# Create Random Forest model
random_forest = RandomForestClassifier(
    n_estimators=200,
    class_weight="balanced",
    max_features="sqrt",
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)


# Train model
random_forest.fit(
    X_train,
    y_train
)


# Predictions
y_pred = random_forest.predict(X_test)

y_probability = random_forest.predict_proba(X)[:, 1]


# Evaluation
accuracy = accuracy_score(
    y_test,
    y_pred
)

precision = precision_score(
    y_test,
    y_pred,
    zero_division=0
)

recall = recall_score(
    y_test,
    y_pred,
    zero_division=0
)

f1 = f1_score(
    y_test,
    y_pred,
    zero_division=0
)


# Add AML probability to transactions
transactions_df["rf_aml_probability"] = (
    y_probability
)


print("\nRandom Forest completed.")

print("\nRandom Forest Evaluation:")
print("Accuracy:", round(accuracy, 4))
print("Precision:", round(precision, 4))
print("Recall:", round(recall, 4))
print("F1 Score:", round(f1, 4))

print(
    "\nSample Random Forest probabilities:"
)

print(
    transactions_df[
        [
            "transaction_id",
            "rf_aml_probability",
            "known_aml_label"
        ]
    ].head(20)
)

# AML Risk Score calculation

# Normalize Isolation Forest anomaly score
anomaly_min = transactions_df["anomaly_score"].min()
anomaly_max = transactions_df["anomaly_score"].max()

transactions_df["anomaly_risk"] = (
    (anomaly_max - transactions_df["anomaly_score"]) /
    (anomaly_max - anomaly_min)
) * 100


# Random Forest risk
transactions_df["rf_risk"] = (
    transactions_df["rf_aml_probability"] * 100
)


# Graph risk
transactions_df["graph_risk"] = (
    (
        transactions_df["sender_cycle_participation"] +
        transactions_df["receiver_cycle_participation"]
    ) * 50
).clip(0, 100)


# Transaction velocity risk
transactions_df["velocity_risk"] = (
    transactions_df["rapid_transaction_flag"] * 100
)


# Structuring risk
transactions_df["structuring_risk"] = (
    transactions_df["structuring_flag"] * 100
)


# Cross-border risk
transactions_df["cross_border_risk"] = (
    transactions_df["cross_border"] * 100
)


# Amount risk
transactions_df["amount_risk"] = (
    transactions_df["amount"] /
    transactions_df["amount"].max()
) * 100


# Final AML Risk Score
transactions_df["aml_risk_score"] = (
    0.30 * transactions_df["anomaly_risk"] +
    0.30 * transactions_df["rf_risk"] +
    0.10 * transactions_df["graph_risk"] +
    0.10 * transactions_df["velocity_risk"] +
    0.05 * transactions_df["structuring_risk"] +
    0.05 * transactions_df["cross_border_risk"] +
    0.10 * transactions_df["amount_risk"]
)


# Keep score between 0 and 100
transactions_df["aml_risk_score"] = (
    transactions_df["aml_risk_score"]
    .clip(0, 100)
    .round(2)
)


# Assign risk levels
transactions_df["risk_level"] = pd.cut(
    transactions_df["aml_risk_score"],
    bins=[-1, 30, 60, 100],
    labels=["Low", "Medium", "High"]
)


print("\nAML Risk Score calculation completed.")

print(
    transactions_df[
        [
            "transaction_id",
            "anomaly_risk",
            "rf_risk",
            "graph_risk",
            "velocity_risk",
            "structuring_risk",
            "cross_border_risk",
            "aml_risk_score",
            "risk_level"
        ]
    ].head(20)
)

# Check suspicious transactions

print("\nSuspicious Transaction Risk Scores:")

print(
    transactions_df[
        transactions_df["known_aml_label"] == 1
    ][
        [
            "transaction_id",
            "rf_aml_probability",
            "anomaly_risk",
            "graph_risk",
            "velocity_risk",
            "structuring_risk",
            "cross_border_risk",
            "aml_risk_score",
            "risk_level"
        ]
    ].sort_values(
        "aml_risk_score",
        ascending=False
    )
)

from sklearn.metrics import average_precision_score

# Step 7: AML Model Evaluation

# Random Forest probabilities for test data
y_test_probability = random_forest.predict_proba(X_test)[:, 1]

# PR-AUC
pr_auc = average_precision_score(
    y_test,
    y_test_probability
)

print("\nAML Model Evaluation:")
print("Accuracy:", round(accuracy, 4))
print("Precision:", round(precision, 4))
print("Recall:", round(recall, 4))
print("F1 Score:", round(f1, 4))
print("PR-AUC:", round(pr_auc, 4))