import sqlite3
from typing import Union
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands, tasks

CREAM = 0xF5E6C8
ORANGE = 0xF4A261
GREEN = 0xB7E4C7
GREY = 0xADB5BD
STAFF_IDS = [1557937118456709192, 1557937214728699997]
REMIND_MIN = 15
EMO_TITLE = "<a:emoji_30:1557004201253544067>"
EMO_STATUS = "<a:emoji_22:1557002516053500015>"
EMO_PEOPLE = "<a:emoji_18:1557001713225965578>"
EMO_TIME = "<a:emoji_52:1557675194015940609>"

db = sqlite3.connect("events.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER, message_id INTEGER, title TEXT, detail TEXT, start_ts INTEGER, voice_id INTEGER, host_id INTEGER, status TEXT DEFAULT 'open', reminded INTEGER DEFAULT 0, started INTEGER DEFAULT 0, rules TEXT DEFAULT '')")
db.execute("CREATE TABLE IF NOT EXISTS attendees (event_id INTEGER, user_id INTEGER, PRIMARY KEY (event_id, user_id))")
db.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)")
db.commit()


def is_staff(member):
    return member.id == member.guild.owner_id or any(r.id in STAFF_IDS for r in member.roles)


def attendee_ids(event_id):
    rows = db.execute("SELECT user_id FROM attendees WHERE event_id=?", (event_id,)).fetchall()
    return [r[0] for r in rows]


def format_rules(rules_text):
    items = [r.strip() for r in (rules_text or "").split("|") if r.strip()]
    if not items:
        return ""
    lines = "\n".join(f"**{i+1}.** {r}" for i, r in enumerate(items))
    return f"📜 __**กติกา**__\n{lines}\n\n"


def build_embed(ev):
    eid, title, detail, start_ts, voice_id, host_id, status, rules = ev
    ids = attendee_ids(eid)
    n = len(ids)
    color = {"open": CREAM, "soon": ORANGE, "live": GREEN, "done": GREY, "cancel": GREY}.get(status, CREAM)
    label = {"open": "", "soon": "ใกล้เริ่มแล้ว", "live": "กำลังจัดอยู่", "done": "จบแล้ว", "cancel": "ยกเลิกแล้ว"}[status]
    names = " ".join(f"<@{i}>" for i in ids[:20]) or "ยังไม่มีผู้เข้าร่วม"
    if n > 20:
        names += f"\nและอีก **{n - 20}** คน"
    desc = f"# {EMO_TITLE} {title}\n"
    if label:
        desc += f"{EMO_STATUS} **{label}**\n"
    desc += f"> {EMO_TIME} __**<t:{start_ts}:F>**__\n> เริ่ม <t:{start_ts}:R>\n\n"
    if detail:
        desc += f"{detail}\n\n"
    desc += format_rules(rules)
    if voice_id:
        desc += f"🎧 ห้องเสียง: __<#{voice_id}>__\n"
    desc += f"{EMO_PEOPLE} ผู้เข้าร่วม: __**{n} คน**__\n{names}\n"
    desc += "\n⚠️ __กดปุ่มเข้าร่วมก่อนเริ่ม เพื่อรับการแจ้งเตือน__"
    e = discord.Embed(description=desc, color=color)
    e.set_footer(text="Bakery House Events")
    return e


def get_event(eid):
    return db.execute(
        "SELECT id, title, detail, start_ts, voice_id, host_id, status, rules FROM events WHERE id=?",
        (eid,),
    ).fetchone()


