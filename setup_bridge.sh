#!/bin/bash
# ---------------------------------------------------
# DEOVEX WIZARD - BRIDGE INSTALLER & GLOBAL COMMAND
# ---------------------------------------------------

# ⚡ THE FIX: Force Termux to the Home directory first
cd /data/data/com.termux/files/home/ || exit

HOME_DIR="/data/data/com.termux/files/home"
BIN_DIR="/data/data/com.termux/files/usr/bin"

clear
echo -e "\e[96m[*] Synthesizing Termux@DeoVex Bridge...\e[0m"

pkg update -y > /dev/null 2>&1
pkg install python -y > /dev/null 2>&1
pip install websockets > /dev/null 2>&1

echo -e "\e[96m[*] Securing Relay Protocol...\e[0m"
# ⚡ THE FIX: Explicitly download the bridge straight into the home folder
curl -sL "https://raw.githubusercontent.com/M-AT-STAR/deovex-engine/main/deovex_bridge.py" -o "$HOME_DIR/deovex_bridge.py"

cat << 'EOF' > "$BIN_DIR/Termux@DeoVex"
#!/bin/bash
clear
echo -e "\e[96m      👑 DEOVEX SOVEREIGN BRIDGE 👑      \e[0m"
echo -e "\e[96m      ✦ Awaiting App Connection... ✦      \e[0m"
cd /data/data/com.termux/files/home || exit
python deovex_bridge.py
EOF

chmod +x "$BIN_DIR/Termux@DeoVex"

clear
echo -e "\e[92m[+] DEOVEX BRIDGE ONLINE & SECURED.\e[0m"
echo -e "\e[93m[!] From now on, simply type 'Termux@DeoVex' in Termux to wake the engine.\e[0m"
echo -e "\e[96m[-] Launching bridge now...\e[0m"
Termux@DeoVex
