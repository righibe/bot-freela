"""
View para devs verificados atualizarem seu perfil.
Disponível em um canal da categoria de verificação.
"""

import logging
import discord
from discord.ui import View, Button
from config.settings import get_cargo_dev_verificado
from core.database import DevVerificado, buscar_dev

logger = logging.getLogger('bot_freeela.views.atualizar_perfil_dev')


class AtualizarPerfilDevView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='🔄  Atualizar Perfil',
        style=discord.ButtonStyle.primary,
        custom_id='btn_atualizar_perfil_dev',
    )
    async def btn_atualizar_perfil(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.response.send_message('❌ Erro interno.', ephemeral=True)
            return

        cargo_dev = get_cargo_dev_verificado(guild)
        tem_cargo = bool(cargo_dev and cargo_dev in user.roles)

        dev = buscar_dev(user.id)
        if not dev and not tem_cargo:
            await interaction.response.send_message(
                '❌ Apenas devs verificados podem atualizar o perfil.\n'
                'Complete a verificação primeiro clicando em **Iniciar Verificação**.',
                ephemeral=True,
            )
            return

        # Tem o cargo mas não está no banco (verificado antes do sistema atual):
        # o fluxo de atualização preenche tudo de novo e recria o registro.
        if not dev:
            dev = DevVerificado(user_id=user.id, username=user.name)

        from modals.atualizar_perfil_dev import AtualizarPerfilDevModal
        await interaction.response.send_modal(AtualizarPerfilDevModal(dev=dev))
        logger.info('Dev %s abriu o fluxo de atualização de perfil', user.name)
