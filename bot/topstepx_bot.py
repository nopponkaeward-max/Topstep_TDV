#!/usr/bin/env python3
"""รับ Webhook จาก TradingView (Renko Engulf, โหมด "TopstepX Clicker") แล้วกดคีย์ลัด Buy/Sell บน TopstepX

  python3 topstepx_bot.py run            # เริ่มรับสัญญาณ
  python3 topstepx_bot.py test buy       # ทดสอบกดคีย์ buy | sell | close (ตาม dry_run)

กดคีย์ลัด 1 ครั้งต่อสัญญาณใส่หน้าต่างที่โฟกัสอยู่ (จำนวนสัญญาตั้งไว้ใน TopstepX แล้ว)
ไม่ใช้ API ไม่ตรวจสถานะบัญชี: Indicator สั่งอะไร บอทกดตามนั้น
"""
import hmac
import json
import platform
import queue
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
LOG_PATH = HERE / "bot.log"
ACTIONS = ("buy", "sell", "close")   # close = กดคีย์ Close Position (ปิดแล้วซ้ำได้ ถ้า flat อยู่แล้วไม่เกิดอะไร)

# คีย์ลัดแนะนำ (ต้องตั้งในหน้า Hotkeys ของ TopstepX ให้ตรงกัน): Windows = Ctrl+Alt+..., macOS = Control+Shift+...
# buy/sell = Buy/Sell Market, close = Close Position, flatten_all = Flatten All, cancel_all = Cancel All
# คำสั่งออก (action "close") กดคีย์ตาม `exit_key` ใน config: "close" (ค่าเริ่มต้น ปิดสถานะ) หรือ "flatten_all" แล้วตามด้วย cancel_all
DEFAULT_HOTKEYS = {
    "Windows": {"buy": ["ctrl", "alt", "b"], "sell": ["ctrl", "alt", "s"], "close": ["ctrl", "alt", "c"], "flatten_all": ["ctrl", "alt", "f"], "cancel_all": ["ctrl", "alt", "x"]},
    "Darwin": {"buy": ["ctrl", "shift", "b"], "sell": ["ctrl", "shift", "s"], "close": ["ctrl", "shift", "c"], "flatten_all": ["ctrl", "shift", "f"], "cancel_all": ["ctrl", "shift", "x"]},
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
    defaults = DEFAULT_HOTKEYS.get(platform.system(), DEFAULT_HOTKEYS["Windows"])
    cfg["hotkeys"] = {**defaults, **cfg.get("hotkeys", {})}   # ค่าที่ไม่ได้ใส่ใน config ใช้ค่าแนะนำ
    return cfg


def gui():
    import pyautogui  # import ตอนใช้ จะได้ตรวจโค้ดบนเครื่องไม่มีจอได้

    pyautogui.FAILSAFE = True  # ลากเมาส์ไปมุมซ้ายบนของจอ = หยุดฉุกเฉิน
    pyautogui.PAUSE = 0  # ค่าเริ่มต้น 0.1 วินาทีต่อคำสั่ง ทำให้ช้า (กดคีย์ 6 คำสั่ง = เสีย ~0.3-0.6 วินาที)
    return pyautogui


def press(cfg, name):
    keys = cfg["hotkeys"][name]
    gui_ = gui()
    # กดทีละปุ่มแล้วค้างไว้สั้นๆ แทน hotkey() ที่กด-ปล่อยเร็วจนเว็บบางตัวจับคีย์ไม่ทัน
    hold = cfg.get("key_hold_seconds", 0.04)
    pressed = []
    try:
        for k in keys:
            gui_.keyDown(k)
            pressed.append(k)
        time.sleep(hold)
    finally:
        for k in reversed(pressed):
            gui_.keyUp(k)
    log(f"  ส่งคีย์ {'+'.join(keys)} ({name}) แล้ว (ยืนยันผลที่หน้า TopstepX เอง)")


def exit_key(cfg):
    """คีย์ที่ใช้ปิดสถานะ: close (Close Position) หรือ flatten_all (Flatten All)"""
    key = cfg.get("exit_key", "close")
    if key not in ("close", "flatten_all"):
        raise RuntimeError(f"exit_key ต้องเป็น close หรือ flatten_all (ได้ {key!r})")
    return key


def press_close(cfg):
    """ปิดสถานะ (Close Position หรือ Flatten All) แล้ว (ถ้าเปิดไว้) Cancel All เพื่อไม่ให้ SL/TP ที่ค้างเหลือเป็นคำสั่งกำพร้า"""
    press(cfg, exit_key(cfg))
    if cfg.get("cancel_after_close", True):
        time.sleep(cfg.get("cancel_delay_seconds", 0.1))
        press(cfg, "cancel_all")


def describe(cfg, action, close_first=False):
    keys = "+".join(cfg["hotkeys"][action])
    if action == "close":
        extra = f" แล้ว {'+'.join(cfg['hotkeys']['cancel_all'])} (Cancel All)" if cfg.get("cancel_after_close", True) else ""
        key = exit_key(cfg)
        return f"กดคีย์ {'+'.join(cfg['hotkeys'][key])} ({'Flatten All' if key == 'flatten_all' else 'Close Position'}){extra}"
    pre = f"{'Flatten All' if exit_key(cfg) == 'flatten_all' else 'Close Position'}{' + Cancel All' if cfg.get('cancel_after_close', True) else ''} ก่อน แล้ว" if close_first else ""
    return f"{pre}กดคีย์ {keys}"


def execute(cfg, action, event, t_recv=None, lag_ms=None, close_first=False):
    t0 = time.time()
    if lag_ms is not None:
        log(f"  (สัญญาณมาถึงบอทหลังถูกสร้างใน TradingView {lag_ms:.0f} ms)")
    if cfg.get("dry_run", True):
        log(f"[DRY RUN] {event} {action} -> จะ{describe(cfg, action, close_first)} (ยังไม่ได้กดจริง)")
        return
    log(f"{event} {action}" + (" (ปิดสถานะก่อน)" if close_first else ""))
    try:
        if close_first:
            press_close(cfg)
            time.sleep(cfg.get("cancel_delay_seconds", 0.1))
        if action == "close":
            press_close(cfg)
        else:
            press(cfg, action)
    except Exception as e:  # noqa: BLE001
        log(f"!! กดไม่สำเร็จ ({event} {action}): {e}  ตรวจสถานะบัญชีด้วยตัวเอง")
        return
    done = time.time()
    since = f" / {1000 * (done - t_recv):.0f} ms นับจากบอทรับสัญญาณ" if t_recv else ""
    log(f"  เวลาที่บอทใช้กด: {1000 * (done - t0):.0f} ms{since}")


def worker(cfg):
    while True:
        action, event, t_recv, lag_ms, close_first = jobs.get()
        execute(cfg, action, event, t_recv, lag_ms, close_first)


def signal_time_ms(data):
    """เวลาที่ Indicator สร้างสัญญาณ (มิลลิวินาที): `t` (ตัวเลข จาก alert()) หรือ `ts` (ข้อความ ISO จาก {{timenow}} ของ alertcondition)"""
    t = data.get("t")
    if isinstance(t, (int, float)):
        return float(t)
    ts = data.get("ts")
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)   # {{timenow}} เป็น UTC
        return dt.timestamp() * 1000
    return None


