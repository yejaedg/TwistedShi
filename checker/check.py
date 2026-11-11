import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

INPUT_FILE = "normal.txt"
OUTPUT_FILE = "final.txt"
TIMEOUT = 3
MAX_WORKERS = 100

def test_config(config: str) -> str:
    config = config.strip()
    if not config or "://" not in config:
        return None
    try:
        parsed = urlparse(config)
        netloc = parsed.netloc.split('@')[-1]
        if ':' in netloc:
            host, port_str = netloc.rsplit(':', 1)
            port = int(port_str.split('?')[0].split('#')[0])
            
            with socket.create_connection((host, port), timeout=TIMEOUT):
                return config
    except Exception:
        pass
    return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        configs = [line.strip() for line in f if line.strip()]

    print(f"Testing {len(configs)} configs...")
    valid_configs = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_config, cfg): cfg for cfg in configs}
        for future in as_completed(futures):
            res = future.result()
            if res:
                valid_configs.append(res)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(valid_configs) + "\n")

    print(f"Done! {len(valid_configs)} valid configs saved to {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
