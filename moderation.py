import sqlite3
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

CREAM = 0xF5E6C8
AUTO_ACTION = "ban"   # "ban" หรือ "timeout"
AUTO_AT = 3
TIMEOUT_HOURS = 24
STAFF_IDS = [1557937118456709192, 1557937214728699997]

WARN_IDS = [
    1557028268899831859,  # เตือนครั้งที่ 1 - สีขาว
    1557028678230220810,  # เตือนครั้งที่ 2 - สีส้ม
    1557028792562753579   # เตือนครั้งที่ 3 - สีแดง
]
db = sqlite3.connect("warns.db")
db.execute("CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER, mod_id INTEGER, reason TEXT, ts TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, log_channel INTEGER)")
db.commit()


def is_staff(member):
    return member.id == member.guild.owner_id or any(r.id in STAFF_IDS for r in member.roles)


def count_warns(guild_id, user_id):
    return db.execute("SELECT COUNT(*) FROM warns WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()[0]

async def sync_roles(member, n):
    roles = [member.guild.get_role(x) for x in WARN_IDS]
    print("GUILD:", member.guild.name, member.guild.id, flush=True)
    print(
        "AVAILABLE ROLES:",
        [(r.name, r.id) for r in member.guild.roles],
        flush=True
    )

    remove = [r for r in roles if r and r in member.roles]
    if remove:
        await member.remove_roles(*remove)

    if n >= 1:
        target = roles[min(n, len(WARN_IDS)) - 1]
        if target:
            await member.add_roles(target)
WARN_COLORS = [0xF5E6C8, 0xF4A261, 0xE76F51]



def warn_embed(member, mod, n, reason):
    total = len(WARN_IDS)
    idx = min(max(n, 1), len(WARN_COLORS)) - 1
    level_emoji = ["⚪", "🟠", "🔴"][min(max(n, 1), 3) - 1]
    bar = f"{level_emoji} {min(n, 3)}/3"

    e = discord.Embed(
        title="⚠️ แจ้งเตือนจากทีมงาน",
        description=(
            f"{member.mention} ได้รับการเตือน\n\n"
            f"**ครั้งที่ {n}**  {bar}"
        ),
        color=WARN_COLORS[idx],
        timestamp=datetime.now(),
    )
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="📝 เหตุผล", value=f"> {reason}", inline=False)
    e.add_field(name="👮 เตือนโดย", value=mod.mention, inline=True)
    e.add_field(name="📊 สถานะ", value=f"{n}/{total}", inline=True)
    e.set_footer(
        text=f"Bakery House • โดย {mod.display_name}",
        icon_url=mod.display_avatar.url,
    )
    return e

async def send_log(guild, title, member, mod, n=None, reason=None):
    row = db.execute("SELECT log_channel FROM settings WHERE guild_id=?", (guild.id,)).fetchone()
    if not row:
        return
    ch = guild.get_channel(row[0])
    if not ch:
        return
    e = discord.Embed(title=title, color=CREAM, timestamp=datetime.now())
    e.add_field(name="ผู้ถูกดำเนินการ", value=member.mention, inline=True)
    e.add_field(name="ทีมงาน", value=mod.mention, inline=True)
    if n is not None:
        e.add_field(name="จำนวนครั้ง", value=str(n), inline=True)
    if reason:
        e.add_field(name="เหตุผล", value=reason, inline=False)
    e.set_thumbnail(url=member.display_avatar.url)
    try:
        await ch.send(embed=e)
    except Exception:
        pass


