import asyncio
import websockets
import json
import re
import os

def clean_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text).strip()

async def bridge_server(websocket):
    print("[*] DeoVex App Connected. Awaiting Launch Sequence...")
    process = None
    TOKEN_FILE = "/data/data/com.termux/files/home/.m0_sys.tok"

    async def read_termux_output():
        nonlocal process
        while True:
            if not process:
                await asyncio.sleep(0.1)
                continue
            line = await process.stdout.readline()
            if not line: break
            clean_text = clean_ansi(line.decode('utf-8', errors='ignore'))
            if not clean_text: continue
            
            # --- THE SCENE DIRECTOR ---
            if "COMMAND HUB" in clean_text:
                process.stdin.write(b"1\n") 
                await process.stdin.drain()
            elif "TARGET DIRECTORY" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "target_directory"}))
            elif "Unfinished Scans Detected" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "omni_vault"}))
            elif "SNI Host(s) OR hosts file" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "target_input"}))
            elif "SCAN MODE" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "scan_mode"}))
            elif "Enter Timeout" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "parameters"}))
            elif "➔ ⇊" in clean_text:
                status_type = clean_text.split("➔")[0].strip()
                host_line = await process.stdout.readline()
                await websocket.send(json.dumps({"type": "scan_result", "status": status_type, "details": clean_ansi(host_line.decode('utf-8', errors='ignore'))}))
            elif "Network Carrier" in clean_text or "SCAN COMPLETED" in clean_text:
                await websocket.send(json.dumps({"type": "telemetry", "text": clean_text}))

    async def read_app_input():
        nonlocal process
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "launch_engine":
                # ⚡ THE BYPASS: Check if authorized. If not, ask app for PIN.
                if not os.path.exists(TOKEN_FILE):
                    await websocket.send(json.dumps({"type": "scene", "name": "pin_entry"}))
                else:
                    process = await asyncio.create_subprocess_shell(
                        "M0scan", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                    )
                    
            elif action == "user_input":
                # ⚡ THE BYPASS: If process hasn't started, this input is the PIN!
                if not process:
                    pin = str(data.get("data")).strip()
                    with open(TOKEN_FILE, "w") as f:
                        f.write(pin + "0") # M0scan adds a 0 salt
                    print("[*] PIN Injected. Launching M0scan...")
                    process = await asyncio.create_subprocess_shell(
                        "M0scan", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                    )
                else:
                    process.stdin.write((str(data.get("data")) + "\n").encode())
                    await process.stdin.drain()
                    
            elif action == "batch_input":
                for val in data.get("data", []):
                    process.stdin.write((str(val) + "\n").encode())
                    await process.stdin.drain()

    await asyncio.gather(read_termux_output(), read_app_input())

async def main():
    async with websockets.serve(bridge_server, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
