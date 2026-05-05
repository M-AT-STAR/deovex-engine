import asyncio
import websockets
import sys
import os
import json
import subprocess

# This bridge acts as a 'Virtual Screen' for your M@☆0scan
async def bridge_handler(websocket):
    print("[*] DeoVex App Linked. Mirroring M@☆ Sovereign Engine...")
    
    # We launch your REAL script as a subprocess
    # This allows the app to see EXACTLY what Termux sees
    cmd = ["python3", "M@☆0scan$01$Apr28SYNC2.py"]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        stdin=asyncio.subprocess.PIPE
    )

    # Task to stream Termux OUTPUT -> App
    async def stream_output():
        while True:
            line = await process.stdout.readline()
            if not line: break
            # Send the raw colored terminal text to the app
            await websocket.send(json.dumps({
                "type": "terminal_output",
                "data": line.decode('utf-8', errors='ignore')
            }))

    # Task to stream App INPUT -> Termux
    async def stream_input():
        async for message in websocket:
            data = json.loads(message)
            if data.get("type") == "terminal_input":
                process.stdin.write(data.get("data").encode() + b"\n")
                await process.stdin.drain()

    await asyncio.gather(stream_output(), stream_input())

async def main():
    async with websockets.serve(bridge_handler, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())

