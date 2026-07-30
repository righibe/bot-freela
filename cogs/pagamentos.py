"""
Cog de pagamentos — integração com a AbacatePay.

Fluxo completo:
1. Empregador clica em "Concluir & Pagar" no canal do projeto.
2. O bot gera um QR Code PIX no valor fechado do projeto.
3. O pagamento é confirmado por polling (e/ou webhook).
4. O bot envia automaticamente o repasse (85%) via PIX para a chave do dev;
   os 15% restantes ficam na conta AbacatePay da plataforma.
5. O projeto é concluído e os canais são arquivados.
"""

import asyncio
import logging

import discord
from discord.ext import commands
from discord import app_commands

import config.settings as settings
from core.database import (
    Pagamento, ProjetoAtivo,
    buscar_dev, buscar_projeto, buscar_projeto_ativo, buscar_pagamento,
    buscar_pagamento_pendente_projeto, listar_pagamentos_por_status,
    salvar_pagamento, atualizar_status_pagamento, atualizar_projeto_ativo,
    marcar_pagamento_em_repasse, marcar_pagamento_repassado,
    somar_receita_plataforma, _gerar_id,
)
from services.abacatepay_service import (
    pagamentos_configurados, criar_cobranca_pix, checar_status_cobranca,
    simular_pagamento, enviar_pix, decodificar_qrcode_base64, calcular_split,
)
from embeds.pagamento_embed import (
    criar_embed_cobranca, criar_embed_pagamento_confirmado,
    criar_embed_solicitar_pix, criar_embed_erro_repasse,
    criar_embed_cobranca_cancelada, criar_embed_cobranca_expirada,
)
from views.pagamento_views import PagamentoView, CadastrarPixView, SelecionarTipoChaveView, mascarar_chave
from utils.helpers import formatar_brl_centavos

logger = logging.getLogger('bot_freeela.cogs.pagamentos')


