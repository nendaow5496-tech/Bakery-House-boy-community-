import os
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands

CREAM = 0xF5E6C8
BLUE = 0xA8C8F0
GREEN = 0xB7E4C7
RED = 0xF0A8A8
STAFF_IDS = [1557937118456709192]
EMO_TITLE = "<a:emoji_18:1557001713225965578>"
EMO_NAME = EMO_TITLE
EMO_BTN = "<:emoji_12:1557001324409659442>"
IMG_DIR = "job_images"
os.makedirs(IMG_DIR, exist_ok=True)

TXT_TITLE = "รับสมัครทีมงาน"
TXT_INTRO = "เตาอบของ Bakery House กำลังรอคนมาช่วยดูแลบ้านหลังนี้ ถ้าคุณใจดี รักษาคำพูด และอยากให้ทุกคนรู้สึกอบอุ่นเวลาแวะมา เราอยากรู้จักคุณ"
TXT_CRITERIA = "คุณสมบัติที่เรามองหา"
TXT_BUTTON = "ขอดูรายละเอียด"
TXT_FOOTER = ""
BANNER = os.path.join(IMG_DIR, "banner.png")

STATUS = {
    "pending": ("⏳", "รอพิจารณา", CREAM),
    "interview": ("🗓️", "รอสัมภาษณ์", BLUE),
    "pass": ("✅", "ผ่าน", GREEN),
    "fail": ("❌", "ไม่ผ่าน", RED),
}

db = sqlite3.connect("jobs.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, name TEXT, description TEXT, conditions TEXT, benefits TEXT DEFAULT '', image TEXT, reviewer_role INTEGER, pass_role INTEGER, channel_id INTEGER, message_id INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS apps (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, job_id INTEGER, user_id INTEGER, answers TEXT, status TEXT DEFAULT 'pending', channel_id INTEGER, message_id INTEGER, itext INTEGER, ivoice INTEGER, created INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, app_channel INTEGER, category INTEGER)")
try:
    db.execute("ALTER TABLE jobs ADD COLUMN emoji TEXT DEFAULT ''")
except sqlite3.OperationalError:
    pass
for _c in ("board_channel INTEGER", "board_message INTEGER"):
    try:
        db.execute(f"ALTER TABLE settings ADD COLUMN {_c}")
    except sqlite3.OperationalError:
        pass
db.commit()


def is_staff(member):
    return member.id == member.guild.owner_id or any(r.id in STAFF_IDS for r in member.roles)


def bullets(text):
    items = [x.strip() for x in (text or "").split("|") if x.strip()]
    return "\n".join(f"- **{x}**" for x in items) or "- **ยังไม่ได้ระบุ**"


def get_job(job_id):
    return db.execute("SELECT id, name, description, conditions, image, reviewer_role, pass_role, benefits FROM jobs WHERE id=?", (job_id,)).fetchone()


def job_file(job):
    path = job[4]
    if path and os.path.exists(path):
        return discord.File(path, filename="job.png")
    return None


def job_embed(job):
    name, image = job[1], job[4]
    fence = "`" * 3
    text = f"{EMO_TITLE}\n{fence}รับสมัครทีมงาน{fence}\n"
    text += f"**ตำแหน่ง:** __**{name}**__\n\n"
    text += "**กดปุ่มด้านล่างเพื่อดูรายละเอียดตำแหน่ง**"
    e = discord.Embed(description=text, color=CREAM)
    if image and os.path.exists(image):
        e.set_image(url="attachment://job.png")
    e.set_footer(text="Bakery House Careers")
    return e


def app_embed(app, job, user):
    aid, uid, answers, status = app
    emo, label, color = STATUS[status]
    fence = "`" * 3
    pairs = [x.split("::", 1) for x in answers.split("||") if "::" in x]
    lines = "\n\n".join(f"**{q}**\n**{a}**" for q, a in pairs)
    text = f"{EMO_TITLE}\n{fence}ใบสมัคร #{aid}{fence}\n"
    text += f"**ตำแหน่ง:** __**{job[1]}**__\n"
    text += f"**ผู้สมัคร:** __**<@{uid}>**__\n"
    text += f"**สถานะ:** {emo} __**{label}**__\n"
    ex = db.execute("SELECT itime, inote FROM apps WHERE id=?", (aid,)).fetchone()
    if ex and ex[0]:
        text += f"**นัดสัมภาษณ์:** __**<t:{ex[0]}:F>**__ (<t:{ex[0]}:R>)\n"
        if ex[1]:
            text += f"**หมายเหตุ:** **{ex[1]}**\n"
    rs = db.execute("SELECT reason FROM apps WHERE id=?", (aid,)).fetchone()
    if status == "fail" and rs and rs[0]:
        text += f"**เหตุผล:** **{rs[0]}**\n"
    text += f"\n{lines}"
    e = discord.Embed(description=text, color=color)
    if user:
        e.set_thumbnail(url=user.display_avatar.url)
    if job[4] and os.path.exists(job[4]):
        e.set_image(url="attachment://job.png")
    e.set_footer(text="Bakery House Careers")
    return e


