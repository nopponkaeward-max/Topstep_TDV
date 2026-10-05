#!/usr/bin/env python3
"""รับ Webhook จาก TradingView (Renko Engulf, โหมด "TopstepX Clicker") แล้วกดคีย์ลัด Buy/Sell บน TopstepX

  python topstepx_bot.py run             # เริ่มรับสัญญาณ
  python topstepx_bot.py test buy        # ทดสอบกดคีย์ (ตาม dry_run)

กดคีย์ลัด Buy/Sell 1 ครั้งต่อสัญญาณ (จำนวนสัญญาตั้งไว้ใน TopstepX แล้ว)
ไม่ใช้ API ไม่ตรวจสถานะบัญชี: Indicator สั่งอะไร บอทกดตามนั้น
"""
import json
import platform
import queue
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
LOG_PATH = HERE / "bot.log"
ACTIONS = ("buy", "sell")

# คีย์ลัดแนะนำ: Windows = Ctrl+Alt+B/S, macOS = Control+Shift+B/S (ดู README)
DEFAULT_HOTKEYS = {
    "Windows": {"buy": ["ctrl", "alt", "b"], "sell": ["ctrl", "alt", "s"]},
    "Darwin": {"buy": ["ctrl", "shift", "b"], "sell": ["ctrl", "shift", "s"]},
}

seen_ids = deque(maxlen=1000)
seen_lock = threading.Lock()
jobs = queue.Queue()  # คิวเดียว ทำทีละงานตามลำดับที่มาถึง (exit ก่อน entry เสมอ)


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config():
    if not CONFIG_PATH.exists():
        sys.exit("ไม่พบ bot/config.json ให้คัดลอกจาก config.example.json ก่อน")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg.setdefault("hotkeys", DEFAULT_HOTKEYS.get(platform.system(), DEFAULT_HOTKEYS["Windows"]))
    return cfg


def gui():
    import pyautogui  # import ตอนใช้ จะได้ตรวจโค้ดบนเครื่องไม่มีจอได้

    pyautogui.FAILSAFE = True  # ลากเมาส์ไปมุมซ้ายบนของจอ = หยุดฉุกเฉิน
    pyautogui.PAUSE = 0.05
    return pyautogui


def focus_window(cfg):
    """ดึงหน้าต่าง TopstepX ขึ้นมาโฟกัส คีย์ลัดทำงานเฉพาะหน้าต่างที่โฟกัส"""
    system = platform.system()
    if system == "Darwin" and cfg.get("focus_app"):
        subprocess.run(["osascript", "-e", f'tell application "{cfg["focus_app"]}" to activate'], check=False)
    elif system == "Windows" and cfg.get("focus_title"):
        import pygetwindow as gw  # pip install pygetwindow

        wins = gw.getWindowsWithTitle(cfg["focus_title"])
        if not wins:
            raise RuntimeError(f"ไม่พบหน้าต่างที่ชื่อมี '{cfg['focus_title']}'")
        if wins[0].isMinimized:
            wins[0].restore()
        wins[0].activate()
    time.sleep(cfg.get("focus_delay_seconds", 0.3))


def press(cfg, action):
    keys = cfg["hotkeys"][action]
    gui_ = gui()
    focus_window(cfg)
    # กดทีละปุ่มแล้วค้างไว้สั้นๆ แทน hotkey() ที่กด-ปล่อยเร็วจนเว็บบางตัวจับคีย์ไม่ทัน
    hold = cfg.get("key_hold_seconds", 0.1)
    pressed = []
    try:
        for k in keys:
            gui_.keyDown(k)
            pressed.append(k)
            time.sleep(0.03)
        time.sleep(hold)
    finally:
        for k in reversed(pressed):
            gui_.keyUp(k)
    log(f"  ส่งคีย์ {'+'.join(keys)} ({action}) แล้ว (ยืนยันผลที่หน้า TopstepX เอง)")


def execute(cfg, action, event):
    if cfg.get("dry_run", True):
        log(f"[DRY RUN] {event} {action} -> จะกดคีย์ {'+'.join(cfg['hotkeys'][action])} (ยังไม่ได้กดจริง)")
        return
    log(f"{event} {action}")
    try:
        press(cfg, action)
    except Exception as e:  # noqa: BLE001
        log(f"!! กดไม่สำเร็จ ({event} {action}): {e}  ตรวจสถานะบัญชีด้วยตัวเอง")


