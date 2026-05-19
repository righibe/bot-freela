import logging
import discord
import os
import re

logger = logging.getLogger('bot_freeela.core.setup_manager')

async def setup_servidor(bot: discord.Client):
    if not bot.guilds:
        logger.warning('Bot não está em nenhum servidor para fazer o setup.')
        return
    guild = bot.guilds[0]
    logger.info('Iniciando verificação e setup automático de estrutura no servidor: %s', guild.name)

    # Definir estrutura esperada
    categorias_esperadas = ['Verificação', 'Projetos Disponíveis', 'Negociação', 'Staff']
    
    # Dicionário para armazenar IDs encontrados/criados
    canais_ids = {}
    cargos_ids = {}

    # 1. Configurar Cargos
    nome_cargo_dev = 'Desenvolvedor Verificado'
    nome_cargo_emp = 'Empregador Verificado'
    nome_cargo_staff = 'Staff Freeela'

    async def get_or_create_role(name, color=discord.Color.default()):
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, color=color, reason='Setup automático Freeela')
            logger.info('Criado cargo %s (ID: %s)', name, role.id)
        else:
            logger.info('Cargo %s encontrado (ID: %s)', name, role.id)
        return role

    cargo_dev = await get_or_create_role(nome_cargo_dev, discord.Color.blue())
    cargo_emp = await get_or_create_role(nome_cargo_emp, discord.Color.green())
    cargo_staff = await get_or_create_role(nome_cargo_staff, discord.Color.red())

    cargos_ids['CARGO_DEV_VERIFICADO'] = cargo_dev.id
    cargos_ids['CARGO_EMPREGADOR_VERIFICADO'] = cargo_emp.id
    cargos_ids['CARGO_STAFF'] = cargo_staff.id

    # 2. Configurar Categorias e Canais
    async def get_or_create_category(name):
        category = discord.utils.get(guild.categories, name=name)
        if not category:
            category = await guild.create_category(name)
            logger.info('Criada categoria %s', name)
        return category

    cat_verificacao = await get_or_create_category('Verificação')
    cat_projetos = await get_or_create_category('Projetos Disponíveis')
    cat_negociacao = await get_or_create_category('Negociação')
    cat_staff = await get_or_create_category('Staff')

    async def get_or_create_channel(name, category, overrides=None):
        channel = discord.utils.get(guild.text_channels, name=name)
        if not channel:
            channel = await guild.create_text_channel(name, category=category, overwrites=overrides)
            logger.info('Criado canal %s (ID: %s)', name, channel.id)
        else:
            # Garante que está na categoria correta
            if channel.category_id != category.id:
                await channel.edit(category=category)
            logger.info('Canal %s encontrado (ID: %s)', name, channel.id)
        return channel

    # Permissões Padrão para canais de leitura apenas (Verificação, Projetos Disponíveis)
    overrides_leitura_apenas = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
    }

    # Permissões Staff
    overrides_staff = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        cargo_staff: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
    }

    # Canais de Verificação
    canal_verificar_dev = await get_or_create_channel('verificar-dev', cat_verificacao, overrides_leitura_apenas)
    canal_verificar_emp = await get_or_create_channel('verificar-empregador', cat_verificacao, overrides_leitura_apenas)
    canal_atualizar_perfil = await get_or_create_channel('atualizar-perfil-dev', cat_verificacao, overrides_leitura_apenas)
    canais_ids['CANAL_VERIFICAR_DEV'] = canal_verificar_dev.id
    canais_ids['CANAL_VERIFICAR_EMPREGADOR'] = canal_verificar_emp.id
    canais_ids['CANAL_ATUALIZAR_PERFIL_DEV'] = canal_atualizar_perfil.id

    # A categoria projetos já existe e será usada como container
    # Removido a criação do canal único projetos-disponiveis.
    canais_ids['CATEGORIA_PROJETOS_ID'] = cat_projetos.id
    canais_ids['CATEGORIA_NEGOCIACAO_ID'] = cat_negociacao.id

    # Canais Staff (Review e Diagnóstico)
    canal_log_dev = await get_or_create_channel('log-dev', cat_staff, overrides_staff)
    canal_log_projetos = await get_or_create_channel('log-projetos', cat_staff, overrides_staff)
    
    canais_ids['CANAL_LOG_DEV'] = canal_log_dev.id
    canais_ids['CANAL_LOG_PROJETOS'] = canal_log_projetos.id

    # Enviar primeira mensagem (embed)
    from embeds.verificacao_embed import criar_embed_verificacao
    from views.iniciar_verificacao import IniciarVerificacaoView
    
    async def verificar_e_enviar(canal, embed_func, view_class):
        logger.info('Limpando e re-enviando embed inicial no canal %s...', canal.name)
        try:
            await canal.purge(limit=10)
        except discord.errors.Forbidden:
            pass
        view = view_class()
        await canal.send(embed=embed_func(), view=view)
        # Parar a view local para que apenas a view global (registrada no bot) ouça o evento
        view.stop()

    await verificar_e_enviar(canal_verificar_dev, criar_embed_verificacao, IniciarVerificacaoView)
    
    from embeds.empregador_embed import criar_embed_verificacao_empregador
    from views.empregador_views import IniciarEmpregadorView
    await verificar_e_enviar(canal_verificar_emp, criar_embed_verificacao_empregador, IniciarEmpregadorView)

    # Enviar embed de atualização de perfil no canal atualizar-perfil-dev
    from embeds.verificacao_embed import criar_embed_atualizar_perfil
    from views.atualizar_perfil_dev import AtualizarPerfilDevView
    await verificar_e_enviar(canal_atualizar_perfil, criar_embed_atualizar_perfil, AtualizarPerfilDevView)

    # Atualizar config/settings.py para injetar os IDs reais no lugar dos 0s ou hardcodes antigos
    atualizar_settings(canais_ids, cargos_ids)
    
    # Atualizar o módulo settings importado em memória
    import config.settings as settings
    settings.CANAL_VERIFICAR_DEV = canais_ids['CANAL_VERIFICAR_DEV']
    settings.CANAL_VERIFICAR_EMPREGADOR = canais_ids['CANAL_VERIFICAR_EMPREGADOR']
    settings.CANAL_ATUALIZAR_PERFIL_DEV = canais_ids['CANAL_ATUALIZAR_PERFIL_DEV']
    settings.CATEGORIA_PROJETOS_ID = canais_ids['CATEGORIA_PROJETOS_ID']
    settings.CATEGORIA_NEGOCIACAO_ID = canais_ids['CATEGORIA_NEGOCIACAO_ID']
    settings.CANAL_LOG_DEV = canais_ids['CANAL_LOG_DEV']
    settings.CANAL_LOG_PROJETOS = canais_ids['CANAL_LOG_PROJETOS']
    
    settings.CARGO_DEV_VERIFICADO = cargos_ids['CARGO_DEV_VERIFICADO']
    settings.CARGO_EMPREGADOR_VERIFICADO = cargos_ids['CARGO_EMPREGADOR_VERIFICADO']
    settings.CARGO_STAFF = cargos_ids['CARGO_STAFF']

    logger.info('Setup da estrutura finalizado com sucesso.')


def atualizar_settings(canais, cargos):
    try:
        import os
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.py')
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()

        for key, val in canais.items():
            content = re.sub(rf'^{key}\s*=\s*\d+', f'{key} = {val}', content, flags=re.MULTILINE)
            
        for key, val in cargos.items():
            content = re.sub(rf'^{key}\s*=\s*\d+', f'{key} = {val}', content, flags=re.MULTILINE)

        with open(settings_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info('Arquivo settings.py atualizado com os IDs corretos.')
    except Exception as e:
        logger.error('Erro ao atualizar settings.py: %s', e)
