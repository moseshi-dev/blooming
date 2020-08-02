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
import constants 
            #tokenファイル
with open("Mintoken.txt") as f:
    token = f.read()
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
    readme = client.get_channel(constants.README_CH_ID)
    ch_guide = client.get_channel(constants.CHANNEL_GUIDE_CH_ID)
    selfintro = client.get_channel(constants.SELFINTRO_CH_ID)
    greeting = client.get_channel(constants.GREETING_CH_ID)

    channel = client.get_channel(constants.JOIN_LOG_CH_ID) #メッセージを送信するチャンネルを定義してください
    msg = member.mention + ' プロデューサーさん、ようこそ「MINTCORD」へ！\n まずはこのサーバのルールがあるから' + readme.mention + 'を見てね。他にも、各チャンネルの紹介があるから' + ch_guide.mention + 'を見てくれると嬉しいな。\n そのあとは、' + selfintro.mention + 'とか' + greeting.mention + 'とかで声をかけてみてね！\n これから一緒に頑張ろうね、プロデューサーさん！ '
    await channel.send(msg)

@client.event
async def on_message(message):
    global tts_ch_id #グローバルで宣言している変数を関数内で使う場合、このように宣言する必要があります。
    if message.author.bot:  #メッセージ送信主がbotだった場合
        return  #処理を全部スキップ

    if client.user in message.mentions and '通話来て' in message.content:
        voicech = message.author.voice_channel
        #voicech = message.author.voice.channel とすると複数のボイスチャンネル対応可能
        voice_client = await voicech.connect()
        tts_ch_id = message.channel.id
        await say('通話に参加しました', voice_client)

    elif client.user in message.mentions and 'おつかれ' in message.content:
        await say('おつかれさまでした', message.guild.voice_client)
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

                            #監視するサーバーID
    if member.channel.id == constants.SERVER_ID and (before.channel == constants.VC_GENERAL_CH_ID):
    #before.channel.idが通話チャンネル1のチャンネルIDと同じなら聞き専1に送信する などのように変更することで複数チャンネルに対応可能
                                           #通知させるテキストchのID
        alert_channel = client.get_channel(constants.VC_TEXT_GENERAL_CH_ID)
        if before.channel is None:
            msg = member.mention + ' さんが通話に参加しました。'
            await alert_channel.send(msg)
        elif after.channel is None:
            msg = member.mention + ' さんが通話から退出しました。'
            await alert_channel.send(msg)


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
        if arg1 in dic:
            msg = f"{arg1}の読みを{arg2}に変更したよ"
        else:
            msg = f"{arg1}は辞書に存在しないみたいだよ。辞書に追加しておくね。"
        dic[arg1] = arg2
        await ctx.send(msg)
        self.write_dic(dic)

    @commands.command()
    async def deldic(self, ctx, arg1):
        dic = self.load_dic()
        if arg1 not in dic:
            msg = f"{arg1}は辞書に存在しないよ"
            await ctx.send(msg)
            return

        del dic[arg1]
        self.write_dic(dic)
        msg = f"{arg1}を辞書から削除したよ"
        await ctx.send(msg)


client.run(token)