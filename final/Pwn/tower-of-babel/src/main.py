import subprocess
import sys
import secrets
import random
import tempfile
import os
import string
import time
import signal
import shutil

source_file = '/app/runner.cpp'
metadata = {
    'Doctor': {
        'arch': 'x86-64',
        'compiler': [
            'g++', '-O2', '-std=c++20', '-static'
        ],
        'secret_path': None,
        'runner_path': None,
        'wrapper_path': None,
        'perm': 1090
    },

    "Kal'tsit": {
        'arch': 'aarch64',
        'compiler': [
            'aarch64-linux-gnu-g++',
            '-O2', '-std=c++20', '-static',
            '-I./unicorn/aarch64/include',
            '-L./unicorn/aarch64/lib'
        ],
        'secret_path': None,
        'runner_path': None,
        'wrapper_path': None,
        'perm': 1101
    },

    "Theresa": {
        'arch': 'riscv64',
        'compiler': [
            'riscv64-linux-gnu-g++',
            '-O2', '-std=c++20', '-static',
            '-I./unicorn/riscv64/include',
            '-L./unicorn/riscv64/lib'
        ],
        'secret_path': None,
        'runner_path': None,
        'wrapper_path': None,
        'perm': 1094
    },

    "Civilight Eterna": {
        'arch': 'mips64',
        'compiler': [
            'mips64-linux-gnuabi64-g++',
            '-O2', '-std=c++20', '-static',
            '-I./unicorn/mips64/include',
            '-L./unicorn/mips64/lib'
        ],
        'secret_path': None,
        'runner_path': None,
        'wrapper_path': None,
        'perm': 1098
    }
}

def validate_hex(s):
    if s.lower().startswith("0x"):
        s = s.lower()[2:]
    try:
        int(s, 16)
        return s
    except ValueError:
        return False

def generate_random_filename(length=8):
    letters = string.printable[:-38]
    return ''.join(random.choice(letters) for i in range(length))

def print_buffered(s):
    print(s, flush=True)

def help_menu():
    while True:
        print_buffered('''
1. info challenge
2. list blacklist syscall
3. lore (not related)
4. back''')
        inp = int(input("> "))
        match inp:
            case 1:
                print_buffered('''
One shellcode input through four-stage shellcode relay.
Doctor          : x86-64
Kal'tsit        : aarch64
Theresa         : riscv64
Civilight Eterna: mips64

Read each stage's secret and submit them in the "authentication sequence". Generate the simulation once you have all four secrets!
====================
| START_SIMULATION |
====================
|
| [*] Build Order: Doctor -> Kal'tsit -> Theresa -> Civilight Eterna
| ... snippet ...
| 
| Doctor          : oracle
| Kal'tsit        : ama-10
| Theresa         : king_sarkaz
| Civilight Eterna: DWDB-221E
| ... snippet ...
| 
| [?] Enter authentication sequence: oracleama-10king_sarkazDWDB-221E
| 
| [+] Access Granted. Flag: FINDIT{TEST_FLAG}
|
==================
| END_SIMULATION |
==================
''')
            case 2:
                print_buffered('''
Doctor          : 41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,288,299,307,322,78,217
Kal'tsit        : 198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,242,243,269,281,61
Theresa         : 198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,242,243,269,281,61
Civilight Eterna: 5040,5041,5042,5043,5044,5045,5046,5047,5048,5049,5050,5051,5052,5053,5054,5316,5217,5076
''')
            case 3:
                print_buffered('''
who inherited DWDB-221E after the Babel incident ?
''')
                inp = str(input("> ")).lower()
                if inp == 'amiya':
                    print_buffered('''- https://arknights.wiki.gg/wiki/Babel
- https://archive.ooo/c/shooow-your-shell/435/''')
                else:
                    exit(1)
            case 4:
                return

