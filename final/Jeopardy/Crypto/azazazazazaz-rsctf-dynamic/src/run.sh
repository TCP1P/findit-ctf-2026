#!/bin/bash
socat tcp-l:6767,reuseaddr,fork exec:"sage --python chall.py"