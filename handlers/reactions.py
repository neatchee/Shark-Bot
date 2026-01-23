import logging
import discord
import utils.read_Yaml as RY
from pathlib import Path
from utils.core import AppConfig, get_channel_id, is_guild_in_config, is_rr_message_id_in_config

class reaction_handler:
    ROLES_PER_GUILD: dict
    CONFIG_PATH: Path
    BOT: discord.Client

    def __init__(self, config_path: Path, roles_per_guild: dict, bot: discord.Client):
        self.CONFIG_PATH = config_path
        self.ROLES_PER_GUILD = roles_per_guild
        self.BOT = bot

    # ======= Ensures React Roles message exists =======
    async def ensure_react_roles_message_internal(self, config: AppConfig, guild: discord.Guild):
        # check for guild config, if none found then skip
        if not is_guild_in_config(guild_id=guild.id, config=config):
            raise ValueError(f"Guild {guild.name} is not in the config. Skipping")

        id_to_name: dict[int,str] = {int(v): k for k, v in config.guilds.items()}
        guild_name: str = id_to_name.get(guild.id) or ""
        # print(guild_name)
        
        react_role_messages: dict = config.guild_role_messages.setdefault(guild_name, {})
        # print(react_role_messages)

        if not is_rr_message_id_in_config(guild_name=guild_name, config=config):
            raise KeyError(f"Guild {guild.name} does not have a react roles message ID Key")
        
        for rr_message in react_role_messages:
            # print(react_role_messages[rr_message])

            channel_id = int(get_channel_id(config, guild_name, "roles"))
            channel = guild.get_channel(channel_id) if channel_id else None

            guild_roles = self.ROLES_PER_GUILD.get(guild.id)
            role_mapping = guild_roles.get(rr_message) if guild_roles else None
            # print("current mapping: ",role_mapping)
            # print(f"emoji: ",role_mapping)

            message = None
            try:
                message_id = int(react_role_messages[rr_message])
                if isinstance(channel, discord.TextChannel):
                    message = await channel.fetch_message(message_id) 
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                logging.error(f"[RR] could not fetch existing react-roles message {rr_message} in {guild_name}. Inner exception:\n{e}")
                continue
            
            if react_role_messages[rr_message] != 0:
                logging.info(f"There is already a react roles message of {rr_message} for {guild_name}")
                if channel is None:
                    logging.error(f"[RR] No valid channel configured for {guild_name}")
                    continue # Keep original flow
                    
                if not role_mapping:
                    continue # nothing to add
                
                existing = {str(r.emoji) for r in message.reactions} if message else {}
                for emoji in role_mapping.keys():
                    if existing and message and emoji not in existing:
                        try:
                            await message.add_reaction(emoji)
                        except discord.HTTPException:
                            logging.error(f"[RR] could not add reaction {emoji} in {guild_name}")

                current_content = ""
                current_lines = current_content.splitlines()
                header = current_lines[0] if current_lines else "React to get your roles: "
                existing_entries = set(current_lines[1 :]) if len(current_lines) > 1 else set()

                desired_entries = [f"{emoji} -> <@&{role_id}>" for emoji, role_id in role_mapping.items()]
                to_append = [line for line in desired_entries if line not in existing_entries]

                if to_append and message: #make sure it isn't empty
                    new_content = (header + "\n" + "\n".join(sorted(existing_entries)) + ("\n" if existing_entries else "") + "\n".join(to_append)).strip()
                    try:
                        await message.edit(content=new_content)
                    except discord.HTTPException:
                        logging.error(f"[RR could not edit react-roles message {rr_message} in {guild_name}]")
                # ---------------------------------------------------------------------------------------------
                continue

            if channel is None:
                raise LookupError(f"[RR] No valid channel configured for {guild_name}")

            if isinstance(channel, discord.TextChannel):
                message = await channel.send(
                    "React to get your roles: \n" +
                    "\n".join((f"{emoji} -> <@&{role_id}>" for emoji, role_id in role_mapping.items()) if role_mapping else "")
                )

                if message:
                    # Add the reactions we'll listen for
                    if role_mapping:
                        for emoji in role_mapping.keys():
                            try:
                                await message.add_reaction(emoji)
                            except discord.HTTPException:
                                logging.error(f"[RR] could not add reaction {emoji} in {guild_name}")
                    
                    config.guild_role_messages[guild_name][rr_message] = message.id
                    RY.save_config(CONFIG=self.CONFIG_PATH, cfg=config.model_dump())
                else:
                    logging.error(f"[RR] could not add reactions in {guild_name}. Channel returned message as None")
                    return
            else:
                logging.critical("[RR] Bad channel type, not a TextChannel")
                return
        
    # ======= REACTION ROLES ADD ROLE =======
    async def on_raw_reaction_add_internal(self, config: AppConfig, payload: discord.RawReactionActionEvent):

        guilds = config.guilds
        
        if guilds is None: 
            logging.info("[RR] Reaction was not from a guild")
            return
        
        id_to_name = {int(v): k for k, v in guilds.items()}
        
        gid = payload.guild_id

        if gid is None:
            logging.error("Guild ID could not be found")
            return
        
        guild_name = id_to_name[int(gid)]

        rr_message_ids: dict = config.guild_role_messages.get(guild_name) or {}
        message_id = None
        for id in rr_message_ids.values():
            if payload.message_id == id:
                message_id = id
                logging.info(f"found message! Reaction to message id: {id}")
        if not message_id:
            logging.info("Message isn't in my list")
            return
        
        react_role_messages: dict = config.guild_role_messages.setdefault(guild_name, {})
        id_to_name_rr = {int(v): k for k, v in react_role_messages.items()}
        rr_message = id_to_name_rr.get(message_id)
        mapping = self.ROLES_PER_GUILD[gid][rr_message]
        key = payload.emoji
        try: 
            role_id = mapping.get(str(key))
            if role_id is None:
                role_id = mapping.get(key)
            print(f"found role ID: {role_id}")
        except KeyError:
            logging.info("not the emoji i care about")
            return
        
        guild = self.BOT.get_guild(gid)
        if guild is None:
            logging.warning(f"Couldn't find guild with ID of {gid}")    
            return
        
        role = guild.get_role(role_id)
        if role is None:
            logging.warning(f"Couldn't find role with ID of {role_id} and emoji of {key}")
            return
        
        if payload.member:
            try:
                await payload.member.add_roles(role)
                logging.info(f"Added role {role} to {payload.member.name}")
            except discord.HTTPException:
                logging.error("HTTPException, I couldn't do it")
                return
        else:
            logging.error("Cannot attach a role to a non-existent member (payload.member is None)")
            return
        
    # ======= REACTION ROLES ADD ROLE =======
    async def on_raw_reaction_remove_internal(self, config: AppConfig, payload: discord.RawReactionActionEvent):

        guilds = config.guilds
        gid = payload.guild_id

        if gid is None: 
            logging.info("[RR] Reaction was not from a guild")
            return
        
        id_to_name = {int(v): k for k, v in guilds.items()}
        if gid is None:
            logging.error("Guild ID could not be found")
            return
        
        guild_name = id_to_name[int(gid)]

        rr_message_ids: dict = config.guild_role_messages.get(guild_name) or {}
        message_id = None
        for id in rr_message_ids.values():
            if payload.message_id == id:
                message_id = id
                logging.info(f"found message! Reaction to message id: {id}")
        if not message_id:
            logging.info("Message isn't in my list")
            return
        
        react_role_messages: dict = config.guild_role_messages.setdefault(guild_name, {})
        id_to_name_rr = {int(v): k for k, v in react_role_messages.items()}
        rr_message = id_to_name_rr.get(message_id)
        mapping = self.ROLES_PER_GUILD[gid][rr_message]
        key = payload.emoji
        try: 
            role_id = mapping.get(str(key))
            if role_id is None:
                role_id = mapping.get(key)
            print(f"found role ID: {role_id}")
        except KeyError:
            logging.info("not the emoji i care about")
            return
        
        guild = self.BOT.get_guild(gid)
        if guild is None:
            logging.warning(f"Couldn't find guild with ID of {gid}")
            return
        
        role = guild.get_role(role_id) if guild else None
        if role is None:
            logging.warning(f"Couldn't find role with ID of {role_id} and emoji of {key}")
            return
        
        member = guild.get_member(payload.user_id)

        if member:
            try:
                await member.remove_roles(role)
                logging.info(f"Removed role {role} from {member.name}")
            except discord.HTTPException:
                logging.error("HTTPException, I couldn't do it")
                return
        else:
            logging.error(f"Failed to remove reaction. get_member failed for guild ID {gid} and user ID {payload.user_id}")