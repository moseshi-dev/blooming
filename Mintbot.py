#coding:utf-8

from discord import Client
import discord
import io
import os
from google.cloud import texttospeech
from discord import PCMAudio
import asyncio
import re
from discord.ext import commands
from typing import Dict
from csv import DictReader, DictWriter
import toml

CONFIG_PATH = "./config.toml"

with open(CONFIG_PATH) as f:
    config = toml.load(f)

token = config["system"]["token"]

client: Client = discord.Client()


#tts起動時処理
gcp = texttospeech.TextToSpeechClient()
voice = texttospeech.VoiceSelectionParams(
            language_code='ja-JP',
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=96000
            )
tts_ch_id = 0 #読み上げチャンネルID保管用


async def say(text, voice_client):
    global voice
    global audio_config
    global gcp
    #ここでメンション、URL、チャンネルリンク、絵文字名を変換する必要あり
    #変換例
    text = re.sub(r'http(s)?://[^\s]+', 'URL', text)
    text = text.replace('<:', '')
    text = re.sub(r':[0-9]*>', '', text)
    while re.search('<@\d+>', text):
        nameresult = re.search('<@(?P<name>\d+)>', text)
        text = text.replace(nameresult.group(), client.get_user(int(nameresult.group('name'))).name)
    while re.search('<@!\d+>', text):
        nameresult = re.search('<@!(?P<name>\d+)>', text)
        text = text.replace(nameresult.group(), client.get_user(int(nameresult.group('name'))).name)
    while re.search('<#\d+>', text):
        channelresult = re.search('<#(?P<channel>\d+)>', text)
        text = text.replace(channelresult.group(), client.get_channel(int(channelresult.group('channel'))).name)
    #メンション→ユーザーネーム、チャンネルリンク→チャンネル名、URL→"URL"、絵文字名→IDを排除

    synthesis_input = texttospeech.SynthesisInput(text=text)
    response = gcp.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    byte_reader = io.BytesIO(response.audio_content)
    source = PCMAudio(byte_reader)
    while voice_client.is_playing():
        await asyncio.sleep(1)
    voice_client.play(source)


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_member_join(member):
    greeting_ch_config = config["greeting"]
    ch_ids = greeting_ch_config["channel_ids"]
    ch_name_mention_mapping = {}
    # moseshi: 違う気もするけど並んでるものきついものがあった
    for ch_name, ch_id in ch_ids.items():
        ch_name_mention_mapping[f"{ch_name}_ch_mention"] = client.get_channel(ch_id).mention

    join_log = client.get_channel(ch_ids["join_log"])

    msg = greeting_ch_config["response_formats"]["join"].format(
        member_mention=member.mention,
        **ch_name_mention_mapping,
    )

    await join_log.send(msg)


@client.event
async def on_message(message):
    global tts_ch_id #グローバルで宣言している変数を関数内で使う場合、このように宣言する必要があります。
    if message.author.bot:  #メッセージ送信主がbotだった場合
        return  #処理を全部スキップ

    command_phrases = config["say"]["command_phrases"]
    res_fmts = config["say"]["response_formats"]
    if client.user in message.mentions and any(phrase in message.content for phrase in command_phrases["connect"]):
        voicech = message.author.voice_channel
        #voicech = message.author.voice.channel とすると複数のボイスチャンネル対応可能
        voice_client = await voicech.connect()
        tts_ch_id = message.channel.id
        await say(res_fmts["bot_connect"], voice_client)

    elif client.user in message.mentions and any(phrase in message.content for phrase in command_phrases["disconnect"]):
        await say(res_fmts["bot_disconnect"], message.guild.voice_client)
        import time
        time.sleep(2)
        await message.guild.voice_client.disconnect()

    elif message.channel.id == tts_ch_id and message.guild.voice_client:
    #elif message.channel.id == tts_ch_id and message.guild.voice_client: とするとよいでしょう
        await say(message.content, message.guild.voice_client)


@client.event
async def on_voice_state_update(member, before, after):
    if member.bot:  #ボイチャの状態が更新されたメンバーがbotだった場合
        return  #処理を全部スキップする

    say_ch_ids = config["say"]["channel_ids"]
    target_voice_channel = client.get_channel(say_ch_ids["voice"])
    # 通知するテキストチャンネル
    notification_text_ch = client.get_channel(say_ch_ids["text"])
    res_fmts = config["say"]["response_formats"]


    # 対象とするボイスチャンネルへの出入りがあった場合は通知
    if before.channel is None and after.channel == target_voice_channel:
        msg = res_fmts["member_connect"].format(member_mention=member.mention)
        await notification_text_ch.send(msg)

    if after.channel is None and before.channel == target_voice_channel:
        msg = res_fmts["member_disconnect"].format(member_mention=member.mention)
        await notification_text_ch.send(msg)

#Dictionary_control
class Dictionary_control(commands.Cog):
    DICTIONARY_PATH = "./dictionary.csv"

    def __init__(self, bot):
        self.bot = bot

    @classmethod
    def load_dic(cls) -> Dict[str, str]:
        with open(cls.DICTIONARY_PATH, encoding='utf-8') as f:
            return {l["word"]: l["pronunciation"] for l in DictReader(f)}

    @classmethod
    def write_dic(cls, word_pronounciation_dic: Dict[str, str]) -> None:
        with open(cls.DICTIONARY_PATH, 'w', encoding='utf-8') as f:
            w = DictWriter(f)
            w.writeheader()
            w.writerows([
                {"word": d, "pronunciation": p}
                for d, p in word_pronounciation_dic.items()
            ])

    @commands.command()
    async def editdic(self, ctx, arg1, arg2):
        dic = self.load_dic()
        # 辞書への追加/上書き処理は同様に dic[arg1] = arg2 でできるのでまとめる
        res_fmts = config["say"]["response_formats"]
        if arg1 in dic:
            msg = res_fmts["dic_edit"].format(word=arg1, pronunciation=arg2)
        else:
            msg = res_fmts["dic_add"].format(word=arg1)
        dic[arg1] = arg2
        await ctx.send(msg)

        self.write_dic(dic)

    @commands.command()
    async def deldic(self, ctx, arg1):
        dic = self.load_dic()
        res_fmts = config["say"]["response_formats"]
        if arg1 not in dic:
            msg = res_fmts["dic_del_err"].format(word=arg1)
            await ctx.send(msg)
            return

        del dic[arg1]
        self.write_dic(dic)
        msg = res_fmts["dic_del"].format(word=arg1)
        await ctx.send(msg)


client.run(token)