"""
Embeds do sistema de tickets.
"""

import discord
from config.settings import COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, TIPOS_TICKET


def criar_embed_abrir_ticket() -> discord.Embed:
    """Card do canal 🎫・abrir-ticket (estilo Painel de Suporte)."""
    embed = discord.Embed(
        description=(
            '## Painel de Suporte\n\n'
            'Se você precisa de ajuda, suporte ou tem alguma dúvida, estamos aqui '
            'para te ajudar. Selecione uma opção no menu abaixo, e abra um ticket.\n\n'
            'Um **canal privado** será criado — só você e a staff podem ver.'
        ),
        color=COR_PRINCIPAL,
    )
    embed.set_footer(text='Membros que abrirem tickets sem motivo serão penalizados.')
    return embed


def criar_embed_ticket_aberto(
    user_mention: str,
    staff_mention: str,
    tipo_rotulo: str,
    tipo_emoji: str,
) -> discord.Embed:
    """Card enviado dentro do canal do ticket recém-criado."""
    embed = discord.Embed(
        title=f'{tipo_emoji}  Ticket — {tipo_rotulo}',
        description=(
            f'{user_mention}, seu ticket foi aberto!\n\n'
            f'**Relate seu problema aqui neste chat** com o máximo de detalhes '
            f'(prints ajudam muito 📸). A {staff_mention} já foi avisada e vai '
            f'responder em breve.\n\n'
            f'Resolvido? Clique em **🔒 Fechar Ticket**.'
        ),
        color=COR_PRINCIPAL,
    )
    embed.set_footer(text='Freeela • Suporte')
    return embed


def criar_embed_ticket_fechado(fechado_por: str) -> discord.Embed:
    embed = discord.Embed(
        title='🔒  Ticket Fechado',
        description=(
            f'Este ticket foi fechado por **{fechado_por}**.\n'
            f'O canal será excluído em **15 segundos**.'
        ),
        color=COR_ERRO,
    )
    return embed
