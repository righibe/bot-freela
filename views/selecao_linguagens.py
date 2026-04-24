import logging
import discord
from discord.ui import View, Select
from config.settings import LINGUAGENS_OPCOES, COR_PRINCIPAL
logger = logging.getLogger('bot_freeela.views.selecao_linguagens')

class SelecaoLinguagensView(View):

    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.linguagens_selecionadas: list[str] = []
        opcoes = [discord.SelectOption(label=lang, value=lang, emoji=_emoji_linguagem(lang)) for lang in LINGUAGENS_OPCOES]
        select = Select(placeholder='Selecione suas linguagens de programação...', min_values=1, max_values=len(LINGUAGENS_OPCOES), options=opcoes, custom_id='select_linguagens')
        select.callback = self.callback_linguagens
        self.add_item(select)

    async def callback_linguagens(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('❌ Apenas o usuário em verificação pode interagir.', ephemeral=True)
            return
        self.linguagens_selecionadas = interaction.data['values']
        langs_fmt = ', '.join((f'**{l}**' for l in self.linguagens_selecionadas))
        embed = discord.Embed(title='✅  Linguagens Selecionadas', description=f'Você selecionou: {langs_fmt}\n\n**Etapa 2 de 3** — Informe seu tempo de experiência.', color=COR_PRINCIPAL)
        from views.selecao_experiencia import SelecaoExperienciaView
        view = SelecaoExperienciaView(user_id=self.user_id, linguagens=self.linguagens_selecionadas)
        await interaction.response.edit_message(embed=embed, view=view)
        logger.info('Linguagens selecionadas por %s: %s', interaction.user.name, self.linguagens_selecionadas)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

def _emoji_linguagem(lang: str) -> str:
    emojis = {'Python': '🐍', 'Java': '☕', 'Rust': '🦀', 'JavaScript': '⚡', 'TypeScript': '🔷', 'Golang': '🐹', 'Kotlin': '🟣', 'C/C++': '⚙️', 'C#': '🎮', 'Swift': '🍎', 'Ruby': '💎'}
    return emojis.get(lang, '💻')