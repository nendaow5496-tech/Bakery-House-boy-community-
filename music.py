import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

YTDL_OPTS = {"format": "bestaudio/best", "noplaylist": True, "quiet": True, "default_search": "ytsearch"}
FFMPEG_OPTS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    async def _play_next(self, guild):
        vc = guild.voice_client
        q = self.queues.get(guild.id)
        if not vc or not q:
            return
        title, url = q.pop(0)
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTS)
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self._play_next(guild), self.bot.loop))
    @app_commands.command(name="play", description="เล่นเพลงจาก URL หรือชื่อเพลง")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("เข้าห้องเสียงก่อนนะครับ", ephemeral=True)
        await interaction.response.defer()
        channel = interaction.user.voice.channel
        vc = interaction.guild.voice_client
        if vc is None:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)
        loop = asyncio.get_running_loop()
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ytdl:
                info = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        except Exception as e:
            return await interaction.followup.send(f"โหลดเพลงไม่ได้: {e}")
        if "entries" in info:
            info = info["entries"][0]
        self.queues.setdefault(interaction.guild.id, []).append((info["title"], info["url"]))
        if vc.is_playing() or vc.is_paused():
            await interaction.followup.send(f"เพิ่มในคิว: **{info['title']}**")
        else:
            await interaction.followup.send(f"กำลังเล่น: **{info['title']}**")
            await self._play_next(interaction.guild)
    @app_commands.command(name="skip", description="ข้ามเพลง")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("ข้ามแล้ว")
        else:
            await interaction.response.send_message("ไม่มีเพลงที่เล่นอยู่", ephemeral=True)

    @app_commands.command(name="pause", description="หยุดชั่วคราว")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("หยุดชั่วคราว")
        else:
            await interaction.response.send_message("ไม่มีเพลงที่เล่นอยู่", ephemeral=True)

    @app_commands.command(name="resume", description="เล่นต่อ")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("เล่นต่อแล้ว")
        else:
            await interaction.response.send_message("ไม่ได้หยุดอยู่", ephemeral=True)
    @app_commands.command(name="queue", description="ดูคิวเพลง")
    async def queue(self, interaction: discord.Interaction):
        q = self.queues.get(interaction.guild.id, [])
        if not q:
            return await interaction.response.send_message("คิวว่าง", ephemeral=True)
        text = "\n".join(f"{i+1}. {t}" for i, (t, _) in enumerate(q[:10]))
        await interaction.response.send_message(text)

    @app_commands.command(name="leave", description="ให้บอทออกจากห้องเสียง")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        self.queues.pop(interaction.guild.id, None)
        if vc:
            await vc.disconnect()
            await interaction.response.send_message("ออกจากห้องแล้ว")
        else:
            await interaction.response.send_message("บอทไม่ได้อยู่ในห้องเสียง", ephemeral=True)


async def setup_music(bot):
    await bot.add_cog(Music(bot))
