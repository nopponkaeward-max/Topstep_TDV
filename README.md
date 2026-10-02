# TradingView → คลิกปุ่ม TopstepX บนเครื่องตัวเอง

สคริปต์ Python รันบน PC/Mac ของคุณ รับสัญญาณจาก TradingView แล้ว **คลิกปุ่ม Buy/Sell/Flatten บนหน้าจอ TopstepX ให้** ไม่ผ่านบริการตัวกลางและไม่ใช้ API

```
TradingView Alert ──(อีเมล หรือ Webhook)──▶ clicker.py ──pyautogui──▶ คลิกปุ่มบน TopstepX
```

## ข้อควรระวังก่อนใช้
- **เช็กกฎ Topstep เรื่องระบบอัตโนมัติก่อน** การคลิกอัตโนมัติอาจเข้าข่ายและเสี่ยงโดนปิดบัญชี
- วิธีนี้ **เปราะบาง**: เครื่องต้องเปิดอยู่ จอไม่ล็อก หน้าต่าง TopstepX ต้องเห็นเต็มและอยู่ตำแหน่ง/ขนาด/zoom เดิมทุกครั้ง ถ้าขยับ คลิกจะผิดที่
- ปุ่ม Buy/Sell ของ TopstepX ส่งออเดอร์ตามขนาดและ stop/target ที่ตั้งไว้ในแผงเทรดตอนนั้น ตั้งให้พร้อมก่อน
- **เริ่มด้วย `dry_run: true` และบัญชี Practice เสมอ**
- มีตัวกันพลาด: secret, cooldown, จำกัดจำนวนคลิกต่อชั่วโมง และลากเมาส์ไปมุมซ้ายบนจอเพื่อหยุดฉุกเฉิน

## ติดตั้ง
```bash
pip install -r requirements.txt
cp config.example.json config.json   # แล้วแก้ค่าในไฟล์
```
- **macOS**: System Settings → Privacy & Security → Accessibility และ Screen Recording ให้ Terminal/IDE ที่รันสคริปต์
- **Windows**: ถ้า TopstepX ถูกเปิดแบบ Administrator ให้รันสคริปต์แบบ Administrator ด้วย

## ขั้นตอน
1. `python clicker.py calibrate` เปิด TopstepX ไว้ตำแหน่งที่ใช้เทรดจริง แล้ววางเมาส์บนปุ่ม buy / sell / flatten ตามที่สคริปต์บอก (ถ้ามีหน้าต่างยืนยันออเดอร์ ให้บันทึก `buy_confirm`/`sell_confirm` ด้วย)
2. `python clicker.py test buy` ดูว่าคลิกถูกที่ (ตอน `dry_run: true` จะแค่พิมพ์ข้อความ ตั้งเป็น `false` เมื่อพร้อมทดสอบจริงบน Practice)
3. ตั้ง TradingView Alert (ดูด้านล่าง)
4. `python clicker.py run` แล้วปล่อยทิ้งไว้

## เลือกวิธีรับสัญญาณ (`source` ใน config.json)

### `imap` (แนะนำ ไม่ต้องเปิดพอร์ต/ไม่ต้องมี URL สาธารณะ)
TradingView ส่งอีเมลเมื่อ Alert ทำงาน สคริปต์ตรวจกล่องจดหมายทุกไม่กี่วินาที
- เปิด 2FA ใน Gmail แล้วสร้าง **App password** ใส่ใน `imap.app_password`
- ใน Alert เปิด **Notifications → Send email**
- ช้ากว่า Webhook ราว 5–30 วินาที ไม่เหมาะกับสัญญาณที่ต้องเร็วมาก

### `webhook` (เร็วกว่า)
สคริปต์เปิดเซิร์ฟเวอร์ที่ `127.0.0.1:8765` แต่ TradingView เรียกเข้าเครื่องคุณตรงๆ ไม่ได้ ต้องมีอุโมงค์ (เช่น Cloudflare Tunnel หรือ ngrok) ซึ่งก็คือบริการอีกตัว และต้องใช้ TradingView แผนเสียเงิน
ใน Alert เปิด **Notifications → Webhook URL** ใส่ URL ของอุโมงค์

## ข้อความ Alert (ใส่ในช่อง Message)
```json
{"secret":"รหัสเดียวกับใน config.json","action":"buy"}
```
`action` เป็น `buy`, `sell` หรือ `flatten` (Strategy ใช้ `{{strategy.order.action}}` แทนค่าได้)

## ปรับค่าใน config.json
| ค่า | ความหมาย |
|---|---|
| `dry_run` | `true` = ไม่คลิกจริง |
| `cooldown_seconds` | ไม่รับสัญญาณซ้ำภายในกี่วินาที |
| `max_clicks_per_hour` | เพดานจำนวนคลิกต่อชั่วโมง |
| `confirm_delay_seconds` | รอก่อนกดปุ่มยืนยัน |

`config.json` อยู่ใน `.gitignore` แล้ว อย่าแชร์เพราะมีรหัสผ่านอีเมลและ secret
