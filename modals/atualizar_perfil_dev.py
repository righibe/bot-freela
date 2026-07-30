"""
Modal para devs atualizarem seu perfil (linguagens e experiência).
Usado por devs verificados que desejam adicionar/atualizar suas informações.
"""

import logging
import discord
from discord.ui import Modal, TextInput
from config.settings import COR_SUCESSO, CARGOS_EXPERIENCIA
from services.api_client import validar_dev_via_api
from core.database import DevVerificado, salvar_dev, buscar_dev

logger = logging.getLogger('bot_freeela.modals.atualizar_perfil_dev')


class AtualizarPerfilDevModal(Modal, title='Atualizar Perfil de Dev'):
    """Modal para atualizar dados de experiência e linguagens."""

    github = TextInput(
        label='URL do GitHub',
        style=discord.TextStyle.short,
        placeholder='https://github.com/seu-usuario',
        required=True,
    )

    descricao = TextInput(
        label='Breve Descrição Profissional',
        style=discord.TextStyle.paragraph,
        placeholder='Sou desenvolvedor com foco em...',
        required=True,
        min_length=20,
        max_length=1000,
    )

    def __init__(self, user_id: int, guild: discord.Guild):
        super().__init__()
        self.user_id = user_id
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        github_url = self.github.value.strip()
        descricao_txt = self.descricao.value.strip()

        # Responder rápido para não dar timeout
        await interaction.response.defer(thinking=True, ephemeral=True)

        logger.info('=== INICIANDO ATUALIZAÇÃO PERFIL DEV ===')
        logger.info('Usuário: %s (%s)', user.name, user.id)
        logger.info('GitHub: %s', github_url)

        # Buscar dev atual para pegar linguagens e experiência
        dev_atual = buscar_dev(user.id)
        if not dev_atual:
            await interaction.followup.send(
                '❌ Você não está verificado como desenvolvedor ainda.',
                ephemeral=True,
            )
            logger.warning('Usuário %s tentou atualizar perfil mas não é dev verificado', user.id)
            return

        linguagens = dev_atual.linguagens_confirmadas or []
        experiencia = dev_atual.experiencia or 'qualquer'

        logger.info('Linguagens atuais: %s', linguagens)
        logger.info('Experiência atual: %s', experiencia)

        # Chamar API para validar
        resultado_api = await validar_dev_via_api(
            github=github_url,
            linkedin='',  # Não obrigatório na atualização
            descricao=descricao_txt,
            linguagens=linguagens,
            experiencia=experiencia
        )

        if not resultado_api:
            await interaction.followup.send(
                '❌ Erro ao conectar com a API de validação. Tente novamente em alguns momentos.',
                ephemeral=True,
            )
            logger.error('Erro ao chamar API de validação para %s', user.id)
            return

        aprovado = resultado_api.get('approved', False)
        needs_review = resultado_api.get('needs_review', False)
        motivos_reprovacao = resultado_api.get('rejection_reasons', [])

        if not aprovado and not needs_review:
            msg = '❌ Sua atualização foi rejeitada:\n\n'
            for motivo in motivos_reprovacao:
                msg += f'• {motivo}\n'
            await interaction.followup.send(msg, ephemeral=True)
            logger.warning('Atualização de %s rejeitada: %s', user.id, motivos_reprovacao)
            return

        if needs_review:
            await interaction.followup.send(
                '⏳ Sua atualização está sob revisão de staff. Você será notificado quando for aprovada.',
                ephemeral=True,
            )
            logger.info('Atualização de %s requer revisão', user.id)
            # TODO: Enviar para staff review se necessário
            return

        # Aprovado! Atualizar cargos
        try:
            # Remover cargos de experiência antigos
            for exp_key, cargo_id in CARGOS_EXPERIENCIA.items():
                cargo = self.guild.get_role(cargo_id)
                if cargo and cargo in user.roles:
                    try:
                        await user.remove_roles(cargo, reason='Atualização de perfil')
                    except Exception:
                        pass

            # Adicionar novo cargo de experiência
            if experiencia in CARGOS_EXPERIENCIA:
                cargo_exp_id = CARGOS_EXPERIENCIA[experiencia]
                cargo_exp = self.guild.get_role(cargo_exp_id)
                if cargo_exp:
                    try:
                        await user.add_roles(cargo_exp, reason=f'Experiência atualizada: {experiencia}')
                    except Exception as e:
                        logger.error('Erro ao adicionar cargo de experiência: %s', e)

            # Atualizar tecnologias: mantém o perfil e ressincroniza os cargos
            # dinamicamente a partir do banco
            linguagens_confirmadas = resultado_api.get('validated_languages', linguagens) or linguagens
            from core.tecnologias import sincronizar_cargos_membro
            await sincronizar_cargos_membro(user, linguagens_confirmadas, remover_antigos=True)

            # Atualizar no banco de dados
            dev_atual.linguagens_confirmadas = linguagens_confirmadas
            dev_atual.experiencia = experiencia
            salvar_dev(dev_atual)

            embed = discord.Embed(
                title='✅ Perfil Atualizado com Sucesso!',
                description=(
                    f'Seus dados foram validados e atualizados.\n\n'
                    f'**Linguagens:** {", ".join(linguagens_confirmadas)}\n'
                    f'**Experiência:** {experiencia.replace("_", " ").title()}'
                ),
                color=COR_SUCESSO,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info('Perfil de %s atualizado com sucesso', user.name)

        except Exception as e:
            logger.exception('Erro ao atualizar cargos: %s', e)
            await interaction.followup.send(
                '⚠️ Seu perfil foi validado, mas houve um erro ao atualizar os cargos. Contate a staff.',
                ephemeral=True,
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception('Erro na modal de atualização de perfil: %s', error)
        try:
            await interaction.response.send_message(
                '❌ Ocorreu um erro ao processar o formulário.',
                ephemeral=True,
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                '❌ Ocorreu um erro ao processar o formulário.',
                ephemeral=True,
            )
