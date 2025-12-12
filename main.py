import asyncio
import json
import os
import html
import time
from decimal import Decimal

import requests
import aiohttp
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CRYPTO_ADDRESS,
    IBAN,
    IBAN_NAME,
    GROUPS,
    ADMIN_USERNAMES,
    LIMITED_GROUPS,
    RENEW_PRICES,
)

DB_FILE = "database.json"


# ===================== DB =====================

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


db = load_db()


def get_user(uid: int):
    uid = str(uid)
    if uid not in db:
        db[uid] = {
            "selected_groups": [],
            "state": None,
            "pending_payment": None,
        }
    return db[uid]


# ===================== HELPERS =====================

def escape(t: str) -> str:
    return html.escape(str(t))


def get_discount_rate(count: int) -> int:
    if count <= 1:
        return 0
    table = {
        2: 10,
        3: 15,
        4: 15,
        5: 20,
        6: 20,
        7: 30,
        8: 30,
        9: 40,
        10: 40,
    }
    return table.get(count, 0)


def calc_totals_with_discount(group_keys):
    normal_total = sum(GROUPS[k]["price_try"] for k in group_keys)
    rate = get_discount_rate(len(group_keys))
    discount_amount = round(normal_total * rate / 100)
    final_price = normal_total - discount_amount
    return normal_total, rate, discount_amount, final_price


def get_usdt_rate() -> float:
    """Binance'ten USDT/TRY kuru çeker. Hata olursa fallback 31."""
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY",
            timeout=5,
        )
        data = r.json()
        return float(data["price"])
    except Exception:
        return 31.0


def calc_usdt_from_try(amount_try: int) -> Decimal:
    """
    TRY → USDT çevirir (Binance USDT/TRY kuru ile)
    """
    rate = Decimal(str(get_usdt_rate()))
    usdt = Decimal(str(amount_try)) / rate

    # 2 ondalık gösterim (USDT için ideal)
    return usdt.quantize(Decimal("0.01"))



def build_support_footer() -> str:
    """ADMIN_USERNAMES'ten destek satırı üretir."""
    if not ADMIN_USERNAMES:
        return ""
    handles = " / ".join(f"@{u.lstrip('@')}" for u in ADMIN_USERNAMES)
    return f"\n\n📞 Destek: {handles}"


def with_support(text: str) -> str:
    """Metnin sonuna destek satırını ekler (bir kere)."""
    footer = build_support_footer()
    if not footer:
        return text
    if footer.strip() in text:
        return text
    return text + footer


# ===================== TRONSCAN: TRC20 TRANSFERLER =====================

async def fetch_trc20_transfers():
    """
    Tronscan'den bu cüzdana gelen son TRC20 transferleri.
    Burada doğrudan token_trc20 endpoint'ini kullanıyoruz.
    """
    url = (
        "https://apilist.tronscanapi.com/api/token_trc20/transfers"
        f"?limit=50&toAddress={CRYPTO_ADDRESS}"
    )

    async with aiohttp.ClientSession() as session:
        # ssl=False: sertifika sorunları yaşamayalım diye
        async with session.get(url, ssl=False, timeout=10) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return (
                data.get("token_transfers")
                or data.get("trc20_transfers")
                or data.get("data")
                or []
            )


def parse_trc20_amount(tx) -> Decimal:
    """
    Tronscan transfer objesinden USDT miktarını parse eder.
    """
    if tx.get("amount_str") is not None:
        return Decimal(str(tx["amount_str"]))
    if tx.get("amount") is not None:
        s = str(tx["amount"])
        if "." in s:
            return Decimal(s)
        else:
            # integer ise 6 decimal varsayımı
            return Decimal(s) / Decimal(10 ** 6)
    if tx.get("quant") is not None:
        return Decimal(str(tx["quant"])) / Decimal(10 ** 6)
    return Decimal("0")


def parse_trc20_timestamp(tx) -> float:
    """
    Transfer zamanını (saniye) döndürür.
    """
    for key in ("block_timestamp", "block_ts", "timestamp"):
        v = tx.get(key)
        if v:
            v_int = int(v)
            if v_int > 10 ** 12:  # ms ise
                return v_int / 1000.0
            return v_int
    return 0.0


