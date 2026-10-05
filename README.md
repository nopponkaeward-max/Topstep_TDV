# TopstepX Clicker: Renko Engulf (TradingView) → คลิกปุ่ม Buy/Sell บน TopstepX

บอทรันบน PC/Mac ของคุณ รับ Webhook จาก TradingView แล้ว **คลิกปุ่ม Buy/Sell Market ในหน้า TopstepX** (หรือกดคีย์ลัด ถ้าคีย์ลัดของ TopstepX ใช้งานได้บนเครื่องคุณ) ไม่ใช้ API ไม่ผ่านบริการตัวกลาง และ **ไม่ตรวจสถานะบัญชี** Indicator สั่งอะไร บอทกดตามนั้น

```
Indicator (Renko Engulf) → alert() JSON → Webhook (อุโมงค์ HTTPS) → bot/topstepx_bot.py → คลิกปุ่มบน TopstepX
```

## ไฟล์
- `pine/renko_engulf_v6.pine` Indicator ที่เพิ่มโหมด `TopstepX Clicker` (ต้นฉบับ: `renko_engulf_v6.pine` ที่ใช้บนกราฟ Renko ของ TradingView)
- `bot/topstepx_bot.py` บอท, `bot/config.example.json` ตัวอย่างค่าตั้ง

## กติกาสัญญาณ
`Last Bull/Bear` ถูกบังคับปิดในโหมดนี้ (ใช้ `Immediate previous bar` เสมอ) และบังคับถือครั้งละ 1 ออเดอร์ ทำให้ 1 brick เกิดเหตุการณ์ได้อย่างมาก 1 อย่าง ไม่มีการกลับทิศใน brick เดียว

| เหตุการณ์ใน Indicator | บอทกด |
|---|---|
| เข้า long | คลิก Buy 1 ครั้ง |
| ออก long (เจอ brick ขาลง) | คลิก Sell 1 ครั้ง |
| เข้า short | คลิก Sell 1 ครั้ง |
| ออก short (เจอ brick ขาขึ้น) | คลิก Buy 1 ครั้ง |

บอทกด **1 ครั้งต่อสัญญาณ** จำนวนสัญญาตั้งไว้ใน TopstepX แล้ว (ไม่มี qty ใน Indicator/บอท) เข้า-ออกใช้ขนาดเดียวกัน จึงปิดสถานะพอดี

ข้อความที่ Indicator ส่ง (`action` คือปุ่มที่ต้องกดจริงอยู่แล้ว):
```json
{"secret":"...","t":1759560000000,"action":"buy","event":"entry","id":"1759560000000-1234-e"}
```

## โหมดการออกจากออเดอร์ (กลุ่ม **Exit Strategy** ใน Indicator)
| ตั้งค่า | ความหมาย |
|---|---|
| **Exit mode = `Opposite brick`** (ค่าเริ่มต้น) | ออกเมื่อเจอ box สีตรงข้ามกับทิศที่ถือ |
| **Exit mode = `N same-color boxes`** | ออกเมื่อมี box สีเดียวกับทิศที่ถือเกิดครบ **N** แท่ง (Buy นับขาขึ้น, Sell นับขาลง) |
| **N** | จำนวน box (ค่าเริ่มต้น 3) |
| **ออกเมื่อเจอ box สีตรงข้ามด้วย** (ค่าเริ่มต้น เปิด) | ถ้าเจอสีตรงข้ามก่อนครบ N ให้ออกทันที (ทำหน้าที่เหมือน stop) **แนะนำให้เปิดไว้** ปิด = ไม่มี stop ถือสวนทางได้นาน |
| **นับ box ที่เข้าเป็น box ที่ 1** (ค่าเริ่มต้น ปิด) | ปิด: N=3 → ออกที่แท่งที่ 3 **หลัง** แท่งที่เข้า / เปิด: ออกที่แท่งที่ 2 หลังเข้า |

- คำสั่งที่ส่งไปบอทไม่เปลี่ยน: ออก long = `sell`, ออก short = `buy` (บอทไม่ต้องแก้)
- ในโหมด `TopstepX Clicker` จะ **ไม่เปิดออเดอร์ใหม่ใน brick เดียวกับที่เพิ่งออก** (กันบอทกดซื้อและขายพร้อมกัน) ต้องรอ brick ถัดไปที่ครอบคลุมตามเงื่อนไขเข้า
- ตาราง Stats คำนวณตามโหมดออกที่เลือก
- ตัวอย่าง N=3 (ไม่นับแท่งเข้า): แท่งที่ 2 เป็น engulf เข้า long → แท่งขาขึ้นอีก 3 แท่งตามมา ออกที่แท่งที่ 3 ด้วย `sell`