async def auto_punish(guild, member, mod, n):
    if n < AUTO_AT:
        return None
    reason = f"เตือนครบ {AUTO_AT} ครั้ง (ลงโทษอัตโนมัติ)"
    try:
        if AUTO_ACTION == "ban":
            try:
                await member.send(embed=discord.Embed(
                    title="🔨 คุณถูกแบน",
                    description=f"เซิร์ฟเวอร์ {guild.name}: {reason}", color=0xE76F51))
            except Exception:
                pass
            await guild.ban(member, reason=reason, delete_message_days=0)
            result = "🔨 แบนอัตโนมัติ"
        else:
            from datetime import timedelta
            await member.timeout(timedelta(hours=TIMEOUT_HOURS), reason=reason)
            result = f"⏳ Timeout {TIMEOUT_HOURS} ชม. อัตโนมัติ"
    except discord.Forbidden:
        return "⚠️ บอทลงโทษอัตโนมัติไม่ได้ (สิทธิ์ไม่พอ)"
    await send_log(guild, result, member, mod, n, reason)
    return result


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="เตือนสมาชิก (ทีมงาน)")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=discord.Embed(title="🔒 สำหรับทีมงานเท่านั้น", description="คุณไม่มีสิทธิ์ใช้คำสั่งนี้", color=CREAM), ephemeral=True)
        if member.bot or is_staff(member):
            return await interaction.response.send_message(embed=discord.Embed(title="❌ เตือนคนนี้ไม่ได้", description="เป้าหมายเป็นบอทหรือทีมงาน", color=CREAM), ephemeral=True)
        await interaction.response.defer()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        db.execute("INSERT INTO warns (guild_id, user_id, mod_id, reason, ts) VALUES (?,?,?,?,?)",
                   (interaction.guild.id, member.id, interaction.user.id, reason, now))
        db.commit()
        n = count_warns(interaction.guild.id, member.id)
        note = ""
        try:
            await sync_roles(member, n)
        except discord.Forbidden:
            note = "\n⚠️ บอทให้ยศไม่ได้ เช็กว่ายศบอทอยู่เหนือยศเตือน"
        e = warn_embed(member, interaction.user, n, reason)
        if note:
            e.add_field(name="หมายเหตุ", value=note.strip(), inline=False)
        try:
            await member.send(embed=e)
        except Exception:
            pass
        await interaction.followup.send(embed=e)
        await send_log(interaction.guild, "⚠️ เตือนสมาชิก", member, interaction.user, n, reason)
        punished = await auto_punish(interaction.guild, member, interaction.user, n)
        if punished:
            await interaction.followup.send(embed=discord.Embed(title=punished, description=f"{member.mention} เตือนครบ {AUTO_AT} ครั้ง", color=0xE76F51))

    @app_commands.command(name="unwarn", description="ลดคำเตือนลง 1 ครั้ง (ทีมงาน)")
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=discord.Embed(title="🔒 สำหรับทีมงานเท่านั้น", description="คุณไม่มีสิทธิ์ใช้คำสั่งนี้", color=CREAM), ephemeral=True)
        await interaction.response.defer()
        row = db.execute("SELECT id FROM warns WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 1",
                         (interaction.guild.id, member.id)).fetchone()
        if not row:
            return await interaction.followup.send(embed=discord.Embed(title="📭 ไม่มีคำเตือน", description="คนนี้ประวัติสะอาด", color=CREAM))
        db.execute("DELETE FROM warns WHERE id=?", (row[0],))
        db.commit()
        n = count_warns(interaction.guild.id, member.id)
        await sync_roles(member, n)
        await interaction.followup.send(embed=discord.Embed(
            title="✅ ปลดคำเตือน", description=f"{member.mention} เหลือ {n} ครั้ง", color=CREAM))
        await send_log(interaction.guild, "✅ ปลดคำเตือน", member, interaction.user, n)
    @app_commands.command(name="clearwarn", description="ล้างคำเตือนทั้งหมด (ทีมงาน)")
    async def clearwarn(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=discord.Embed(title="🔒 สำหรับทีมงานเท่านั้น", description="คุณไม่มีสิทธิ์ใช้คำสั่งนี้", color=CREAM), ephemeral=True)
        await interaction.response.defer()
        db.execute("DELETE FROM warns WHERE guild_id=? AND user_id=?", (interaction.guild.id, member.id))
        db.commit()
        await sync_roles(member, 0)
        await interaction.followup.send(embed=discord.Embed(
            title="🧹 ล้างคำเตือนแล้ว", description=member.mention, color=CREAM))
        await send_log(interaction.guild, "🧹 ล้างคำเตือนทั้งหมด", member, interaction.user, 0)

    @app_commands.command(name="warnings", description="ดูประวัติคำเตือน (ทีมงาน)")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=discord.Embed(title="🔒 สำหรับทีมงานเท่านั้น", description="คุณไม่มีสิทธิ์ใช้คำสั่งนี้", color=CREAM), ephemeral=True)
        rows = db.execute("SELECT mod_id, reason, ts FROM warns WHERE guild_id=? AND user_id=? ORDER BY id",
                          (interaction.guild.id, member.id)).fetchall()
        if not rows:
            return await interaction.response.send_message(embed=discord.Embed(title="📭 ไม่มีประวัติคำเตือน", description="คนนี้ประวัติสะอาด", color=CREAM), ephemeral=True)
        text = "\n".join(f"**{i+1}.** {r} — <@{m}> ({t})" for i, (m, r, t) in enumerate(rows[-10:]))
        await interaction.response.send_message(embed=discord.Embed(
            title=f"📋 ประวัติของ {member.display_name}", description=text, color=CREAM))

    @app_commands.command(name="setlog", description="ตั้งห้อง mod-log (ทีมงาน)")
    async def setlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=discord.Embed(title="🔒 สำหรับทีมงานเท่านั้น", description="คุณไม่มีสิทธิ์ใช้คำสั่งนี้", color=CREAM), ephemeral=True)
        db.execute("INSERT OR REPLACE INTO settings (guild_id, log_channel) VALUES (?,?)", (interaction.guild.id, channel.id))
        db.commit()
        await interaction.response.send_message(embed=discord.Embed(title="📋 ตั้งห้อง mod-log แล้ว", description=channel.mention, color=CREAM))


async def setup_moderation(bot):
    await bot.add_cog(Moderation(bot))
