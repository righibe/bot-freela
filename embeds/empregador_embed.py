"""
Embeds para o sistema de empregadores.
"""

import discord
from config.settings import COR_PRINCIPAL, COR_SUCESSO, COR_ALERTA, COR_PROJETO
from utils.helpers import formatar_data


def criar_embed_verificacao_empregador() -> discord.Embed:
    """Embed inicial no canal de empregadores."""
    embed = discord.Embed(
        description=(
            '## Precisa de um programador? 🏢\n\n'
            '**1.** Clique em **📋 Criar Projeto** e preencha o formulário\n'
            '**2.** Seu projeto entra na vitrine e os **devs verificados** vêm negociar\n'
            '**3.** Projeto entregue? Pague o **QR Code PIX** — só no final 🔒\n\n'
            '💡 Quanto mais detalhada a descrição, melhores os candidatos. '
            'Valor mínimo: **R$ 50**.'
        ),
        color=COR_PRINCIPAL,
    )
    embed.set_footer(text='Publicar é grátis • Pagamento seguro pelo bot')
    return embed


def criar_embed_projeto_aprovado(dados: dict) -> discord.Embed:
    """Embed mostrado quando um projeto é aprovado."""
    embed = discord.Embed(
        title='✅  Projeto Aprovado!',
        description=(
            f'Seu projeto **{dados.get("titulo", "Sem título")}** foi aprovado '
            f'e será listado no canal de projetos.\n\n'
            f'Desenvolvedores verificados poderão se candidatar.'
        ),
        color=COR_SUCESSO,
    )
    embed.add_field(
        name='📊  Score de Validação',
        value=f'**{dados.get("score", 0)}%**',
        inline=True,
    )
    embed.add_field(
        name='📂  Categoria',
        value=f'`{dados.get("categoria", "N/A")}`',
        inline=True,
    )
    embed.add_field(
        name='📈  Complexidade',
        value=f'`{dados.get("complexidade", "N/A")}`',
        inline=True,
    )
    if dados.get('sugestoes'):
        embed.add_field(
            name='💡  Sugestões',
            value='\n'.join(f'• {s}' for s in dados['sugestoes']),
            inline=False,
        )
    embed.set_footer(text=f'Aprovado em {formatar_data()}')
    return embed


def criar_embed_projeto_reprovado(dados: dict) -> discord.Embed:
    """Embed mostrado quando um projeto é reprovado."""
    embed = discord.Embed(
        title='❌  Projeto Não Aprovado',
        description=(
            'Seu projeto não passou na validação automática. '
            'Revise os problemas abaixo e tente novamente.'
        ),
        color=COR_ALERTA,
    )
    embed.add_field(
        name='📊  Score',
        value=f'**{dados.get("score", 0)}%**',
        inline=True,
    )
    if dados.get('problemas'):
        embed.add_field(
            name='🚫  Problemas Encontrados',
            value='\n'.join(f'• {p}' for p in dados['problemas']),
            inline=False,
        )
    if dados.get('sugestoes'):
        embed.add_field(
            name='💡  Sugestões',
            value='\n'.join(f'• {s}' for s in dados['sugestoes']),
            inline=False,
        )
    embed.set_footer(text='Você pode tentar novamente após corrigir os problemas.')
    return embed
