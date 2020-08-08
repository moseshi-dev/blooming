#coding:utf-8

from discord.ext.commands import Bot
import discord
import re
from discord.ext import commands
from typing import Dict
import toml
from speak_cog import SpeakCog

CONFIG_PATH = "./config.toml"

with open(CONFIG_PATH) as f:
    config = toml.load(f)

token = config["system"]["token"]

bot: Bot = Bot(command_prefix=config["system"]["command_prefix"])


@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))


class WelcomeGreetingCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = self.config
        ch_ids = config["channel_ids"]
        ch_name_mention_mapping = {}
        for ch_name, ch_id in ch_ids.items():
            ch_name_mention_mapping[f"{ch_name}_ch_mention"] = self.bot.get_channel(ch_id).mention

        join_log = self.bot.get_channel(ch_ids["join_log"])

        msg = config["response_formats"]["join"].format(
            member_mention=member.mention,
            **ch_name_mention_mapping,
        )

        await join_log.send(msg)

bot.add_cog(WelcomeGreetingCog(bot, config["greeting"]))
bot.add_cog(SpeakCog(bot, config["say"]))

bot.run(token)