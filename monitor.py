import os
import time
import re
import json
import random
import base64
import io
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pytesseract
from PIL import Image

# =================== CONFIG ===================
UPTOLINK_URL = "https://octolink.vip/Rw9J4NBS"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

BUTTON_PATTERNS = [
    "VƯỢT MÃ STEP 1", "VƯỢT MÃ STEP1", "VƯỢT MÃ STEP", "VƯỢT MÃ",
    "LẤY MÃ STEP 1", "LẤY MÃ STEP1", "STEP 1", "STEP1", "BẮT ĐẦU", "NHẬN MÃ"
]

BLACKLIST_DOMAINS = [
    "fonts.googleapis.com", "googleapis.com", "gstatic.com",
    "google.com", "youtube.com", "cdn.tailwindcss.com",
    "cloudflare.com", "webflow.com", "amazonaws.com",
    "googlesyndication.com", "doubleclick.net"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
CODES_FILE = os.path.join(BASE_DIR, "found_codes.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STEP1_TIMEOUT = 15

# =================== PROXY CONFIG ===================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "use_proxy": False,
        "proxy_host": "",
        "proxy_port": "",
        "proxy_type": "http",
        "proxy_user": "",
        "proxy_pass": ""
    }

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# =================== DRIVER WITH PROXY ===================
def get_driver(log_fn=None):
    log = log_fn or print
    config = load_config()
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    
    # PROXY
    if config.get("use_proxy") and config.get("proxy_host") and config.get("proxy_port"):
        ph = config["proxy_host"].strip()
        pp = config["proxy_port"].strip()
        pt = config["proxy_type"].lower()
        user = config.get("proxy_user", "").strip()
        pwd = config.get("proxy_pass", "").strip()
        
        if pt in ["socks4", "socks5"]:
            proxy_str = f"{pt}://{ph}:{pp}" if not (user and pwd) else f"{pt}://{user}:{pwd}@{ph}:{pp}"
        else:
            proxy_str = f"http://{ph}:{pp}" if not (user and pwd) else f"http://{user}:{pwd}@{ph}:{pp}"
        options.add_argument(f'--proxy-server={proxy_str}')
        log(f"[*] Sử dụng {pt.upper()} proxy: {ph}:{pp}")
    
    # Chrome paths
    chrome_paths = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
    for path in chrome_paths:
        if os.path.exists(path):
            options.binary_location = path
            break
    
    driver_paths = ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver", "/usr/bin/chromium-driver"]
    for path in driver_paths:
        if os.path.exists(path):
            try:
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=options)
                return driver
            except:
                continue
    raise Exception("Chromedriver not found")

# =================== DATA FUNCTIONS ===================
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get("users", [])
        except:
            return []
    return []

def save_users(users):
    data = {"users": users, "last_update": datetime.now().isoformat()}
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_codes():
    if os.path.exists(CODES_FILE):
        try:
            with open(CODES_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f).get("codes", []))
        except:
            return set()
    return set()

def save_codes(codes):
    data = {"codes": list(codes), "last_update": datetime.now().isoformat()}
    with open(CODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =================== HELPERS ===================
def extract_code_from_url(url):
    if "het-ma" in url.lower():
        return None
    match = re.search(r'/(\d+-\d+)/?', url)
    if match:
        return match.group(1)
    match = re.search(r'/(\d+)(?:\?|$)', url)
    if match:
        return match.group(1)
    return None

def is_code_expired(url):
    return "het-ma" in url.lower()

# =================== OCR ===================
def extract_domain_from_image_ocr(driver):
    try:
        print("[*] Đang OCR...")
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            try:
                src = img.get_attribute("src")
                if not src: continue
                if src.startswith("data:image"):
                    image_bytes = base64.b64decode(src.split(",")[1])
                else:
                    response = requests.get(src, timeout=10, headers={"User-Agent": random.choice(USER_AGENTS)})
                    image_bytes = response.content
                image = Image.open(io.BytesIO(image_bytes))
                text = pytesseract.image_to_string(image, lang='vie+eng')
                matches = re.findall(r'(https?://[^/\s?#]+)', text)
                for domain in matches:
                    if not any(bad in domain.lower() for bad in BLACKLIST_DOMAINS):
                        return domain
            except:
                continue
        return None
    except:
        return None

# =================== MAIN FUNCTIONS ===================
def check_uptolink(log_fn=None):
    log = log_fn or print
    driver = get_driver(log)
    new_codes = []
    try:
        for i in range(10):
            log(f"[*] Lần {i+1}/10 - Mở link gốc")
            driver.get(UPTOLINK_URL)
            time.sleep(5)
            url = driver.current_url
            if "linkhuongdan.online" in url:
                code = extract_code_from_url(url)
                if code and code not in new_codes:
                    new_codes.append(code)
                    log(f"[+] Phát hiện mã: {code}")
    except Exception as e:
        log(f"[-] Lỗi: {e}")
    finally:
        driver.quit()
    return new_codes

def check_single_code(code, log_fn=None):
    log = log_fn or print
    driver = get_driver(log)
    found = False
    try:
        url = f"https://linkhuongdan.online/{code}/?qq=complete"
        driver.get(url)
        time.sleep(5)
        target_domain = extract_domain_from_image_ocr(driver)
        if not target_domain:
            return False
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(target_domain)
        time.sleep(5)
        # Tìm nút
        start_time = time.time()
        while time.time() - start_time < STEP1_TIMEOUT:
            for pattern in BUTTON_PATTERNS:
                try:
                    el = driver.find_element(By.XPATH, f"//*[contains(text(), '{pattern}')]")
                    if el.is_displayed():
                        found = True
                        break
                except:
                    continue
            if found: break
            time.sleep(1)
        if found:
            log(f"[+] Mã {code} CÓ NÚT")
            existing = load_codes()
            existing.add(code)
            save_codes(existing)
        return found
    except Exception as e:
        log(f"[!] Lỗi check {code}: {e}")
        return False
    finally:
        driver.quit()

def check_all_codes(new_codes, log_fn=None):
    log = log_fn or print
    codes_with = []
    codes_without = []
    for i, code in enumerate(new_codes, 1):
        log(f"[*] Kiểm tra mã {i}/{len(new_codes)}: {code}")
        if check_single_code(code, log_fn=log):
            codes_with.append(code)
        else:
            codes_without.append(code)
    return codes_with, codes_without
