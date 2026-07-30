"""
Seleção de tecnologias na verificação de dev.
As opções vêm do banco (tabela tecnologias) — máximo de 5 por dev,
com selects paginados (25 opções cada) e botão de confirmação.
"""

import logging

import discord
from discord.ui import View, Select, Button

from config.settings import COR_PRINCIPAL, COR_ERRO, MAX_TECNOLOGIAS_POR_DEV
from core.tecnologias import nomes_ativas

logger = logging.getLogger('bot_freeela.views.selecao_linguagens')

EMOJIS_TECNOLOGIA = {
    'Python': '🐍', 'Java': '☕', 'Rust': '🦀', 'JavaScript': '⚡',
    'TypeScript': '🔷', 'Golang': '🐹', 'Kotlin': '🟣', 'C/C++': '⚙️',
    'C#': '🎮', 'Swift': '🍎', 'Ruby': '💎', 'PHP': '🐘', 'Dart': '🎯',
    'HTML/CSS': '🎨', 'SQL': '🗄️', 'Bash': '💲', 'React': '⚛️',
    'React Native': '📱', 'Node.js': '🟢', 'Angular': '🅰️', 'Vue': '💚',
    'Django': '🌿', 'Flutter': '🦋', 'Unity': '🕹️',
}


def _emoji_tecnologia(nome: str) -> str:
    return EMOJIS_TECNOLOGIA.get(nome, '💻')


class SelecaoLinguagensView(View):
    """Selects paginados de tecnologias + botão Confirmar (máximo 5 no total)."""

    def __init__(self, user_id: int, github: str, linkedin: str, descricao: str, thread: discord.Thread):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.github = github
        self.linkedin = linkedin
        self.descricao = descricao
        self.thread = thread
        self.selecoes_por_pagina: dict[int, list[str]] = {}

        tecnologias = nomes_ativas()
        paginas = [tecnologias[i:i + 25] for i in range(0, len(tecnologias), 25)][:4]

        for indice, pagina in enumerate(paginas):
            opcoes = [
                discord.SelectOption(label=nome, value=nome, emoji=_emoji_tecnologia(nome))
                for nome in pagina
            ]
            select = Select(
                placeholder=(
                    f'Suas tecnologias ({pagina[0][0]}–{pagina[-1][0]})...'
                    if len(paginas) > 1 else
                    f'Selecione até {MAX_TECNOLOGIAS_POR_DEV} tecnologias...'
                ),
                min_values=0,
                max_values=min(MAX_TECNOLOGIAS_POR_DEV, len(opcoes)),
                options=opcoes,
                custom_id=f'select_tecnologias_{indice}',
                row=indice,
            )
            select.callback = self._fazer_callback(indice)
            self.add_item(select)

        btn = Button(
            label=f'✅  Confirmar Seleção (máx. {MAX_TECNOLOGIAS_POR_DEV})',
            style=discord.ButtonStyle.success,
            custom_id='btn_confirmar_tecnologias',
            row=4,
        )
        btn.callback = self.callback_confirmar
        self.add_item(btn)

    def _fazer_callback(self, indice: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    '❌ Apenas o usuário em verificação pode interagir.', ephemeral=True,
                )
                return
            self.selecoes_por_pagina[indice] = list(interaction.data['values'])
            total = self._selecionadas()
            await interaction.response.defer()
            logger.info('Seleção parcial de %s: %s', interaction.user.name, total)
        return callback

    def _selecionadas(self) -> list[str]:
        todas = []
        for pagina in sorted(self.selecoes_por_pagina):
            for nome in self.selecoes_por_pagina[pagina]:
                if nome not in todas:
                    todas.append(nome)
        return todas

    async def callback_confirmar(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                '❌ Apenas o usuário em verificação pode interagir.', ephemeral=True,
            )
            return

        selecionadas = self._selecionadas()
        if not selecionadas:
            await interaction.response.send_message(
                '⚠️ Selecione pelo menos **1 tecnologia** antes de confirmar.',
                ephemeral=True,
            )
            return
        if len(selecionadas) > MAX_TECNOLOGIAS_POR_DEV:
            await interaction.response.send_message(
                f'⚠️ Você selecionou **{len(selecionadas)}** tecnologias — o máximo é '
                f'**{MAX_TECNOLOGIAS_POR_DEV}**. Ajuste sua seleção e confirme de novo.',
                ephemeral=True,
            )
            return

        langs_fmt = ', '.join(f'**{l}**' for l in selecionadas)
        embed = discord.Embed(
            title='✅  Tecnologias Selecionadas',
            description=(
                f'Você selecionou: {langs_fmt}\n\n'
                f'**Etapa 3 de 3** — Informe seu tempo de experiência.'
            ),
            color=COR_PRINCIPAL,
        )
        from views.selecao_experiencia import SelecaoExperienciaView
        view = SelecaoExperienciaView(
            user_id=self.user_id,
            github=self.github,
            linkedin=self.linkedin,
            descricao=self.descricao,
            thread=self.thread,
            linguagens=selecionadas,
        )
        await interaction.response.edit_message(embed=embed, view=view)
        logger.info('Tecnologias confirmadas por %s: %s', interaction.user.name, selecionadas)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
