"""
Cog do sistema de tickets.

Fluxo: usuário escolhe o assunto no select do canal 🎫・abrir-ticket →
o bot cria um canal privado na categoria 🎟️・TICKETS (visível só para o
usuário + staff), marca a staff e o usuário relata o problema no chat.
"""

import asyncio
import logging

import discord
from discord.ext import commands
from discord import app_commands

import config.settings as settings
from config.settings import TIPOS_TICKET, COR_PRINCIPAL
from core.database import (
    Ticket, salvar_ticket, buscar_ticket_por_canal,
    buscar_ticket_aberto_usuario, fechar_ticket, contar_tickets,
)
from embeds.ticket_embed import criar_embed_ticket_aberto, criar_embed_ticket_fechado
from views.ticket_views import AbrirTicketView, FecharTicketView
from utils.helpers import slug_canal
from utils.locks import guarda_acao

logger = logging.getLogger('bot_freeela.cogs.tickets')


def _info_tipo(slug: str) -> tuple[str, str]:
    """Retorna (rótulo, emoji) de um tipo de ticket."""
    for rotulo, s, emoji, _desc in TIPOS_TICKET:
        if s == slug:
            return rotulo, emoji
    return slug.title(), '🎫'


class TicketsCog(commands.Cog):
    """Cog responsável pelo sistema de suporte por tickets."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(AbrirTicketView())
        self.bot.add_view(FecharTicketView())
        logger.info('Views persistentes de tickets registradas')

    # ══════════════════════════════════════════════════
    #  ABRIR
    # ══════════════════════════════════════════════════

    async def abrir_ticket(self, interaction: discord.Interaction, tipo_slug: str):
        user = interaction.user
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message('❌ Erro interno.', ephemeral=True)
            return

        # Trava de idempotência: impede que um duplo-clique abra dois tickets.
        with guarda_acao(('ticket', user.id)) as livre:
            if not livre:
                await interaction.response.send_message(
                    '⏳ Seu ticket já está sendo aberto. Aguarde um instante...',
                    ephemeral=True,
                )
                return

            # Limite: 1 ticket aberto por usuário
            existente = buscar_ticket_aberto_usuario(user.id)
            if existente:
                canal_existente = guild.get_channel(existente.canal_id)
                if canal_existente:
                    await interaction.response.send_message(
                        f'⚠️ Você já tem um ticket aberto: {canal_existente.mention}\n'
                        f'Feche-o antes de abrir outro.',
                        ephemeral=True,
                    )
                    return
                # Canal sumiu (deletado manualmente) — fecha o registro órfão
                fechar_ticket(existente.canal_id)

            categoria = guild.get_channel(settings.CATEGORIA_TICKETS_ID)
            if not categoria or not isinstance(categoria, discord.CategoryChannel):
                await interaction.response.send_message(
                    '❌ Categoria de tickets não encontrada. Contate a staff.',
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            rotulo, emoji = _info_tipo(tipo_slug)
            cargo_staff = guild.get_role(settings.CARGO_STAFF)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, attach_files=True, embed_links=True,
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, manage_channels=True, embed_links=True,
                ),
            }
            if cargo_staff:
                overwrites[cargo_staff] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, manage_messages=True, attach_files=True,
                )

            try:
                canal = await guild.create_text_channel(
                    name=f'{emoji}・{tipo_slug}-{slug_canal(user.name, 20)}',
                    category=categoria,
                    overwrites=overwrites,
                    topic=f'Ticket de {user.name} • {rotulo}',
                    reason=f'Ticket ({rotulo}) aberto por {user.name}',
                )
            except discord.Forbidden:
                await interaction.followup.send('❌ Sem permissão para criar o canal do ticket.', ephemeral=True)
                return

            ticket = Ticket(
                user_id=user.id,
                username=user.name,
                tipo=tipo_slug,
                canal_id=canal.id,
            )
            salvar_ticket(ticket)

            embed = criar_embed_ticket_aberto(
                user_mention=user.mention,
                staff_mention=cargo_staff.mention if cargo_staff else 'staff',
                tipo_rotulo=rotulo,
                tipo_emoji=emoji,
            )
            mencao = f'{user.mention} {cargo_staff.mention}' if cargo_staff else user.mention
            await canal.send(content=mencao, embed=embed, view=FecharTicketView())

            await interaction.followup.send(
                f'✅ Ticket aberto! Vá para {canal.mention} e relate seu problema. 🎫',
                ephemeral=True,
            )
            logger.info('Ticket %s (%s) aberto por %s | canal=%d', ticket.id, tipo_slug, user.name, canal.id)

    # ══════════════════════════════════════════════════
    #  FECHAR
    # ══════════════════════════════════════════════════

    async def fechar_ticket_canal(self, interaction: discord.Interaction):
        canal = interaction.channel
        ticket = buscar_ticket_por_canal(canal.id)
        if not ticket:
            await interaction.response.send_message('❌ Este canal não é um ticket.', ephemeral=True)
            return

        eh_staff = bool(
            interaction.guild
            and isinstance(interaction.user, discord.Member)
            and (
                interaction.user.guild_permissions.administrator
                or any(r.id == settings.CARGO_STAFF for r in interaction.user.roles)
            )
        )
        if interaction.user.id != ticket.user_id and not eh_staff:
            await interaction.response.send_message(
                '❌ Apenas quem abriu o ticket ou a staff podem fechá-lo.',
                ephemeral=True,
            )
            return

        fechar_ticket(canal.id)
        await interaction.response.send_message(
            embed=criar_embed_ticket_fechado(interaction.user.display_name)
        )
        logger.info('Ticket %s fechado por %s', ticket.id, interaction.user.name)

        await asyncio.sleep(15)
        try:
            await canal.delete(reason=f'Ticket {ticket.id} fechado por {interaction.user.name}')
        except Exception as e:
            logger.error('Erro ao deletar canal do ticket %s: %s', ticket.id, e)

    # ══════════════════════════════════════════════════
    #  COMANDOS
    # ══════════════════════════════════════════════════

    @app_commands.command(
        name='tickets',
        description='[STAFF] Estatísticas dos tickets de suporte',
    )
    @app_commands.default_permissions(administrator=True)
    async def tickets(self, interaction: discord.Interaction):
        embed = discord.Embed(title='🎫  Tickets de Suporte', color=COR_PRINCIPAL)
        embed.add_field(name='🟢  Abertos', value=str(contar_tickets('aberto')), inline=True)
        embed.add_field(name='🔒  Fechados', value=str(contar_tickets('fechado')), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
    logger.info('Cog de tickets carregado')
