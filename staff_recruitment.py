import discord
from discord.ext import commands
from discord import app_commands

APPLY_CHANNEL_ID = 1556654127872745573
REVIEW_CHANNEL_ID = 1558155630529876068

STAFF_REVIEWER_ROLE_IDS = [
    1556386319293218957,
    1556386431277080676,
    1556386505990213702,
]

POSITIONS = [
    ("🐰 ⊹ ADMIN . ꒱", "admin"),
    ("🐼 ⊹ POLICE . ꒱", "police"),
    ("🐻‍❄️ ⊹ EVENT . ꒱", "event"),
    ("🐹 ⊹ DOCTOR . ꒱", "doctor"),
    ("🦊 ⊹ ENTERTAIN . ꒱", "entertain"),
]

CLOSED_POSITION = "🐺 ⊹ DJ . ꒱"

# ภาพการ์ดรับสมัครจาก Discord CDN
RECRUITMENT_IMAGE_URLS = {
    "banner": "https://cdn.discordapp.com/attachments/1556654127872745573/1558177998052524062/01_header_banner.png",
    "admin": "https://cdn.discordapp.com/attachments/1556654127872745573/1558177998685868074/02_admin_card.png",
    "police": "https://cdn.discordapp.com/attachments/1556654127872745573/1558177999428390982/03_police_card.png",
    "event": "https://cdn.discordapp.com/attachments/1556654127872745573/1558177999814262956/04_event_card.png",
    "doctor": "https://cdn.discordapp.com/attachments/1556654127872745573/1558178000200011868/05_doctor_card.png",
    "entertain": "https://cdn.discordapp.com/attachments/1556654127872745573/1558178000585892051/06_entertain_card.png",
    "dj": "https://cdn.discordapp.com/attachments/1556654127872745573/1558178000959307876/07_dj_closed_card.png",
}



class ApplicationModal(discord.ui.Modal, title="แบบฟอร์มสมัครทีมงาน"):
    applicant_name = discord.ui.TextInput(
        label="ชื่อที่ใช้เรียก",
        placeholder="ชื่อเล่นหรือชื่อที่สมาชิกเรียก",
        max_length=50,
    )
    age = discord.ui.TextInput(
        label="อายุ",
        placeholder="ระบุอายุ",
        max_length=3,
    )
    experience = discord.ui.TextInput(
        label="ประสบการณ์",
        placeholder="เคยทำงานด้านนี้หรือไม่",
        style=discord.TextStyle.paragraph,
        max_length=800,
    )
    reason = discord.ui.TextInput(
        label="เหตุผลที่สมัคร",
        placeholder="เพราะอะไรจึงอยากเข้าทีมนี้",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    availability = discord.ui.TextInput(
        label="เวลาที่สะดวก",
        placeholder="เช่น หลังเลิกเรียนหรือวันหยุด",
        max_length=300,
        required=False,
    )

    def __init__(self, position):
        super().__init__()
        self.position = position

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.client.get_channel(REVIEW_CHANNEL_ID)

        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(
                    REVIEW_CHANNEL_ID
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "ไม่พบช่องตรวจใบสมัคร กรุณาแจ้งทีมงาน",
                    ephemeral=True,
                )
                return

        embed = discord.Embed(
            title="📋 ใบสมัครทีมงานใหม่",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="ตำแหน่ง",
            value=self.position,
            inline=False,
        )
        embed.add_field(
            name="ผู้สมัคร",
            value=f"{interaction.user.mention}\nID: `{interaction.user.id}`",
            inline=False,
        )
        embed.add_field(
            name="ชื่อที่ใช้เรียก",
            value=self.applicant_name.value,
            inline=True,
        )
        embed.add_field(
            name="อายุ",
            value=self.age.value,
            inline=True,
        )
        embed.add_field(
            name="ประสบการณ์",
            value=self.experience.value,
            inline=False,
        )
        embed.add_field(
            name="เหตุผลที่สมัคร",
            value=self.reason.value,
            inline=False,
        )
        embed.add_field(
            name="เวลาที่สะดวก",
            value=self.availability.value or "ไม่ได้ระบุ",
            inline=False,
        )
        embed.add_field(
            name="สถานะ",
            value="🟠 รอตรวจสอบ",
            inline=False,
        )

        view = ReviewView()

        try:
            await channel.send(embed=embed, view=view)
        except discord.HTTPException:
            await interaction.response.send_message(
                "ส่งใบสมัครไม่สำเร็จ กรุณาแจ้งทีมงาน",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "ส่งใบสมัครเรียบร้อยแล้ว กรุณารอทีมงานตรวจสอบ",
            ephemeral=True,
        )
class PositionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=position,
                value=position,
                description="เปิดรับสมัคร",
            )
            for position, _ in POSITIONS
        ]
        super().__init__(
            placeholder="เลือกตำแหน่งที่ต้องการสมัคร",
            custom_id="recruitment:position",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ApplicationModal(self.values[0])
        )


