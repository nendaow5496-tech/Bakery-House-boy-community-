import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from staff_config import DB_FILE

THAI_TZ = ZoneInfo("Asia/Bangkok")


def connect_db():
    return sqlite3.connect(DB_FILE)


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS employee_of_the_month (
                guild_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                selected_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, month)
            )
        """)
        db.commit()


def get_employee_of_the_month(guild_id: int, month: str):
    with connect_db() as db:
        row = db.execute(
            "SELECT user_id, reason, selected_by, created_at FROM employee_of_the_month WHERE guild_id = ? AND month = ?",
            (guild_id, month),
        ).fetchone()
        return row


def set_employee_of_the_month(guild_id: int, month: str, user_id: int, reason: str, selected_by: int):
    with connect_db() as db:
        db.execute(
            "INSERT INTO employee_of_the_month (guild_id, month, user_id, reason, selected_by, created_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(guild_id, month) DO UPDATE SET user_id = excluded.user_id, reason = excluded.reason, selected_by = excluded.selected_by, created_at = excluded.created_at",
            (guild_id, month, user_id, reason, selected_by, datetime.now(THAI_TZ).isoformat()),
        )
        db.commit()


async def setup_staff_employee(bot):
    init_db()

    @bot.tree.command(
        name="employee_of_month",
        description="เลือกพนักงานดีเด่นประจำเดือน (ผู้ดูแลเท่านั้น)",
    )
    @app_commands.default_permissions(administrator=True)
    async def employee_of_month(
        interaction: discord.Interaction,
        month: str,
        member: discord.Member,
        reason: str,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        if member.bot:
            await interaction.response.send_message("ไม่สามารถเลือกบอทเป็นพนักงานดีเด่นได้", ephemeral=True)
            return

        set_employee_of_the_month(
            interaction.guild.id,
            month,
            member.id,
            reason,
            interaction.user.id,
        )

        await interaction.response.send_message(
            f"บันทึกพนักงานดีเด่นประจำเดือน {month} แล้ว: {member.mention}\nเหตุผล: {reason}",
            ephemeral=True,
        )

    @bot.tree.command(
        name="show_employee_of_month",
        description="ดูรายชื่อพนักงานดีเด่นประจำเดือน",
    )
    async def show_employee_of_month(interaction: discord.Interaction, month: str):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        row = get_employee_of_the_month(interaction.guild.id, month)
        if row is None:
            await interaction.response.send_message(f"ยังไม่มีการเลือกพนักงานดีเด่นสำหรับเดือน {month}", ephemeral=True)
            return

        user_id, reason, selected_by, created_at = row
        member = interaction.guild.get_member(user_id)
        display = member.mention if member else f"<@{user_id}>"
        await interaction.response.send_message(
            f"พนักงานดีเด่นประจำเดือน {month}: {display}\nเหตุผล: {reason}\nเลือกโดย: <@{selected_by}>\nเวลา: {created_at[:16]}",
            ephemeral=True,
        )

    return True


__all__ = [
    "init_db",
    "get_employee_of_the_month",
    "set_employee_of_the_month",
    "setup_staff_employee",
]
