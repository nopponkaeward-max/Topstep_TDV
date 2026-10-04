#!/usr/bin/env python3
"""รับสัญญาณ Buy/Sell จาก TradingView แล้วคลิกปุ่มบนหน้าจอ TopstepX บนเครื่องของคุณเอง

ใช้งาน:
  python clicker.py calibrate     # (โหมด click) บันทึกตำแหน่งปุ่ม / จุดโฟกัส
  python clicker.py test buy 2    # (qty ใส่หรือไม่ก็ได้) ทดสอบกดคีย์ลัด/คลิก (ตาม dry_run)
  python clicker.py run           # เริ่มรับสัญญาณ
"""
import email
import imaplib
import json
import platform
import subprocess
import sys
import threading
import time
from email.header import decode_header
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
ACTIONS = ("buy", "sell")  # เข้า long = buy, ออก long = sell / เข้า short = sell, ออก short = buy

lock = threading.Lock()
last_by_action = {}  # เวลาล่าสุดที่ทำแต่ละ action ใช้กันสัญญาณซ้ำ (buy กับ sell แยกกัน)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def load_config():
    if not CONFIG_PATH.exists():
        sys.exit("ไม่พบ config.json ให้คัดลอกจาก config.example.json ก่อน")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def gui():
    import pyautogui  # import ตอนใช้ เพื่อให้รันเช็กสคริปต์บนเครื่องไม่มีจอได้

    pyautogui.FAILSAFE = True  # ลากเมาส์ไปมุมซ้ายบนเพื่อหยุดฉุกเฉิน
    pyautogui.PAUSE = 0.05
    return pyautogui


def click_point(pg, point, label):
    pg.moveTo(point["x"], point["y"], duration=0.1)
    pg.click()
    log(f"คลิก {label} ที่ ({point['x']}, {point['y']})")


def focus_window(cfg, pg):
    """ดึงหน้าต่างเบราว์เซอร์ที่เปิด TopstepX ขึ้นมาโฟกัส เพราะคีย์ลัดทำงานเฉพาะหน้าต่างที่โฟกัส"""
    system = platform.system()
    if system == "Darwin" and cfg.get("focus_app"):
        subprocess.run(["osascript", "-e", f'tell application "{cfg["focus_app"]}" to activate'], check=False)
    elif system == "Windows" and cfg.get("focus_title"):
        import pygetwindow as gw  # pip install pygetwindow (เฉพาะ Windows)

        wins = gw.getWindowsWithTitle(cfg["focus_title"])
        if not wins:
            raise RuntimeError(f"ไม่พบหน้าต่างที่ชื่อมี '{cfg['focus_title']}'")
        if wins[0].isMinimized:
            wins[0].restore()
        wins[0].activate()
    point = cfg.get("focus_click")  # จุดว่างที่คลิกแล้วไม่เกิดอะไร ช่วยย้ายโฟกัสออกจากช่องพิมพ์
    if point:
        pg.click(point["x"], point["y"])
    time.sleep(cfg.get("focus_delay_seconds", 0.15))


def send_hotkey(cfg, action, presses=1):
    keys = cfg.get("hotkeys", {}).get(action)
    if not keys:
        raise RuntimeError(f"ยังไม่ได้ตั้ง hotkeys.{action} ใน config.json")
    pg = gui()
    focus_window(cfg, pg)
    for i in range(presses):
        pg.hotkey(*keys)
        log(f"กดคีย์ลัด {'+'.join(keys)} ({action}) ครั้งที่ {i + 1}/{presses}")
        if i < presses - 1:
            time.sleep(cfg.get("press_delay_seconds", 0.3))


