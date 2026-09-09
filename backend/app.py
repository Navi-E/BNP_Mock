from fastapi import FastAPI, HTTPException, Query
import networkx as nx
import pandas as pd
import numpy as np

from fastapi.middleware.cors import CORSMiddleware

from backend.db import fetch_all, fetch_one
from backend.graph_engine import (
    build_transaction_graph,
    graph_to_cytoscape,
    find_cycles,
)
from backend.ml_scorer import (
    load_model,
    predict,
    DEFAULT_FEATURES,
)


app = FastAPI(
    title="AML Transaction Network Analysis API",
    version="1.0.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@app.get("/health")
def health():
    try:
        fetch_one("SELECT 1 AS ok")

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception as exc:

        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(exc),
        }


# ---------------------------------------------------------
# ACCOUNTS
# ---------------------------------------------------------

@app.get("/accounts")
def get_accounts(
    limit: int = Query(100, ge=1, le=1000)
):

    return fetch_all(
        """
        SELECT
            account_id,
            customer_id,
            account_type,
            country,
            currency,
            status,
            created_at
        FROM accounts
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/accounts/{account_id}")
def get_account(account_id: str):

    account = fetch_one(
        """
        SELECT
            account_id,
            customer_id,
            account_type,
            country,
            currency,
            status,
            created_at
        FROM accounts
        WHERE account_id = %s
        """,
        (account_id,),
    )

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Account not found",
        )

    return account


# ---------------------------------------------------------
# TRANSACTIONS
# ---------------------------------------------------------

@app.get("/transactions")
def get_transactions(
    limit: int = Query(100, ge=1, le=2000)
):

    return fetch_all(
        """
        SELECT
            transaction_id,
            sender_id,
            receiver_id,
            amount,
            currency,
            transaction_type,
            timestamp,
            status
        FROM transactions
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str):

    tx = fetch_one(
        """
        SELECT
            transaction_id,
            sender_id,
            receiver_id,
            amount,
            currency,
            transaction_type,
            timestamp,
            status
        FROM transactions
        WHERE transaction_id = %s
        """,
        (transaction_id,),
    )

    if not tx:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    return tx


# ---------------------------------------------------------
# ACCOUNT FEATURES
# ---------------------------------------------------------

def get_account_features(account_id: str):

    row = fetch_one(
        """
        SELECT
            a.account_id,

            COUNT(t.transaction_id)::int
                AS transaction_count,

            COALESCE(
                SUM(
                    CASE
                        WHEN t.receiver_id = a.account_id
                        THEN t.amount
                        ELSE 0
                    END
                ),
                0
            ) AS total_inflow,

            COALESCE(
                SUM(
                    CASE
                        WHEN t.sender_id = a.account_id
                        THEN t.amount
                        ELSE 0
                    END
                ),
                0
            ) AS total_outflow,

            COALESCE(
                AVG(t.amount),
                0
            ) AS average_transaction_amount,

            COUNT(
                DISTINCT CASE
                    WHEN t.receiver_id = a.account_id
                    THEN t.sender_id
                END
            )::int AS unique_senders,

            COUNT(
                DISTINCT CASE
                    WHEN t.sender_id = a.account_id
                    THEN t.receiver_id
                END
            )::int AS unique_receivers

        FROM accounts a

        LEFT JOIN transactions t
            ON t.sender_id = a.account_id
            OR t.receiver_id = a.account_id

        WHERE a.account_id = %s

        GROUP BY a.account_id
        """,
        (account_id,),
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Account not found",
        )

    return row


@app.get("/accounts/{account_id}/features")
def get_features(account_id: str):

    return get_account_features(account_id)


# ---------------------------------------------------------
# ACCOUNT NETWORK
# ---------------------------------------------------------

