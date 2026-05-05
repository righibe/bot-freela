import logging
import discord
from discord.ext import commands
from discord import app_commands
from config.settings import CANAL_VERIFICAR_DEV
from embeds.verificacao_embed import criar_embed_verificacao
from views.iniciar_verificacao import IniciarVerificacaoView
logger = logging.getLogger('bot_freeela.cogs.verificacao')

class VerificacaoCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(IniciarVerificacaoView())
        logger.info('View persistente de verificação registrada')

    @app_commands.command(name='setup_verificacao', description='[STAFF] Envia a embed de verificação no canal #verificar-dev')
    @app_commands.default_permissions(administrator=True)
    async def setup_verificacao(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message('❌ Este comando só pode ser usado em um servidor.', ephemeral=True)
            return
        canal = guild.get_channel(CANAL_VERIFICAR_DEV)
        if not canal:
            await interaction.response.send_message(f'❌ Canal verificar-dev (ID: {CANAL_VERIFICAR_DEV}) não encontrado.', ephemeral=True)
            return
        embed = criar_embed_verificacao()
        view = IniciarVerificacaoView()
        await canal.send(embed=embed, view=view)
        await interaction.response.send_message(f'✅ Embed de verificação enviada em {canal.mention}!', ephemeral=True)
        logger.info('Embed de verificação enviada por %s em #verificar-dev', interaction.user.name)

    @app_commands.command(name='status_verificacao', description='[STAFF] Verifica o status do sistema de verificação')
    @app_commands.default_permissions(administrator=True)
    async def status_verificacao(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return
        canal_verif = guild.get_channel(CANAL_VERIFICAR_DEV)
        canal_diag = guild.get_channel(1497289159344128081)
        canal_review = guild.get_channel(1497293598818045982)
        embed = discord.Embed(title='📊  Status do Sistema de Verificação', color=5793266)
        embed.add_field(name='📡  Canais', value=f"• verificar-dev: {('✅' if canal_verif else '❌')}\n• diagnostico-dev: {('✅' if canal_diag else '❌')}\n• staff-review: {('✅' if canal_review else '❌')}", inline=False)
        cargo_dev = guild.get_role(1495614792961097899)
        embed.add_field(name='🏅  Cargo Principal', value=f"Desenvolvedor Verificado: {('✅' if cargo_dev else '❌')}", inline=False)
        embed.add_field(name='🤖  Bot', value=f'Latência: `{round(self.bot.latency * 1000)}ms`', inline=False)

        # Estatísticas de devs verificados
        from core.database import listar_devs
        devs = listar_devs()
        embed.add_field(name='👨‍💻  Devs Verificados', value=f'**{len(devs)}** no sistema', inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VerificacaoCog(bot))
    logger.info('Cog de verificação carregado')