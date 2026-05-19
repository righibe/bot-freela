"""
View para devs verificados atualizarem seu perfil.
Disponível em um canal da categoria de verificação.
"""

import logging
import discord
from discord.ui import View, Button
from config.settings import COR_PRINCIPAL, get_cargo_dev_verificado
from modals.atualizar_perfil_dev import AtualizarPerfilDevModal

logger = logging.getLogger('bot_freeela.views.atualizar_perfil_dev')


class AtualizarPerfilDevView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='🔄  Atualizar Perfil',
        style=discord.ButtonStyle.primary,
        custom_id='btn_atualizar_perfil_dev',
        emoji='🔄'
    )
    async def btn_atualizar_perfil(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.response.send_message('❌ Erro interno.', ephemeral=True)
            return

        # Verificar se o usuário é dev verificado
        cargo_dev = get_cargo_dev_verificado(guild)
        if not cargo_dev or cargo_dev not in user.roles:
            await interaction.response.send_message(
                '❌ Apenas devs verificados podem atualizar seu perfil.\n'
                'Complete a verificação primeiro clicando em **Iniciar Verificação**.',
                ephemeral=True,
            )
            return

        # Abrir modal
        modal = AtualizarPerfilDevModal(user_id=user.id, guild=guild)
        await interaction.response.send_modal(modal)
        logger.info('Dev %s abriu modal de atualização de perfil', user.name)