@app.get("/accounts/{account_id}/network")
def get_account_network(
    account_id: str,
    hops: int = Query(1, ge=1, le=3),
):

    account = fetch_one(
        """
        SELECT account_id
        FROM accounts
        WHERE account_id = %s
        """,
        (account_id,),
    )

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Account not found",
        )

    transactions = fetch_all(
        """
        SELECT
            transaction_id,
            sender_id,
            receiver_id,
            amount,
            currency,
            transaction_type,
            timestamp,
            status
        FROM transactions
        WHERE status = 'SUCCESS'
        """
    )

    graph = build_transaction_graph(transactions)

    if account_id not in graph:

        return {
            "nodes": [],
            "edges": [],
            "cycles": [],
        }

    undirected = graph.to_undirected()

    neighborhood = set(
        nx.single_source_shortest_path_length(
            undirected,
            account_id,
            cutoff=hops,
        ).keys()
    )

    subgraph = graph.subgraph(
        neighborhood
    ).copy()

    return {
        **graph_to_cytoscape(subgraph),
        "cycles": find_cycles(subgraph),
    }


# =========================================================
# ML FEATURE ENGINE
# =========================================================

WINDOW_MINUTES = 15
RAPID_TRANSACTION_MINUTES = 5


def build_ml_features():

    # -----------------------------------------------------
    # LOAD TRANSACTIONS
    # -----------------------------------------------------

    transactions = fetch_all(
        """
        SELECT
            transaction_id,
            sender_id,
            receiver_id,
            amount,
            currency,
            transaction_type,
            timestamp,
            status
        FROM transactions
        WHERE status = 'SUCCESS'
        ORDER BY timestamp
        """
    )

    if not transactions:
        return pd.DataFrame()

    transactions_df = pd.DataFrame(transactions)

    # -----------------------------------------------------
    # LOAD ACCOUNTS
    # -----------------------------------------------------

    accounts = fetch_all(
        """
        SELECT
            account_id,
            country
        FROM accounts
        """
    )

    accounts_df = pd.DataFrame(accounts)

    # -----------------------------------------------------
    # DATA TYPES
    # -----------------------------------------------------

    transactions_df["timestamp"] = pd.to_datetime(
        transactions_df["timestamp"]
    )

    transactions_df["amount"] = pd.to_numeric(
        transactions_df["amount"]
    )

    # -----------------------------------------------------
    # SENDER TRANSACTION COUNT
    # -----------------------------------------------------

    transactions_df["sender_transaction_count"] = (
        transactions_df
        .groupby("sender_id")["transaction_id"]
        .transform("count")
    )

    # -----------------------------------------------------
    # RECEIVER TRANSACTION COUNT
    # -----------------------------------------------------

    transactions_df["receiver_transaction_count"] = (
        transactions_df
        .groupby("receiver_id")["transaction_id"]
        .transform("count")
    )

    # -----------------------------------------------------
    # COUNTRY INFORMATION
    # -----------------------------------------------------

    account_country = (
        accounts_df
        .set_index("account_id")["country"]
        .to_dict()
    )

    transactions_df["sender_country"] = (
        transactions_df["sender_id"]
        .map(account_country)
    )

    transactions_df["receiver_country"] = (
        transactions_df["receiver_id"]
        .map(account_country)
    )

    # -----------------------------------------------------
    # CROSS BORDER
    # -----------------------------------------------------

    transactions_df["cross_border"] = (
        transactions_df["sender_country"]
        != transactions_df["receiver_country"]
    ).astype(int)

    # -----------------------------------------------------
    # STRUCTURING
    #
    # Same rule used by teammate:
    # 4500 <= amount < 5000
    # -----------------------------------------------------

    transactions_df["structuring_flag"] = (
        (transactions_df["amount"] >= 4500)
        &
        (transactions_df["amount"] < 5000)
    ).astype(int)

    # -----------------------------------------------------
    # TIME SINCE PREVIOUS SENDER TRANSACTION
    # -----------------------------------------------------

    transactions_df = (
        transactions_df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    transactions_df["time_since_previous_sender_txn"] = (
        transactions_df
        .groupby("sender_id")["timestamp"]
        .diff()
        .dt.total_seconds()
        .div(60)
    )

    transactions_df[
        "time_since_previous_sender_txn"
    ] = transactions_df[
        "time_since_previous_sender_txn"
    ].fillna(999999)

    # -----------------------------------------------------
    # RAPID TRANSACTION
    # -----------------------------------------------------

    transactions_df["rapid_transaction_flag"] = (
        transactions_df[
            "time_since_previous_sender_txn"
        ] <= RAPID_TRANSACTION_MINUTES
    ).astype(int)

    # -----------------------------------------------------
    # INITIALIZE GRAPH FEATURES
    # -----------------------------------------------------

    graph_features = [
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
    ]

    for feature in graph_features:

        transactions_df[feature] = 0.0

    # -----------------------------------------------------
    # DYNAMIC 15-MINUTE GRAPH
    # -----------------------------------------------------

    for index, row in transactions_df.iterrows():

        current_time = row["timestamp"]

        window_start = (
            current_time
            - pd.Timedelta(
                minutes=WINDOW_MINUTES
            )
        )

        window_df = transactions_df[
            (transactions_df["timestamp"] >= window_start)
            &
            (transactions_df["timestamp"] <= current_time)
        ]

        # Directed graph
        G = nx.DiGraph()

        # Add all accounts
        for account_id in accounts_df["account_id"]:
            G.add_node(str(account_id))

        # Add transactions
        for _, txn in window_df.iterrows():

            G.add_edge(
                str(txn["sender_id"]),
                str(txn["receiver_id"]),
            )

        # Degree
        in_degree = dict(G.in_degree())
        out_degree = dict(G.out_degree())

        sender = str(row["sender_id"])
        receiver = str(row["receiver_id"])

        transactions_df.at[
            index,
            "sender_in_degree"
        ] = in_degree.get(sender, 0)

        transactions_df.at[
            index,
            "sender_out_degree"
        ] = out_degree.get(sender, 0)

        transactions_df.at[
            index,
            "receiver_in_degree"
        ] = in_degree.get(receiver, 0)

        transactions_df.at[
            index,
            "receiver_out_degree"
        ] = out_degree.get(receiver, 0)

        # PageRank
        if len(G.nodes) > 0:

            pagerank_scores = nx.pagerank(G)

        else:

            pagerank_scores = {}

        transactions_df.at[
            index,
            "sender_pagerank"
        ] = pagerank_scores.get(
            sender,
            0,
        )

        transactions_df.at[
            index,
            "receiver_pagerank"
        ] = pagerank_scores.get(
            receiver,
            0,
        )

        # Betweenness
        if len(G.nodes) > 1:

            betweenness_scores = (
                nx.betweenness_centrality(G)
            )

        else:

            betweenness_scores = {}

        transactions_df.at[
            index,
            "sender_betweenness"
        ] = betweenness_scores.get(
            sender,
            0,
        )

        transactions_df.at[
            index,
            "receiver_betweenness"
        ] = betweenness_scores.get(
            receiver,
            0,
        )

        # Cycle detection
        strongly_connected_components = list(
            nx.strongly_connected_components(G)
        )

        circular_accounts = set()

        for component in strongly_connected_components:

            if len(component) > 1:

                circular_accounts.update(
                    component
                )

        transactions_df.at[
            index,
            "sender_cycle_participation"
        ] = int(
            sender in circular_accounts
        )

        transactions_df.at[
            index,
            "receiver_cycle_participation"
        ] = int(
            receiver in circular_accounts
        )

    # -----------------------------------------------------
    # DEGREE RATIOS
    # -----------------------------------------------------

    transactions_df[
        "sender_in_out_degree_ratio"
    ] = (
        transactions_df["sender_in_degree"]
        /
        transactions_df[
            "sender_out_degree"
        ].replace(0, 1)
    )

    transactions_df[
        "receiver_in_out_degree_ratio"
    ] = (
        transactions_df["receiver_in_degree"]
        /
        transactions_df[
            "receiver_out_degree"
        ].replace(0, 1)
    )

    # -----------------------------------------------------
    # DWELL TIME
    # -----------------------------------------------------

    transactions_df["dwell_time_latency"] = (
        transactions_df
        .groupby("sender_id")["timestamp"]
        .shift(-1)
        -
        transactions_df["timestamp"]
    ).dt.total_seconds().div(60)

    transactions_df[
        "dwell_time_latency"
    ] = transactions_df[
        "dwell_time_latency"
    ].fillna(999999)

    # -----------------------------------------------------
    # BALANCE RETENTION PROXY
    # -----------------------------------------------------

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

    transactions_df[
        "balance_retention_rate"
    ] = (
        (inflow - outflow).clip(lower=0)
        /
        inflow.replace(0, np.nan)
    )

    transactions_df[
        "balance_retention_rate"
    ] = (
        transactions_df[
            "balance_retention_rate"
        ]
        .fillna(0)
        .clip(0, 1)
    )

    return transactions_df


# =========================================================
# TRANSACTION RISK
# =========================================================

@app.get("/transactions/{transaction_id}/risk")
def get_transaction_risk(
    transaction_id: str
):

    # -----------------------------------------------------
    # CHECK TRANSACTION EXISTS
    # -----------------------------------------------------

    transaction = fetch_one(
        """
        SELECT
            transaction_id,
            sender_id,
            receiver_id,
            amount,
            currency,
            transaction_type,
            timestamp,
            status
        FROM transactions
        WHERE transaction_id = %s
        """,
        (transaction_id,),
    )

    if not transaction:

        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    # -----------------------------------------------------
    # BUILD ALL ML FEATURES
    # -----------------------------------------------------

    features_df = build_ml_features()

    if features_df.empty:

        raise HTTPException(
            status_code=400,
            detail="No successful transactions available for ML scoring",
        )

    # -----------------------------------------------------
    # FIND REQUESTED TRANSACTION
    # -----------------------------------------------------

    matching = features_df[
        features_df["transaction_id"].astype(str)
        ==
        str(transaction_id)
    ]

    if matching.empty:

        raise HTTPException(
            status_code=400,
            detail="Transaction is not eligible for ML scoring",
        )

    row = matching.iloc[0]

    # -----------------------------------------------------
    # CREATE FEATURE DICTIONARY
    # -----------------------------------------------------

    feature_row = {}

    for feature in DEFAULT_FEATURES:

        value = row[feature]

        if pd.isna(value):
            value = 0

        if isinstance(
            value,
            (np.integer,)
        ):
            value = int(value)

        elif isinstance(
            value,
            (np.floating,)
        ):
            value = float(value)

        feature_row[feature] = value

    # -----------------------------------------------------
    # LOAD MODEL
    # -----------------------------------------------------

    model = load_model()

    if model is None:

        raise HTTPException(
            status_code=500,
            detail="ml_scorer.pkl not found in backend folder",
        )

    # -----------------------------------------------------
    # RANDOM FOREST
    # -----------------------------------------------------

    result = predict(
        model,
        feature_row,
    )

    # -----------------------------------------------------
    # ADD EXPLAINABLE RISK SIGNALS
    # -----------------------------------------------------

    risk_signals = []

    if feature_row["cross_border"] == 1:
        risk_signals.append(
            "Cross-border transaction"
        )

    if feature_row["structuring_flag"] == 1:
        risk_signals.append(
            "Transaction falls in structuring range"
        )

    if feature_row["rapid_transaction_flag"] == 1:
        risk_signals.append(
            "Rapid transaction within 5 minutes"
        )

    if (
        feature_row[
            "sender_cycle_participation"
        ]
        == 1
        or
        feature_row[
            "receiver_cycle_participation"
        ]
        == 1
    ):
        risk_signals.append(
            "Account participates in a transaction cycle"
        )

    if feature_row["sender_out_degree"] > 3:
        risk_signals.append(
            "High sender network connectivity"
        )

    if feature_row["receiver_in_degree"] > 3:
        risk_signals.append(
            "High receiver network connectivity"
        )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "transaction_id": transaction_id,

        "sender_id": transaction["sender_id"],

        "receiver_id": transaction["receiver_id"],

        "amount": float(transaction["amount"]),

        "currency": transaction["currency"],

        "prediction": result["prediction"],

        "aml_probability": result["probability"],

        "rf_risk": result["rf_risk"],

        "risk_signals": risk_signals,

        "model_status": result["model_status"],

        "features": feature_row,
    }


