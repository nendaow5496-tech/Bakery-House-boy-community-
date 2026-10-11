import discord

WELCOME_CHANNEL_ID = 1556370421132300328

BAKERY_EMOJI = "<a:emoji_36:1557336264871780503>"


async def member_join(member):

    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)

    if channel is None:
        print("ไม่พบห้องต้อนรับ")
        return

    embed = discord.Embed(
        title=f"{BAKERY_EMOJI} สมาชิกใหม่เข้าบ้านแล้ว!",
        description=(
            f"ยินดีต้อนรับ {member.mention} {BAKERY_EMOJI}\n\n"
            f"เข้าสู่ **Bakery House Community**\n"
            f"บ้านหลังนี้ยินดีต้อนรับคุณเสมอ\n\n"
            f"╭───────────────╮\n"
            f"  {BAKERY_EMOJI} สมาชิกคนที่ **{member.guild.member_count}**\n"
            f"  {BAKERY_EMOJI} อย่าลืมแวะอ่านกฎของบ้าน\n"
            f"╰───────────────╯"
        ),
        color=0xD8A15D
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    embed.set_footer(
        text="Bakery House Community • ยินดีต้อนรับกลับบ้าน"
    )

    await channel.send(
        content=(
            f"{BAKERY_EMOJI} "
            f"**มีสมาชิกใหม่เข้าบ้านแล้ว!** "
            f"{member.mention}"
        ),
        embed=embed
    )


# =========================
# ระบบแจ้งเตือนสมาชิกบูสต์เซิร์ฟเวอร์
# =========================
BOOST_CHANNEL_ID = 1558414637874290688

async def member_boost(member):
    if member.bot:
        return

    guild = member.guild
    channel = guild.get_channel(BOOST_CHANNEL_ID)
    if channel is None:
        try:
            channel = await guild.fetch_channel(BOOST_CHANNEL_ID)
        except Exception as e:
            print(f"ไม่พบห้องประกาศบูสต์: {e}", flush=True)
            return

    boost_count = guild.premium_subscription_count or 0

    embed = discord.Embed(
        title="<a:emoji_53:1558434672973975612> ขอบคุณที่บูสต์เซิร์ฟเวอร์!",
        description=(
            f"ขอบคุณ {member.mention} ที่สนับสนุน "
            f"**Bakery House Community** <a:emoji_53:1558434672973975612>\n\n"
            "การบูสต์ของคุณช่วยให้ชุมชนของเราเติบโตขึ้น "
            "ขอบคุณที่เป็นส่วนหนึ่งของบ้านหลังนี้!\n\n"
            f"<a:emoji_53:1558434672973975612> บูสต์รวมของเซิร์ฟเวอร์: **{boost_count} ครั้ง**"
        ),
        color=0xD8A15D
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.set_image(url="https://cdn.discordapp.com/attachments/1558414637874290688/1558431969736527882/42b9ed4e879fedfc303832f2b4dce58d.jpg")

    embed.set_footer(text="Bakery House Community • Server Booster")

    try:
        await channel.send(
            content=f"<a:emoji_53:1558434672973975612> ขอบคุณ {member.mention} สำหรับการบูสต์เซิร์ฟเวอร์!",
            embed=embed
        )
    except Exception as e:
        print(f"ส่ง Embed บูสต์ไม่สำเร็จ: {e}", flush=True)
