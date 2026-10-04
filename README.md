# TopstepX Clicker: Renko Engulf (TradingView) → กดคีย์ลัด Buy/Sell บน TopstepX

บอทรันบน PC/Mac ของคุณ รับ Webhook จาก TradingView แล้ว **กดคีย์ลัด Buy/Sell Market ในหน้า TopstepX** ไม่ใช้ API ไม่ผ่านบริการตัวกลาง และ **ไม่ตรวจสถานะบัญชี** Indicator สั่งอะไร บอทกดตามนั้น

```
Indicator (Renko Engulf) → alert() JSON → Webhook (อุโมงค์ HTTPS) → bot/topstepx_bot.py → กดคีย์ลัดบน TopstepX
```

## ไฟล์
- `pine/renko_engulf_v6.pine` Indicator ที่เพิ่มโหมด `TopstepX Clicker` (ต้นฉบับ: `renko_engulf_v6.pine` ที่ใช้บนกราฟ Renko ของ TradingView)
- `bot/topstepx_bot.py` บอท, `bot/config.example.json` ตัวอย่างค่าตั้ง

## กติกาสัญญาณ
`Last Bull/Bear` ถูกบังคับปิดในโหมดนี้ (ใช้ `Immediate previous bar` เสมอ) และบังคับถือครั้งละ 1 ออเดอร์ ทำให้ 1 brick เกิดเหตุการณ์ได้อย่างมาก 1 อย่าง ไม่มีการกลับทิศใน brick เดียว

| เหตุการณ์ใน Indicator | บอทกด |
|---|---|
| เข้า long | Buy 1 ครั้ง |
| ออก long (เจอ brick ขาลง) | Sell 1 ครั้ง |
| เข้า short | Sell 1 ครั้ง |
| ออก short (เจอ brick ขาขึ้น) | Buy 1 ครั้ง |

บอทกด **1 ครั้งต่อสัญญาณ** จำนวนสัญญาตั้งไว้ใน TopstepX แล้ว (ไม่มี qty ใน Indicator/บอท) เข้า-ออกใช้ขนาดเดียวกัน จึงปิดสถานะพอดี

ข้อความที่ Indicator ส่ง (`action` คือปุ่มที่ต้องกดจริงอยู่แล้ว):
```json
{"secret":"...","t":1759560000000,"action":"buy","event":"entry","id":"1759560000000-1234-e"}
```

## ข้อควรระวัง
- **เช็กกฎ Topstep เรื่องระบบอัตโนมัติก่อน** ผิดกฎอาจโดนปิดบัญชี
- **บอทไม่รู้สถานะจริง** ถ้าสัญญาณหลุด (เน็ตหลุด, เครื่องหลับ, บอทดับ) สถานะจะค้างหรือเกิน ต้องเฝ้าดูและปิดเอง
- **Indicator ไม่มี stop loss** ถือจนเจอ brick ตรงข้าม ตั้ง bracket ในแผงเทรด TopstepX หรือเฝ้าดู และระวัง Daily Loss Limit
- ราคาเข้าจริงไม่เท่าราคาปิด brick ในตาราง Stats (มี latency ของ Alert + การกด)
- เครื่องต้องเปิดอยู่ ไม่หลับ ไม่ล็อกจอ และหน้า TopstepX ต้องเปิดค้างเป็นแท็บที่แสดงอยู่
- **เริ่มด้วย `dry_run: true` และบัญชี Practice เสมอ**

## 1) ตั้งคีย์ลัดใน TopstepX
บอทตั้งคีย์ลัดในบัญชีคุณให้เองไม่ได้ ต้องตั้งเองในหน้า Hotkeys ของ TopstepX ตามนี้:

| | Buy Market | Sell Market |
|---|---|---|
| **Windows** | `Ctrl + Alt + B` | `Ctrl + Alt + S` |
| **macOS** | `Control + Shift + B` | `Control + Shift + S` |

เหตุผล: เลี่ยงคีย์ที่เบราว์เซอร์/ระบบใช้
- Windows: `Ctrl+B`, `Ctrl+S`, `Ctrl+Shift+B` ชนกับ Bookmarks/Save/แถบบุ๊กมาร์ก แต่ `Ctrl+Alt+B/S` ไม่มีใน Chrome/Edge/Firefox
- macOS: เลี่ยง `Option` เพราะ Option+ตัวอักษรพิมพ์สัญลักษณ์พิเศษ (เช่น Option+B = ∫) ทำให้หน้าเว็บอ่านคีย์ผิด และ Control+Shift ไม่ชนกับคีย์ลัดของ macOS/Chrome
- ใช้ 3 ปุ่มรวมกัน กันเผลอกดเอง เพราะกดแล้วส่งออเดอร์จริง

ถ้า TopstepX ไม่ยอมรับชุดนี้ ให้เปลี่ยน แล้วแก้ `hotkeys` ใน `bot/config.json` ให้ตรง เช่น `"hotkeys": {"buy": ["ctrl","alt","b"], "sell": ["ctrl","alt","s"]}`

