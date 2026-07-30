"""
Setup automático da estrutura do servidor.

- Cria/renomeia categorias e canais no padrão visual 'emoji・nome'.
- Reconhece canais existentes pelos nomes antigos (sem emoji) e os renomeia,
  em vez de criar duplicatas.
- Reposta os cards de cada canal usando personas (webhooks com nome e avatar
  temáticos) e banners gerados em assets/.
- Monta o sistema de tickets (categoria de abertura + categoria dos tickets).
"""

import logging
import os
import re
import unicodedata

import discord

from utils.persona import enviar_como_persona, caminho_banner

logger = logging.getLogger('bot_freeela.core.setup_manager')


def _slug_comparacao(nome: str) -> str:
    """Normaliza um nome de canal para comparação: sem emoji, acento ou separador."""
    nome = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '', nome.lower())


# Estrutura desejada do servidor.
# 'aliases' são nomes antigos que devem ser reconhecidos e renomeados.
CATEGORIAS = {
    'verificacao': {'nome': '🔐・VERIFICAÇÃO', 'aliases': ['Verificação']},
    'projetos':    {'nome': '📂・PROJETOS DISPONÍVEIS', 'aliases': ['Projetos Disponíveis']},
    'negociacao':  {'nome': '🤝・NEGOCIAÇÃO', 'aliases': ['Negociação']},
    'suporte':     {'nome': '🎫・SUPORTE', 'aliases': ['Suporte']},
    'tickets':     {'nome': '🎟️・TICKETS', 'aliases': ['Tickets']},
    'staff':       {'nome': '🛡️・STAFF', 'aliases': ['Staff']},
}

CANAIS = {
    'comece_aqui':      {'nome': '👋・comece-aqui', 'categoria': 'verificacao', 'aliases': ['comece-aqui', 'bem-vindo']},
    'termos':           {'nome': '📜・termos-de-uso', 'categoria': 'verificacao', 'aliases': ['termos-de-uso']},
    'verificar_dev':    {'nome': '🧑‍💻・verificar-dev', 'categoria': 'verificacao', 'aliases': ['verificar-dev']},
    'verificar_emp':    {'nome': '🏢・verificar-empregador', 'categoria': 'verificacao', 'aliases': ['verificar-empregador']},
    'atualizar_perfil': {'nome': '🔄・atualizar-perfil', 'categoria': 'verificacao', 'aliases': ['atualizar-perfil-dev', 'atualizar-perfil']},
    'sugerir_tec':      {'nome': '💡・sugerir-tecnologia', 'categoria': 'verificacao', 'aliases': ['sugerir-tecnologia']},
    'abrir_ticket':     {'nome': '🎫・abrir-ticket', 'categoria': 'suporte', 'aliases': ['abrir-ticket', 'suporte']},
    'log_dev':          {'nome': '🧾・log-dev', 'categoria': 'staff', 'aliases': ['log-dev']},
    'log_projetos':     {'nome': '📊・log-projetos', 'categoria': 'staff', 'aliases': ['log-projetos']},
}

# Persona (nome visual + tema de avatar/banner) de cada canal com card
PERSONAS = {
    'comece_aqui': ('Freeela · Boas-Vindas', 'comece'),
    'regras': ('Freeela · Regras', 'regras'),
    'termos': ('Freeela · Jurídico', 'termos'),
    'verificar_dev': ('Freeela · Verificação', 'dev'),
    'verificar_emp': ('Freeela · Contratações', 'emp'),
    'atualizar_perfil': ('Freeela · Perfis', 'perfil'),
    'sugerir_tec': ('Freeela · Tecnologias', 'sugestao'),
    'abrir_ticket': ('Freeela · Suporte', 'ticket'),
}


def _procurar_por_alias(colecao, nome_alvo: str, aliases: list[str]):
    """Procura um canal/categoria cujo nome normalizado bata com o alvo ou algum alias."""
    alvos = {_slug_comparacao(nome_alvo)} | {_slug_comparacao(a) for a in aliases}
    for item in colecao:
        if _slug_comparacao(item.name) in alvos:
            return item
    return None