class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PositionSelect())

    @discord.ui.button(
        label="DJ — ยังไม่เปิดรับสมัคร",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="recruitment:closed_dj",
    )
    async def closed_dj(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "ตำแหน่ง 🐺 DJ ยังไม่เปิดรับสมัคร",
            ephemeral=True,
        )




POSITION_CARD_DATA = {
    "admin": ("👑", "ADMIN", "ดูแลภาพรวมและจัดการชุมชน",
              "ดูแลเซิร์ฟเวอร์ ประสานงานทีม และช่วยแก้ปัญหาสำคัญ",
              0xA66B4F),
    "police": ("🛡️", "POLICE", "ดูแลกฎระเบียบ",
               "ตรวจสอบการละเมิดกฎ ช่วยแก้ปัญหา และรายงานทีมงาน",
               0x6685A8),
    "event": ("🎉", "EVENT", "สร้างกิจกรรมให้ชุมชน",
              "วางแผนกิจกรรม ดูแลการดำเนินงาน และเสนอไอเดียใหม่",
              0xD59A55),
    "doctor": ("🩺", "DOCTOR", "ช่วยเหลือสมาชิก",
               "รับฟังปัญหา ตอบคำถาม และประสานงานเมื่อจำเป็น",
               0xD98282),
    "entertain": ("🎤", "ENTERTAIN", "เติมสีสันให้ชุมชน",
                  "สร้างความสนุก ดูแลบรรยากาศ และคิดกิจกรรมสร้างสรรค์",
                  0x9A78B5),
}


class PositionCardView(discord.ui.View):
    def __init__(self, position_key):
        super().__init__(timeout=None)
        self.position_key = position_key
        button = discord.ui.Button(
            label="สมัครตำแหน่งนี้",
            emoji="🥐",
            style=discord.ButtonStyle.success,
            custom_id=f"recruitment:card:{position_key}",
        )
        button.callback = self.apply
        self.add_item(button)

    async def apply(self, interaction: discord.Interaction):
        position_label = next(
            label for label, key in POSITIONS
            if key == self.position_key
        )
        await interaction.response.send_modal(
            ApplicationModal(position_label)
        )


class ClosedPositionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="ยังไม่เปิดรับสมัคร",
            emoji="🔒",
            style=discord.ButtonStyle.secondary,
            custom_id="recruitment:card:dj",
            disabled=True,
        ))


class RecruitmentRulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="อ่านข้อตกลงการสมัคร",
        emoji="📜",
        style=discord.ButtonStyle.secondary,
        custom_id="recruitment:read_rules",
    )
    async def read_rules(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        embed = discord.Embed(
            title="📜 ข้อตกลงการสมัครทีมงาน",
            description=(
                "1. กรอกข้อมูลตามความเป็นจริง\\n"
                "2. เคารพกฎและสมาชิกทุกคน\\n"
                "3. ใช้สิทธิ์ทีมงานอย่างเหมาะสม\\n"
                "4. รอทีมงานตรวจสอบใบสมัคร\\n"
                "5. หากได้รับเลือก ต้องรับผิดชอบหน้าที่\\n\\n"
                "การส่งใบสมัครไม่ได้รับประกันว่าจะได้รับเลือก"
            ),
            color=0xA66B4F,
        )
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )


