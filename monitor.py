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
from selenium.webdriver.common.keys import Keys
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
    "VƯỢT MÃ STEP 1",
    "VƯỢT MÃ STEP1",
    "VƯỢT MÃ STEP",
    "VƯỢT MÃ",
    "LẤY MÃ STEP 1",
    "LẤY MÃ STEP1",
    "STEP 1",
    "STEP1",
    "BẮT ĐẦU",
    "NHẬN MÃ"
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
    """Load proxy config từ file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"use_proxy": False, "proxy_host": "", "proxy_port": "", "proxy_type": "http", "proxy_user": "", "proxy_pass": ""}

def save_config(config):
    """Save proxy config ra file"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def test_proxy_connection(log_fn=None):
    """Test kết nối proxy có hoạt động không"""
    log = log_fn or print
    config = load_config()
    
    log(f"[*] Config hiện tại: use_proxy = {config.get('use_proxy')}, host = {config.get('proxy_host')}")
    
    if not config.get("use_proxy") or not config.get("proxy_host") or not config.get("proxy_port"):
        log("[*] Không dùng proxy hoặc config chưa đầy đủ")
        return True
    
    proxy_host = config["proxy_host"].strip()
    proxy_port = config["proxy_port"].strip()
    proxy_type = config["proxy_type"].lower()
    
    log(f"[*] Đang test kết nối {proxy_type.upper()}://{proxy_host}:{proxy_port} (timeout 8s)...")
    
    try:
        proxies = {}
        if proxy_type in ["socks4", "socks5"]:
            proxies = {"http": f"{proxy_type}://{proxy_host}:{proxy_port}", "https": f"{proxy_type}://{proxy_host}:{proxy_port}"}
        else:
            proxies = {"http": f"http://{proxy_host}:{proxy_port}", "https": f"http://{proxy_host}:{proxy_port}"}
        
        start = time.time()
        response = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=8, headers={"User-Agent": random.choice(USER_AGENTS)})
        
        if response.status_code == 200:
            log(f"[+] Proxy HOẠT ĐỘNG ({int((time.time()-start)*1000)}ms)")
            return True
        else:
            log(f"[-] Proxy lỗi status {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        log("[-] Proxy DIE (timeout 8 giây)")
        return False
    except Exception as e:
        log(f"[-] Proxy lỗi: {str(e)[:80]}")
        return False

# =================== DRIVER ===================
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
    
    # Cấu hình proxy nếu có
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
    
    # Đường dẫn Chromium trên Railway
    chrome_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium/chrome",
        "/usr/bin/google-chrome-stable"
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            options.binary_location = path
            break
    
    # Đường dẫn chromedriver
    driver_paths = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/bin/chromium-driver",
        "/usr/local/bin/chromedriver"
    ]
    
    for path in driver_paths:
        if os.path.exists(path):
            try:
                service = Service(path)
                return webdriver.Chrome(service=service, options=options)
            except:
                continue
    
    raise Exception("Chromedriver not found")

# =================== QUẢN LÝ DỮ LIỆU ===================
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

# =================== HÀM TRÍCH XUẤT ===================
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
        print("[*] Đang trích xuất domain từ ảnh bằng OCR...")
        
        images = driver.find_elements(By.XPATH, """
            //img[ancestor::*[contains(@style, 'border:red') or 
                              contains(@style, 'border:#ff') or 
                              contains(@class, 'border-red') or 
                              contains(@class, 'red-border')]]
        """)
        
        if not images:
            try:
                images = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, "img"))
                )
            except:
                images = driver.find_elements(By.TAG_NAME, "img")
        
        for img in images[:3]:
            try:
                src = img.get_attribute("src")
                if not src:
                    continue
                
                if src.startswith("data:image"):
                    base64_data = src.split(",")[1]
                    image_bytes = base64.b64decode(base64_data)
                else:
                    response = requests.get(src, timeout=5, headers={"User-Agent": random.choice(USER_AGENTS)})
                    if response.status_code != 200:
                        continue
                    image_bytes = response.content
                
                image = Image.open(io.BytesIO(image_bytes))
                text = pytesseract.image_to_string(image, lang='vie+eng')
                print(f"[*] OCR đọc được: {text[:200]}...")
                
                matches = re.findall(r'(https?://[^/\s?#]+)', text)
                for domain in matches:
                    if not any(bad in domain.lower() for bad in BLACKLIST_DOMAINS):
                        return domain
                
                matches = re.findall(r'([a-zA-Z0-9\-]+(\.[a-zA-Z]{2,})+)', text)
                for domain_match in matches:
                    domain = domain_match[0]
                    if not any(bad in domain.lower() for bad in BLACKLIST_DOMAINS):
                        return f"https://{domain}"
                        
            except Exception as e:
                continue
        
        return None
    except Exception as e:
        print(f"[-] Lỗi OCR: {e}")
        return None

