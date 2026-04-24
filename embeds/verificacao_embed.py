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