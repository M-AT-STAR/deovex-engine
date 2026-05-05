import asyncio
import websockets
import json
import re
import os
import signal
import sys

TOKEN_FILE = "/data/data/com.termux/files/home/.m0_sys.tok"

def clean_ansi(text):
    """Purifies raw terminal output into clean text for state matching."""
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text).strip()

async def bridge_server(websocket):
    print("[*] DeoVex Unleashed Bridge Connected. Awaiting Launch Sequence...")
    process = None

    async def read_termux_output():
        nonlocal process
        while True:
            if not process:
                await asyncio.sleep(0.1)
                continue
            
            try:
                raw_line = await process.stdout.readline()
            except Exception:
                break
                
            if not raw_line:
                print("\n[!] M0scan Subprocess exited or terminated.")
                process = None
                await websocket.send(json.dumps({"type": "engine_status", "status": "offline"}))
                break
            
            # Decode the raw line, preserving ANSI color codes for the App's RawFeedConsole
            raw_text = raw_line.decode('utf-8', errors='ignore')
            clean_text = clean_ansi(raw_text)
            
            if not clean_text: continue
            
            # Mirror the exact colored output to the local Termux screen
            sys.stdout.write(raw_text)
            sys.stdout.flush()

            # ==========================================
            # 1. THE SOVEREIGN IDENTITY EXTRACTION
            # ==========================================
            if "[User]" in clean_text or "User:" in clean_text:
                val = clean_text.split(":")[-1].replace("VERIFIED (", "").replace(")", "").strip()
                await websocket.send(json.dumps({"type": "sys_info", "key": "user", "val": val}))
                continue
            if "[HW-ID]" in clean_text or "HW-ID:" in clean_text:
                await websocket.send(json.dumps({"type": "sys_info", "key": "hw_id", "val": clean_text.split(":")[-1].strip()}))
                continue
            if "[License" in clean_text or "License" in clean_text:
                await websocket.send(json.dumps({"type": "sys_info", "key": "license", "val": clean_text.split(":")[-1].strip()}))
                continue
            if "Your Termux ID:" in clean_text:
                await websocket.send(json.dumps({"type": "sys_info", "key": "termux_id", "val": clean_text.split(":")[-1].strip()}))
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
                status_type = "hit"
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
            # 6. THE RAW FEED FALLBACK (ANSI PRESERVED)
            # ==========================================
            # Sends raw terminal colors to the App's System Console
            await websocket.send(json.dumps({"type": "raw_feed", "text": raw_text}))

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
                
                # ⚡ THE HARDWARE INTERRUPT (CTRL+C)
                elif action == "interrupt":
                    if process:
                        print("[*] Received SIGINT (Ctrl+C) from App. Halting engine...")
                        try:
                            os.kill(process.pid, signal.SIGINT)
                        except Exception as e:
                            print(f"[!] Interrupt failed: {e}")

                # ⚡ STANDARD KEYBOARD INPUT
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

