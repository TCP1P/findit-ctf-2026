from sage.all import *
from pwn import *
from chall import LIFT_POWER, MONOMIALS
import ast

HOST = "challctf.find-it.id"
PORT = 6767


def recv_value(io, key):
    prefix = f"{key} =".encode()
    while True:
        line = io.recvline()
        if line.startswith(prefix):
            return line[len(prefix):].strip().decode()


def recover_secret(p, coeffs, G, P):
    K = Qp(p, LIFT_POWER)
    R = PolynomialRing(K, names="x,y,z")
    x, y, z = R.gens()

    F = R.zero()
    for coeff, (a, b, c) in zip(coeffs, MONOMIALS):
        F += K(ZZ(coeff)) * x**a * y**b * z**c

    phi = EllipticCurve_from_cubic(F, [1, -1, 0], morphism=True)
    E = phi.codomain()
    S = phi([K(ZZ(v)) for v in G])
    T = phi([K(ZZ(v)) for v in P])

    n = E.change_ring(GF(p)).order()
    S = n * S
    T = n * T

    log = E.formal_group().log(2 * LIFT_POWER + 2)
    tS = -S[0] / S[1]
    tT = -T[0] / T[1]
    return ZZ(log(tT) / log(tS)) % (p ** (LIFT_POWER - 1))


def main():
    set_verbose(-1)
    io = remote(HOST, PORT)
    # io = process(["sage", "--python", "chall.py"], cwd=".")

    p = ZZ(recv_value(io, "p"))
    recv_value(io, "monomials")
    coeffs = ast.literal_eval(recv_value(io, "coeffs"))
    G = ast.literal_eval(recv_value(io, "G"))
    P = ast.literal_eval(recv_value(io, "P"))

    secret = recover_secret(p, coeffs, G, P)
    print(secret)
    io.sendlineafter(b"Secret? ", str(secret).encode())
    io.interactive()


if __name__ == "__main__":
    main()