## ข้อควรระวัง
- **เช็กกฎ Topstep เรื่องระบบอัตโนมัติก่อน** ผิดกฎอาจโดนปิดบัญชี
- **บอทไม่รู้สถานะจริง** ถ้าสัญญาณหลุด (เน็ตหลุด, เครื่องหลับ, บอทดับ) สถานะจะค้างหรือเกิน ต้องเฝ้าดูและปิดเอง
- **Indicator ไม่มี stop loss** ถือจนเจอ brick ตรงข้าม ตั้ง bracket ในแผงเทรด TopstepX หรือเฝ้าดู และระวัง Daily Loss Limit
- ราคาเข้าจริงไม่เท่าราคาปิด brick ในตาราง Stats (มี latency ของ Alert + การกด)
- เครื่องต้องเปิดอยู่ ไม่หลับ ไม่ล็อกจอ และหน้า TopstepX ต้องเป็นแท็บที่แสดงอยู่ **อยู่หน้าสุด ไม่มีหน้าต่างอื่นบังปุ่ม Buy/Sell** และอยู่ตำแหน่ง/ขนาด/zoom เดิมตอน calibrate (ขยับแล้วคลิกพลาด)
- **log ที่ขึ้นว่าคลิก/กดแล้ว ไม่ได้ยืนยันว่าออเดอร์เข้า** ดูผลที่หน้า Positions ของ TopstepX เอง
- **เริ่มด้วย `dry_run: true` และบัญชี Practice เสมอ**

## 1) เลือกโหมด (`mode` ใน `bot/config.json`)

### `click` (ค่าเริ่มต้น แนะนำถ้าคีย์ลัด TopstepX ใช้ไม่ได้)
บอทคลิกปุ่ม Buy/Sell บนหน้าจอตามพิกัดที่บันทึกด้วย `calibrate` ไม่ขึ้นกับคีย์ลัดและภาษาของคีย์บอร์ด
- ตั้งขนาดออเดอร์ (และ stop/target ถ้าต้องการ) ในแผงเทรด TopstepX ให้พร้อมก่อน ปุ่ม Buy/Sell ส่งออเดอร์ตามค่าที่ตั้งไว้ ณ ตอนนั้น
- ถ้า TopstepX ถามยืนยันก่อนส่งออเดอร์ `calibrate` จะบันทึกปุ่มยืนยันให้ด้วย (ตอบ `y`)
- **หลัง calibrate ห้ามขยับ ย่อ ขยาย หรือซูมหน้าต่าง TopstepX** และอย่าเปลี่ยนความละเอียดจอ (บอทเช็กขนาดจอ ถ้าเปลี่ยนจะไม่ยอมคลิกและให้ calibrate ใหม่) ถ้าจัดวางแผงเทรดใหม่ ต้อง calibrate ใหม่
- บอทย้ายเมาส์ไปคลิกแล้วย้ายกลับตำแหน่งเดิม (ปิดได้ด้วย `"restore_mouse": false`)

### `hotkey`
กดคีย์ลัด Buy/Sell Market (ตั้ง `"mode": "hotkey"`) ใช้ได้เมื่อ TopstepX รับคีย์ลัดบนเครื่องคุณ (กดมือแล้วออเดอร์เข้า)
- ตั้งคีย์ลัดในหน้า Hotkeys ของ TopstepX: Windows `Ctrl+Alt+B / Ctrl+Alt+S`, macOS `Control+Shift+B / Control+Shift+S` แล้วให้ `hotkeys` ใน config ตรงกัน
- ต้องเปิด Keyboard layout เป็นภาษาอังกฤษ (ถ้าเป็นไทย ตัวอักษรที่ส่งไม่ตรง คีย์ลัดไม่ทำงาน)
- ทดสอบว่าคีย์ถึงเบราว์เซอร์ไหมด้วย `bot/keytest.html`

## 2) ติดตั้งบอท
```bash
cd bot
pip install -r requirements.txt
cp config.example.json config.json
```
แก้ `config.json`:
- `secret` รหัสสุ่มอย่างน้อย 16 ตัว (ใช้ค่าเดียวกันใน Indicator) บอทไม่ยอมรัน ถ้ายังเป็นค่าตัวอย่าง
- **หน้าต่างโฟกัส:** แนะนำให้ใส่ macOS: `"focus_app": "Google Chrome"` (หรือ `"Safari"`) / Windows: `"focus_title": "TopstepX"` (Windows ต้อง `pip install pygetwindow`) บอทจะดึงเบราว์เซอร์ขึ้นหน้าสุดก่อนคลิก/กดคีย์ (ต้องให้แท็บ TopstepX เป็นแท็บที่แสดงอยู่ในหน้าต่างนั้น) ถ้าไม่ใส่ บอททำงานกับหน้าจอตามที่เป็นอยู่ ถ้าหน้า TopstepX ไม่ได้อยู่หน้าสุด จะคลิกผิดที่
- macOS ให้สิทธิ์ Accessibility แก่ Terminal ที่รันบอท (System Settings → Privacy & Security)
- ปล่อย `dry_run: true` ไว้ก่อน

