import asyncio
import websockets
import json
import re
import os

TOKEN_FILE = "/data/data/com.termux/files/home/.m0_sys.tok"

def clean_ansi(text):
    """Purifies raw terminal output into clean text."""
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text).strip()

async def bridge_server(websocket):
    print("[*] DeoVex Universal Remote Connected. Awaiting Launch Sequence...")
    process = None

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
            
            # Mirror to Termux for local debugging
            print(f"[M0scan] {clean_text}")

            # ==========================================
            # 1. THE SOVEREIGN IDENTITY HEADER
            # ==========================================
            if "User:" in clean_text or "HW-ID:" in clean_text or "License Valid Until:" in clean_text or "Your Termux ID:" in clean_text:
                await websocket.send(json.dumps({"type": "sys_info", "text": clean_text}))
                continue

            # ==========================================
            # 2. THE LOOP CATCH (DRM & PIN)
            # ==========================================
            if "Activation PIN for the second time" in clean_text or "Activation PIN:" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "pin_entry", "error": "Invalid PIN or Lock Triggered."}))
                continue
            elif "Enter Registered Name" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "drm_name"}))
                continue
            elif "Enter License Key" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "drm_key"}))
                continue
            
            # ==========================================
            # 3. INTERACTIVE SCENE MAPPING
            # ==========================================
            if "COMMAND HUB" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "command_hub"}))
                continue
            elif "TARGET DIRECTORY" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "target_directory"}))
                continue
            elif "Unfinished Scans Detected" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "omni_vault"}))
                continue
            elif "SNI Host(s) OR hosts file" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "target_input"}))
                continue
            elif "SCAN MODE" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "scan_mode"}))
                continue
            elif "Enter Timeout" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "parameters"}))
                continue
            elif "nano" in clean_text.lower() and "hosts" in clean_text.lower():
                await websocket.send(json.dumps({"type": "scene", "name": "editor"}))
                continue
            
            # ==========================================
            # 4. ACTIONABLE RESULTS (HITS)
            # ==========================================
            if "➔ ⇊" in clean_text or "✅" in clean_text or "🔥" in clean_text or "🚫" in clean_text or "❌" in clean_text:
                status_type = "hit" # Generic catch for frontend logic to parse
                if "➔ ⇊" in clean_text:
                    host_line = await process.stdout.readline()
                    host_details = clean_ansi(host_line.decode('utf-8', errors='ignore'))
                else:
                    host_details = clean_text
                
                await websocket.send(json.dumps({
                    "type": "scan_result", 
                    "details": host_details
                }))
                continue
            
            # ==========================================
            # 5. THE HUD TELEMETRY (Real-Time Matrix)
            # ==========================================
            if "Elapsed:" in clean_text and "ETA:" in clean_text:
                try:
                    el = re.search(r'Elapsed:\s*([\w:]+)', clean_text)
                    eta = re.search(r'ETA:\s*([\w:]+)', clean_text)
                    pshd = re.search(r'Pshd:\s*(\d+)', clean_text)
                    await websocket.send(json.dumps({
                        "type": "live_time", 
                        "elapsed": el.group(1) if el else "00s", 
                        "eta": eta.group(1) if eta else "00s", 
                        "pshd": pshd.group(1) if pshd else "0"
                    }))
                except: pass
                continue
                
            if "0Rated:" in clean_text and "Bugs:" in clean_text:
                try:
                    batch_match = re.search(r'(\d+)/(\d+)', clean_text)
                    total_match = re.search(r'\|\s*🌐\s*(\d+)/(\d+)', clean_text)
                    zr = re.search(r'0Rated:\s*(\d+)', clean_text)
                    bg = re.search(r'Bugs:\s*(\d+)', clean_text)
                    
                    await websocket.send(json.dumps({
                        "type": "live_counts",
                        "batch_prog": batch_match.group(1) if batch_match else "0",
                        "batch_size": batch_match.group(2) if batch_match else "0",
                        "scanned": total_match.group(1) if total_match else "0",
                        "total": total_match.group(2) if total_match else "0",
                        "zero": zr.group(1) if zr else "0",
                        "bugs": bg.group(1) if bg else "0"
                    }))
                except: pass
                continue

            if "SCAN COMPLETED" in clean_text:
                await websocket.send(json.dumps({"type": "telemetry", "text": "COMPLETED"}))
                continue

            # ==========================================
            # 6. THE RAW FEED FALLBACK (Guides & Errors)
            # ==========================================
            # If the text did not match any of the strict rules above, send it to the App's log console.
            await websocket.send(json.dumps({"type": "raw_feed", "text": clean_text}))

    async def read_app_input():
        nonlocal process
        try:
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")
                
                if action == "launch_engine":
                    if process: continue
                    if not os.path.exists(TOKEN_FILE):
                        await websocket.send(json.dumps({"type": "scene", "name": "pin_entry"}))
                    else:
                        process = await asyncio.create_subprocess_shell(
                            "/data/data/com.termux/files/usr/bin/M0scan", 
                            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                        )
                
                elif action == "submit_pin":
                    pin = str(data.get("data")).strip()
                    if process:
                        try:
                            process.kill()
                            await process.wait()
                        except: pass
                        process = None

                    with open(TOKEN_FILE, "w") as f:
                        f.write(pin + "0\n") 
                    
                    process = await asyncio.create_subprocess_shell(
                        "/data/data/com.termux/files/usr/bin/M0scan", 
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                    )
                        
                elif action == "user_input":
                    if process:
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
            pass
        except Exception as e:
            print(f"[!] Bridge Error: {e}")

    await asyncio.gather(read_termux_output(), read_app_input())

async def main():
    async with websockets.serve(bridge_server, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
