"""
Cog de sincronização Discord ↔ banco de dados.

O banco segue o servidor mesmo quando a staff mexe manualmente nos canais:
- canal de vitrine apagado      → projeto cancelado, negociações encerradas
- canal de negociação apagado   → candidatura cancelada, dev liberado
- ambiente de projeto apagado   → projeto encerrado, contadores corrigidos
- canal de ticket apagado       → ticket fechado
- membro saiu/expulso           → candidaturas e projetos dele são encerrados

Todos os handlers são idempotentes: quando o próprio bot apaga um canal como
parte do fluxo normal, o status no banco já mudou antes da exclusão e nada é
refeito. No startup, uma varredura completa reconcilia o que aconteceu com o
bot offline (canais apagados, membros que saíram) e recalcula os contadores.
"""

import asyncio
import logging

import discord
from discord.ext import commands

import config.settings as settings
from core.database import (
    buscar_projeto, buscar_projeto_por_canal_listagem,
    atualizar_status_projeto, remover_candidato_projeto,
    listar_projetos, listar_projetos_empregador,
    buscar_candidatura_por_thread, atualizar_candidatura,
    listar_candidaturas_projeto, listar_candidaturas_por_status,
    listar_candidaturas_dev_por_status,
    buscar_projeto_ativo_por_ambiente, atualizar_projeto_ativo,
    atualizar_projetos_ativos_dev, listar_projetos_ativos_por_status,
    listar_projetos_ativos_dev, listar_projetos_ativos_empregador,
    buscar_pagamento_pendente_projeto, atualizar_status_pagamento,
    buscar_ticket_por_canal, fechar_ticket, listar_tickets_por_status,
    recalcular_projetos_ativos_devs,
)

logger = logging.getLogger('bot_freeela.cogs.sincronizacao')

STATUS_PA_VIVOS = ('ativo', 'aguardando_pagamento')


