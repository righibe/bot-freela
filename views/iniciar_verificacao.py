import logging
import discord
from discord.ui import View, Button
from config.settings import CANAL_VERIFICAR_DEV, COR_PRINCIPAL, MSG_VERIFICACAO_INICIADA
logger = logging.getLogger('bot_freeela.views.iniciar_verificacao')

class IniciarVerificacaoView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🚀  Iniciar Verificação', style=discord.ButtonStyle.primary, custom_id='btn_iniciar_verificacao', row=0)
    async def btn_iniciar(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        channel = interaction.channel
        user = interaction.user
        if not guild or not channel:
            await interaction.response.send_message('❌ Erro interno. Tente novamente.', ephemeral=True)
            return
        for thread in channel.threads:
            if thread.name == f'verificacao-{user.name}' and (not thread.archived):
                await interaction.response.send_message(f'⚠️ Você já possui uma verificação em andamento: {thread.mention}', ephemeral=True)
                return
        try:
            thread = await channel.create_thread(name=f'verificacao-{user.name}', type=discord.ChannelType.private_thread, auto_archive_duration=60, reason=f'Verificação dev para {user.name}')
            await thread.add_user(user)
            embed = discord.Embed(title='🔐  Verificação de Desenvolvedor', description=f'Olá {user.mention}!\n\n{MSG_VERIFICACAO_INICIADA}\n\n**Etapa 1 de 3** — Selecione suas linguagens de programação.', color=COR_PRINCIPAL)
            embed.set_footer(text='Esta thread é privada. Apenas você e a staff podem vê-la.')
            from views.selecao_linguagens import SelecaoLinguagensView
            view = SelecaoLinguagensView(user_id=user.id)
            await thread.send(embed=embed, view=view)
            await interaction.response.send_message(f'✅ Sua verificação foi criada! Acesse: {thread.mention}', ephemeral=True)
            logger.info('Thread de verificação criada para %s (%s)', user.name, user.id)
        except discord.Forbidden:
            await interaction.response.send_message('❌ Não tenho permissão para criar threads neste canal.', ephemeral=True)
            logger.error('Sem permissão para criar thread em %s', channel.id)
        except Exception as e:
            await interaction.response.send_message('❌ Ocorreu um erro ao iniciar a verificação. Tente novamente.', ephemeral=True)
            logger.exception('Erro ao criar thread de verificação: %s', e)