def main():
    tmp = tempfile.TemporaryDirectory()
    temp_dir = tmp.name

    def cleanup_and_exit(signum=None, frame=None):
        tmp.cleanup()
        sys.exit(0)

    # catch signals that might be sent to the python process
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    while True:
        print_buffered('''
1. Help Menu
2. Run''')
        inp = int(input("> "))
        match inp:
            case 1:
                help_menu()
            case 2:
                print_buffered("\nInitializing ...")
                break

    try:
        os.chmod(temp_dir, 0o711)
        
        characters = list(metadata.keys())
        random.shuffle(characters)
        print(f"[*] Build Order: {' -> '.join(characters)}")
        generated_keys = []
        first_member = None
        
        for char_name in characters:
            metadata[char_name]['secret_path'] = os.path.join(temp_dir, 'secret_' + generate_random_filename())
            metadata[char_name]['runner_path'] = os.path.join(temp_dir, 'runner_' + generate_random_filename())
            metadata[char_name]['wrapper_path'] = os.path.join(temp_dir, generate_random_filename())
            
                
        for idx, char_name in enumerate(characters):
            data = metadata[char_name]
            keydata = secrets.token_hex(8)
            generated_keys.append(keydata)

            secret_file = data['secret_path']
            runner_file = data['runner_path']
            wrapper_file = data['wrapper_path']

            if first_member is None:
                first_member = runner_file

            with open(secret_file, 'w') as f:
                f.write(keydata)

            # prepare optional SUID qemu copy for non-x86 arches
            qemu_copy = None
            if data['arch'] != 'x86-64':
                qemu_src = f"/usr/bin/qemu-{data['arch']}"
                qemu_copy = os.path.join(temp_dir, 'qemu_' + generate_random_filename())
                shutil.copy2(qemu_src, qemu_copy)

            # runner script
            with open(runner_file, 'w') as f:
                if data['arch'] == 'x86-64':
                    # native: run the SUID executor directly
                    f.write(f"#!/usr/bin/env bash\n{wrapper_file} <<< \"$1\"\n")
                else:
                    # cross-arch: use our SUID copy of qemu, NOT the system one
                    f.write(f"#!/usr/bin/env bash\n{qemu_copy} {wrapper_file} <<< \"$1\"\n")

            # build runner executor as before
            with open(source_file) as src, open(f"{wrapper_file}.c", 'w') as dst:
                if idx + 1 < len(characters):
                    next_runner = metadata[characters[idx + 1]]['runner_path']
                else:
                    next_runner = ""    # terminal stage: no execve target is valid
                dst.write(
                    src.read()
                    .replace('/*CHANGEME*/', f'"{next_runner}"')
                )

            compile_cmd = data['compiler'] + [
                f"{wrapper_file}.c",
                "-o", wrapper_file,
                "-lunicorn", "-latomic", "-lpthread", "-lm", "-ldl"
            ]
            result = subprocess.run(
                compile_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            os.chmod(runner_file, 0o755)

            uid = int(data['perm'])
            gid = uid

            # chown + SUID for executor, runner, secret
            os.chown(wrapper_file, uid, gid)
            # os.chown(runner_file, uid, gid)
            os.chown(secret_file, uid, gid)

            os.chmod(wrapper_file, 0o4555)
            # os.chmod(runner_file, 0o4555)
            os.chmod(runner_file, 0o555)
            os.chmod(secret_file, 0o400)

            # chown + SUID for qemu copy
            if qemu_copy is not None:
                os.chown(qemu_copy, uid, gid)
                os.chmod(qemu_copy, 0o4555)
            
            print(f"    [{char_name}] secret at {secret_file} | executor at {runner_file}")
        
        user_input = validate_hex(input("input hex: ").strip())
        if user_input:
            process = subprocess.Popen(
                ["runuser", "-u", "runner", "--", first_member, user_input],
                stdin=subprocess.DEVNULL,
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            sys.stdout.write("\n")
            sys.stdout.flush()
            if "".join(generated_keys) == input("[?] Enter authentication sequence: ").strip():
                print(f"\n[+] Access Granted. Flag: {open('/app/flag.txt').read()}")
            else:
                print(f"\n[-] Invalid Sequence!")
    finally:
        tmp.cleanup()

if __name__ == '__main__':
    main()