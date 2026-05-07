from sage.all import *
from Crypto.Util.number import getPrime
from Crypto.Random.random import getrandbits

PRIME_BITS = 420
LIFT_POWER = 6
MONOMIALS = [
    (3, 0, 0),
    (2, 1, 0),
    (2, 0, 1),
    (1, 2, 0),
    (1, 1, 1),
    (1, 0, 2),
    (0, 3, 0),
    (0, 2, 1),
    (0, 1, 2),
    (0, 0, 3),
]


class SAWIT:
    def __init__(self, p, coeffs):
        assert is_prime(p)
        self.p = p
        self.modulus = p**LIFT_POWER
        self.R = Zmod(self.modulus)
        self.Fp = GF(p)
        self.O = [self.R(1), self.R(-1), self.R(0)]

        self.Rxyz = PolynomialRing(self.R, names="x,y,z")
        self.x, self.y, self.z = self.Rxyz.gens()
        self.Ruv = PolynomialRing(self.R, names="u,v")
        self.u, self.v = self.Ruv.gens()
        self.Fpy = PolynomialRing(self.Fp, names="yy")
        self.yy = self.Fpy.gen()

        self.coeffs = [self.R(c) for c in coeffs]
        self.Fpoly = self.Rxyz.zero()
        for coeff, (a, b, c) in zip(self.coeffs, MONOMIALS):
            self.Fpoly += coeff * self.x**a * self.y**b * self.z**c

        self.Fx = self.Fpoly.derivative(self.x)
        self.Fy = self.Fpoly.derivative(self.y)
        self.Fz = self.Fpoly.derivative(self.z)

        self.coeffs_mod_p = [self.Fp(int(c) % self.p) for c in self.coeffs]

    def coeffs_to_list(self):
        return [int(c) for c in self.coeffs]

    def point_to_list(self, P):
        return [int(c) for c in P]

    def normalize(self, P):
        P = [self.R(c) for c in P]
        if P[2].is_unit():
            inv = P[2] ** -1
            return [P[0] * inv, P[1] * inv, self.R(1)]
        if P[0].is_unit():
            inv = P[0] ** -1
            return [self.R(1), P[1] * inv, P[2] * inv]
        if P[1].is_unit():
            inv = P[1] ** -1
            return [P[0] * inv, self.R(1), P[2] * inv]
        raise ValueError("no unit coordinate")

    def same(self, P, Q):
        return self.normalize(P) == self.normalize(Q)

    def eval(self, P):
        return self.Fpoly(*[self.R(c) for c in P])

    def is_on_curve(self, P):
        return self.eval(P) == 0

    def reduce_mod_p(self, x):
        return self.Fp(int(self.R(x)) % self.p)

    def lift_y(self, x0, y0):
        x = self.R(int(x0))
        y = self.R(int(y0))
        for _ in range(LIFT_POWER):
            val = self.Fpoly(x, y, self.R(1))
            dval = self.Fy(x, y, self.R(1))
            if not dval.is_unit():
                raise ValueError("bad Hensel derivative")
            y -= val / dval
        return y

    def random_point(self):
        while True:
            x0 = self.Fp.random_element()
            poly = self.Fpoly(self.R(int(x0)), self.yy, self.R(1))
            poly = self.Fpy([self.reduce_mod_p(c) for c in poly.list()])
            roots = poly.roots(multiplicities=False)
            if not roots:
                continue
            for y0 in roots:
                fy0 = self.reduce_mod_p(self.Fy(self.R(int(x0)), self.R(int(y0)), self.R(1)))
                if fy0 == 0:
                    continue
                try:
                    y = self.lift_y(x0, y0)
                    P = self.normalize([self.R(int(x0)), y, self.R(1)])
                except Exception:
                    continue
                if self.same(P, self.O):
                    continue
                return P

    def poly_on_line(self, P, Q):
        X = self.u * P[0] + self.v * Q[0]
        Y = self.u * P[1] + self.v * Q[1]
        Z = self.u * P[2] + self.v * Q[2]
        return self.Fpoly(X, Y, Z)

    def third_intersection(self, P, Q):
        g = self.poly_on_line(P, Q)
        c21 = g.monomial_coefficient(self.u**2 * self.v)
        c12 = g.monomial_coefficient(self.u * self.v**2)
        return self.normalize([-c12 * P[i] + c21 * Q[i] for i in range(3)])

    def tangent_direction(self, P):
        fx = self.Fx(*P)
        fy = self.Fy(*P)
        fz = self.Fz(*P)

        if fy.is_unit():
            return [self.R(1), -fx / fy, self.R(0)]
        if fx.is_unit():
            return [-fy / fx, self.R(1), self.R(0)]
        if fz.is_unit():
            return [self.R(1), self.R(0), -fx / fz]
        raise ValueError("singular or non-smooth lift")

    def tangent_third(self, P):
        dx, dy, dz = self.tangent_direction(P)
        Q = [P[0] + dx, P[1] + dy, P[2] + dz]
        g = self.poly_on_line(P, Q)
        c12 = g.monomial_coefficient(self.u * self.v**2)
        c03 = g.monomial_coefficient(self.v**3)
        return self.normalize([-c03 * P[i] + c12 * Q[i] for i in range(3)])

    def neg(self, P):
        if self.same(P, self.O):
            return P
        return self.third_intersection(P, self.O)

    def add(self, P, Q):
        if self.same(P, self.O):
            return Q
        if self.same(Q, self.O):
            return P
        if self.same(P, self.neg(Q)):
            return self.O
        R = self.tangent_third(P) if self.same(P, Q) else self.third_intersection(P, Q)
        return self.neg(R)

    def scalarmult(self, k, P):
        assert k >= 0
        R = self.O
        Q = P
        while k > 0:
            if k & 1:
                R = self.add(R, Q)
            Q = self.add(Q, Q)
            k >>= 1
        return R
    
def random_curve():
    while True:
        p = getPrime(PRIME_BITS)
        R = Zmod(p**LIFT_POWER)

        lam = R.random_element()
        if not lam.is_unit():
            continue

        a = R.random_element()
        b = R.random_element()
        c = R.random_element()
        d = R.random_element()
        e = R.random_element()
        f = R.random_element()

        if not (a - b + c).is_unit():
            continue

        coeffs = [
            lam,
            3 * lam,
            a,
            3 * lam,
            b,
            d,
            lam,
            c,
            e,
            f,
        ]

        curve = SAWIT(p, coeffs)
        try:
            G = curve.random_point()
            H = curve.random_point()
            _ = curve.add(G, H)
            _ = curve.scalarmult(7, G)
            return curve
        except Exception:
            continue


def main():
    secret = getrandbits(2047) | (1 << 2047)
    curve = random_curve()
    G = curve.random_point()
    P = curve.scalarmult(secret, G)

    print(f"p = {curve.p}")
    print("monomials = x^3,x^2*y,x^2*z,x*y^2,x*y*z,x*z^2,y^3,y^2*z,y*z^2,z^3")
    print(f"coeffs = {curve.coeffs_to_list()}")
    print(f"G = {curve.point_to_list(G)}")
    print(f"P = {curve.point_to_list(P)}")

    guess = int(input("Secret? "))
    if guess == secret:
        print(open("flag.txt").read())


if __name__ == "__main__":
    main()
