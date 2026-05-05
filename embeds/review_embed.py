import discord
from datetime import datetime, timezone
from config.settings import COR_REVIEW
from services.scoring_service import ResultadoScore
from utils.helpers import formatar_data

def criar_embed_review(usuario: discord.Member, resultado: ResultadoScore, github_url: str, linkedin_url: str, descricao: str, experiencia_label: str) -> discord.Embed:
    embed = discord.Embed(title='🔎  Revisão Manual Necessária', description=f'O membro {usuario.mention} (`{usuario.name}`) não atingiu os critérios para aprovação automática e precisa de análise manual.', color=COR_REVIEW)
    embed.set_author(name=usuario.display_name, icon_url=usuario.display_avatar.url)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name='📈  Compatibilidade', value=f'**{resultado.compatibilidade}%**', inline=True)
    embed.add_field(name='🔒  Integridade', value=f'**{resultado.integridade}%**', inline=True)
    embed.add_field(name='⏱️  Experiência', value=f'`{experiencia_label}`', inline=True)
    motivos = '\n'.join((f'• {m}' for m in resultado.motivos_reprovacao)) or 'Nenhum motivo específico'
    embed.add_field(name='🚫  Motivos da Reprovação', value=motivos, inline=False)
    if resultado.penalizacoes:
        penalidades_txt = '\n'.join(resultado.penalizacoes)
        embed.add_field(name='⚠️  Penalizações de Integridade', value=penalidades_txt, inline=False)
    if resultado.detalhes_compat:
        compat_txt = '\n'.join(resultado.detalhes_compat)
        embed.add_field(name='📋  Detalhes de Compatibilidade', value=compat_txt, inline=False)
    selecionadas = ', '.join(resultado.linguagens_selecionadas) or 'Nenhuma'
    detectadas = ', '.join(resultado.linguagens_detectadas) or 'Nenhuma'
    confirmadas = ', '.join(resultado.linguagens_confirmadas) or 'Nenhuma'
    embed.add_field(name='📝  Linguagens Declaradas', value=f'`{selecionadas}`', inline=False)
    embed.add_field(name='🔍  Linguagens no GitHub', value=f'`{detectadas}`', inline=True)
    embed.add_field(name='✅  Confirmadas', value=f'`{confirmadas}`', inline=True)
    embed.add_field(name='📄  Descrição Profissional', value=f'>>> {descricao[:500]}' if descricao else 'Não informada', inline=False)
    links_txt = ''
    if github_url:
        links_txt += f'🐙 **GitHub:** [{github_url}]({github_url})\n'
    if linkedin_url:
        links_txt += f'💼 **LinkedIn:** [{linkedin_url}]({linkedin_url})\n'
    if links_txt:
        embed.add_field(name='🔗  Links Analisados', value=links_txt, inline=False)
    embed.add_field(name='🆔  User ID', value=f'`{usuario.id}`', inline=True)
    embed.add_field(name='📊  Senioridade Estimada', value=f'`{resultado.senioridade}`', inline=True)
    embed.set_footer(text=f'Enviado para revisão em {formatar_data()}')
    return embed

def criar_embed_review_empregador(usuario: discord.Member, nome: str, titulo: str, descricao: str, score: int, problemas: list) -> discord.Embed:
    embed = discord.Embed(
        title='🔎 Revisão Manual Necessária — Empregador',
        description=f'O membro {usuario.mention} tentou cadastrar um projeto, mas foi retido para análise.',
        color=COR_REVIEW
    )
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name='👤 Empregador', value=f'**Nome:** {nome}\n**ID:** `{usuario.id}`', inline=False)
    embed.add_field(name='📊 Score', value=f'**{score}%**', inline=True)
    if problemas:
        embed.add_field(name='⚠️ Problemas', value='\n'.join(f'• {p}' for p in problemas), inline=False)
    embed.add_field(name='📝 Projeto', value=f'**{titulo}**\n>>> {descricao[:500]}', inline=False)
    embed.set_footer(text=f'Enviado para revisão em {formatar_data()}')
    return embed