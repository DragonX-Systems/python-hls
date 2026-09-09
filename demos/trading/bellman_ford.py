"""
Bellman-Ford (4 nodes) - Arbitrage detection, shortest path.
Simplified: fixed 4-node graph, 6 edges. Edge list flat: [u,v,w, u,v,w, ...].
V-1 relaxation rounds. edges must have length 18 (6 edges * 3).
"""


def bellman_ford_4(edges, src):
    """
    Shortest path from src in 4-node graph with up to 6 edges.
    edges: flat list of 18 ints (u0,v0,w0, u1,v1,w1, ...).
    Returns dist[4].
    """
    INF = 999999
    n = 4
    num_edges = 6
    dist = [INF, INF, INF, INF]
    dist[src] = 0
    for _ in range(n - 1):
        for e in range(num_edges):
            u = edges[e * 3]
            v = edges[e * 3 + 1]
            w = edges[e * 3 + 2]
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    return dist