# =================== KIỂM TRA UPTOLINK ===================
def check_uptolink(log_fn=None):
    log = log_fn or print
    driver = get_driver(log_fn=log)
    new_codes = []
    ignore_count = 0
    
    try:
        for i in range(10):
            if ignore_count >= 5:
                break
            
            log(f"[*] Lần {i+1}/10")
            driver.get(UPTOLINK_URL)
            time.sleep(5)
            
            url = driver.current_url
            log(f"[*] URL cuối: {url}")
            
            if is_code_expired(url):
                ignore_count += 1
                log(f"[*] Hết mã (het-ma) (lần {ignore_count})")
                continue
                
            if "linkhuongdan.online" in url:
                code = extract_code_from_url(url)
                if code and code not in new_codes:
                    new_codes.append(code)
                    log(f"[+] Phát hiện mã: {code}")
            
            time.sleep(2)
            
    except Exception as e:
        log(f"[-] Lỗi check_uptolink: {e}")
    finally:
        driver.quit()
    
    log(f"[*] Tìm thấy {len(new_codes)} mã mới")
    return new_codes

# =================== KIỂM TRA 1 MÃ ===================
def check_single_code(code, log_fn=None):
    log = log_fn or print
    driver = get_driver(log_fn=log)
    found = False
    
    try:
        log(f"\n[*] Kiểm tra mã: {code}")
        
        url = f"https://linkhuongdan.online/{code}/?qq=complete"
        driver.get(url)
        time.sleep(5)
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        target_domain = extract_domain_from_image_ocr(driver)
        if not target_domain:
            log(f"[-] Không tìm thấy domain cho mã {code}")
            return False
        
        log(f"[*] Domain: {target_domain}")
        
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(target_domain)
        time.sleep(5)
        
        log(f"[*] Đang tìm text/label VƯỢT MÃ (timeout {STEP1_TIMEOUT}s)...")
        start_time = time.time()
        
        while time.time() - start_time < STEP1_TIMEOUT:
            for i in range(8):
                driver.execute_script(f"window.scrollTo(0, {i * 400});")
                time.sleep(0.5)
                
                for pattern in BUTTON_PATTERNS:
                    try:
                        elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{pattern}')]")
                        for el in elements:
                            if el.is_displayed():
                                log(f"[+] ✅ TÌM THẤY: '{pattern}'")
                                found = True
                                break
                        if found:
                            break
                    except:
                        continue
                
                if found:
                    break
                
                for pattern in BUTTON_PATTERNS:
                    try:
                        element = WebDriverWait(driver, 1).until(
                            EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{pattern}')]"))
                        )
                        if element and element.is_displayed():
                            log(f"[+] ✅ TÌM THẤY: '{pattern}'")
                            found = True
                            break
                    except:
                        continue
                
                if found:
                    break
            
            if found:
                break
            time.sleep(1)
        
        if found:
            log(f"[+] ✅ TÌM THẤY VƯỢT MÃ cho mã {code}")
            existing = load_codes()
            existing.add(code)
            save_codes(existing)
        else:
            log(f"[-] ⏱️ Hết {STEP1_TIMEOUT}s, bỏ qua mã {code}")
        
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        
        return found
        
    except Exception as e:
        log(f"[-] Lỗi check mã {code}: {e}")
        return False
    finally:
        try:
            driver.quit()
        except:
            pass

# =================== KIỂM TRA TẤT CẢ ===================
def check_all_codes(new_codes, log_fn=None):
    """Kiểm tra tất cả mã, có thể chạy song song"""
    log = log_fn or print
    codes_with = []
    codes_without = []
    
    log(f"[*] Bắt đầu kiểm tra {len(new_codes)} mã...")
    
    # Dùng ThreadPoolExecutor để chạy song song nếu có nhiều mã
    if len(new_codes) > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def check_one(code):
            result = check_single_code(code, log_fn=log)
            return code, result
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(check_one, code): code for code in new_codes}
            for future in as_completed(futures):
                code, result = future.result()
                if result:
                    codes_with.append(code)
                else:
                    codes_without.append(code)
    else:
        # Nếu chỉ có 1 mã, check tuần tự
        for code in new_codes:
            if check_single_code(code, log_fn=log):
                codes_with.append(code)
            else:
                codes_without.append(code)
    
    log(f"[*] Kết quả: {len(codes_with)} mã có nút, {len(codes_without)} mã không có nút")
    return codes_with, codes_without