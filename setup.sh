#!/bin/bash
clear
echo "[*] Initializing DeoVex Termux Engine..."
pkg update -y > /dev/null 2>&1
pkg install python -y > /dev/null 2>&1
pip install websockets > /dev/null 2>&1
echo "[*] Downloading M@☆0scan Core..."
curl -sO https://raw.githubusercontent.com/M-AT-STAR/deovex-engine/main/mscan.py
clear
echo "[+] DeoVex Engine ONLINE."
echo "[+] Return to the DeoVex App to start scanning."
python mscan.py