def worker(cfg):
    while True:
        action, event = jobs.get()
        execute(cfg, action, event)


def validate(cfg, data):
    """คืน (action, event, error)"""
    if data.get("secret") != cfg["secret"]:
        return None, None, "secret ไม่ถูกต้อง"
    action = str(data.get("action", "")).lower()
    if action not in ACTIONS:
        return None, None, f"action ไม่รู้จัก: {action!r}"
    event = str(data.get("event", "entry")).lower()
    if event not in ("entry", "exit"):
        return None, None, f"event ไม่รู้จัก: {event!r}"
    max_age = cfg.get("max_age_seconds", 120)
    t = data.get("t")
    if max_age and isinstance(t, (int, float)) and abs(time.time() * 1000 - t) > max_age * 1000:
        return None, None, f"สัญญาณเก่าเกิน {max_age}s (อายุ {abs(time.time() * 1000 - t) / 1000:.0f}s) ไม่ทำ"
    sig_id = str(data.get("id", ""))
    if not sig_id:
        return None, None, "ไม่มี id"
    with seen_lock:
        if sig_id in seen_ids:
            return None, None, f"id ซ้ำ ({sig_id}) ข้าม"
        seen_ids.append(sig_id)
    return action, event, None


def make_handler(cfg):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code, text):
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(text.encode())

        def do_GET(self):
            log(f"GET จาก {self.client_address[0]} (เช็กว่าเชื่อมต่อถึง)")
            self._reply(200, "ok")

        def do_POST(self):
            n = min(int(self.headers.get("Content-Length", 0)), 4096)
            body = self.rfile.read(n).decode("utf-8", "replace")
            log(f"รับ POST จาก {self.client_address[0]} ({len(body)} ตัวอักษร)")
            try:
                data = json.loads(body)
            except ValueError:
                log(f"ปฏิเสธ: ข้อความไม่ใช่ JSON: {body[:100]!r}")
                return self._reply(400, "not json")
            action, event, err = validate(cfg, data if isinstance(data, dict) else {})
            if err:
                log(f"ปฏิเสธ: {err}")
                return self._reply(403 if "secret" in err else 202, err)
            jobs.put((action, event))  # ตอบ TradingView ทันที (ต้องตอบภายใน 3 วินาที)
            self._reply(200, "queued")

        def log_message(self, *args):
            pass

    return Handler


def cmd_run(cfg):
    secret = str(cfg.get("secret", ""))
    if len(secret) < 16 or secret in ("CHANGE_ME",) or secret.startswith("เปลี่ยน"):
        sys.exit("ตั้ง secret ใน config.json เป็นรหัสสุ่มอย่างน้อย 16 ตัวอักษรก่อน (ใช้ค่าเดียวกับใน Indicator)")
    if not cfg.get("focus_app") and not cfg.get("focus_title"):
        log("คำเตือน: ไม่ได้ตั้ง focus_app/focus_title บอทจะกดคีย์ใส่หน้าต่างที่โฟกัสอยู่ตอนนั้น "
            "ถ้าไม่ใช่หน้า TopstepX คีย์จะไม่ถึงและออเดอร์ไม่ออก (แม้ log จะบอกว่าส่งคีย์แล้ว)")
    threading.Thread(target=worker, args=(cfg,), daemon=True).start()
    host, port = cfg.get("host", "127.0.0.1"), cfg.get("port", 8765)
    log(f"รอ Webhook ที่ http://{host}:{port}/  dry_run={cfg.get('dry_run', True)}  hotkeys={cfg['hotkeys']}")
    ThreadingHTTPServer((host, port), make_handler(cfg)).serve_forever()


def cmd_test(cfg, action):
    if action not in ACTIONS:
        sys.exit("ใช้: test buy|sell")
    print("จะกดใน 3 วินาที สลับไปหน้า TopstepX ได้เลย")
    time.sleep(3)
    execute(cfg, action, "test")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    cfg = load_config()
    try:
        if cmd == "run":
            cmd_run(cfg)
        elif cmd == "test" and len(sys.argv) > 2:
            cmd_test(cfg, sys.argv[2].lower())
        else:
            sys.exit(__doc__)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