class InterviewScheduleModal(discord.ui.Modal, title="กำหนดนัดสัมภาษณ์"):
    interview_time = discord.ui.TextInput(
        label="วันและเวลาสัมภาษณ์",
        placeholder="เช่น 12 ต.ค. 2026 เวลา 19:00 น.",
        max_length=100,
    )
    details = discord.ui.TextInput(
        label="รายละเอียดเพิ่มเติม",
        placeholder="แจ้งสิ่งที่ผู้สมัครต้องเตรียม",
        style=discord.TextStyle.paragraph,
        max_length=800,
        required=False,
    )

    def __init__(self, application_message):
        super().__init__()
        self.application_message = application_message

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "คำสั่งนี้ใช้ได้ภายในเซิร์ฟเวอร์เท่านั้น",
                ephemeral=True,
            )
            return

        is_owner = guild.owner_id == interaction.user.id
        has_role = any(
            role.id in STAFF_REVIEWER_ROLE_IDS
            for role in interaction.user.roles
        )
        if not (is_owner or has_role):
            await interaction.response.send_message(
                "คุณไม่มีสิทธิ์นัดสัมภาษณ์",
                ephemeral=True,
            )
            return

        if not self.application_message.embeds:
            await interaction.response.send_message(
                "ไม่พบข้อมูลใบสมัคร",
                ephemeral=True,
            )
            return

        embed = self.application_message.embeds[0]
        applicant_id = None
        applicant_name = "applicant"

        for field in embed.fields:
            if field.name == "ผู้สมัคร":
                import re
                match = re.search(r"ID:\s*`?(\d{15,22})", field.value)
                mention_match = re.search(r"<@!?(\d{15,22})>", field.value)
                if match:
                    applicant_id = int(match.group(1))
                elif mention_match:
                    applicant_id = int(mention_match.group(1))
            elif field.name == "ชื่อที่ใช้เรียก":
                applicant_name = field.value

        if applicant_id is None:
            await interaction.response.send_message(
                "อ่าน Discord ID ของผู้สมัครไม่สำเร็จ",
                ephemeral=True,
            )
            return

        applicant = guild.get_member(applicant_id)
        if applicant is None:
            try:
                applicant = await guild.fetch_member(applicant_id)
            except discord.HTTPException:
                await interaction.response.send_message(
                    "ไม่พบผู้สมัครในเซิร์ฟเวอร์",
                    ephemeral=True,
                )
                return

        bot_member = guild.me
        if bot_member is None:
            await interaction.response.send_message(
                "ไม่สามารถตรวจสอบสิทธิ์ของบอทได้",
                ephemeral=True,
            )
            return

        bot_permissions = guild.me.guild_permissions
        if not bot_permissions.manage_channels:
            await interaction.response.send_message(
                "บอทต้องมีสิทธิ์ Manage Channels ก่อนสร้างห้อง",
                ephemeral=True,
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            applicant: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                connect=True,
                speak=True,
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                connect=True,
                speak=True,
            ),
        }

        for role in guild.roles:
            if role.id in STAFF_REVIEWER_ROLE_IDS:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    connect=True,
                    speak=True,
                )

        clean_name = "".join(
            c.lower() if c.isalnum() else "-"
            for c in applicant_name
        ).strip("-")
        clean_name = (clean_name or str(applicant_id))[:35]
        base_name = f"interview-{clean_name}-{applicant_id % 10000}"

        text_channel = None
        voice_channel = None
        try:
            review_channel = guild.get_channel(REVIEW_CHANNEL_ID)
            category = (
                review_channel.category
                if isinstance(review_channel, discord.TextChannel)
                else None
            )

            text_channel = await guild.create_text_channel(
                name=base_name,
                category=category,
                overwrites=overwrites,
                topic=f"Bakery interview applicant={applicant_id}",
                reason=f"Interview for applicant {applicant_id}",
            )

            voice_channel = await guild.create_voice_channel(
                name=f"สัมภาษณ์・{clean_name}"[:100],
                category=category,
                overwrites=overwrites,
                reason=f"Interview for applicant {applicant_id}",
            )

            await text_channel.edit(
                topic=(
                    f"Bakery interview applicant={applicant_id};"
                    f"voice_channel_id={voice_channel.id}"
                )
            )

            await text_channel.send(
                f"## 🦊 ห้องสัมภาษณ์ Bakery House Community\n"
                f"ผู้สมัคร: {applicant.mention}\n"
                f"ผู้นัดสัมภาษณ์: {interaction.user.mention}\n"
                f"วันและเวลา: **{self.interview_time.value}**\n"
                f"ห้องเสียง: {voice_channel.mention}\n"
                f"รายละเอียด: {self.details.value or 'ไม่มีเพิ่มเติม'}\n\n"
                "ห้องนี้เป็นส่วนตัว โปรดใช้สำหรับการสัมภาษณ์เท่านั้น "
                "เมื่อทุกคนออกจากห้องเสียง ห้องสัมภาษณ์ทั้งสองห้องจะถูกลบ"
            )

        except (discord.HTTPException, discord.Forbidden) as exc:
            for channel in (voice_channel, text_channel):
                if channel is not None:
                    try:
                        await channel.delete(
                            reason="Cleanup after interview setup failure"
                        )
                    except discord.HTTPException:
                        pass
            await interaction.response.send_message(
                f"สร้างห้องสัมภาษณ์ไม่สำเร็จ ตรวจสอบสิทธิ์บอท "
                f"(รายละเอียด: {type(exc).__name__})",
                ephemeral=True,
            )
            return

        updated = self.application_message.embeds[0].copy()
        for i, field in enumerate(updated.fields):
            if field.name == "สถานะ":
                updated.set_field_at(
                    i,
                    name="สถานะ",
                    value=f"🔵 นัดสัมภาษณ์: {self.interview_time.value}",
                    inline=False,
                )
                break

        updated.add_field(
            name="ห้องสัมภาษณ์",
            value=f"ข้อความ: {text_channel.mention}\nเสียง: {voice_channel.mention}",
            inline=False,
        )
        updated.add_field(
            name="ผู้นัดสัมภาษณ์",
            value=interaction.user.mention,
            inline=False,
        )
        updated.color = discord.Color.blue()

        try:
            await self.application_message.edit(embed=updated)
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            f"สร้างห้องสัมภาษณ์แล้ว: {text_channel.mention} "
            f"และ {voice_channel.mention}",
            ephemeral=True,
        )


class ReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_status(
        self,
        interaction: discord.Interaction,
        status: str,
        color: discord.Color,
    ):
        is_owner = (
            interaction.guild is not None
            and interaction.guild.owner_id == interaction.user.id
        )

        has_role = (
            isinstance(interaction.user, discord.Member)
            and any(
                role.id in STAFF_REVIEWER_ROLE_IDS
                for role in interaction.user.roles
            )
        )

        if not (is_owner or has_role):
            await interaction.response.send_message(
                "คุณไม่มีสิทธิ์ตรวจใบสมัคร",
                ephemeral=True,
            )
            return

        if not interaction.message.embeds:
            await interaction.response.send_message(
                "ไม่พบข้อมูลใบสมัคร",
                ephemeral=True,
            )
            return

        embed = interaction.message.embeds[0].copy()

        for field in embed.fields:
            if field.name == "สถานะ":
                field.value = status
                break

        embed.color = color
        embed.add_field(
            name="ผู้พิจารณา",
            value=interaction.user.mention,
            inline=False,
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self,
        )

    @discord.ui.button(
        label="นัดสัมภาษณ์",
        emoji="🗓️",
        style=discord.ButtonStyle.primary,
        custom_id="recruitment:interview",
    )
    async def interview(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        is_owner = (
            interaction.guild is not None
            and interaction.guild.owner_id == interaction.user.id
        )
        has_role = (
            isinstance(interaction.user, discord.Member)
            and any(
                role.id in STAFF_REVIEWER_ROLE_IDS
                for role in interaction.user.roles
            )
        )
        if not (is_owner or has_role):
            await interaction.response.send_message(
                "คุณไม่มีสิทธิ์นัดสัมภาษณ์",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            InterviewScheduleModal(interaction.message)
        )

    @discord.ui.button(
        label="อนุมัติ",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="recruitment:approve",
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.update_status(
            interaction,
            "🟢 ผ่านการอนุมัติ — มอบยศด้วยตนเอง",
            discord.Color.green(),
        )

    @discord.ui.button(
        label="ไม่ผ่าน",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="recruitment:reject",
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.update_status(
            interaction,
            "🔴 ไม่ผ่านการคัดเลือก",
            discord.Color.red(),
        )


class StaffRecruitment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # ทำงานเมื่อสมาชิกออกจากห้องเสียงหรือย้ายไปห้องอื่น
        channel = before.channel
        if channel is None or channel == after.channel:
            return
        if not isinstance(channel, discord.VoiceChannel):
            return
        if not channel.name.startswith("สัมภาษณ์・"):
            return
        if channel.members:
            return

        # หา text channel ที่บันทึก voice_channel_id นี้ไว้ใน topic
        guild = channel.guild
        marker = f"voice_channel_id={channel.id}"
        linked_text = next(
            (
                ch for ch in guild.text_channels
                if ch.topic and marker in ch.topic
            ),
            None,
        )

        try:
            await channel.delete(
                reason="Interview voice channel is empty"
            )
        except discord.HTTPException:
            return

        if linked_text is not None:
            try:
                await linked_text.delete(
                    reason="Interview voice channel became empty"
                )
            except discord.HTTPException:
                pass

    @app_commands.command(
        name="ตั้งค่ารับสมัคร",
        description="ส่งการ์ดรับสมัครทีมงานแยกตามตำแหน่ง",
    )
    @app_commands.default_permissions(administrator=True)
    async def post_recruitment(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = self.bot.get_channel(APPLY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(APPLY_CHANNEL_ID)
            except discord.HTTPException:
                await interaction.followup.send(
                    "ไม่พบช่องรับสมัคร กรุณาตรวจสอบ Channel ID",
                    ephemeral=True,
                )
                return

        intro = discord.Embed(
            title="🥐 BAKERY HOUSE COMMUNITY",
            description=(
                "୨୧ ── THE STAFF BAKERY ── ୨୧\n"
                "มาร่วมเป็นส่วนหนึ่งในการดูแลบ้านหลังนี้\n\n"
                "เลือกตำแหน่งที่ตรงกับความถนัด อ่านรายละเอียด "
                "แล้วกดปุ่มสมัครได้เลย\n"
                "กรุณากรอกข้อมูลตามจริง และรอทีมงานตรวจสอบ"
            ),
            color=0x6B3E32,
        )
        intro.set_footer(
            text="BAKERY HOUSE • อบอุ่น เป็นมิตร เติบโตไปด้วยกัน"
        )
        intro.set_image(url=RECRUITMENT_IMAGE_URLS["banner"])

        try:
            await channel.send(embed=intro, view=RecruitmentRulesView())

            for key, data in POSITION_CARD_DATA.items():
                emoji, name, tagline, duties, color = data
                card = discord.Embed(
                    title=f"{emoji}  {name}",
                    description=(
                        f"*{tagline}*\n\n"
                        f"**หน้าที่โดยย่อ**\n{duties}\n\n"
                        "**คุณสมบัติที่เหมาะสม**\n"
                        "• มีความรับผิดชอบและสุภาพ\n"
                        "• ทำงานร่วมกับผู้อื่นได้\n"
                        "• พร้อมเรียนรู้และเคารพกฎชุมชน"
                    ),
                    color=color,
                )
                card.set_image(url=RECRUITMENT_IMAGE_URLS[key])
                card.set_footer(
                    text="Bakery House Recruitment • เลือกตำแหน่งที่ใช่"
                )
                await channel.send(
                    embed=card,
                    view=PositionCardView(key),
                )

            dj = discord.Embed(
                title="🐺 DJ",
                description=(
                    "*ดูแลบรรยากาศทางเสียงของชุมชน*\n\n"
                    "🔒 ตำแหน่งนี้ยังไม่เปิดรับสมัคร "
                    "โปรดติดตามประกาศจากทีมงาน"
                ),
                color=0x8B8178,
            )
            dj.set_image(url=RECRUITMENT_IMAGE_URLS["dj"])
            await channel.send(embed=dj, view=ClosedPositionView())

        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"ส่งการ์ดรับสมัครไม่ครบ กรุณาตรวจสอบสิทธิ์บอท "
                f"และดู log เพิ่มเติม ({type(exc).__name__})",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "ส่งหน้าและการ์ดรับสมัครเรียบร้อยแล้ว",
            ephemeral=True,
        )


async def setup_staff_recruitment(bot):
    await bot.add_cog(StaffRecruitment(bot))
    bot.add_view(ApplyView())
    bot.add_view(ReviewView())
    bot.add_view(RecruitmentRulesView())
    bot.add_view(ClosedPositionView())
    for key in POSITION_CARD_DATA:
        bot.add_view(PositionCardView(key))
