"""
Scaled Dot-Product Attention Slice.
Computes an attention head projection slice for edge transformer primitives.
"""


def attention_slice(q, k, v, out):
    """
    Scaled Dot-Product Attention Slice (d_k=4, sequence_length=4).
    q: 4-element query head vector
    k: 4x4 key matrix
    v: 4x4 value matrix
    out: 4-element context projection vector
    """
    scores = [0] * 4
    for i in range(4):
        s = 0
        for d in range(4):
            s += q[d] * k[i][d]
        if s < 0:
            s = 0
        scores[i] = s // 2

    # Normalization sum
    total = 0
    for i in range(4):
        total += scores[i]
    if total == 0:
        total = 1

    # Context projection
    for d in range(4):
        ctx = 0
        for i in range(4):
            ctx += scores[i] * v[i][d]
        out[d] = ctx // total
