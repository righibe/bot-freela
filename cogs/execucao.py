"""
Cog de execução de projetos.
Criação automática de canais privados, conclusão, cancelamento e logs.
"""

import asyncio
import logging
import re

import discord
from discord.ext import commands
from discord import app_commands

import config.settings as settings
from config.settings import COR_EXECUCAO
from core.database import (
    Candidatura, ProjetoAtivo, buscar_projeto, buscar_projeto_ativo,
    buscar_projeto_ativo_por_candidatura,
    salvar_projeto_ativo, atualizar_projeto_ativo,
    atualizar_projetos_ativos_dev, atualizar_status_projeto,
    listar_projetos_ativos_dev, listar_projetos_ativos_por_status,
    listar_candidaturas_projeto, atualizar_candidatura,
    contar_devs, contar_empregadores, contar_projetos_por_status,
    contar_candidaturas, contar_projetos_ativos, somar_receita_plataforma,
    _gerar_id,
)
from utils.locks import guarda_acao
from embeds.execucao_embed import (
    criar_embed_projeto_criado, criar_embed_regras_projeto,
    criar_embed_alerta_dados_faltando, criar_embed_log_projeto,
    criar_embed_projeto_concluido,
)
from views.execucao_views import ExecucaoProjetoView
from utils.helpers import formatar_brl, formatar_brl_centavos

logger = logging.getLogger('bot_freeela.cogs.execucao')