class PagamentosCog(commands.Cog):
    """Cog responsável pelo fluxo de pagamento dos projetos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._poll_tasks: dict[str, asyncio.Task] = {}

    async def cog_load(self):
        # Botão global de cadastro de PIX
        self.bot.add_view(CadastrarPixView())

        # Recuperar cobranças que ficaram pendentes entre reinícios do bot
        pendentes = listar_pagamentos_por_status('aguardando') + listar_pagamentos_por_status('pago')
        for pg in pendentes:
            self.bot.add_view(PagamentoView(pagamento_id=pg.id, dev_mode=pg.dev_mode))
            self._iniciar_poll(pg.id)

        # Pagamentos que morreram no meio do repasse precisam de revisão humana
        # (o PIX pode ou não ter saído — nunca reenviar automaticamente).
        interrompidos = listar_pagamentos_por_status('repassando')
        for pg in interrompidos:
            atualizar_status_pagamento(pg.id, 'erro_repasse')
            logger.error(
                'Pagamento %s estava em repasse durante o desligamento — marcado para revisão manual',
                pg.id,
            )

        logger.info(
            'Cog de pagamentos carregado | %d cobranças pendentes retomadas | gateway %s',
            len(pendentes),
            'CONFIGURADO' if pagamentos_configurados() else 'NÃO CONFIGURADO (fluxo manual)',
        )

    def cog_unload(self):
        for task in self._poll_tasks.values():
            task.cancel()

    # ══════════════════════════════════════════════════
    #  INÍCIO DA COBRANÇA
    # ══════════════════════════════════════════════════

    async def iniciar_cobranca(
        self,
        canal: discord.TextChannel,
        pa: ProjetoAtivo,
    ) -> tuple[bool, str]:
        """
        Cria a cobrança PIX de um projeto ativo e publica o QR Code no canal.
        Retorna (sucesso, mensagem para o usuário).
        """
        # Evitar cobrança duplicada
        existente = buscar_pagamento_pendente_projeto(pa.id)
        if existente:
            return False, (
                '⚠️ Já existe uma cobrança PIX **em aberto** para este projeto. '
                'Pague o QR Code acima ou cancele a cobrança antes de gerar outra.'
            )

        dev = buscar_dev(pa.dev_id)
        if not dev or not dev.pix_key:
            # Dev ainda não cadastrou a chave — pedir no canal
            embed = criar_embed_solicitar_pix(f'<@{pa.dev_id}>')
            await canal.send(embed=embed, view=CadastrarPixView())
            return False, (
                '⚠️ O desenvolvedor ainda **não cadastrou a chave PIX**. '
                'Pedi para ele cadastrar aqui no canal — assim que fizer isso, '
                'clique em **Concluir & Pagar** novamente.'
            )

        projeto = buscar_projeto(pa.projeto_id)
        titulo = projeto.titulo if projeto else 'Projeto Freeela'

        valor_centavos = round(pa.valor * 100)
        if valor_centavos < 100:
            return False, '❌ O valor do projeto é inválido para cobrança (mínimo R$ 1,00).'

        taxa, valor_dev = calcular_split(valor_centavos, settings.TAXA_PLATAFORMA_PERCENT)

        pagamento = Pagamento(
            id=_gerar_id('pgto'),
            projeto_ativo_id=pa.id,
            dev_id=pa.dev_id,
            empregador_id=pa.empregador_id,
            valor_total_centavos=valor_centavos,
            taxa_plataforma_centavos=taxa,
            valor_dev_centavos=valor_dev,
            pix_key=dev.pix_key,
            pix_key_type=dev.pix_key_type,
            canal_id=canal.id,
        )

        cobranca = await criar_cobranca_pix(
            valor_centavos=valor_centavos,
            descricao=f'Freeela: {titulo}'[:37],
            external_id=pagamento.id,
            expiracao_segundos=settings.PIX_EXPIRACAO_SEGUNDOS,
        )
        if not cobranca:
            return False, (
                '❌ Não foi possível gerar a cobrança PIX agora. '
                'Tente novamente em instantes ou acione a staff.'
            )

        pagamento.cobranca_id = cobranca.get('id', '')
        pagamento.br_code = cobranca.get('brCode', '')
        pagamento.dev_mode = bool(cobranca.get('devMode', False))

        # Publicar o QR Code no canal
        embed = criar_embed_cobranca(
            titulo_projeto=titulo,
            valor_total_centavos=valor_centavos,
            dev_mention=f'<@{pa.dev_id}>',
            empregador_mention=f'<@{pa.empregador_id}>',
            br_code=pagamento.br_code,
            expiracao_minutos=settings.PIX_EXPIRACAO_SEGUNDOS // 60,
            dev_mode=pagamento.dev_mode,
        )
        view = PagamentoView(pagamento_id=pagamento.id, dev_mode=pagamento.dev_mode)

        arquivos = []
        qr_bytes = decodificar_qrcode_base64(cobranca.get('brCodeBase64', ''))
        if qr_bytes:
            import io
            arquivos.append(discord.File(io.BytesIO(qr_bytes), filename='qrcode_pix.png'))

        msg = await canal.send(embed=embed, view=view, files=arquivos)
        pagamento.mensagem_id = msg.id
        salvar_pagamento(pagamento)

        # Projeto entra em "aguardando pagamento"
        pa.status = 'aguardando_pagamento'
        atualizar_projeto_ativo(pa)

        self._iniciar_poll(pagamento.id)
        logger.info(
            'Cobrança iniciada: %s | projeto=%s | %s',
            pagamento.id, pa.id, formatar_brl_centavos(valor_centavos),
        )
        return True, '✅ Cobrança PIX gerada! O QR Code foi publicado no canal. 👇'

    # ══════════════════════════════════════════════════
    #  POLLING
    # ══════════════════════════════════════════════════

    def _iniciar_poll(self, pagamento_id: str) -> None:
        if pagamento_id in self._poll_tasks and not self._poll_tasks[pagamento_id].done():
            return
        self._poll_tasks[pagamento_id] = asyncio.create_task(self._poll_loop(pagamento_id))

    async def _poll_loop(self, pagamento_id: str) -> None:
        """Consulta o status da cobrança periodicamente até resolução."""
        # Margem extra além da expiração do QR Code
        tentativas_max = (settings.PIX_EXPIRACAO_SEGUNDOS + 120) // settings.PIX_POLL_INTERVALO_SEGUNDOS
        try:
            for _ in range(int(tentativas_max)):
                await asyncio.sleep(settings.PIX_POLL_INTERVALO_SEGUNDOS)

                pagamento = buscar_pagamento(pagamento_id)
                if not pagamento:
                    return

                # Webhook pode já ter marcado como pago
                if pagamento.status == 'pago':
                    await self._processar_pagamento_confirmado(pagamento_id)
                    return
                if pagamento.status != 'aguardando':
                    return  # cancelado/expirado/repassado por outro caminho

                status = await checar_status_cobranca(pagamento.cobranca_id)
                if status == 'PAID':
                    await self._processar_pagamento_confirmado(pagamento_id)
                    return
                if status in ('EXPIRED', 'CANCELLED'):
                    await self._encerrar_cobranca(pagamento_id, 'expirado' if status == 'EXPIRED' else 'cancelado')
                    return

            # Tempo esgotado sem resposta definitiva
            pagamento = buscar_pagamento(pagamento_id)
            if pagamento and pagamento.status == 'aguardando':
                await self._encerrar_cobranca(pagamento_id, 'expirado')
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception('Erro no polling do pagamento %s: %s', pagamento_id, e)

    # ══════════════════════════════════════════════════
    #  CONFIRMAÇÃO + REPASSE
    # ══════════════════════════════════════════════════

    async def _processar_pagamento_confirmado(self, pagamento_id: str) -> None:
        """
        Pagamento confirmado: envia o repasse ao dev, publica o recibo
        e conclui o projeto. Protegido contra processamento duplo.
        """
        if not marcar_pagamento_em_repasse(pagamento_id):
            return  # outro fluxo já está processando

        pagamento = buscar_pagamento(pagamento_id)
        if not pagamento:
            return

        pa = buscar_projeto_ativo(pagamento.projeto_ativo_id)
        projeto = buscar_projeto(pa.projeto_id) if pa else None
        titulo = projeto.titulo if projeto else 'Projeto Freeela'
        canal = self.bot.get_channel(pagamento.canal_id)

        # ── Repasse ao dev (85%) ──
        repasse_ok = False
        transferencia = await enviar_pix(
            chave=pagamento.pix_key,
            tipo_chave=pagamento.pix_key_type,
            valor_centavos=pagamento.valor_dev_centavos,
            external_id=f'{pagamento.id}_repasse',
            descricao=f'Freeela: {titulo}'[:100],
        )
        if transferencia:
            marcar_pagamento_repassado(pagamento.id, transferencia.get('id', ''))
            repasse_ok = True
        else:
            atualizar_status_pagamento(pagamento.id, 'erro_repasse')
            await self._alertar_staff_erro_repasse(pagamento, canal)

        # ── Recibo no canal ──
        embed = criar_embed_pagamento_confirmado(
            titulo_projeto=titulo,
            valor_total_centavos=pagamento.valor_total_centavos,
            taxa_centavos=pagamento.taxa_plataforma_centavos,
            valor_dev_centavos=pagamento.valor_dev_centavos,
            dev_mention=f'<@{pagamento.dev_id}>',
            repasse_ok=repasse_ok,
        )
        if canal:
            await self._desativar_botoes_cobranca(canal, pagamento)
            try:
                await canal.send(
                    content=f'<@{pagamento.dev_id}> <@{pagamento.empregador_id}>',
                    embed=embed,
                )
            except Exception as e:
                logger.error('Erro ao enviar recibo no canal %d: %s', pagamento.canal_id, e)

        # ── Recibo por DM ──
        await self._enviar_recibos_dm(pagamento, titulo, repasse_ok)

        # ── Concluir o projeto ──
        if pa:
            execucao_cog = self.bot.get_cog('ExecucaoCog')
            if execucao_cog and canal:
                await execucao_cog.finalizar_conclusao(
                    guild=canal.guild,
                    projeto_ativo_id=pa.id,
                    delay_limpeza=60,  # deixa o recibo visível por 1 min antes de arquivar
                )

        logger.info(
            'Pagamento %s processado | repasse_ok=%s | total=%s',
            pagamento.id, repasse_ok, formatar_brl_centavos(pagamento.valor_total_centavos),
        )

    async def _desativar_botoes_cobranca(self, canal: discord.TextChannel, pagamento: Pagamento) -> None:
        if not pagamento.mensagem_id:
            return
        try:
            msg = await canal.fetch_message(pagamento.mensagem_id)
            await msg.edit(view=None)
        except Exception:
            pass

    async def _enviar_recibos_dm(self, pagamento: Pagamento, titulo: str, repasse_ok: bool) -> None:
        total = formatar_brl_centavos(pagamento.valor_total_centavos)
        valor_dev = formatar_brl_centavos(pagamento.valor_dev_centavos)

        msg_dev = (
            f'💸 **Pagamento recebido!**\n\n'
            f'O projeto **{titulo}** foi pago ({total}).\n'
            + (
                f'Seu repasse de **{valor_dev}** foi enviado via PIX para a chave '
                f'`{mascarar_chave(pagamento.pix_key)}`. 🎉'
                if repasse_ok else
                f'Seu repasse de **{valor_dev}** está em processamento — a staff foi notificada.'
            )
        )
        msg_emp = (
            f'✅ **Pagamento confirmado!**\n\n'
            f'Seu pagamento de **{total}** pelo projeto **{titulo}** foi processado.\n'
            f'O desenvolvedor recebeu o repasse automaticamente. Obrigado por usar a Freeela! 💚'
        )
        for user_id, texto in ((pagamento.dev_id, msg_dev), (pagamento.empregador_id, msg_emp)):
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(texto)
            except Exception:
                pass  # DM fechada

    async def _alertar_staff_erro_repasse(
        self,
        pagamento: Pagamento,
        canal_projeto: discord.TextChannel | None,
    ) -> None:
        embed = criar_embed_erro_repasse(
            pagamento_id=pagamento.id,
            dev_mention=f'<@{pagamento.dev_id}>',
            valor_dev_centavos=pagamento.valor_dev_centavos,
        )
        guild = canal_projeto.guild if canal_projeto else (self.bot.guilds[0] if self.bot.guilds else None)
        if not guild:
            return
        canal_log = guild.get_channel(settings.CANAL_LOG_PROJETOS)
        cargo_staff = guild.get_role(settings.CARGO_STAFF)
        mencao = cargo_staff.mention if cargo_staff else ''
        for destino in (canal_log, canal_projeto):
            if destino:
                try:
                    await destino.send(content=mencao, embed=embed)
                except Exception:
                    pass

    async def _encerrar_cobranca(self, pagamento_id: str, motivo: str) -> None:
        """Encerra uma cobrança não paga (expirada ou cancelada) e reativa o projeto."""
        pagamento = buscar_pagamento(pagamento_id)
        if not pagamento or pagamento.status != 'aguardando':
            return
        atualizar_status_pagamento(pagamento_id, motivo)

        pa = buscar_projeto_ativo(pagamento.projeto_ativo_id)
        if pa and pa.status == 'aguardando_pagamento':
            pa.status = 'ativo'
            atualizar_projeto_ativo(pa)

        canal = self.bot.get_channel(pagamento.canal_id)
        if canal:
            await self._desativar_botoes_cobranca(canal, pagamento)
            projeto = buscar_projeto(pa.projeto_id) if pa else None
            titulo = projeto.titulo if projeto else 'Projeto'
            embed = (
                criar_embed_cobranca_expirada(titulo)
                if motivo == 'expirado'
                else criar_embed_cobranca_cancelada(titulo)
            )
            try:
                await canal.send(embed=embed)
            except Exception:
                pass
        logger.info('Cobrança %s encerrada (%s)', pagamento_id, motivo)

    # ══════════════════════════════════════════════════
    #  AÇÕES DOS BOTÕES (chamadas pelas views)
    # ══════════════════════════════════════════════════

    async def verificar_pagamento_agora(self, pagamento_id: str) -> str:
        """Checagem imediata de status (botão 'Verificar Pagamento')."""
        pagamento = buscar_pagamento(pagamento_id)
        if not pagamento:
            return 'ERRO'
        if pagamento.status in ('repassado', 'repassando', 'erro_repasse'):
            return 'JA_PROCESSADO'
        if pagamento.status == 'pago':
            asyncio.create_task(self._processar_pagamento_confirmado(pagamento_id))
            return 'PAID'
        if pagamento.status in ('expirado', 'cancelado'):
            return 'EXPIRED' if pagamento.status == 'expirado' else 'CANCELLED'

        status = await checar_status_cobranca(pagamento.cobranca_id)
        if status == 'PAID':
            asyncio.create_task(self._processar_pagamento_confirmado(pagamento_id))
            return 'PAID'
        if status in ('EXPIRED', 'CANCELLED'):
            await self._encerrar_cobranca(pagamento_id, 'expirado' if status == 'EXPIRED' else 'cancelado')
        return status or 'ERRO'

    async def simular_pagamento_teste(self, pagamento_id: str) -> bool:
        """Simula o pagamento em modo de desenvolvimento (botão de teste)."""
        pagamento = buscar_pagamento(pagamento_id)
        if not pagamento or not pagamento.dev_mode or pagamento.status != 'aguardando':
            return False
        ok = await simular_pagamento(pagamento.cobranca_id)
        if ok:
            asyncio.create_task(self._processar_pagamento_confirmado(pagamento_id))
        return ok

    async def cancelar_cobranca(self, pagamento_id: str, canal: discord.TextChannel | None = None) -> None:
        task = self._poll_tasks.pop(pagamento_id, None)
        if task:
            task.cancel()
        await self._encerrar_cobranca(pagamento_id, 'cancelado')

    # ══════════════════════════════════════════════════
    #  SLASH COMMANDS
    # ══════════════════════════════════════════════════

    @app_commands.command(
        name='configurar_pagamento',
        description='Cadastre ou atualize sua chave PIX para receber pagamentos (devs)',
    )
    async def configurar_pagamento(self, interaction: discord.Interaction):
        dev = buscar_dev(interaction.user.id)
        if not dev:
            await interaction.response.send_message(
                '❌ Apenas **desenvolvedores verificados** podem configurar pagamento.\n'
                'Complete sua verificação primeiro no canal de verificação.',
                ephemeral=True,
            )
            return

        atual = ''
        if dev.pix_key:
            atual = f'\n\n🔑 Chave atual: `{mascarar_chave(dev.pix_key)}` ({dev.pix_key_type})'
        await interaction.response.send_message(
            f'💳 **Configuração de pagamento**{atual}\n\n'
            f'Selecione o **tipo** da sua chave PIX:',
            view=SelecionarTipoChaveView(),
            ephemeral=True,
        )

    @app_commands.command(
        name='receita_plataforma',
        description='[STAFF] Mostra a receita acumulada da plataforma (taxa de 15%)',
    )
    @app_commands.default_permissions(administrator=True)
    async def receita_plataforma(self, interaction: discord.Interaction):
        receita = somar_receita_plataforma()
        pagos = listar_pagamentos_por_status('repassado')
        erros = listar_pagamentos_por_status('erro_repasse')

        embed = discord.Embed(
            title='🏦  Receita da Plataforma',
            color=settings.COR_SUCESSO,
        )
        embed.add_field(
            name=f'💰  Total arrecadado ({settings.TAXA_PLATAFORMA_PERCENT:.0f}%)',
            value=f'**{formatar_brl_centavos(receita)}**',
            inline=False,
        )
        embed.add_field(name='✅  Pagamentos concluídos', value=str(len(pagos)), inline=True)
        embed.add_field(name='🚨  Repasses com erro', value=str(len(erros)), inline=True)
        if erros:
            detalhes = '\n'.join(
                f'• `{p.id}` — {formatar_brl_centavos(p.valor_dev_centavos)} para <@{p.dev_id}>'
                for p in erros[:10]
            )
            embed.add_field(name='⚠️  Pendências de repasse manual', value=detalhes, inline=False)
        embed.set_footer(text='Freeela • AbacatePay')
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PagamentosCog(bot))
    logger.info('Cog de pagamentos carregado')