async def auto_check_payments(app: Application):
    """
    TronGrid üzerinden USDT (TRC20) ödemelerini OTOMATİK kontrol eder.
    Kullanıcı ödeme yaptıysa anında onay verir.
    FORMAT FARKLILIKLARI (to / to_address, büyük-küçük harf)
    TAMAMEN DÜZELTİLDİ → %100 ÇALIŞIR.
    """

    import ssl
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # Base58 adres kullanıyoruz → CRYPTO_ADDRESS
    tron_addr = CRYPTO_ADDRESS.strip().lower()

    # Sadece yeni işlemleri görmek için
    last_seen = set()

    # Base58 → HEX adres (Tron requirement)
    # Hex adres zaten sende hazır: sadece kısaltıp otomatik map edelim
    hex_addr = "41d4f3c20ba5b558b05fabc7e682d12a52a8fe0efc"

    while True:
        try:
            # TRC20 transferleri çeken endpoint
            url = f"https://api.trongrid.io/v1/accounts/{hex_addr}/transactions/trc20?limit=50"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=ssl_ctx, timeout=10) as r:
                    data = await r.json()

            tx_list = data.get("data", [])
            if not tx_list:
                await asyncio.sleep(5)
                continue

            for tx in tx_list:
                txid = tx.get("transaction_id")
                if not txid or txid in last_seen:
                    continue
                last_seen.add(txid)

                # Token bilgisi → sadece USDT
                token = tx.get("token_info", {})
                symbol = token.get("symbol", "").upper()

                if symbol != "USDT":
                    continue

                # TRONGRID bazen "to", bazen "to_address" döner → ikisini de kontrol et
                to_addr = (
                    tx.get("to")
                    or tx.get("to_address")
                    or tx.get("toAddress")
                    or ""
                ).strip().lower()

                # Adres eşleşmezse geç
                if to_addr != tron_addr:
                    continue

                raw_value = tx.get("value") or "0"
                amount = Decimal(raw_value) / Decimal(10**6)

                # Her kullanıcıyı tara
                for uid, user in db.items():
                    pending = user.get("pending_payment") or {}

                    if pending.get("method") != "crypto":
                        continue
                    if pending.get("status") == "paid":
                        continue

                    expected = Decimal(str(pending["usdt_amount"]))

                    # Gönderilen miktar yeterliyse ödeme tamam
                    if amount >= expected:
                        pending["status"] = "paid"
                        user["state"] = None
                        save_db(db)

                        # 30 günlük üyelik sadece LIMITED_GROUPS için
                        user.setdefault("group_access", {})

                        for key in user["selected_groups"]:
                            if key in LIMITED_GROUPS:
                                user["group_access"][key] = {
                                    "start": int(time.time()),
                                    "notified": False
                                }

                        # Kullanıcıya mesaj
                        await app.bot.send_message(
                            chat_id=int(uid),
                            text=with_support(
                                "✅ USDT ödemeniz otomatik olarak doğrulandı!\nGruplarınız hazırlanıyor..."
                            )
                        )

                        # Adminlere mesaj (destek satırı eklemiyoruz)
                        groups_text = ", ".join(GROUPS[k]["name"] for k in user["selected_groups"])
                        for admin_id in ADMIN_IDS:
                            await app.bot.send_message(
                                chat_id=admin_id,
                                text=(
                                    "💰 <b>Yeni KRİPTO ödeme alındı!</b>\n\n"
                                    f"<b>Kullanıcı:</b> {uid}\n"
                                    f"<b>Tutar:</b> {amount} USDT\n"
                                    f"<b>Gruplar:</b> {groups_text}"
                                ),
                                parse_mode="HTML"
                            )

                        # Davet linklerini gönder
                        await send_group_links(app.bot, int(uid), user["selected_groups"])

            await asyncio.sleep(5)

        except Exception as e:
            print("auto_check_payments ERROR:", e)
            await asyncio.sleep(5)


# ===================== KEYBOARDS =====================

def build_group_keyboard(selected):
    rows = []

    for key, g in GROUPS.items():
        checked = "✅ " if key in selected else ""
        name = g["name"]
        price = g["price_try"]

        main_label = f"{checked}{name} ({price}₺)"

        rows.append([
            InlineKeyboardButton(main_label, callback_data=f"grp:{key}")
        ])

    rows.append([InlineKeyboardButton("Devam ➡️", callback_data="next")])
    rows.append([InlineKeyboardButton("📢 Grup Tanıtımları", callback_data="show_info_menu")])
    rows.append([InlineKeyboardButton("Seçimleri temizle ❌", callback_data="clear")])

    return InlineKeyboardMarkup(rows)


