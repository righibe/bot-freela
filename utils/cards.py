"""
Cards no formato Components V2 do Discord (Container + MediaGallery + TextDisplay).

O banner fica DENTRO do card, com cantos arredondados — visual do painel de
suporte de referência. Requer discord.py >= 2.6.

- embed_para_md(): converte um Embed existente em texto markdown para o card.
- clonar_interativos(): clona botões/selects de uma View clássica para o card,
  reaproveitando os callbacks originais (mesmos custom_ids).
- montar_card(): monta o LayoutView final (banner + texto + arquivo + botões).
"""

import logging
from pathlib import Path

import discord

logger = logging.getLogger('bot_freeela.utils.cards')


class CardLayout(discord.ui.LayoutView):
    """LayoutView persistente contendo um único Container."""

    def __init__(self, container: discord.ui.Container):
        super().__init__(timeout=None)
        self.add_item(container)


def embed_para_md(embed: discord.Embed) -> str:
    """Converte um Embed em markdown para usar num TextDisplay."""
    partes = []
    if embed.title:
        partes.append(f'## {embed.title}')
    if embed.description:
        partes.append(embed.description)
    for field in embed.fields:
        partes.append(f'**{field.name}**\n{field.value}')
    if embed.footer and embed.footer.text:
        partes.append(f'-# {embed.footer.text}')
    return '\n\n'.join(partes)


def clonar_interativos(view: discord.ui.View) -> list:
    """
    Clona os botões/selects de uma View clássica para uso dentro de um card,
    mantendo custom_id e delegando o clique ao callback original.
    A instância da view original fica viva via closure dos callbacks.
    """
    clones = []
    for item in view.children:
        if isinstance(item, discord.ui.Button):
            clone = discord.ui.Button(
                label=item.label,
                style=item.style,
                custom_id=item.custom_id,
                emoji=item.emoji,
            )
        elif isinstance(item, discord.ui.Select):
            clone = discord.ui.Select(
                placeholder=item.placeholder,
                min_values=item.min_values,
                max_values=item.max_values,
                options=item.options,
                custom_id=item.custom_id,
            )
        else:
            continue
        clone.callback = item.callback  # delega para a lógica original
        clones.append(clone)
    return clones


def montar_card(
    texto: str,
    banner_path: Path | str | None = None,
    itens: list | None = None,
    arquivo_path: Path | str | None = None,
    accent: int | None = None,
) -> tuple[CardLayout, list]:
    """
    Monta um card Components V2.
    Retorna (view, file_paths) — os arquivos devem ser anexados no send
    (a referência interna usa attachment://<nome-do-arquivo>).
    """
    partes = []
    file_paths = []

    if banner_path and Path(banner_path).exists():
        partes.append(discord.ui.MediaGallery(
            discord.MediaGalleryItem(media=f'attachment://{Path(banner_path).name}')
        ))
        file_paths.append(banner_path)

    partes.append(discord.ui.TextDisplay(texto[:3900]))

    if arquivo_path and Path(arquivo_path).exists():
        partes.append(discord.ui.File(media=f'attachment://{Path(arquivo_path).name}'))
        file_paths.append(arquivo_path)

    if itens:
        partes.append(discord.ui.Separator())
        partes.append(discord.ui.ActionRow(*itens))

    container = discord.ui.Container(*partes, accent_color=accent)
    return CardLayout(container), file_paths