def parse_qty(cfg, qty):
    """qty จาก Alert -> (จำนวนครั้งที่ต้องกด, ข้อความ error) ถ้าไม่ส่ง qty มา กด 1 ครั้ง"""
    if qty in (None, ""):
        return 1, None
    try:
        q = float(qty)
    except (TypeError, ValueError):
        return 0, f"qty ไม่ถูกต้อง: {qty!r}"
    if q < 1 or q != int(q):
        return 0, f"qty ต้องเป็นจำนวนเต็มตั้งแต่ 1: {qty!r}"
    if q > cfg.get("max_qty", 10):
        return 0, f"ปฏิเสธ: qty={int(q)} เกิน max_qty={cfg.get('max_qty', 10)}"
    per_press = max(1, int(cfg.get("contracts_per_press", 1)))
    return -(-int(q) // per_press), None  # ปัดขึ้น


def perform(cfg, action, qty=None):
    """กดคีย์ลัด/คลิกปุ่มตาม action (ทำ qty ครั้งเมื่อกำหนด) คืน (ok, ข้อความ)"""
    if action not in ACTIONS:
        return False, f"action ไม่รู้จัก: {action}"
    presses, err = parse_qty(cfg, qty)
    if err:
        return False, err
    hotkey_mode = cfg.get("mode", "hotkey") == "hotkey"
    btn = cfg.get("buttons", {}).get(action)
    if hotkey_mode:
        if not cfg.get("hotkeys", {}).get(action):
            return False, f"ยังไม่ได้ตั้ง hotkeys.{action} ใน config.json"
    elif not btn:
        return False, f"ยังไม่ได้ calibrate ปุ่ม {action}"

    with lock:
        now = time.time()
        if now - last_by_action.get(action, 0.0) < cfg.get("cooldown_seconds", 2):
            return False, f"ข้าม: {action} ซ้ำภายใน cooldown (กันอีเมล/Webhook ส่งซ้ำ)"

        if cfg.get("dry_run", True):
            what = "+".join(cfg["hotkeys"][action]) if hotkey_mode else f"({btn['x']}, {btn['y']})"
            log(f"[DRY RUN] จะ{'กดคีย์ลัด' if hotkey_mode else 'คลิก'} {action} x{presses} -> {what} แต่ยังไม่ได้ทำจริง")
        elif hotkey_mode:
            try:
                send_hotkey(cfg, action, presses)
            except Exception as e:  # noqa: BLE001
                return False, f"กดคีย์ลัดไม่สำเร็จ: {e}"
        else:
            pg = gui()
            for i in range(presses):
                click_point(pg, btn, action)
                confirm = cfg["buttons"].get(f"{action}_confirm")
                if confirm:  # ถ้า TopstepX มีหน้าต่างยืนยัน
                    time.sleep(cfg.get("confirm_delay_seconds", 0.4))
                    click_point(pg, confirm, f"{action} confirm")
                if i < presses - 1:
                    time.sleep(cfg.get("press_delay_seconds", 0.3))
        last_by_action[action] = now
    return True, f"ทำ {action} x{presses} แล้ว"


# ---------- แหล่งสัญญาณ 1: Webhook ----------
def make_handler(cfg):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code, text):
            self.send_response(code)
            self.end_headers()
            self.wfile.write(text.encode())

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8", "replace")
            try:
                data = json.loads(body)
            except ValueError:
                return self._reply(400, "not json")
            if data.get("secret") != cfg["secret"]:
                log("ปฏิเสธ: secret ไม่ถูกต้อง")
                return self._reply(403, "forbidden")
            ok, msg = perform(cfg, str(data.get("action", "")).lower(), data.get("qty"))
            log(msg)
            self._reply(200 if ok else 202, msg)

        def log_message(self, *args):
            pass

    return Handler


def run_webhook(cfg):
    host, port = cfg.get("host", "127.0.0.1"), cfg.get("port", 8765)
    log(f"รอ Webhook ที่ http://{host}:{port}/  (dry_run={cfg.get('dry_run', True)})")
    HTTPServer((host, port), make_handler(cfg)).serve_forever()


# ---------- แหล่งสัญญาณ 2: อีเมลจาก TradingView (ไม่ต้องเปิดพอร์ต) ----------
def message_text(msg):
    parts = msg.walk() if msg.is_multipart() else [msg]
    for p in parts:
        if p.get_content_type() == "text/plain":
            payload = p.get_payload(decode=True) or b""
            return payload.decode(p.get_content_charset() or "utf-8", "replace")
    return ""


