import discord
from config.settings import COR_PRINCIPAL

def criar_embed_verificacao() -> discord.Embed:
    embed = discord.Embed(title='🔐  Verificação de Desenvolvedor', description='Para receber o cargo de **Desenvolvedor Verificado** e ter acesso completo ao servidor, você precisa passar por um processo de validação técnica.\n\nO processo analisa:\n>>> • Compatibilidade técnica com seu perfil\n• Integridade dos dados fornecidos\n• Coerência entre GitHub, LinkedIn e experiência\n\n', color=COR_PRINCIPAL)
    embed.add_field(name='📋  Como funciona?', value='```\n1️⃣ Selecione suas linguagens de programação\n2️⃣ Informe seu tempo de experiência\n3️⃣ Preencha seu perfil profissional\n4️⃣ Aguarde a validação automática\n```', inline=False)
    embed.add_field(name='⚙️  Requisitos mínimos', value='• Pelo menos **1 ano** de experiência em programação\n• Conta no **GitHub** com repositórios públicos\n• Perfil no **LinkedIn**\n• Mínimo de **2 linguagens** confirmadas no GitHub', inline=False)
    embed.add_field(name='⏱️  Tempo estimado', value='A verificação leva de **1 a 3 minutos**.', inline=True)
    embed.add_field(name='🔒  Privacidade', value='Seus dados são analisados em **thread privada**.', inline=True)
    embed.set_footer(text='Freeela • Verificação Dev', icon_url='https://cdn.discordapp.com/embed/avatars/0.png')
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