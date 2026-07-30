"""
Cog de verificação de empregadores.
Gerencia o fluxo de criação de projetos.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands
import config.settings as settings
from embeds.empregador_embed import criar_embed_verificacao_empregador
from views.empregador_views import IniciarEmpregadorView

logger = logging.getLogger('bot_freeela.cogs.empregador')


class EmpregadorCog(commands.Cog):
    """Cog responsável pelo sistema de empregadores."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(IniciarEmpregadorView())
        logger.info('View persistente de empregador registrada')

    @app_commands.command(
        name='setup_empregador',
        description='[STAFF] Envia a embed de empregador no canal #verificar-empregador',
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_empregador(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                '❌ Este comando só pode ser usado em um servidor.',
                ephemeral=True,
            )
            return

        canal = guild.get_channel(settings.CANAL_VERIFICAR_EMPREGADOR)
        if not canal:
            await interaction.response.send_message(
                f'❌ Canal verificar-empregador (ID: {settings.CANAL_VERIFICAR_EMPREGADOR}) não encontrado.\n'
                f'Atualize o ID em `config/settings.py`.',
                ephemeral=True,
            )
            return

        embed = criar_embed_verificacao_empregador()
        view = IniciarEmpregadorView()
        await canal.send(embed=embed, view=view)

        await interaction.response.send_message(
            f'✅ Embed de empregador enviada em {canal.mention}!',
            ephemeral=True,
        )
        logger.info(
            'Embed de empregador enviada por %s em #verificar-empregador',
            interaction.user.name,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EmpregadorCog(bot))
    logger.info('Cog de empregador carregado')