FORM_QUESTIONS = ["ชื่อเล่น และอายุ", "เหตุผลที่อยากสมัคร", "ประสบการณ์", "เวลาที่ว่างต่อวัน"]


class ApplyModal(discord.ui.Modal):
    def __init__(self, job_id, job_name):
        super().__init__(title=f"สมัคร {job_name}"[:45])
        self.job_id = job_id
        self.fields = []
        for i, q in enumerate(FORM_QUESTIONS):
            style = discord.TextStyle.paragraph if i in (1, 2) else discord.TextStyle.short
            ti = discord.ui.TextInput(label=q, style=style, max_length=500, required=(i != 2))
            self.fields.append((q, ti))
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        dup = db.execute(
            "SELECT id FROM apps WHERE guild_id=? AND job_id=? AND user_id=? AND status IN ('pending','interview')",
            (interaction.guild.id, self.job_id, interaction.user.id)).fetchone()
        if dup:
            return await interaction.response.send_message("คุณมีใบสมัครตำแหน่งนี้ที่ยังรอผลอยู่", ephemeral=True)
        row = db.execute("SELECT app_channel FROM settings WHERE guild_id=?", (interaction.guild.id,)).fetchone()
        ch = interaction.guild.get_channel(row[0]) if row and row[0] else None
        if not ch:
            return await interaction.response.send_message("ยังไม่ได้ตั้งห้องรับใบสมัคร แจ้งทีมงานด้วยครับ", ephemeral=True)
        answers = "||".join(
            f"{q}::{(t.value or '-').replace('||', '/').replace('::', ':')}" for q, t in self.fields)
        cur = db.execute(
            "INSERT INTO apps (guild_id, job_id, user_id, answers, created) VALUES (?,?,?,?,?)",
            (interaction.guild.id, self.job_id, interaction.user.id, answers, int(interaction.created_at.timestamp())))
        db.commit()
        aid = cur.lastrowid
        job = get_job(self.job_id)
        embed = app_embed((aid, interaction.user.id, answers, "pending"), job, interaction.user)
        f = job_file(job)
        if f:
            msg = await ch.send(embed=embed, file=f, view=ReviewView(aid))
        else:
            msg = await ch.send(embed=embed, view=ReviewView(aid))
        db.execute("UPDATE apps SET channel_id=?, message_id=? WHERE id=?", (ch.id, msg.id, aid))
        db.commit()
        await interaction.response.send_message(f"ส่งใบสมัครแล้ว (เลข #{aid}) รอทีมงานพิจารณาครับ", ephemeral=True)


class DetailView(discord.ui.View):
    def __init__(self, job_id):
        super().__init__(timeout=300)
        self.job_id = job_id

    @discord.ui.button(label="เงื่อนไข", emoji=EMO_BTN, style=discord.ButtonStyle.secondary)
    async def conditions(self, interaction: discord.Interaction, button: discord.ui.Button):
        job = get_job(self.job_id)
        text = f"**เงื่อนไขของตำแหน่ง** __**{job[1]}**__\n\n{bullets(job[3])}"
        await interaction.response.send_message(embed=discord.Embed(description=text, color=CREAM), ephemeral=True)

    @discord.ui.button(label="สวัสดิการ", emoji=EMO_BTN, style=discord.ButtonStyle.secondary)
    async def benefits(self, interaction: discord.Interaction, button: discord.ui.Button):
        job = get_job(self.job_id)
        text = f"**สวัสดิการของตำแหน่ง** __**{job[1]}**__\n\n{bullets(job[7])}"
        await interaction.response.send_message(embed=discord.Embed(description=text, color=CREAM), ephemeral=True)

    @discord.ui.button(label="สมัครตำแหน่งนี้", emoji=EMO_BTN, style=discord.ButtonStyle.success)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        job = get_job(self.job_id)
        await interaction.response.send_modal(ApplyModal(self.job_id, job[1]))


