import React, { useState } from "react";

export default function TransactionPortal({ accounts, transactions, onExecuteTransaction }) {
    const [senderId, setSenderId] = useState(accounts[0]?.account_id || "");
    const [receiverId, setReceiverId] = useState(accounts[1]?.account_id || "");
    const [amount, setAmount] = useState("");
    const [currency, setCurrency] = useState("USD");
    const [txType, setTxType] = useState("WIRE_TRANSFER");
    const [statusMsg, setStatusMsg] = useState(null);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (senderId === receiverId) {
            alert("Error: Sender and Receiver account IDs must be distinct.");
            return;
        }
        if (!amount || Number(amount) <= 0) {
            alert("Error: Please provide a valid transaction amount.");
            return;
        }

        const payload = {
            transaction_id: `TX_${Math.floor(100000 + Math.random() * 900000)}`,
            sender_id: senderId,
            receiver_id: receiverId,
            amount: parseFloat(amount),
            currency: currency,
            transaction_type: txType,
            timestamp: new Date().toISOString().replace("T", " ").substring(0, 19),
            status: "COMPLETED",
            isLaundering: parseFloat(amount) >= 10000 ? 1 : 0
        };

        onExecuteTransaction(payload);
        setStatusMsg(`Transaction ${payload.transaction_id} committed & visualized successfully.`);
        setAmount("");
        setTimeout(() => setStatusMsg(null), 4000);
    };

    return (
        <div className="studio-container">
            {/* Transaction Terminal */}
            <div className="form-glass-card">
                <h2 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>
                    Transaction Gateway
                </h2>
                <p style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "18px" }}>
                    Commit directed transactions to the AML surveillance ledger.
                </p>

                {statusMsg && (
                    <div style={{ background: "rgba(16, 185, 129, 0.15)", border: "1px solid #10b981", color: "#6ee7b7", padding: "10px", borderRadius: "8px", fontSize: "0.75rem", marginBottom: "16px" }}>
                        {statusMsg}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label className="form-label">Source Account (sender_id)</label>
                        <select
                            className="form-control"
                            value={senderId}
                            onChange={(e) => setSenderId(e.target.value)}
                        >
                            {accounts.map((acc) => (
                                <option key={acc.account_id} value={acc.account_id}>
                                    {acc.account_id} — {acc.account_type} [{acc.country}]
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Destination Account (receiver_id)</label>
                        <select
                            className="form-control"
                            value={receiverId}
                            onChange={(e) => setReceiverId(e.target.value)}
                        >
                            {accounts.map((acc) => (
                                <option key={acc.account_id} value={acc.account_id}>
                                    {acc.account_id} — {acc.account_type} [{acc.country}]
                                </option>
                            ))}
                        </select>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "10px" }}>
                        <div className="form-group">
                            <label className="form-label">Transfer Amount</label>
                            <input
                                type="number"
                                step="0.01"
                                placeholder="e.g. 9850"
                                className="form-control mono"
                                value={amount}
                                onChange={(e) => setAmount(e.target.value)}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Currency</label>
                            <select
                                className="form-control"
                                value={currency}
                                onChange={(e) => setCurrency(e.target.value)}
                            >
                                <option value="USD">USD ($)</option>
                                <option value="EUR">EUR (€)</option>
                                <option value="INR">INR (₹)</option>
                            </select>
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Transfer Protocol (transaction_type)</label>
                        <select
                            className="form-control"
                            value={txType}
                            onChange={(e) => setTxType(e.target.value)}
                        >
                            <option value="WIRE_TRANSFER">WIRE_TRANSFER</option>
                            <option value="ACH_TRANSFER">ACH_TRANSFER</option>
                            <option value="SWIFT_INTERNATIONAL">SWIFT_INTERNATIONAL</option>
                            <option value="INTERNAL_LEDGER">INTERNAL_LEDGER</option>
                        </select>
                    </div>

                    <button type="submit" className="btn-primary-glow">
                        Transmit Transfer
                    </button>
                </form>
            </div>

            {/* Real-time Ledger Output */}
            <div className="glass-panel" style={{ flex: 1, maxWidth: "680px" }}>
                <div className="panel-title">Committed Ledger Entries (SQL Table: transactions)</div>
                <table className="glass-table">
                    <thead>
                        <tr>
                            <th>tx_id</th>
                            <th>sender</th>
                            <th>receiver</th>
                            <th>amount</th>
                            <th>protocol</th>
                            <th>status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {transactions.slice(0, 10).map((tx) => (
                            <tr key={tx.transaction_id}>
                                <td className="mono" style={{ fontWeight: 600 }}>{tx.transaction_id}</td>
                                <td style={{ color: "#94a3b8" }}>{tx.sender_id}</td>
                                <td style={{ color: "#94a3b8" }}>{tx.receiver_id}</td>
                                <td className="mono" style={{ color: tx.amount >= 10000 ? "#f87171" : "#38bdf8", fontWeight: 700 }}>
                                    ${Number(tx.amount).toLocaleString()}
                                </td>
                                <td style={{ fontSize: "0.68rem", color: "#64748b" }}>{tx.transaction_type}</td>
                                <td>
                                    <span style={{ fontSize: "0.68rem", color: tx.status === "COMPLETED" ? "#34d399" : "#fbbf24", fontWeight: 600 }}>
                                        {tx.status}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}