# =========================================================
# ACCOUNT RISK
# =========================================================

@app.get("/accounts/{account_id}/risk")
def get_account_risk(account_id: str):

    account = fetch_one(
        """
        SELECT account_id
        FROM accounts
        WHERE account_id = %s
        """,
        (account_id,),
    )

    if not account:

        raise HTTPException(
            status_code=404,
            detail="Account not found",
        )

    features_df = build_ml_features()

    if features_df.empty:

        return {
            "account_id": account_id,
            "transactions": [],
            "message": "No successful transactions available",
        }

    account_transactions = features_df[
        (
            features_df["sender_id"].astype(str)
            == str(account_id)
        )
        |
        (
            features_df["receiver_id"].astype(str)
            == str(account_id)
        )
    ]

    model = load_model()

    if model is None:

        raise HTTPException(
            status_code=500,
            detail="ml_scorer.pkl not found",
        )

    results = []

    for _, row in account_transactions.iterrows():

        feature_row = {}

        for feature in DEFAULT_FEATURES:

            value = row[feature]

            if pd.isna(value):
                value = 0

            if isinstance(
                value,
                (np.integer,)
            ):
                value = int(value)

            elif isinstance(
                value,
                (np.floating,)
            ):
                value = float(value)

            feature_row[feature] = value

        prediction_result = predict(
            model,
            feature_row,
        )

        results.append(
            {
                "transaction_id": str(
                    row["transaction_id"]
                ),
                "sender_id": str(
                    row["sender_id"]
                ),
                "receiver_id": str(
                    row["receiver_id"]
                ),
                "amount": float(
                    row["amount"]
                ),
                **prediction_result,
            }
        )

    return {
        "account_id": account_id,
        "transactions": results,
    }


