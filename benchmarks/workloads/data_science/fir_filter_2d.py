"""
2D Spatial FIR Filter.
Computes a 2D spatial convolution on sensor/image arrays using a 3x3 filter kernel.
"""


def fir_filter_2d(img, kernel, out):
    """
    2D Spatial FIR Filter (6x6 input image, 3x3 filter kernel, 4x4 valid output).
    img: 6x6 2D image matrix
    kernel: 3x3 2D filter kernel
    out: 4x4 filtered spatial output
    """
    for r in range(4):
        for c in range(4):
            val = 0
            for kr in range(3):
                for kc in range(3):
                    val += img[r + kr][c + kc] * kernel[kr][kc]
            out[r][c] = val // 16
