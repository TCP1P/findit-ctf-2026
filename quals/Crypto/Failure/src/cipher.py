from __future__ import annotations

from typing import Tuple

MASK32 = 0xFFFFFFFF
Words = Tuple[int, int, int]


def _rotl32(x: int, n: int) -> int:
    return ((x << n) | (x >> (32 - n))) & MASK32


def _rotl2(x: int) -> int:
    x &= 0xFF
    return ((x << 2) | (x >> 6)) & 0xFF


def _sep_byte(w: int, idx: int) -> int:
    return (w >> (8 * idx)) & 0xFF


def _combine_bytes(b3: int, b2: int, b1: int, b0: int) -> int:
    return ((b3 & 0xFF) << 24) | ((b2 & 0xFF) << 16) | ((b1 & 0xFF) << 8) | (b0 & 0xFF)


def _g_box(a: int, b: int, mode: int) -> int:
    return _rotl2((a + b + mode) & 0xFF)


def _f_box(w: int) -> int:
    w = _rotl32(w, 5)

    x0 = _sep_byte(w, 0)
    x1 = _sep_byte(w, 1)
    x2 = _sep_byte(w, 2)
    x3 = _sep_byte(w, 3)

    t0 = x2 ^ x3
    y1 = _g_box(x0 ^ x1, t0, 1)
    y0 = _g_box(x0, y1, 0)
    y2 = _g_box(t0, y1, 0)
    y3 = _g_box(x3, y2, 1)

    return _combine_bytes(y3, y2, y1, y0) & MASK32

def words_from_bytes(block: bytes) -> Words:
    return (
        int.from_bytes(block[0:4], "big"),
        int.from_bytes(block[4:8], "big"),
        int.from_bytes(block[8:12], "big"),
    )


def words_to_bytes(words: Words) -> bytes:
    a, b, c = words
    return (
        (a & MASK32).to_bytes(4, "big")
        + (b & MASK32).to_bytes(4, "big")
        + (c & MASK32).to_bytes(4, "big")
    )


def _xorshift32(x: int) -> int:
    x &= MASK32
    x ^= (x << 13) & MASK32
    x ^= x >> 17
    x ^= (x << 5) & MASK32
    return x & MASK32


def _triplet_ok(a: int, b: int, c: int) -> bool:
    mix = (
        (_rotl32(a, 3) + _rotl32(b, 11) + _rotl32(c, 19))
        ^ (a + _rotl32(b, 5) ^ _rotl32(c, 27))
    ) & MASK32
    return (mix & 0xFFFF) == 0xC3E1


def _base_word(kA: int, kB: int, kC: int, idx: int) -> int:
    x = (
        kA
        ^ _rotl32(kB, idx + 3)
        ^ _rotl32(kC, idx + 9)
        ^ ((idx + 1) * 0x9E3779B9)
        ^ 0xA5A5A5A5
    ) & MASK32
    x = _xorshift32((x + _rotl32(kA, idx + 5)) & MASK32)
    x = _xorshift32((x ^ _rotl32(kB, idx + 11) ^ kC) & MASK32)
    return x


def _derive_prev(kA: int, kB: int, kC: int, idx: int, b: int, c: int) -> int:
    x = (
        _base_word(kA, kB, kC, idx)
        ^ b
        ^ _rotl32(c, idx + 1)
        ^ _rotl32(kA, idx + 7)
        ^ _rotl32(kB, idx + 13)
        ^ _rotl32(kC, idx + 17)
    ) & MASK32
    while True:
        x = _xorshift32(x)
        if _triplet_ok(x, b, c):
            return x


def expand_subkeys(key: bytes, rounds: int) -> tuple[int, ...]:
    kA, kB, kC = words_from_bytes(key)

    k5 = _base_word(kA, kB, kC, 5)
    k4 = _base_word(kB, kC, kA, 4)
    k3 = _derive_prev(kA, kB, kC, 3, k4, k5)
    k2 = _derive_prev(kA, kB, kC, 2, k3, k4)
    k1 = _derive_prev(kA, kB, kC, 1, k2, k3)
    k0 = _derive_prev(kA, kB, kC, 0, k1, k2)

    return kA, kB, kC, k0, k1, k2, k3, k4, k5


class F41LUR3:
    def __init__(self, key: bytes, rounds: int = 6):
        self.rounds = rounds
        self.key = key
        self.subkeys = expand_subkeys(self.key, self.rounds)
        self.whitening = self.subkeys[:3]
        self.round_keys = self.subkeys[3:]

    def encrypt_block(self, block: bytes) -> bytes:
        a, b, c = words_from_bytes(block)
        a ^= self.whitening[0]
        b ^= self.whitening[1]
        c ^= self.whitening[2]
        for round_key in self.round_keys:
            a, b, c = (
                b,
                c,
                (a ^ _f_box((b ^ c ^ round_key) & MASK32)) & MASK32,
            )
        return words_to_bytes((a, b, c))

    def decrypt_block(self, block: bytes) -> bytes:
        a, b, c = words_from_bytes(block)
        for round_key in reversed(self.round_keys):
            a, b, c = (
                (c ^ _f_box((a ^ b ^ round_key) & MASK32)) & MASK32,
                a,
                b,
            )
        a ^= self.whitening[0]
        b ^= self.whitening[1]
        c ^= self.whitening[2]
        return words_to_bytes((a, b, c))