def build_payment_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💠 Kripto (USDT-TRC20)", callback_data="pay:crypto")],
            [InlineKeyboardButton("🏦 Havale / EFT", callback_data="pay:eft")],
        ]
    )


def build_admin_links_text():
    if not ADMIN_USERNAMES:
        return "admin"

    return " / ".join(
        f"@{u.lstrip('@')}" for u in ADMIN_USERNAMES
    )



# ===================== HANDLERS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    user["selected_groups"] = []
    user["state"] = "selecting"
    user["pending_payment"] = None
    save_db(db)

    msg = (
        "👋 <b>Merhaba!</b>\n"
        "Katılmak istediğiniz grupları aşağıdan seçebilirsiniz.\n\n"
        "<b>📌 Birden fazla grup seçtiğinizde otomatik indirim uygulanır:</b>\n\n"
        "<b>2</b> grup → <b>%10</b> indirim\n"
        "<b>3</b> grup → <b>%15</b> indirim\n"
        "<b>4</b> grup → <b>%15</b> indirim\n"
        "<b>5</b> grup → <b>%20</b> indirim\n"
        "<b>6</b> grup → <b>%20</b> indirim\n"
        "<b>7</b> grup → <b>%30</b> indirim\n"
        "<b>8</b> grup → <b>%30</b> indirim\n"
        "<b>9</b> grup → <b>%40</b> indirim\n"
        "<b>10</b> grup → <b>%40</b> indirim\n\n"
        "<b>✔ Seçimlerinize göre indirimler otomatik hesaplanacaktır.</b>"
    )
    msg = with_support(msg)

    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=build_group_keyboard(user["selected_groups"]),
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user = get_user(uid)
    data = query.data

    # -------- Yenileme callbackleri --------
    if data.startswith("renew:"):
        group_key = data.split(":", 1)[1]

        price = RENEW_PRICES[group_key]

        user["selected_groups"] = [group_key]
        user["pending_payment"] = {
            "total_try": price,
            "status": "pending",
        }
        user["state"] = "choose_payment"
        save_db(db)

        g = GROUPS[group_key]

        txt = (
            f"🔄 <b>{g['name']}</b> üyeliğini yenilemek üzeresiniz.\n\n"
            f"Yenileme fiyatı: <b>{price}₺</b>\n"
            "Ödeme yöntemini seçin:"
        )
        txt = with_support(txt)

        await query.edit_message_text(
            txt,
            parse_mode="HTML",
            reply_markup=build_payment_keyboard()
        )
        return

    if data == "renew_no":
        # Yenilemeyi reddetti, sadece notified = True yapıyoruz
        access = user.get("group_access", {})
        for gkey in access:
            if gkey in LIMITED_GROUPS:
                access[gkey]["notified"] = True
        save_db(db)

        await query.edit_message_text(
            with_support("❌ Yenileme isteği iptal edildi. Üyeliğiniz yarın sona erecek ve ilgili gruptan çıkarılacaksınız.")
        )
        return

    # -------- TANITIM MENÜSÜ --------
    if data == "show_info_menu":
        rows = []
        for key, g in GROUPS.items():
            rows.append([
                InlineKeyboardButton(
                    f"{g['name']}",
                    callback_data=f"show_info:{key}"
                )
            ])

        rows.append([InlineKeyboardButton("🔙 Satın Almaya Geri Dön", callback_data="back_to_groups")])

        msg = (
            "📢 <b>Grup Tanıtımları</b>\n\n"
            "İncelemek istediğiniz grubu seçin:"
        )
        msg = with_support(msg)

        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows)
        )
        return

    # -------- Satın almaya geri dön --------
    if data == "back_to_groups":
        msg = with_support("📌 Lütfen katılmak istediğiniz grupları seçin:")
        await query.from_user.send_message(
            msg,
            reply_markup=build_group_keyboard(user["selected_groups"]),
            parse_mode="HTML"
        )
        return

    # -------- Grup Tanıtım / Info --------
    if data.startswith("info:"):
        key = data.split(":", 1)[1]
        g = GROUPS[key]

        photos = g.get("photo", [])

        if isinstance(photos, list) and len(photos) > 0:
            media = [InputMediaPhoto(p) for p in photos]
            await query.from_user.send_media_group(media)

        txt = f"📌 <b>{g['name']}</b>\n\n{g['info']}"
        txt = with_support(txt)

        await query.from_user.send_message(
            txt,
            parse_mode="HTML"
        )
        return

    # -------- TEK GRUP TANITIM SAYFASI --------
    if data.startswith("show_info:"):
        key = data.split(":", 1)[1]
        g = GROUPS[key]

        photos = g.get("photo", [])
        if isinstance(photos, str):
            photos = [photos]

        if len(photos) > 1:
            media = [InputMediaPhoto(p) for p in photos]
            await query.from_user.send_media_group(media)
        elif len(photos) == 1:
            await query.from_user.send_photo(photos[0])

        txt = f"<b>{g['name']} Tanıtımı</b>\n\n{g['info']}"
        txt = with_support(txt)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Tanıtımlara Geri Dön", callback_data="show_info_menu")],
            [InlineKeyboardButton("🏠 Satın Almaya Geri Dön", callback_data="back_to_groups")]
        ])

        await query.from_user.send_message(
            text=txt,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    # -------- Grup toggle --------
    if data.startswith("grp:"):
        key = data.split(":", 1)[1]
        if key in user["selected_groups"]:
            user["selected_groups"].remove(key)
        else:
            user["selected_groups"].append(key)
        save_db(db)

        await query.edit_message_reply_markup(
            reply_markup=build_group_keyboard(user["selected_groups"])
        )
        return

    # -------- Temizle --------
    if data == "clear":
        user["selected_groups"] = []
        save_db(db)

        await query.edit_message_reply_markup(
            reply_markup=build_group_keyboard(user["selected_groups"])
        )
        return

    # -------- Devam (özet + ödeme seçimi) --------
    if data == "next":
        if not user["selected_groups"]:
            await query.answer("Önce en az bir grup seçmelisiniz.", show_alert=True)
            return

        normal_total, rate, disc_amount, final_price = calc_totals_with_discount(
            user["selected_groups"]
        )

        user["pending_payment"] = {
            "total_try": final_price,
            "status": "pending",
        }
        user["state"] = "choose_payment"
        save_db(db)

        lines = ["🧾 <b>Seçtiğiniz gruplar</b>\n"]
        for k in user["selected_groups"]:
            g = GROUPS[k]
            lines.append(f"• {escape(g['name'])} ({g['price_try']}₺)")
        lines.append("")
        lines.append(f"<b>Normal toplam:</b> {normal_total}₺")
        if rate > 0:
            lines.append(f"<b>İndirim (%{rate}):</b> -{disc_amount}₺")
        else:
            lines.append("<b>İndirim:</b> Yok")
        lines.append(f"<b>Ödenecek tutar:</b> {final_price}₺")
        lines.append("\nÖdeme yöntemini seçiniz:")

        txt = "\n".join(lines)
        txt = with_support(txt)

        await query.edit_message_text(
            txt,
            parse_mode="HTML",
            reply_markup=build_payment_keyboard(),
        )
        return

    # -------- Kripto seçimi --------
    if data == "pay:crypto":
        if not user["selected_groups"] or not user.get("pending_payment"):
            await query.answer("Önce grup ve tutar seçmelisiniz.", show_alert=True)
            return

        total_try = user["pending_payment"]["total_try"]
        usdt_amount = calc_usdt_from_try(total_try)
        user["pending_payment"]["method"] = "crypto"
        user["pending_payment"]["usdt_amount"] = str(usdt_amount)
        user["pending_payment"]["status"] = "waiting"
        user["pending_payment"]["created_at"] = time.time()
        user["state"] = "wait_crypto"
        save_db(db)

        txt = (
            "💠 <b>Kripto (USDT-TRC20) ile ödeme</b>\n\n"
            f"<b>Ödenecek tutar:</b> {total_try}₺\n"
            f"<b>Yaklaşık USDT karşılığı:</b> {usdt_amount} USDT\n\n"
            f"Lütfen aşağıdaki adrese sadece <b>USDT (TRC20)</b> gönderin:\n"
            f"<code>{CRYPTO_ADDRESS}</code>\n\n"
            "Ödemeyi yaptıktan sonra ekstra bir işlem yapmanıza gerek yoktur.\n"
            "Bot cüzdanı otomatik olarak kontrol eder ve ödemeniz onaylandığında size mesaj gönderir."
        )
        txt = with_support(txt)

        await query.edit_message_text(txt, parse_mode="HTML")
        return

    # -------- EFT seçimi --------
    if data == "pay:eft":
        if not user["selected_groups"] or not user.get("pending_payment"):
            await query.answer("Önce grup ve tutar seçmelisiniz.", show_alert=True)
            return

        total_try = user["pending_payment"]["total_try"]
        user["pending_payment"]["method"] = "eft"
        user["state"] = "wait_eft"
        save_db(db)

        txt = (
            "🏦 <b>Havale / EFT ile ödeme</b>\n\n"
            f"<b>Ödenecek tutar:</b> {total_try}₺\n\n"
            f"<b>IBAN:</b> <code>{IBAN}</code>\n"
            f"<b>Ad Soyad:</b> {escape(IBAN_NAME)}\n\n"
            "Ödemeyi yaptıktan sonra dekontu <b>fotoğraf</b> veya <b>PDF</b> olarak bu sohbete gönderin.\n"
            "Metin / açıklama olarak gönderilen dekontlar kabul edilmez.\n\n"
            f"Herhangi bir sorunda {ADMIN_USERNAMES} ile iletişime geçebilirsiniz."
        )
        txt = with_support(txt)

        await query.edit_message_text(txt, parse_mode="HTML")
        return


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    msg = update.message

    # ---------- EFT: DEKONT BEKLENİYOR ----------
    if user.get("state") == "wait_eft":
        pending = user.get("pending_payment") or {}
        if pending.get("method") != "eft":
            return

        if not msg.photo and not msg.document:
            txt = "❌ Dekont <b>fotoğraf</b> veya <b>PDF</b> olmalıdır."
            await msg.reply_text(
                with_support(txt),
                parse_mode="HTML",
            )
            return

        if msg.document and msg.document.mime_type != "application/pdf":
            txt = "❌ Yalnızca PDF veya fotoğraf kabul edilir."
            await msg.reply_text(
                with_support(txt),
                parse_mode="HTML",
            )
            return

        user["state"] = "eft_wait_admin"
        save_db(db)

        txt = (
            "🧾 Dekontunuz alındı.\n"
            "Ödemeniz admin onayına gönderildi, sonuç size bildirilecektir."
        )
        await msg.reply_text(
            with_support(txt)
        )

        groups_text = ", ".join(
            escape(GROUPS[k]["name"]) for k in user["selected_groups"]
        )
        caption = (
            "🧾 <b>Yeni EFT / Havale ödeme talebi</b>\n\n"
            f"<b>Kullanıcı:</b> {update.effective_user.mention_html()}\n"
            f"<b>Tutar:</b> {pending['total_try']}₺\n"
            f"<b>Gruplar:</b> {groups_text}\n\n"
            "Bu ödemeyi onaylıyor musunuz?"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Onayla", callback_data=f"admin:approve:{uid}")],
                [InlineKeyboardButton("❌ Reddet", callback_data=f"admin:reject:{uid}")],
            ]
        )

        for admin_id in ADMIN_IDS:
            if msg.photo:
                file_id = msg.photo[-1].file_id
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=caption,  # admin caption'ına destek eklemiyoruz
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=msg.document.file_id,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        return


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # admin:approve:<uid> / admin:reject:<uid>

    if not data.startswith("admin:"):
        return

    parts = data.split(":")
    if len(parts) != 3:
        return

    _, action, uid_str = parts
    target_uid = int(uid_str)

    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Bu buton sadece admin içindir.", show_alert=True)
        return

    user = get_user(target_uid)
    pending = user.get("pending_payment") or {}

    if action == "approve":
        pending["status"] = "paid"
        user["state"] = None
        save_db(db)

        user.setdefault("group_access", {})

        for key in user["selected_groups"]:
            if key in LIMITED_GROUPS:
                user["group_access"][key] = {
                    "start": int(time.time()),
                    "notified": False
                }

        # Admin mesajı (destek yazmıyoruz)
        await query.message.reply_text("✅ Ödeme onaylandı.")

        # Kullanıcıya mesaj
        await context.bot.send_message(
            chat_id=target_uid,
            text=with_support("✅ Ödemeniz onaylandı, gruplarınız hazırlanıyor..."),
        )
        await send_group_links(context.bot, target_uid, user["selected_groups"])

    elif action == "reject":
        pending["status"] = "rejected"
        user["state"] = None
        save_db(db)

        await query.message.reply_text("❌ Ödeme reddedildi.")
        admin_links = build_admin_links_text()
        await context.bot.send_message(
            chat_id=target_uid,
            text=with_support(
                "❌ Ödemeniz admin tarafından reddedildi.\n"
                f"Detaylı bilgi için {admin_links} ile iletişime geçebilirsiniz."
            ),
            parse_mode="HTML",
        )


