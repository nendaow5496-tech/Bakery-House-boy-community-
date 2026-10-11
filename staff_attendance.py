import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from staff_config import (
    DB_FILE,
    get_leave_review_channel_id,
    get_staff_role_ids,
)

TZ = ZoneInfo("Asia/Bangkok")


def now_thai():
    return datetime.now(TZ)


def init_db():
    with sqlite3.connect(DB_FILE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                clock_in TEXT NOT NULL,
                clock_out TEXT,
                duration_minutes INTEGER
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS leave_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'รออนุมัติ',
                created_at TEXT NOT NULL
            )
        """)
        db.commit()


def is_leave_approved(guild_id: int, user_id: int, target_date: str) -> bool:
    with sqlite3.connect(DB_FILE) as db:
        row = db.execute(
            """
            SELECT 1
            FROM leave_requests
            WHERE guild_id = ?
              AND user_id = ?
              AND status = 'อนุมัติ'
              AND start_date <= ?
              AND end_date >= ?
            LIMIT 1
            """,
            (guild_id, user_id, target_date, target_date),
        ).fetchone()
        return row is not None


class AttendancePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="เข้างาน",
        style=discord.ButtonStyle.success,
        custom_id="staff_attendance:clock_in",
    )
    async def clock_in(self, interaction, button):
        if interaction.guild is None:
            await interaction.response.send_message(
                "ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True
            )
            return

        with sqlite3.connect(DB_FILE) as db:
            active = db.execute(
                """
                SELECT id FROM attendance
                WHERE guild_id = ? AND user_id = ? AND clock_out IS NULL
                """,
                (interaction.guild.id, interaction.user.id),
            ).fetchone()

            if active:
                await interaction.response.send_message(
                    "คุณเข้างานอยู่แล้ว กรุณากดออกงานก่อน",
                    ephemeral=True,
                )
                return

            db.execute(
                """
                INSERT INTO attendance (guild_id, user_id, clock_in)
                VALUES (?, ?, ?)
                """,
                (
                    interaction.guild.id,
                    interaction.user.id,
                    now_thai().isoformat(),
                ),
            )

        await interaction.response.send_message(
            f"บันทึกเวลาเข้างานแล้ว: {now_thai():%d/%m/%Y %H:%M}",
            ephemeral=True,
        )

    @discord.ui.button(
        label="ออกงาน",
        style=discord.ButtonStyle.danger,
        custom_id="staff_attendance:clock_out",
    )
    async def clock_out(self, interaction, button):
        if interaction.guild is None:
            await interaction.response.send_message(
                "ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True
            )
            return

        now = now_thai()

        with sqlite3.connect(DB_FILE) as db:
            row = db.execute(
                """
                SELECT id, clock_in FROM attendance
                WHERE guild_id = ? AND user_id = ? AND clock_out IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (interaction.guild.id, interaction.user.id),
            ).fetchone()

            if not row:
                await interaction.response.send_message(
                    "ไม่พบรายการเข้างานที่ยังเปิดอยู่",
                    ephemeral=True,
                )
                return

            start = datetime.fromisoformat(row[1])
            minutes = max(0, int((now - start).total_seconds() // 60))

            db.execute(
                """
                UPDATE attendance
                SET clock_out = ?, duration_minutes = ?
                WHERE id = ?
                """,
                (now.isoformat(), minutes, row[0]),
            )

        hours, remaining = divmod(minutes, 60)
        await interaction.response.send_message(
            f"บันทึกเวลาออกงานแล้ว: {now:%d/%m/%Y %H:%M}\n"
            f"ระยะเวลารวม {hours} ชั่วโมง {remaining} นาที",
            ephemeral=True,
        )

    @discord.ui.button(
        label="ลางาน",
        style=discord.ButtonStyle.primary,
        custom_id="staff_attendance:leave",
    )
    async def leave(self, interaction, button):
        await interaction.response.send_modal(LeaveModal())

    @discord.ui.button(
        label="ลาออก",
        style=discord.ButtonStyle.danger,
        custom_id="staff_attendance:resign",
    )
    async def resign(self, interaction, button):
        await interaction.response.send_message(
            "คุณแน่ใจหรือไม่ว่าต้องการลาออก? ระบบจะถอดเฉพาะยศทีมงานที่กำหนดไว้\n"
            "ยศสมาชิกทั่วไปยังคงอยู่",
            view=ResignConfirmView(),
            ephemeral=True,
        )


class LeaveReviewView(discord.ui.View):
    def __init__(self, request_id: int):
        super().__init__(timeout=180)
        self.request_id = request_id

    @discord.ui.button(
        label="อนุมัติ",
        style=discord.ButtonStyle.success,
        custom_id="staff_leave:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("เฉพาะผู้ดูแลเท่านั้นที่อนุมัติใบลา", ephemeral=True)
            return

        with sqlite3.connect(DB_FILE) as db:
            row = db.execute(
                """
                SELECT guild_id, user_id, start_date, end_date, reason
                FROM leave_requests
                WHERE id = ?
                """,
                (self.request_id,),
            ).fetchone()
            if not row:
                await interaction.response.send_message("ไม่พบใบลานี้", ephemeral=True)
                return
            db.execute(
                "UPDATE leave_requests SET status = 'อนุมัติ' WHERE id = ?",
                (self.request_id,),
            )

        guild_id, user_id, start_date, end_date, reason = row
        member = interaction.guild.get_member(user_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except Exception:
                member = None
        if member is not None:
            try:
                await member.send(
                    f"ใบลาของคุณได้รับการอนุมัติแล้ว\n"
                    f"ช่วงวันที่: {start_date} ถึง {end_date}\n"
                    f"เหตุผล: {reason}"
                )
            except Exception:
                pass

        await interaction.response.edit_message(
            content=f"✅ อนุมัติใบลา #{self.request_id} แล้ว",
            view=None,
        )

    @discord.ui.button(
        label="ปฏิเสธ",
        style=discord.ButtonStyle.danger,
        custom_id="staff_leave:reject",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("เฉพาะผู้ดูแลเท่านั้นที่ปฏิเสธใบลา", ephemeral=True)
            return

        with sqlite3.connect(DB_FILE) as db:
            row = db.execute(
                """
                SELECT guild_id, user_id, start_date, end_date, reason
                FROM leave_requests
                WHERE id = ?
                """,
                (self.request_id,),
            ).fetchone()
            if not row:
                await interaction.response.send_message("ไม่พบใบลานี้", ephemeral=True)
                return
            db.execute(
                "UPDATE leave_requests SET status = 'ปฏิเสธ' WHERE id = ?",
                (self.request_id,),
            )

        _, user_id, start_date, end_date, reason = row
        member = interaction.guild.get_member(user_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except Exception:
                member = None
        if member is not None:
            try:
                await member.send(
                    f"ใบลาของคุณไม่ได้รับการอนุมัติ\n"
                    f"ช่วงวันที่: {start_date} ถึง {end_date}\n"
                    f"เหตุผล: {reason}"
                )
            except Exception:
                pass

        await interaction.response.edit_message(
            content=f"❌ ปฏิเสธใบลา #{self.request_id} แล้ว",
            view=None,
        )


class LeaveModal(discord.ui.Modal, title="แบบฟอร์มขอลางาน"):
    start_date = discord.ui.TextInput(
        label="วันที่เริ่มลา (YYYY-MM-DD)",
        placeholder="เช่น 2026-10-15",
        max_length=10,
    )
    end_date = discord.ui.TextInput(
        label="วันที่สิ้นสุดการลา (YYYY-MM-DD)",
        placeholder="เช่น 2026-10-16",
        max_length=10,
    )
    reason = discord.ui.TextInput(
        label="เหตุผลในการลา",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    async def on_submit(self, interaction):
        try:
            start = datetime.strptime(self.start_date.value, "%Y-%m-%d").date()
            end = datetime.strptime(self.end_date.value, "%Y-%m-%d").date()
        except ValueError:
            await interaction.response.send_message(
                "รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้ YYYY-MM-DD",
                ephemeral=True,
            )
            return

        if end < start:
            await interaction.response.send_message(
                "วันที่สิ้นสุดต้องไม่ก่อนวันที่เริ่มลา",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True
            )
            return

        with sqlite3.connect(DB_FILE) as db:
            cursor = db.execute(
                """
                INSERT INTO leave_requests
                (guild_id, user_id, start_date, end_date, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'รออนุมัติ', ?)
                """,
                (
                    interaction.guild.id,
                    interaction.user.id,
                    start.isoformat(),
                    end.isoformat(),
                    self.reason.value,
                    now_thai().isoformat(),
                ),
            )
            request_id = cursor.lastrowid

        channel_id = get_leave_review_channel_id(interaction.guild.id)
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if channel is None:
            await interaction.response.send_message(
                f"บันทึกใบลาเลขที่ {request_id} แล้ว แต่ไม่พบห้องตรวจสอบ กรุณาแจ้งผู้ดูแลระบบ",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"ใบลางาน #{request_id}",
            color=discord.Color.orange(),
            timestamp=now_thai(),
        )
        embed.add_field(name="ผู้ขอลา", value=interaction.user.mention)
        embed.add_field(
            name="ช่วงวันที่ลา",
            value=f"{start.isoformat()} ถึง {end.isoformat()}",
            inline=False,
        )
        embed.add_field(name="เหตุผล", value=self.reason.value, inline=False)

        await channel.send(embed=embed, view=LeaveReviewView(request_id))
        await interaction.response.send_message(
            f"ส่งใบลาหมายเลข {request_id} ให้ทีมงานตรวจสอบแล้ว",
            ephemeral=True,
        )


class ResignConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="ยืนยันลาออก",
        style=discord.ButtonStyle.danger,
        custom_id="staff_attendance:resign_confirm",
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        from staff_management import STAFF_ROLE_IDS, add_history

        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        member = interaction.user
        roles = [role for role in member.roles if role.id in get_staff_role_ids(interaction.guild.id)]

        if not roles:
            await interaction.response.send_message("คุณไม่มียศทีมงานที่ระบบกำหนด", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await member.remove_roles(*roles, reason="Staff resignation requested by member")
        except discord.Forbidden:
            await interaction.followup.send("ถอดยศไม่สำเร็จ กรุณาตรวจสอบสิทธิ์และลำดับยศของบอท", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.followup.send("Discord ดำเนินการไม่สำเร็จ กรุณาลองใหม่", ephemeral=True)
            return

        add_history(
            interaction.guild.id,
            member.id,
            "resignation_completed",
            "ลาออกและถอดยศทีมงาน: " + ", ".join(role.name for role in roles),
        )
        await interaction.followup.send(
            "ดำเนินการลาออกแล้ว ยศสมาชิกทั่วไปยังคงอยู่",
            ephemeral=True,
        )

    @discord.ui.button(
        label="ยกเลิก",
        style=discord.ButtonStyle.secondary,
        custom_id="staff_attendance:resign_cancel",
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="ยกเลิกการลาออกแล้ว", view=None)


async def setup_staff_attendance(bot):
    init_db()
    bot.add_view(AttendancePanel())

    @bot.tree.command(
        name="staff_panel",
        description="แสดงแผงเข้างาน ออกงาน และลางาน",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def staff_panel(interaction: discord.Interaction):
        embed = discord.Embed(
            title="Bakery House Community",
            description="ระบบเข้างาน • ออกงาน • ลางาน • ลาออก",
            color=discord.Color.from_rgb(245, 230, 200),
        )
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/1556561306071474216/1558725224575275008/file_0000000037d08206bb625d68fc853b10.png?ex=6acc7b7d&is=6acb29fd&hm=da104ef0d0fa915599789f39d865b7dfe"
        )
        await interaction.response.send_message(
            embed=embed,
            view=AttendancePanel(),
        )

    @bot.tree.command(
        name="leave_status",
        description="ตรวจสอบสถานะการลาของตนเอง",
    )
    async def leave_status(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        with sqlite3.connect(DB_FILE) as db:
            rows = db.execute(
                """
                SELECT id, start_date, end_date, status, reason
                FROM leave_requests
                WHERE guild_id = ? AND user_id = ?
                ORDER BY id DESC LIMIT 10
                """,
                (interaction.guild.id, interaction.user.id),
            ).fetchall()

        if not rows:
            await interaction.response.send_message("ยังไม่มีประวัติการลา", ephemeral=True)
            return

        lines = [
            f"#{row_id} | {start} ถึง {end} | {status} | {reason}"
            for row_id, start, end, status, reason in rows
        ]
        await interaction.response.send_message(
            "```\n" + "\n".join(lines) + "\n```",
            ephemeral=True,
        )

    @bot.tree.command(
        name="approve_leave",
        description="อนุมัติหรือปฏิเสธใบลาตามหมายเลข (ผู้ดูแลเท่านั้น)",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def approve_leave(interaction: discord.Interaction, request_id: int, action: str):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        if action not in {"approve", "reject"}:
            await interaction.response.send_message("action ต้องเป็น approve หรือ reject", ephemeral=True)
            return

        with sqlite3.connect(DB_FILE) as db:
            row = db.execute(
                """
                SELECT user_id, start_date, end_date, reason
                FROM leave_requests
                WHERE id = ? AND guild_id = ?
                """,
                (request_id, interaction.guild.id),
            ).fetchone()
            if not row:
                await interaction.response.send_message("ไม่พบใบลานี้", ephemeral=True)
                return
            status = 'อนุมัติ' if action == 'approve' else 'ปฏิเสธ'
            db.execute(
                "UPDATE leave_requests SET status = ? WHERE id = ?",
                (status, request_id),
            )

        user_id, start_date, end_date, reason = row
        member = interaction.guild.get_member(user_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except Exception:
                member = None
        if member is not None:
            try:
                await member.send(
                    f"ใบลาของคุณถูก{('อนุมัติ' if action == 'approve' else 'ปฏิเสธ')}แล้ว\n"
                    f"ช่วงวันที่: {start_date} ถึง {end_date}\n"
                    f"เหตุผล: {reason}"
                )
            except Exception:
                pass

        await interaction.response.send_message(
            f"{('อนุมัติ' if action == 'approve' else 'ปฏิเสธ')}ใบลา #{request_id} แล้ว",
            ephemeral=True,
        )


__all__ = [
    "AttendancePanel",
    "LeaveModal",
    "LeaveReviewView",
    "ResignConfirmView",
    "is_leave_approved",
    "setup_staff_attendance",
]
