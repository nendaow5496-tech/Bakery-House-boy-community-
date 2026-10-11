import asyncio
import os
import shutil
import sqlite3
import time
import discord
from discord import app_commands
from discord.ext import commands, tasks

from shop import (shop, db, ITEMS, CREAM, CUR_EMO, FENCE, EMO_TITLE, LINE, BUY_LIMIT, SELL_RATE,
                  day_info, today, get_stock, coins, add_coins, add_item, item_name, pretty, is_admin)

IMG_DIR = "shop_images"
BANNER = os.path.join(IMG_DIR, "banner.png")
MAX_BOARD = 6
os.makedirs(IMG_DIR, exist_ok=True)
TAG_TEXT = {"good": "🔥 ราคาดี — ขายได้แพง", "low": "🏷️ ราคาต่ำ — ซื้อถูก", "norm": "🛒 ราคาปกติ"}

db.execute("CREATE TABLE IF NOT EXISTS products (code TEXT PRIMARY KEY, emoji TEXT DEFAULT '', name TEXT, price INTEGER, stock INTEGER, detail TEXT DEFAULT '', pos INTEGER DEFAULT 0)")
for _c in ("board_channel INTEGER", "board_message INTEGER", "board_sig TEXT DEFAULT ''"):
    try:
        db.execute(f"ALTER TABLE shop_set ADD COLUMN {_c}")
    except sqlite3.OperationalError:
        pass
if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
    for _n, (_k, _v) in enumerate(list(ITEMS.items())[:6]):
        db.execute("INSERT INTO products (code, emoji, name, price, stock, pos) VALUES (?,?,?,?,?,?)", (_k, _v[0], _v[1], _v[2], _v[3], _n))
db.commit()


def load_items():
    rows = db.execute("SELECT code, emoji, name, price, stock FROM products ORDER BY pos, rowid").fetchall()
    ITEMS.clear()
    for k, e, n, p, s in rows:
        ITEMS[k] = (e or "🍞", n, p, s)


load_items()


def get_detail(code):
    r = db.execute("SELECT detail FROM products WHERE code=?", (code,)).fetchone()
    return (r[0] or "") if r else ""


def img_ok(code):
    p = os.path.join(IMG_DIR, f"product_{code}.png")
    return p if os.path.exists(p) else None


def board_files():
    files = []
    if os.path.exists(BANNER):
        files.append(discord.File(BANNER, filename="banner.png"))
    for k in list(ITEMS)[:MAX_BOARD]:
        p = img_ok(k)
        if p:
            files.append(discord.File(p, filename=f"product_{k}.png"))
    return files


def board_sig():
    day = today()
    info = day_info(day)
    parts = [day, str(os.path.getmtime(BANNER)) if os.path.exists(BANNER) else "nobanner"]
    for k in list(ITEMS)[:MAX_BOARD]:
        p = img_ok(k)
        parts.append(f"{k}|{ITEMS[k][0]}|{ITEMS[k][1]}|{info[k][0]}|{info[k][1]}|{get_stock(day, k)}|{os.path.getmtime(p) if p else 0}")
    return ";".join(parts)


def make_buy_button(k, disabled=False):
    b = discord.ui.Button(label="ซื้อ", emoji="🛒", style=discord.ButtonStyle.success, custom_id=f"shopbuy:{k}", disabled=disabled)

    async def cb(i: discord.Interaction):
        await i.response.send_modal(BuyModal(k))
    b.callback = cb
    return b


def make_info_button(k):
    b = discord.ui.Button(label="รายละเอียด", emoji="📖", style=discord.ButtonStyle.secondary, custom_id=f"shopinfo:{k}")

    async def cb(i: discord.Interaction):
        await send_info(i, k)
    b.callback = cb
    return b


class BoardView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        day = today()
        info = day_info(day)
        parts = []
        if os.path.exists(BANNER):
            parts.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://banner.png")))
        parts.append(discord.ui.TextDisplay(f"{EMO_TITLE}\n{FENCE}ร้านเบเกอรี่ Bakery House{FENCE}\n**ราคาและจำนวนสินค้าอัปเดตอัตโนมัติ**"))
        parts.append(discord.ui.Separator())
        keys = list(ITEMS)[:MAX_BOARD]
        if not keys:
            parts.append(discord.ui.TextDisplay("**ยังไม่มีสินค้าในร้าน**"))
        for k in keys:
            price, tag, _ = info[k]
            left = get_stock(day, k)
            sell = round(price * SELL_RATE)
            status = f"**เหลือ** __**{left}**__ ชิ้น" if left > 0 else "**สินค้าหมด**"
            parts.append(discord.ui.TextDisplay(f"## {ITEMS[k][0]} __**{ITEMS[k][1]}**__\n**ราคา** __**{price}**__ {CUR_EMO} · **รับซื้อ** **{sell}**\n{TAG_TEXT[tag]}\n{status}"))
            if img_ok(k):
                parts.append(discord.ui.MediaGallery(discord.MediaGalleryItem(f"attachment://product_{k}.png")))
            parts.append(discord.ui.ActionRow(make_buy_button(k, left <= 0), make_info_button(k)))
        parts.append(discord.ui.Separator())
        parts.append(discord.ui.TextDisplay(f"**ซื้อได้วันละไม่เกิน {BUY_LIMIT} ชิ้นต่อสินค้า · ราคาใหม่ตอนเที่ยงคืน**"))
        self.add_item(discord.ui.Container(*parts, accent_colour=discord.Colour(CREAM)))


