import discord
from datetime import datetime, timezone
from config.settings import COR_SUCESSO, COR_REVIEW, COR_DIAGNOSTICO
from services.scoring_service import ResultadoScore
from utils.helpers import formatar_data

def criar_embed_diagnostico(usuario: discord.Member, resultado: ResultadoScore, github_url: str, linkedin_url: str) -> discord.Embed:
    cor = COR_SUCESSO if resultado.aprovado else COR_REVIEW
    status = '✅ Desenvolvedor Verificado' if resultado.aprovado else '⏳ Enviado para Revisão'
    embed = discord.Embed(title='📊  Diagnóstico Dev', color=cor)
    embed.set_author(name=f'{usuario.display_name}', icon_url=usuario.display_avatar.url)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name='👤  Usuário', value=f'{usuario.mention}\n`{usuario.name}`', inline=True)
    embed.add_field(name='🆔  ID', value=f'`{usuario.id}`', inline=True)
    embed.add_field(name='\u200b', value='\u200b', inline=True)
    barra_compat = _barra_progresso(resultado.compatibilidade)
    barra_integ = _barra_progresso(resultado.integridade)
    embed.add_field(name='📈  Compatibilidade', value=f'{barra_compat} **{resultado.compatibilidade}%**', inline=True)
    embed.add_field(name='🔒  Integridade', value=f'{barra_integ} **{resultado.integridade}%**', inline=True)
    embed.add_field(name='\u200b', value='\u200b', inline=True)
    embed.add_field(name='🛠️  Stack Principal', value=f'`{resultado.stack_principal}`', inline=True)
    embed.add_field(name='📂  Área Principal', value=f'`{resultado.area_principal}`', inline=True)
    embed.add_field(name='📊  Senioridade', value=f'`{resultado.senioridade}`', inline=True)
    detectadas = ', '.join(resultado.linguagens_detectadas) or 'Nenhuma'
    confirmadas = ', '.join(resultado.linguagens_confirmadas) or 'Nenhuma'
    embed.add_field(name='🔍  Linguagens Detectadas', value=f'```{detectadas}```', inline=False)
    embed.add_field(name='✅  Linguagens Confirmadas', value=f'```{confirmadas}```', inline=False)
    embed.add_field(name='🐙  GitHub', value=f'[{github_url}]({github_url})' if github_url else 'Não informado', inline=True)
    embed.add_field(name='💼  LinkedIn', value=f'[{linkedin_url}]({linkedin_url})' if linkedin_url else 'Não informado', inline=True)
    embed.add_field(name='📌  Status Final', value=f'**{status}**', inline=False)
    embed.set_footer(text=f'Verificação realizada em {formatar_data()}')
    return embed

def _barra_progresso(valor: int, tamanho: int=10) -> str:
    preenchido = round(valor / 100 * tamanho)
    vazio = tamanho - preenchido
    if valor >= 70:
        bloco = '🟢'
    elif valor >= 50:
        bloco = '🟡'
    else:
        bloco = '🔴'
    return bloco * preenchido + '⚫' * vazio