import React, { useState, useEffect, useCallback } from "react";
import GraphCanvas from "./components/GraphCanvas";
import TransactionPortal from "./components/TransactionPortal";
import "./App.css";

// Full SQL Mock Database with All Explicit Columns
const INITIAL_DB = {
    accounts: [
        {
            account_id: "ACC_HUB_99",
            customer_id: "CUST_9901",
            account_type: "CURRENT",
            country: "USA",
            currency: "USD",
            status: "ACTIVE",
            created_at: "2026-01-15 08:30:00",
            risk: 86.4,
            inDegree: 2,
            outDegree: 1,
            totalInflow: 29300.0,
            totalOutflow: 28500.0,
            inCycle: false
        },
        {
            account_id: "ACC_MULE_1",
            customer_id: "CUST_1102",
            account_type: "SAVINGS",
            country: "USA",
            currency: "USD",
            status: "ACTIVE",
            created_at: "2026-02-10 14:15:00",
            risk: 74.2,
            inDegree: 0,
            outDegree: 1,
            totalInflow: 0.0,
            totalOutflow: 9800.0,
            inCycle: false
        },
        {
            account_id: "ACC_MULE_2",
            customer_id: "CUST_1103",
            account_type: "SAVINGS",
            country: "USA",
            currency: "USD",
            status: "SUSPENDED",
            created_at: "2026-02-11 09:40:00",
            risk: 79.5,
            inDegree: 0,
            outDegree: 1,
            totalInflow: 0.0,
            totalOutflow: 9500.0,
            inCycle: false
        },
        {
            account_id: "ACC_SINK_1",
            customer_id: "CUST_8840",
            account_type: "BUSINESS",
            country: "PAN",
            currency: "USD",
            status: "ACTIVE",
            created_at: "2025-11-05 11:20:00",
            risk: 92.0,
            inDegree: 1,
            outDegree: 0,
            totalInflow: 28500.0,
            totalOutflow: 0.0,
            inCycle: false
        }
    ],
    transactions: [
        {
            transaction_id: "TX_10091",
            sender_id: "ACC_MULE_1",
            receiver_id: "ACC_HUB_99",
            amount: 9800.0,
            currency: "USD",
            transaction_type: "WIRE_TRANSFER",
            timestamp: "2026-03-01 09:15:00",
            status: "COMPLETED",
            isLaundering: 1
        },
        {
            transaction_id: "TX_10092",
            sender_id: "ACC_MULE_2",
            receiver_id: "ACC_HUB_99",
            amount: 9500.0,
            currency: "USD",
            transaction_type: "ACH_TRANSFER",
            timestamp: "2026-03-01 10:45:00",
            status: "COMPLETED",
            isLaundering: 1
        },
        {
            transaction_id: "TX_10093",
            sender_id: "ACC_HUB_99",
            receiver_id: "ACC_SINK_1",
            amount: 28500.0,
            currency: "USD",
            transaction_type: "SWIFT_INTERNATIONAL",
            timestamp: "2026-03-01 14:30:00",
            status: "COMPLETED",
            isLaundering: 1
        }
    ]
};

function formatGraph(accounts, transactions) {
    const nodes = accounts.map((acc) => ({
        data: {
            id: acc.account_id,
            label: acc.account_id,
            customer_id: acc.customer_id,
            account_type: acc.account_type,
            country: acc.country,
            currency: acc.currency,
            status: acc.status,
            created_at: acc.created_at,
            risk: acc.risk,
            inDegree: acc.inDegree,
            outDegree: acc.outDegree,
            totalInflow: acc.totalInflow,
            totalOutflow: acc.totalOutflow,
            inCycle: acc.inCycle
        }
    }));

    const edges = transactions.map((tx) => ({
        data: {
            id: tx.transaction_id,
            source: tx.sender_id,
            target: tx.receiver_id,
            amount: `$${Number(tx.amount).toLocaleString()}`,
            currency: tx.currency,
            transaction_type: tx.transaction_type,
            timestamp: tx.timestamp,
            status: tx.status,
            isLaundering: tx.isLaundering
        }
    }));

    return [...nodes, ...edges];
}

