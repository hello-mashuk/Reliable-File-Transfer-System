"""
hamming.py
==========
Implements Hamming(7,4) encoding and decoding from scratch.

THEORY (read this before the code — it will make the code obvious):

We take 4 data bits: d1 d2 d3 d4
We build a 7-bit codeword by placing 3 parity bits at positions
that are powers of two (1, 2, 4) and the data bits at the remaining
positions (3, 5, 6, 7):

    Position:   1    2    3    4    5    6    7
    Contents:   p1   p2   d1   p3   d2   d3   d4

Each parity bit "covers" a specific set of positions, chosen so that
every position from 1-7 has a UNIQUE 3-bit binary "address":

    Position 1 = 001   Position 5 = 101
    Position 2 = 010   Position 6 = 110
    Position 3 = 011   Position 7 = 111
    Position 4 = 100

  - p1 (bit 0 of the address) covers every position whose address has
    bit 0 set  -> positions 1, 3, 5, 7
  - p2 (bit 1) covers positions 2, 3, 6, 7
  - p3 (bit 2) covers positions 4, 5, 6, 7

Each parity bit is chosen so the XOR of all bits it covers (including
itself) is 0 (even parity):

    p1 = d1 ^ d2 ^ d4      (covers 1,3,5,7 -> solve for position 1)
    p2 = d1 ^ d3 ^ d4      (covers 2,3,6,7 -> solve for position 2)
    p3 = d2 ^ d3 ^ d4      (covers 4,5,6,7 -> solve for position 4)

DECODING / ERROR CORRECTION:

At the receiver, we recompute three "check" values from the received
7 bits, using the exact same coverage groups:

    c1 = r1 ^ r3 ^ r5 ^ r7
    c2 = r2 ^ r3 ^ r6 ^ r7
    c4 = r4 ^ r5 ^ r6 ^ r7

If nothing went wrong, all three checks are 0. If exactly one bit
flipped during transmission, the checks will not all be zero — and
the beautiful property of this bit layout is that reading the checks
as a binary number (c4 c2 c1) gives you the EXACT 1-indexed position
of the flipped bit. This number is called the "syndrome".

    syndrome = c4*4 + c2*2 + c1*1

If syndrome == 0          -> no error
If syndrome in 1..7       -> flip bit at that position to fix it

After correcting, the data bits are simply read back out of
positions 3, 5, 6, 7.
"""

from typing import List, Dict, Optional


def encode_hamming(data_bits: List[int]) -> List[int]:
    """
    Encode exactly 4 data bits into a 7-bit Hamming(7,4) codeword.

    Args:
        data_bits: list of 4 ints, each 0 or 1 -> [d1, d2, d3, d4]

    Returns:
        list of 7 ints representing the encoded codeword, in
        position order [p1, p2, d1, p3, d2, d3, d4]
    """
    if len(data_bits) != 4:
        raise ValueError(f"encode_hamming expects exactly 4 bits, got {len(data_bits)}")
    for bit in data_bits:
        if bit not in (0, 1):
            raise ValueError("data_bits must only contain 0 or 1")

    d1, d2, d3, d4 = data_bits

    # Calculate parity bits using even parity over their coverage groups.
    p1 = d1 ^ d2 ^ d4   # covers positions 1, 3, 5, 7
    p2 = d1 ^ d3 ^ d4   # covers positions 2, 3, 6, 7
    p3 = d2 ^ d3 ^ d4   # covers positions 4, 5, 6, 7

    # Assemble the codeword in position order 1..7
    codeword = [p1, p2, d1, p3, d2, d3, d4]
    return codeword


def decode_hamming(encoded_bits: List[int]) -> Dict[str, Optional[object]]:
    """
    Decode a 7-bit Hamming(7,4) codeword, detecting and correcting
    a single-bit error if present.

    Args:
        encoded_bits: list of 7 ints (0 or 1), positions 1..7 in order

    Returns:
        dict with keys:
            error_detected  (bool)  - True if a bit error was found
            error_position  (int|None) - 1-indexed position of the
                                          flipped bit, or None
            corrected_bits  (list)  - the full 7-bit codeword after
                                       correction (unchanged if no error)
            data_bits       (list)  - the recovered 4 original data bits
    """
    if len(encoded_bits) != 7:
        raise ValueError(f"decode_hamming expects exactly 7 bits, got {len(encoded_bits)}")

    # Work on a copy so we never mutate the caller's list
    r = list(encoded_bits)  # r[0]=pos1, r[1]=pos2, ..., r[6]=pos7

    # Recompute the three parity checks using the SAME coverage groups
    # that were used during encoding.
    c1 = r[0] ^ r[2] ^ r[4] ^ r[6]   # checks positions 1,3,5,7
    c2 = r[1] ^ r[2] ^ r[5] ^ r[6]   # checks positions 2,3,6,7
    c4 = r[3] ^ r[4] ^ r[5] ^ r[6]   # checks positions 4,5,6,7

    # The syndrome directly encodes the 1-indexed error position.
    syndrome = (c4 << 2) | (c2 << 1) | c1

    error_detected = syndrome != 0
    corrected = list(r)

    if error_detected:
        # Flip the bit at the faulty position (convert 1-indexed -> 0-indexed)
        corrected[syndrome - 1] ^= 1

    # Data bits always live at positions 3, 5, 6, 7 -> indices 2, 4, 5, 6
    data_bits = [corrected[2], corrected[4], corrected[5], corrected[6]]

    return {
        "error_detected": error_detected,
        "error_position": syndrome if error_detected else None,
        "corrected_bits": corrected,
        "data_bits": data_bits,
    }
