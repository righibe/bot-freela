"""
Cog de matching — gerencia candidaturas e negociações.
Registra views persistentes de negociação.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands
from config.settings import COR_MATCHING
from core.database import (
    buscar_candidatura, buscar_candidatura_por_thread,
    listar_projetos, buscar_dev, buscar_projeto,
)
from core.matching_engine import verificar_compatibilidade_dev_projeto
from views.projeto_views import NegociacaoView

logger = logging.getLogger('bot_freeela.cogs.matching')


class MatchingCog(commands.Cog):
    """Cog responsável pelo sistema de matching dev ↔ projeto."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Registrar views persistentes de negociações ativas
        from core.database import listar_candidaturas_por_status
        negociando = listar_candidaturas_por_status('negociando')
        for cand in negociando:
            self.bot.add_view(NegociacaoView(candidatura_id=cand.id))
        logger.info(
            'Views persistentes registradas para %d negociações ativas',
            len(negociando),
        )

    @app_commands.command(
        name='meu_perfil',
        description='Mostra seu perfil de desenvolvedor verificado',
    )
    async def meu_perfil(self, interaction: discord.Interaction):
        dev = buscar_dev(interaction.user.id)
        if not dev:
            await interaction.response.send_message(
                '❌ Você não é um desenvolvedor verificado.\n'
                'Acesse o canal de verificação para se verificar.',
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title='👨‍💻  Seu Perfil de Desenvolvedor',
            color=COR_MATCHING,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(
            name='📊  Compatibilidade',
            value=f'**{dev.compatibilidade}%**',
            inline=True,
        )
        embed.add_field(
            name='🔒  Integridade',
            value=f'**{dev.integridade}%**',
            inline=True,
        )
        embed.add_field(
            name='📈  Senioridade',
            value=f'`{dev.senioridade}`',
            inline=True,
        )
        embed.add_field(
            name='🛠️  Linguagens',
            value=', '.join(f'`{l}`' for l in dev.linguagens_confirmadas) or 'N/A',
            inline=False,
        )
        embed.add_field(
            name='📂  Área',
            value=f'`{dev.area}`',
            inline=True,
        )
        embed.add_field(
            name='📋  Projetos Ativos',
            value=f'**{dev.projetos_ativos}**',
            inline=True,
        )
        embed.add_field(
            name='🔗  Links',
            value=(
                f'[GitHub]({dev.github_url})' +
                (f' | [LinkedIn]({dev.linkedin_url})' if dev.linkedin_url else '')
            ) if dev.github_url else 'N/A',
            inline=False,
        )

        if dev.pix_key:
            from views.pagamento_views import mascarar_chave
            embed.add_field(
                name='💳  Recebimento (PIX)',
                value=f'`{mascarar_chave(dev.pix_key)}` ({dev.pix_key_type})',
                inline=False,
            )
        else:
            embed.add_field(
                name='💳  Recebimento (PIX)',
                value='⚠️ Nenhuma chave cadastrada — use **/configurar_pagamento**',
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name='compatibilidade',
        description='Verifica sua compatibilidade com um projeto',
    )
    @app_commands.describe(projeto_id='ID do projeto para verificar compatibilidade')
    async def compatibilidade(self, interaction: discord.Interaction, projeto_id: str):
        dev = buscar_dev(interaction.user.id)
        if not dev:
            await interaction.response.send_message(
                '❌ Você não é um desenvolvedor verificado.',
                ephemeral=True,
            )
            return

        projeto = buscar_projeto(projeto_id)
        if not projeto:
            await interaction.response.send_message(
                '❌ Projeto não encontrado.',
                ephemeral=True,
            )
            return

        compat = verificar_compatibilidade_dev_projeto(dev, projeto)

        emoji = '✅' if compat['compativel'] else '❌'
        embed = discord.Embed(
            title=f'{emoji}  Compatibilidade com "{projeto.titulo}"',
            color=COR_MATCHING,
        )
        embed.add_field(
            name='📊  Score de Match',
            value=f'**{compat["score_match"]}%**',
            inline=True,
        )
        embed.add_field(
            name='✅  Linguagens Match',
            value=', '.join(f'`{l}`' for l in compat['linguagens_match']) or 'Nenhuma',
            inline=True,
        )
        embed.add_field(
            name='❌  Faltando',
            value=', '.join(f'`{l}`' for l in compat['linguagens_faltando']) or 'Nenhuma',
            inline=True,
        )
        embed.add_field(
            name='📈  Experiência OK',
            value='✅' if compat['experiencia_ok'] else '❌',
            inline=True,
        )
        embed.add_field(
            name='📋  Disponibilidade',
            value='✅' if compat['disponibilidade_ok'] else '❌',
            inline=True,
        )

        if compat['motivos_rejeicao']:
            embed.add_field(
                name='🚫  Motivos de Incompatibilidade',
                value='\n'.join(f'• {m}' for m in compat['motivos_rejeicao']),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MatchingCog(bot))
    logger.info('Cog de matching carregado')
