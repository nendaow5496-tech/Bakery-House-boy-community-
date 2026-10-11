import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

from welcome import member_join, member_boost
# from radio import setup_radio
#0 from radio_voice import setup_radio_voice
from music import setup_music
from jobs import setup_jobs
#from shop import setup_shop
from events import setup_events
from moderation import setup_moderation
from staff_management import setup_staff_management
from staff_attendance import setup_staff_attendance
from staff_config import setup_staff_config
from staff_monitoring import setup_staff_monitoring
from staff_employee import setup_staff_employee
#from staff_recruitment import setup_staff_recruitment

load_dotenv()

# =========================
# ตั้งค่า Discord Bot
# =========================

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================
# เมื่อบอทออนไลน์
# =========================
@bot.event
async def on_ready():
    print(f"🦊 {bot.user} ออนไลน์แล้ว!", flush=True)
    try:
        synced = await bot.tree.sync()
        print(f"โหลด Slash Commands แล้ว {len(synced)} คำสั่ง", flush=True)
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการ Sync Commands: {e}", flush=True)

# =========================
# ระบบสมาชิกใหม่
# =========================
@bot.event
async def on_member_join(member):
    await member_join(member)

# =========================
# เมื่อสมาชิกเริ่มบูสต์เซิร์ฟเวอร์
# =========================
@bot.event
async def on_member_update(before, after):
    if before.premium_since is None and after.premium_since is not None:
        await member_boost(after)


# =========================
# โหลด Bakery FM
# =========================

# setup_radio(bot)

# =========================
# โหลดระบบ Bakery FM Voice
# =========================

# setup_radio_voice(bot)


async def _music_hook():
    print("DEBUG 1: เริ่มโหลดระบบเพลง", flush=True)
    await setup_music(bot)
    await setup_jobs(bot)
    #await setup_shop(bot)
    #print("DEBUG 6: โหลดระบบร้านค้าสำเร็จ", flush=True)
    print("DEBUG 2: โหลดระบบเพลงสำเร็จ", flush=True)

    await setup_events(bot)
    print("DEBUG 3: โหลดระบบกิจกรรมสำเร็จ", flush=True)

    await setup_moderation(bot)
    await setup_staff_management(bot)
    await setup_staff_config(bot)
    await setup_staff_attendance(bot)
    await setup_staff_monitoring(bot)
    await setup_staff_employee(bot)
    print("DEBUG: โหลดระบบเข้างานสำเร็จ", flush=True)
    print("DEBUG: โหลดระบบทีมงานสำเร็จ", flush=True)
    print("DEBUG: โหลดระบบแจ้งเตือนทีมงานสำเร็จ", flush=True)
    print("DEBUG: โหลดระบบพนักงานดีเด่นสำเร็จ", flush=True)
    print("DEBUG 4: โหลดระบบดูแลสมาชิกสำเร็จ", flush=True)

    # await setup_staff_recruitment(bot)
    print("DEBUG 5: โหลดระบบรับสมัครทีมงานสำเร็จ", flush=True)


bot.setup_hook = _music_hook


@bot.tree.command(name="testboost", description="ทดสอบ Embed ขอบคุณผู้บูสต์เซิร์ฟเวอร์")
@commands.has_permissions(administrator=True)
async def testboost(interaction: discord.Interaction):
    count = interaction.guild.premium_subscription_count or 0
    await interaction.response.defer(ephemeral=True)
    channel = interaction.guild.get_channel(1558414637874290688)
    if channel is None:
        try:
            channel = await interaction.guild.fetch_channel(1558414637874290688)
        except Exception:
            await interaction.followup.send("ไม่พบห้องประกาศบูสต์", ephemeral=True)
            return

    embed = discord.Embed(
        title="<a:emoji_53:1558434672973975612> ขอบคุณที่บูสต์เซิร์ฟเวอร์!",
        description=(
            f"ขอบคุณ {interaction.user.mention} ที่สนับสนุน "
            "**Bakery House Community** <a:emoji_53:1558434672973975612>\n\n"
            f"นี่คือข้อความทดสอบระบบประกาศบูสต์\n\n<a:emoji_53:1558434672973975612> บูสต์รวมของเซิร"
        ),
        color=0xD8A15D
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_image(url="https://cdn.discordapp.com/attachments/1558414637874290688/1558431969736527882/42b9ed4e879fedfc303832f2b4dce58d.jpg")
    embed.set_footer(text="Bakery House Community • Server Booster")

    try:
        await channel.send(embed=embed)
        await interaction.followup.send("ส่ง Embed ทดสอบแล้ว", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(
            "บอทไม่มีสิทธิ์ส่งข้อความหรือ Embed ในห้องนี้",
            ephemeral=True
        )
    except Exception as e:
        print(f"Testboost error: {e}", flush=True)
        await interaction.followup.send("ส่ง Embed ไม่สำเร็จ ตรวจสอบ Log ของบอท", ephemeral=True)

# =========================
# Token
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "ไม่พบ DISCORD_TOKEN ในไฟล์ .env"
    )

# =========================
# เริ่มบอท
# =========================

bot.run(TOKEN)
