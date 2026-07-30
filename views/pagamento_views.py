"""
Views do fluxo de pagamento:
- PagamentoView: botões da cobrança PIX (verificar / simular / cancelar).
- CadastrarPixView: botão persistente para o dev cadastrar a chave PIX.
- SelecionarTipoChaveView + PixModal: fluxo de cadastro da chave.
"""

import logging
import discord
from discord.ui import View, Button, Select, Modal, TextInput

from config.settings import TIPOS_CHAVE_PIX, COR_ERRO
from core.database import buscar_dev, buscar_pagamento, salvar_pix_dev
from utils.helpers import validar_chave_pix
from embeds.pagamento_embed import criar_embed_pix_cadastrado

logger = logging.getLogger('bot_freeela.views.pagamento')


def mascarar_chave(chave: str) -> str:
    """Mascara a chave PIX para exibição: mostra só início e fim."""
    if len(chave) <= 6:
        return chave[:2] + '***'
    return f'{chave[:4]}***{chave[-3:]}'


# ══════════════════════════════════════════════════════
#  COBRANÇA
# ══════════════════════════════════════════════════════

class PagamentoView(View):
    """Botões anexados à mensagem da cobrança PIX."""

    def __init__(self, pagamento_id: str, dev_mode: bool = False):
        super().__init__(timeout=None)
        self.pagamento_id = pagamento_id

        btn_verificar = Button(
            label='🔄  Verificar Pagamento',
            style=discord.ButtonStyle.primary,
            custom_id=f'btn_pg_verificar_{pagamento_id}',
        )
        btn_verificar.callback = self.callback_verificar
        self.add_item(btn_verificar)

        if dev_mode:
            btn_simular = Button(
                label='🧪  Simular Pagamento (teste)',
                style=discord.ButtonStyle.secondary,
                custom_id=f'btn_pg_simular_{pagamento_id}',
            )
            btn_simular.callback = self.callback_simular
            self.add_item(btn_simular)

        btn_cancelar = Button(
            label='❌  Cancelar Cobrança',
            style=discord.ButtonStyle.danger,
            custom_id=f'btn_pg_cancelar_{pagamento_id}',
        )
        btn_cancelar.callback = self.callback_cancelar
        self.add_item(btn_cancelar)

    def _get_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog('PagamentosCog')

    async def callback_verificar(self, interaction: discord.Interaction):
        cog = self._get_cog(interaction)
        if not cog:
            await interaction.response.send_message('❌ Sistema de pagamentos indisponível.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        status = await cog.verificar_pagamento_agora(self.pagamento_id)
        mensagens = {
            'PAID': '✅ **Pagamento confirmado!** Processando o repasse...',
            'PENDING': '⏳ Pagamento ainda **não identificado**. Após pagar, aguarde alguns segundos e verifique novamente.',
            'EXPIRED': '⏰ Esta cobrança **expirou**. Gere uma nova com o botão **Concluir & Pagar**.',
            'CANCELLED': '❌ Esta cobrança foi **cancelada**.',
            'JA_PROCESSADO': '✅ Este pagamento já foi processado.',
        }
        await interaction.followup.send(
            mensagens.get(status, '❌ Não foi possível consultar o status agora. Tente novamente.'),
            ephemeral=True,
        )

    async def callback_simular(self, interaction: discord.Interaction):
        pagamento = buscar_pagamento(self.pagamento_id)
        if not pagamento or not pagamento.dev_mode:
            await interaction.response.send_message(
                '❌ Simulação disponível apenas em modo de desenvolvimento.',
                ephemeral=True,
            )
            return
        cog = self._get_cog(interaction)
        if not cog:
            await interaction.response.send_message('❌ Sistema de pagamentos indisponível.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        ok = await cog.simular_pagamento_teste(self.pagamento_id)
        await interaction.followup.send(
            '🧪 Pagamento simulado! O fluxo de confirmação e repasse será executado em instantes.'
            if ok else '❌ Não foi possível simular o pagamento.',
            ephemeral=True,
        )

    async def callback_cancelar(self, interaction: discord.Interaction):
        pagamento = buscar_pagamento(self.pagamento_id)
        if not pagamento:
            await interaction.response.send_message('❌ Cobrança não encontrada.', ephemeral=True)
            return
        if interaction.user.id not in (pagamento.dev_id, pagamento.empregador_id):
            await interaction.response.send_message(
                '❌ Apenas o dev ou o empregador podem cancelar a cobrança.',
                ephemeral=True,
            )
            return
        if pagamento.status != 'aguardando':
            await interaction.response.send_message(
                '⚠️ Esta cobrança não está mais pendente e não pode ser cancelada.',
                ephemeral=True,
            )
            return
        cog = self._get_cog(interaction)
        if not cog:
            await interaction.response.send_message('❌ Sistema de pagamentos indisponível.', ephemeral=True)
            return
        await interaction.response.defer()
        await cog.cancelar_cobranca(self.pagamento_id, canal=interaction.channel)
        logger.info('Cobrança %s cancelada por %s', self.pagamento_id, interaction.user.name)


# ══════════════════════════════════════════════════════
#  CADASTRO DE CHAVE PIX
# ══════════════════════════════════════════════════════

class CadastrarPixView(View):
    """Botão persistente para o dev cadastrar/atualizar a chave PIX."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='💳  Cadastrar Chave PIX',
        style=discord.ButtonStyle.success,
        custom_id='btn_cadastrar_pix_global',
    )
    async def btn_cadastrar(self, interaction: discord.Interaction, button: Button):
        dev = buscar_dev(interaction.user.id)
        if not dev:
            await interaction.response.send_message(
                '❌ Apenas **desenvolvedores verificados** podem cadastrar chave PIX.\n'
                'Complete sua verificação primeiro no canal de verificação.',
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            '🔑 Qual é o **tipo** da sua chave PIX?',
            view=SelecionarTipoChaveView(),
            ephemeral=True,
        )


class SelecionarTipoChaveView(View):
    """Select do tipo de chave PIX (efêmero)."""

    def __init__(self):
        super().__init__(timeout=300)
        opcoes = [
            discord.SelectOption(label=label, value=valor, emoji=emoji)
            for label, valor, emoji in TIPOS_CHAVE_PIX
        ]
        select = Select(
            placeholder='Selecione o tipo da chave...',
            min_values=1,
            max_values=1,
            options=opcoes,
        )
        select.callback = self.callback_tipo
        self.add_item(select)

    async def callback_tipo(self, interaction: discord.Interaction):
        tipo = interaction.data['values'][0]
        await interaction.response.send_modal(PixModal(tipo=tipo))


class PixModal(Modal, title='💳 Cadastro de Chave PIX'):
    """Modal para o dev informar a chave PIX e o nome do titular."""

    EXEMPLOS = {
        'CPF': '123.456.789-01',
        'CNPJ': '12.345.678/0001-90',
        'EMAIL': 'voce@email.com',
        'PHONE': '(11) 98765-4321',
        'RANDOM': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    }

    def __init__(self, tipo: str):
        super().__init__()
        self.tipo = tipo

        self.chave = TextInput(
            label=f'Chave PIX ({tipo})',
            placeholder=f'Ex: {self.EXEMPLOS.get(tipo, "")}',
            style=discord.TextStyle.short,
            required=True,
            max_length=120,
        )
        self.nome = TextInput(
            label='Nome completo do titular da chave',
            placeholder='Ex: João da Silva',
            style=discord.TextStyle.short,
            required=True,
            min_length=5,
            max_length=100,
        )
        self.add_item(self.chave)
        self.add_item(self.nome)

    async def on_submit(self, interaction: discord.Interaction):
        chave_normalizada = validar_chave_pix(self.chave.value, self.tipo)
        if not chave_normalizada:
            await interaction.response.send_message(
                f'❌ A chave informada **não é válida** para o tipo **{self.tipo}**.\n'
                f'Exemplo esperado: `{self.EXEMPLOS.get(self.tipo, "")}`\n'
                f'Tente novamente.',
                ephemeral=True,
            )
            return

        ok = salvar_pix_dev(
            user_id=interaction.user.id,
            pix_key=chave_normalizada,
            pix_key_type=self.tipo,
            pix_nome=self.nome.value,
        )
        if not ok:
            await interaction.response.send_message(
                '❌ Não encontrei seu cadastro de desenvolvedor. Complete a verificação primeiro.',
                ephemeral=True,
            )
            return

        tipo_label = next(
            (label for label, valor, _ in TIPOS_CHAVE_PIX if valor == self.tipo),
            self.tipo,
        )
        embed = criar_embed_pix_cadastrado(tipo_label, mascarar_chave(chave_normalizada))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info('Dev %s (%d) cadastrou chave PIX (%s)', interaction.user.name, interaction.user.id, self.tipo)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception('Erro no modal de PIX: %s', error)
        try:
            await interaction.response.send_message('❌ Erro ao salvar a chave. Tente novamente.', ephemeral=True)
        except discord.InteractionResponded:
            pass
