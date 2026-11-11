import base64
import json
import logging
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict
import urllib
import pycountry
import requests
import shutil
import telegram_sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# لیست لینک‌های Raw گیت‌هاب برای دریافت کانفیگ‌ها
GITHUB_RAW_URLS = [
    "https://github.com/0xRadikal/Free-v2ray-Configs/raw/refs/heads/main/top100.txt",
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/fast/configs.txt" ,
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/verified/configs.txt" ,
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/secure/configs.txt",
    
]

SEND_TO_TELEGRAM = os.getenv('SEND_TO_TELEGRAM', 'false').lower() == 'true'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

# تغییر نام پوشه به دلخواه خودتان (مثلا checker)
SUB_CHECKER_DIR = Path("checker")

def full_unquote(s: str) -> str:
    if '%' not in s:
        return s
    prev_s = ""
    while s != prev_s:
        prev_s = s
        s = urllib.parse.unquote(s)
    return s

def clean_previous_configs(configs: List[str]) -> List[str]:
    cleaned_configs = []
    for config in configs:
        try:
            if '#' in config:
                base_uri, tag = config.split('#', 1)
                decoded_tag = full_unquote(tag)
                cleaned_tag = re.sub(r'::[A-Z]{2}$', '', decoded_tag).strip()
                if cleaned_tag:
                    final_config = f"{base_uri}#{cleaned_tag}"
                else:
                    final_config = base_uri
                cleaned_configs.append(final_config)
            else:
                cleaned_configs.append(config)
        except Exception as e:
            logging.warning(f"Could not clean config, adding original: {config[:50]}... Error: {e}")
            cleaned_configs.append(config)
    return cleaned_configs

def fetch_configs_from_github_raw(url: str) -> List[str]:
    configs = []
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        content = response.text.strip()

        decoded_content = content
        try:
            if not any(proto in content for proto in ["vless://", "vmess://", "ss://", "trojan://", "hy2://", "hysteria2://"]):
                padding = '=' * (-len(content) % 4)
                decoded_bytes = base64.b64decode(content + padding)
                decoded_content = decoded_bytes.decode('utf-8', errors='ignore')
        except Exception:
            pass

        pattern = r'((?:vmess|vless|ss|hy2|trojan|hysteria2)://[^\s<>"\'`]+)'
        found_configs = re.findall(pattern, decoded_content)

        for config in found_configs:
            configs.append(config.strip())

        logging.info(f"Fetched {len(configs)} configs from {url}")
        return configs
    except Exception as e:
        logging.error(f"Could not fetch or parse GitHub raw {url}: {e}")
        return []

def run_sub_checker(input_configs: List[str]) -> List[str]:
    if not SUB_CHECKER_DIR.is_dir():
        logging.error(f"Checker directory not found at '{SUB_CHECKER_DIR}'")
        return []

    normal_txt_path = SUB_CHECKER_DIR / "normal.txt"
    final_txt_path = SUB_CHECKER_DIR / "final.txt"
    # نام فایل اجرایی داخلی را هم می‌توانید تغییر دهید (مثلا check.py)
    cl_py_path = SUB_CHECKER_DIR / "check.py"

    logging.info(f"Writing {len(input_configs)} configs to '{normal_txt_path}'")
    normal_txt_path.write_text("\n".join(input_configs), encoding="utf-8")

    logging.info("Running checker script (check.py)...")
    try:
        process = subprocess.run(
            ["python", cl_py_path.name],
            cwd=SUB_CHECKER_DIR,
            capture_output=True,
            text=True,
            timeout=3600
        )
        logging.info("Checker stdout:\n" + process.stdout)
        if process.stderr:
            logging.error("Checker stderr:\n" + process.stderr)

        if process.returncode != 0:
            logging.error("Checker script failed to execute properly.")
            return []

        if final_txt_path.exists():
            logging.info("Reading checked configs from 'final.txt'")
            checked_configs = final_txt_path.read_text(encoding="utf-8").splitlines()
            return [line for line in checked_configs if line.strip()]
        else:
            logging.error("'final.txt' was not created by the checker.")
            return []

    except subprocess.TimeoutExpired:
        logging.error("Checker script timed out.")
        return []
    except Exception as e:
        logging.error(f"An error occurred while running checker: {e}")
        return []

