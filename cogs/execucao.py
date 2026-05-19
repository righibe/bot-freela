"""
Cog de execução de projetos.
Criação automática de canais privados, gerenciamento e logs.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands
from config.settings import (
    COR_EXECUCAO, COR_ALERTA, COR_SUCESSO,
    CARGO_STAFF, CANAL_LOG_PROJETOS,
)
from core.database import (
    Candidatura, ProjetoAtivo, buscar_projeto, buscar_dev,
    buscar_empregador, salvar_projeto_ativo,
    atualizar_projetos_ativos_dev, atualizar_status_projeto,
    buscar_projeto_ativo_por_canal, listar_projetos_ativos_dev,
    _gerar_id,
)
from embeds.execucao_embed import (
    criar_embed_projeto_criado, criar_embed_regras_projeto,
    criar_embed_alerta_dados_faltando, criar_embed_log_projeto,
)
from views.execucao_views import ExecucaoProjetoView

logger = logging.getLogger('bot_freeela.cogs.execucao')


class ExecucaoCog(commands.Cog):
    """Cog responsável pela execução real de projetos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Registrar views persistentes de projetos ativos
        from core.database import _carregar_json, PROJETOS_ATIVOS_FILE
        dados = _carregar_json(PROJETOS_ATIVOS_FILE)
        count = 0
        for d in dados:
            if d.get('status') == 'ativo':
                pa_id = d.get('id', '')
                self.bot.add_view(ExecucaoProjetoView(projeto_ativo_id=pa_id))
                count += 1
        logger.info(
            'Views persistentes registradas para %d projetos ativos',
            count,
        )

    async def criar_projeto_ativo(
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
        nome_projeto = projeto.titulo[:30].replace(' ', '-').lower()
        categoria_nome = f'📋 {nome_projeto}'

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
            if CARGO_STAFF:
                cargo_staff = guild.get_role(CARGO_STAFF)
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
                name='💬-projeto',
                topic=f'Projeto: {projeto.titulo} | Dev: {dev.name} | Empregador: {emp.name}',
            )

            # 4. Criar canal de voz
            canal_voz = await categoria.create_voice_channel(
                name='🔊 Reunião',
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
            if CANAL_LOG_PROJETOS:
                canal_log = guild.get_channel(CANAL_LOG_PROJETOS)
                if canal_log:
                    embed_log = criar_embed_log_projeto(
                        projeto_id=pa.id,
                        titulo=projeto.titulo,
                        dev_id=dev.id,
                        dev_nome=dev.name,
                        empregador_id=emp.id,
                        empregador_nome=emp.name,
                        valor=projeto.valor,
                        prazo=projeto.prazo_estimado,
                        status='ativo',
                    )
                    await canal_log.send(embed=embed_log)

            logger.info(
                'Projeto ativo criado: %s | cat=%d | texto=%d | voz=%d',
                pa.id, categoria.id, canal_texto.id, canal_voz.id,
            )

            # ──────────────────────────────────────────────────────
            # 8. LIMPEZA: remover canal de listagem + canal de negociação
            # Feito APÓS toda a categoria ativa estar pronta.
            # ──────────────────────────────────────────────────────
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
        Apaga o canal de listagem (vitrine de projetos) e o canal de
        negociação após a parceria ser fechada.
        """
        import asyncio
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
                    logger.info(
                        'Canal de listagem %d deletado (projeto %s)',
                        canal_listagem_id, projeto.id,
                    )
                except discord.Forbidden:
                    logger.error(
                        'Sem permissão para deletar canal de listagem %d', canal_listagem_id
                    )
                except Exception as e:
                    logger.error('Erro ao deletar canal de listagem: %s', e)
            else:
                logger.warning(
                    'Canal de listagem %d não encontrado ou já deletado', canal_listagem_id
                )
        else:
            logger.info(
                'Projeto %s não tem canal_listagem_id salvo — pulando limpeza da vitrine',
                projeto.id,
            )

        # 2. Cancelar e deletar TODAS as negociações do projeto (não só a fechada)
        from core.database import listar_candidaturas_projeto, atualizar_candidatura
        todas_candidaturas = listar_candidaturas_projeto(projeto.id)

        for cand in todas_candidaturas:
            # Cancelar candidaturas que não são a fechada
            if cand.id != candidatura.id and cand.status == 'negociando':
                cand.status = 'cancelado'
                atualizar_candidatura(cand)
                logger.info(
                    'Candidatura %s cancelada automaticamente (parceria fechada com outro dev)',
                    cand.id,
                )

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
                            logger.info(
                                'Thread de negociação %d arquivada (cand %s)',
                                canal_neg_id, cand.id,
                            )
                        elif isinstance(canal_neg, discord.TextChannel):
                            await canal_neg.delete(
                                reason=f'Parceria fechada para "{projeto.titulo}" — negociação encerrada'
                            )
                            logger.info(
                                'Canal de negociação %d deletado (cand %s)',
                                canal_neg_id, cand.id,
                            )
                    except discord.Forbidden:
                        logger.error('Sem permissão para deletar canal de negociação %d', canal_neg_id)
                    except Exception as e:
                        logger.error('Erro ao deletar canal de negociação: %s', e)
                    await asyncio.sleep(0.5)  # evitar rate limit

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

        for pa in projetos:
            projeto = buscar_projeto(pa.projeto_id)
            titulo = projeto.titulo if projeto else 'Projeto desconhecido'
            canal = interaction.guild.get_channel(pa.canal_texto_id)
            canal_mention = canal.mention if canal else 'Canal não encontrado'

            embed.add_field(
                name=titulo,
                value=(
                    f'💰 R$ {pa.valor:,.2f}\n'
                    f'⏰ {pa.prazo or "N/A"}\n'
                    f'💬 {canal_mention}\n'
                    f'📌 `{pa.status}`'
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
        from core.database import (
            _carregar_json, DEVS_FILE, EMPREGADORES_FILE,
            PROJETOS_FILE, CANDIDATURAS_FILE, PROJETOS_ATIVOS_FILE,
        )

        devs = _carregar_json(DEVS_FILE)
        emps = _carregar_json(EMPREGADORES_FILE)
        projs = _carregar_json(PROJETOS_FILE)
        cands = _carregar_json(CANDIDATURAS_FILE)
        ativos = _carregar_json(PROJETOS_ATIVOS_FILE)

        proj_abertos = len([p for p in projs if p.get('status') == 'aberto'])
        proj_andamento = len([p for p in projs if p.get('status') == 'em_andamento'])
        proj_concluidos = len([p for p in projs if p.get('status') == 'concluido'])
        cands_ativas = len([c for c in cands if c.get('status') == 'negociando'])
        ativos_count = len([a for a in ativos if a.get('status') == 'ativo'])

        embed = discord.Embed(
            title='📊  Status da Plataforma Freeela',
            color=COR_EXECUCAO,
        )
        embed.add_field(
            name='👨‍💻  Devs Verificados',
            value=f'**{len(devs)}**',
            inline=True,
        )
        embed.add_field(
            name='🏢  Empregadores',
            value=f'**{len(emps)}**',
            inline=True,
        )
        embed.add_field(name='\u200b', value='\u200b', inline=True)
        embed.add_field(
            name='📂  Projetos',
            value=(
                f'🟢 Abertos: **{proj_abertos}**\n'
                f'🔵 Em andamento: **{proj_andamento}**\n'
                f'✅ Concluídos: **{proj_concluidos}**\n'
                f'📋 Total: **{len(projs)}**'
            ),
            inline=True,
        )
        embed.add_field(
            name='🤝  Candidaturas',
            value=(
                f'💬 Negociando: **{cands_ativas}**\n'
                f'📋 Total: **{len(cands)}**'
            ),
            inline=True,
        )
        embed.add_field(
            name='🏗️  Projetos Ativos',
            value=f'**{ativos_count}**',
            inline=True,
        )
        embed.add_field(
            name='🤖  Bot',
            value=f'Latência: `{round(self.bot.latency * 1000)}ms`',
            inline=True,
        )
        embed.add_field(
            name='📡  API',
            value=f'`http://127.0.0.1:8000`',
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ExecucaoCog(bot))
    logger.info('Cog de execução carregado')
