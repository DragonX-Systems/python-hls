"""
Binomial Option Pricing Lattice (Cox-Ross-Rubinstein Model).
Computes European call option price using discrete backwards induction.
"""


def black_scholes_lattice(s_nodes, strike, q_up, q_down, discount_denom):
    """
    4-step Binomial Option Pricing Lattice solver for European options.
    s_nodes: 5 terminal asset prices at maturity T=4
    strike: strike price K
    q_up, q_down: risk-neutral probabilities
    discount_denom: discount denominator
    """
    values = [0] * 5
    for i in range(5):
        payoff = s_nodes[i] - strike
        if payoff < 0:
            payoff = 0
        values[i] = payoff

    # Backwards induction roll-back
    for i in range(4):
        v = (values[i + 1] * q_up + values[i] * q_down) // discount_denom
        values[i] = v

    for i in range(3):
        v = (values[i + 1] * q_up + values[i] * q_down) // discount_denom
        values[i] = v

    for i in range(2):
        v = (values[i + 1] * q_up + values[i] * q_down) // discount_denom
        values[i] = v

    v0 = (values[1] * q_up + values[0] * q_down) // discount_denom
    return v0
