import discord, sqlite3, io, asyncio
from ..utils import read_Yaml as RY
from zoneinfo import ZoneInfo
from datetime import datetime
import chat_exporter # pip install chat-exporter

conn = sqlite3.connect("databases/Ticket_System.db")
cur = conn.cursor()

# ===== CONFIG =====
config = RY.load_config("ticketingSystem/ticketing.yaml")
GUILD_IDS: dict = config["guild ids"]
TICKET_CHANNELS: dict = config["ticket channels"]
CATEGORY_IDS: dict = config["category ids"]
ROLE_IDS: dict = config["role ids"]
EMBED_TITLE: str = config["embed title"]
EMBED_DESCRIPTION: str = config["embed description"]
LOG_CHANNEL: int = config["log channel"]
timezone = ZoneInfo("America/Chicago")


class TicketOptions(discord.ui.View):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        super().__init__()

    @discord.ui.button(label="Delete Ticket 🎫", style=discord.ButtonStyle.red, custom_id="delete")
    async def delete_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.guild.id in GUILD_IDS.values():
            guild_id = interaction.guild.id

        guild = self.bot.get_guild(guild_id)
        channel = self.bot.get_channel(LOG_CHANNEL)
        ticket_id = interaction.channel.id

        cur.execute("SELECT id, discord_id, ticket_created FROM ticket WHERE ticket_channel=?", (ticket_id,))
        ticket_data = cur.fetchone()
        id, ticket_creator_id, ticket_created = ticket_data
        ticket_creator = guild.get_member(ticket_creator_id)
        ticket_created_unix = self.convert_to_unix_timestamp(ticket_created)

        ticket_closed = datetime.now(timezone).strftime(r'%Y-%m-%d %H:%M:%S')
        ticket_closed_unix = self.convert_to_unix_timestamp(ticket_closed)
        
        # Creating Transcript
        military_time: bool = True
        transcript = await chat_exporter.export(interaction.channel, limit=200, tz_info=timezone, military_time=military_time, bot=self.bot)

        transcript_file = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"transcript-{interaction.channel.name}.html"
            )
        transcript_file2 = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"transcript-{interaction.channel.name}.html"
            )
        
        embed = discord.Embed(description=f"Ticket is deleting in 5 seconds.", color=0xff0000)
        transcript_info = discord.Embed(title=f"Ticket Deleted | {interaction.channel.name}", color=discord.colour.Color.blue())
        transcript_info.add_field(name="ID", value=id, inline=True)
        transcript_info.add_field(name="Opened by", value=ticket_creator.mention, inline=True)
        transcript_info.add_field(name="Closed by", value=interaction.user.mention, inline=True)
        transcript_info.add_field(name="Ticket Created", value=f"<t:{ticket_created_unix}:f>", inline=True)
        transcript_info.add_field(name="Ticket Closed", value=f"<t:{ticket_closed_unix}:f>", inline=True)

        await interaction.response.send_message(embed=embed)
        try:
            await ticket_creator.send(embed=transcript_info, file=transcript_file)
        except:
            transcript_info.add_field(name="Error", value="Ticket Creator DM's are disabled", inline=True)
        
        await channel.send(embed=transcript_info, file=transcript_file)
        await asyncio.sleep(3)
        await interaction.channel.delete(reason="Ticket Deleted")
        cur.execute("DELETE FROM ticket WHERE discord_id=?", (ticket_creator_id, ))
        conn.commit()
    
    def convert_to_unix_timestamp(self, date_string):
        date_format= r"%Y-%m-%d %H:%M:%S"
        dt_obj: datetime = datetime.strftime(date_string, date_format)
        return int(dt_obj.timestamp())

        