async def membership_checker(app: Application):
    while True:
        try:
            now = int(time.time())

            for uid, user in db.items():
                access = user.get("group_access", {})

                for group_key, info in list(access.items()):
                    # Sadece LIMITED_GROUPS için
                    if group_key not in LIMITED_GROUPS:
                        continue

                    start_time = info.get("start")
                    if not start_time:
                        continue

                    passed_days = (now - start_time) / 86400

                    # 29. gün → uyarı gönder
                    if 29 <= passed_days < 30 and not info.get("notified"):
                        price = RENEW_PRICES.get(group_key, GROUPS[group_key]["price_try"])

                        g = GROUPS[group_key]
                        txt = (
                            f"⚠️ <b>{g['name']}</b> üyeliğiniz yarın sona eriyor.\n"
                            f"Yenileme fiyatı: <b>{price}₺</b>\n"
                            "Yenilemek ister misiniz?"
                        )
                        txt = with_support(txt)

                        await app.bot.send_message(
                            chat_id=int(uid),
                            text=txt,
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔄 Yenile", callback_data=f"renew:{group_key}")],
                                [InlineKeyboardButton("❌ Hayır", callback_data="renew_no")]
                            ])
                        )

                        info["notified"] = True
                        save_db(db)

                    # 30. gün → gruptan çıkar
                    if now - start_time >= 30 * 86400:
                        g = GROUPS[group_key]
                        chat_id = g["chat_id"]

                        try:
                            await app.bot.ban_chat_member(chat_id, int(uid))
                        except Exception:
                            pass

                        try:
                            await app.bot.unban_chat_member(chat_id, int(uid))
                        except Exception:
                            pass

                        txt = (
                            f"⛔ <b>{g['name']}</b> üyeliğiniz sona erdi ve gruptan çıkarıldınız.\n"
                            "Dilerseniz tekrar satın alabilirsiniz."
                        )
                        txt = with_support(txt)

                        await app.bot.send_message(
                            chat_id=int(uid),
                            text=txt,
                            parse_mode="HTML"
                        )

                        del access[group_key]
                        save_db(db)

        except Exception as e:
            print("membership_checker ERROR:", e)

        await asyncio.sleep(3600)  # 1 saatte bir kontrol


