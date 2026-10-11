import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

THAI_TZ = ZoneInfo("Asia/Bangkok")
DB_FILE = "staff_management.db"

STAFF_ROLE_IDS = {
    1556386505990213702,  # Admin
    1557753342766096505,  # Police
    1558076158736732330,  # Event
    1558076631480803388,  # Entertainment
}


def now_thai():
    return datetime.now(THAI_TZ)


def connect_db():
    return sqlite3.connect(DB_FILE)


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS staff_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
        """)


def add_history(guild_id, user_id, event_type, details):
    with connect_db() as db:
        db.execute("""
            INSERT INTO staff_history
            (guild_id, user_id, event_type, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            event_type,
            details,
            now_thai().isoformat(),
        ))


async def setup_staff_management(bot):
    init_db()

    @bot.tree.command(
        name="resign",
        description="ลาออกจากทีมงานและถอดยศทันที",
    )
    async def resign(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "ไม่สามารถตรวจสอบสมาชิกได้",
                ephemeral=True,
            )
            return

        member = interaction.user
        roles_to_remove = [
            role for role in member.roles
            if role.id in STAFF_ROLE_IDS
        ]

        if not roles_to_remove:
            await interaction.response.send_message(
                "คุณไม่มียศทีมงานที่กำหนดไว้ในระบบ",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await member.remove_roles(
                *roles_to_remove,
                reason="Staff resignation requested by member",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "ถอดยศไม่สำเร็จ กรุณาตรวจสอบสิทธิ์ Manage Roles "
                "และลำดับยศของบอท",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "Discord ไม่สามารถดำเนินการได้ในขณะนี้ กรุณาลองใหม่",
                ephemeral=True,
            )
            return

        add_history(
            interaction.guild.id,
            member.id,
            "resignation_completed",
            "ลาออกและถอดยศทีมงาน: "
            + ", ".join(role.name for role in roles_to_remove),
        )

        await interaction.followup.send(
            "ดำเนินการลาออกแล้ว และถอดเฉพาะยศทีมงานที่กำหนด "
            "ยศสมาชิกทั่วไปยังคงอยู่",
            ephemeral=True,
        )

    @bot.tree.command(
        name="staff_history",
        description="ดูประวัติทีมงานของตนเอง",
    )
    async def staff_history(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "ใช้คำสั่งนี้ภายในเซิร์ฟเวอร์เท่านั้น",
                ephemeral=True,
            )
            return

        with connect_db() as db:
            rows = db.execute("""
                SELECT event_type, details, created_at
                FROM staff_history
                WHERE guild_id = ? AND user_id = ?
                ORDER BY id DESC
                LIMIT 10
            """, (
                interaction.guild.id,
                interaction.user.id,
            )).fetchall()

        if not rows:
            message = "ยังไม่มีประวัติทีมงาน"
        else:
            message = "\n".join(
                f"• {event_type}: {details or '-'} "
                f"({created_at[:16]})"
                for event_type, details, created_at in rows
            )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )
