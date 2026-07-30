"""
Views do sistema de tecnologias:
- SugerirTecnologiaView: botão persistente do canal 💡・sugerir-tecnologia.
- SugestaoTecnologiaModal: formulário da sugestão.
- AnalisarSugestaoView: botões aprovar/rejeitar para a staff (persistente,
  reconstruída no cog_load para sugestões pendentes).
"""

import logging

import discord
from discord.ui import View, Button, Modal, TextInput

import config.settings as settings
from config.settings import COR_SUCESSO, COR_ERRO, COR_PRINCIPAL
from core.database import buscar_dev, buscar_tecnologia
from core.tecnologias import sugerir_tecnologia, aprovar_sugestao, rejeitar_sugestao

logger = logging.getLogger('bot_freeela.views.tecnologia')


class SugerirTecnologiaView(View):
    """Botão persistente para sugerir uma nova tecnologia."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='💡  Sugerir Tecnologia',
        style=discord.ButtonStyle.primary,
        custom_id='btn_sugerir_tecnologia',
    )
    async def btn_sugerir(self, interaction: discord.Interaction, button: Button):
        # Apenas devs verificados podem sugerir (evita spam de sugestões)
        if not buscar_dev(interaction.user.id):
            await interaction.response.send_message(
                '❌ Apenas **desenvolvedores verificados** podem sugerir tecnologias.\n'
                'Complete sua verificação primeiro!',
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(SugestaoTecnologiaModal())


class SugestaoTecnologiaModal(Modal, title='💡 Sugerir Nova Tecnologia'):
    nome = TextInput(
        label='Nome da tecnologia',
        placeholder='Ex: Elixir, Laravel, Kubernetes...',
        style=discord.TextStyle.short,
        required=True,
        min_length=2,
        max_length=40,
    )
    justificativa = TextInput(
        label='Por que ela deveria existir aqui?',
        placeholder='Ex: trabalho com Elixir há 3 anos e há demanda de projetos...',
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        ok, mensagem = sugerir_tecnologia(self.nome.value, interaction.user.id)
        await interaction.response.send_message(mensagem, ephemeral=True)
        if not ok:
            return

        tec = buscar_tecnologia(self.nome.value)
        if not tec:
            return

        # Enviar para análise da staff no canal de log
        guild = interaction.guild
        canal_log = guild.get_channel(settings.CANAL_LOG_DEV) if guild else None
        if canal_log:
            cargo_staff = guild.get_role(settings.CARGO_STAFF)
            embed = discord.Embed(
                title='💡  Nova Sugestão de Tecnologia',
                description=(
                    f'**Tecnologia:** `{tec.nome}`\n'
                    f'**Sugerida por:** {interaction.user.mention} (`{interaction.user.name}`)\n'
                    f'**Justificativa:** {self.justificativa.value}'
                ),
                color=COR_PRINCIPAL,
            )
            embed.set_footer(text='Aprovar cria o cargo e libera a tecnologia para seleção e matching.')
            try:
                await canal_log.send(
                    content=cargo_staff.mention if cargo_staff else '',
                    embed=embed,
                    view=AnalisarSugestaoView(nome_tecnologia=tec.nome),
                )
            except Exception as e:
                logger.error('Erro ao enviar sugestão para a staff: %s', e)
        logger.info('Sugestão de tecnologia "%s" por %s', tec.nome, interaction.user.name)


class AnalisarSugestaoView(View):
    """Botões de aprovação/rejeição de uma sugestão (staff)."""

    def __init__(self, nome_tecnologia: str):
        super().__init__(timeout=None)
        self.nome_tecnologia = nome_tecnologia

        btn_aprovar = Button(
            label='✅  Aprovar e Criar Cargo',
            style=discord.ButtonStyle.success,
            custom_id=f'btn_aprovar_tec_{nome_tecnologia}',
        )
        btn_aprovar.callback = self.callback_aprovar
        self.add_item(btn_aprovar)

        btn_rejeitar = Button(
            label='❌  Rejeitar',
            style=discord.ButtonStyle.danger,
            custom_id=f'btn_rejeitar_tec_{nome_tecnologia}',
        )
        btn_rejeitar.callback = self.callback_rejeitar
        self.add_item(btn_rejeitar)

    async def _finalizar(self, interaction: discord.Interaction, embed_cor, titulo: str):
        embed = interaction.message.embeds[0]
        embed.color = embed_cor
        embed.title = titulo
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)

    async def _notificar_sugestor(self, interaction: discord.Interaction, texto: str):
        tec = buscar_tecnologia(self.nome_tecnologia)
        if not tec or not tec.sugerida_por:
            return
        try:
            user = interaction.client.get_user(tec.sugerida_por) or await interaction.client.fetch_user(tec.sugerida_por)
            await user.send(texto)
        except Exception:
            pass

    async def callback_aprovar(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cargo = await aprovar_sugestao(interaction.guild, self.nome_tecnologia)
        await self._finalizar(
            interaction, COR_SUCESSO,
            f'✅ APROVADA por {interaction.user.name} — {self.nome_tecnologia}',
        )
        await self._notificar_sugestor(
            interaction,
            f'🎉 Sua sugestão de tecnologia **{self.nome_tecnologia}** foi **aprovada**!\n'
            f'Ela já está disponível na verificação e no matching de projetos. '
            f'Atualize seu perfil para adicioná-la ao seu stack!',
        )
        logger.info(
            'Tecnologia %s aprovada por %s (cargo=%s)',
            self.nome_tecnologia, interaction.user.name, cargo.id if cargo else 'ERRO',
        )

    async def callback_rejeitar(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rejeitar_sugestao(self.nome_tecnologia)
        await self._finalizar(
            interaction, COR_ERRO,
            f'❌ REJEITADA por {interaction.user.name} — {self.nome_tecnologia}',
        )
        await self._notificar_sugestor(
            interaction,
            f'❌ Sua sugestão de tecnologia **{self.nome_tecnologia}** foi analisada '
            f'pela staff e **não foi aprovada** neste momento.',
        )
        logger.info('Tecnologia %s rejeitada por %s', self.nome_tecnologia, interaction.user.name)
