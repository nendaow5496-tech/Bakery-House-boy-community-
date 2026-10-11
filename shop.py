import discord
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from discord import app_commands
from discord.ext import commands, tasks

CREAM = 0xF5E6C8
CUR = "Bakery Coin"
CUR_EMO = "<a:emoji_54:1558668750142570577>"
TZ = timezone(timedelta(hours=7))
DAILY_REWARD = 100
VOICE_PAY = 5
BUY_LIMIT = 5
SELL_RATE = 0.9
TAX = 0.05
MAX_LISTINGS = 5
STAFF_ROLES = [1557937118456709192]
FENCE = "`" * 3
EMO_TITLE = "<a:emoji_18:1557001713225965578>"
LINE = "▬" * 14

ITEMS = {
    "bread": ("🍞", "ขนมปัง", 40, 20),
    "cookie": ("🍪", "คุกกี้", 30, 25),
    "donut": ("🍩", "โดนัท", 60, 15),
    "croissant": ("🥐", "ครัวซองต์", 80, 12),
    "pie": ("🥧", "พาย", 110, 10),
    "cupcake": ("🧁", "คัพเค้ก", 130, 10),
    "cake": ("🍰", "เค้ก", 180, 8),
    "choco": ("🍫", "ช็อกโกแลต", 150, 8),
}
ITEM_CHOICES = [app_commands.Choice(name=f"{v[0]} {v[1]}", value=k) for k, v in ITEMS.items()]
TAGS = {"good": "🔥 ราคาดี", "low": "🏷️ ราคาต่ำ", "norm": ""}

shop = app_commands.Group(name="shop", description="ร้านค้าเบเกอรี่")
game = app_commands.Group(name="game", description="เกมและเหรียญ")

db = sqlite3.connect("shop.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS wallets (user_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0, last_daily TEXT DEFAULT '')")
db.execute("CREATE TABLE IF NOT EXISTS inv (user_id INTEGER, item TEXT, qty INTEGER DEFAULT 0, PRIMARY KEY (user_id, item))")
db.execute("CREATE TABLE IF NOT EXISTS stock (day TEXT, item TEXT, remain INTEGER, PRIMARY KEY (day, item))")
db.execute("CREATE TABLE IF NOT EXISTS bought (day TEXT, user_id INTEGER, item TEXT, qty INTEGER DEFAULT 0, PRIMARY KEY (day, user_id, item))")
db.execute("CREATE TABLE IF NOT EXISTS vtime (user_id INTEGER PRIMARY KEY, mins INTEGER DEFAULT 0)")
db.execute("CREATE TABLE IF NOT EXISTS shop_set (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, last_ann TEXT DEFAULT '')")
db.execute("CREATE TABLE IF NOT EXISTS market (id INTEGER PRIMARY KEY AUTOINCREMENT, seller INTEGER, item TEXT, qty INTEGER, price INTEGER, created INTEGER)")
db.commit()


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def tomorrow():
    return (datetime.now(TZ) + timedelta(days=1)).strftime("%Y-%m-%d")


def day_info(day):
    keys = sorted(ITEMS, key=lambda x: random.Random(f"{day}-tag-{x}").random())
    info = {}
    for n, k in enumerate(keys):
        r = random.Random(f"{day}-{k}")
        base = ITEMS[k][2]
        if n < 2:
            tag, mul = "good", r.uniform(1.5, 1.8)
        elif n < 4:
            tag, mul = "low", r.uniform(0.55, 0.7)
        else:
            tag, mul = "norm", r.uniform(0.9, 1.1)
        stock = max(3, int(ITEMS[k][3] * r.uniform(0.7, 1.3)))
        info[k] = (max(1, round(base * mul)), tag, stock)
    return info


def get_stock(day, key):
    row = db.execute("SELECT remain FROM stock WHERE day=? AND item=?", (day, key)).fetchone()
    if row:
        return row[0]
    n = day_info(day)[key][2]
    db.execute("INSERT INTO stock (day, item, remain) VALUES (?,?,?)", (day, key, n))
    db.commit()
    return n


