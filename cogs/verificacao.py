import logging
import discord
from discord.ext import commands
from discord import app_commands
from config.settings import CANAL_VERIFICAR_DEV, CANAL_ATUALIZAR_PERFIL_DEV
from embeds.verificacao_embed import criar_embed_verificacao, criar_embed_atualizar_perfil
from views.iniciar_verificacao import IniciarVerificacaoView
from views.atualizar_perfil_dev import AtualizarPerfilDevView

logger = logging.getLogger('bot_freeela.cogs.verificacao')

class VerificacaoCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(IniciarVerificacaoView())
        self.bot.add_view(AtualizarPerfilDevView())
        logger.info('Views persistentes de verificação registradas')

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

    @app_commands.command(name='setup_atualizar_perfil', description='[STAFF] Envia a embed de atualização de perfil no canal #atualizar-perfil-dev')
    @app_commands.default_permissions(administrator=True)
    async def setup_atualizar_perfil(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message('❌ Este comando só pode ser usado em um servidor.', ephemeral=True)
            return
        canal = guild.get_channel(CANAL_ATUALIZAR_PERFIL_DEV)
        if not canal:
            await interaction.response.send_message(f'❌ Canal atualizar-perfil-dev (ID: {CANAL_ATUALIZAR_PERFIL_DEV}) não encontrado.', ephemeral=True)
            return
        
        embed = criar_embed_atualizar_perfil()
        view = AtualizarPerfilDevView()
        await canal.send(embed=embed, view=view)
        await interaction.response.send_message(f'✅ Embed de atualização de perfil enviada em {canal.mention}!', ephemeral=True)
        logger.info('Embed de atualização de perfil enviada por %s em #atualizar-perfil-dev', interaction.user.name)
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

        from config.settings import get_cargo_dev_verificado, CARGO_DEV_VERIFICADO
        cargo_dev = get_cargo_dev_verificado(guild)
        cargo_info = f"Desenvolvedor Verificado: {('✅' if cargo_dev else '❌')}"
        if cargo_dev:
            cargo_info += f"\n• ID: `{cargo_dev.id}`\n• Nome: `{cargo_dev.name}`\n• Posição: `{cargo_dev.position}`"
            if cargo_dev.id != CARGO_DEV_VERIFICADO:
                cargo_info += f"\n• ID configurado: `{CARGO_DEV_VERIFICADO}` (não corresponde ao cargo encontrado)"
        else:
            cargo_info += f"\n• ID configurado: `{CARGO_DEV_VERIFICADO}`"

        embed.add_field(name='🏅  Cargo Principal', value=cargo_info, inline=False)

        # Verificar permissões do bot
        bot_perms = guild.me.guild_permissions
        perms_info = f"• Manage Roles: {('✅' if bot_perms.manage_roles else '❌')}"
        if bot_perms.manage_roles and cargo_dev:
            top_role = guild.me.top_role
            perms_info += f"\n• Cargo do bot: `{top_role.name}` (posição: {top_role.position})"
            perms_info += f"\n• Cargo alvo: `{cargo_dev.name}` (posição: {cargo_dev.position})"
            perms_info += f"\n• Pode atribuir: {('✅' if cargo_dev.position < top_role.position else '❌')}"

        embed.add_field(name='🤖  Bot Permissions', value=perms_info, inline=False)
        embed.add_field(name='📶  Bot', value=f'Latência: `{round(self.bot.latency * 1000)}ms`', inline=False)

        # Estatísticas de devs verificados
        from core.database import listar_devs
        devs = listar_devs()
        embed.add_field(name='👨‍💻  Devs Verificados', value=f'**{len(devs)}** no sistema', inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VerificacaoCog(bot))
    logger.info('Cog de verificação carregado')