import asyncio
import websockets
import json
import os
import re

async def phantom_driver(websocket, config):
    print("[*] DeoVex App connected. Engaging Phantom Driver for M0scan...")
    
    # 1. Write the app's hosts to a temporary file for M0scan to read
    hosts = config.get("hosts", [])
    with open("deovex_target.txt", "w") as f:
        for h in hosts:
            f.write(h + "\n")

    # 2. Launch your locked M0scan engine in the background
    process = await asyncio.create_subprocess_shell(
        "M0scan",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    # 3. The Auto-Responder Loop
    while True:
        line = await process.stdout.readline()
        if not line: break
        
        decoded = line.decode('utf-8', errors='ignore')
        clean_text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', decoded).strip()
        
        # --- INTERCEPT RESULTS AND SEND TO APP UI ---
        if "➔ ⇊" in clean_text:
            status_type = clean_text.split("➔")[0].strip()
            # Read the next line which contains the host info
            host_line = await process.stdout.readline()
            host_text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', host_line.decode('utf-8', errors='ignore')).strip()
            
            # Send clean JSON back to React to draw a beautiful card
            await websocket.send(json.dumps({
                "type": "scan_result",
                "status": status_type,
                "details": host_text
            }))
            continue
            
        # Send system updates to the App UI
        if "Network Carrier" in clean_text or "SCAN COMPLETED" in clean_text:
            await websocket.send(json.dumps({"type": "system_msg", "text": clean_text}))

        # --- AUTO-ANSWER THE M0scan PROMPTS ---
        if "Activation PIN" in clean_text:
            process.stdin.write(b"202614\n")
        elif "COMMAND HUB" in clean_text:
            process.stdin.write(b"1\n") # Start Execution
        elif "TARGET DIRECTORY" in clean_text:
            process.stdin.write(b"3\n") # Current Folder
        elif "SNI Host(s)" in clean_text:
            process.stdin.write(b"deovex_target.txt\n") # Inject App Hosts
        elif "SCAN MODE" in clean_text:
            process.stdin.write(str(config.get("mode", 2)).encode() + b"\n")
        elif "Enter Timeout" in clean_text:
            process.stdin.write(str(config.get("timeout", 5)).encode() + b"\n")
        elif "Enter Max Retries" in clean_text:
            process.stdin.write(str(config.get("retries", 0)).encode() + b"\n")
        elif "Enter Concurrency/Threads" in clean_text:
            process.stdin.write(str(config.get("threads", 100)).encode() + b"\n")
        elif "Enter batch size" in clean_text:
            process.stdin.write(str(config.get("batch", 100)).encode() + b"\n")
        elif "Mark Your Saved files" in clean_text:
            process.stdin.write(b"DeoVexUI\n")
        elif "DEADLOCK RECOVERY MODE" in clean_text:
            process.stdin.write(str(config.get("recovery", 1)).encode() + b"\n")

        await process.stdin.drain()

async def server_handler(websocket):
    try:
        async for message in websocket:
            data = json.loads(message)
            if data.get("action") == "start_scan": 
                await phantom_driver(websocket, data)
    except: pass

async def main():
    print("[*] M@☆0scan Phantom Bridge ONLINE. Waiting for App...")
    async with websockets.serve(server_handler, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
