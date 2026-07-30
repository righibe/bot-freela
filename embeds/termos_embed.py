"""
Embeds dos Termos de Uso.
"""

import discord
from config.settings import (
    COR_PRINCIPAL, COR_ALERTA, TERMOS_VERSAO, TERMOS_DATA_VIGENCIA,
    TAXA_PLATAFORMA_PERCENT,
)


def criar_embed_termos_resumo() -> discord.Embed:
    """Resumo dos Termos de Uso com os pontos principais (o documento completo é anexado)."""
    embed = discord.Embed(
        title='📜  Termos de Uso — Freeela',
        description=(
            f'**Versão {TERMOS_VERSAO}** • vigente desde {TERMOS_DATA_VIGENCIA}\n\n'
            'A Freeela é uma **plataforma de intermediação** entre desenvolvedores '
            'autônomos e contratantes. Antes de usar, você precisa ler e aceitar os '
            'Termos de Uso completos (documento anexo). Resumo dos pontos principais:'
        ),
        color=COR_PRINCIPAL,
    )
    embed.add_field(
        name='🤝  Natureza do serviço',
        value=(
            'A plataforma **aproxima** dev e contratante. O contrato de prestação de '
            'serviços é **entre vocês dois** — a Freeela não é parte, não é empregadora '
            'e não garante qualidade, prazo ou resultado dos projetos.'
        ),
        inline=False,
    )
    embed.add_field(
        name='💰  Pagamentos e taxa',
        value=(
            f'Todo pagamento passa **obrigatoriamente pela plataforma** (PIX via gateway). '
            f'A taxa de intermediação é de **{TAXA_PLATAFORMA_PERCENT:.0f}%**; o dev recebe '
            f'**{100 - TAXA_PLATAFORMA_PERCENT:.0f}%** automaticamente na chave PIX cadastrada. '
            f'**Pagamento por fora = banimento** e perda de toda proteção.'
        ),
        inline=False,
    )
    embed.add_field(
        name='🔞  Elegibilidade',
        value='Uso permitido apenas para **maiores de 18 anos**, com informações verdadeiras.',
        inline=False,
    )
    embed.add_field(
        name='⚖️  Responsabilidades',
        value=(
            'O dev é **autônomo** (responsável pelos próprios impostos); o contratante '
            'responde pelo que publica e paga. Disputas têm **mediação voluntária** da staff, '
            'sem obrigação de resultado.'
        ),
        inline=False,
    )
    embed.add_field(
        name='🔐  Seus dados (LGPD)',
        value=(
            'Coletamos apenas o necessário para operar (Discord ID, GitHub/LinkedIn, '
            'chave PIX para repasses). Dados de pagamento são compartilhados somente '
            'com o processador (AbacatePay). Você pode solicitar acesso/correção/exclusão.'
        ),
        inline=False,
    )
    embed.add_field(
        name='✅  Aceite',
        value=(
            'Ao clicar em **"Li e Aceito"**, seu aceite é registrado (usuário, versão, '
            'data/hora) e vale como manifestação eletrônica de vontade. '
            'O aceite é **obrigatório** para verificar-se, publicar projetos ou candidatar-se.'
        ),
        inline=False,
    )
    embed.set_footer(text='O resumo não substitui o documento completo — leia o arquivo anexo.')
    return embed


def criar_embed_aceite_necessario() -> discord.Embed:
    """Aviso de que o aceite dos Termos é obrigatório para continuar."""
    embed = discord.Embed(
        title='📜  Aceite dos Termos de Uso Necessário',
        description=(
            'Para usar esta funcionalidade você precisa **ler e aceitar os Termos de Uso** '
            f'(versão {TERMOS_VERSAO}) da plataforma.\n\n'
            '1️⃣ Clique em **"Ler Termos Completos"** para receber o documento.\n'
            '2️⃣ Clique em **"Li e Aceito"** para registrar seu aceite.\n'
            '3️⃣ Depois, clique novamente no botão da ação que você queria fazer.'
        ),
        color=COR_ALERTA,
    )
    embed.set_footer(text='O aceite é registrado com data e hora e só precisa ser feito uma vez por versão.')
    return embed
