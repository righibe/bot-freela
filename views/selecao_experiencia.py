import logging
import discord
from discord.ui import View, Select
from config.settings import OPCOES_EXPERIENCIA, COR_PRINCIPAL, COR_ERRO, MSG_REPROVADO_EXPERIENCIA
logger = logging.getLogger('bot_freeela.views.selecao_experiencia')

class SelecaoExperienciaView(View):

    def __init__(self, user_id: int, linguagens: list[str]):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.linguagens = linguagens
        opcoes = [discord.SelectOption(label=label, value=valor, emoji=_emoji_experiencia(valor)) for label, valor in OPCOES_EXPERIENCIA]
        select = Select(placeholder='Selecione seu tempo de experiência...', min_values=1, max_values=1, options=opcoes, custom_id='select_experiencia')
        select.callback = self.callback_experiencia
        self.add_item(select)

    async def callback_experiencia(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('❌ Apenas o usuário em verificação pode interagir.', ephemeral=True)
            return
        experiencia = interaction.data['values'][0]
        if experiencia == '6_meses':
            embed = discord.Embed(title='❌  Verificação Encerrada', description=MSG_REPROVADO_EXPERIENCIA, color=COR_ERRO)
            embed.set_footer(text='Você pode tentar novamente quando atingir 1 ano de experiência.')
            await interaction.response.edit_message(embed=embed, view=None)
            await _arquivar_thread(interaction.channel)
            logger.info('Usuário %s reprovado por experiência insuficiente', interaction.user.name)
            return
        from modals.perfil_profissional import PerfilProfissionalModal
        modal = PerfilProfissionalModal(user_id=self.user_id, linguagens=self.linguagens, experiencia=experiencia, thread=interaction.channel)
        await interaction.response.send_modal(modal)
        logger.info('Experiência selecionada por %s: %s', interaction.user.name, experiencia)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

async def _arquivar_thread(channel):
    import asyncio
    await asyncio.sleep(10)
    try:
        if isinstance(channel, discord.Thread):
            await channel.edit(archived=True, locked=True)
    except Exception as e:
        logger.error('Erro ao arquivar thread: %s', e)

def _emoji_experiencia(valor: str) -> str:
    emojis = {'6_meses': '🌱', '1_ano': '📗', '2_anos': '📘', '4_6_anos': '📙', '6_mais': '📕'}
    return emojis.get(valor, '📖')