export default function App() {
    const [activeTab, setActiveTab] = useState("graph");
    const [dataset, setDataset] = useState(INITIAL_DB);
    const [elements, setElements] = useState(() =>
        formatGraph(INITIAL_DB.accounts, INITIAL_DB.transactions)
    );
    const [selectedNode, setSelectedNode] = useState(INITIAL_DB.accounts[0]);
    const [backendActive, setBackendActive] = useState(false);

    // Sync with FastAPI Backend (http://localhost:8000)
    const syncBackend = useCallback(async () => {
        try {
            const res = await fetch("http://localhost:8000/api/graph/suspicious-cluster");
            if (res.ok) {
                const json = await res.json();
                setElements(json.elements);
                setBackendActive(true);
            }
        } catch {
            setBackendActive(false);
        }
    }, []);

    useEffect(() => {
        syncBackend();
    }, [syncBackend]);

    // Execute Transaction (Pushes to Backend and updates local graph state instantly)
    const handleExecuteTransaction = async (newTx) => {
        const nextTxs = [newTx, ...dataset.transactions];
        const nextDb = { ...dataset, transactions: nextTxs };

        setDataset(nextDb);
        setElements(formatGraph(nextDb.accounts, nextTxs));

        try {
            await fetch("http://localhost:8000/api/transactions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(newTx)
            });
            setBackendActive(true);
        } catch {
            setBackendActive(false);
        }
    };

    const accountTransactions = dataset.transactions.filter(
        (tx) =>
            tx.sender_id === (selectedNode?.account_id || selectedNode?.id) ||
            tx.receiver_id === (selectedNode?.account_id || selectedNode?.id)
    );

    return (
        <div className="dashboard-root">
            {/* Top Header */}
            <header className="top-navbar">
                <div className="brand-section">
                    <div className="logo-badge">⚡</div>
                    <div className="brand-name">AML Sentinel Graph</div>
                    <div className={`badge-live-pulse ${backendActive ? "online" : ""}`}>
                        <span className="pulse-dot"></span>
                        {backendActive ? "BACKEND CONNECTED" : "OFFLINE DEMO"}
                    </div>
                </div>

                {/* View Switcher Tabs */}
                <div className="nav-tab-container">
                    <button
                        className={`nav-tab ${activeTab === "graph" ? "active" : ""}`}
                        onClick={() => setActiveTab("graph")}
                    >
                        Surveillance Graph
                    </button>
                    <button
                        className={`nav-tab ${activeTab === "transactions" ? "active" : ""}`}
                        onClick={() => setActiveTab("transactions")}
                    >
                        Transaction Terminal
                    </button>
                </div>

                <div className="action-tools">
                    <button className="btn-secondary" onClick={syncBackend}>
                        Sync Database
                    </button>
                </div>
            </header>

            {/* Main Workspace */}
            <div className="dashboard-content">
                {activeTab === "graph" ? (
                    <>
                        <div className="graph-stage">
                            <GraphCanvas elements={elements} onNodeSelect={setSelectedNode} />
                        </div>

                        {/* Complete SQL Entity Inspector */}
                        <aside className="sidebar-drawer">
                            <div className="glass-panel">
                                <div className="panel-title">SQL Entity Inspector (accounts)</div>
                                {selectedNode ? (
                                    <>
                                        <div className="profile-row">
                                            <div>
                                                <div className="profile-id mono">{selectedNode.account_id || selectedNode.id}</div>
                                                <div className="profile-sub">Customer ID: {selectedNode.customer_id}</div>
                                            </div>
                                            <div className={`risk-chip ${selectedNode.risk >= 70 ? "risk-high" : selectedNode.risk >= 40 ? "risk-medium" : "risk-low"}`}>
                                                {selectedNode.risk}
                                                <div style={{ fontSize: "0.55rem", letterSpacing: "0.5px" }}>RISK</div>
                                            </div>
                                        </div>

                                        <div className="data-grid">
                                            <div className="data-tile">
                                                <div className="data-tile-label">account_type</div>
                                                <div className="data-tile-val">{selectedNode.account_type}</div>
                                            </div>
                                            <div className="data-tile">
                                                <div className="data-tile-label">country / currency</div>
                                                <div className="data-tile-val">{selectedNode.country} ({selectedNode.currency})</div>
                                            </div>
                                            <div className="data-tile">
                                                <div className="data-tile-label">status</div>
                                                <div className="data-tile-val" style={{ color: selectedNode.status === "ACTIVE" ? "#34d399" : "#f87171" }}>
                                                    {selectedNode.status}
                                                </div>
                                            </div>
                                            <div className="data-tile">
                                                <div className="data-tile-label">created_at</div>
                                                <div className="data-tile-val mono" style={{ fontSize: "0.7rem" }}>
                                                    {selectedNode.created_at?.split(" ")[0]}
                                                </div>
                                            </div>
                                            <div className="data-tile">
                                                <div className="data-tile-label">total_inflow</div>
                                                <div className="data-tile-val mono">${Number(selectedNode.totalInflow || 0).toLocaleString()}</div>
                                            </div>
                                            <div className="data-tile">
                                                <div className="data-tile-label">total_outflow</div>
                                                <div className="data-tile-val mono">${Number(selectedNode.totalOutflow || 0).toLocaleString()}</div>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <p style={{ color: "#64748b", fontSize: "0.8rem" }}>Select an account node to inspect attributes.</p>
                                )}
                            </div>

                            {/* Transactions Ledger Panel */}
                            <div className="glass-panel" style={{ flex: 1 }}>
                                <div className="panel-title">Linked Transactions (transactions)</div>
                                {accountTransactions.length > 0 ? (
                                    <table className="glass-table">
                                        <thead>
                                            <tr>
                                                <th>tx_id</th>
                                                <th>amount</th>
                                                <th>protocol</th>
                                                <th>status</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {accountTransactions.map((tx) => (
                                                <tr key={tx.transaction_id}>
                                                    <td className="mono" style={{ fontWeight: 600 }}>{tx.transaction_id}</td>
                                                    <td className="mono" style={{ color: tx.amount >= 10000 ? "#f87171" : "#38bdf8", fontWeight: 700 }}>
                                                        ${Number(tx.amount).toLocaleString()}
                                                    </td>
                                                    <td style={{ fontSize: "0.68rem", color: "#94a3b8" }}>{tx.transaction_type}</td>
                                                    <td>
                                                        <span style={{ fontSize: "0.68rem", color: tx.status === "COMPLETED" ? "#34d399" : "#fbbf24" }}>
                                                            {tx.status}
                                                        </span>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <div style={{ color: "#64748b", fontSize: "0.75rem" }}>
                                        No recorded transactions for this node.
                                    </div>
                                )}
                            </div>
                        </aside>
                    </>
                ) : (
                    <TransactionPortal
                        accounts={dataset.accounts}
                        transactions={dataset.transactions}
                        onExecuteTransaction={handleExecuteTransaction}
                    />
                )}
            </div>
        </div>
    );
}