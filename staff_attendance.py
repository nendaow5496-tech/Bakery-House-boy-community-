import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

TZ = ZoneInfo("Asia/Bangkok")
DB_FILE = "staff_attendance.db"
LEAVE_REVIEW_CHANNEL_ID = 1558155630529876068


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
            active = db.execute("""
                SELECT id FROM attendance
                WHERE guild_id = ? AND user_id = ? AND clock_out IS NULL
            """, (interaction.guild.id, interaction.user.id)).fetchone()

            if active:
                await interaction.response.send_message(
                    "คุณเข้างานอยู่แล้ว กรุณากดออกงานก่อน",
                    ephemeral=True,
                )
                return

            db.execute("""
                INSERT INTO attendance
                (guild_id, user_id, clock_in)
                VALUES (?, ?, ?)
            """, (
                interaction.guild.id,
                interaction.user.id,
                now_thai().isoformat(),
            ))

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
            row = db.execute("""
                SELECT id, clock_in FROM attendance
                WHERE guild_id = ? AND user_id = ? AND clock_out IS NULL
                ORDER BY id DESC LIMIT 1
            """, (interaction.guild.id, interaction.user.id)).fetchone()

            if not row:
                await interaction.response.send_message(
                    "ไม่พบรายการเข้างานที่ยังเปิดอยู่",
                    ephemeral=True,
                )
                return

            start = datetime.fromisoformat(row[1])
            minutes = max(0, int((now - start).total_seconds() // 60))

            db.execute("""
                UPDATE attendance
                SET clock_out = ?, duration_minutes = ?
                WHERE id = ?
            """, (now.isoformat(), minutes, row[0]))

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
            "คุณแน่ใจหรือไม่ว่าต้องการลาออก? ระบบจะถอดเฉพาะยศทีมงานที่กำหนด",
            view=ResignConfirmView(),
            ephemeral=True,
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
            cursor = db.execute("""
                INSERT INTO leave_requests
                (guild_id, user_id, start_date, end_date, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                interaction.guild.id,
                interaction.user.id,
                start.isoformat(),
                end.isoformat(),
                self.reason.value,
                now_thai().isoformat(),
            ))
            request_id = cursor.lastrowid

        channel = interaction.guild.get_channel(LEAVE_REVIEW_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                f"บันทึกใบลาเลขที่ {request_id} แล้ว แต่ไม่พบห้องตรวจสอบ "
                "กรุณาแจ้งผู้ดูแลระบบ",
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

        await channel.send(embed=embed)
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
        roles = [role for role in member.roles if role.id in STAFF_ROLE_IDS]

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
            url="https://cdn.discordapp.com/attachments/1556561306071474216/1558725224575275008/file_0000000037d08206bb625d68fc853b10.png?ex=6acc7b7d&is=6acb29fd&hm=da104ef0d0fa915599789f39d865b7cd4512522bd3bf3e2ce6442a05ff4c54dc"
        )
        await interaction.response.send_message(
            embed=embed,
            view=AttendancePanel(),
        )
