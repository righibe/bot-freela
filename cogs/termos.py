"""
Cog dos Termos de Uso.
Comandos de consulta e estatísticas de aceite.
"""

import logging

import discord
from discord.ext import commands
from discord import app_commands

from config.settings import TERMOS_VERSAO, COR_PRINCIPAL
from core.database import usuario_aceitou_termos, contar_aceites_termos
from embeds.termos_embed import criar_embed_termos_resumo
from views.termos_views import TermosAceiteView, _arquivo_termos

logger = logging.getLogger('bot_freeela.cogs.termos')


class TermosCog(commands.Cog):
    """Cog responsável pelos Termos de Uso da plataforma."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TermosAceiteView())
        logger.info('View persistente dos Termos de Uso registrada (versão %s)', TERMOS_VERSAO)

    @app_commands.command(
        name='termos',
        description='Exibe os Termos de Uso da plataforma Freeela',
    )
    async def termos(self, interaction: discord.Interaction):
        embed = criar_embed_termos_resumo()
        view = TermosAceiteView()
        arquivo = _arquivo_termos()

        ja_aceitou = usuario_aceitou_termos(interaction.user.id, TERMOS_VERSAO)
        if ja_aceitou:
            embed.add_field(
                name='📌  Seu status',
                value=f'✅ Você já aceitou a versão {TERMOS_VERSAO}.',
                inline=False,
            )

        kwargs = {'embed': embed, 'view': view, 'ephemeral': True}
        if arquivo:
            kwargs['file'] = arquivo
        await interaction.response.send_message(**kwargs)

    @app_commands.command(
        name='aceites_termos',
        description='[STAFF] Estatísticas de aceite dos Termos de Uso',
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(usuario='(Opcional) Verificar se um usuário específico aceitou')
    async def aceites_termos(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member | None = None,
    ):
        embed = discord.Embed(
            title='📜  Aceites dos Termos de Uso',
            color=COR_PRINCIPAL,
        )
        embed.add_field(
            name=f'✅  Aceites da versão vigente ({TERMOS_VERSAO})',
            value=f'**{contar_aceites_termos(TERMOS_VERSAO)}** usuários',
            inline=False,
        )
        if usuario:
            aceitou = usuario_aceitou_termos(usuario.id, TERMOS_VERSAO)
            embed.add_field(
                name=f'👤  {usuario.display_name}',
                value='✅ Aceitou a versão vigente' if aceitou else '❌ **Não** aceitou a versão vigente',
                inline=False,
            )
        embed.set_footer(text='Os registros individuais (data/hora UTC) ficam na tabela aceites_termos do banco.')
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TermosCog(bot))
    logger.info('Cog de termos carregado')
