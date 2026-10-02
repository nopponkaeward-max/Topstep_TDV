#!/usr/bin/env python3
"""รับสัญญาณ Buy/Sell จาก TradingView แล้วคลิกปุ่มบนหน้าจอ TopstepX บนเครื่องของคุณเอง

ใช้งาน:
  python clicker.py calibrate     # บันทึกตำแหน่งปุ่ม
  python clicker.py test buy      # ทดสอบคลิก (ตาม dry_run)
  python clicker.py run           # เริ่มรับสัญญาณ
"""
import email
import imaplib
import json
import sys
import threading
import time
from email.header import decode_header
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
ACTIONS = ("buy", "sell", "flatten")

lock = threading.Lock()
last_click = 0.0
recent = []  # เวลาคลิกย้อนหลัง ใช้จำกัดจำนวนครั้งต่อชั่วโมง


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


def perform(cfg, action):
    """คลิกปุ่มตาม action คืน (ok, ข้อความ)"""
    global last_click
    if action not in ACTIONS:
        return False, f"action ไม่รู้จัก: {action}"
    btn = cfg["buttons"].get(action)
    if not btn:
        return False, f"ยังไม่ได้ calibrate ปุ่ม {action}"

    with lock:
        now = time.time()
        if now - last_click < cfg.get("cooldown_seconds", 5):
            return False, "ข้าม: อยู่ในช่วง cooldown (กันสัญญาณซ้ำ)"
        recent[:] = [t for t in recent if now - t < 3600]
        if len(recent) >= cfg.get("max_clicks_per_hour", 20):
            return False, "ข้าม: ครบจำนวนคลิกสูงสุดต่อชั่วโมงแล้ว"

        if cfg.get("dry_run", True):
            log(f"[DRY RUN] จะคลิก {action} ที่ ({btn['x']}, {btn['y']}) แต่ไม่ได้คลิกจริง")
        else:
            pg = gui()
            click_point(pg, btn, action)
            confirm = cfg["buttons"].get(f"{action}_confirm")
            if confirm:  # ถ้า TopstepX มีหน้าต่างยืนยัน
                time.sleep(cfg.get("confirm_delay_seconds", 0.4))
                click_point(pg, confirm, f"{action} confirm")
        last_click = now
        recent.append(now)
    return True, f"ทำ {action} แล้ว"


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
            ok, msg = perform(cfg, str(data.get("action", "")).lower())
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
                    ok, text = perform(cfg, str(data.get("action", "")).lower())
                    log(text)
                seen_startup = False
                time.sleep(interval)
        except Exception as e:  # noqa: BLE001 - เชื่อมต่อใหม่เมื่อหลุด
            log(f"IMAP error: {e} ลองใหม่ใน 15s")
            time.sleep(15)


# ---------- คำสั่งช่วย ----------
def calibrate(cfg):
    pg = gui()
    cfg.setdefault("buttons", {})
    print("เปิด TopstepX ให้อยู่ตำแหน่ง/ขนาด/zoom เดียวกับตอนเทรดจริง แล้วทำตามขั้นตอน")
    names = list(ACTIONS) + [f"{a}_confirm" for a in ("buy", "sell")]
    for name in names:
        optional = name.endswith("_confirm")
        ans = input(f"\nบันทึกปุ่ม '{name}'{' (ถ้ามีหน้าต่างยืนยัน)' if optional else ''}? Enter=ใช่ / s=ข้าม: ")
        if ans.strip().lower() == "s":
            cfg["buttons"].pop(name, None)
            continue
        for i in range(5, 0, -1):
            print(f"  วางเมาส์บนปุ่ม {name} ... {i}", end="\r", flush=True)
            time.sleep(1)
        x, y = pg.position()
        cfg["buttons"][name] = {"x": x, "y": y}
        print(f"  บันทึก {name} = ({x}, {y})        ")
    save_config(cfg)
    print("\nบันทึกลง config.json แล้ว")


def test(cfg, action):
    print("จะคลิกใน 3 วินาที ย้ายหน้าต่าง TopstepX ให้พร้อม")
    time.sleep(3)
    print(perform(cfg, action)[1])


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    cfg = load_config()
    if cmd == "calibrate":
        calibrate(cfg)
    elif cmd == "test" and len(sys.argv) > 2:
        test(cfg, sys.argv[2])
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
