import asyncio
import websockets
import json
import re
import os

# The Sovereign Token Path
TOKEN_FILE = "/data/data/com.termux/files/home/.m0_sys.tok"

def clean_ansi(text):
    """Purifies raw terminal output into readable text for the React App."""
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text).strip()

async def bridge_server(websocket):
    print("[*] DeoVex Cinematic Bridge Connected. Awaiting Launch Sequence...")
    process = None

    # ====================================================
    # TASK 1: THE SCENE TRANSLATOR (Termux -> App)
    # ====================================================
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
                print("\n[!] M0scan Subprocess exited or terminated.")
                process = None
                await websocket.send(json.dumps({"type": "engine_status", "status": "offline"}))
                break
                
            clean_text = clean_ansi(line.decode('utf-8', errors='ignore'))
            if not clean_text: continue
            
            # Print to Termux for debugging visibility
            print(f"[M0scan] {clean_text}")

            # ⚡ 1. SOVEREIGN HEADER EXTRACTION (Extract Termux ID for App)
            if "Your Termux ID:" in clean_text:
                t_id = clean_text.split("Your Termux ID:")[-1].strip()
                await websocket.send(json.dumps({"type": "sys_info", "termux_id": t_id}))

            # ⚡ 2. THE LOOP CATCH (Second PIN Prompt / Invalid Token)
            elif "Activation PIN for the second time" in clean_text or "Activation PIN:" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "pin_entry", "error": "Invalid PIN. Security Lock Triggered. Try Again."}))
            
            # ⚡ 3. DRM GATEWAY
            elif "Enter Registered Name" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "drm_name"}))
            elif "Enter License Key" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "drm_key"}))
            
            # ⚡ 4. COMMAND HUB (The Menu)
            elif "COMMAND HUB" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "command_hub"}))
                
            # ⚡ 5. EXECUTION SCENES
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
            
            # ⚡ 6. LIVE HITS & TELEMETRY
            elif "➔ ⇊" in clean_text:
                status_type = clean_text.split("➔")[0].strip()
                host_line = await process.stdout.readline()
                await websocket.send(json.dumps({"type": "scan_result", "status": status_type, "details": clean_ansi(host_line.decode('utf-8', errors='ignore'))}))
            elif "Network Carrier" in clean_text or "SCAN COMPLETED" in clean_text:
                await websocket.send(json.dumps({"type": "telemetry", "text": clean_text}))

    # ====================================================
    # TASK 2: THE PHANTOM DRIVER (App -> Termux)
    # ====================================================
    async def read_app_input():
        nonlocal process
        try:
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")
                
                # 🛡️ THE ANTI-COLLISION LOCK
                if action == "launch_engine":
                    if process:
                        print("[!] Anti-Collision: Engine already running. Ignored.")
                        continue
                        
                    if not os.path.exists(TOKEN_FILE):
                        await websocket.send(json.dumps({"type": "scene", "name": "pin_entry"}))
                    else:
                        print("[*] Token Found. Booting M0scan...")
                        process = await asyncio.create_subprocess_shell(
                            "/data/data/com.termux/files/usr/bin/M0scan", 
                            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                        )
                
                # 🛡️ THE LOOP CATCHER (Bypass /dev/tty by pre-writing the token and cleanly restarting)
                elif action == "submit_pin":
                    pin = str(data.get("data")).strip()
                    
                    if process:
                        print("[*] Loop Catch: Terminating stuck engine to refresh token...")
                        try:
                            process.kill()
                            await process.wait()
                        except: pass
                        process = None

                    with open(TOKEN_FILE, "w") as f:
                        f.write(pin + "0\n") 
                    
                    print(f"[*] PIN '{pin}' Secured. Launching Engine...")
                    process = await asyncio.create_subprocess_shell(
                        "/data/data/com.termux/files/usr/bin/M0scan", 
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                    )
                        
                # 🕹️ STANDARD INTERACTIVE INPUTS
                elif action == "user_input":
                    if process:
                        process.stdin.write((str(data.get("data")) + "\n").encode())
                        await process.stdin.drain()
                        
                # 🕹️ BATCH PARAMETER INJECTION
                elif action == "batch_input":
                    if process:
                        for val in data.get("data", []):
                            process.stdin.write((str(val) + "\n").encode())
                            await process.stdin.drain()
                            
        except websockets.exceptions.ConnectionClosed:
            print("[*] DeoVex App Disconnected.")
        except ConnectionResetError:
            print("\n[!] Error: Connection to M0scan severed.")
        except Exception as e:
            print(f"[!] Bridge Error: {e}")

    await asyncio.gather(read_termux_output(), read_app_input())

async def main():
    async with websockets.serve(bridge_server, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
