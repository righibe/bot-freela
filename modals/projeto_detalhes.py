"""
Modal para definir detalhes obrigatórios do projeto ativo.
(valor fechado, prazo, escopo)
"""

import logging
import discord
from discord.ui import Modal, TextInput
from config.settings import COR_SUCESSO, COR_ERRO
from core.database import (
    buscar_projeto_ativo_por_canal, atualizar_projeto_ativo,
)

logger = logging.getLogger('bot_freeela.modals.projeto_detalhes')


class ProjetoDetalhesModal(Modal, title='📋 Definir Detalhes do Projeto'):
    """Modal para definir valor, prazo e escopo obrigatórios."""

    valor_final = TextInput(
        label='Valor fechado (R$)',
        style=discord.TextStyle.short,
        placeholder='Ex: 1500',
        required=True,
        max_length=20,
    )
    prazo_final = TextInput(
        label='Prazo de entrega',
        style=discord.TextStyle.short,
        placeholder='Ex: 2 semanas / 30 dias',
        required=True,
        max_length=100,
    )
    escopo_final = TextInput(
        label='Escopo do projeto',
        style=discord.TextStyle.paragraph,
        placeholder='Descreva exatamente o que será entregue...',
        required=True,
        min_length=10,
        max_length=2000,
    )

    def __init__(self, canal_id: int):
        super().__init__()
        self.canal_id = canal_id

    async def on_submit(self, interaction: discord.Interaction):
        pa = buscar_projeto_ativo_por_canal(self.canal_id)
        if not pa:
            await interaction.response.send_message(
                '❌ Projeto ativo não encontrado para este canal.',
                ephemeral=True,
            )
            return

        # Parse valor
        valor_str = self.valor_final.value.replace('R$', '').replace('r$', '').replace('.', '').replace(',', '.').strip()
        try:
            valor = float(valor_str)
        except ValueError:
            await interaction.response.send_message(
                '❌ Valor inválido. Use apenas números.',
                ephemeral=True,
            )
            return

        # Atualizar projeto ativo
        pa.valor = valor
        pa.prazo = self.prazo_final.value.strip()
        pa.escopo = self.escopo_final.value.strip()
        pa.regras_confirmadas = True
        atualizar_projeto_ativo(pa)

        embed = discord.Embed(
            title='✅  Detalhes do Projeto Definidos',
            description='Os detalhes obrigatórios foram registrados com sucesso.',
            color=COR_SUCESSO,
        )
        embed.add_field(
            name='💰  Valor Fechado',
            value=f'**R$ {valor:,.2f}**',
            inline=True,
        )
        embed.add_field(
            name='⏰  Prazo',
            value=self.prazo_final.value,
            inline=True,
        )
        embed.add_field(
            name='📋  Escopo',
            value=self.escopo_final.value[:1024],
            inline=False,
        )
        await interaction.response.send_message(embed=embed)
        logger.info(
            'Detalhes definidos para projeto ativo %s: valor=%.2f prazo=%s',
            pa.id, valor, self.prazo_final.value,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception('Erro no modal de detalhes: %s', error)
        try:
            await interaction.response.send_message(
                '❌ Erro ao processar os detalhes.',
                ephemeral=True,
            )
        except discord.InteractionResponded:
            pass
