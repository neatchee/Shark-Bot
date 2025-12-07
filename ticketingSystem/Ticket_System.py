import discord
import logging
from  ticketingSystem.MyView import MyView, CloseButton, TicketOptions

# ======= Logging =======
handler = logging.FileHandler(filename="tickets.log", encoding="utf-8", mode="a")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

class TicketSystem:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def setup(self):
        print("Ticket system loaded | Ticket_System.py")

        #Register the persistence views
        self.bot.add_view(MyView(bot=self.bot))
        self.bot.add_view(CloseButton(bot=self.bot))
        self.bot.add_view(TicketOptions(bot=self.bot))