def process_and_save_results(checked_configs: List[str]) -> Dict[str, int]:
    if not checked_configs:
        logging.warning("No checked configs to process.")
        return {}

    loc_dir = Path("loc")
    mix_dir = Path("mix")

    if loc_dir.is_dir():
        try:
            shutil.rmtree(loc_dir)
        except OSError as e:
            logging.error(f"Error removing directory {loc_dir}: {e}")

    loc_dir.mkdir(exist_ok=True)
    mix_dir.mkdir(exist_ok=True)

    configs_by_protocol = {
        "vless": [], "vmess": [], "ss": [], "trojan": [], "hy2": []
    }
    configs_by_location = {}

    for config in checked_configs:
        if config.startswith(("hysteria://", "hysteria2://", "hy2://")):
            configs_by_protocol["hy2"].append(config)
        elif config.startswith("vless://"):
            configs_by_protocol["vless"].append(config)
        elif config.startswith("vmess://"):
            configs_by_protocol["vmess"].append(config)
        elif config.startswith("ss://"):
            configs_by_protocol["ss"].append(config)
        elif config.startswith("trojan://"):
            configs_by_protocol["trojan"].append(config)

        location_code = "XX"
        try:
            decoded_config = urllib.parse.unquote(config)
            match = re.search(r'::([A-Za-z]{2})$', decoded_config)
            if match:
                location_code = match.group(1).upper()
        except Exception:
            pass

        if location_code not in configs_by_location:
            configs_by_location[location_code] = []
        configs_by_location[location_code].append(config)

    for proto, configs in configs_by_protocol.items():
        if configs:
            file_path = Path(f"{proto}.txt")
            file_path.write_text("\n".join(configs), encoding="utf-8")
            logging.info(f"Saved {len(configs)} configs to '{file_path}'")

    Path("mix/sub.txt").write_text("\n".join(checked_configs), encoding="utf-8")
    logging.info(f"Saved {len(checked_configs)} configs to 'mix/sub.txt'")

    for loc_code, configs in configs_by_location.items():
        country_flag = "❓"
        try:
            country = pycountry.countries.get(alpha_2=loc_code)
            if country and hasattr(country, 'flag'):
                country_flag = country.flag
        except Exception:
            pass

        file_path = Path("loc") / f"{loc_code} {country_flag}.txt"
        file_path.write_text("\n".join(configs), encoding="utf-8")
        logging.info(f"Saved {len(configs)} configs for location {loc_code} to '{file_path}'")

    protocol_counts = {proto: len(configs) for proto, configs in configs_by_protocol.items()}
    logging.info(f"Final protocol counts: {protocol_counts}")
    return protocol_counts

def main():
    logging.info("--- Starting V2Ray Extractor with Custom Checker ---")

    logging.info("Step 1: Fetching configs from GitHub Raw URLs...")
    all_raw_configs = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(fetch_configs_from_github_raw, url): url for url in GITHUB_RAW_URLS}
        for future in future_to_url:
            all_raw_configs.extend(future.result())

    unique_new_configs = sorted(list(set(all_raw_configs)))
    logging.info(f"Collected {len(unique_new_configs)} unique new configs from GitHub.")

    logging.info("Step 2: Reading previous cache with 8-hour TTL check...")
    previous_configs = []
    previous_mix_file = Path("mix/sub.txt")
    
    if previous_mix_file.is_file():
        try:
            file_age_seconds = time.time() - previous_mix_file.stat().st_mtime
            max_age_seconds = 8 * 3600  # 8 hours

            if file_age_seconds > max_age_seconds:
                logging.info(f"Previous cache older than 8 hours. Discarding.")
                previous_mix_file.unlink(missing_ok=True)
            else:
                previous_configs = previous_mix_file.read_text(encoding="utf-8").splitlines()
                previous_configs = [line.strip() for line in previous_configs if '://' in line]
                previous_configs = clean_previous_configs(previous_configs)
                logging.info(f"Successfully loaded {len(previous_configs)} valid previous configs.")
        except Exception as e:
            logging.error(f"Cache read error: {e}")
    else:
        logging.info("No previous cache found.")

    logging.info("Step 3: Merging new and previous configs...")
    combined_configs = unique_new_configs + previous_configs
    unique_combined_configs = sorted(list(set(combined_configs)))
    logging.info(f"Total unique configs to be tested: {len(unique_combined_configs)}")

    if not unique_combined_configs:
        logging.warning("No configs to check. Exiting.")
        return

    logging.info("Step 4: Running the checker...")
    checked_configs = run_sub_checker(unique_combined_configs)
    logging.info(f"Checker returned {len(checked_configs)} valid configs.")

    logging.info("Step 5: Processing and saving results...")
    protocol_counts = process_and_save_results(checked_configs)
    
    # بخش ارسال به تلگرام
    if SEND_TO_TELEGRAM:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_CHANNEL_ID:
            try:
                bot = telegram_sender.init_bot(TELEGRAM_BOT_TOKEN)
                if bot:
                   # telegram_sender.send_summary_message(bot, TELEGRAM_CHANNEL_ID, protocol_counts)
                    telegram_sender.send_all_grouped_configs(bot, TELEGRAM_CHANNEL_ID, checked_configs, chunk_size=10)
                    logging.info("Telegram notifications sent successfully.")
            except Exception as e:
                logging.error(f"Telegram error: {e}")
        else:
            logging.warning("Telegram credentials missing.")

    logging.info("--- Process finished successfully! ---")

if __name__ == "__main__":
    main()
