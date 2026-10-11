import sqlite3
from typing import List, Optional

import discord
from discord import app_commands

DB_FILE = "staff_attendance.db"

DEFAULT_ROLE_IDS = [
    1556386505990213702,
    1557753342766096505,
    1558076158736732330,
    1558076631480803388,
]
DEFAULT_LEAVE_REVIEW_CHANNEL_ID = 1558155630529876068
DEFAULT_ALERT_CHANNEL_ID = None


def connect_db():
    return sqlite3.connect(DB_FILE)


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (guild_id, key)
            )
        """)
        db.commit()


def set_setting(guild_id: int, key: str, value: str):
    with connect_db() as db:
        db.execute(
            "INSERT INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
            (guild_id, key, value),
        )
        db.commit()


def get_setting(guild_id: int, key: str, default=None):
    with connect_db() as db:
        row = db.execute(
            "SELECT value FROM guild_settings WHERE guild_id = ? AND key = ?",
            (guild_id, key),
        ).fetchone()
        if row is None:
            return default
        return row[0]


def get_staff_role_ids(guild_id: int) -> List[int]:
    raw = get_setting(guild_id, "staff_role_ids", "")
    if not raw:
        return list(DEFAULT_ROLE_IDS)
    try:
        ids = [int(part.strip()) for part in str(raw).split(",") if part.strip()]
        return ids or list(DEFAULT_ROLE_IDS)
    except ValueError:
        return list(DEFAULT_ROLE_IDS)


def set_staff_role_ids(guild_id: int, role_ids: List[int]):
    set_setting(guild_id, "staff_role_ids", ",".join(str(r) for r in role_ids))


def get_leave_review_channel_id(guild_id: int, default: Optional[int] = None) -> Optional[int]:
    value = get_setting(guild_id, "leave_review_channel_id", None)
    if value is None:
        return default if default is not None else DEFAULT_LEAVE_REVIEW_CHANNEL_ID
    try:
        return int(value)
    except (TypeError, ValueError):
        return default if default is not None else DEFAULT_LEAVE_REVIEW_CHANNEL_ID


def set_leave_review_channel_id(guild_id: int, channel_id: int):
    set_setting(guild_id, "leave_review_channel_id", str(channel_id))


def get_alert_channel_id(guild_id: int) -> Optional[int]:
    value = get_setting(guild_id, "alert_channel_id", "")
    if not value:
        return DEFAULT_ALERT_CHANNEL_ID
    try:
        return int(value)
    except ValueError:
        return DEFAULT_ALERT_CHANNEL_ID


def set_alert_channel_id(guild_id: int, channel_id: int):
    set_setting(guild_id, "alert_channel_id", str(channel_id))


async def setup_staff_config(bot):
    init_db()

    @bot.tree.command(
        name="set_staff_roles",
        description="ตั้งค่า Role ID ของทีมงานที่ใช้ระบบเข้างาน/แจ้งเตือน",
    )
    @app_commands.default_permissions(administrator=True)
    async def set_staff_roles(interaction: discord.Interaction, role_ids: str):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        values = []
        for part in role_ids.split(","):
            cleaned = part.strip()
            if not cleaned:
                continue
            try:
                values.append(int(cleaned))
            except ValueError:
                await interaction.response.send_message(
                    "รูปแบบ Role ID ไม่ถูกต้อง ต้องเป็นเลขคั่นด้วยคอมม่า เช่น 111,222,333",
                    ephemeral=True,
                )
                return

        if not values:
            await interaction.response.send_message("ต้องมี Role ID อย่างน้อย 1 ตัว", ephemeral=True)
            return

        set_staff_role_ids(interaction.guild.id, values)
        await interaction.response.send_message(
            f"ตั้งค่า Role ID ของทีมงานแล้ว: {', '.join(str(v) for v in values)}",
            ephemeral=True,
        )

    @bot.tree.command(
        name="set_leave_channel",
        description="ตั้งค่าห้องตรวจสอบใบลาของทีมงาน",
    )
    @app_commands.default_permissions(administrator=True)
    async def set_leave_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        set_leave_review_channel_id(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"ตั้งค่าห้องตรวจสอบใบลาเป็น {channel.mention} แล้ว",
            ephemeral=True,
        )

    @bot.tree.command(
        name="set_alert_channel",
        description="ตั้งค่าห้องแจ้งเตือนรายชื่อที่ยังไม่ลงเวลา (ไม่บังคับ)",
    )
    @app_commands.default_permissions(administrator=True)
    async def set_alert_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        set_alert_channel_id(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"ตั้งค่าห้องแจ้งเตือนเป็น {channel.mention} แล้ว",
            ephemeral=True,
        )

    @bot.tree.command(
        name="staff_config_status",
        description="ดูค่าการตั้งค่า Role ID และ Channel ID ของระบบทีมงาน",
    )
    @app_commands.default_permissions(administrator=True)
    async def staff_config_status(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        role_ids = get_staff_role_ids(interaction.guild.id)
        leave_channel_id = get_leave_review_channel_id(interaction.guild.id)
        alert_channel_id = get_alert_channel_id(interaction.guild.id)

        text = "```\n"
        text += f"Role IDs: {', '.join(str(r) for r in role_ids)}\n"
        text += f"Leave Review Channel: {leave_channel_id or 'ยังไม่ได้ตั้งค่า'}\n"
        text += f"Alert Channel: {alert_channel_id or 'ยังไม่ได้ตั้งค่า'}\n"
        text += "```"
        await interaction.response.send_message(text, ephemeral=True)

    return True


__all__ = [
    "DB_FILE",
    "DEFAULT_ROLE_IDS",
    "DEFAULT_LEAVE_REVIEW_CHANNEL_ID",
    "DEFAULT_ALERT_CHANNEL_ID",
    "init_db",
    "set_setting",
    "get_setting",
    "get_staff_role_ids",
    "set_staff_role_ids",
    "get_leave_review_channel_id",
    "set_leave_review_channel_id",
    "get_alert_channel_id",
    "set_alert_channel_id",
    "setup_staff_config",
]
