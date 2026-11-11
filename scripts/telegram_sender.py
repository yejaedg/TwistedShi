import base64
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import List, Dict
import urllib.parse
import pytz
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY', 'arshiacomplus/V2rayExtractor')
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPOSITORY}"

MAIN_CHANNEL_ID_RAW = os.getenv('TELEGRAM_CHAT_ID', 'arshia_mod_fun').lstrip('@')
MAIN_CHANNEL_URL = f"https://t.me/{MAIN_CHANNEL_ID_RAW}"

CONFIG_CHANNEL_ID_RAW = os.getenv('TELEGRAM_CHANNEL_ID', 'v2ray_Extractor').lstrip('@')
CONFIG_CHANNEL_URL = f"https://t.me/{CONFIG_CHANNEL_ID_RAW}"

MARKUP = types.InlineKeyboardMarkup(row_width=2)
btn1 = types.InlineKeyboardButton("Github", url="https://github.com/arshiacomplus")
btn2 = types.InlineKeyboardButton("Author", url="https://t.me/arshiacomplus")
MARKUP.add(btn1, btn2)


def init_bot(token: str):
    try:
        bot = telebot.TeleBot(token)
        return bot
    except Exception as e:
        logging.error(f"Failed to initialize Telegram bot: {e}")
        return None

def full_unquote(s: str) -> str:
    if '%' not in s:
        return s

    prev_s = ""
    while s != prev_s:
        prev_s = s
        s = urllib.parse.unquote(s)
    return s

def send_summary_message(bot: telebot.TeleBot, chat_id: str, counts: Dict[str, int]):
    base_raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main"

    message = "📊 **خلاصه ساب‌لینک‌های V2rayExtractor** 📊\n\n"
    total_configs = sum(counts.values())
    message += f"تعداد کل کانفیگ‌های سالم: **{total_configs}**\n\n"

    links_map = {
        "mix": f"{base_raw_url}/mix/sub.html", "vless": f"{base_raw_url}/vless.html",
        "vmess": f"{base_raw_url}/vmess.html", "ss": f"{base_raw_url}/ss.html",
        "trojan": f"{base_raw_url}/trojan.html", "hy2": f"{base_raw_url}/hy2.html",
    }

    if total_configs > 0:
        message += f"**MIX (ALL):**\n"
        message += f"```\n{links_map['mix']}\n```\n"

    for protocol, count in counts.items():
        message += f"**{protocol.upper()}:**\n"
        message += f"```\n{links_map.get(protocol, '')}\n```\n"

    iran_tz = pytz.timezone("Asia/Tehran")
    time_ir = datetime.now(iran_tz).strftime("%Y-%m-%d %H:%M")
    message += f"\n*آخرین بروزرسانی: {time_ir}*"

    try:
        bot.send_message(chat_id, message, parse_mode='Markdown', disable_web_page_preview=True)
        logging.info("Summary message sent to Telegram.")
    except Exception as e:
        logging.error(f"Failed to send summary message to {chat_id}: {e}")

def clean_config_for_telegram(config: str) -> str:
    return re.sub(r'(#.*?)::[A-Z]{2}$', r'\1', config)

def send_with_rate_limit_handling(bot_instance, chat_id, text, reply_markup=None, parse_mode='Markdown'):
    """مدیریت ارسال پیام همراه با کنترل نرخ درخواست (Rate Limit) تلگرام"""
    while True:
        try:
            bot_instance.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            time.sleep(1)  # وقفه کوتاه برای جلوگیری از اسپم
            break
        except ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = int(e.result_json.get('parameters', {}).get('retry_after', 20))
                logging.warning(f"Rate limited by Telegram. Retrying after {retry_after + 1} seconds...")
                time.sleep(retry_after + 1)
            else:
                logging.error(f"An unhandled Telegram API error occurred: {e}")
                break
        except Exception as e:
            logging.error(f"Failed to send telegram message: {e}")
            break

def send_all_grouped_configs(bot, channel_id: str, checked_configs: List[str], chunk_size: int = 10):
    """
    تقسیم کانفیگ‌ها به دسته‌های حداکثر ۱۰ تایی و ارسال هر دسته به صورت جداگانه با دکمه و قالب شکیل
    """
    if not checked_configs:
        return

    try:
        iran_tz = pytz.timezone("Asia/Tehran")
        
        for i in range(0, len(checked_configs), chunk_size):
            chunk = checked_configs[i:i + chunk_size]
            
            # تمیزسازی و آماده‌سازی متن کانفیگ‌ها داخل بلوک کد
            cleaned_chunk = [clean_config_for_telegram(cfg) for cfg in chunk]
            configs_text = "```\n" + "\n".join(cleaned_chunk) + "\n```"
            
            time_ir = datetime.now(iran_tz).strftime("%Y-%m-%d %H:%M:%S")
            part_number = (i // chunk_size) + 1
            total_parts = (len(checked_configs) + chunk_size - 1) // chunk_size

            safe_main_channel_id = ("@" + MAIN_CHANNEL_ID_RAW).replace('__', '\\_\\_')
            safe_config_channel_id = ("@" + CONFIG_CHANNEL_ID_RAW).replace('__', '\\_\\_')

            caption = (
                f"📦 **پک کانفیگ (بخش {part_number} از {total_parts}):**\n\n"
                f"{configs_text}\n\n"
                f"⏰ Time: {time_ir}\n\n"
                f"🆔 Main Channel: [{safe_main_channel_id}]({MAIN_CHANNEL_URL})\n"
                f"🚀 Config Channel: [{safe_config_channel_id}]({CONFIG_CHANNEL_URL})"
            )

            send_with_rate_limit_handling(
                bot,
                chat_id=channel_id,
                text=caption,
                reply_markup=MARKUP,
                parse_mode='Markdown'
            )
            
        logging.info(f"All {len(checked_configs)} configs sent in chunks of {chunk_size}.")
    except Exception as e:
        logging.error(f"Error sending grouped configs: {e}")
