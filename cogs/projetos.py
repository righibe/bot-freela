"""
Cog de listagem e gerenciamento de projetos.
Exibe projetos organizados por categoria.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands
from dataclasses import asdict
from config.settings import (
    CATEGORIAS_PROJETO, COR_PROJETO, COR_PRINCIPAL,
)
from core.database import (
    listar_projetos, listar_projetos_por_categoria,
    buscar_projeto, atualizar_status_projeto,
)
from embeds.projeto_embed import criar_embed_projeto_listagem
from views.projeto_views import ProjetoInteresseView

logger = logging.getLogger('bot_freeela.cogs.projetos')


class ProjetosCog(commands.Cog):
    """Cog responsável pela listagem e gerenciamento de projetos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Registrar views persistentes de projetos abertos
        projetos_abertos = listar_projetos('aberto')
        for projeto in projetos_abertos:
            self.bot.add_view(ProjetoInteresseView(projeto_id=projeto.id))
        logger.info(
            'Views persistentes registradas para %d projetos abertos',
            len(projetos_abertos),
        )

    @app_commands.command(
        name='listar_projetos',
        description='Mostra os projetos disponíveis para candidatura',
    )
    async def listar_projetos_cmd(self, interaction: discord.Interaction):
        projetos = listar_projetos('aberto')

        if not projetos:
            await interaction.response.send_message(
                '📭 Nenhum projeto aberto no momento.',
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title='📂  Projetos Disponíveis',
            description=f'Há **{len(projetos)}** projeto(s) aberto(s):',
            color=COR_PROJETO,
        )

        from utils.helpers import formatar_brl
        for p in projetos[:10]:  # Limite de 10
            langs = ', '.join(p.linguagens_requeridas[:5])
            embed.add_field(
                name=f'{p.titulo}',
                value=(
                    f'💰 {formatar_brl(p.valor)} | 📂 {p.categoria}\n'
                    f'🛠️ {langs}\n'
                    f'📋 ID: `{p.id}`'
                ),
                inline=False,
            )

        if len(projetos) > 10:
            embed.set_footer(text=f'Mostrando 10 de {len(projetos)} projetos.')

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProjetosCog(bot))
    logger.info('Cog de projetos carregado')