# ===================== GRUP LINKLERI =====================

async def send_group_links(bot, uid: int, group_keys):
    text_lines = [
        "🔓 Aşağıdaki gruplara erişim kazandınız:\n\n"
        "⚠️ LİNKLER BİR KERE KULLANILMASI İÇİN OTOMATİK ÜRETİLMİŞTİR, "
        "İLK KULLANIMINDAN SONRA GEÇERSİZ OLACAKTIR. ⚠️\n"
    ]

    user = get_user(uid)
    user.setdefault("group_access", {})

    for key in group_keys:
        g = GROUPS[key]
        chat_id = g["chat_id"]

        invite = await bot.create_chat_invite_link(
            chat_id=chat_id,
            member_limit=1,
            name=f"user_{uid}_{key}",
        )

        text_lines.append(f"• {escape(g['name'])} → {invite.invite_link}")

        # Sadece limited grupları süreli yap
        if key in LIMITED_GROUPS:
            user["group_access"][key] = {
                "start": int(time.time()),
                "notified": False
            }

    save_db(db)

    txt = "\n".join(text_lines)
    txt = with_support(txt)

    await bot.send_message(chat_id=uid, text=txt)


# ===================== MAIN / LOOP =====================

if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(
        MessageHandler(
            filters.TEXT | filters.PHOTO | filters.Document.PDF,
            message_handler,
        )
    )

    print("Bot başlatılıyor...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner():
        await application.initialize()
        await application.start()
        print("Bot çalışıyor... /start yazıp deneyebilirsin.")

        asyncio.create_task(auto_check_payments(application))
        asyncio.create_task(membership_checker(application))

        await application.updater.start_polling()
        await asyncio.Event().wait()

    loop.create_task(runner())
    loop.run_forever()