class BuyModal(discord.ui.Modal):
    def __init__(self, code):
        name = ITEMS[code][1] if code in ITEMS else "สินค้า"
        super().__init__(title=f"ซื้อ {name}"[:45])
        self.code = code
        self.amount_in = discord.ui.TextInput(label=f"จำนวน (1-{BUY_LIMIT})", default="1", max_length=2)
        self.add_item(self.amount_in)

    async def on_submit(self, i: discord.Interaction):
        try:
            n = int(self.amount_in.value.strip())
        except ValueError:
            return await i.response.send_message("กรุณากรอกจำนวนเป็นตัวเลข", ephemeral=True)
        await do_buy(i, self.code, n)


async def do_buy(i, key, amount):
    if key not in ITEMS:
        return await i.response.send_message("สินค้านี้ถูกถอนออกจากร้านแล้ว", ephemeral=True)
    day = today()
    uid = i.user.id
    price = day_info(day)[key][0]
    left = get_stock(day, key)
    row = db.execute("SELECT qty FROM bought WHERE day=? AND user_id=? AND item=?", (day, uid, key)).fetchone()
    used = row[0] if row else 0
    if amount < 1 or used + amount > BUY_LIMIT:
        return await i.response.send_message(f"ซื้อได้วันละไม่เกิน {BUY_LIMIT} ชิ้นต่อสินค้า (วันนี้คุณซื้อไปแล้ว {used})", ephemeral=True)
    if amount > left:
        return await i.response.send_message(f"ของเหลือแค่ {left} ชิ้น", ephemeral=True)
    total = price * amount
    if coins(uid) < total:
        return await i.response.send_message(f"เหรียญไม่พอ ต้องใช้ {total} (คุณมี {coins(uid)})", ephemeral=True)
    add_coins(uid, -total)
    add_item(uid, key, amount)
    db.execute("UPDATE stock SET remain = remain - ? WHERE day=? AND item=?", (amount, day, key))
    db.execute("INSERT INTO bought (day, user_id, item, qty) VALUES (?,?,?,?) ON CONFLICT(day, user_id, item) DO UPDATE SET qty = qty + ?", (day, uid, key, amount, amount))
    db.commit()
    text = f"{EMO_TITLE}\n{FENCE}ซื้อสำเร็จ{FENCE}\n{item_name(key)} × __**{amount}**__\n**จ่าย:** __**{total}**__ {CUR_EMO} (ชิ้นละ {price})\n**สินค้าในร้านเหลือ:** __**{left - amount}**__ ชิ้น\n**เหรียญคงเหลือ:** __**{coins(uid)}**__ {CUR_EMO}"
    await i.response.send_message(embed=pretty(text))
    await refresh_boards(i.client)


async def send_info(i, key):
    if key not in ITEMS:
        return await i.response.send_message("สินค้านี้ถูกถอนออกจากร้านแล้ว", ephemeral=True)
    day = today()
    price, tag, _ = day_info(day)[key]
    left = get_stock(day, key)
    row = db.execute("SELECT qty FROM bought WHERE day=? AND user_id=? AND item=?", (day, i.user.id, key)).fetchone()
    used = row[0] if row else 0
    sell = round(price * SELL_RATE)
    text = (f"{EMO_TITLE}\n{FENCE}{ITEMS[key][1]}{FENCE}\n{item_name(key)}\n"
            f"**ราคา:** __**{price}**__ {CUR_EMO} · **รับซื้อ:** **{sell}**\n{TAG_TEXT[tag]}\n"
            f"**เหลือ:** __**{left}**__ ชิ้น · **วันนี้คุณซื้อได้อีก:** __**{max(0, BUY_LIMIT - used)}**__ ชิ้น")
    detail = get_detail(key)
    if detail:
        lines = "\n".join(f"- **{x.strip()}**" for x in detail.split("|") if x.strip())
        text += f"\n\n{LINE}\n{lines}"
    e = pretty(text)
    p = img_ok(key)
    if p:
        e.set_image(url=f"attachment://product_{key}.png")
        await i.response.send_message(embed=e, file=discord.File(p, filename=f"product_{key}.png"), ephemeral=True)
    else:
        await i.response.send_message(embed=e, ephemeral=True)