def extract_json(text):
    start = text.find("{")
    while start != -1:
        end = text.find("}", start)
        while end != -1:
            try:
                return json.loads(text[start : end + 1])
            except ValueError:
                end = text.find("}", end + 1)
        start = text.find("{", start + 1)
    return None


def run_imap(cfg):
    ic = cfg["imap"]
    interval = ic.get("poll_seconds", 5)
    log(f"ตรวจอีเมลจาก {ic['sender']} ทุก {interval}s  (dry_run={cfg.get('dry_run', True)})")
    seen_startup = True
    while True:
        try:
            m = imaplib.IMAP4_SSL(ic.get("host", "imap.gmail.com"))
            m.login(ic["user"], ic["app_password"])
            while True:
                m.select("INBOX")
                _, ids = m.search(None, "UNSEEN", "FROM", f'"{ic["sender"]}"')
                for num in ids[0].split():
                    _, raw = m.fetch(num, "(RFC822)")  # ทำเครื่องหมายอ่านแล้ว
                    msg = email.message_from_bytes(raw[0][1])
                    if seen_startup:
                        continue  # ข้ามเมลค้างเก่าตอนเริ่มโปรแกรม ไม่ให้ยิงย้อนหลัง
                    data = extract_json(message_text(msg))
                    if not data or data.get("secret") != cfg["secret"]:
                        log("ข้ามอีเมล: ไม่มี JSON หรือ secret ไม่ตรง")
                        continue
                    ok, text = perform(cfg, str(data.get("action", "")).lower(), data.get("qty"))
                    log(text)
                seen_startup = False
                time.sleep(interval)
        except Exception as e:  # noqa: BLE001 - เชื่อมต่อใหม่เมื่อหลุด
            log(f"IMAP error: {e} ลองใหม่ใน 15s")
            time.sleep(15)


# ---------- คำสั่งช่วย ----------
def record_point(pg, name):
    for i in range(5, 0, -1):
        print(f"  วางเมาส์บน {name} ... {i}", end="\r", flush=True)
        time.sleep(1)
    x, y = pg.position()
    print(f"  บันทึก {name} = ({x}, {y})        ")
    return {"x": x, "y": y}


def calibrate(cfg):
    pg = gui()
    print("เปิด TopstepX ให้อยู่ตำแหน่ง/ขนาด/zoom เดียวกับตอนเทรดจริง แล้วทำตามขั้นตอน")
    if cfg.get("mode", "hotkey") == "hotkey":
        ans = input("\nบันทึก 'focus_click' (จุดว่างบนหน้าเว็บที่คลิกแล้วไม่เกิดอะไร ใช้ย้ายโฟกัสก่อนกดคีย์ลัด)? Enter=ใช่ / s=ข้าม: ")
        if ans.strip().lower() != "s":
            cfg["focus_click"] = record_point(pg, "focus_click")
        save_config(cfg)
        print("\nบันทึกลง config.json แล้ว")
        return
    cfg.setdefault("buttons", {})
    names = list(ACTIONS) + [f"{a}_confirm" for a in ("buy", "sell")]
    for name in names:
        optional = name.endswith("_confirm")
        ans = input(f"\nบันทึกปุ่ม '{name}'{' (ถ้ามีหน้าต่างยืนยัน)' if optional else ''}? Enter=ใช่ / s=ข้าม: ")
        if ans.strip().lower() == "s":
            cfg["buttons"].pop(name, None)
            continue
        cfg["buttons"][name] = record_point(pg, name)
    save_config(cfg)
    print("\nบันทึกลง config.json แล้ว")


def test(cfg, action, qty=None):
    print("จะคลิกใน 3 วินาที ย้ายหน้าต่าง TopstepX ให้พร้อม")
    time.sleep(3)
    print(perform(cfg, action, qty)[1])


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    cfg = load_config()
    if cmd == "calibrate":
        calibrate(cfg)
    elif cmd == "test" and len(sys.argv) > 2:
        test(cfg, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "run":
        if cfg.get("source", "webhook") == "imap":
            run_imap(cfg)
        else:
            run_webhook(cfg)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
