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
            
            try:
                line = await process.stdout.readline()
            except Exception:
                break
                
            if not line:
                print("\n[!] M0scan Subprocess exited or crashed.")
                process = None
                break
                
            clean_text = clean_ansi(line.decode('utf-8', errors='ignore'))
            if not clean_text: continue
            
            # ⚡ TURN ON THE LIGHTS: Print EVERYTHING to the Termux screen so we can see errors
            print(f"[M0scan] {clean_text}")
            
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
        try:
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")
                
                if action == "launch_engine":
                    if not os.path.exists(TOKEN_FILE):
                        await websocket.send(json.dumps({"type": "scene", "name": "pin_entry"}))
                    else:
                        print("[*] Token Found. Booting M0scan...")
                        process = await asyncio.create_subprocess_shell(
                            "/data/data/com.termux/files/usr/bin/M0scan", 
                            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                        )
                        
                elif action == "user_input":
                    if not process:
                        pin = str(data.get("data")).strip()
                        # ⚡ FIX: Added the \n newline character to exactly match your bash script format
                        with open(TOKEN_FILE, "w") as f:
                            f.write(pin + "0\n") 
                        print(f"[*] PIN '{pin}' Injected. Launching M0scan...")
                        process = await asyncio.create_subprocess_shell(
                            "/data/data/com.termux/files/usr/bin/M0scan", 
                            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                        )
                    else:
                        process.stdin.write((str(data.get("data")) + "\n").encode())
                        await process.stdin.drain()
                        
                elif action == "batch_input":
                    if process:
                        for val in data.get("data", []):
                            process.stdin.write((str(val) + "\n").encode())
                            await process.stdin.drain()
        except websockets.exceptions.ConnectionClosed:
            print("[*] DeoVex App Disconnected.")
        except ConnectionResetError:
            print("\n[!] Error: Lost connection to M0scan. It may have crashed.")
        except Exception as e:
            print(f"[!] Bridge Error: {e}")

    await asyncio.gather(read_termux_output(), read_app_input())

async def main():
    async with websockets.serve(bridge_server, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
