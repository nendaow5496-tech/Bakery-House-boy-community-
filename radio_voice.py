import discord
from discord import app_commands
import asyncio
import yt_dlp

voice_client = None
current_url = None


def setup_radio_voice(bot):

    voice = app_commands.Group(
        name="radio-voice",
        description="ระบบเสียงของ Bakery FM"
    )

    bot.tree.add_command(voice)

    # =========================
    # /radio-voice join
    # =========================

    @voice.command(
        name="join",
        description="ให้ Bakery FM เข้าห้องเสียง"
    )
    async def join(interaction: discord.Interaction):

        global voice_client

        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ คุณต้องเข้าห้อง Voice ก่อน",
                ephemeral=True
            )
            return

        channel = interaction.user.voice.channel

        try:
            if voice_client and voice_client.is_connected():
                await voice_client.move_to(channel)
            else:
                voice_client = await channel.connect()

            await interaction.response.send_message(
                f"🎙️ Bakery FM เข้าห้อง **{channel.name}** แล้ว"
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ ไม่สามารถเข้าห้องเสียงได้\n```{e}```",
                ephemeral=True
            )

    # =========================
    # /radio-voice leave
    # =========================

    @voice.command(
        name="leave",
        description="ให้ Bakery FM ออกจากห้องเสียง"
    )
    async def leave(interaction: discord.Interaction):

        global voice_client
        global current_url

        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message(
                "❌ Bakery FM ไม่ได้อยู่ในห้องเสียง",
                ephemeral=True
            )
            return

        if voice_client.is_playing():
            voice_client.stop()

        await voice_client.disconnect()

        voice_client = None
        current_url = None

