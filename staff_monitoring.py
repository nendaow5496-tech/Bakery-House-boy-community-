import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from discord.ext import tasks

from staff_config import DB_FILE, get_staff_role_ids

THAI_TZ = ZoneInfo("Asia/Bangkok")
BOT = None


def now_thai():
    return datetime.now(THAI_TZ)


def connect_db():
    return sqlite3.connect(DB_FILE)


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS reminder_log (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                alert_date TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id, alert_date)
            )
        """)
        db.commit()


def get_missing_staff_ids(guild_id: int, target_date: str):
    with connect_db() as db:
        role_ids = get_staff_role_ids(guild_id)
        if not role_ids:
            return []

        attendance_rows = db.execute(
            """
            SELECT user_id, clock_in, clock_out
            FROM attendance
            WHERE guild_id = ? AND clock_in LIKE ?
            """,
            (guild_id, f"{target_date}%"),
        ).fetchall()

        logged_clock_in = {}
        logged_clock_out = {}
        for user_id, clock_in, clock_out in attendance_rows:
            uid = int(user_id)
            logged_clock_in[uid] = clock_in
            logged_clock_out[uid] = clock_out

        approved_leave = set()
        leave_rows = db.execute(
            """
            SELECT DISTINCT user_id
            FROM leave_requests
            WHERE guild_id = ? AND status = 'อนุมัติ'
              AND start_date <= ? AND end_date >= ?
            """,
            (guild_id, target_date, target_date),
        ).fetchall()
        for (user_id,) in leave_rows:
            approved_leave.add(int(user_id))

        missing = []
        guild = BOT.get_guild(guild_id) if BOT else None
        if guild is None:
            return []

        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role is None:
                continue
            for member in role.members:
                if member.bot:
                    continue
                if member.id in approved_leave:
                    continue

                # ถ้าคุณมี clock_in ในวันนั้นแล้ว และ clock_out ไม่ว่าง => ลงเวลาเรียบร้อย
                # ถ้าคุณมี clock_in แต่ clock_out ว่าง => ยังไม่ปิดงาน -> ยังถือว่า missing
                if member.id in logged_clock_in and logged_clock_out.get(member.id) is not None:
                    continue

                if member.id not in missing:
                    missing.append(member.id)
        return missing


async def send_dm_once(guild, user_id: int, target_date: str):
    with connect_db() as db:
        row = db.execute(
            "SELECT 1 FROM reminder_log WHERE guild_id = ? AND user_id = ? AND alert_date = ?",
            (guild.id, user_id, target_date),
        ).fetchone()
        if row is not None:
            return

    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            return

    try:
        await member.send(
            f"ระบบตรวจพบว่าคุณยังไม่ได้ลงเวลาเข้างานสำหรับวันที่ {target_date}\n"
            "กรุณาลงเวลาให้ครบถ้วนก่อนเวลา 20:00 น. ตามเวลาไทย\n"
            "※ ระบบนี้ส่งเฉพาะบุคคล ไม่ใช้ @everyone หรือ @here"
        )
        with connect_db() as db:
            db.execute(
                "INSERT INTO reminder_log (guild_id, user_id, alert_date, sent_at) VALUES (?, ?, ?, ?)",
                (guild.id, user_id, target_date, now_thai().isoformat()),
            )
            db.commit()
    except Exception:
        pass


async def process_all_guilds_for_current_time():
    if BOT is None:
        return

    target_date = now_thai().date().isoformat()
    for guild in BOT.guilds:
        for user_id in get_missing_staff_ids(guild.id, target_date):
            await send_dm_once(guild, user_id, target_date)


@tasks.loop(minutes=1)
async def reminder_loop():
    if BOT is None or not BOT.is_ready():
        return

    now = now_thai()
    if now.hour == 20 and now.minute <= 2:
        await process_all_guilds_for_current_time()


@reminder_loop.before_loop
async def before_reminder_loop():
    await BOT.wait_until_ready()


async def setup_staff_monitoring(bot):
    global BOT
    BOT = bot
    init_db()
    if not reminder_loop.is_running():
        reminder_loop.start()

    @bot.tree.command(
        name="manual_absence_check",
        description="ตรวจสอบรายชื่อทีมงานที่ยังไม่ได้ลงเวลาในวันนี้ (ผู้ดูแลเท่านั้น)",
    )
    async def manual_absence_check(interaction):
        if interaction.guild is None:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("สำหรับผู้ดูแลเท่านั้น", ephemeral=True)
            return

        target_date = now_thai().date().isoformat()
        missing = get_missing_staff_ids(interaction.guild.id, target_date)
        if not missing:
            await interaction.response.send_message("ไม่มีทีมงานที่ยังไม่ได้ลงเวลาในวันนี้", ephemeral=True)
            return

        names = []
        for user_id in missing:
            member = interaction.guild.get_member(user_id)
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(user_id)
                except Exception:
                    continue
            names.append(member.display_name if member else str(user_id))

        await interaction.response.send_message(
            "ทีมงานที่ยังไม่ได้ลงเวลาในวันนี้:\n" + "\n".join(f"• {name}" for name in names),
            ephemeral=True,
        )

    return True


__all__ = [
    "now_thai",
    "init_db",
    "get_missing_staff_ids",
    "send_dm_once",
    "process_all_guilds_for_current_time",
    "setup_staff_monitoring",
]
