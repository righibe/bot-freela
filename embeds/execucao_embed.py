"""
Embeds para o sistema de execução de projetos.
"""

import discord
from config.settings import COR_EXECUCAO, COR_SUCESSO, COR_ALERTA, COR_ERRO
from utils.helpers import formatar_data


def criar_embed_projeto_criado(
    titulo: str,
    dev_nome: str,
    empregador_nome: str,
    valor: float,
    prazo: str,
    escopo: str,
) -> discord.Embed:
    """Embed enviado no canal do projeto quando ele é criado."""
    embed = discord.Embed(
        title='🏗️  Projeto Iniciado!',
        description=(
            f'O projeto **{titulo}** foi oficialmente iniciado.\n\n'
            f'Este canal é o ambiente oficial de desenvolvimento. '
            f'**Toda comunicação sobre o projeto deve acontecer aqui.**'
        ),
        color=COR_EXECUCAO,
    )
    embed.add_field(name='👨‍💻  Desenvolvedor', value=dev_nome, inline=True)
    embed.add_field(name='👤  Empregador', value=empregador_nome, inline=True)
    embed.add_field(name='\u200b', value='\u200b', inline=True)
    embed.add_field(name='💰  Valor Fechado', value=f'**R$ {valor:,.2f}**', inline=True)
    embed.add_field(name='⏰  Prazo', value=prazo or 'Não definido', inline=True)
    embed.add_field(name='\u200b', value='\u200b', inline=True)
    embed.add_field(
        name='📋  Escopo',
        value=escopo[:1024] if escopo else 'Não definido',
        inline=False,
    )
    embed.set_footer(text=f'Projeto iniciado em {formatar_data()}')
    return embed


def criar_embed_regras_projeto() -> discord.Embed:
    """Embed com as regras obrigatórias do projeto."""
    embed = discord.Embed(
        title='📜  Regras Obrigatórias do Projeto',
        description=(
            'Este projeto segue as regras da plataforma Freeela. '
            '**O descumprimento pode resultar em sanções.**'
        ),
        color=COR_ALERTA,
    )
    embed.add_field(
        name='📢  Comunicação',
        value=(
            '• Toda comunicação sobre o projeto **deve acontecer neste canal**.\n'
            '• Não negocie por DM ou fora da plataforma.'
        ),
        inline=False,
    )
    embed.add_field(
        name='💳  Pagamento',
        value=(
            '• O envio de **comprovante de pagamento** é obrigatório.\n'
            '• Envie o comprovante neste canal após o pagamento.'
        ),
        inline=False,
    )
    embed.add_field(
        name='⏰  Prazo',
        value=(
            '• O **prazo definido é obrigatório**.\n'
            '• Solicite extensão com antecedência se necessário.'
        ),
        inline=False,
    )
    embed.add_field(
        name='📋  Escopo',
        value=(
            '• O **escopo definido é obrigatório**.\n'
            '• Alterações devem ser acordadas por ambas as partes.'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚠️  Importante',
        value=(
            '• Use os botões abaixo para gerenciar o projeto.\n'
            '• Em caso de disputa, acione a staff.'
        ),
        inline=False,
    )
    embed.set_footer(text='Freeela • Sistema de Execução de Projetos')
    return embed


def criar_embed_alerta_dados_faltando(campos_faltando: list[str]) -> discord.Embed:
    """Alerta quando dados obrigatórios estão faltando."""
    embed = discord.Embed(
        title='⚠️  Dados Obrigatórios Pendentes!',
        description=(
            'O projeto precisa dos seguintes dados para prosseguir:\n\n'
            + '\n'.join(f'• ❌ **{campo}**' for campo in campos_faltando)
            + '\n\nUse o botão **📋 Definir Detalhes** para preencher.'
        ),
        color=COR_ALERTA,
    )
    return embed


def criar_embed_log_projeto(
    projeto_id: str,
    titulo: str,
    dev_id: int,
    dev_nome: str,
    empregador_id: int,
    empregador_nome: str,
    valor: float,
    prazo: str,
    status: str,
) -> discord.Embed:
    """Embed de log para registro de projetos."""
    status_emojis = {
        'ativo': '🟢',
        'concluido': '✅',
        'cancelado': '❌',
        'disputa': '⚠️',
    }

    embed = discord.Embed(
        title=f'📊  Log de Projeto — {titulo}',
        color=COR_EXECUCAO,
    )
    embed.add_field(name='🆔  ID', value=f'`{projeto_id}`', inline=True)
    embed.add_field(
        name='📌  Status',
        value=f'{status_emojis.get(status, "❓")} {status.upper()}',
        inline=True,
    )
    embed.add_field(name='\u200b', value='\u200b', inline=True)
    embed.add_field(name='👨‍💻  Dev', value=f'<@{dev_id}> (`{dev_nome}`)', inline=True)
    embed.add_field(name='👤  Empregador', value=f'<@{empregador_id}> (`{empregador_nome}`)', inline=True)
    embed.add_field(name='\u200b', value='\u200b', inline=True)
    embed.add_field(name='💰  Valor', value=f'R$ {valor:,.2f}', inline=True)
    embed.add_field(name='⏰  Prazo', value=prazo or 'N/A', inline=True)
    embed.add_field(name='📅  Data', value=formatar_data(), inline=True)
    return embed


def criar_embed_projeto_concluido(titulo: str) -> discord.Embed:
    """Embed quando um projeto é marcado como concluído."""
    embed = discord.Embed(
        title='✅  Projeto Concluído!',
        description=(
            f'O projeto **{titulo}** foi marcado como **concluído** com sucesso.\n\n'
            f'Obrigado por usar a plataforma Freeela! 🎉'
        ),
        color=COR_SUCESSO,
    )
    embed.set_footer(text=f'Concluído em {formatar_data()}')
    return embed
