"""
Limit Order Book VWAP and Micro-Price Signal.
Processes top 5 levels of market depth for market making and signal generation.
"""


def vwap_orderbook(bid_prices, bid_sizes, ask_prices, ask_sizes):
    """
    Process 5-level Limit Order Book market depth:
    1. Accumulate total bid/ask volume and notional values.
    2. Compute volume-weighted average price (VWAP) for bids and asks.
    3. Calculate top-of-book micro-price.
    """
    tot_bid_vol = 0
    tot_ask_vol = 0
    bid_notional = 0
    ask_notional = 0
    for i in range(5):
        tot_bid_vol += bid_sizes[i]
        tot_ask_vol += ask_sizes[i]
        bid_notional += bid_prices[i] * bid_sizes[i]
        ask_notional += ask_prices[i] * ask_sizes[i]

    vwap_bid = 0
    if tot_bid_vol > 0:
        vwap_bid = bid_notional // tot_bid_vol

    vwap_ask = 0
    if tot_ask_vol > 0:
        vwap_ask = ask_notional // tot_ask_vol

    combined_vol = tot_bid_vol + tot_ask_vol
    vwap_mid = 0
    if combined_vol > 0:
        vwap_mid = (bid_notional + ask_notional) // combined_vol

    top_spread_vol = bid_sizes[0] + ask_sizes[0]
    micro_price = 0
    if top_spread_vol > 0:
        micro_price = (bid_prices[0] * ask_sizes[0] + ask_prices[0] * bid_sizes[0]) // top_spread_vol

    return micro_price + vwap_mid
