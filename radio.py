import discord
from discord import app_commands
from datetime import datetime
import random
import asyncio
import yt_dlp

RADIO_EMOJI_1 = "<a:emoji_38:1557336451463520296>"
RADIO_EMOJI_2 = "<a:emoji_15:1557001484799971411>"

radio_status = False
radio_start_time = None
radio_voice = None
radio_player_url = None


def setup_radio(bot):

    radio = app_commands.Group(
        name="radio",
        description="ระบบวิทยุ Bakery FM ของ Bakery House"
    )

    bot.tree.add_command(radio)

    # =========================
    # /radio now
    # =========================

    @radio.command(
        name="now",
        description="ดูสถานะการออกอากาศตอนนี้"
    )
    async def radio_now(interaction):

        if radio_status:
            if radio_start_time:
                timestamp = int(radio_start_time.timestamp())
                started = f"<t:{timestamp}:R>"
            else:
                started = "ไม่ทราบเวลา"

            voice_text = (
                "🔊 กำลังเล่นเสียง"
                if radio_voice and radio_voice.is_playing()
                else "⏸️ ยังไม่มีเสียงที่กำลังเล่น"
            )

            embed = discord.Embed(
                title=f"{RADIO_EMOJI_1} Bakery FM",
                description=(
                    f"{RADIO_EMOJI_2} **สถานีออนไลน์อยู่**\n\n"
                    f"กำลังออกอากาศรายการของ "
                    f"**Bakery House Community**\n\n"
                    f"เริ่มออกอากาศ {started}\n"
                    f"{voice_text}"
                ),
                color=0xD8A15D
            )

        else:
            embed = discord.Embed(
                title=f"{RADIO_EMOJI_1} Bakery FM",
                description=(
                    f"{RADIO_EMOJI_2} **ขณะนี้สถานีปิดอยู่**\n\n"
                    "สามารถรอประกาศรอบการออกอากาศถัดไปได้"
                ),
                color=0x777777
            )

        await interaction.response.send_message(embed=embed)

    # =========================
    # /radio schedule
    # =========================

    @radio.command(
        name="schedule",
        description="ดูตารางรายการ Bakery FM"
    )
    async def radio_schedule(interaction):

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} ตาราง Bakery FM",
            description=(
                f"{RADIO_EMOJI_2} **ช่วงเช้า**\n"
                "08:00 • Bakery Morning\n\n"
                f"{RADIO_EMOJI_2} **ช่วงบ่าย**\n"
                "13:00 • Bakery Afternoon\n\n"
                f"{RADIO_EMOJI_2} **ช่วงเย็น**\n"
                "18:00 • Bakery Evening\n\n"
                f"{RADIO_EMOJI_2} **ช่วงดึก**\n"
                "21:00 • Bakery Night"
            ),
            color=0xD8A15D
        )

        embed.set_footer(
            text="Bakery FM • Bakery House Community"
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # /radio news
    # =========================

    @radio.command(
        name="news",
        description="ดูข่าวสารล่าสุดจาก Bakery FM"
    )
    async def radio_news(interaction):

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} Bakery FM News",
            description=(
                f"{RADIO_EMOJI_2} "
                "**ข่าวสารจากบ้าน Bakery House**\n\n"
                "ติดตามประกาศ กิจกรรม และข่าวสารต่าง ๆ "
                "ของชุมชนได้ที่นี่"
            ),
            color=0xD8A15D
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # /radio request
    # =========================

    @radio.command(
        name="request",
        description="ส่งคำขอเพลงหรือรายการให้ Bakery FM"
    )
    @app_commands.describe(
        message="ระบุชื่อเพลงหรือรายการที่ต้องการ"
    )
    async def radio_request(interaction, message: str):

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} ส่งคำขอสำเร็จ",
            description=(
                f"{RADIO_EMOJI_2} ผู้ขอ: {interaction.user.mention}\n\n"
                f"คำขอ:\n**{message}**\n\n"
                "ทีมงาน Bakery FM ได้รับคำขอแล้ว"
            ),
            color=0xD8A15D
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # /radio shoutout
    # =========================

    @radio.command(
        name="shoutout",
        description="ฝากข้อความให้สมาชิกใน Bakery FM"
    )
    @app_commands.describe(
        message="ข้อความที่ต้องการฝาก"
    )
    async def radio_shoutout(interaction, message: str):

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} Bakery FM Shoutout",
            description=(
                f"{RADIO_EMOJI_2} จาก {interaction.user.mention}\n\n"
                f"**{message}**"
            ),
            color=0xD8A15D
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # /radio mystery
    # =========================

    @radio.command(
        name="mystery",
        description="สุ่มข้อความลึกลับจาก Bakery FM"
    )
    async def radio_mystery(interaction):

        messages = [
            "คืนนี้อาจมีบางอย่างกำลังรอคุณอยู่...",
            "มีเสียงบางอย่างดังมาจากหลังร้าน...",
            "มีสมาชิกบางคนกำลังถูกพูดถึงในสถานี...",
            "วันนี้คุณอาจได้รับเซอร์ไพรส์จาก Bakery House",
            "อย่าเพิ่งปิดวิทยุ...รายการนี้ยังไม่จบ"
        ]

        message = random.choice(messages)

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} Bakery FM Mystery",
            description=f"{RADIO_EMOJI_2} **{message}**",
            color=0x6B4C7A
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # /radio stats
    # =========================

    @radio.command(
        name="stats",
        description="ดูสถานะระบบ Bakery FM"
    )
    async def radio_stats(interaction):

        status = (
            "🟢 กำลังออกอากาศ"
            if radio_status
            else
            "🔴 ปิดสถานี"
        )

        if radio_start_time:
            timestamp = int(radio_start_time.timestamp())
            start_text = f"<t:{timestamp}:R>"
        else:
            start_text = "ยังไม่ได้เริ่ม"

        voice_status = (
            "🟢 เชื่อมต่อห้องเสียง"
            if radio_voice and radio_voice.is_connected()
            else
            "🔴 ไม่ได้เชื่อมต่อ"
        )

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} Bakery FM Status",
            color=0xD8A15D
        )

        embed.add_field(
            name="สถานะ",
            value=status,
            inline=False
        )

        embed.add_field(
            name="เริ่มออกอากาศ",
            value=start_text,
            inline=False
        )

        embed.add_field(
            name="Voice",
            value=voice_status,
            inline=False
        )

        embed.add_field(
            name="สถานี",
            value="Bakery FM",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # /radio join
    # =========================

    @radio.command(
        name="join",
        description="ให้ Bakery FM เข้าห้องเสียงของคุณ"
    )
    async def radio_join(interaction):

        global radio_voice

        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ คุณต้องอยู่ในห้อง Voice ก่อน",
                ephemeral=True
            )
            return

        channel = interaction.user.voice.channel

        try:
            if radio_voice and radio_voice.is_connected():
                await radio_voice.move_to(channel)
            else:
                radio_voice = await channel.connect()

            await interaction.response.send_message(
                f"{RADIO_EMOJI_1} Bakery FM เข้าห้อง **{channel.name}** แล้ว"
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ ไม่สามารถเข้าห้องเสียงได้\n```{e}```",
                ephemeral=True
            )

    # =========================
    # /radio play
    # =========================

    @radio.command(
        name="play",
        description="เล่นเสียงจาก URL"
    )
    @app_commands.describe(
        url="URL ของเพลงหรือสตรีมเสียง"
    )
    async def radio_play(interaction, url: str):

        global radio_voice
        global radio_player_url

        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ คุณต้องอยู่ในห้อง Voice ก่อน",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        channel = interaction.user.voice.channel

        try:
            if not radio_voice or not radio_voice.is_connected():
                radio_voice = await channel.connect()

            elif radio_voice.channel != channel:
                await radio_voice.move_to(channel)

            ytdl_options = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True
            }

            loop = asyncio.get_running_loop()

            def extract_audio():
                with yt_dlp.YoutubeDL(ytdl_options) as ytdl:
                    info = ytdl.extract_info(
                        url,
                        download=False
                    )

                    if "entries" in info:
                        info = info["entries"][0]

                    return info["url"]

            audio_url = await loop.run_in_executor(
                None,
                extract_audio
            )

            if radio_voice.is_playing():
                radio_voice.stop()

            ffmpeg_options = {
                "before_options": (
                    "-reconnect 1 "
                    "-reconnect_streamed 1 "
                    "-reconnect_delay_max 5"
                ),
                "options": "-vn"
            }

            source = discord.FFmpegPCMAudio(
                audio_url,
                **ffmpeg_options
            )

            radio_voice.play(
                source,
                after=lambda e: print(
                    f"Radio player ended: {e}"
                )
            )

            radio_player_url = url

            await interaction.followup.send(
                f"{RADIO_EMOJI_1} **Bakery FM กำลังเล่นเสียงแล้ว**\n"
                f"{RADIO_EMOJI_2} ห้อง: **{channel.name}**"
            )

        except Exception as e:

            await interaction.followup.send(
                f"❌ ไม่สามารถเล่นเสียงได้\n```{e}```"
            )

    # =========================
    # /radio pause
    # =========================

    @radio.command(
        name="pause",
        description="หยุดเสียงชั่วคราว"
    )
    async def radio_pause(interaction):

        if not radio_voice or not radio_voice.is_connected():
            await interaction.response.send_message(
                "❌ Bakery FM ไม่ได้อยู่ในห้องเสียง",
                ephemeral=True
            )
            return

        if not radio_voice.is_playing():
            await interaction.response.send_message(
                "❌ ตอนนี้ไม่มีเสียงที่กำลังเล่น",
                ephemeral=True
            )
            return

        radio_voice.pause()

        await interaction.response.send_message(
            f"{RADIO_EMOJI_1} ⏸️ หยุดเสียงชั่วคราวแล้ว"
        )

    # =========================
    # /radio resume
    # =========================

    @radio.command(
        name="resume",
        description="เล่นเสียงต่อ"
    )
    async def radio_resume(interaction):

        if not radio_voice or not radio_voice.is_connected():
            await interaction.response.send_message(
                "❌ Bakery FM ไม่ได้อยู่ในห้องเสียง",
                ephemeral=True
            )
            return

        if not radio_voice.is_paused():
            await interaction.response.send_message(
                "❌ ตอนนี้เสียงไม่ได้ถูกพักไว้",
                ephemeral=True
            )
            return

        radio_voice.resume()

        await interaction.response.send_message(
            f"{RADIO_EMOJI_1} ▶️ เล่นเสียงต่อแล้ว"
        )

    # =========================
    # /radio leave
    # =========================

    @radio.command(
        name="leave",
        description="ให้ Bakery FM ออกจากห้องเสียง"
    )
    async def radio_leave(interaction):

        global radio_voice
        global radio_player_url

        if not radio_voice or not radio_voice.is_connected():
            await interaction.response.send_message(
                "❌ Bakery FM ไม่ได้อยู่ในห้องเสียง",
                ephemeral=True
            )
            return

        await radio_voice.disconnect()

        radio_voice = None
        radio_player_url = None

        await interaction.response.send_message(
            f"{RADIO_EMOJI_1} Bakery FM ออกจากห้องเสียงแล้ว"
        )

    # =========================
    # /radio start
    # =========================

    @radio.command(
        name="start",
        description="เปิดสถานี Bakery FM"
    )
    @app_commands.default_permissions(
        manage_guild=True
    )
    async def radio_start(interaction):

        global radio_status
        global radio_start_time

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
                ephemeral=True
            )
            return

        if radio_status:
            await interaction.response.send_message(
                f"{RADIO_EMOJI_1} Bakery FM กำลังออกอากาศอยู่แล้ว",
                ephemeral=True
            )
            return

        radio_status = True
        radio_start_time = datetime.now()

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} Bakery FM",
            description=(
                f"{RADIO_EMOJI_2} **สถานีเปิดแล้ว!**\n\n"
                "Bakery FM เริ่มออกอากาศแล้ว\n"
                "สามารถให้บอทเข้าห้องเสียงและเล่นเสียงได้"
            ),
            color=0xD8A15D
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =========================
    # /radio stop
    # =========================

    @radio.command(
        name="stop",
        description="ปิดสถานี Bakery FM"
    )
    @app_commands.default_permissions(
        manage_guild=True
    )
    async def radio_stop(interaction):

        global radio_status
        global radio_start_time
        global radio_voice
        global radio_player_url

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "คุณไม่มีสิทธิ์ใช้คำสั่งนี้",
                ephemeral=True
            )
            return

        if radio_voice and radio_voice.is_connected():

            if radio_voice.is_playing():
                radio_voice.stop()

            await radio_voice.disconnect()

        radio_voice = None
        radio_player_url = None
        radio_status = False
        radio_start_time = None

        embed = discord.Embed(
            title=f"{RADIO_EMOJI_1} Bakery FM",
            description=(
                f"{RADIO_EMOJI_2} **สถานีปิดแล้ว**\n\n"
                "ขอบคุณทุกคนที่รับฟัง Bakery FM"
            ),
            color=0x777777
        )

        await interaction.response.send_message(
            embed=embed
        )
