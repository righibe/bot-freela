"""
Ponto de entrada principal do sistema Freeela.
Inicializa o Bot Discord e a API FastAPI em paralelo.
"""

import os
import sys
import logging
import asyncio
import threading
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

# ══════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8'),
    ],
)
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)

logger = logging.getLogger('bot_freeela')

# ══════════════════════════════════════════════════════
#  BOT
# ══════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    description='Bot Freeela — Plataforma de Freelancing no Discord',
)

# Todos os cogs do sistema
COGS = [
    'cogs.verificacao',    # Verificação de devs
    'cogs.empregador',     # Verificação de empregadores
    'cogs.projetos',       # Listagem de projetos
    'cogs.matching',       # Matching dev ↔ projeto
    'cogs.execucao',       # Execução de projetos
]


async def carregar_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info('[OK] Cog carregado: %s', cog)
        except Exception as e:
            logger.error('[ERRO] Erro ao carregar cog %s: %s', cog, e)

@bot.event
async def on_ready():
    logger.info('=' * 60)
    logger.info('  Bot online como: %s (ID: %s)', bot.user, bot.user.id)
    logger.info('  Servidores: %d', len(bot.guilds))
    logger.info('  Cogs carregados: %s', ', '.join(COGS))
    logger.info('=' * 60)
    
    # Registrar views persistentes globais
    from views.staff_views import StaffReviewView
    bot.add_view(StaffReviewView())
    
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

    # Executar setup da estrutura
    from core.setup_manager import setup_servidor
    if bot.guilds:
        await setup_servidor(bot)

    # Limpar cooldowns expirados
    from core.database import limpar_cooldowns_expirados
    limpar_cooldowns_expirados()
    logger.info('Cooldowns expirados limpos')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error('Erro no comando %s: %s', ctx.command, error)

# ══════════════════════════════════════════════════════
#  API FASTAPI (em thread separada)
# ══════════════════════════════════════════════════════
def iniciar_api():
    """Inicia a API FastAPI em uma thread separada."""
    try:
        import uvicorn
        from config.settings import API_HOST, API_PORT
        logger.info('[API] Iniciando API FastAPI em %s:%d...', API_HOST, API_PORT)
        uvicorn.run(
            'api.main:app',
            host=API_HOST,
            port=API_PORT,
            log_level='warning',
        )
    except ImportError:
        logger.warning(
            '[AVISO] uvicorn/fastapi não instalado. '
            'A API não será iniciada. '
            'Instale com: pip install fastapi uvicorn'
        )
    except Exception as e:
        logger.error('Erro ao iniciar API: %s', e)


# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
async def main():
    # Iniciar API em thread separada (daemon para fechar junto com o bot)
    api_thread = threading.Thread(target=iniciar_api, daemon=True)
    api_thread.start()

    # Garantir que o diretório de dados existe
    from pathlib import Path
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    async with bot:
        await carregar_cogs()
        await bot.start(TOKEN)


if __name__ == '__main__':
    asyncio.run(main())