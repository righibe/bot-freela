import os
import sys
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
if not TOKEN:
    print('DISCORD_TOKEN nao definido no .env')
    sys.exit(1)
if GUILD_ID:
    GUILD_ID = int(GUILD_ID)
logging.basicConfig(level=logging.INFO, format='%(asctime)s │ %(levelname)-8s │ %(name)-35s │ %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('bot.log', encoding='utf-8')])
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logger = logging.getLogger('bot_freeela')
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, description='Bot Freeela — Verificação de Desenvolvedores')
COGS = ['cogs.verificacao']

async def carregar_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info('✅ Cog carregado: %s', cog)
        except Exception as e:
            logger.error('❌ Erro ao carregar cog %s: %s', cog, e)

@bot.event
async def on_ready():
    logger.info('═' * 60)
    logger.info('  Bot online como: %s (ID: %s)', bot.user, bot.user.id)
    logger.info('  Servidores: %d', len(bot.guilds))
    logger.info('═' * 60)
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info('%d slash commands sincronizados no servidor %s', len(synced), GUILD_ID)
        else:
            synced = await bot.tree.sync()
            logger.info('%d slash commands sincronizados globalmente', len(synced))
    except Exception as e:
        logger.error('Erro ao sincronizar commands: %s', e)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error('Erro no comando %s: %s', ctx.command, error)

async def main():
    async with bot:
        await carregar_cogs()
        await bot.start(TOKEN)
if __name__ == '__main__':
    asyncio.run(main())