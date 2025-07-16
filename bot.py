import discord
from discord.ext import commands
import asyncio
from googletrans import Translator
from PIL import Image
import pytesseract
import aiohttp
import io
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
translator = Translator()

emoji_language_map = {
    "🇷🇺": "ru", "🇬🇧": "en", "🇺🇸": "en", "🇩🇪": "de", "🇹🇷": "tr",
    "🇪🇸": "es", "🇨🇳": "zh-cn", "🇻🇳": "vi", "🇫🇷": "fr", "🇮🇹": "it", "🇰🇷": "ko"
}
supported_languages = set(emoji_language_map.values())

lang_aliases = {
    "ru": ["ru", "🇷🇺"],
    "en": ["en", "🇬🇧", "🇺🇸"],
    "de": ["de", "🇩🇪"],
    "fr": ["fr", "🇫🇷"],
    "it": ["it", "🇮🇹"],
    "es": ["es", "🇪🇸"],
    "tr": ["tr", "🇹🇷"],
    "vi": ["vi", "🇻🇳"],
    "zh-cn": ["cn", "zh", "🇨🇳"],
    "ko": ["kr", "ko", "🇰🇷"]
}

translated_flags = {}            # (msg.id, user.id, lang): message
auto_translated_ids = set()      # message.id

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()
    words = content.split()
    last_word = words[-1].lower() if words else ""
    matched_lang = None

    for lang, aliases in lang_aliases.items():
        if last_word.lower() in aliases:
            matched_lang = lang
            break

    # 📌 Ручной перевод (перманентный)
    if matched_lang:
        text_to_translate = " ".join(words[:-1])
        if text_to_translate:
            translated = translator.translate(text_to_translate, dest=matched_lang)
            await message.delete()
            await message.channel.send(
                f"📜 A whisper echoes from the Warp...\n\n🕯️ By will of **{message.author.display_name}**, translated to **{matched_lang.upper()}**:\n> {translated.text}"
            )
        return

    # 🔁 Автоперевод по роли
    if message.id in auto_translated_ids:
        return

    user_lang = None
    for role in message.author.roles:
        role_name = role.name.lower()
        if role_name in supported_languages:
            user_lang = role_name
            break

    if user_lang:
        detected_lang = translator.detect(message.content).lang
        if detected_lang != user_lang:
            translated = translator.translate(message.content, dest=user_lang)
            sent = await message.channel.send(
                f"👁 The Warp sees all...\n\nAuto-translation for **{message.author.display_name}** ({user_lang.upper()}):\n> {translated.text}"
            )
            auto_translated_ids.add(message.id)
            await asyncio.sleep(300)
            await sent.delete()
            auto_translated_ids.discard(message.id)

    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    emoji = str(payload.emoji)
    if emoji not in emoji_language_map:
        return

    lang = emoji_language_map[emoji]
    key = (payload.message_id, payload.user_id, lang)
    if key in translated_flags:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    user = guild.get_member(payload.user_id)
    display_name = user.display_name if user else f"User {payload.user_id}"

    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        return

    try:
        message = await channel.fetch_message(payload.message_id)
    except discord.NotFound:
        return

    content = message.content.strip()
    text_to_translate = content

    # 🖼️ Извлекаем текст с картинки, если есть вложение
    if not content and message.attachments:
        attachment = message.attachments[0]
        if attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                            image = Image.open(io.BytesIO(image_data))
                            ocr_text = pytesseract.image_to_string(image)
                            text_to_translate = ocr_text.strip()
            except Exception as e:
                print(f"OCR error: {e}")
                return

    if not text_to_translate:
        return

    translated = translator.translate(text_to_translate, dest=lang)
    sent = await channel.send(
        f"🔮 **{display_name}** calls upon forbidden tongues... ({lang.upper()}):\n> {translated.text}"
    )
    translated_flags[key] = sent

    await asyncio.sleep(300)
    await sent.delete()
    translated_flags.pop(key, None)

bot.run(os.environ["DISCORD_TOKEN"])
