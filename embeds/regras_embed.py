"""
Embed de regras do servidor — tom formal e direto.
Postado no canal oficial de regras.
"""

import discord
from config.settings import COR_ERRO, TAXA_PLATAFORMA_PERCENT


def criar_embed_regras_serias() -> discord.Embed:
    embed = discord.Embed(
        title='REGRAS DO SERVIDOR',
        description=(
            'O descumprimento de qualquer regra abaixo resulta em **advertência, '
            'suspensão ou banimento permanente**, a critério da administração, '
            'sem aviso prévio. Ao permanecer neste servidor, você declara estar '
            'de acordo com estas regras e com os Termos de Uso.'
        ),
        color=COR_ERRO,
    )
    embed.add_field(
        name='§1 — Pagamentos exclusivamente pela plataforma',
        value=(
            'Todo pagamento de projeto deve ser processado pelo sistema oficial do bot. '
            'Negociar, oferecer ou aceitar pagamento por fora **resulta em banimento '
            'permanente de ambas as partes** e na cobrança da taxa devida, conforme os '
            'Termos de Uso. Não há exceções.'
        ),
        inline=False,
    )
    embed.add_field(
        name='§2 — Veracidade das informações',
        value=(
            'É proibido declarar experiência, linguagens ou identidade falsas, '
            'usar contas múltiplas ou manipular o sistema de verificação. '
            'Fraude comprovada resulta em banimento e registro da ocorrência.'
        ),
        inline=False,
    )
    embed.add_field(
        name='§3 — Conduta',
        value=(
            'Assédio, discriminação, ameaça, doxxing, spam ou divulgação não autorizada '
            'são proibidos. Aplicação imediata de banimento nos casos graves.'
        ),
        inline=False,
    )
    embed.add_field(
        name='§4 — Cumprimento de acordos',
        value=(
            'Escopo, prazo e valor registrados no canal do projeto vinculam ambas as partes. '
            'Abandono de projeto ou calote são registrados e punidos com suspensão ou banimento.'
        ),
        inline=False,
    )
    embed.add_field(
        name='§5 — Comunicação nos canais oficiais',
        value=(
            'Negociações e acordos devem ocorrer nos canais da plataforma. '
            'O que for combinado fora dos canais oficiais não possui validade '
            'nem proteção da administração.'
        ),
        inline=False,
    )
    embed.add_field(
        name='§6 — Conteúdo lícito',
        value=(
            'É proibido solicitar ou desenvolver projetos ilícitos: malware, fraudes, '
            'burla de sistemas, violação de direitos autorais ou qualquer atividade ilegal. '
            'Casos são reportados às autoridades competentes.'
        ),
        inline=False,
    )
    embed.add_field(
        name='§7 — Idade mínima e taxa',
        value=(
            f'O uso da plataforma é restrito a maiores de 18 anos. A taxa de intermediação '
            f'é de {TAXA_PLATAFORMA_PERCENT:.0f}% sobre o valor de cada projeto, conforme '
            f'os Termos de Uso disponíveis no canal de termos.'
        ),
        inline=False,
    )
    embed.set_footer(text='Administração Freeela • Estas regras complementam os Termos de Uso e os Termos do Discord.')
    return embed
