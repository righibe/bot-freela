"""
Views para listagem de projetos.
Botão "Tenho Interesse" aberto para desenvolvedores verificados, sem bloquear por senioridade ou número de stacks.
"""

import logging
import discord
from discord.ui import View, Button
from dataclasses import asdict
from config.settings import COR_ERRO, COR_MATCHING, COR_ALERTA
from core.database import (
    buscar_projeto, buscar_dev, Candidatura, salvar_candidatura,
    adicionar_candidato_projeto, registrar_cooldown, _gerar_id,
)
from core.protection import verificar_candidatura_permitida
from embeds.projeto_embed import criar_embed_interesse_enviado, criar_embed_negociacao
from utils.locks import guarda_acao

logger = logging.getLogger('bot_freeela.views.projeto')


class ProjetoInteresseView(View):
    """View com o botão 'Tenho Interesse' nos projetos listados."""

    def __init__(self, projeto_id: str):
        super().__init__(timeout=None)
        self.projeto_id = projeto_id

        btn = Button(
            label='🤝  Tenho Interesse',
            style=discord.ButtonStyle.success,
            custom_id=f'btn_interesse_{projeto_id}',
        )
        btn.callback = self.callback_interesse
        self.add_item(btn)

    async def callback_interesse(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.response.send_message('❌ Erro interno.', ephemeral=True)
            return

        # Aceite dos Termos de Uso é obrigatório antes de se candidatar
        from views.termos_views import exigir_aceite_termos
        if not await exigir_aceite_termos(interaction):
            return

        # 1. Verificar se é dev verificado
        # Fallback: se tem o cargo mas não está no banco (verificado antes do
        # sistema atual), reconstrói o registro a partir dos cargos de linguagem.
        dev = buscar_dev(user.id)
        if not dev:
            from config.settings import get_cargo_dev_verificado
            from core.tecnologias import mapa_cargos
            cargo_dev = get_cargo_dev_verificado(guild)
            if cargo_dev and cargo_dev in user.roles:
                from core.database import DevVerificado, salvar_dev
                linguagens_confirmadas = []
                for lang, cargo_id in mapa_cargos().items():
                    cargo_lang = guild.get_role(cargo_id)
                    if cargo_lang and cargo_lang in user.roles:
                        linguagens_confirmadas.append(lang)
                if linguagens_confirmadas:
                    dev = DevVerificado(
                        user_id=user.id,
                        username=user.name,
                        linguagens_confirmadas=linguagens_confirmadas,
                        experiencia='qualquer',
                        senioridade='Não determinado',
                        area='Não determinado',
                        compatibilidade=70,
                        integridade=70,
                    )
                    salvar_dev(dev)

        if not dev:
            await interaction.response.send_message(
                '❌ Você precisa ser um **Desenvolvedor Verificado** para se candidatar.\n'
                'Acesse o canal de verificação para se verificar primeiro.',
                ephemeral=True,
            )
            return

        # 2. Verificar proteção (cooldown, limites)
        protecao = verificar_candidatura_permitida(user.id)
        if not protecao.permitido:
            await interaction.response.send_message(
                '❌ **Candidatura bloqueada:**\n' +
                '\n'.join(f'• {m}' for m in protecao.motivos),
                ephemeral=True,
            )
            return

        # 3. Buscar projeto
        projeto = buscar_projeto(self.projeto_id)
        if not projeto:
            await interaction.response.send_message(
                '❌ Projeto não encontrado ou já foi removido.',
                ephemeral=True,
            )
            return

        if projeto.status != 'aberto':
            await interaction.response.send_message(
                '❌ Este projeto não está mais aberto para candidaturas.',
                ephemeral=True,
            )
            return

        # 4. Verificar se já é candidato
        if user.id in projeto.candidatos:
            await interaction.response.send_message(
                '⚠️ Você já se candidatou a este projeto.',
                ephemeral=True,
            )
            return

        # 5. Verificar se é o próprio empregador
        if user.id == projeto.empregador_id:
            await interaction.response.send_message(
                '❌ Você não pode se candidatar ao próprio projeto.',
                ephemeral=True,
            )
            return

        # 6. Match obrigatório: o projeto é visível para todos, mas só quem é
        # compatível (stack + experiência + disponibilidade) pode se candidatar.
        from core.matching_engine import verificar_compatibilidade_dev_projeto
        compat = verificar_compatibilidade_dev_projeto(dev, projeto)
        if not compat['compativel']:
            embed_nomatch = discord.Embed(
                title='🔒  Você ainda não dá match com este projeto',
                description=(
                    'Este projeto exige um perfil compatível para candidatura:\n\n'
                    + '\n'.join(f'• {m}' for m in compat['motivos_rejeicao'])
                ),
                color=COR_ALERTA,
            )
            if compat['linguagens_match']:
                embed_nomatch.add_field(
                    name='✅  Você tem',
                    value=', '.join(f'`{l}`' for l in compat['linguagens_match']),
                    inline=True,
                )
            if compat['linguagens_faltando']:
                embed_nomatch.add_field(
                    name='❌  Falta',
                    value=', '.join(f'`{l}`' for l in compat['linguagens_faltando']),
                    inline=True,
                )
            embed_nomatch.set_footer(
                text='Aprendeu uma stack nova? Atualize seu perfil no canal 🔄・atualizar-perfil!'
            )
            await interaction.response.send_message(embed=embed_nomatch, ephemeral=True)
            return

        # 7. Tudo OK — criar canal de negociação
        # Trava de idempotência: impede que um duplo-clique crie dois canais
        # de negociação para o mesmo dev no mesmo projeto.
        with guarda_acao(('interesse', user.id, self.projeto_id)) as livre:
            if not livre:
                await interaction.response.send_message(
                    '⏳ Sua candidatura já está sendo processada. Aguarde um instante...',
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            try:
                # Obter a categoria Negociação
                from config.settings import CATEGORIA_NEGOCIACAO_ID
                cat_negociacao = guild.get_channel(CATEGORIA_NEGOCIACAO_ID)

                if not cat_negociacao or not isinstance(cat_negociacao, discord.CategoryChannel):
                    await interaction.followup.send(
                        '❌ Categoria de negociação não encontrada. Contate a staff.',
                        ephemeral=True
                    )
                    return

                # Revalidar candidatura dentro da trava: se um clique anterior
                # já registrou o dev, não cria um segundo canal.
                projeto_atual = buscar_projeto(self.projeto_id)
                if projeto_atual and user.id in projeto_atual.candidatos:
                    await interaction.followup.send(
                        '⚠️ Você já se candidatou a este projeto.',
                        ephemeral=True,
                    )
                    return

                empregador = guild.get_member(projeto.empregador_id)
                empregador_nome = empregador.display_name if empregador else projeto.empregador_nome

                from utils.helpers import nome_canal as montar_nome_canal
                nome_canal = montar_nome_canal('🤝', f'negoc-{user.name}-{projeto.titulo[:10]}')

                # Definir permissões: apenas Dev, Empregador e bot podem ver
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
                }
                if empregador:
                    overwrites[empregador] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

                # Criar canal de texto na categoria
                thread = await guild.create_text_channel(
                    name=nome_canal,
                    category=cat_negociacao,
                    overwrites=overwrites,
                    reason=f'Negociação: {user.name} → {projeto.titulo}'
                )

                # Registrar candidatura
                candidatura = Candidatura(
                    id=_gerar_id('cand'),
                    projeto_id=projeto.id,
                    dev_id=user.id,
                    dev_username=user.name,
                    empregador_id=projeto.empregador_id,
                    thread_id=thread.id,
                    status='negociando',
                )
                salvar_candidatura(candidatura)
                adicionar_candidato_projeto(projeto.id, user.id)

                # Registrar cooldown
                registrar_cooldown(user.id, 'candidatura')

                # Enviar embed de negociação na thread
                projeto_dict = asdict(projeto)
                embed = criar_embed_negociacao(
                    projeto=projeto_dict,
                    dev_nome=user.mention,
                    empregador_nome=empregador.mention if empregador else empregador_nome,
                )
                view = NegociacaoView(candidatura_id=candidatura.id)
                await thread.send(embed=embed, view=view)

                # Responder ao dev
                embed_resp = criar_embed_interesse_enviado(projeto.titulo)
                await interaction.followup.send(
                    embed=embed_resp,
                    ephemeral=True,
                )

                logger.info(
                    'Interesse registrado: dev=%s projeto=%s',
                    user.name, projeto.id,
                )

            except Exception as e:
                logger.exception('Erro ao processar interesse: %s', e)
                await interaction.followup.send(
                    '❌ Ocorreu um erro ao processar seu interesse. Tente novamente.',
                    ephemeral=True,
                )


class NegociacaoView(View):
    """View de negociação com botões de fechar/cancelar parceria."""

    def __init__(self, candidatura_id: str):
        super().__init__(timeout=None)
        self.candidatura_id = candidatura_id

        btn_fechar = Button(
            label='✅  Fechar Parceria',
            style=discord.ButtonStyle.success,
            custom_id=f'btn_fechar_{candidatura_id}',
        )
        btn_fechar.callback = self.callback_fechar
        self.add_item(btn_fechar)

        btn_cancelar = Button(
            label='❌  Não Fechar Parceria',
            style=discord.ButtonStyle.danger,
            custom_id=f'btn_cancelar_{candidatura_id}',
        )
        btn_cancelar.callback = self.callback_cancelar
        self.add_item(btn_cancelar)

    async def callback_fechar(self, interaction: discord.Interaction):
        """Lógica de fechar parceria — ambos precisam clicar."""
        from core.database import buscar_candidatura, atualizar_candidatura

        # Fechar parceria formaliza o contrato entre as partes — exige aceite dos Termos
        from views.termos_views import exigir_aceite_termos
        if not await exigir_aceite_termos(interaction):
            return

        cand = buscar_candidatura(self.candidatura_id)
        if not cand:
            await interaction.response.send_message(
                '❌ Candidatura não encontrada.',
                ephemeral=True,
            )
            return

        user = interaction.user

        if user.id == cand.dev_id:
            if cand.dev_aceito:
                await interaction.response.send_message(
                    '⚠️ Você já confirmou a parceria. Aguardando o empregador.',
                    ephemeral=True,
                )
                return
            cand.dev_aceito = True
            atualizar_candidatura(cand)
            await interaction.response.send_message(
                f'✅ **{user.display_name}** (Dev) confirmou a parceria!',
            )
        elif user.id == cand.empregador_id:
            if cand.empregador_aceito:
                await interaction.response.send_message(
                    '⚠️ Você já confirmou a parceria. Aguardando o dev.',
                    ephemeral=True,
                )
                return
            cand.empregador_aceito = True
            atualizar_candidatura(cand)
            await interaction.response.send_message(
                f'✅ **{user.display_name}** (Empregador) confirmou a parceria!',
            )
        else:
            await interaction.response.send_message(
                '❌ Apenas o dev ou o empregador podem interagir.',
                ephemeral=True,
            )
            return

        # Verificar se ambos aceitaram
        cand = buscar_candidatura(self.candidatura_id)
        if cand and cand.dev_aceito and cand.empregador_aceito:
            cand.status = 'fechado'
            atualizar_candidatura(cand)

            embed = discord.Embed(
                title='🎉  Parceria Fechada!',
                description=(
                    '**Ambas as partes confirmaram!**\n\n'
                    'O ambiente privado do projeto será criado automaticamente.\n'
                    'Aguarde...'
                ),
                color=COR_MATCHING,
            )
            await interaction.channel.send(embed=embed)

            # Criar projeto ativo (chamar o cog de execução)
            bot = interaction.client
            cog = bot.get_cog('ExecucaoCog')
            if cog:
                await cog.criar_projeto_ativo(
                    guild=interaction.guild,
                    candidatura=cand,
                )
            else:
                logger.error('ExecucaoCog não encontrado — projeto não criado automaticamente')
                await interaction.channel.send(
                    '⚠️ Sistema de execução indisponível. Contate a staff.'
                )

            logger.info('Parceria fechada: cand=%s', self.candidatura_id)

    async def callback_cancelar(self, interaction: discord.Interaction):
        """Cancelar negociação."""
        from core.database import buscar_candidatura, atualizar_candidatura

        cand = buscar_candidatura(self.candidatura_id)
        if not cand:
            await interaction.response.send_message(
                '❌ Candidatura não encontrada.',
                ephemeral=True,
            )
            return

        user = interaction.user

        if user.id not in (cand.dev_id, cand.empregador_id):
            await interaction.response.send_message(
                '❌ Apenas o dev ou o empregador podem interagir.',
                ephemeral=True,
            )
            return

        cand.status = 'cancelado'
        atualizar_candidatura(cand)

        embed = discord.Embed(
            title='❌  Negociação Cancelada',
            description=(
                f'**{user.display_name}** cancelou a negociação.\n\n'
                f'Esta thread será arquivada em breve.'
            ),
            color=COR_ERRO,
        )
        await interaction.response.send_message(embed=embed)

        # Arquivar thread ou deletar canal
        import asyncio
        await asyncio.sleep(10)
        try:
            if isinstance(interaction.channel, discord.Thread):
                await interaction.channel.edit(archived=True, locked=True)
            elif isinstance(interaction.channel, discord.TextChannel):
                await interaction.channel.delete()
        except Exception as e:
            logger.error('Erro ao arquivar thread de negociação: %s', e)

        logger.info(
            'Negociação cancelada por %s: cand=%s',
            user.name, self.candidatura_id,
        )
