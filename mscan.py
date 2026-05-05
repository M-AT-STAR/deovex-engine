import asyncio
import aiohttp
import websockets
import json
import time
import ssl
from urllib.parse import urlparse

# --- 1. GLOBALS & SSL CONTEXT ---
UA = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# --- 2. MASTER TIER PROBES ---
CAPTIVE_PATTERNS = {
    "vodacom": "connectu.vodacom.co.za", "mtn": "nofunds.mtn",
    "telkom": "oob.telkom", "cellc": "nofunds.cellc",
    "knect": "knectmobile", "rain": "rain.co.za/error"
}

# --- 3. THE CORE HTTP ENGINE ---
async def http_test(session, host, https=True, timeout_val=5, follow_redirects=True):
    url = f"{'https' if https else 'http'}://{host}/"
    try:
        async with session.get(url, headers={"User-Agent": UA}, timeout=timeout_val, allow_redirects=follow_redirects, ssl=False) as r:
            if not follow_redirects and r.status in [301, 302, 303, 307, 308]:
                redirect_url = r.headers.get('Location', '')
                if not redirect_url.startswith('http') and redirect_url:
                    redirect_url = f"{'https' if https else 'http'}://{host}{redirect_url}"
                await r.release()
                return r.status, str(redirect_url), ""
            body = await r.text()
            return r.status, str(r.url), body[:5000].lower()
    except Exception:
        return None, None, ""

# --- 4. RAW TCP SOCKET SNIPER ---
async def sniper_test(host, timeout_val):
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, 443, ssl=SSL_CTX, server_hostname=host), timeout=timeout_val)
        raw_payload = f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: upgrade\r\nUpgrade: websocket\r\nUser-Agent: {UA}\r\n\r\n"
        writer.write(raw_payload.encode('utf-8'))
        await writer.drain()
        response_bytes = await asyncio.wait_for(reader.read(4096), timeout=timeout_val)
        writer.close()
        await writer.wait_closed()
        
        response_str = response_bytes.decode('utf-8', errors='ignore').lower()
        first_line = response_str.split('\r\n')[0]
        status_code = int(first_line.split(' ')[1]) if 'http/' in first_line and len(first_line.split(' ')) >= 2 else None
        return status_code, response_str
    except Exception:
        return None, ""

# --- 5. THE CLASSIFIER ---
def classify(original_host, final_url, status_code, body):
    if not final_url or status_code is None:
        return "blocked", f"{original_host} (Timeout/Blocked)", None
    final_url_lower = final_url.lower()
    orig_domain = urlparse(f"http://{original_host}").netloc.split(':')[0]
    final_domain = urlparse(final_url).netloc.split(':')[0]

    if orig_domain == final_domain or orig_domain in final_domain or final_domain in orig_domain:
        return "hit", f"{original_host} - ZERO-RATED (HTTP {status_code})", None

    for c, pattern in CAPTIVE_PATTERNS.items():
        if pattern in final_url_lower or pattern in body:
            return "blocked", f"{original_host} -> {final_url} (Billed/Captive)", final_url
            
    if status_code in [200, 204, 301, 302, 400, 401, 403, 404, 500, 502, 503]:
        return "hit", f"{original_host} -> {final_url} (Zero-Rated Proxy/Redirect)", final_url

    return "blocked", f"{original_host} -> {final_url} (Unknown)", final_url

# --- 6. THE WEBSOCKET BRIDGE ---
async def scan_host(session, host, timeout_val, websocket):
    start_time = time.time()
    # Try HTTPS
    code, url, body = await http_test(session, host, https=True, timeout_val=timeout_val)
    if not code: # Try HTTP
        code, url, body = await http_test(session, host, https=False, timeout_val=timeout_val)
        
    status_type, clean_msg, redir = classify(host, url, code, body)

    # ⚡ Hidden Bug TCP Sniper Failsafe
    if status_type == "blocked":
        s_code, s_body = await sniper_test(host, 2)
        if s_code:
            hit_captive = any(p in s_body[:5000].lower() for p in CAPTIVE_PATTERNS.values())
            if not hit_captive:
                status_type = "hit"
                clean_msg = f"{host} - 🔥 HIDDEN BUG (TCP {s_code})"
                
    latency = f"{int((time.time() - start_time) * 1000)}ms"
    result_payload = {"host": host, "status": status_type, "message": clean_msg, "latency": latency}
    
    # Instantly stream result back to the App UI
    await websocket.send(json.dumps(result_payload))

async def handle_scan(websocket, payload):
    hosts = payload.get("hosts", [])
    threads = payload.get("threads", 100)
    timeout_val = payload.get("timeout", 5)
    
    connector = aiohttp.TCPConnector(limit=threads, ssl=False)
    client_timeout = aiohttp.ClientTimeout(total=timeout_val * 2)
    
    async with aiohttp.ClientSession(connector=connector, timeout=client_timeout) as session:
        tasks = []
        for host in hosts:
            if host.strip():
                tasks.append(scan_host(session, host.strip(), timeout_val, websocket))
        
        # Fire concurrent strikes
        await asyncio.gather(*tasks)
        
    await websocket.send(json.dumps({"action": "scan_complete"}))

async def server_handler(websocket):
    try:
        async for message in websocket:
            data = json.loads(message)
            if data.get("action") == "start_scan": 
                await handle_scan(websocket, data)
    except: pass

async def main():
    print("[*] M@☆0scan Headless Engine ONLINE. Waiting for DeoVex App commands...")
    async with websockets.serve(server_handler, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