**สำคัญ:**
- ตั้งขนาดออเดอร์ (และ stop/target ถ้าต้องการ) ในแผงเทรด TopstepX ให้พร้อมก่อน บอทกดคีย์ลัดครั้งเดียว ออเดอร์จะออกตามค่าที่ตั้งไว้ ณ ตอนนั้น
- **เปิด Keyboard layout เป็นภาษาอังกฤษ** ตอนบอททำงาน ถ้าเป็นไทย ตัวอักษรที่ส่งอาจเป็นอักษรไทย คีย์ลัดจะไม่ทำงาน
- กดด้วยมือทดสอบก่อนว่าส่งออเดอร์ได้จริง บนบัญชี Practice

## 2) ติดตั้งบอท
```bash
cd bot
pip install -r requirements.txt
cp config.example.json config.json
```
แก้ `config.json`:
- `secret` รหัสสุ่มอย่างน้อย 16 ตัว (ใช้ค่าเดียวกันใน Indicator) บอทไม่ยอมรัน ถ้ายังเป็นค่าตัวอย่าง
- macOS: `focus_app` ชื่อเบราว์เซอร์ เช่น `"Google Chrome"` / Windows: `focus_title` คำในชื่อหน้าต่าง เช่น `"TopstepX"`
- macOS ให้สิทธิ์ Accessibility แก่ Terminal ที่รันบอท (System Settings → Privacy & Security)
- ปล่อย `dry_run: true` ไว้ก่อน

ทดสอบ: `python topstepx_bot.py test buy` (ตอน dry-run จะแค่พิมพ์ข้อความ)

## 3) อุโมงค์ Webhook
TradingView เรียกเข้าเครื่องคุณตรงๆ ไม่ได้ ต้องมี URL HTTPS สาธารณะชี้มาที่ `127.0.0.1:8765`:
- **ngrok:** สมัครฟรีแล้วใช้โดเมนคงที่ของบัญชี เช่น `ngrok http --url=ชื่อของคุณ.ngrok-free.app 8765` (ดูคำสั่งล่าสุดในเอกสาร ngrok)
- **Cloudflare Tunnel:** ถ้ามีโดเมนของตัวเอง ใช้ named tunnel ได้ (quick tunnel ที่ไม่มีโดเมน URL เปลี่ยนทุกครั้งที่เปิด ไม่เหมาะ)
- TradingView รับ Webhook เฉพาะพอร์ต 80/443 และต้องเปิด 2FA กับแผนที่รองรับ Webhook
- ใครรู้ URL + secret สั่งเปิดออเดอร์ในเครื่องคุณได้ เก็บ secret เป็นความลับ บอทกัน secret ผิด สัญญาณซ้ำ (id) และสัญญาณเก่าเกิน `max_age_seconds` (ค่าเริ่มต้น 120 วินาที)

## 4) ตั้ง Indicator และ Alert
1. กราฟ **Renko** ของ TradingView (Chart type → Renko) ด้วยสัญลักษณ์ฟิวเจอร์สที่เทรดบน TopstepX
2. ใส่ `pine/renko_engulf_v6.pine` ตั้งค่า **Alert mode = `TopstepX Clicker`**, **Webhook secret** ให้ตรง `config.json`
3. สร้าง Alert: Condition = Indicator นี้ → **Any alert() function call**, Frequency ไม่ต้องตั้ง (โค้ดใช้ `freq_all`), Notifications → **Webhook URL** ใส่ URL อุโมงค์ (ปล่อยช่อง Message ไว้ ข้อความมาจาก `alert()`)
4. รัน `python topstepx_bot.py run` ตอนเทรด

## ลำดับทดสอบก่อนใช้จริง
1. `dry_run: true` ยิง Alert ทดสอบจาก TradingView ดู `bot/bot.log` ว่ารับ `entry`/`exit` ครบและ action ถูก
2. `dry_run: false` บนบัญชี **Practice**: `python topstepx_bot.py test buy` ได้ออเดอร์ตามขนาดที่ตั้งไว้ไหม แล้ว `test sell` ปิดสถานะพอดีไหม
3. รอครบ 1 รอบเข้า-ออกจริง ตรวจว่าปิดสถานะหมด
4. ค่อยพิจารณาบัญชีจริง

## ค่าใน `bot/config.json`
| ค่า | ความหมาย |
|---|---|
| `dry_run` | `true` = ไม่กดจริง |
| `max_age_seconds` | ทิ้งสัญญาณที่เก่าเกินกี่วินาที (0 = ไม่เช็ก, ต้องให้นาฬิกาเครื่องตรงเวลา) |
| `hotkeys` | ไม่ใส่ = ใช้ค่าแนะนำตามระบบปฏิบัติการ |

หยุดฉุกเฉิน: ลากเมาส์ไปมุมซ้ายบนของจอ หรือปิดบอท (Ctrl+C)
