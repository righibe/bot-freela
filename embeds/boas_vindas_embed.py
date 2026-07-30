"""
Embeds do canal de boas-vindas (👋・comece-aqui).
Curto e direto — o banner faz o trabalho visual.
"""

import discord
from config.settings import COR_PRINCIPAL, TAXA_PLATAFORMA_PERCENT


def criar_embed_boas_vindas(
    canal_termos_id: int = 0,
    canal_dev_id: int = 0,
    canal_emp_id: int = 0,
    canal_ticket_id: int = 0,
) -> discord.Embed:
    """Card único de boas-vindas: escolha seu lado em 3 passos."""
    termos = f'<#{canal_termos_id}>' if canal_termos_id else '`📜・termos-de-uso`'
    dev = f'<#{canal_dev_id}>' if canal_dev_id else '`💻・verificar-dev`'
    emp = f'<#{canal_emp_id}>' if canal_emp_id else '`🏢・verificar-empregador`'
    ticket = f'<#{canal_ticket_id}>' if canal_ticket_id else '`🎫・abrir-ticket`'

    embed = discord.Embed(
        description=(
            '## Freelas de programação com pagamento garantido via PIX 💸\n\n'
            f'🔒 **O servidor está trancado para você** — os canais de verificação '
            f'só aparecem para quem aceita os termos em {termos}. '
            f'**Leva 30 segundos e desbloqueia tudo.** 🔓\n\n'
            f'**💻 Sou programador:**\n'
            f'aceite em {termos} → verifique-se → `/configurar_pagamento` → fature!\n\n'
            f'**🏢 Quero contratar:**\n'
            f'aceite em {termos} → publique seu projeto → devs verificados vêm até você!\n\n'
            f'O dev recebe **{100 - TAXA_PLATAFORMA_PERCENT:.0f}%** no PIX, na hora, automático. '
            f'Dúvidas? {ticket} 🎫'
        ),
        color=COR_PRINCIPAL,
    )
    return embed
