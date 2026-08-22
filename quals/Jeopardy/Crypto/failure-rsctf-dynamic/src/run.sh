#!/bin/sh
socat tcp-l:8999,reuseaddr,fork exec:"python3 chall.py"