**โหมด click:** เปิด TopstepX ไว้ตำแหน่งที่ใช้เทรดจริง แล้วรัน `python3 topstepx_bot.py calibrate` ทำตามที่บอกบนจอ (วางเมาส์บนปุ่ม Buy แล้วปุ่ม Sell ภายใน 5 วินาทีต่อปุ่ม) ค่าจะถูกบันทึกลง `config.json`

ทดสอบ: `python3 topstepx_bot.py test buy` (ตอน dry-run จะแค่พิมพ์ข้อความว่าจะคลิกที่ไหน ตั้ง `dry_run: false` บนบัญชี Practice เพื่อทดสอบคลิกจริง)

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
4. รัน `python3 topstepx_bot.py run` ตอนเทรด

## ทดสอบสายส่งด้วยปุ่มทดสอบใน Indicator
ไม่ต้องรอสัญญาณจริง (ใช้ได้ตอนตลาดฟิวเจอร์สปิด ให้เปิดบนสัญลักษณ์ที่ราคาขยับ เช่น BTCUSD):
1. ใน Indicator ตั้ง Alert mode = `TopstepX Clicker`, เปิด **ส่งสัญญาณทดสอบไปบอท**, เลือก **ทดสอบ action** (buy/sell)
2. สร้าง Alert ใหม่: Condition = Indicator นี้ → **Any alert() function call**, Webhook URL = URL อุโมงค์
3. เมื่อ Alert เริ่มทำงาน จะส่งสัญญาณทดสอบ **1 ครั้ง** บอทต้องขึ้น `รับ POST ...` แล้ว `entry buy` (หรือ `[DRY RUN] ...` ถ้า `dry_run: true`)
4. **ลบ Alert ทดสอบทิ้ง และปิดตัวเลือกทดสอบ** ก่อนสร้าง Alert จริง

## ลำดับทดสอบก่อนใช้จริง
1. `dry_run: true` ยิง Alert ทดสอบจาก TradingView ดู `bot/bot.log` ว่ารับ `entry`/`exit` ครบและ action ถูก
2. `dry_run: false` บนบัญชี **Practice**: `python3 topstepx_bot.py test buy` ได้ออเดอร์ตามขนาดที่ตั้งไว้ไหม แล้ว `test sell` ปิดสถานะพอดีไหม (ทดสอบตอนที่ TopstepX เห็นปุ่มครบ ไม่มีหน้าต่างอื่นบัง)
3. รอครบ 1 รอบเข้า-ออกจริง ตรวจว่าปิดสถานะหมด
4. ค่อยพิจารณาบัญชีจริง

## ค่าใน `bot/config.json`
| ค่า | ความหมาย |
|---|---|
| `mode` | `click` (ค่าเริ่มต้น) หรือ `hotkey` |
| `dry_run` | `true` = ไม่ทำจริง |
| `buttons`, `screen_size` | ตำแหน่งปุ่มและขนาดจอ บันทึกโดย `calibrate` (โหมด click) |
| `restore_mouse` | ย้ายเมาส์กลับที่เดิมหลังคลิก (ค่าเริ่มต้น true) |
| `confirm_delay_seconds` | รอก่อนคลิกปุ่มยืนยัน (ถ้ามี) |
| `max_age_seconds` | ทิ้งสัญญาณที่เก่าเกินกี่วินาที (0 = ไม่เช็ก, ต้องให้นาฬิกาเครื่องตรงเวลา) |
| `focus_app` / `focus_title` | ดึงหน้าต่างเบราว์เซอร์ขึ้นมาก่อนคลิก/กดคีย์ macOS ใส่ชื่อแอป เช่น `"Google Chrome"` / Windows ใส่คำในชื่อหน้าต่าง **แนะนำให้ใส่** ไม่ใส่ = ไม่ดึงหน้าต่าง |
| `hotkeys` | (โหมด hotkey) ไม่ใส่ = ใช้ค่าแนะนำตามระบบปฏิบัติการ |

หยุดฉุกเฉิน: ลากเมาส์ไปมุมซ้ายบนของจอ หรือปิดบอท (Ctrl+C)