class SincronizacaoCog(commands.Cog):
    """Mantém o banco consistente com exclusões manuais feitas no Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._varredura_feita = False

    # ══════════════════════════════════════════════════
    #  UTILITÁRIOS
    # ══════════════════════════════════════════════════

    async def _dm(self, guild: discord.Guild, user_id: int, texto: str):
        """Tenta avisar um usuário por DM (silencioso se bloqueada)."""
        membro = guild.get_member(user_id)
        if not membro:
            return
        try:
            await membro.send(texto)
        except Exception:
            pass

    async def _log(self, guild: discord.Guild, texto: str):
        canal = guild.get_channel(settings.CANAL_LOG_PROJETOS)
        if canal:
            try:
                await canal.send(texto)
            except Exception:
                pass

    async def _deletar_canal(self, guild: discord.Guild, canal_id: int, motivo: str):
        """Apaga um canal/thread se ele ainda existir."""
        if not canal_id:
            return
        canal = guild.get_channel(canal_id) or guild.get_thread(canal_id)
        if not canal:
            return
        try:
            await canal.delete(reason=motivo)
        except Exception as e:
            logger.error('Erro ao apagar canal %d durante sincronização: %s', canal_id, e)
        await asyncio.sleep(0.5)  # evitar rate limit

    def _canal_existe(self, guild: discord.Guild, canal_id: int) -> bool:
        if not canal_id:
            return False
        return guild.get_channel_or_thread(canal_id) is not None

    # ══════════════════════════════════════════════════
    #  ENCERRAMENTOS (idempotentes)
    # ══════════════════════════════════════════════════

    async def encerrar_projeto_aberto(
        self,
        guild: discord.Guild,
        projeto,
        motivo: str,
        apagar_vitrine: bool = False,
    ):
        """
        Cancela um projeto ainda aberto: encerra todas as negociações,
        apaga os canais de negociação e avisa os devs candidatos.
        """
        if projeto.status not in ('aberto', 'pendente'):
            return
        atualizar_status_projeto(projeto.id, 'cancelado')

        for cand in listar_candidaturas_projeto(projeto.id):
            if cand.status != 'negociando':
                continue
            cand.status = 'cancelado'
            atualizar_candidatura(cand)
            await self._deletar_canal(
                guild, cand.thread_id,
                f'Projeto "{projeto.titulo}" removido — negociação encerrada',
            )
            await self._dm(
                guild, cand.dev_id,
                f'ℹ️ O projeto **"{projeto.titulo}"** foi removido da plataforma '
                f'e sua negociação foi encerrada. Fique de olho nos próximos freelas!',
            )

        if apagar_vitrine:
            await self._deletar_canal(
                guild, projeto.canal_listagem_id,
                f'Projeto "{projeto.titulo}" cancelado',
            )

        await self._log(
            guild,
            f'🧹 **Projeto cancelado (sincronização):** "{projeto.titulo}" (`{projeto.id}`) — {motivo}',
        )
        logger.info('Projeto %s cancelado via sincronização: %s', projeto.id, motivo)

    async def encerrar_candidatura(
        self,
        guild: discord.Guild,
        cand,
        motivo: str,
        apagar_canal: bool = False,
        avisar_dev: bool = True,
    ):
        """
        Cancela uma negociação e libera o dev para se candidatar de novo
        ao mesmo projeto.
        """
        if cand.status != 'negociando':
            return
        cand.status = 'cancelado'
        atualizar_candidatura(cand)
        remover_candidato_projeto(cand.projeto_id, cand.dev_id)

        if apagar_canal:
            await self._deletar_canal(guild, cand.thread_id, motivo)

        projeto = buscar_projeto(cand.projeto_id)
        titulo = projeto.titulo if projeto else cand.projeto_id
        if avisar_dev:
            await self._dm(
                guild, cand.dev_id,
                f'ℹ️ Sua negociação no projeto **"{titulo}"** foi encerrada ({motivo}). '
                f'Se o projeto continuar disponível, você pode se candidatar novamente.',
            )
        await self._log(
            guild,
            f'🧹 **Negociação encerrada (sincronização):** dev <@{cand.dev_id}> '
            f'no projeto "{titulo}" — {motivo}',
        )
        logger.info('Candidatura %s cancelada via sincronização: %s', cand.id, motivo)

    async def encerrar_projeto_ativo(
        self,
        guild: discord.Guild,
        pa,
        motivo: str,
        apagar_ambiente: bool = True,
    ):
        """
        Encerra um projeto em execução cujo ambiente foi removido manualmente:
        cancela cobrança pendente, corrige o contador do dev e apaga o que
        sobrou do ambiente (categoria/canais restantes).
        """
        if pa.status not in STATUS_PA_VIVOS:
            return

        # Cobrança PIX em aberto não pode ficar órfã
        pagamento = buscar_pagamento_pendente_projeto(pa.id)
        if pagamento:
            atualizar_status_pagamento(pagamento.id, 'cancelado')
            logger.warning(
                'Cobrança %s cancelada — ambiente do projeto %s removido manualmente',
                pagamento.id, pa.id,
            )

        pa.status = 'cancelado'
        atualizar_projeto_ativo(pa)
        atualizar_projetos_ativos_dev(pa.dev_id, -1)
        atualizar_status_projeto(pa.projeto_id, 'cancelado')

        projeto = buscar_projeto(pa.projeto_id)
        titulo = projeto.titulo if projeto else pa.projeto_id

        if apagar_ambiente:
            categoria = guild.get_channel(pa.categoria_id)
            if categoria and isinstance(categoria, discord.CategoryChannel):
                for canal in list(categoria.channels):
                    await self._deletar_canal(guild, canal.id, f'Projeto "{titulo}" encerrado')
                await self._deletar_canal(guild, categoria.id, f'Projeto "{titulo}" encerrado')
            else:
                for canal_id in (pa.canal_texto_id, pa.canal_voz_id):
                    await self._deletar_canal(guild, canal_id, f'Projeto "{titulo}" encerrado')
            # Vitrine antiga, se ainda existir
            if projeto:
                await self._deletar_canal(
                    guild, projeto.canal_listagem_id, f'Projeto "{titulo}" encerrado',
                )

        aviso = (
            f'⚠️ O ambiente do projeto **"{titulo}"** foi removido ({motivo}) '
            f'e o projeto foi **encerrado**. Se isso não deveria ter acontecido, '
            f'abra um ticket com a staff.'
        )
        await self._dm(guild, pa.dev_id, aviso)
        await self._dm(guild, pa.empregador_id, aviso)
        await self._log(
            guild,
            f'🧹 **Projeto ativo encerrado (sincronização):** "{titulo}" (`{pa.id}`) — {motivo}. '
            f'Dev: <@{pa.dev_id}> | Empregador: <@{pa.empregador_id}>'
            + (' | ⚠️ havia cobrança PIX em aberto (cancelada)' if pagamento else ''),
        )
        logger.info('Projeto ativo %s encerrado via sincronização: %s', pa.id, motivo)

    # ══════════════════════════════════════════════════
    #  EVENTOS
    # ══════════════════════════════════════════════════

    async def _processar_exclusao_canal(self, guild: discord.Guild, canal_id: int):
        """Reconcilia o banco após a exclusão de um canal/thread qualquer."""
        # 1. Vitrine de projeto (Projetos Disponíveis)
        projeto = buscar_projeto_por_canal_listagem(canal_id)
        if projeto and projeto.status in ('aberto', 'pendente'):
            await self.encerrar_projeto_aberto(
                guild, projeto, motivo='canal da vitrine apagado manualmente',
            )
            return

        # 2. Canal de negociação
        cand = buscar_candidatura_por_thread(canal_id)
        if cand and cand.status == 'negociando':
            await self.encerrar_candidatura(
                guild, cand, motivo='canal de negociação apagado manualmente',
            )
            return

        # 3. Ambiente de projeto ativo (texto, voz ou categoria)
        pa = buscar_projeto_ativo_por_ambiente(canal_id)
        if pa and pa.status in STATUS_PA_VIVOS:
            await self.encerrar_projeto_ativo(
                guild, pa, motivo='canal do projeto apagado manualmente',
            )
            return

        # 4. Ticket de suporte
        ticket = buscar_ticket_por_canal(canal_id)
        if ticket and ticket.status == 'aberto':
            fechar_ticket(canal_id)
            logger.info('Ticket %s fechado — canal apagado manualmente', ticket.id)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        try:
            await self._processar_exclusao_canal(channel.guild, channel.id)
        except Exception as e:
            logger.exception('Erro ao sincronizar exclusão do canal %d: %s', channel.id, e)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        try:
            await self._processar_exclusao_canal(thread.guild, thread.id)
        except Exception as e:
            logger.exception('Erro ao sincronizar exclusão da thread %d: %s', thread.id, e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Membro saiu/expulso: encerra o que ele tinha em aberto."""
        guild = member.guild
        try:
            # Negociações em que era o dev
            for cand in listar_candidaturas_dev_por_status(member.id, 'negociando'):
                await self.encerrar_candidatura(
                    guild, cand,
                    motivo=f'o dev {member.name} saiu do servidor',
                    apagar_canal=True,
                    avisar_dev=False,
                )

            # Projetos abertos em que era o empregador
            for status in ('aberto', 'pendente'):
                for projeto in listar_projetos_empregador(member.id, status):
                    await self.encerrar_projeto_aberto(
                        guild, projeto,
                        motivo=f'o empregador {member.name} saiu do servidor',
                        apagar_vitrine=True,
                    )

            # Projetos em execução: não encerra sozinho (pode haver pagamento
            # em jogo) — alerta o canal do projeto e a staff decidirem.
            envolvidos = (
                listar_projetos_ativos_dev(member.id)
                + listar_projetos_ativos_empregador(member.id)
            )
            for pa in envolvidos:
                canal = guild.get_channel(pa.canal_texto_id)
                if not canal:
                    continue
                cargo_staff = guild.get_role(settings.CARGO_STAFF)
                papel = 'desenvolvedor' if member.id == pa.dev_id else 'empregador'
                try:
                    await canal.send(
                        f'🚨 {cargo_staff.mention if cargo_staff else "@staff"} '
                        f'O **{papel}** deste projeto (`{member.name}`) **saiu do servidor**. '
                        f'Use os botões acima para cancelar ou acionem a staff para resolver.'
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.exception('Erro ao sincronizar saída de %s: %s', member.name, e)

    # ══════════════════════════════════════════════════
    #  VARREDURA DE STARTUP
    # ══════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_ready(self):
        if self._varredura_feita or not self.bot.guilds:
            return
        self._varredura_feita = True
        try:
            await self.varrer_estado(self.bot.guilds[0])
        except Exception as e:
            logger.exception('Erro na varredura de sincronização: %s', e)

    async def varrer_estado(self, guild: discord.Guild):
        """Reconcilia tudo o que mudou enquanto o bot esteve offline."""
        logger.info('Iniciando varredura de sincronização Discord ↔ banco...')
        acoes = 0

        # Projetos abertos: vitrine sumiu ou empregador saiu
        for projeto in listar_projetos('aberto') + listar_projetos('pendente'):
            if not guild.get_member(projeto.empregador_id):
                await self.encerrar_projeto_aberto(
                    guild, projeto,
                    motivo='o empregador não está mais no servidor',
                    apagar_vitrine=True,
                )
                acoes += 1
            elif projeto.canal_listagem_id and not self._canal_existe(guild, projeto.canal_listagem_id):
                await self.encerrar_projeto_aberto(
                    guild, projeto, motivo='canal da vitrine não existe mais',
                )
                acoes += 1

        # Negociações: canal sumiu ou dev saiu
        for cand in listar_candidaturas_por_status('negociando'):
            if not guild.get_member(cand.dev_id):
                await self.encerrar_candidatura(
                    guild, cand, motivo='o dev não está mais no servidor',
                    apagar_canal=True, avisar_dev=False,
                )
                acoes += 1
            elif cand.thread_id and not self._canal_existe(guild, cand.thread_id):
                # Projeto pode ter sido cancelado no bloco acima — revalida
                cand_atual = buscar_candidatura_por_thread(cand.thread_id)
                if cand_atual and cand_atual.status == 'negociando':
                    await self.encerrar_candidatura(
                        guild, cand_atual, motivo='canal de negociação não existe mais',
                    )
                    acoes += 1

        # Projetos em execução: canal de texto sumiu
        for status in STATUS_PA_VIVOS:
            for pa in listar_projetos_ativos_por_status(status):
                if pa.canal_texto_id and not self._canal_existe(guild, pa.canal_texto_id):
                    await self.encerrar_projeto_ativo(
                        guild, pa, motivo='canais do projeto não existem mais',
                    )
                    acoes += 1

        # Tickets abertos sem canal
        for ticket in listar_tickets_por_status('aberto'):
            if ticket.canal_id and not self._canal_existe(guild, ticket.canal_id):
                fechar_ticket(ticket.canal_id)
                acoes += 1

        # Contadores de projetos ativos dos devs (fonte da verdade: tabela)
        corrigidos = recalcular_projetos_ativos_devs()
        acoes += corrigidos

        logger.info(
            'Varredura de sincronização concluída: %d correções aplicadas', acoes,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SincronizacaoCog(bot))
    logger.info('Cog de sincronização carregado')
