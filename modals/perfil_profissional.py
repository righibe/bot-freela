import discord
from discord.ui import Modal, TextInput
from config.settings import COR_ALERTA, MSG_ERRO_API, MSG_REPROVADO_AUTO, MSG_APROVADO_AUTO, MSG_REVIEW, COR_SUCESSO, COR_ERRO, COR_PRINCIPAL, MSG_VERIFICACAO_INICIADA
import logging

logger = logging.getLogger('bot_freeela.modals.perfil_profissional')

class PerfilProfissionalModal(Modal, title='Passo 1 — Seus Dados'):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        
        self.github = TextInput(label='Link do GitHub', placeholder='https://github.com/seu-usuario', style=discord.TextStyle.short, required=True)
        self.linkedin = TextInput(label='Link do LinkedIn (Opcional)', placeholder='https://linkedin.com/in/seu-usuario', style=discord.TextStyle.short, required=False)
        self.descricao = TextInput(label='Breve Descrição Profissional', placeholder='Sou desenvolvedor backend com foco em...', style=discord.TextStyle.paragraph, required=True, min_length=20, max_length=1000)
        
        self.add_item(self.github)
        self.add_item(self.linkedin)
        self.add_item(self.descricao)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('❌ Apenas o usuário em verificação pode interagir.', ephemeral=True)
            return

        channel = interaction.channel
        user = interaction.user
        guild = interaction.guild
        
        if not guild or not channel:
            await interaction.response.send_message('❌ Erro interno. Tente novamente.', ephemeral=True)
            return
            
        # Verificar se já existe thread
        for t in channel.threads:
            if t.name == f'verificacao-{user.name}' and not t.archived:
                await interaction.response.send_message(f'⚠️ Você já possui uma verificação em andamento: {t.mention}', ephemeral=True)
                return
                
        try:
            thread = await channel.create_thread(name=f'verificacao-{user.name}', type=discord.ChannelType.private_thread, auto_archive_duration=60, reason=f'Verificação dev para {user.name}')
            await thread.add_user(user)
            
            embed = discord.Embed(title='🔐 Verificação de Desenvolvedor', description=f'Olá {user.mention}!\n\nDados salvos com sucesso!\n\n**Etapa 2 de 3** — Selecione suas linguagens de programação.', color=COR_PRINCIPAL)
            embed.set_footer(text='Esta thread é privada. Apenas você e a staff podem vê-la.')
            
            from views.selecao_linguagens import SelecaoLinguagensView
            view = SelecaoLinguagensView(
                user_id=user.id,
                github=self.github.value,
                linkedin=self.linkedin.value,
                descricao=self.descricao.value,
                thread=thread
            )
            
            await thread.send(embed=embed, view=view)
            await interaction.response.send_message(f'✅ Seus dados foram recebidos! Continue em: {thread.mention}', ephemeral=True)
            logger.info('Thread de verificação criada para %s (%s)', user.name, user.id)
            
        except discord.Forbidden:
            await interaction.response.send_message('❌ Não tenho permissão para criar threads neste canal.', ephemeral=True)
            logger.error('Sem permissão para criar thread em %s', channel.id)
        except Exception as e:
            await interaction.response.send_message('❌ Ocorreu um erro ao iniciar a verificação. Tente novamente.', ephemeral=True)
            logger.exception('Erro ao criar thread de verificação: %s', e)