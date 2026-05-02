import os
import signal
from cipher import F41LUR3

# tadinya mau kasi timeout tapi kayanya lebi seru kalo gapake :D
# TIMEOUT = XXXX

def encrypt(pt) :
    assert len(pt) % 12 == 0, "Bad Plaintext"
    blocks = [pt[i:i+12] for i in range(0, len(pt), 12)]
    cts = []
    for block in blocks :
        cts.append(cipher.encrypt_block(block))
    return b"".join(cts)

def decrypt(ct) :
    assert len(ct) % 12 == 0, "Bad Plaintext"
    blocks = [ct[i:i+12] for i in range(0, len(ct), 12)]
    pts = []
    for block in blocks :
        pts.append(cipher.decrypt_block(block))
    return b"".join(pts)

def menu() :
    print("[1] Encrypt")
    print("[2] Decrypt")
    print("[3] Claim Flag")
    return int(input(">> "))

timed = False
if __name__ == "__main__" :
    master_key = os.urandom(12)
    cipher = F41LUR3(rounds = 6, key = master_key)
    
    while True :
        cmd = menu()
        if cmd == 1 :
            pt = bytes.fromhex(input("Input Plaintext (Hex): "))
            print(f"Encrypted: {encrypt(pt).hex()}")
        elif cmd == 2 :
            ct = bytes.fromhex(input("Input Ciphertext (Hex): "))
            print(f"Decrypted: {decrypt(ct).hex()}")
        elif cmd == 3 :
            key = bytes.fromhex(input("Input Key (Hex): "))
            if key == master_key :
                print(open('flag.txt', 'r').read())
                break
            print("Wrong key")

        # gausah pake
        # if not timed :
        #     signal.alarm(TIMEOUT)
        #     timed = not timed
