import asyncio
import websockets
import json
import re
import sys

# ⚡ V76.25 ANSI Purifier: Strips terminal color codes to read raw engine logic
def clean_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text).strip()

async def bridge_server(websocket):
    print("[*] DeoVex App Connected. Awaiting Launch Sequence...")
    process = None

    # Task 1: Read EXACT output from M0scan and translate it to UI Scenes
    async def read_termux_output():
        nonlocal process
        while True:
            if not process:
                await asyncio.sleep(0.1)
                continue
                
            line = await process.stdout.readline()
            if not line: break
            
            raw_text = line.decode('utf-8', errors='ignore')
            clean_text = clean_ansi(raw_text)
            if not clean_text: continue
            
            # --- THE SCENE DIRECTOR LOGIC ---
            if "Activation PIN" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "pin_entry"}))
            elif "COMMAND HUB" in clean_text:
                process.stdin.write(b"1\n") # Auto-bypass Hub directly into Execution
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
            
            # --- LIVE HIT INTERCEPTION ---
            elif "➔ ⇊" in clean_text:
                status_type = clean_text.split("➔")[0].strip()
                host_line = await process.stdout.readline()
                host_text = clean_ansi(host_line.decode('utf-8', errors='ignore'))
                await websocket.send(json.dumps({"type": "scan_result", "status": status_type, "details": host_text}))
            
            # --- SYSTEM TELEMETRY (Network/Time) ---
            elif "Network Carrier" in clean_text or "SCAN COMPLETED" in clean_text:
                await websocket.send(json.dumps({"type": "telemetry", "text": clean_text}))

    # Task 2: Listen to App UI inputs and feed them into M0scan's stdin
    async def read_app_input():
        nonlocal process
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "launch_engine":
                print("[*] Launching M0scan Subprocess...")
                # We execute your locked M0scan globally
                process = await asyncio.create_subprocess_shell(
                    "M0scan",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
            
            elif action == "user_input":
                # Single input (e.g. Folder number, PIN, Mode)
                val = str(data.get("data")) + "\n"
                process.stdin.write(val.encode())
                await process.stdin.drain()
                
            elif action == "batch_input":
                # Parameter grid injection (Timeout -> Retries -> Threads -> Batch -> FileMark -> Recovery)
                for val in data.get("data", []):
                    process.stdin.write((str(val) + "\n").encode())
                    await process.stdin.drain()

    await asyncio.gather(read_termux_output(), read_app_input())

async def main():
    print("[*] Termux@DeoVex Bridge ONLINE. Port 8765 SECURED.")
    async with websockets.serve(bridge_server, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())

