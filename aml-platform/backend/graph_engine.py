import networkx as nx

def build_transaction_graph(transactions):
    graph = nx.MultiDiGraph()

    for tx in transactions:
        sender = str(tx["sender_id"])
        receiver = str(tx["receiver_id"])

        graph.add_node(sender)
        graph.add_node(receiver)

        graph.add_edge(
            sender,
            receiver,
            transaction_id=str(tx["transaction_id"]),
            amount=float(tx["amount"]),
            currency=tx["currency"],
            transaction_type=tx["transaction_type"],
            timestamp=str(tx["timestamp"]),
            status=tx["status"],
        )

    return graph

def graph_to_cytoscape(graph):
    nodes = [{"data": {"id": str(node)}} for node in graph.nodes]

    edges = []
    for source, target, key, data in graph.edges(keys=True, data=True):
        edges.append({
            "data": {
                "id": str(data.get("transaction_id", key)),
                "source": str(source),
                "target": str(target),
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "timestamp": data.get("timestamp"),
            }
        })

    return {"nodes": nodes, "edges": edges}

def find_cycles(graph):
    # Collapse multiple transactions between the same accounts for cycle detection.
    simple_graph = nx.DiGraph()
    simple_graph.add_edges_from((u, v) for u, v in graph.edges())

    cycles = list(nx.simple_cycles(simple_graph))
    return cycles