class JobView(discord.ui.View):
    def __init__(self, job_id):
        super().__init__(timeout=None)
        self.job_id = job_id
        b = discord.ui.Button(label="สนใจตำแหน่งนี้", emoji="✨", style=discord.ButtonStyle.primary,
                              custom_id=f"job_int_{job_id}")
        b.callback = self.on_interest
        self.add_item(b)

    async def on_interest(self, interaction: discord.Interaction):
        job = get_job(self.job_id)
        if not job:
            return await interaction.response.send_message("ตำแหน่งนี้ถูกลบแล้ว", ephemeral=True)
        text = f"**หน้าที่ของตำแหน่ง** __**{job[1]}**__\n\n{bullets(job[2])}"
        e = discord.Embed(description=text, color=CREAM)
        f = job_file(job)
        if f:
            e.set_image(url="attachment://job.png")
            await interaction.response.send_message(embed=e, file=f, view=DetailView(self.job_id), ephemeral=True)
        else:
            await interaction.response.send_message(embed=e, view=DetailView(self.job_id), ephemeral=True)


def get_app(aid):
    return db.execute(
        "SELECT id, user_id, answers, status, job_id, itext, ivoice FROM apps WHERE id=?", (aid,)).fetchone()


async def dm_applicant(guild, uid, text):
    try:
        member = await guild.fetch_member(uid)
        await member.send(embed=discord.Embed(description=text, color=CREAM))
    except Exception:
        pass


async def set_status(interaction, aid, status, reason=None):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
    app = get_app(aid)
    if not app:
        return await interaction.response.send_message("ไม่พบใบสมัครนี้", ephemeral=True)
    db.execute("UPDATE apps SET status=?, reason=? WHERE id=?", (status, reason, aid))
    db.commit()
    job = get_job(app[4])
    try:
        user = await interaction.guild.fetch_member(app[1])
    except Exception:
        user = None
    await interaction.response.edit_message(embed=app_embed((aid, app[1], app[2], status), job, user), view=ReviewView(aid))
    emo, label, _ = STATUS[status]
    await dm_applicant(interaction.guild, app[1], f"ใบสมัครตำแหน่ง __**{job[1]}**__ ของคุณ\n**สถานะ:** {emo} __**{label}**__" + (f"\n**เหตุผล:** **{reason}**" if reason else ""))
    if status == "pass" and job[6] and user:
        role = interaction.guild.get_role(job[6])
        if role:
            try:
                await user.add_roles(role)
            except Exception:
                pass


async def open_interview(interaction, aid):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
    app = get_app(aid)
    if not app:
        return await interaction.response.send_message("ไม่พบใบสมัครนี้", ephemeral=True)
    guild = interaction.guild
    if app[5] and guild.get_channel(app[5]):
        return await interaction.response.send_message(f"มีห้องสัมภาษณ์แล้ว: <#{app[5]}>", ephemeral=True)
    row = db.execute("SELECT category FROM settings WHERE guild_id=?", (guild.id,)).fetchone()
    category = guild.get_channel(row[0]) if row and row[0] else None
    if not category:
        return await interaction.response.send_message("ยังไม่ได้ตั้งหมวดหมู่ห้องสัมภาษณ์ (ใช้แผง /job)", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    job = get_job(app[4])
    try:
        member = await guild.fetch_member(app[1])
    except Exception:
        return await interaction.followup.send("ไม่พบผู้สมัครในเซิร์ฟเวอร์", ephemeral=True)
    ow = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, connect=True, send_messages=True),
        member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True, read_message_history=True),
    }
    for rid in STAFF_IDS + ([job[5]] if job[5] else []):
        role = guild.get_role(rid)
        if role:
            ow[role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True, read_message_history=True)
    text = await guild.create_text_channel(f"สัมภาษณ์-{aid}", category=category, overwrites=ow)
    voice = await guild.create_voice_channel(f"สัมภาษณ์-{aid}", category=category, overwrites=ow)
    db.execute("UPDATE apps SET itext=?, ivoice=?, status='interview' WHERE id=?", (text.id, voice.id, aid))
    db.commit()
    try:
        user = member
        await interaction.message.edit(embed=app_embed((aid, app[1], app[2], "interview"), job, user), view=ReviewView(aid))
    except Exception:
        pass
    await text.send(f"<@{app[1]}> **ถึงเวลานัดสัมภาษณ์ตำแหน่ง** __**{job[1]}**__\nเข้าห้องเสียงได้เลย: {voice.mention}")
    await dm_applicant(guild, app[1], f"ทีมงานนัดสัมภาษณ์ตำแหน่ง __**{job[1]}**__\nห้องแชท: {text.mention}\nห้องเสียง: {voice.mention}")
    await interaction.followup.send(f"สร้างห้องสัมภาษณ์แล้ว: {text.mention}", ephemeral=True)


class FailModal(discord.ui.Modal):
    def __init__(self, aid):
        super().__init__(title="เหตุผลที่ไม่ผ่าน")
        self.aid = aid
        self.reason_in = discord.ui.TextInput(label="เหตุผล", style=discord.TextStyle.paragraph, max_length=500)
        self.add_item(self.reason_in)
    async def on_submit(self, interaction: discord.Interaction):
        await set_status(interaction, self.aid, "fail", self.reason_in.value.strip())
