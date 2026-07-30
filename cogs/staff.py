"""
Cog de comandos administrativos da staff.

O sistema é orientado ao banco de dados — estes comandos permitem à staff
registrar/corrigir informações manualmente (ex.: verificação do GitHub
falhou e o usuário abriu um ticket) com sincronização automática dos cargos.

- /registrar    cadastra ou substitui o perfil completo de um dev
- /vincular     adiciona UMA tecnologia ao perfil de um dev
- /desvincular  remove UMA tecnologia do perfil de um dev
"""

import logging

import discord
from discord.ext import commands
from discord import app_commands

import config.settings as settings
from config.settings import (
    COR_SUCESSO, COR_ERRO, OPCOES_EXPERIENCIA, MAX_TECNOLOGIAS_POR_DEV,
)
from core.database import DevVerificado, buscar_dev, salvar_dev
from core.tecnologias import (
    nomes_ativas, normalizar_nome, validar_lista_tecnologias,
    sincronizar_cargos_membro,
)
from utils.helpers import estimar_senioridade, estimar_area, experiencia_label

logger = logging.getLogger('bot_freeela.cogs.staff')

CHOICES_EXPERIENCIA = [
    app_commands.Choice(name=label, value=valor)
    for label, valor in OPCOES_EXPERIENCIA
]


async def _autocomplete_tecnologias(interaction: discord.Interaction, atual: str):
    """Autocomplete com as tecnologias ativas do banco."""
    atual = atual.lower()
    nomes = [n for n in nomes_ativas() if atual in n.lower()]
    return [app_commands.Choice(name=n, value=n) for n in nomes[:25]]


async def _autocomplete_tecnologias_do_dev(interaction: discord.Interaction, atual: str):
    """Autocomplete com as tecnologias do dev informado no comando."""
    usuario = interaction.namespace.usuario
    if usuario:
        dev = buscar_dev(usuario.id)
        if dev:
            nomes = [n for n in dev.linguagens_confirmadas if atual.lower() in n.lower()]
            return [app_commands.Choice(name=n, value=n) for n in nomes[:25]]
    return []


