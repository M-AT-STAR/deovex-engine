import asyncio
import websockets
import json
import re
import os

TOKEN_FILE = "/data/data/com.termux/files/home/.m0_sys.tok"

def clean_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text).strip()

async def bridge_server(websocket):
    print("[*] DeoVex Director's Cut Bridge Connected. Awaiting Launch Sequence...")
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
            
            print(f"[M0scan] {clean_text}")

            # ⚡ 1. SOVEREIGN HEADER
            if "Your Termux ID:" in clean_text:
                t_id = clean_text.split("Your Termux ID:")[-1].strip()
                await websocket.send(json.dumps({"type": "sys_info", "termux_id": t_id}))

            # ⚡ 2. THE LOOP CATCH
            elif "Activation PIN for the second time" in clean_text or "Activation PIN:" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "pin_entry", "error": "Invalid PIN. Security Lock Triggered. Try Again."}))
            
            # ⚡ 3. DRM GATEWAY
            elif "Enter Registered Name" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "drm_name"}))
            elif "Enter License Key" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "drm_key"}))
            
            # ⚡ 4. COMMAND HUB & EXECUTION SCENES
            elif "COMMAND HUB" in clean_text:
                await websocket.send(json.dumps({"type": "scene", "name": "command_hub"}))
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
            
            # ⚡ 5. LIVE HITS (Extracting Raw Results)
            elif "➔ ⇊" in clean_text:
                status_type = clean_text.split("➔")[0].strip()
                host_line = await process.stdout.readline()
                await websocket.send(json.dumps({"type": "scan_result", "status": status_type, "details": clean_ansi(host_line.decode('utf-8', errors='ignore'))}))
            
            # ⚡ 6. THE HUD TELEMETRY (Director's Cut Regex)
            elif "Elapsed:" in clean_text and "ETA:" in clean_text:
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
                
            elif "0Rated:" in clean_text and "Bugs:" in clean_text:
                try:
                    # Extracts: ⚡️ 361/500 | 🌐 1639/575439
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

            elif "Network Carrier" in clean_text or "SCAN COMPLETED" in clean_text:
                await websocket.send(json.dumps({"type": "telemetry", "text": clean_text}))

    async def read_app_input():
        nonlocal process
        try:
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")
                
                if action == "launch_engine":
                    if process:
                        continue
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
                        # This is how the App sends P (Pause), R (Resume), E (Exit), S (Stop)
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
            print("\n[!] Error: Connection to M0scan severed.")
        except Exception as e:
            print(f"[!] Bridge Error: {e}")

    await asyncio.gather(read_termux_output(), read_app_input())

async def main():
    async with websockets.serve(bridge_server, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
