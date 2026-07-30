"""
Embeds do sistema de tecnologias.
"""

import discord
from config.settings import COR_PRINCIPAL, MAX_TECNOLOGIAS_POR_DEV, MATCH_MIN_TECNOLOGIAS


def criar_embed_sugerir_tecnologia() -> discord.Embed:
    """Card do canal 💡・sugerir-tecnologia."""
    embed = discord.Embed(
        description=(
            '## Sua tecnologia não está aqui? 💡\n\n'
            'Trabalha com algo que ainda não existe na plataforma? '
            '**Sugira!** Se a staff aprovar, ela ganha **cargo próprio**, entra na '
            'verificação e passa a valer no **matching de projetos**.\n\n'
            f'📌 Lembre: cada dev tem até **{MAX_TECNOLOGIAS_POR_DEV} tecnologias** no perfil '
            f'e o match com projetos exige **{MATCH_MIN_TECNOLOGIAS}+ em comum**.\n'
            '🛠️ Veja as existentes com **/tecnologias** antes de sugerir.'
        ),
        color=COR_PRINCIPAL,
    )
    embed.set_footer(text='Sugestões repetidas ou sem justificativa são recusadas.')
    return embed
