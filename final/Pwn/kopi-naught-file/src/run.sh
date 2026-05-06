#!/bin/sh
set -eu

TIMEOUT_DEVICE=30

cd /app

python3 pow.py ask 31337
if [ $? -ne 0 ]; then
  exit 1
fi

timeout --foreground "$TIMEOUT_DEVICE" qemu-system-x86_64 \
  -cpu qemu64,+smep,+smap,+umip \
  -m 128M \
  -smp 1 \
  -kernel "$PWD/bzImage" \
  -initrd "$PWD/initramfs.cpio.gz" \
  -display none \
  -serial stdio \
  -monitor none \
  -no-reboot \
  -netdev user,id=net0,dns=8.8.8.8 \
  -device virtio-net-pci,netdev=net0 \
  -append "console=ttyS0,115200n8 rdinit=/init loglevel=0 oops=panic panic=-1 page_table_check=on pti=on" \
  -drive file="$PWD/flag.txt",format=raw,if=none,id=flag,readonly=on \
  -device virtio-blk-pci,drive=flag
