## 1. map cubic equation to elliptic curve
elliptic curve can be represented as cubic surface, kebalikannya belum tentu tapi dari strukturnya bisa cukup mudah ditebak dan kebetulan kurvanya uda sengaja digampangin

Convertnya pake fungsi builtin sage 'EllipticCurve_from_cubic' aja, cuma perlu dipatch sedikit biar ga error di file sage/src/sage/schemes/curves/constructor.py cari is irreducible check terus di comment out, ada 2 yg harus di comment out, ini gapenting soalnya checknya tapi malah bikin error
```py
        if isinstance(k, FiniteField):
            # if _is_irreducible_and_reduced(F):
            #     return IntegralAffinePlaneCurve_finite_field(A, F)
            return AffinePlaneCurve_finite_field(A, F)
...
...
...
        if isinstance(k, FiniteField):
            # if _is_irreducible_and_reduced(F):
            #     return IntegralProjectivePlaneCurve_finite_field(A, F)
            return ProjectivePlaneCurve_finite_field(A, F)
```

referensi lain:
- https://github.com/hackthebox/uni-ctf-2023/tree/main/uni-ctf-2023/crypto/%5BHard%5D%20Zombie%20Rolled
- case sedikit lebi susah: https://github.com/Giapppp/my-ctf-challenges/tree/main/wannagame-championship-2025/clair-obscur

## 2. map elliptic curve over p^k to p-adic field
dlog EC over Zmod(p^k) itu solvable karena bisa di lift ke p-adic field
karena exponentnya > 4 butuh log di formal group nya buat bisa recover mod p^(k-1) kalo misal sampe p^4 gapake gpp
referensi lain:
- triknya dibahas dari paper arxiv yg Elliptic Curve over Z/NZ
- chall klasik: https://hackmd.io/@mitsu/ByhK-tZX_
- cara lain: https://gist.github.com/maple3142/24ed4621e8b8c9839bb100a0236235a2