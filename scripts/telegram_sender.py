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

MARKUP = types.InlineKeyboardMarkup(row_width=1)
btn1 = types.InlineKeyboardButton("Stay Connected", url="https://t.me/DemonDungeon")

MARKUP.add(btn1)


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
            
def add_tag_to_config(config_line, tag="DemonWasHere"):
    """تگ دلخواه را با امنیت کامل به انتهای نام کانفیگ اضافه می‌کند"""
    if not isinstance(config_line, str):
        return str(config_line)
        
    config_line = config_line.strip()
    if not config_line or '://' not in config_line:
        return config_line
        
    try:
        if '#' in config_line:
            base_config, current_name = config_line.rsplit('#', 1)
            if tag in current_name:
                return config_line
            new_name = f"{current_name}-{tag}"
            return f"{base_config}#{new_name}"
        else:
            return f"{config_line}#{tag}"
    except Exception:
        return config_line


def send_all_grouped_configs(bot, channel_id, configs, chunk_size=10):
    """ارسال کانفیگ‌ها به صورت دسته‌ای همراه با تگ‌گذاری و جلوگیری از خطای متغیر"""
    if not configs:
        logging.warning("No configs to send.")
        return

    total = len(configs)
    logging.info(f"Starting to send {total} configs in chunks of {chunk_size}...")

    for i in range(0, total, chunk_size):
        chunk = configs[i:i + chunk_size]
        
        # تگ‌گذاری تک‌تک کانفیگ‌های این چانک
        tagged_chunk = [add_tag_to_config(line, "DemonWasHere") for line in chunk]
        chunk_text = "\n".join(tagged_chunk)
        
        try:
            # استفاده از channel_id که نام درست متغیر ورودی است
            bot.send_message(
                chat_id=channel_id,
                text=chunk_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            time.sleep(1.5) # تاخیر ایمن برای جلوگیری از محدودیت تلگرام (FloodWait)
      except Exception as e:
            logging.error(f"Failed to send chunk {i}: {e}")
            time.sleep(3) # اگر خطا داد کمی بیشتر صبر کند و ادامه دهد

    logging.info(f"All {total} configs processed and sent to Telegram.")
            # تمیزسازی و آماده‌سازی متن کانفیگ‌ها داخل بلوک کد
            cleaned_chunk = [clean_config_for_telegram(cfg) for cfg in chunk]
            configs_text = "```\n" + "\n".join(cleaned_chunk) + "\n```"
            
            time_ir = datetime.now(iran_tz).strftime("%Y-%m-%d %H:%M:%S")
            part_number = (i // chunk_size) + 1
            total_parts = (len(checked_configs) + chunk_size - 1) // chunk_size

            safe_main_channel_id = ("@" + MAIN_CHANNEL_ID_RAW).replace('__', '\\_\\_')
            safe_config_channel_id = ("@" + CONFIG_CHANNEL_ID_RAW).replace('__', '\\_\\_')

            caption = (
                f"📦 **Pack ( {part_number} of  {total_parts}):**\n\n"
                f"{configs_text}\n\n\n\n"
                f" Time: {time_ir}\n"
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