async def setup_servidor(bot: discord.Client):
    if not bot.guilds:
        logger.warning('Bot não está em nenhum servidor para fazer o setup.')
        return
    guild = bot.guilds[0]
    logger.info('Iniciando setup automático de estrutura no servidor: %s', guild.name)

    canais_ids = {}
    cargos_ids = {}

    # ── 1. Cargos ──
    async def get_or_create_role(name, color=discord.Color.default()):
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, color=color, reason='Setup automático Freeela')
            logger.info('Criado cargo %s (ID: %s)', name, role.id)
        return role

    cargo_dev = await get_or_create_role('Desenvolvedor Verificado', discord.Color.blue())
    cargo_emp = await get_or_create_role('Empregador Verificado', discord.Color.green())
    cargo_staff = await get_or_create_role('Staff Freeela', discord.Color.red())
    # Cargo concedido ao aceitar os Termos — desbloqueia os canais de verificação
    cargo_termos = await get_or_create_role('Membro Freeela', discord.Color.teal())

    cargos_ids['CARGO_DEV_VERIFICADO'] = cargo_dev.id
    cargos_ids['CARGO_EMPREGADOR_VERIFICADO'] = cargo_emp.id
    cargos_ids['CARGO_STAFF'] = cargo_staff.id
    cargos_ids['CARGO_TERMOS_ACEITOS'] = cargo_termos.id

    # ── 2. Categorias (com renomeação para o padrão emoji・NOME) ──
    overrides_ocultos = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        cargo_staff: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
    }

    async def get_or_create_category(chave: str, overwrites=None) -> discord.CategoryChannel:
        cfg = CATEGORIAS[chave]
        categoria = _procurar_por_alias(guild.categories, cfg['nome'], cfg['aliases'])
        if not categoria:
            categoria = await guild.create_category(
                cfg['nome'], overwrites=overwrites or {}, reason='Setup automático Freeela'
            )
            logger.info('Criada categoria %s', cfg['nome'])
        elif categoria.name != cfg['nome']:
            await categoria.edit(name=cfg['nome'])
            logger.info('Categoria renomeada para %s', cfg['nome'])
        return categoria

    cat_verificacao = await get_or_create_category('verificacao')
    cat_projetos = await get_or_create_category('projetos')
    cat_negociacao = await get_or_create_category('negociacao')
    cat_suporte = await get_or_create_category('suporte')
    cat_tickets = await get_or_create_category('tickets', overwrites=overrides_ocultos)
    cat_staff = await get_or_create_category('staff')

    # Projetos disponíveis: visíveis para TODOS (vitrine), mas ninguém escreve —
    # a candidatura é só pelo botão, e apenas devs compatíveis conseguem.
    try:
        await cat_projetos.set_permissions(guild.default_role, read_messages=True, send_messages=False)
        await cat_projetos.set_permissions(
            guild.me, read_messages=True, send_messages=True, embed_links=True, manage_channels=True,
        )
    except Exception as e:
        logger.error('Erro ao ajustar permissões da categoria de projetos: %s', e)
    categorias = {
        'verificacao': cat_verificacao,
        'projetos': cat_projetos,
        'negociacao': cat_negociacao,
        'suporte': cat_suporte,
        'tickets': cat_tickets,
        'staff': cat_staff,
    }

    # ── 3. Canais (com renomeação para o padrão emoji・nome) ──
    bot_overwrite = discord.PermissionOverwrite(
        read_messages=True, send_messages=True, embed_links=True,
        attach_files=True, manage_webhooks=True,
    )
    overrides_leitura_apenas = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        guild.me: bot_overwrite,
    }
    # Canais bloqueados até o aceite dos Termos: invisíveis para @everyone,
    # visíveis (somente leitura) para quem tem o cargo Membro Freeela.
    overrides_bloqueado_termos = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        cargo_termos: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        cargo_staff: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: bot_overwrite,
    }
    overrides_staff = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        cargo_staff: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: bot_overwrite,
    }

    # Canais que exigem aceite dos Termos para serem vistos
    CANAIS_BLOQUEADOS = {'verificar_dev', 'verificar_emp', 'atualizar_perfil', 'sugerir_tec'}

    def _overrides_para(chave: str) -> dict:
        cfg = CANAIS[chave]
        if cfg['categoria'] == 'staff':
            return overrides_staff
        if chave in CANAIS_BLOQUEADOS:
            return overrides_bloqueado_termos
        return overrides_leitura_apenas

    async def get_or_create_channel(chave: str) -> discord.TextChannel:
        cfg = CANAIS[chave]
        categoria = categorias[cfg['categoria']]
        overrides = _overrides_para(chave)

        canal = _procurar_por_alias(guild.text_channels, cfg['nome'], cfg['aliases'])
        if not canal:
            canal = await guild.create_text_channel(cfg['nome'], category=categoria, overwrites=overrides)
            logger.info('Criado canal %s (ID: %s)', cfg['nome'], canal.id)
        else:
            edits = {}
            if canal.name != cfg['nome']:
                edits['name'] = cfg['nome']
            if canal.category_id != categoria.id:
                edits['category'] = categoria
            # Reaplicar o bloqueio por termos em canais já existentes
            if chave in CANAIS_BLOQUEADOS:
                edits['overwrites'] = overrides
            if edits:
                await canal.edit(**edits)
                logger.info('Canal %s ajustado (%s)', cfg['nome'], ', '.join(edits))
        return canal

    canal_comece = await get_or_create_channel('comece_aqui')
    canal_termos = await get_or_create_channel('termos')
    canal_verificar_dev = await get_or_create_channel('verificar_dev')
    canal_verificar_emp = await get_or_create_channel('verificar_emp')
    canal_atualizar_perfil = await get_or_create_channel('atualizar_perfil')
    canal_sugerir_tec = await get_or_create_channel('sugerir_tec')
    canal_abrir_ticket = await get_or_create_channel('abrir_ticket')
    canal_log_dev = await get_or_create_channel('log_dev')
    canal_log_projetos = await get_or_create_channel('log_projetos')

    # Garantir que comece-aqui fica no topo da categoria
    try:
        await canal_comece.edit(position=0)
    except Exception:
        pass

    canais_ids['CANAL_VERIFICAR_DEV'] = canal_verificar_dev.id
    canais_ids['CANAL_VERIFICAR_EMPREGADOR'] = canal_verificar_emp.id
    canais_ids['CANAL_ATUALIZAR_PERFIL_DEV'] = canal_atualizar_perfil.id
    canais_ids['CATEGORIA_PROJETOS_ID'] = cat_projetos.id
    canais_ids['CATEGORIA_NEGOCIACAO_ID'] = cat_negociacao.id
    canais_ids['CATEGORIA_TICKETS_ID'] = cat_tickets.id
    canais_ids['CANAL_ABRIR_TICKET'] = canal_abrir_ticket.id
    canais_ids['CANAL_LOG_DEV'] = canal_log_dev.id
    canais_ids['CANAL_LOG_PROJETOS'] = canal_log_projetos.id

    # ── 4. Canal de regras (ID fixo em settings.CANAL_REGRAS) ──
    import config.settings as settings
    canal_regras = guild.get_channel(settings.CANAL_REGRAS)
    if canal_regras and isinstance(canal_regras, discord.TextChannel):
        try:
            edits = {}
            if canal_regras.name != '📕・regras':
                edits['name'] = '📕・regras'
            if edits:
                await canal_regras.edit(**edits)
            await canal_regras.set_permissions(
                guild.default_role, read_messages=True, send_messages=False,
            )
        except Exception as e:
            logger.error('Erro ao ajustar canal de regras: %s', e)
    else:
        logger.warning('Canal de regras (%s) não encontrado — card de regras não postado', settings.CANAL_REGRAS)

    # ── 5. Cards de cada canal (Components V2: banner DENTRO do card) ──
    from utils.cards import montar_card, embed_para_md, clonar_interativos

    async def repostar_card(
        canal: discord.TextChannel,
        chave_persona: str,
        embed: discord.Embed,
        view_origem: discord.ui.View | None = None,
        arquivo_extra=None,
    ):
        """Limpa o canal e envia um card V2 (banner + texto + botões) como a persona."""
        try:
            await canal.purge(limit=10)
        except discord.errors.Forbidden:
            pass
        nome_persona, tema = PERSONAS[chave_persona]
        banner = caminho_banner(tema)
        card, file_paths = montar_card(
            texto=embed_para_md(embed),
            banner_path=banner if banner.exists() else None,
            itens=clonar_interativos(view_origem) if view_origem else None,
            arquivo_path=arquivo_extra,
            accent=settings.COR_CARD_ACCENT,
        )
        await enviar_como_persona(
            canal, nome_persona, tema,
            [{'view': card, 'file_paths': file_paths}],
        )

    # 👋 comece-aqui (card único e curto)
    from embeds.boas_vindas_embed import criar_embed_boas_vindas
    await repostar_card(
        canal_comece, 'comece_aqui',
        criar_embed_boas_vindas(
            canal_termos_id=canal_termos.id,
            canal_dev_id=canal_verificar_dev.id,
            canal_emp_id=canal_verificar_emp.id,
            canal_ticket_id=canal_abrir_ticket.id,
        ),
    )

    # 📕 regras (tom formal)
    if canal_regras and isinstance(canal_regras, discord.TextChannel):
        from embeds.regras_embed import criar_embed_regras_serias
        await repostar_card(canal_regras, 'regras', criar_embed_regras_serias())

    # 📜 termos-de-uso: resumo + PDF + botões de aceite
    from embeds.termos_embed import criar_embed_termos_resumo
    from views.termos_views import TermosAceiteView, TERMOS_PDF
    await repostar_card(
        canal_termos, 'termos',
        criar_embed_termos_resumo(),
        view_origem=TermosAceiteView(),
        arquivo_extra=TERMOS_PDF if TERMOS_PDF.exists() else None,
    )

    # 🧑‍💻 verificar-dev
    from embeds.verificacao_embed import criar_embed_verificacao, criar_embed_atualizar_perfil
    from views.iniciar_verificacao import IniciarVerificacaoView
    await repostar_card(
        canal_verificar_dev, 'verificar_dev',
        criar_embed_verificacao(), view_origem=IniciarVerificacaoView(),
    )

    # 🏢 verificar-empregador
    from embeds.empregador_embed import criar_embed_verificacao_empregador
    from views.empregador_views import IniciarEmpregadorView
    await repostar_card(
        canal_verificar_emp, 'verificar_emp',
        criar_embed_verificacao_empregador(), view_origem=IniciarEmpregadorView(),
    )

    # 🔄 atualizar-perfil
    from views.atualizar_perfil_dev import AtualizarPerfilDevView
    await repostar_card(
        canal_atualizar_perfil, 'atualizar_perfil',
        criar_embed_atualizar_perfil(), view_origem=AtualizarPerfilDevView(),
    )

    # 💡 sugerir-tecnologia
    from embeds.tecnologia_embed import criar_embed_sugerir_tecnologia
    from views.tecnologia_views import SugerirTecnologiaView
    await repostar_card(
        canal_sugerir_tec, 'sugerir_tec',
        criar_embed_sugerir_tecnologia(), view_origem=SugerirTecnologiaView(),
    )

    # 🎫 abrir-ticket (estilo "Painel de Suporte" da referência)
    from embeds.ticket_embed import criar_embed_abrir_ticket
    from views.ticket_views import AbrirTicketView
    await repostar_card(
        canal_abrir_ticket, 'abrir_ticket',
        criar_embed_abrir_ticket(), view_origem=AbrirTicketView(),
    )

    # ── 5.1 Cargos de tecnologia: garante um cargo por tecnologia ativa ──
    from core.tecnologias import garantir_cargos_ativos
    criados_tec = await garantir_cargos_ativos(guild)
    if criados_tec:
        logger.info('%d cargos de tecnologia criados', criados_tec)

    # ── 6. Persistir IDs no settings.py e em memória ──
    atualizar_settings(canais_ids, cargos_ids)

    for chave, valor in {**canais_ids, **cargos_ids}.items():
        setattr(settings, chave, valor)

    # ── 6.1 Avatar do bot principal (aplicado uma única vez — rate limit do Discord) ──
    from pathlib import Path
    avatar_bot = Path(__file__).parent.parent / 'assets' / 'avatars' / 'bot.png'
    flag_avatar = Path(__file__).parent.parent / 'data' / '.avatar_bot_aplicado'
    if avatar_bot.exists() and not flag_avatar.exists():
        try:
            await bot.user.edit(avatar=avatar_bot.read_bytes())
            flag_avatar.write_text('ok', encoding='utf-8')
            logger.info('Avatar do bot atualizado para a identidade Freeela')
        except discord.HTTPException as e:
            logger.warning('Não foi possível atualizar o avatar do bot agora: %s', e)

    # ── 7. Varredura: quem já aceitou os Termos ganha o cargo de desbloqueio ──
    from core.database import usuario_aceitou_termos
    concedidos = 0
    for member in guild.members:
        if member.bot or cargo_termos in member.roles:
            continue
        if usuario_aceitou_termos(member.id, settings.TERMOS_VERSAO):
            try:
                await member.add_roles(cargo_termos, reason='Já aceitou os Termos de Uso')
                concedidos += 1
            except discord.Forbidden:
                pass
    if concedidos:
        logger.info('Cargo Membro Freeela concedido retroativamente a %d membros', concedidos)

    logger.info('Setup da estrutura finalizado com sucesso.')


def atualizar_settings(canais, cargos):
    try:
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.py')
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()

        for key, val in {**canais, **cargos}.items():
            content = re.sub(rf'^{key}\s*=\s*\d+', f'{key} = {val}', content, flags=re.MULTILINE)

        with open(settings_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info('Arquivo settings.py atualizado com os IDs corretos.')
    except Exception as e:
        logger.error('Erro ao atualizar settings.py: %s', e)
