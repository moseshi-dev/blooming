import io
import re

from discord.ext import commands
from discord.ext.commands import Bot
from typing import Dict, Any
from csv import DictReader, DictWriter
from google.cloud import texttospeech
from discord import PCMAudio
import asyncio

class SpeakCog(commands.Cog):
    SAMPLING_RATE = 96000
    LANG_CODE = 'ja-JP'
    DICTIONARY_PATH = './dictionary.csv'
    DICTIONARY_ENCODING = 'utf-8'

    def __init__(self, bot: Bot, config: Dict[str, Any]):
        self.config = config
        #tts起動時処理
        self.gcp = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code=self.LANG_CODE,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.SAMPLING_RATE,
        )
        self.dic = SpeakCog.load_dic()
        self.bot = bot
        self.tts_ch = None

    @classmethod
    def load_dic(cls) -> Dict[str, str]:
        with open(cls.DICTIONARY_PATH, encoding=cls.DICTIONARY_ENCODING) as f:
            return {l["word"]: l["pronunciation"] for l in DictReader(f)}

    @classmethod
    def write_dic(cls, word_pronounciation_dic: Dict[str, str]) -> None:
        with open(cls.DICTIONARY_PATH, 'w', encoding=cls.DICTIONARY_ENCODING) as f:
            w = DictWriter(f, fieldnames=["word", "pronunciation"])
            w.writeheader()
            a = [
                {"word": d, "pronunciation": p}
                for d, p in word_pronounciation_dic.items()
            ]
            w.writerows(a)

    @commands.Cog.listener()
    async def on_message(self, message) -> None:
        # メッセージ送信主がbotだった場合、処理を全部スキップ
        if message.author.bot:
            return

        # コマンドの場合は処理を全部スキップ
        if message.content.startswith(self.bot.command_prefix):
            return

        config = self.config
        command_phrases = config["command_phrases"]
        res_fmts = config["response_formats"]
        # bot 宛に mention 飛ばしてたらコマンド起動の確認をする
        if self.bot.user in message.mentions:
            if any(phrase in message.content for phrase in command_phrases["connect"]):
                # ユーザがVCに接続してなかったらエラー
                if message.author.voice is None:
                    msg = res_fmts["member_not_in_voice_channel_err"].format(
                        member_mention=message.author.mention,
                    )
                    await message.channel.send(msg)
                    return
                voice_client = message.guild.voice_client
                if voice_client is not None:
                    msg = res_fmts["already_in_voice_channel_err"].format(
                        member_mention=message.author.mention,
                        voice_ch_name=voice_client.channel.name,
                    )
                    await message.channel.send(msg)
                    return

                voicech = message.author.voice.channel
                self.voice_client = await voicech.connect()
                self.tts_ch = message.channel
                vb = self.get_voice_bytes(res_fmts["bot_connect"])
                await self.speak_voice_bytes(vb)
                return

            if any(phrase in message.content for phrase in command_phrases["disconnect"]):
                # botがVCに接続してなかったらエラー
                if message.guild.voice_client is None:
                    await message.channel.send(res_fmts["bot_not_in_voice_channel_err"])
                    return

                vb = self.get_voice_bytes(res_fmts["bot_disconnect"])
                await self.speak_voice_bytes(vb)
                await asyncio.sleep(2)
                await message.guild.voice_client.disconnect()
                return

        if message.channel == self.tts_ch and message.guild.voice_client:
            #elif message.channel.id == tts_ch_id and message.guild.voice_client: とするとよいでしょう
            processed_text = self.preprocess_text(message.content)
            vb = self.get_voice_bytes(processed_text)
            await self.speak_voice_bytes(vb)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after) -> None:
        config = self.config
        if member.bot:  #ボイチャの状態が更新されたメンバーがbotだった場合
            return  #処理を全部スキップする

        ch_ids = config["channel_ids"]
        target_voice_channel = self.bot.get_channel(ch_ids["voice"])
        # 通知するテキストチャンネル
        notification_text_ch = self.bot.get_channel(ch_ids["text"])
        res_fmts = config["response_formats"]

        # 対象とするボイスチャンネルへの出入りがあった場合は通知
        if before.channel is None and after.channel == target_voice_channel:
            msg = res_fmts["member_connect"].format(member_mention=member.mention)
            await notification_text_ch.send(msg)

        if after.channel is None and before.channel == target_voice_channel:
            msg = res_fmts["member_disconnect"].format(member_mention=member.mention)
            await notification_text_ch.send(msg)

    def preprocess_text(self, text: str) -> str:
        # 個人的には message で受け取った方が処理はしやすい気がする
        #ここでメンション、URL、チャンネルリンク、絵文字名を変換する必要あり
        #変換例
        text = re.sub(r'http(s)?://[^\s]+', 'URL', text)
        text = text.replace('<:', '')
        text = re.sub(r':[0-9]*>', '', text)
        while re.search('<@\d+>', text):
            nameresult = re.search('<@(?P<name>\d+)>', text)
            text = text.replace(nameresult.group(), self.bot.get_user(int(nameresult.group('name'))).name)
        while re.search('<@!\d+>', text):
            nameresult = re.search('<@!(?P<name>\d+)>', text)
            text = text.replace(nameresult.group(), self.bot.get_user(int(nameresult.group('name'))).name)
        while re.search('<#\d+>', text):
            channelresult = re.search('<#(?P<channel>\d+)>', text)
            text = text.replace(channelresult.group(), self.bot.get_channel(int(channelresult.group('channel'))).name)
        for w, p in self.dic.items():
            text = text.replace(w, p)
        return text

    def get_voice_bytes(self, text: str) -> io.BytesIO:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = self.gcp.synthesize_speech(
            input=synthesis_input,
            voice=self.voice,
            audio_config=self.audio_config,
        )
        return io.BytesIO(response.audio_content)

    async def speak_voice_bytes(self, voice_bytes: io.BytesIO) -> None:
        source = PCMAudio(voice_bytes)
        while self.voice_client.is_playing():
            await asyncio.sleep(1)
        if self.voice_client.is_connected():
            self.voice_client.play(source)

    @commands.command()
    async def editdic(self, ctx, arg1, arg2):
        dic = self.dic
        # 辞書への追加/上書き処理は同様に dic[arg1] = arg2 でできるのでまとめる
        res_fmts = self.config["response_formats"]
        if arg1 in dic:
            msg = res_fmts["dic_edit"].format(word=arg1, pronunciation=arg2)
        else:
            msg = res_fmts["dic_add"].format(word=arg1)
        dic[arg1] = arg2
        print(dic)
        self.write_dic(dic)
        await ctx.send(msg)

    @commands.command()
    async def deldic(self, ctx, arg1):
        dic = self.dic
        res_fmts = self.config["response_formats"]
        if arg1 not in dic:
            msg = res_fmts["dic_del_err"].format(word=arg1)
            await ctx.send(msg)
            return

        del dic[arg1]
        self.write_dic(dic)
        msg = res_fmts["dic_del"].format(word=arg1)
        await ctx.send(msg)
