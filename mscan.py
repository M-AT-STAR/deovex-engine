import asyncio
import websockets
import json
import time

async def check_host(host, timeout_ms):
    timeout_sec = timeout_ms / 1000.0
    start_time = time.time()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, 80), timeout=timeout_sec)
        writer.close()
        await writer.wait_closed()
        return {"host": host, "status": "hit", "latency": f"{int((time.time() - start_time) * 1000)}ms"}
    except Exception:
        return {"host": host, "status": "blocked", "latency": "TIMEOUT"}

async def handle_scan(websocket, payload):
    for host in payload.get("hosts", []):
        if host.strip():
            await websocket.send(json.dumps(await check_host(host.strip(), payload.get("timeout", 2000))))
    await websocket.send(json.dumps({"action": "scan_complete"}))

async def server_handler(websocket, path):
    try:
        async for message in websocket:
            data = json.loads(message)
            if data.get("action") == "start_scan": await handle_scan(websocket, data)
    except: pass

async def main():
    async with websockets.serve(server_handler, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())

