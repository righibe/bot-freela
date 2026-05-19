"""
Views para o sistema de execução de projetos.
Botões de gerenciamento dentro do canal privado do projeto.
"""

import logging
import discord
from discord.ui import View, Button
from config.settings import COR_SUCESSO, COR_ERRO, COR_ALERTA, COR_EXECUCAO, CANAL_LOG_PROJETOS
from core.database import (
    buscar_projeto_ativo_por_canal, atualizar_projeto_ativo,
    atualizar_projetos_ativos_dev, buscar_projeto, atualizar_status_projeto,
    salvar_projeto,
)
from embeds.execucao_embed import (
    criar_embed_projeto_concluido, criar_embed_alerta_dados_faltando,
    criar_embed_log_projeto,
)
from modals.projeto_detalhes import ProjetoDetalhesModal

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

        # Botão concluir projeto
        btn_concluir = Button(
            label='✅  Concluir Projeto',
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
        """Marca o projeto como concluído."""
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

        # Verificar se os detalhes obrigatórios foram definidos
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

        pa.status = 'concluido'
        atualizar_projeto_ativo(pa)
        atualizar_projetos_ativos_dev(pa.dev_id, -1)

        # Atualizar status do projeto original
        atualizar_status_projeto(pa.projeto_id, 'concluido')

        # Buscar projeto para título
        projeto = buscar_projeto(pa.projeto_id)
        titulo = projeto.titulo if projeto else 'Projeto'

        embed = criar_embed_projeto_concluido(titulo)
        await interaction.response.send_message(embed=embed)

        # Log
        await self._enviar_log(interaction.guild, pa, 'concluido', titulo)

        # Remover do canal de projetos disponíveis e deletar canal de negociação
        await self._limpar_projeto(interaction.guild, pa, projeto)

        logger.info('Projeto %s concluído por %s', pa.id, interaction.user.name)

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

        await self._enviar_log(interaction.guild, pa, 'cancelado → reaberto', titulo)

        # Limpar candidatos anteriores para permitir novas candidaturas
        if projeto:
            projeto.candidatos = []
            projeto.status = 'aberto'
            salvar_projeto(projeto)

        # Republicar na vitrine de projetos disponíveis
        guild = interaction.guild
        await self._republicar_projeto_na_vitrine(guild, projeto)

        # Deletar a categoria do projeto ativo (canais texto + voz)
        await self._deletar_categoria_ativa(guild, pa)

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
        await interaction.response.send_message(embed=embed)
        logger.warning('Staff acionada no projeto %s por %s', pa.id, interaction.user.name)

    async def _limpar_projeto(self, guild: discord.Guild, pa, projeto):
        """Remove o projeto dos canais quando concluído ou cancelado.
        
        - Deleta o canal inteiro da vitrine de projetos disponíveis
        - Deleta TODOS os canais da categoria do projeto ativo (texto + voz)
        - Deleta a categoria do projeto ativo
        """
        import asyncio

        # 1. Deletar o canal de listagem da vitrine de projetos disponíveis
        canal_listagem_id = getattr(projeto, 'canal_listagem_id', 0) if projeto else 0
        if canal_listagem_id:
            canal_listagem = guild.get_channel(canal_listagem_id)
            if canal_listagem and isinstance(canal_listagem, discord.TextChannel):
                try:
                    await canal_listagem.delete(
                        reason=f'Projeto {pa.projeto_id} concluído/cancelado — removido da vitrine'
                    )
                    logger.info(
                        'Canal de listagem %d deletado (projeto %s)',
                        canal_listagem_id, pa.projeto_id,
                    )
                except discord.Forbidden:
                    logger.error('Sem permissão para deletar canal de listagem %d', canal_listagem_id)
                except Exception as e:
                    logger.error('Erro ao deletar canal de listagem: %s', e)
            else:
                logger.warning('Canal de listagem %d não encontrado ou já deletado', canal_listagem_id)
        else:
            # Fallback: tentar deletar a mensagem se canal_listagem_id não existir
            if projeto and projeto.message_id:
                try:
                    from config.settings import CATEGORIA_PROJETOS_ID
                    categoria_projetos = guild.get_channel(CATEGORIA_PROJETOS_ID)
                    if categoria_projetos and isinstance(categoria_projetos, discord.CategoryChannel):
                        for canal in categoria_projetos.text_channels:
                            try:
                                msg = await canal.fetch_message(projeto.message_id)
                                await msg.delete()
                                logger.info('Mensagem do projeto %s deletada (fallback)', projeto.id)
                                break
                            except discord.NotFound:
                                continue
                            except Exception as e:
                                logger.error('Erro ao deletar mensagem do projeto: %s', e)
                except Exception as e:
                    logger.error('Erro ao remover projeto de projetos disponíveis (fallback): %s', e)

        # 2. Deletar a categoria INTEIRA do projeto ativo (todos os canais dentro)
        if pa.categoria_id:
            categoria = guild.get_channel(pa.categoria_id)
            if categoria and isinstance(categoria, discord.CategoryChannel):
                # Deletar todos os canais dentro da categoria primeiro
                for canal in categoria.channels:
                    try:
                        await canal.delete(reason=f'Projeto {pa.projeto_id} concluído/cancelado')
                        logger.info('Canal %s (%d) deletado da categoria do projeto', canal.name, canal.id)
                    except discord.Forbidden:
                        logger.error('Sem permissão para deletar canal %d', canal.id)
                    except Exception as e:
                        logger.error('Erro ao deletar canal %d: %s', canal.id, e)
                    await asyncio.sleep(0.5)  # evitar rate limit

                # Agora deletar a categoria vazia
                try:
                    await categoria.delete(reason=f'Projeto {pa.projeto_id} concluído/cancelado')
                    logger.info('Categoria %d deletada (projeto %s)', pa.categoria_id, pa.projeto_id)
                except discord.Forbidden:
                    logger.error('Sem permissão para deletar categoria %d', pa.categoria_id)
                except Exception as e:
                    logger.error('Erro ao deletar categoria: %s', e)
            else:
                logger.warning('Categoria %d não encontrada ou já deletada', pa.categoria_id)

    async def _enviar_log(
        self,
        guild: discord.Guild,
        pa,
        status: str,
        titulo: str,
    ):
        """Envia log do projeto para o canal de logs."""
        if not CANAL_LOG_PROJETOS:
            return

        canal_log = guild.get_channel(CANAL_LOG_PROJETOS)
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