class ExecucaoCog(commands.Cog):
    """Cog responsável pela execução real de projetos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Registrar views persistentes de projetos ativos
        ativos = (
            listar_projetos_ativos_por_status('ativo')
            + listar_projetos_ativos_por_status('aguardando_pagamento')
        )
        for pa in ativos:
            self.bot.add_view(ExecucaoProjetoView(projeto_ativo_id=pa.id))
        logger.info('Views persistentes registradas para %d projetos ativos', len(ativos))

    # ══════════════════════════════════════════════════
    #  CRIAÇÃO DO AMBIENTE DO PROJETO
    # ══════════════════════════════════════════════════

    async def criar_projeto_ativo(
        self,
        guild: discord.Guild,
        candidatura: Candidatura,
    ):
        """
        Cria o ambiente do projeto de forma idempotente.

        Se ambos os cliques de "Fechar Parceria" (ou um duplo-clique da parte
        que confirma por último) dispararem a criação ao mesmo tempo, apenas
        um ambiente é criado — evitando categorias/canais duplicados.
        """
        # Guarda durável: se o ambiente já foi salvo no banco, não recria.
        if buscar_projeto_ativo_por_candidatura(candidatura.id):
            logger.warning(
                'Ambiente já existe para candidatura %s — ignorando duplicata',
                candidatura.id,
            )
            return

        # Guarda em memória: impede duas execuções concorrentes antes do commit.
        with guarda_acao(('projeto_ativo', candidatura.id)) as livre:
            if not livre:
                logger.warning(
                    'Criação de ambiente já em andamento para candidatura %s',
                    candidatura.id,
                )
                return
            await self._criar_projeto_ativo_impl(guild, candidatura)

    async def _criar_projeto_ativo_impl(
        self,
        guild: discord.Guild,
        candidatura: Candidatura,
    ):
        """
        Cria o ambiente completo de execução de um projeto:
        - Categoria privada
        - Canal de texto
        - Canal de voz
        - Permissões para dev, empregador e staff
        """
        projeto = buscar_projeto(candidatura.projeto_id)
        if not projeto:
            logger.error('Projeto %s não encontrado ao criar projeto ativo', candidatura.projeto_id)
            return

        dev = guild.get_member(candidatura.dev_id)
        emp = guild.get_member(candidatura.empregador_id)

        if not dev or not emp:
            logger.error(
                'Dev (%s) ou Empregador (%s) não encontrado no servidor',
                candidatura.dev_id, candidatura.empregador_id,
            )
            return

        # Nome seguro para a categoria
        from utils.helpers import slug_canal
        categoria_nome = f'📋・{slug_canal(projeto.titulo[:30])}'

        try:
            # 1. Configurar permissões
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False,
                    connect=False,
                ),
                dev: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    connect=True,
                    speak=True,
                ),
                emp: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    connect=True,
                    speak=True,
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_messages=True,
                    connect=True,
                    speak=True,
                ),
            }

            # Adicionar staff se o cargo existir
            if settings.CARGO_STAFF:
                cargo_staff = guild.get_role(settings.CARGO_STAFF)
                if cargo_staff:
                    overwrites[cargo_staff] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                        connect=True,
                        speak=True,
                    )

            # 2. Criar categoria
            categoria = await guild.create_category(
                name=categoria_nome,
                overwrites=overwrites,
                reason=f'Projeto Freeela: {projeto.titulo}',
            )

            # 3. Criar canal de texto
            canal_texto = await categoria.create_text_channel(
                name='💬・projeto',
                topic=f'Projeto: {projeto.titulo} | Dev: {dev.name} | Empregador: {emp.name}',
            )

            # 4. Criar canal de voz
            canal_voz = await categoria.create_voice_channel(
                name='🔊・Reunião',
            )

            # 5. Salvar projeto ativo no banco
            pa = ProjetoAtivo(
                id=_gerar_id('pativo'),
                projeto_id=projeto.id,
                candidatura_id=candidatura.id,
                dev_id=candidatura.dev_id,
                empregador_id=candidatura.empregador_id,
                categoria_id=categoria.id,
                canal_texto_id=canal_texto.id,
                canal_voz_id=canal_voz.id,
                valor=projeto.valor,
                prazo=projeto.prazo_estimado,
                status='ativo',
            )
            salvar_projeto_ativo(pa)

            # Atualizar contador de projetos ativos do dev
            atualizar_projetos_ativos_dev(candidatura.dev_id, 1)

            # Atualizar status do projeto
            atualizar_status_projeto(projeto.id, 'em_andamento')

            # 6. Enviar embeds no canal de texto
            embed_criado = criar_embed_projeto_criado(
                titulo=projeto.titulo,
                dev_nome=dev.mention,
                empregador_nome=emp.mention,
                valor=projeto.valor,
                prazo=projeto.prazo_estimado,
                escopo='A ser definido — use o botão "Definir Detalhes"',
            )
            await canal_texto.send(embed=embed_criado)

            # Regras obrigatórias
            embed_regras = criar_embed_regras_projeto()
            view = ExecucaoProjetoView(projeto_ativo_id=pa.id)
            await canal_texto.send(embed=embed_regras, view=view)

            # Alerta de dados pendentes
            embed_alerta = criar_embed_alerta_dados_faltando([
                'Valor fechado',
                'Prazo de entrega',
                'Escopo do projeto',
            ])
            await canal_texto.send(embed=embed_alerta)

            # 7. Log
            await self.enviar_log_projeto(guild, pa, 'ativo', projeto.titulo)

            logger.info(
                'Projeto ativo criado: %s | cat=%d | texto=%d | voz=%d',
                pa.id, categoria.id, canal_texto.id, canal_voz.id,
            )

            # 8. LIMPEZA: remover canal de listagem + canais de negociação
            await self._limpar_canais_anteriores(
                guild=guild,
                projeto=projeto,
                candidatura=candidatura,
            )

        except discord.Forbidden:
            logger.error('Sem permissão para criar categoria/canais para projeto %s', projeto.id)
        except Exception as e:
            logger.exception('Erro ao criar projeto ativo: %s', e)

    async def _limpar_canais_anteriores(
        self,
        guild: discord.Guild,
        projeto,
        candidatura: Candidatura,
    ):
        """
        Apaga o canal de listagem (vitrine de projetos) e os canais de
        negociação após a parceria ser fechada.
        """
        await asyncio.sleep(3)  # pequena pausa para garantir embeds carregadas

        # 1. Deletar canal de listagem (vitrine de projetos disponíveis)
        canal_listagem_id = getattr(projeto, 'canal_listagem_id', 0)
        if canal_listagem_id:
            canal_listagem = guild.get_channel(canal_listagem_id)
            if canal_listagem and isinstance(canal_listagem, discord.TextChannel):
                try:
                    await canal_listagem.delete(
                        reason=f'Parceria fechada — projeto "{projeto.titulo}" removido da vitrine'
                    )
                except discord.Forbidden:
                    logger.error('Sem permissão para deletar canal de listagem %d', canal_listagem_id)
                except Exception as e:
                    logger.error('Erro ao deletar canal de listagem: %s', e)

        # 2. Cancelar e deletar TODAS as negociações do projeto (não só a fechada)
        todas_candidaturas = listar_candidaturas_projeto(projeto.id)

        for cand in todas_candidaturas:
            # Cancelar candidaturas que não são a fechada
            if cand.id != candidatura.id and cand.status == 'negociando':
                cand.status = 'cancelado'
                atualizar_candidatura(cand)

                # Notificar o dev que perdeu a vaga
                try:
                    dev_perdeu = guild.get_member(cand.dev_id)
                    if dev_perdeu:
                        await dev_perdeu.send(
                            f'❌ A negociação para o projeto **"{projeto.titulo}"** foi encerrada '
                            f'porque o empregador fechou parceria com outro desenvolvedor.\n'
                            f'Fique de olho nos próximos projetos!'
                        )
                except Exception:
                    pass  # DM bloqueada

            # Deletar o canal de negociação (de TODAS as candidaturas)
            canal_neg_id = cand.thread_id
            if canal_neg_id:
                canal_neg = guild.get_channel(canal_neg_id)
                if canal_neg:
                    try:
                        if isinstance(canal_neg, discord.Thread):
                            await canal_neg.edit(archived=True, locked=True)
                        elif isinstance(canal_neg, discord.TextChannel):
                            await canal_neg.delete(
                                reason=f'Parceria fechada para "{projeto.titulo}" — negociação encerrada'
                            )
                    except discord.Forbidden:
                        logger.error('Sem permissão para deletar canal de negociação %d', canal_neg_id)
                    except Exception as e:
                        logger.error('Erro ao deletar canal de negociação: %s', e)
                    await asyncio.sleep(0.5)  # evitar rate limit

    # ══════════════════════════════════════════════════
    #  CONCLUSÃO
    # ══════════════════════════════════════════════════

    async def finalizar_conclusao(
        self,
        guild: discord.Guild,
        projeto_ativo_id: str,
        delay_limpeza: int = 0,
    ):
        """
        Marca o projeto como concluído, envia embeds/log e arquiva os canais.
        Chamado pelo fluxo de pagamento (após repasse) ou pela conclusão manual.
        """
        pa = buscar_projeto_ativo(projeto_ativo_id)
        if not pa or pa.status == 'concluido':
            return

        pa.status = 'concluido'
        atualizar_projeto_ativo(pa)
        atualizar_projetos_ativos_dev(pa.dev_id, -1)
        atualizar_status_projeto(pa.projeto_id, 'concluido')

        projeto = buscar_projeto(pa.projeto_id)
        titulo = projeto.titulo if projeto else 'Projeto'

        canal_texto = guild.get_channel(pa.canal_texto_id)
        if canal_texto:
            try:
                embed = criar_embed_projeto_concluido(titulo)
                if delay_limpeza:
                    embed.set_footer(
                        text=f'Os canais deste projeto serão arquivados em {delay_limpeza} segundos.'
                    )
                await canal_texto.send(embed=embed)
            except Exception as e:
                logger.error('Erro ao enviar embed de conclusão: %s', e)

        await self.enviar_log_projeto(guild, pa, 'concluido', titulo)

        if delay_limpeza:
            await asyncio.sleep(delay_limpeza)

        await self._limpar_projeto(guild, pa, projeto)
        logger.info('Projeto %s concluído e arquivado', pa.id)

    # ══════════════════════════════════════════════════
    #  LIMPEZA / REPUBLICAÇÃO
    # ══════════════════════════════════════════════════

    async def _limpar_projeto(self, guild: discord.Guild, pa, projeto):
        """Remove os canais do projeto quando concluído: vitrine + categoria ativa."""
        # 1. Deletar o canal de listagem da vitrine (se ainda existir)
        canal_listagem_id = getattr(projeto, 'canal_listagem_id', 0) if projeto else 0
        if canal_listagem_id:
            canal_listagem = guild.get_channel(canal_listagem_id)
            if canal_listagem and isinstance(canal_listagem, discord.TextChannel):
                try:
                    await canal_listagem.delete(
                        reason=f'Projeto {pa.projeto_id} concluído — removido da vitrine'
                    )
                except Exception as e:
                    logger.error('Erro ao deletar canal de listagem: %s', e)

        # 2. Deletar a categoria inteira do projeto ativo
        await self.deletar_categoria_projeto(guild, pa)

    async def deletar_categoria_projeto(self, guild: discord.Guild, pa):
        """Deleta todos os canais da categoria do projeto ativo e a categoria."""
        if not pa.categoria_id:
            return
        categoria = guild.get_channel(pa.categoria_id)
        if not categoria or not isinstance(categoria, discord.CategoryChannel):
            logger.warning('Categoria %d não encontrada ou já deletada', pa.categoria_id)
            return

        for canal in list(categoria.channels):
            try:
                await canal.delete(reason=f'Projeto {pa.projeto_id} encerrado')
            except discord.Forbidden:
                logger.error('Sem permissão para deletar canal %d', canal.id)
            except Exception as e:
                logger.error('Erro ao deletar canal %d: %s', canal.id, e)
            await asyncio.sleep(0.5)  # evitar rate limit

        try:
            await categoria.delete(reason=f'Projeto {pa.projeto_id} encerrado')
        except Exception as e:
            logger.error('Erro ao deletar categoria: %s', e)

    async def republicar_projeto_na_vitrine(self, guild: discord.Guild, projeto):
        """Republica um projeto cancelado na vitrine de Projetos Disponíveis."""
        if not projeto:
            return
        categoria_projetos = guild.get_channel(settings.CATEGORIA_PROJETOS_ID)
        if not categoria_projetos or not isinstance(categoria_projetos, discord.CategoryChannel):
            logger.warning('Categoria de projetos não encontrada — projeto %s não republicado', projeto.id)
            return

        try:
            from utils.helpers import nome_canal_projeto
            nome_canal = nome_canal_projeto(projeto.categoria, projeto.titulo)
            canal_projeto = await guild.create_text_channel(nome_canal, category=categoria_projetos)

            from dataclasses import asdict
            from embeds.projeto_embed import criar_embed_projeto_listagem
            from views.projeto_views import ProjetoInteresseView

            embed = criar_embed_projeto_listagem(asdict(projeto))
            view = ProjetoInteresseView(projeto_id=projeto.id)

            from core.tecnologias import mapa_cargos
            cargos_tec = mapa_cargos()
            pings = []
            for lang in projeto.linguagens_requeridas:
                cargo_id = cargos_tec.get(lang)
                if cargo_id:
                    cargo = guild.get_role(cargo_id)
                    if cargo:
                        pings.append(cargo.mention)
            content = (
                f"{' '.join(pings)} 🔄 Projeto **reaberto**: procurando dev com "
                f"**{', '.join(projeto.linguagens_requeridas)}**!"
                if pings else ''
            )

            msg = await canal_projeto.send(content=content, embed=embed, view=view)
            from core.database import salvar_projeto
            projeto.message_id = msg.id
            projeto.canal_listagem_id = canal_projeto.id
            salvar_projeto(projeto)
            logger.info('Projeto %s republicado na vitrine (canal %d)', projeto.id, canal_projeto.id)
        except Exception as e:
            logger.exception('Erro ao republicar projeto %s: %s', projeto.id, e)

    # ══════════════════════════════════════════════════
    #  LOG
    # ══════════════════════════════════════════════════

    async def enviar_log_projeto(
        self,
        guild: discord.Guild,
        pa,
        status: str,
        titulo: str,
    ):
        """Envia log do projeto para o canal de logs."""
        canal_log = guild.get_channel(settings.CANAL_LOG_PROJETOS)
        if not canal_log:
            return

        dev = guild.get_member(pa.dev_id)
        emp = guild.get_member(pa.empregador_id)

        embed = criar_embed_log_projeto(
            projeto_id=pa.id,
            titulo=titulo,
            dev_id=pa.dev_id,
            dev_nome=dev.name if dev else str(pa.dev_id),
            empregador_id=pa.empregador_id,
            empregador_nome=emp.name if emp else str(pa.empregador_id),
            valor=pa.valor,
            prazo=pa.prazo,
            status=status,
        )
        try:
            await canal_log.send(embed=embed)
        except Exception as e:
            logger.error('Erro ao enviar log de projeto: %s', e)

    # ══════════════════════════════════════════════════
    #  SLASH COMMANDS
    # ══════════════════════════════════════════════════

    @app_commands.command(
        name='meus_projetos',
        description='Lista seus projetos ativos',
    )
    async def meus_projetos(self, interaction: discord.Interaction):
        projetos = listar_projetos_ativos_dev(interaction.user.id)

        if not projetos:
            await interaction.response.send_message(
                '📭 Você não tem projetos ativos no momento.',
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title='📋  Seus Projetos Ativos',
            description=f'Você tem **{len(projetos)}** projeto(s) ativo(s):',
            color=COR_EXECUCAO,
        )

        status_labels = {
            'ativo': '🟢 Em andamento',
            'aguardando_pagamento': '💳 Aguardando pagamento',
        }
        for pa in projetos:
            projeto = buscar_projeto(pa.projeto_id)
            titulo = projeto.titulo if projeto else 'Projeto desconhecido'
            canal = interaction.guild.get_channel(pa.canal_texto_id)
            canal_mention = canal.mention if canal else 'Canal não encontrado'

            embed.add_field(
                name=titulo,
                value=(
                    f'💰 {formatar_brl(pa.valor)}\n'
                    f'⏰ {pa.prazo or "N/A"}\n'
                    f'💬 {canal_mention}\n'
                    f'📌 {status_labels.get(pa.status, pa.status)}'
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name='status_plataforma',
        description='[STAFF] Mostra o status geral da plataforma Freeela',
    )
    @app_commands.default_permissions(administrator=True)
    async def status_plataforma(self, interaction: discord.Interaction):
        projetos_status = contar_projetos_por_status()
        cands_ativas, cands_total = contar_candidaturas()

        embed = discord.Embed(
            title='📊  Status da Plataforma Freeela',
            color=COR_EXECUCAO,
        )
        embed.add_field(
            name='👨‍💻  Devs Verificados',
            value=f'**{contar_devs()}**',
            inline=True,
        )
        embed.add_field(
            name='🏢  Empregadores',
            value=f'**{contar_empregadores()}**',
            inline=True,
        )
        embed.add_field(
            name='🏦  Receita da Plataforma',
            value=f'**{formatar_brl_centavos(somar_receita_plataforma())}**',
            inline=True,
        )
        embed.add_field(
            name='📂  Projetos',
            value=(
                f'🟢 Abertos: **{projetos_status.get("aberto", 0)}**\n'
                f'🔵 Em andamento: **{projetos_status.get("em_andamento", 0)}**\n'
                f'✅ Concluídos: **{projetos_status.get("concluido", 0)}**\n'
                f'📋 Total: **{sum(projetos_status.values())}**'
            ),
            inline=True,
        )
        embed.add_field(
            name='🤝  Candidaturas',
            value=(
                f'💬 Negociando: **{cands_ativas}**\n'
                f'📋 Total: **{cands_total}**'
            ),
            inline=True,
        )
        embed.add_field(
            name='🏗️  Projetos Ativos',
            value=(
                f'**{contar_projetos_ativos("ativo")}** em execução\n'
                f'**{contar_projetos_ativos("aguardando_pagamento")}** aguardando pagamento'
            ),
            inline=True,
        )
        embed.add_field(
            name='🤖  Bot',
            value=f'Latência: `{round(self.bot.latency * 1000)}ms`',
            inline=True,
        )
        embed.add_field(
            name='📡  API',
            value=f'`http://{settings.API_HOST}:{settings.API_PORT}`',
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ExecucaoCog(bot))
    logger.info('Cog de execução carregado')
