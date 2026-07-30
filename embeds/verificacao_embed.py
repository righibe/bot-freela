import discord
from config.settings import COR_PRINCIPAL

def criar_embed_verificacao() -> discord.Embed:
    embed = discord.Embed(
        description=(
            '## Verifique-se e comece a faturar 💻\n\n'
            '**1.** Clique em **🚀 Iniciar Verificação**\n'
            '**2.** Cole seu **GitHub**, marque suas **linguagens** e experiência\n'
            '**3.** O bot confere e aprova **na hora** 🎉\n\n'
            '✅ Precisa de: **1+ ano** programando e GitHub com **repositórios públicos** '
            'mostrando pelo menos **2 linguagens**.'
        ),
        color=COR_PRINCIPAL,
    )
    embed.set_footer(text='Verificado? Cadastre seu PIX: /configurar_pagamento 💳')
    return embed

def criar_embed_resultado_dev(resultado) -> discord.Embed:
    from config.settings import COR_SUCESSO, COR_ALERTA, COR_ERRO
    cor = COR_SUCESSO if getattr(resultado, 'aprovado', False) else (COR_ALERTA if getattr(resultado, 'requires_review', False) else COR_ERRO)
    status = "✅ Aprovado" if getattr(resultado, 'aprovado', False) else "⏳ Em Revisão" if getattr(resultado, 'requires_review', False) else "❌ Reprovado"
    
    embed = discord.Embed(
        title='📊  Resultado da Verificação',
        description=f'O seu perfil foi analisado.\n\n**Status:** {status}',
        color=cor
    )
    
    compat = getattr(resultado, 'compatibilidade', 0)
    integ = getattr(resultado, 'integridade', 0)
    embed.add_field(name='Score de Compatibilidade', value=f'{compat}%', inline=True)
    embed.add_field(name='Score de Integridade', value=f'{integ}%', inline=True)
    
    langs = getattr(resultado, 'linguagens_confirmadas', [])
    if langs:
        embed.add_field(name='Linguagens Confirmadas', value=', '.join(langs), inline=False)
        
    motivos = getattr(resultado, 'motivos_reprovacao', [])
    if motivos:
        embed.add_field(name='Motivos de Atenção', value='\n'.join(f'• {m}' for m in motivos), inline=False)
        
    return embed

def criar_embed_aprovado(user: discord.Member) -> discord.Embed:
    from config.settings import COR_SUCESSO
    embed = discord.Embed(
        title='🎉  Verificação Concluída',
        description=f'Parabéns {user.mention}! Você foi aprovado e agora é um **Desenvolvedor Verificado**.',
        color=COR_SUCESSO
    )
    embed.set_footer(text='Os seus cargos foram atribuídos automaticamente.')
    return embed


def criar_embed_atualizar_perfil() -> discord.Embed:
    """Embed para devs verificados atualizarem seu perfil."""
    embed = discord.Embed(
        description=(
            '## Aprendeu coisa nova? Atualize seu perfil 🔄\n\n'
            'Para quem **já é verificado** — em 3 etapas rápidas:\n\n'
            '**1.** 🔗 Atualize seu **GitHub** e **LinkedIn** (já vêm preenchidos)\n'
            '**2.** 🛠️ Marque suas **tecnologias** de novo (as atuais já vêm selecionadas)\n'
            '**3.** 📈 Confirme sua **experiência** — o bot revalida e troca seus cargos na hora ✅\n\n'
            '⚠️ O GitHub é conferido de novo — só marque o que realmente aparece lá.'
        ),
        color=COR_PRINCIPAL,
    )
    embed.set_footer(text='Sua chave PIX não muda ao atualizar o perfil 💳')
    return embed