class EventView(discord.ui.View):
    def __init__(self, eid):
        super().__init__(timeout=None)
        self.eid = eid
        join = discord.ui.Button(label="เข้าร่วม", emoji="✅", style=discord.ButtonStyle.success, custom_id=f"ev_join_{eid}")
        leave = discord.ui.Button(label="ยกเลิก", emoji="❌", style=discord.ButtonStyle.secondary, custom_id=f"ev_leave_{eid}")
        join.callback = self.on_join
        leave.callback = self.on_leave
        self.add_item(join)
        self.add_item(leave)

    async def _refresh(self, interaction):
        ev = get_event(self.eid)
        await interaction.response.edit_message(embed=build_embed(ev), view=self)

    async def on_join(self, interaction: discord.Interaction):
        ev = get_event(self.eid)
        if not ev or ev[6] in ("done", "cancel"):
            return await interaction.response.send_message("กิจกรรมนี้ปิดแล้ว", ephemeral=True)
        db.execute("INSERT OR IGNORE INTO attendees (event_id, user_id) VALUES (?,?)", (self.eid, interaction.user.id))
        db.commit()
        await self._refresh(interaction)

    async def on_leave(self, interaction: discord.Interaction):
        ev = get_event(self.eid)
        if not ev or ev[6] in ("done", "cancel"):
            return await interaction.response.send_message("กิจกรรมนี้ปิดแล้ว", ephemeral=True)
        db.execute("DELETE FROM attendees WHERE event_id=? AND user_id=?", (self.eid, interaction.user.id))
        db.commit()
        await self._refresh(interaction)


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticker.start()

    def cog_unload(self):
        self.ticker.cancel()

    group = app_commands.Group(name="event", description="ระบบกิจกรรม", default_permissions=discord.Permissions(administrator=True))

    @group.command(name="ตั้งห้อง", description="ตั้งห้องประกาศกิจกรรม (ทีมงาน)")
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
        db.execute("INSERT OR REPLACE INTO settings (guild_id, channel_id) VALUES (?,?)", (interaction.guild.id, channel.id))
        db.commit()
        await interaction.response.send_message(f"ตั้งห้องประกาศเป็น {channel.mention} แล้ว")

    @group.command(name="สร้าง", description="สร้างกิจกรรม (ทีมงาน)")
    @app_commands.describe(title="ชื่อกิจกรรม", date="วันที่ เช่น 18/10/2026", time="เวลา เช่น 20:00", voice="ห้องเสียง", detail="รายละเอียด", rules="กฎ คั่นด้วย |")
    async def create(self, interaction: discord.Interaction, title: str, date: str, time: str,
                     voice: Union[discord.VoiceChannel, discord.StageChannel] = None, detail: str = "", rules: str = ""):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
        try:
            d = date.strip().replace("-", "/").replace(".", "/")
            t = time.strip().replace(".", ":").replace("น", "").strip()
            dd, mm, yy = [int(x) for x in d.split("/")]
            if yy > 2400:
                yy -= 543
            hh, mi = [int(x) for x in t.split(":")]
            dt = datetime(yy, mm, dd, hh, mi, tzinfo=timezone(timedelta(hours=7)))
        except ValueError:
            return await interaction.response.send_message("รูปแบบวันเวลาไม่ถูก ใช้ เช่น 18/10/2026 และ 20:00", ephemeral=True)
        ts = int(dt.timestamp())
        row = db.execute("SELECT channel_id FROM settings WHERE guild_id=?", (interaction.guild.id,)).fetchone()
        ch = interaction.guild.get_channel(row[0]) if row else interaction.channel
        cur = db.execute(
            "INSERT INTO events (guild_id, channel_id, title, detail, start_ts, voice_id, host_id, rules) VALUES (?,?,?,?,?,?,?,?)",
            (interaction.guild.id, ch.id, title, detail, ts, voice.id if voice else None, interaction.user.id, rules))
        db.commit()
        eid = cur.lastrowid
        msg = await ch.send(embed=build_embed(get_event(eid)), view=EventView(eid))
        db.execute("UPDATE events SET message_id=? WHERE id=?", (msg.id, eid))
        db.commit()
        await interaction.response.send_message(f"สร้างกิจกรรม #{eid} แล้ว: {msg.jump_url}", ephemeral=True)

    @group.command(name="รายการ", description="ดูกิจกรรมที่กำลังจะมาถึง")
    async def list_events(self, interaction: discord.Interaction):
        rows = db.execute(
            "SELECT id, title, start_ts FROM events WHERE guild_id=? AND status IN ('open','soon','live') ORDER BY start_ts LIMIT 10",
            (interaction.guild.id,)).fetchall()
        if not rows:
            return await interaction.response.send_message("ยังไม่มีกิจกรรม", ephemeral=True)
        text = "\n".join(f"**#{i}** {t} — <t:{ts}:R>" for i, t, ts in rows)
        await interaction.response.send_message(embed=discord.Embed(title="📅 กิจกรรมที่กำลังจะมาถึง", description=text, color=CREAM))


    @group.command(name="เพิ่มกฎ", description="เพิ่มกฎให้กิจกรรม (ทีมงาน)")
    async def add_rule(self, interaction: discord.Interaction, event_id: int, rule: str):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
        row = db.execute("SELECT rules FROM events WHERE id=? AND guild_id=?", (event_id, interaction.guild.id)).fetchone()
        if not row:
            return await interaction.response.send_message("ไม่พบกิจกรรมนี้", ephemeral=True)
        new = (row[0] + " | " if row[0] else "") + rule.replace("|", "/")
        db.execute("UPDATE events SET rules=? WHERE id=?", (new, event_id))
        db.commit()
        await self.refresh_message(event_id)
        await interaction.response.send_message("เพิ่มกฎแล้ว", ephemeral=True)

    @group.command(name="ลบกฎ", description="ลบกฎตามข้อ (ทีมงาน)")
    async def del_rule(self, interaction: discord.Interaction, event_id: int, number: int):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
        row = db.execute("SELECT rules FROM events WHERE id=? AND guild_id=?", (event_id, interaction.guild.id)).fetchone()
        items = [r.strip() for r in (row[0] if row else "").split("|") if r.strip()]
        if not row or not 1 <= number <= len(items):
            return await interaction.response.send_message("ไม่พบกิจกรรมหรือข้อที่ระบุ", ephemeral=True)
        items.pop(number - 1)
        db.execute("UPDATE events SET rules=? WHERE id=?", (" | ".join(items), event_id))
        db.commit()
        await self.refresh_message(event_id)
        await interaction.response.send_message("ลบกฎแล้ว", ephemeral=True)

    @group.command(name="ยกเลิก", description="ยกเลิกกิจกรรม (ทีมงาน)")
    async def cancel(self, interaction: discord.Interaction, event_id: int):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
        db.execute("UPDATE events SET status='cancel' WHERE id=? AND guild_id=?", (event_id, interaction.guild.id))
        db.commit()
        await self.refresh_message(event_id)
        await interaction.response.send_message("ยกเลิกกิจกรรมแล้ว", ephemeral=True)

    async def refresh_message(self, eid):
        row = db.execute("SELECT channel_id, message_id FROM events WHERE id=?", (eid,)).fetchone()
        if not row or not row[1]:
            return
        ch = self.bot.get_channel(row[0])
        if not ch:
            return
        try:
            msg = await ch.fetch_message(row[1])
            await msg.edit(embed=build_embed(get_event(eid)))
        except Exception:
            pass

    @tasks.loop(seconds=30)
    async def ticker(self):
        now = int(datetime.now().timestamp())
        rows = db.execute("SELECT id, channel_id, title, start_ts, voice_id, reminded, started, status FROM events WHERE status IN ('open','soon','live')").fetchall()
        for eid, chid, title, ts, voice_id, reminded, started, status in rows:
            if not reminded and 0 < ts - now <= REMIND_MIN * 60:
                db.execute("UPDATE events SET reminded=1, status='soon' WHERE id=?", (eid,))
                db.commit()
                await self.refresh_message(eid)
                for uid in attendee_ids(eid):
                    user = self.bot.get_user(uid)
                    if user:
                        try:
                            await user.send(embed=discord.Embed(
                                title="⏰ กิจกรรมใกล้เริ่มแล้ว",
                                description=f"**{title}**\nเริ่ม <t:{ts}:R>" + (f"\nห้องเสียง: <#{voice_id}>" if voice_id else ""),
                                color=ORANGE))
                        except Exception:
                            pass
            if not started and ts <= now:
                db.execute("UPDATE events SET started=1, status='live' WHERE id=?", (eid,))
                db.commit()
                await self.refresh_message(eid)
                ch = self.bot.get_channel(chid)
                if ch:
                    ids = attendee_ids(eid)
                    mention = " ".join(f"<@{i}>" for i in ids[:30])
                    await ch.send(embed=discord.Embed(title="🎉 กิจกรรมเริ่มแล้ว!", description=f"**{title}**\n{mention}", color=GREEN))
            if started and ts + 3 * 3600 <= now:
                db.execute("UPDATE events SET status='done' WHERE id=?", (eid,))
                db.commit()
                await self.refresh_message(eid)

    @ticker.before_loop
    async def before_ticker(self):
        await self.bot.wait_until_ready()


async def setup_events(bot):
    await bot.add_cog(Events(bot))
    for (eid,) in db.execute("SELECT id FROM events WHERE status IN ('open','soon','live')").fetchall():
        bot.add_view(EventView(eid))
