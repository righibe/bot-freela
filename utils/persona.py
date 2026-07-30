"""
Personas por canal via webhooks.

Cada canal importante tem um webhook próprio com nome e avatar temáticos —
as mensagens enviadas por ele aparecem como um "bot diferente" no Discord.
Se o envio via webhook falhar (sem permissão Manage Webhooks, view não
suportada etc.), cai no envio normal pelo bot.
"""

import logging
from pathlib import Path

import discord

logger = logging.getLogger('bot_freeela.utils.persona')

ASSETS = Path(__file__).parent.parent / 'assets'


def caminho_banner(tema: str) -> Path:
    return ASSETS / 'banners' / f'{tema}.png'


def caminho_avatar(tema: str) -> Path:
    return ASSETS / 'avatars' / f'{tema}.png'


async def _obter_webhook_persona(
    canal: discord.TextChannel,
    nome: str,
    tema: str,
) -> discord.Webhook | None:
    """Busca (ou cria) o webhook da persona neste canal, mantendo o avatar atualizado."""
    try:
        avatar_bytes = None
        avatar_path = caminho_avatar(tema)
        if avatar_path.exists():
            avatar_bytes = avatar_path.read_bytes()

        for wh in await canal.webhooks():
            if wh.name == nome:
                # Ressincroniza o avatar (a identidade visual pode ter mudado)
                if avatar_bytes:
                    try:
                        await wh.edit(avatar=avatar_bytes, reason='Atualização visual da persona')
                    except Exception:
                        pass
                return wh

        return await canal.create_webhook(
            name=nome,
            avatar=avatar_bytes,
            reason='Persona visual Freeela',
        )
    except discord.Forbidden:
        logger.warning('Sem permissão Manage Webhooks no canal %s', canal.name)
        return None
    except Exception as e:
        logger.error('Erro ao obter webhook persona em %s: %s', canal.name, e)
        return None


async def enviar_como_persona(
    canal: discord.TextChannel,
    nome_persona: str,
    tema: str,
    mensagens: list[dict],
) -> None:
    """
    Envia uma sequência de mensagens como a persona do canal.

    Cada item de `mensagens` é um dict de kwargs do send(); a chave extra
    'file_path' (Path/str) vira um discord.File criado na hora — necessário
    porque um File não pode ser reutilizado entre tentativas.
    """
    webhook = await _obter_webhook_persona(canal, nome_persona, tema)

    for kwargs in mensagens:
        kwargs = dict(kwargs)
        file_path = kwargs.pop('file_path', None)
        file_paths = kwargs.pop('file_paths', None)
        view = kwargs.get('view')

        def _montar_kwargs() -> dict:
            k = dict(kwargs)
            if file_path and Path(file_path).exists():
                k['file'] = discord.File(str(file_path))
            if file_paths:
                k['files'] = [
                    discord.File(str(p)) for p in file_paths if Path(p).exists()
                ]
            return k

        enviado = False
        if webhook:
            try:
                await webhook.send(**_montar_kwargs())
                enviado = True
            except Exception as e:
                logger.warning(
                    'Envio via persona falhou em %s (%s) — usando o bot',
                    canal.name, e,
                )
        if not enviado:
            await canal.send(**_montar_kwargs())

        # Views clássicas: a view global registrada no bot escuta os cliques,
        # então a instância local pode parar. Cards V2 (LayoutView) carregam os
        # próprios callbacks — NUNCA parar, senão os botões morrem.
        if view and not isinstance(view, discord.ui.LayoutView):
            view.stop()
