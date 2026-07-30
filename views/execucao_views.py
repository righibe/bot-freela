"""
Views para o sistema de execução de projetos.
Botões de gerenciamento dentro do canal privado do projeto.

Com o gateway de pagamento configurado, "Concluir & Pagar" gera uma cobrança
PIX para o empregador; a conclusão só acontece após o pagamento confirmado e
o repasse automático ao dev.
"""

import logging
import discord
from discord.ui import View, Button

import config.settings as settings
from config.settings import COR_ERRO, COR_ALERTA
from core.database import (
    buscar_projeto_ativo_por_canal, atualizar_projeto_ativo,
    atualizar_projetos_ativos_dev, buscar_projeto, atualizar_status_projeto,
    salvar_projeto, buscar_pagamento_pendente_projeto,
)
from embeds.execucao_embed import criar_embed_alerta_dados_faltando
from modals.projeto_detalhes import ProjetoDetalhesModal
from services.abacatepay_service import pagamentos_configurados

logger = logging.getLogger('bot_freeela.views.execucao')


class ExecucaoProjetoView(View):
    """View com botões de gerenciamento do projeto ativo."""

    def __init__(self, projeto_ativo_id: str):
        super().__init__(timeout=None)
        self.projeto_ativo_id = projeto_ativo_id

        # Botão definir detalhes
        btn_detalhes = Button(
            label='📋  Definir Detalhes',
            style=discord.ButtonStyle.primary,
            custom_id=f'btn_detalhes_{projeto_ativo_id}',
            row=0,
        )
        btn_detalhes.callback = self.callback_detalhes
        self.add_item(btn_detalhes)

        # Botão concluir + pagar
        btn_concluir = Button(
            label='✅  Concluir & Pagar',
            style=discord.ButtonStyle.success,
            custom_id=f'btn_concluir_{projeto_ativo_id}',
            row=0,
        )
        btn_concluir.callback = self.callback_concluir
        self.add_item(btn_concluir)

        # Botão cancelar projeto
        btn_cancelar = Button(
            label='❌  Cancelar Projeto',
            style=discord.ButtonStyle.danger,
            custom_id=f'btn_cancelar_proj_{projeto_ativo_id}',
            row=1,
        )
        btn_cancelar.callback = self.callback_cancelar
        self.add_item(btn_cancelar)

        # Botão acionar staff
        btn_staff = Button(
            label='🚨  Acionar Staff',
            style=discord.ButtonStyle.secondary,
            custom_id=f'btn_staff_{projeto_ativo_id}',
            row=1,
        )
        btn_staff.callback = self.callback_staff
        self.add_item(btn_staff)

    async def callback_detalhes(self, interaction: discord.Interaction):
        """Abre modal para definir detalhes obrigatórios."""
        pa = buscar_projeto_ativo_por_canal(interaction.channel.id)
        if not pa:
            await interaction.response.send_message(
                '❌ Projeto não encontrado.',
                ephemeral=True,
            )
            return

        if interaction.user.id not in (pa.dev_id, pa.empregador_id):
            await interaction.response.send_message(
                '❌ Apenas o dev ou empregador podem definir detalhes.',
                ephemeral=True,
            )
            return

        modal = ProjetoDetalhesModal(canal_id=interaction.channel.id)
        await interaction.response.send_modal(modal)

    async def callback_concluir(self, interaction: discord.Interaction):
        """
        Conclui o projeto. Com o gateway configurado, gera a cobrança PIX
        (apenas o empregador pode iniciar, pois é ele quem paga).
        """
        pa = buscar_projeto_ativo_por_canal(interaction.channel.id)
        if not pa:
            await interaction.response.send_message(
                '❌ Projeto não encontrado.',
                ephemeral=True,
            )
            return

        if interaction.user.id not in (pa.dev_id, pa.empregador_id):
            await interaction.response.send_message(
                '❌ Apenas o dev ou empregador podem concluir.',
                ephemeral=True,
            )
            return

        # Detalhes obrigatórios precisam estar definidos
        if not pa.regras_confirmadas:
            campos_faltando = []
            if not pa.valor:
                campos_faltando.append('Valor fechado')
            if not pa.prazo:
                campos_faltando.append('Prazo de entrega')
            if not pa.escopo:
                campos_faltando.append('Escopo do projeto')
            if campos_faltando:
                embed = criar_embed_alerta_dados_faltando(campos_faltando)
                await interaction.response.send_message(embed=embed)
                return

        # ── Fluxo com pagamento automático (AbacatePay) ──
        if pagamentos_configurados():
            if buscar_pagamento_pendente_projeto(pa.id):
                await interaction.response.send_message(
                    '⚠️ Já existe uma cobrança PIX **em aberto** neste canal. '
                    'Pague o QR Code acima ou cancele-a antes de gerar outra.',
                    ephemeral=True,
                )
                return

            if interaction.user.id != pa.empregador_id:
                await interaction.response.send_message(
                    '💳 A conclusão do projeto passa pelo **pagamento via PIX**, '
                    'que deve ser iniciado pelo **empregador**.\n'
                    f'Peça para <@{pa.empregador_id}> clicar em **Concluir & Pagar**.',
                    ephemeral=True,
                )
                return

            cog_pg = interaction.client.get_cog('PagamentosCog')
            if not cog_pg:
                await interaction.response.send_message(
                    '❌ Sistema de pagamentos indisponível. Acione a staff.',
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)
            sucesso, mensagem = await cog_pg.iniciar_cobranca(
                canal=interaction.channel,
                pa=pa,
            )
            await interaction.followup.send(mensagem, ephemeral=True)
            return

        # ── Fallback: gateway não configurado — conclusão manual ──
        await interaction.response.defer()
        cog = interaction.client.get_cog('ExecucaoCog')
        if cog:
            await cog.finalizar_conclusao(
                guild=interaction.guild,
                projeto_ativo_id=pa.id,
            )
        logger.info('Projeto %s concluído manualmente por %s', pa.id, interaction.user.name)

    async def callback_cancelar(self, interaction: discord.Interaction):
        """Cancela o projeto ativo e republica na vitrine de projetos disponíveis."""
        pa = buscar_projeto_ativo_por_canal(interaction.channel.id)
        if not pa:
            await interaction.response.send_message(
                '❌ Projeto não encontrado.',
                ephemeral=True,
            )
            return

        if interaction.user.id not in (pa.dev_id, pa.empregador_id):
            await interaction.response.send_message(
                '❌ Apenas o dev ou empregador podem cancelar.',
                ephemeral=True,
            )
            return

        # Não permitir cancelar com cobrança em aberto
        if buscar_pagamento_pendente_projeto(pa.id):
            await interaction.response.send_message(
                '⚠️ Existe uma cobrança PIX **em aberto** para este projeto. '
                'Cancele a cobrança primeiro (botão na mensagem do QR Code).',
                ephemeral=True,
            )
            return

        # Marcar projeto ativo como cancelado
        pa.status = 'cancelado'
        atualizar_projeto_ativo(pa)
        atualizar_projetos_ativos_dev(pa.dev_id, -1)

        # Voltar status do projeto original para 'aberto'
        atualizar_status_projeto(pa.projeto_id, 'aberto')

        projeto = buscar_projeto(pa.projeto_id)
        titulo = projeto.titulo if projeto else 'Projeto'

        embed = discord.Embed(
            title='❌  Parceria Cancelada',
            description=(
                f'A parceria do projeto **{titulo}** foi cancelada por '
                f'**{interaction.user.display_name}**.\n\n'
                f'O projeto será republicado em **Projetos Disponíveis** '
                f'para que outros desenvolvedores possam se candidatar.\n\n'
                f'Se houver disputa, acione a staff.'
            ),
            color=COR_ERRO,
        )
        await interaction.response.send_message(embed=embed)

        cog = interaction.client.get_cog('ExecucaoCog')
        if cog:
            await cog.enviar_log_projeto(interaction.guild, pa, 'cancelado → reaberto', titulo)

        # Limpar candidatos anteriores para permitir novas candidaturas
        if projeto:
            projeto.candidatos = []
            projeto.status = 'aberto'
            salvar_projeto(projeto)

        if cog:
            await cog.republicar_projeto_na_vitrine(interaction.guild, projeto)
            await cog.deletar_categoria_projeto(interaction.guild, pa)

        logger.info('Projeto %s cancelado e republicado por %s', pa.id, interaction.user.name)

    async def callback_staff(self, interaction: discord.Interaction):
        """Aciona a staff para intervenção."""
        pa = buscar_projeto_ativo_por_canal(interaction.channel.id)
        if not pa:
            await interaction.response.send_message(
                '❌ Projeto não encontrado.',
                ephemeral=True,
            )
            return

        cargo_staff = interaction.guild.get_role(settings.CARGO_STAFF)
        mencao = cargo_staff.mention if cargo_staff else ''

        embed = discord.Embed(
            title='🚨  Staff Acionada!',
            description=(
                f'{interaction.user.mention} solicitou intervenção da staff.\n\n'
                f'**Projeto:** {pa.id}\n'
                f'**Dev:** <@{pa.dev_id}>\n'
                f'**Empregador:** <@{pa.empregador_id}>\n\n'
                f'A equipe será notificada e responderá em breve.'
            ),
            color=COR_ALERTA,
        )
        await interaction.response.send_message(content=mencao, embed=embed)
        logger.warning('Staff acionada no projeto %s por %s', pa.id, interaction.user.name)