# =========================================================
# ALERTS
# =========================================================

@app.get("/alerts")
def get_alerts():

    features_df = build_ml_features()

    if features_df.empty:

        return {
            "alerts": [],
            "message": "No successful transactions available",
        }

    model = load_model()

    if model is None:

        raise HTTPException(
            status_code=500,
            detail="ml_scorer.pkl not found",
        )

    alerts = []

    for _, row in features_df.iterrows():

        feature_row = {}

        for feature in DEFAULT_FEATURES:

            value = row[feature]

            if pd.isna(value):
                value = 0

            if isinstance(
                value,
                (np.integer,)
            ):
                value = int(value)

            elif isinstance(
                value,
                (np.floating,)
            ):
                value = float(value)

            feature_row[feature] = value

        result = predict(
            model,
            feature_row,
        )

        probability = result["probability"]

        if probability is not None and probability >= 0.50:

            alerts.append(
                {
                    "alert_id": (
                        f"AML-{row['transaction_id']}"
                    ),

                    "transaction_id": str(
                        row["transaction_id"]
                    ),

                    "sender_id": str(
                        row["sender_id"]
                    ),

                    "receiver_id": str(
                        row["receiver_id"]
                    ),

                    "amount": float(
                        row["amount"]
                    ),

                    "risk_score": result["rf_risk"],

                    "prediction": result["prediction"],

                    "aml_probability": probability,

                    "patterns": [],

                }
            )

    # Highest risk first
    alerts.sort(
        key=lambda x: x["risk_score"],
        reverse=True,
    )

    return {
        "alerts": alerts,
        "count": len(alerts),
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/dashboard")
def dashboard():

    counts = fetch_one(
        """
        SELECT

            (
                SELECT COUNT(*)
                FROM accounts
            ) AS total_accounts,

            (
                SELECT COUNT(*)
                FROM transactions
            ) AS total_transactions,

            (
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM transactions
                WHERE status = 'SUCCESS'
            ) AS total_successful_amount
        """
    )

    return counts