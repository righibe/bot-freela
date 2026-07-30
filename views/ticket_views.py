"""
Views do sistema de tickets:
- AbrirTicketView: select persistente com os tipos de ticket.
- FecharTicketView: botão persistente de fechar o ticket.
"""

import logging

import discord
from discord.ui import View, Select, Button

from config.settings import TIPOS_TICKET

logger = logging.getLogger('bot_freeela.views.ticket')


class AbrirTicketView(View):
    """Select persistente para abrir um ticket."""

    def __init__(self):
        super().__init__(timeout=None)
        opcoes = [
            discord.SelectOption(
                label=rotulo,
                value=slug,
                emoji=emoji,
                description=descricao[:100],
            )
            for rotulo, slug, emoji, descricao in TIPOS_TICKET
        ]
        select = Select(
            placeholder='🎫 Escolha o assunto do seu ticket...',
            min_values=1,
            max_values=1,
            options=opcoes,
            custom_id='select_abrir_ticket',
        )
        select.callback = self.callback_abrir
        self.add_item(select)

    async def callback_abrir(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog('TicketsCog')
        if not cog:
            await interaction.response.send_message(
                '❌ Sistema de tickets indisponível. Contate a staff.',
                ephemeral=True,
            )
            return
        tipo_slug = interaction.data['values'][0]
        await cog.abrir_ticket(interaction, tipo_slug)


class FecharTicketView(View):
    """Botão persistente de fechar ticket (dentro do canal do ticket)."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='🔒  Fechar Ticket',
        style=discord.ButtonStyle.danger,
        custom_id='btn_fechar_ticket_global',
    )
    async def btn_fechar(self, interaction: discord.Interaction, button: Button):
        cog = interaction.client.get_cog('TicketsCog')
        if not cog:
            await interaction.response.send_message('❌ Sistema de tickets indisponível.', ephemeral=True)
            return
        await cog.fechar_ticket_canal(interaction)