def coins(uid):
    r = db.execute("SELECT coins FROM wallets WHERE user_id=?", (uid,)).fetchone()
    return r[0] if r else 0


def add_coins(uid, n):
    db.execute("INSERT INTO wallets (user_id, coins) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET coins = coins + ?", (uid, n, n))
    db.execute("UPDATE wallets SET coins=0 WHERE user_id=? AND coins<0", (uid,))
    db.commit()


def have(uid, key):
    r = db.execute("SELECT qty FROM inv WHERE user_id=? AND item=?", (uid, key)).fetchone()
    return r[0] if r else 0


def add_item(uid, key, n):
    db.execute("INSERT INTO inv (user_id, item, qty) VALUES (?,?,?) ON CONFLICT(user_id, item) DO UPDATE SET qty = qty + ?", (uid, key, n, n))
    db.execute("DELETE FROM inv WHERE user_id=? AND item=? AND qty<=0", (uid, key))
    db.commit()


def item_name(key):
    return f"{ITEMS[key][0]} {ITEMS[key][1]}"


def is_admin(i):
    u = i.user
    if i.guild and u.id == i.guild.owner_id:
        return True
    perms = getattr(u, "guild_permissions", None)
    if perms and perms.administrator:
        return True
    return any(r.id in STAFF_ROLES for r in getattr(u, "roles", []))


def shop_embed():
    day = today()
    info = day_info(day)
    lines = []
    for k in ITEMS:
        price, tag, _ = info[k]
        left = get_stock(day, k)
        sell = round(price * SELL_RATE)
        mark = f"  {TAGS[tag]}" if tag != "norm" else ""
        lines.append(f"{item_name(k)} — ซื้อ __**{price}**__ · รับซื้อ **{sell}** {CUR_EMO} · เหลือ __**{left}**__{mark}")
    text = f"{EMO_TITLE}\n{FENCE}ร้านเบเกอรี่วันนี้{FENCE}\n" + "\n".join(lines)
    text += f"\n\n**ซื้อได้วันละไม่เกิน {BUY_LIMIT} ชิ้นต่อสินค้า · ราคาใหม่ตอนเที่ยงคืน**"
    return pretty(text)


def announce_embed(day):
    info = day_info(day)
    good = [k for k in ITEMS if info[k][1] == "good"]
    low = [k for k in ITEMS if info[k][1] == "low"]
    g = "\n".join(f"{item_name(k)} — รับซื้อ __**{round(info[k][0] * SELL_RATE)}**__ {CUR_EMO}" for k in good)
    lo = "\n".join(f"{item_name(k)} — ซื้อได้ __**{info[k][0]}**__ {CUR_EMO}" for k in low)
    text = f"{EMO_TITLE}\n{FENCE}ประกาศราคาพรุ่งนี้{FENCE}\n**🔥 ราคาดี (ขายได้แพง)**\n{g}\n\n**🏷️ ราคาต่ำ (ซื้อถูก)**\n{lo}\n\n__**ราคาใหม่เริ่มตอนเที่ยงคืน**__"
    return pretty(text)