class StaffCog(commands.Cog):
    """Comandos administrativos de correção do banco de dados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _sincronizar_cargos_dev(self, member: discord.Member, dev: DevVerificado):
        """Aplica todos os cargos correspondentes ao perfil: verificado + experiência + tecnologias."""
        guild = member.guild

        # Cargo de Desenvolvedor Verificado
        cargo_dev = guild.get_role(settings.CARGO_DEV_VERIFICADO)
        if cargo_dev and cargo_dev not in member.roles:
            try:
                await member.add_roles(cargo_dev, reason='Registro manual pela staff')
            except discord.Forbidden:
                logger.error('Sem permissão para dar cargo de dev a %s', member.name)

        # Cargo de experiência (remove os antigos)
        for exp, cargo_id in settings.CARGOS_EXPERIENCIA.items():
            cargo = guild.get_role(cargo_id)
            if not cargo:
                continue
            try:
                if exp == dev.experiencia and cargo not in member.roles:
                    await member.add_roles(cargo, reason='Registro manual pela staff')
                elif exp != dev.experiencia and cargo in member.roles:
                    await member.remove_roles(cargo, reason='Registro manual pela staff')
            except discord.Forbidden:
                pass

        # Cargos de tecnologia (cria se necessário e remove os que saíram)
        await sincronizar_cargos_membro(member, dev.linguagens_confirmadas, remover_antigos=True)

    async def _log_staff(self, guild: discord.Guild, texto: str):
        canal = guild.get_channel(settings.CANAL_LOG_DEV)
        if canal:
            try:
                await canal.send(texto)
            except Exception:
                pass

    # ══════════════════════════════════════════════════
    #  /registrar
    # ══════════════════════════════════════════════════

    @app_commands.command(
        name='registrar',
        description='[STAFF] Registra/corrige manualmente o perfil de um dev no banco de dados',
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        usuario='O membro a registrar como dev verificado',
        tecnologias=f'Tecnologias separadas por vírgula (máx. {MAX_TECNOLOGIAS_POR_DEV}). Ex: Python, React, Node.js',
        experiencia='Tempo de experiência do dev',
        github='(Opcional) URL do GitHub',
    )
    @app_commands.choices(experiencia=CHOICES_EXPERIENCIA)
    async def registrar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        tecnologias: str,
        experiencia: app_commands.Choice[str],
        github: str = '',
    ):
        await interaction.response.defer(ephemeral=True)

        validas, invalidas = validar_lista_tecnologias(tecnologias)
        if not validas:
            await interaction.followup.send(
                f'❌ Nenhuma tecnologia válida em `{tecnologias}`.\n'
                f'Disponíveis: {", ".join(f"`{n}`" for n in nomes_ativas())}',
                ephemeral=True,
            )
            return

        existente = buscar_dev(usuario.id)
        dev = existente or DevVerificado(user_id=usuario.id)
        dev.username = usuario.name
        dev.linguagens_confirmadas = validas
        dev.experiencia = experiencia.value
        dev.senioridade = estimar_senioridade(experiencia.value, dev.compatibilidade or 70)
        dev.area = estimar_area(validas)
        if github:
            dev.github_url = github.strip()
        if not existente:
            dev.compatibilidade = dev.compatibilidade or 70
            dev.integridade = dev.integridade or 70
        salvar_dev(dev)

        await self._sincronizar_cargos_dev(usuario, dev)

        embed = discord.Embed(
            title='✅  Dev Registrado Manualmente',
            description=(
                f'**Usuário:** {usuario.mention} (`{usuario.name}`)\n'
                f'**Tecnologias:** {", ".join(f"`{t}`" for t in validas)}\n'
                f'**Experiência:** {experiencia_label(experiencia.value)}\n'
                f'**GitHub:** {dev.github_url or "—"}\n'
                f'**Registro:** {"atualizado" if existente else "criado"} no banco + cargos sincronizados'
            ),
            color=COR_SUCESSO,
        )
        if invalidas:
            embed.add_field(
                name='⚠️  Ignoradas (não existem no banco)',
                value=', '.join(f'`{t}`' for t in invalidas) +
                      '\nSe necessário, aprove-as primeiro via sugestão de tecnologia.',
                inline=False,
            )
        embed.set_footer(text=f'Ação de {interaction.user.name}')
        await interaction.followup.send(embed=embed, ephemeral=True)

        await self._log_staff(
            interaction.guild,
            f'🛠️ **Registro manual**: {interaction.user.mention} registrou {usuario.mention} '
            f'como dev — {", ".join(validas)} | {experiencia_label(experiencia.value)}',
        )
        logger.info(
            'Registro manual: %s registrou %s com %s',
            interaction.user.name, usuario.name, validas,
        )

    # ══════════════════════════════════════════════════
    #  /vincular
    # ══════════════════════════════════════════════════

    @app_commands.command(
        name='vincular',
        description='[STAFF] Adiciona uma tecnologia ao perfil de um dev (banco + cargo)',
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        usuario='O dev que receberá a tecnologia',
        tecnologia='Tecnologia a adicionar',
    )
    @app_commands.autocomplete(tecnologia=_autocomplete_tecnologias)
    async def vincular(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        tecnologia: str,
    ):
        await interaction.response.defer(ephemeral=True)

        dev = buscar_dev(usuario.id)
        if not dev:
            await interaction.followup.send(
                f'❌ {usuario.mention} não está registrado como dev. Use **/registrar** primeiro.',
                ephemeral=True,
            )
            return

        nome = normalizar_nome(tecnologia)
        if not nome:
            await interaction.followup.send(
                f'❌ Tecnologia `{tecnologia}` não existe no banco. '
                f'Aprove-a primeiro via sugestão, ou verifique a grafia.',
                ephemeral=True,
            )
            return
        if nome in dev.linguagens_confirmadas:
            await interaction.followup.send(
                f'⚠️ {usuario.mention} já tem `{nome}` no perfil.', ephemeral=True,
            )
            return
        if len(dev.linguagens_confirmadas) >= MAX_TECNOLOGIAS_POR_DEV:
            await interaction.followup.send(
                f'❌ {usuario.mention} já tem o máximo de **{MAX_TECNOLOGIAS_POR_DEV}** tecnologias '
                f'({", ".join(dev.linguagens_confirmadas)}). Use **/desvincular** antes.',
                ephemeral=True,
            )
            return

        dev.linguagens_confirmadas.append(nome)
        dev.area = estimar_area(dev.linguagens_confirmadas)
        salvar_dev(dev)
        await sincronizar_cargos_membro(usuario, dev.linguagens_confirmadas, remover_antigos=False)

        await interaction.followup.send(
            f'✅ `{nome}` vinculada a {usuario.mention} '
            f'({len(dev.linguagens_confirmadas)}/{MAX_TECNOLOGIAS_POR_DEV}). '
            f'Cargo aplicado e banco atualizado.',
            ephemeral=True,
        )
        await self._log_staff(
            interaction.guild,
            f'🛠️ **Vínculo manual**: {interaction.user.mention} adicionou `{nome}` a {usuario.mention}',
        )
        logger.info('%s vinculou %s a %s', interaction.user.name, nome, usuario.name)

    # ══════════════════════════════════════════════════
    #  /desvincular
    # ══════════════════════════════════════════════════

    @app_commands.command(
        name='desvincular',
        description='[STAFF] Remove uma tecnologia do perfil de um dev (banco + cargo)',
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        usuario='O dev que perderá a tecnologia',
        tecnologia='Tecnologia a remover',
    )
    @app_commands.autocomplete(tecnologia=_autocomplete_tecnologias_do_dev)
    async def desvincular(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        tecnologia: str,
    ):
        await interaction.response.defer(ephemeral=True)

        dev = buscar_dev(usuario.id)
        if not dev:
            await interaction.followup.send(
                f'❌ {usuario.mention} não está registrado como dev.', ephemeral=True,
            )
            return

        nome = normalizar_nome(tecnologia) or tecnologia.strip()
        if nome not in dev.linguagens_confirmadas:
            await interaction.followup.send(
                f'⚠️ {usuario.mention} não tem `{nome}` no perfil '
                f'(atual: {", ".join(dev.linguagens_confirmadas) or "vazio"}).',
                ephemeral=True,
            )
            return

        dev.linguagens_confirmadas.remove(nome)
        dev.area = estimar_area(dev.linguagens_confirmadas)
        salvar_dev(dev)
        await sincronizar_cargos_membro(usuario, dev.linguagens_confirmadas, remover_antigos=True)

        await interaction.followup.send(
            f'✅ `{nome}` removida de {usuario.mention} '
            f'({len(dev.linguagens_confirmadas)}/{MAX_TECNOLOGIAS_POR_DEV} restantes). '
            f'Cargo removido e banco atualizado.',
            ephemeral=True,
        )
        await self._log_staff(
            interaction.guild,
            f'🛠️ **Desvínculo manual**: {interaction.user.mention} removeu `{nome}` de {usuario.mention}',
        )
        logger.info('%s desvinculou %s de %s', interaction.user.name, nome, usuario.name)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffCog(bot))
    logger.info('Cog de staff carregado')
