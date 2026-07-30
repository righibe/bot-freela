import logging
import discord
from discord.ui import View, Button
from config.settings import CANAL_VERIFICAR_DEV, COR_PRINCIPAL, MSG_VERIFICACAO_INICIADA
logger = logging.getLogger('bot_freeela.views.iniciar_verificacao')

class IniciarVerificacaoView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🚀  Iniciar Verificação', style=discord.ButtonStyle.primary, custom_id='btn_iniciar_verificacao', row=0)
    async def btn_iniciar(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message('❌ Erro interno. Tente novamente.', ephemeral=True)
            return

        # Aceite dos Termos de Uso é obrigatório antes da verificação
        from views.termos_views import exigir_aceite_termos
        if not await exigir_aceite_termos(interaction):
            return

        from modals.perfil_profissional import PerfilProfissionalModal
        modal = PerfilProfissionalModal(user_id=interaction.user.id)
        await interaction.response.send_modal(modal)