class ShopRefresh(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="รีเฟรช", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.edit_message(embed=shop_embed(), view=self)


@shop.command(name="view", description="ดูของในร้านและราคาวันนี้")
async def shop_view(i: discord.Interaction):
    await i.response.send_message(embed=shop_embed(), view=ShopRefresh())


@shop.command(name="buy", description="ซื้อของจากร้าน")
@app_commands.describe(item="สินค้า", amount="จำนวน")
async def shop_buy(i: discord.Interaction, item: str, amount: app_commands.Range[int, 1, 50] = 1):
    key = item
    if key not in ITEMS:
        return await i.response.send_message("กรุณาเลือกสินค้าจากรายการที่ขึ้นให้", ephemeral=True)
    day = today()
    uid = i.user.id
    price = day_info(day)[key][0]
    left = get_stock(day, key)
    row = db.execute("SELECT qty FROM bought WHERE day=? AND user_id=? AND item=?", (day, uid, key)).fetchone()
    used = row[0] if row else 0
    if used + amount > BUY_LIMIT:
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


@shop.command(name="sell", description="ขายของคืนให้ร้าน")
@app_commands.describe(item="สินค้า", amount="จำนวน")
async def shop_sell(i: discord.Interaction, item: str, amount: app_commands.Range[int, 1, 50] = 1):
    key = item
    if key not in ITEMS:
        return await i.response.send_message("กรุณาเลือกสินค้าจากรายการที่ขึ้นให้", ephemeral=True)
    day = today()
    uid = i.user.id
    if have(uid, key) < amount:
        return await i.response.send_message("คุณมีของไม่พอ ลอง /shop bag ดู", ephemeral=True)
    total = round(day_info(day)[key][0] * SELL_RATE) * amount
    get_stock(day, key)
    add_item(uid, key, -amount)
    add_coins(uid, total)
    db.execute("UPDATE stock SET remain = remain + ? WHERE day=? AND item=?", (amount, day, key))
    db.commit()
    text = f"{EMO_TITLE}\n{FENCE}ขายสำเร็จ{FENCE}\n{item_name(key)} × __**{amount}**__\n**ได้รับ:** __**{total}**__ {CUR_EMO}\n**คงเหลือ:** __**{coins(uid)}**__ {CUR_EMO}"
    await i.response.send_message(embed=pretty(text))


@shop.command(name="bag", description="ดูเหรียญและของในกระเป๋า")
async def shop_bag(i: discord.Interaction):
    uid = i.user.id
    info = day_info(today())
    rows = db.execute("SELECT item, qty FROM inv WHERE user_id=? AND qty>0", (uid,)).fetchall()
    lines = [f"{item_name(k)} × __**{q}**__ (รับซื้อชิ้นละ {round(info[k][0] * SELL_RATE)})" for k, q in rows if k in ITEMS]
    text = f"{EMO_TITLE}\n{FENCE}กระเป๋าของคุณ{FENCE}\n**{CUR_EMO} {CUR}:** __**{coins(uid)}**__\n\n" + ("\n".join(lines) or "**ยังไม่มีของในกระเป๋า**")
    await i.response.send_message(embed=pretty(text))


@shop.command(name="post", description="ลงขายของในตลาดผู้เล่น")
@app_commands.describe(item="สินค้า", amount="จำนวน", price="ราคารวมทั้งหมด")
async def shop_post(i: discord.Interaction, item: str, amount: app_commands.Range[int, 1, 50], price: app_commands.Range[int, 1, 100000]):
    uid = i.user.id
    if item not in ITEMS:
        return await i.response.send_message("กรุณาเลือกสินค้าจากรายการที่ขึ้นให้", ephemeral=True)
    n = db.execute("SELECT COUNT(*) FROM market WHERE seller=?", (uid,)).fetchone()[0]
    if n >= MAX_LISTINGS:
        return await i.response.send_message(f"ลงขายพร้อมกันได้ไม่เกิน {MAX_LISTINGS} รายการ", ephemeral=True)
    if have(uid, item) < amount:
        return await i.response.send_message("คุณมีของไม่พอ ลอง /shop bag ดู", ephemeral=True)
    add_item(uid, item, -amount)
    cur = db.execute("INSERT INTO market (seller, item, qty, price, created) VALUES (?,?,?,?,?)", (uid, item, amount, price, int(time.time())))
    db.commit()
    text = f"{EMO_TITLE}\n{FENCE}ลงขายแล้ว{FENCE}\n**รายการ #{cur.lastrowid}** {item_name(item)} × __**{amount}**__\n**ราคารวม:** __**{price}**__ {CUR_EMO}\n**ยกเลิกได้ด้วย** /shop cancel"
    await i.response.send_message(embed=pretty(text))


@shop.command(name="market", description="ดูรายการขายของผู้เล่น")
async def shop_market(i: discord.Interaction):
    rows = db.execute("SELECT id, seller, item, qty, price FROM market ORDER BY id DESC LIMIT 15").fetchall()
    lines = [f"**#{lid}** {item_name(k)} × __**{q}**__ — __**{p}**__ {CUR_EMO} โดย <@{s}>" for lid, s, k, q, p in rows if k in ITEMS]
    text = f"{EMO_TITLE}\n{FENCE}ตลาดผู้เล่น{FENCE}\n" + ("\n".join(lines) or "**ยังไม่มีรายการขาย**")
    text += "\n\n**ซื้อด้วย** /shop take **ใส่เลขรายการ**"
    await i.response.send_message(embed=pretty(text))


@shop.command(name="take", description="ซื้อของจากตลาดผู้เล่น")
@app_commands.describe(listing="เลขรายการ เช่น 3")
async def shop_take(i: discord.Interaction, listing: int):
    uid = i.user.id
    r = db.execute("SELECT seller, item, qty, price FROM market WHERE id=?", (listing,)).fetchone()
    if not r:
        return await i.response.send_message("ไม่พบรายการนี้ (อาจถูกซื้อไปแล้ว)", ephemeral=True)
    s, k, q, p = r
    if s == uid:
        return await i.response.send_message("ซื้อของตัวเองไม่ได้ ใช้ /shop cancel เพื่อยกเลิก", ephemeral=True)
    if coins(uid) < p:
        return await i.response.send_message(f"เหรียญไม่พอ ต้องใช้ {p} (คุณมี {coins(uid)})", ephemeral=True)
    fee = int(p * TAX)
    db.execute("DELETE FROM market WHERE id=?", (listing,))
    db.commit()
    add_coins(uid, -p)
    add_coins(s, p - fee)
    add_item(uid, k, q)
    text = f"{EMO_TITLE}\n{FENCE}ซื้อจากตลาดสำเร็จ{FENCE}\n{item_name(k)} × __**{q}**__ จาก <@{s}>\n**จ่าย:** __**{p}**__ {CUR_EMO} (ผู้ขายได้ {p - fee} หลังหักภาษี {int(TAX * 100)}%)"
    await i.response.send_message(embed=pretty(text))


@shop.command(name="cancel", description="ยกเลิกรายการขายของคุณ")
@app_commands.describe(listing="เลขรายการ")
async def shop_cancel(i: discord.Interaction, listing: int):
    r = db.execute("SELECT seller, item, qty FROM market WHERE id=?", (listing,)).fetchone()
    if not r or (r[0] != i.user.id and not is_admin(i)):
        return await i.response.send_message("ไม่พบรายการของคุณ", ephemeral=True)
    db.execute("DELETE FROM market WHERE id=?", (listing,))
    db.commit()
    add_item(r[0], r[1], r[2])
    await i.response.send_message(f"ยกเลิกรายการ #{listing} แล้ว คืนของเข้ากระเป๋าให้เรียบร้อย")


@shop.command(name="setchannel", description="ตั้งห้องประกาศราคา (ทีมงาน)")
async def shop_setchannel(i: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(i):
        return await i.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
    db.execute("INSERT INTO shop_set (guild_id, channel_id) VALUES (?,?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=?", (i.guild.id, channel.id, channel.id))
    db.commit()
    await i.response.send_message(f"ตั้งห้องประกาศราคาเป็น {channel.mention} แล้ว จะประกาศทุกวันเวลา 23:00")


@shop.command(name="give", description="เพิ่ม/ลดเหรียญให้สมาชิก (ทีมงาน)")
async def shop_give(i: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, -100000, 100000]):
    if not is_admin(i):
        return await i.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
    add_coins(user.id, amount)
    await i.response.send_message(f"ปรับเหรียญของ {user.mention} {amount:+d} แล้ว (ตอนนี้มี {coins(user.id)})")


@game.command(name="daily", description="รับเหรียญประจำวัน")
async def game_daily(i: discord.Interaction):
    day = today()
    uid = i.user.id
    r = db.execute("SELECT last_daily FROM wallets WHERE user_id=?", (uid,)).fetchone()
    if r and r[0] == day:
        return await i.response.send_message("วันนี้คุณรับไปแล้ว กลับมาใหม่หลังเที่ยงคืนนะ", ephemeral=True)
    add_coins(uid, DAILY_REWARD)
    db.execute("UPDATE wallets SET last_daily=? WHERE user_id=?", (day, uid))
    db.commit()
    text = f"{EMO_TITLE}\n{FENCE}รับเหรียญประจำวัน{FENCE}\n**ได้รับ:** __**{DAILY_REWARD}**__ {CUR_EMO}\n**คงเหลือ:** __**{coins(uid)}**__ {CUR_EMO}"
    await i.response.send_message(embed=pretty(text))


async def buy_ac(i: discord.Interaction, current: str):
    day = today()
    info = day_info(day)
    cur = (current or "").lower()
    out = []
    for k in ITEMS:
        if cur and cur not in ITEMS[k][1].lower() and cur not in k:
            continue
        price, tag, _ = info[k]
        left = get_stock(day, k)
        mark = " 🔥" if tag == "good" else (" 🏷️" if tag == "low" else "")
        label = f"{item_name(k)} · ราคา {price} · เหลือ {left}{mark}"
        out.append(app_commands.Choice(name=label[:100], value=k))
    return out[:25]


shop_buy.autocomplete("item")(buy_ac)


def pretty(text):
    e = discord.Embed(description=text, color=CREAM, timestamp=datetime.now(TZ))
    e.set_footer(text="Bakery House • ร้านเบเกอรี่")
    return e


def shop_embed():
    day = today()
    info = day_info(day)
    groups = {"good": [], "low": [], "norm": []}
    for k in ITEMS:
        price, tag, _ = info[k]
        left = get_stock(day, k)
        sell = round(price * SELL_RATE)
        status = f"เหลือ __**{left}**__" if left > 0 else "**หมด**"
        groups[tag].append(f"{item_name(k)} — __**{price}**__ {CUR_EMO}\n> รับซื้อ **{sell}** · {status}")
    parts = [f"{EMO_TITLE}\n{FENCE}ร้านเบเกอรี่วันนี้{FENCE}"]
    heads = (("good", "🔥 **ราคาดี — ขายได้แพง**"), ("low", "🏷️ **ราคาต่ำ — ซื้อถูก**"), ("norm", "🛒 **สินค้าทั่วไป**"))
    for tag, head in heads:
        if groups[tag]:
            parts.append(head + "\n" + "\n".join(groups[tag]))
    parts.append(f"{LINE}\n**ซื้อได้วันละไม่เกิน {BUY_LIMIT} ชิ้น/สินค้า · ราคาใหม่ตอนเที่ยงคืน**")
    return pretty("\n\n".join(parts))


def announce_embed(day):
    info = day_info(day)
    good = [k for k in ITEMS if info[k][1] == "good"]
    low = [k for k in ITEMS if info[k][1] == "low"]
    g = "\n".join(f"{item_name(k)} — รับซื้อ __**{round(info[k][0] * SELL_RATE)}**__ {CUR_EMO}" for k in good)
    lo = "\n".join(f"{item_name(k)} — ซื้อได้ __**{info[k][0]}**__ {CUR_EMO}" for k in low)
    text = (f"{EMO_TITLE}\n{FENCE}ประกาศราคาพรุ่งนี้{FENCE}\n"
            f"🔥 **ราคาดี — ขายได้แพง**\n{g}\n\n"
            f"🏷️ **ราคาต่ำ — ซื้อถูก**\n{lo}\n\n"
            f"{LINE}\n__**ราคาใหม่เริ่มตอนเที่ยงคืน**__")
    return pretty(text)


def pretty(text):
    e = discord.Embed(description=text, color=CREAM, timestamp=datetime.now(TZ))
    e.set_footer(text="Bakery House • ร้านเบเกอรี่")
    return e


def shop_embed():
    day = today()
    info = day_info(day)
    groups = {"good": [], "low": [], "norm": []}
    for k in ITEMS:
        price, tag, _ = info[k]
        left = get_stock(day, k)
        sell = round(price * SELL_RATE)
        status = f"เหลือ __**{left}**__" if left > 0 else "**หมด**"
        groups[tag].append(f"{item_name(k)} — __**{price}**__ {CUR_EMO}\n> รับซื้อ **{sell}** · {status}")
    parts = [f"{EMO_TITLE}\n{FENCE}ร้านเบเกอรี่วันนี้{FENCE}"]
    heads = (("good", "🔥 **ราคาดี — ขายได้แพง**"), ("low", "🏷️ **ราคาต่ำ — ซื้อถูก**"), ("norm", "🛒 **สินค้าทั่วไป**"))
    for tag, head in heads:
        if groups[tag]:
            parts.append(head + "\n" + "\n".join(groups[tag]))
    parts.append(f"{LINE}\n**ซื้อได้วันละไม่เกิน {BUY_LIMIT} ชิ้น/สินค้า · ราคาใหม่ตอนเที่ยงคืน**")
    return pretty("\n\n".join(parts))


def announce_embed(day):
    info = day_info(day)
    good = [k for k in ITEMS if info[k][1] == "good"]
    low = [k for k in ITEMS if info[k][1] == "low"]
    g = "\n".join(f"{item_name(k)} — รับซื้อ __**{round(info[k][0] * SELL_RATE)}**__ {CUR_EMO}" for k in good)
    lo = "\n".join(f"{item_name(k)} — ซื้อได้ __**{info[k][0]}**__ {CUR_EMO}" for k in low)
    text = (f"{EMO_TITLE}\n{FENCE}ประกาศราคาพรุ่งนี้{FENCE}\n"
            f"🔥 **ราคาดี — ขายได้แพง**\n{g}\n\n"
            f"🏷️ **ราคาต่ำ — ซื้อถูก**\n{lo}\n\n"
            f"{LINE}\n__**ราคาใหม่เริ่มตอนเที่ยงคืน**__")
    return pretty(text)


async def item_ac(i: discord.Interaction, current: str):
    cur = (current or "").lower()
    out = []
    for k, v in ITEMS.items():
        if cur and cur not in v[1].lower() and cur not in k.lower():
            continue
        out.append(app_commands.Choice(name=f"{v[1]} · คุณมี {have(i.user.id, k)}"[:100], value=k))
    return out[:25]


shop_sell.autocomplete("item")(item_ac)
shop_post.autocomplete("item")(item_ac)


class ShopLoops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announce_loop.start()
        self.voice_loop.start()

    def cog_unload(self):
        self.announce_loop.cancel()
        self.voice_loop.cancel()

    @tasks.loop(minutes=1)
    async def announce_loop(self):
        if datetime.now(TZ).hour != 23:
            return
        day = tomorrow()
        rows = db.execute("SELECT guild_id, channel_id, last_ann FROM shop_set WHERE channel_id IS NOT NULL").fetchall()
        for gid, cid, last in rows:
            if last == day:
                continue
            ch = self.bot.get_channel(cid)
            if not ch:
                continue
            try:
                await ch.send(embed=announce_embed(day))
            except Exception as e:
                print("shop announce error:", e, flush=True)
                continue
            db.execute("UPDATE shop_set SET last_ann=? WHERE guild_id=?", (day, gid))
            db.commit()

    @announce_loop.before_loop
    async def before_announce(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def voice_loop(self):
        for g in self.bot.guilds:
            for vc in list(g.voice_channels) + list(g.stage_channels):
                if vc == g.afk_channel:
                    continue
                for m in vc.members:
                    if m.bot or (m.voice and m.voice.self_deaf):
                        continue
                    db.execute("INSERT INTO vtime (user_id, mins) VALUES (?,5) ON CONFLICT(user_id) DO UPDATE SET mins = mins + 5", (m.id,))
                    mins = db.execute("SELECT mins FROM vtime WHERE user_id=?", (m.id,)).fetchone()[0]
                    if mins >= 60:
                        db.execute("UPDATE vtime SET mins = mins - 60 WHERE user_id=?", (m.id,))
                        add_coins(m.id, VOICE_PAY)
        db.commit()

    @voice_loop.before_loop
    async def before_voice(self):
        await self.bot.wait_until_ready()


async def setup_shop(bot):
    bot.tree.add_command(shop)
    bot.tree.add_command(game)
    await bot.add_cog(ShopLoops(bot))
