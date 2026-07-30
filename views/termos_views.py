"""
Views dos Termos de Uso:
- TermosAceiteView: botões "Ler Termos Completos" e "Li e Aceito" (persistente).
- exigir_aceite_termos(): portão usado pelos fluxos críticos — bloqueia a ação
  e apresenta os Termos se o usuário ainda não aceitou a versão vigente.
"""

import logging
from pathlib import Path

import discord
from discord.ui import View, Button

import config.settings as settings
from config.settings import TERMOS_VERSAO
from core.database import registrar_aceite_termos, usuario_aceitou_termos
from embeds.termos_embed import criar_embed_termos_resumo, criar_embed_aceite_necessario

logger = logging.getLogger('bot_freeela.views.termos')

_RAIZ = Path(__file__).parent.parent
TERMOS_PDF = _RAIZ / 'TERMOS_DE_USO.pdf'
TERMOS_ARQUIVO = _RAIZ / 'TERMOS_DE_USO.md'  # fonte; o PDF é o documento distribuído


def _arquivo_termos() -> discord.File | None:
    """Retorna o documento dos Termos (PDF preferencialmente, .md como fallback)."""
    try:
        if TERMOS_PDF.exists():
            return discord.File(str(TERMOS_PDF), filename='TERMOS_DE_USO_FREEELA.pdf')
        return discord.File(str(TERMOS_ARQUIVO), filename='TERMOS_DE_USO_FREEELA.md')
    except (FileNotFoundError, OSError) as e:
        logger.error('Arquivo de Termos de Uso não encontrado: %s', e)
        return None


async def conceder_cargo_termos(member: discord.Member) -> bool:
    """Concede o cargo que desbloqueia os canais de verificação."""
    if not settings.CARGO_TERMOS_ACEITOS:
        return False
    cargo = member.guild.get_role(settings.CARGO_TERMOS_ACEITOS)
    if not cargo or cargo in member.roles:
        return cargo is not None and cargo in member.roles
    try:
        await member.add_roles(cargo, reason='Aceitou os Termos de Uso')
        return True
    except discord.Forbidden:
        logger.error('Sem permissão para conceder cargo de termos a %s', member.name)
        return False


class TermosAceiteView(View):
    """Botões persistentes de leitura e aceite dos Termos de Uso."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='📜  Ler Termos Completos',
        style=discord.ButtonStyle.secondary,
        custom_id='btn_ler_termos_global',
        row=0,
    )
    async def btn_ler(self, interaction: discord.Interaction, button: Button):
        arquivo = _arquivo_termos()
        if not arquivo:
            await interaction.response.send_message(
                '❌ Documento indisponível no momento. Contate a staff.',
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f'📜 **Termos de Uso da Freeela — versão {TERMOS_VERSAO}** (documento completo em anexo):',
            file=arquivo,
            ephemeral=True,
        )

    @discord.ui.button(
        label='✅  Li e Aceito',
        style=discord.ButtonStyle.success,
        custom_id='btn_aceitar_termos_global',
        row=0,
    )
    async def btn_aceitar(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if usuario_aceitou_termos(user.id, TERMOS_VERSAO):
            if isinstance(user, discord.Member):
                await conceder_cargo_termos(user)
            await interaction.response.send_message(
                f'✅ Você já aceitou os Termos de Uso (versão {TERMOS_VERSAO}). Está tudo certo!',
                ephemeral=True,
            )
            return

        contexto = ''
        if interaction.channel and getattr(interaction.channel, 'name', None):
            contexto = f'canal:{interaction.channel.name}'
        registrar_aceite_termos(
            user_id=user.id,
            username=user.name,
            versao=TERMOS_VERSAO,
            contexto=contexto,
        )
        if isinstance(user, discord.Member):
            await conceder_cargo_termos(user)

        await interaction.response.send_message(
            f'🔓 **Aceite registrado — acesso desbloqueado!** (Termos v{TERMOS_VERSAO})\n\n'
            f'Os canais de verificação **apareceram para você agora**:\n'
            f'💻 Programador? Entre em **verificar-dev** e prove sua stack.\n'
            f'🏢 Quer contratar? Entre em **verificar-empregador** e publique seu projeto.\n\n'
            f'Bem-vindo(a) à Freeela! 🚀',
            ephemeral=True,
        )
        logger.info('Usuário %s (%d) aceitou os Termos v%s', user.name, user.id, TERMOS_VERSAO)


async def exigir_aceite_termos(interaction: discord.Interaction) -> bool:
    """
    Portão de aceite: retorna True se o usuário já aceitou a versão vigente.
    Caso contrário, responde com o pedido de aceite (efêmero) e retorna False —
    o fluxo chamador deve simplesmente dar `return`.
    """
    if usuario_aceitou_termos(interaction.user.id, TERMOS_VERSAO):
        # Autocorreção: garante o cargo de desbloqueio para quem já aceitou
        if isinstance(interaction.user, discord.Member):
            await conceder_cargo_termos(interaction.user)
        return True

    embed = criar_embed_aceite_necessario()
    view = TermosAceiteView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    return False
