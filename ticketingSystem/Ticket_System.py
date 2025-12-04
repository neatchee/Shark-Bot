import discord
import logging

# ======= Logging =======
handler = logging.FileHandler(filename="tickets.log", encoding="utf-8", mode="a")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)