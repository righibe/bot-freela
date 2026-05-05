"""
Embeds para listagem e exibição de projetos.
"""

import discord
from config.settings import COR_PROJETO, COR_MATCHING
from utils.helpers import formatar_data


def criar_embed_projeto_listagem(projeto: dict) -> discord.Embed:
    """
    Embed de um projeto para listagem no canal de projetos.
    Inclui resumo, valor, stack, experiência e botão de interesse.
    """
    # Emoji por categoria
    emojis_categoria = {
        'Bots': '🤖',
        'SaaS': '☁️',
        'Mobile': '📱',
        'Web App': '🌐',
        'API / Backend': '⚙️',
        'Automação': '🔄',
        'Data / ML': '📊',
        'Jogos': '🎮',
        'Desktop': '🖥️',
        'Outro': '📦',
    }

    categoria = projeto.get('categoria', 'Outro')
    emoji = emojis_categoria.get(categoria, '📦')

    embed = discord.Embed(
        title=f'{emoji}  {projeto.get("titulo", "Projeto")}',
        description=projeto.get('descricao', 'Sem descrição')[:500],
        color=COR_PROJETO,
    )

    # Valor
    valor = projeto.get('valor', 0)
    embed.add_field(
        name='💰  Valor Oferecido',
        value=f'**R$ {valor:,.2f}**',
        inline=True,
    )

    # Experiência requerida
    exp_labels = {
        'junior': '🌱 Júnior',
        'pleno': '📗 Pleno',
        'senior': '📕 Sênior',
        'qualquer': '🔓 Qualquer nível',
    }
    exp = projeto.get('experiencia_minima', 'qualquer')
    embed.add_field(
        name='📊  Experiência Mínima',
        value=exp_labels.get(exp, exp),
        inline=True,
    )

    # Categoria
    embed.add_field(
        name='📂  Categoria',
        value=f'`{categoria}`',
        inline=True,
    )

    # Stack
    langs = projeto.get('linguagens_requeridas', [])
    if langs:
        embed.add_field(
            name='🛠️  Stack Requerida',
            value=', '.join(f'`{l}`' for l in langs),
            inline=False,
        )

    # Prazo
    prazo = projeto.get('prazo_estimado', '')
    if prazo:
        embed.add_field(
            name='⏰  Prazo Estimado',
            value=prazo,
            inline=True,
        )

    # Empregador
    empregador_nome = projeto.get('empregador_nome', 'Anônimo')
    embed.add_field(
        name='👤  Empregador',
        value=empregador_nome,
        inline=True,
    )

    # Candidatos
    candidatos = projeto.get('candidatos', [])
    embed.add_field(
        name='👥  Candidatos',
        value=f'{len(candidatos)} interessado(s)',
        inline=True,
    )

    embed.set_footer(text=f'ID: {projeto.get("id", "?")} • Publicado em {formatar_data()}')
    return embed


def criar_embed_interesse_enviado(projeto_titulo: str) -> discord.Embed:
    """Embed enviado ao dev quando ele demonstra interesse."""
    embed = discord.Embed(
        title='🤝  Interesse Registrado!',
        description=(
            f'Você demonstrou interesse no projeto **{projeto_titulo}**.\n\n'
            f'Uma thread de negociação foi criada para você conversar '
            f'com o empregador. Use-a para:\n\n'
            f'• 💰 Negociar o preço\n'
            f'• 📋 Ajustar o escopo\n'
            f'• ⏰ Definir prazos\n'
        ),
        color=COR_MATCHING,
    )
    embed.set_footer(text='Ambos precisam clicar em "Fechar Parceria" para confirmar.')
    return embed


def criar_embed_negociacao(projeto: dict, dev_nome: str, empregador_nome: str) -> discord.Embed:
    """Embed inicial da thread de negociação."""
    embed = discord.Embed(
        title='🤝  Negociação de Projeto',
        description=(
            f'**Projeto:** {projeto.get("titulo", "?")}\n'
            f'**Dev:** {dev_nome}\n'
            f'**Empregador:** {empregador_nome}\n\n'
            f'Esta thread é para negociação. Discutam:\n\n'
            f'1. 💰 **Valor final** do projeto\n'
            f'2. 📋 **Escopo** detalhado do trabalho\n'
            f'3. ⏰ **Prazo** de entrega\n\n'
            f'Quando ambos estiverem de acordo, cliquem em **✅ Fechar Parceria**.\n'
            f'Se não houver acordo, cliquem em **❌ Não Fechar Parceria**.'
        ),
        color=COR_MATCHING,
    )
    embed.add_field(
        name='💰  Valor Proposto',
        value=f'R$ {projeto.get("valor", 0):,.2f}',
        inline=True,
    )
    embed.add_field(
        name='🛠️  Stack',
        value=', '.join(projeto.get('linguagens_requeridas', ['N/A'])),
        inline=True,
    )
    embed.set_footer(text='⚠️ Ambos devem clicar em Fechar Parceria para prosseguir.')
    return embed