def validate(cfg, data, url_secret=None):
    """คืน (action, event, close_first, error)  secret รับได้จากในข้อความ (`secret`) หรือจาก Webhook URL (?secret=...)"""
    given = str(data.get("secret") or url_secret or "")
    if not hmac.compare_digest(given.encode(), str(cfg["secret"]).encode()):
        return None, None, False, "secret ไม่ถูกต้อง"
    action = str(data.get("action", "")).lower()
    if action not in ACTIONS:
        return None, None, False, f"action ไม่รู้จัก: {action!r}"
    event = str(data.get("event", "entry")).lower()
    if event not in ("entry", "exit"):
        return None, None, False, f"event ไม่รู้จัก: {event!r}"
    max_age = cfg.get("max_age_seconds", 120)
    t_ms = signal_time_ms(data)
    if max_age and t_ms is not None and abs(time.time() * 1000 - t_ms) > max_age * 1000:
        return None, None, False, f"สัญญาณเก่าเกิน {max_age}s (อายุ {abs(time.time() * 1000 - t_ms) / 1000:.0f}s) ไม่ทำ"
    sig_id = str(data.get("id", ""))
    if not sig_id:
        return None, None, False, "ไม่มี id"
    with seen_lock:
        if sig_id in seen_ids:
            return None, None, False, f"id ซ้ำ ({sig_id}) ข้าม"
        seen_ids.append(sig_id)
    close_first = data.get("close_first") is True   # ใน brick เดียวกันที่ออกแล้วกลับทิศ: ปิดสถานะก่อนแล้วค่อยเข้า (ในข้อความเดียว ลำดับไม่สลับ)
    return action, event, close_first, None


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
            data = data if isinstance(data, dict) else {}
            url_secret = (parse_qs(urlparse(self.path).query).get("secret") or [None])[0]
            action, event, close_first, err = validate(cfg, data, url_secret)
            if err:
                log(f"ปฏิเสธ: {err}")
                return self._reply(403 if "secret" in err else 202, err)
            t_sig = signal_time_ms(data)
            lag = time.time() * 1000 - t_sig if t_sig is not None else None
            jobs.put((action, event, time.time(), lag, close_first))  # ตอบ TradingView ทันที (ต้องตอบภายใน 3 วินาที)
            self._reply(200, "queued")

        def log_message(self, *args):
            pass

    return Handler


def cmd_run(cfg):
    secret = str(cfg.get("secret", ""))
    if len(secret) < 16 or secret in ("CHANGE_ME",) or secret.startswith("เปลี่ยน"):
        sys.exit("ตั้ง secret ใน config.json เป็นรหัสสุ่มอย่างน้อย 16 ตัวอักษรก่อน (ใช้ค่าเดียวกับใน Indicator)")
    log("หมายเหตุ: บอทกดคีย์ใส่หน้าต่างที่โฟกัสอยู่ตอนนั้น (ไม่ได้ตรวจหรือดึงหน้าต่าง TopstepX) "
        "ต้องให้หน้า TopstepX อยู่หน้าสุดและโฟกัสตลอดเวลาเทรด")
    try:  # อุ่นเครื่อง: import pyautogui และเรียกครั้งแรกตอนเริ่ม ไม่ให้ออเดอร์แรกช้ากว่าปกติ
        gui().position()
    except Exception as e:  # noqa: BLE001
        log(f"คำเตือน: อุ่นเครื่อง pyautogui ไม่สำเร็จ ({e})")
    threading.Thread(target=worker, args=(cfg,), daemon=True).start()
    host, port = cfg.get("host", "127.0.0.1"), cfg.get("port", 8765)
    log(f"รอ Webhook ที่ http://{host}:{port}/  dry_run={cfg.get('dry_run', True)}  hotkeys={cfg['hotkeys']}")
    ThreadingHTTPServer((host, port), make_handler(cfg)).serve_forever()


def cmd_test(cfg, action):
    if action not in ACTIONS:
        sys.exit("ใช้: test buy|sell|close")
    print("จะกดคีย์ใน 3 วินาที สลับไปหน้า TopstepX ได้เลย")
    time.sleep(3)
    execute(cfg, action, "test", time.time())


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