class ReviewView(discord.ui.View):
    def __init__(self, aid):
        super().__init__(timeout=None)
        self.aid = aid
        for key, label, emoji, style in [
            ("pass", "ผ่าน", "✅", discord.ButtonStyle.success),
            ("fail", "ไม่ผ่าน", "❌", discord.ButtonStyle.danger),
            ("interview", "นัดสัมภาษณ์", "🗓️", discord.ButtonStyle.primary),
        ]:
            b = discord.ui.Button(label=label, emoji=emoji, style=style, custom_id=f"app_{key}_{aid}")
            b.callback = self.make_cb(key)
            self.add_item(b)

    def make_cb(self, key):
        async def cb(interaction: discord.Interaction):
            if key == "interview":
                await open_interview(interaction, self.aid)
            elif key == "fail":
                if not is_staff(interaction.user):
                    return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
                await interaction.response.send_modal(FailModal(self.aid))
            else:
                await set_status(interaction, self.aid, key)
        return cb


import shutil
from discord.ext import tasks


async def refresh_post(client, job_id):
    row = db.execute("SELECT channel_id, message_id FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row or not row[1]:
        return
    ch = client.get_channel(row[0])
    job = get_job(job_id)
    if not ch or not job:
        return
    try:
        msg = await ch.fetch_message(row[1])
        f = job_file(job)
        await msg.edit(embed=job_embed(job), attachments=[f] if f else [])
    except Exception:
        pass


class JobModal(discord.ui.Modal):
    def __init__(self, job=None, image_path=None):
        super().__init__(title="แก้ไขตำแหน่ง" if job else "เพิ่มตำแหน่ง")
        self.job = job
        self.image_path = image_path
        para = discord.TextStyle.paragraph
        self.name_in = discord.ui.TextInput(label="ชื่อตำแหน่ง", max_length=60, default=job[1] if job else None)
        self.desc_in = discord.ui.TextInput(label="หน้าที่ (คั่นด้วย |)", style=para, required=False, max_length=1000, default=job[2] if job else None)
        self.cond_in = discord.ui.TextInput(label="เงื่อนไข (คั่นด้วย |)", style=para, required=False, max_length=1000, default=job[3] if job else None)
        self.ben_in = discord.ui.TextInput(label="สวัสดิการ (คั่นด้วย |)", style=para, required=False, max_length=1000, default=job[7] if job else None)
        self.emo_in = discord.ui.TextInput(label="อีโมจิหน้าชื่อ (ไม่บังคับ)", required=False, max_length=80, default=(_job_emoji(job[0]) or None) if job else None)
        for item in (self.name_in, self.desc_in, self.cond_in, self.ben_in, self.emo_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        vals = (self.name_in.value.strip(), self.desc_in.value.strip(), self.cond_in.value.strip(), self.ben_in.value.strip())
        if self.job:
            jid = self.job[0]
            db.execute("UPDATE jobs SET name=?, description=?, conditions=?, benefits=? WHERE id=?", vals + (jid,))
        else:
            cur = db.execute("INSERT INTO jobs (guild_id, name, description, conditions, benefits) VALUES (?,?,?,?,?)",
                             (interaction.guild.id,) + vals)
            jid = cur.lastrowid
        db.execute("UPDATE jobs SET emoji=? WHERE id=?", (self.emo_in.value.strip(), jid))
        db.commit()
        if self.image_path and os.path.exists(self.image_path):
            final = os.path.join(IMG_DIR, f"job_{jid}.png")
            shutil.copyfile(self.image_path, final)
            db.execute("UPDATE jobs SET image=? WHERE id=?", (final, jid))
            db.commit()
        await refresh_post(interaction.client, jid)
        await interaction.response.send_message(
            f"บันทึกตำแหน่ง **#{jid}** แล้ว กดปุ่ม โพสต์ ในแผงเพื่อประกาศในห้องที่คุณอยู่", ephemeral=True)


class JobPick(discord.ui.Select):
    def __init__(self, guild_id, action, image_path=None):
        rows = db.execute("SELECT id, name FROM jobs WHERE guild_id=? ORDER BY id LIMIT 25", (guild_id,)).fetchall()
        opts = [discord.SelectOption(label=f"#{i} {n}"[:100], value=str(i)) for i, n in rows]
        super().__init__(placeholder="เลือกตำแหน่ง", options=opts or [discord.SelectOption(label="ยังไม่มีตำแหน่ง", value="0")])
        self.action = action
        self.image_path = image_path

    async def callback(self, interaction: discord.Interaction):
        jid = int(self.values[0])
        job = get_job(jid) if jid else None
        if not job:
            return await interaction.response.send_message("ยังไม่มีตำแหน่งนี้", ephemeral=True)
        if self.action == "edit":
            return await interaction.response.send_modal(JobModal(job, self.image_path))
        if self.action == "delete":
            row = db.execute("SELECT channel_id, message_id, image FROM jobs WHERE id=?", (jid,)).fetchone()
            ch = interaction.client.get_channel(row[0]) if row[0] else None
            if ch and row[1]:
                try:
                    m = await ch.fetch_message(row[1])
                    await m.delete()
                except Exception:
                    pass
            if row[2] and os.path.exists(row[2]):
                os.remove(row[2])
            db.execute("DELETE FROM jobs WHERE id=?", (jid,))
            db.commit()
            return await interaction.response.send_message(f"ลบตำแหน่ง **#{jid}** แล้ว", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        row = db.execute("SELECT channel_id, message_id FROM jobs WHERE id=?", (jid,)).fetchone()
        old = interaction.client.get_channel(row[0]) if row[0] else None
        if old and row[1]:
            try:
                m = await old.fetch_message(row[1])
                await m.delete()
            except Exception:
                pass
        kw = {"embed": job_embed(job), "view": JobView(jid)}
        f = job_file(job)
        if f:
            kw["file"] = f
        msg = await interaction.channel.send(**kw)
        db.execute("UPDATE jobs SET channel_id=?, message_id=? WHERE id=?", (interaction.channel.id, msg.id, jid))
        db.commit()
        await interaction.followup.send("โพสต์ประกาศตำแหน่งแล้ว", ephemeral=True)


class PickView(discord.ui.View):
    def __init__(self, guild_id, action, image_path=None):
        super().__init__(timeout=120)
        self.add_item(JobPick(guild_id, action, image_path))


class ChanPick(discord.ui.ChannelSelect):
    def __init__(self, kind):
        types = [discord.ChannelType.category] if kind == "category" else [discord.ChannelType.text]
        super().__init__(placeholder="เลือกหมวดหมู่" if kind == "category" else "เลือกห้อง", channel_types=types)
        self.kind = kind

    async def callback(self, interaction: discord.Interaction):
        cid = self.values[0].id
        db.execute("INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (interaction.guild.id,))
        col = "category" if self.kind == "category" else "app_channel"
        db.execute(f"UPDATE settings SET {col}=? WHERE guild_id=?", (cid, interaction.guild.id))
        db.commit()
        await interaction.response.send_message(f"ตั้งค่าเป็น <#{cid}> แล้ว", ephemeral=True)


class ChanView(discord.ui.View):
    def __init__(self, kind):
        super().__init__(timeout=120)
        self.add_item(ChanPick(kind))


class PanelView(discord.ui.View):
    def __init__(self, image_path=None):
        super().__init__(timeout=600)
        self.image_path = image_path

    @discord.ui.button(label="เพิ่มตำแหน่ง", emoji="➕", style=discord.ButtonStyle.success)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(JobModal(None, self.image_path))

    @discord.ui.button(label="แก้ไข", emoji="✏️", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=PickView(interaction.guild.id, "edit", self.image_path), ephemeral=True)

    @discord.ui.button(label="โพสต์ในห้องนี้", emoji="📣", style=discord.ButtonStyle.primary)
    async def post(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=PickView(interaction.guild.id, "post"), ephemeral=True)

    @discord.ui.button(label="ลบ", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=PickView(interaction.guild.id, "delete"), ephemeral=True)

    @discord.ui.button(label="ตั้งแบนเนอร์", emoji="🖼️", style=discord.ButtonStyle.secondary)
    async def set_banner(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.image_path or not os.path.exists(self.image_path):
            return await interaction.response.send_message(
                "พิมพ์ /job พร้อมแนบรูปในช่อง image ก่อน แล้วกดปุ่มนี้", ephemeral=True)
        shutil.copyfile(self.image_path, BANNER)
        await interaction.response.send_message("ตั้งแบนเนอร์แล้ว", ephemeral=True)

    @discord.ui.button(label="โพสต์รวมทุกตำแหน่ง", emoji="📋", style=discord.ButtonStyle.primary)
    async def post_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await post_board(interaction)

    @discord.ui.button(label="ตั้งห้องใบสมัคร", emoji="📥", style=discord.ButtonStyle.secondary)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=ChanView("channel"), ephemeral=True)

    @discord.ui.button(label="ตั้งหมวดหมู่ห้องสัมภาษณ์", emoji="📂", style=discord.ButtonStyle.secondary)
    async def set_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=ChanView("category"), ephemeral=True)


from datetime import datetime, timezone


class Jobs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sweeper.start()

    def cog_unload(self):
        self.sweeper.cancel()

    @app_commands.command(name="job", description="แผงจัดการตำแหน่งงาน (ทีมงาน)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(image="รูปประจำตำแหน่ง (ไม่บังคับ ผูกกับตำแหน่งที่เพิ่มหรือแก้ไขในแผงนี้)")
    async def job(self, interaction: discord.Interaction, image: discord.Attachment = None):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        path = None
        if image:
            if not (image.content_type or "").startswith("image/"):
                return await interaction.followup.send("ไฟล์ที่แนบต้องเป็นรูปภาพ", ephemeral=True)
            path = os.path.join(IMG_DIR, f"tmp_{interaction.user.id}.png")
            await image.save(path)
        text = "**แผงจัดการตำแหน่งงาน**\n\n"
        text += "- **เพิ่ม / แก้ไข / ลบ / โพสต์ตำแหน่ง**\n"
        text += "- **ตั้งห้องรับใบสมัคร และหมวดหมู่ห้องสัมภาษณ์**\n"
        if path:
            text += "\n__**แนบรูปแล้ว: จะใช้กับตำแหน่งที่เพิ่มหรือแก้ไขในแผงนี้**__"
        await interaction.followup.send(embed=discord.Embed(description=text, color=CREAM), view=PanelView(path), ephemeral=True)

    async def remove_interview(self, guild, ivoice):
        row = db.execute("SELECT id, itext FROM apps WHERE ivoice=?", (ivoice,)).fetchone()
        if not row:
            return
        for cid in (ivoice, row[1]):
            c = guild.get_channel(cid) if cid else None
            if c:
                try:
                    await c.delete(reason="จบการสัมภาษณ์")
                except Exception:
                    pass
        db.execute("UPDATE apps SET itext=NULL, ivoice=NULL WHERE id=?", (row[0],))
        db.commit()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        ch = before.channel
        if not ch or (after.channel and after.channel.id == ch.id):
            return
        if ch.members:
            return
        await self.remove_interview(ch.guild, ch.id)

    @tasks.loop(minutes=10)
    async def sweeper(self):
        now = datetime.now(timezone.utc)
        for aid, ivoice in db.execute("SELECT id, ivoice FROM apps WHERE ivoice IS NOT NULL").fetchall():
            ch = self.bot.get_channel(ivoice)
            if ch is None:
                db.execute("UPDATE apps SET itext=NULL, ivoice=NULL WHERE id=?", (aid,))
                db.commit()
            elif not ch.members and (now - ch.created_at).total_seconds() > 3 * 3600:
                await self.remove_interview(ch.guild, ivoice)

    @sweeper.before_loop
    async def before_sweeper(self):
        await self.bot.wait_until_ready()


async def setup_jobs(bot):
    await bot.add_cog(Jobs(bot))
    for (jid,) in db.execute("SELECT id FROM jobs").fetchall():
        bot.add_view(JobView(jid))
    for (aid,) in db.execute("SELECT id FROM apps WHERE status IN ('pending','interview')").fetchall():
        bot.add_view(ReviewView(aid))


from datetime import timedelta

for col in ("itime INTEGER", "inote TEXT", "iopened INTEGER DEFAULT 0", "reason TEXT"):
    try:
        db.execute(f"ALTER TABLE apps ADD COLUMN {col}")
    except sqlite3.OperationalError:
        pass
db.commit()

_BOT = None


def parse_dt(date, time):
    try:
        d = date.strip().replace("-", "/").replace(".", "/")
        t = time.strip().replace(".", ":").replace("น", "").strip()
        dd, mm, yy = [int(x) for x in d.split("/")]
        if yy > 2400:
            yy -= 543
        hh, mi = [int(x) for x in t.split(":")]
        return int(datetime(yy, mm, dd, hh, mi, tzinfo=timezone(timedelta(hours=7))).timestamp())
    except Exception:
        return None


async def refresh_card(guild, aid):
    app = get_app(aid)
    row = db.execute("SELECT channel_id, message_id FROM apps WHERE id=?", (aid,)).fetchone()
    if not app or not row or not row[1]:
        return
    ch = guild.get_channel(row[0])
    if not ch:
        return
    try:
        member = await guild.fetch_member(app[1])
    except Exception:
        member = None
    try:
        msg = await ch.fetch_message(row[1])
        await msg.edit(embed=app_embed((aid, app[1], app[2], app[3]), get_job(app[4]), member), view=ReviewView(aid))
    except Exception:
        pass


async def create_rooms(guild, aid):
    app = get_app(aid)
    if not app:
        return "ไม่พบใบสมัคร"
    row = db.execute("SELECT category FROM settings WHERE guild_id=?", (guild.id,)).fetchone()
    category = guild.get_channel(row[0]) if row and row[0] else None
    if not category:
        return "ยังไม่ได้ตั้งหมวดหมู่ห้องสัมภาษณ์ (ใช้แผง /job)"
    job = get_job(app[4])
    try:
        member = await guild.fetch_member(app[1])
    except Exception:
        db.execute("UPDATE apps SET iopened=1 WHERE id=?", (aid,))
        db.commit()
        return "ไม่พบผู้สมัครในเซิร์ฟเวอร์"
    perm = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True, read_message_history=True)
    ow = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, connect=True, send_messages=True),
        member: perm,
    }
    for rid in STAFF_IDS + ([job[5]] if job[5] else []):
        role = guild.get_role(rid)
        if role:
            ow[role] = perm
    text = await guild.create_text_channel(f"สัมภาษณ์-{aid}", category=category, overwrites=ow)
    voice = await guild.create_voice_channel(f"สัมภาษณ์-{aid}", category=category, overwrites=ow)
    db.execute("UPDATE apps SET itext=?, ivoice=?, status='interview', iopened=1 WHERE id=?", (text.id, voice.id, aid))
    db.commit()
    await refresh_card(guild, aid)
    await text.send(f"<@{app[1]}> **ถึงเวลานัดสัมภาษณ์ตำแหน่ง** __**{job[1]}**__\nเข้าห้องเสียงได้เลย: {voice.mention}")
    await dm_applicant(guild, app[1], f"ห้องสัมภาษณ์ตำแหน่ง __**{job[1]}**__ เปิดแล้ว\nห้องแชท: {text.mention}\nห้องเสียง: {voice.mention}")
    return text


class ScheduleModal(discord.ui.Modal):
    def __init__(self, aid):
        super().__init__(title=f"นัดสัมภาษณ์ #{aid}")
        self.aid = aid
        self.date_in = discord.ui.TextInput(label="วันที่ เช่น 18/10/2026", required=False, max_length=12,
                                            placeholder="เว้นว่างทั้งวันที่และเวลา = เปิดห้องตอนนี้")
        self.time_in = discord.ui.TextInput(label="เวลา เช่น 20:00", required=False, max_length=8)
        self.note_in = discord.ui.TextInput(label="หมายเหตุถึงผู้สมัคร", style=discord.TextStyle.paragraph,
                                            required=False, max_length=300)
        for item in (self.date_in, self.time_in, self.note_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        d = self.date_in.value.strip()
        t = self.time_in.value.strip()
        app = get_app(self.aid)
        if not app:
            return await interaction.response.send_message("ไม่พบใบสมัครนี้", ephemeral=True)
        if not d and not t:
            await interaction.response.defer(ephemeral=True)
            res = await create_rooms(interaction.guild, self.aid)
            if isinstance(res, str):
                return await interaction.followup.send(res, ephemeral=True)
            return await interaction.followup.send(f"สร้างห้องสัมภาษณ์แล้ว: {res.mention}", ephemeral=True)
        ts = parse_dt(d, t) if d and t else None
        if not ts:
            return await interaction.response.send_message("รูปแบบวันที่หรือเวลาไม่ถูก ใช้ เช่น 18/10/2026 และ 20:00 (ต้องใส่ทั้งคู่)", ephemeral=True)
        if ts <= int(datetime.now(timezone.utc).timestamp()):
            return await interaction.response.send_message("เวลานี้ผ่านไปแล้ว", ephemeral=True)
        note = self.note_in.value.strip()
        db.execute("UPDATE apps SET status='interview', itime=?, inote=?, iopened=0 WHERE id=?", (ts, note, self.aid))
        db.commit()
        job = get_job(app[4])
        await refresh_card(interaction.guild, self.aid)
        msg = f"ทีมงานนัดสัมภาษณ์ตำแหน่ง __**{job[1]}**__\n**เวลา:** __**<t:{ts}:F>**__ (<t:{ts}:R>)\nห้องสัมภาษณ์จะเปิดก่อนเวลานัด 10 นาที"
        if note:
            msg += f"\n**หมายเหตุ:** **{note}**"
        await dm_applicant(interaction.guild, app[1], msg)
        await interaction.response.send_message(f"นัดสัมภาษณ์แล้ว <t:{ts}:F> ห้องจะเปิดก่อนเวลา 10 นาที", ephemeral=True)


async def open_interview(interaction, aid):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("สำหรับทีมงานเท่านั้น", ephemeral=True)
    app = get_app(aid)
    if not app:
        return await interaction.response.send_message("ไม่พบใบสมัครนี้", ephemeral=True)
    if app[5] and interaction.guild.get_channel(app[5]):
        return await interaction.response.send_message(f"มีห้องสัมภาษณ์แล้ว: <#{app[5]}>", ephemeral=True)
    await interaction.response.send_modal(ScheduleModal(aid))


@tasks.loop(minutes=1)
async def schedule_ticker():
    now = int(datetime.now(timezone.utc).timestamp())
    rows = db.execute(
        "SELECT id, guild_id FROM apps WHERE status='interview' AND itime IS NOT NULL AND iopened=0 AND itime - ? <= 600",
        (now,)).fetchall()
    for aid, gid in rows:
        guild = _BOT.get_guild(gid)
        if guild:
            await create_rooms(guild, aid)


@schedule_ticker.before_loop
async def before_schedule_ticker():
    await _BOT.wait_until_ready()


async def setup_jobs(bot):
    global _BOT
    _BOT = bot
    await bot.add_cog(Jobs(bot))
    for (jid,) in db.execute("SELECT id FROM jobs").fetchall():
        bot.add_view(JobView(jid))
    for (aid,) in db.execute("SELECT id FROM apps WHERE status IN ('pending','interview')").fetchall():
        bot.add_view(ReviewView(aid))
    for (gid,) in db.execute("SELECT DISTINCT guild_id FROM jobs").fetchall():
        bot.add_view(BoardView(gid))
    if not schedule_ticker.is_running():
        schedule_ticker.start()


def _job_emoji(jid):
    r = db.execute("SELECT emoji FROM jobs WHERE id=?", (jid,)).fetchone()
    return (r[0] or "").strip() if r else ""
def board_rows(guild_id):
    return db.execute(
        "SELECT id, name, conditions, image FROM jobs WHERE guild_id=? ORDER BY id LIMIT 6",
        (guild_id,)).fetchall()


def board_files(guild_id):
    files = []
    if os.path.exists(BANNER):
        files.append(discord.File(BANNER, filename="banner.png"))
    for jid, name, cond, img in board_rows(guild_id):
        if img and os.path.exists(img):
            files.append(discord.File(img, filename=f"job_{jid}.png"))
    return files


def make_interest_button(jid):
    btn = discord.ui.Button(label=TXT_BUTTON, emoji=EMO_BTN, style=discord.ButtonStyle.success,
                            custom_id=f"job_int_{jid}")

    async def cb(interaction: discord.Interaction):
        await JobView(jid).on_interest(interaction)

    btn.callback = cb
    return btn


class BoardView(discord.ui.LayoutView):
    def __init__(self, guild_id=None):
        super().__init__(timeout=None)
        fence = "`" * 3
        parts = []
        if os.path.exists(BANNER):
            parts.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://banner.png")))
            parts.append(discord.ui.Separator())
        parts.append(discord.ui.TextDisplay(f"{EMO_TITLE}\n{fence}{TXT_TITLE}{fence}\n**{TXT_INTRO}**"))
        parts.append(discord.ui.Separator())
        rows = board_rows(guild_id) if guild_id else []
        if not rows:
            parts.append(discord.ui.TextDisplay("**ยังไม่มีตำแหน่งที่เปิดรับ**"))
        for jid, name, cond, img in rows:
            parts.append(discord.ui.TextDisplay(f"## {_job_emoji(jid) or EMO_NAME} __**{name}**__"))
            if img and os.path.exists(img):
                parts.append(discord.ui.MediaGallery(discord.MediaGalleryItem(f"attachment://job_{jid}.png")))
            parts.append(discord.ui.ActionRow(make_interest_button(jid)))
            parts.append(discord.ui.Separator())
        if TXT_FOOTER:
            parts.append(discord.ui.TextDisplay(f"**{TXT_FOOTER}**"))
        self.add_item(discord.ui.Container(*parts, accent_colour=discord.Colour(CREAM)))


async def refresh_board(client, guild):
    row = db.execute("SELECT board_channel, board_message FROM settings WHERE guild_id=?", (guild.id,)).fetchone()
    if not row or not row[1]:
        return
    ch = client.get_channel(row[0])
    if not ch:
        return
    try:
        msg = await ch.fetch_message(row[1])
        await msg.edit(view=BoardView(guild.id), attachments=board_files(guild.id))
    except Exception:
        pass


async def post_board(interaction):
    await interaction.response.defer(ephemeral=True)
    gid = interaction.guild.id
    row = db.execute("SELECT board_channel, board_message FROM settings WHERE guild_id=?", (gid,)).fetchone()
    if row and row[1]:
        old = interaction.client.get_channel(row[0])
        if old:
            try:
                m = await old.fetch_message(row[1])
                await m.delete()
            except Exception:
                pass
    msg = await interaction.channel.send(view=BoardView(gid), files=board_files(gid))
    db.execute("INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (gid,))
    db.execute("UPDATE settings SET board_channel=?, board_message=? WHERE guild_id=?",
               (interaction.channel.id, msg.id, gid))
    db.commit()
    await interaction.followup.send("โพสต์รวมทุกตำแหน่งแล้ว", ephemeral=True)
