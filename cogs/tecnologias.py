"""
Cog de tecnologias — sugestões da comunidade e listagem.
"""

import logging

import discord
from discord.ext import commands
from discord import app_commands

from config.settings import COR_PRINCIPAL, MAX_TECNOLOGIAS_POR_DEV, MATCH_MIN_TECNOLOGIAS
from core.database import listar_tecnologias
from views.tecnologia_views import SugerirTecnologiaView, AnalisarSugestaoView

logger = logging.getLogger('bot_freeela.cogs.tecnologias')


class TecnologiasCog(commands.Cog):
    """Cog responsável pelo registro de tecnologias da plataforma."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(SugerirTecnologiaView())
        # Reativar botões de análise das sugestões pendentes entre reinícios
        pendentes = listar_tecnologias('sugerida')
        for tec in pendentes:
            self.bot.add_view(AnalisarSugestaoView(nome_tecnologia=tec.nome))
        logger.info(
            'Views de tecnologia registradas (%d sugestões pendentes)', len(pendentes)
        )

    @app_commands.command(
        name='tecnologias',
        description='Lista todas as tecnologias disponíveis na plataforma',
    )
    async def tecnologias(self, interaction: discord.Interaction):
        ativas = listar_tecnologias('ativa')
        nomes = ', '.join(f'`{t.nome}`' for t in ativas)
        embed = discord.Embed(
            title='🛠️  Tecnologias da Plataforma',
            description=(
                f'**{len(ativas)}** tecnologias disponíveis:\n\n{nomes}\n\n'
                f'📌 Cada dev pode ter até **{MAX_TECNOLOGIAS_POR_DEV}** no perfil, e o '
                f'match com um projeto exige **{MATCH_MIN_TECNOLOGIAS}+ em comum**.\n'
                f'💡 Sentiu falta de alguma? Sugira no canal **sugerir-tecnologia**!'
            ),
            color=COR_PRINCIPAL,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TecnologiasCog(bot))
    logger.info('Cog de tecnologias carregado')
