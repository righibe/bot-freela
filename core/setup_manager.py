"""
Setup do servidor — modo leitura.

O bot NÃO cria, renomeia, move nem reposiciona canais e categorias: a staff
monta a estrutura do servidor como quiser e vincula cada função a um canal
com /configurar_canal (os IDs ficam gravados em config/settings.py).

No startup o bot apenas:
- garante os cargos do sistema (verificado, staff, termos, tecnologias);
- reposta os cards interativos nos canais já vinculados;
- avisa no log quais funções ainda estão sem canal.
"""

import logging
import os
import re

import discord

import config.settings as settings
from utils.persona import enviar_como_persona, caminho_banner

logger = logging.getLogger('bot_freeela.core.setup_manager')


# Registro central de funções → chave em settings.py.
# 'categoria': o vínculo deve apontar para uma categoria, não um canal de texto.
# 'card': o bot reposta um card interativo nesse canal.
FUNCOES_CANAL = {
    'comece_aqui':           {'attr': 'CANAL_COMECE_AQUI', 'label': '👋 Comece aqui (card de boas-vindas)', 'categoria': False, 'card': True},
    'regras':                {'attr': 'CANAL_REGRAS', 'label': '📕 Regras (card de regras)', 'categoria': False, 'card': True},
    'termos':                {'attr': 'CANAL_TERMOS', 'label': '📜 Termos de Uso (card + botão de aceite)', 'categoria': False, 'card': True},
    'verificar_dev':         {'attr': 'CANAL_VERIFICAR_DEV', 'label': '🧑‍💻 Verificar dev', 'categoria': False, 'card': True},
    'verificar_empregador':  {'attr': 'CANAL_VERIFICAR_EMPREGADOR', 'label': '🏢 Verificar empregador / criar projeto', 'categoria': False, 'card': True},
    'atualizar_perfil':      {'attr': 'CANAL_ATUALIZAR_PERFIL_DEV', 'label': '🔄 Atualizar perfil de dev', 'categoria': False, 'card': True},
    'sugerir_tecnologia':    {'attr': 'CANAL_SUGERIR_TEC', 'label': '💡 Sugerir tecnologia', 'categoria': False, 'card': True},
    'abrir_ticket':          {'attr': 'CANAL_ABRIR_TICKET', 'label': '🎫 Abrir ticket (painel de suporte)', 'categoria': False, 'card': True},
    'log_dev':               {'attr': 'CANAL_LOG_DEV', 'label': '🧾 Log de verificações (staff)', 'categoria': False, 'card': False},
    'log_projetos':          {'attr': 'CANAL_LOG_PROJETOS', 'label': '📊 Log de projetos (staff)', 'categoria': False, 'card': False},
    'categoria_projetos':    {'attr': 'CATEGORIA_PROJETOS_ID', 'label': '📂 Categoria das vitrines de projetos', 'categoria': True, 'card': False},
    'categoria_negociacao':  {'attr': 'CATEGORIA_NEGOCIACAO_ID', 'label': '🤝 Categoria dos canais de negociação', 'categoria': True, 'card': False},
    'categoria_tickets':     {'attr': 'CATEGORIA_TICKETS_ID', 'label': '🎟️ Categoria dos tickets abertos', 'categoria': True, 'card': False},
}

# Persona (nome visual + tema de avatar/banner) de cada canal com card
PERSONAS = {
    'comece_aqui': ('Freeela · Boas-Vindas', 'comece'),
    'regras': ('Freeela · Regras', 'regras'),
    'termos': ('Freeela · Jurídico', 'termos'),
    'verificar_dev': ('Freeela · Verificação', 'dev'),
    'verificar_empregador': ('Freeela · Contratações', 'emp'),
    'atualizar_perfil': ('Freeela · Perfis', 'perfil'),
    'sugerir_tecnologia': ('Freeela · Tecnologias', 'sugestao'),
    'abrir_ticket': ('Freeela · Suporte', 'ticket'),
}


def canal_da_funcao(guild: discord.Guild, chave: str):
    """Resolve o canal/categoria vinculado a uma função (ou None)."""
    cfg = FUNCOES_CANAL[chave]
    canal_id = getattr(settings, cfg['attr'], 0)
    if not canal_id:
        return None
    return guild.get_channel(canal_id)


async def setup_servidor(bot: discord.Client):
    if not bot.guilds:
        logger.warning('Bot não está em nenhum servidor para fazer o setup.')
        return
    guild = bot.guilds[0]
    logger.info('Iniciando setup (modo leitura) no servidor: %s', guild.name)

    # ── 1. Cargos do sistema (cargos não são canais — o bot ainda os garante) ──
    async def get_or_create_role(name, color=discord.Color.default()):
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, color=color, reason='Setup automático Freeela')
            logger.info('Criado cargo %s (ID: %s)', name, role.id)
        return role

    cargo_dev = await get_or_create_role('Desenvolvedor Verificado', discord.Color.blue())
    cargo_emp = await get_or_create_role('Empregador Verificado', discord.Color.green())
    cargo_staff = await get_or_create_role('Staff Freeela', discord.Color.red())
    cargo_termos = await get_or_create_role('Membro Freeela', discord.Color.teal())

    cargos_ids = {
        'CARGO_DEV_VERIFICADO': cargo_dev.id,
        'CARGO_EMPREGADOR_VERIFICADO': cargo_emp.id,
        'CARGO_STAFF': cargo_staff.id,
        'CARGO_TERMOS_ACEITOS': cargo_termos.id,
    }
    atualizar_settings({}, cargos_ids)
    for chave, valor in cargos_ids.items():
        setattr(settings, chave, valor)

    # ── 2. Cargos de tecnologia: garante um cargo por tecnologia ativa ──
    from core.tecnologias import garantir_cargos_ativos
    criados_tec = await garantir_cargos_ativos(guild)
    if criados_tec:
        logger.info('%d cargos de tecnologia criados', criados_tec)

    # ── 3. Cards nos canais vinculados pela staff ──
    postados, faltando = await repostar_todos_cards(guild)
    if postados:
        logger.info('Cards repostados em: %s', ', '.join(postados))
    if faltando:
        logger.warning(
            'Funções SEM canal vinculado (use /configurar_canal): %s',
            ', '.join(faltando),
        )

    # ── 4. Avatar do bot (aplicado uma única vez — rate limit do Discord) ──
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

    # ── 5. Varredura: quem já aceitou os Termos ganha o cargo de desbloqueio ──
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

    logger.info('Setup (modo leitura) finalizado.')


async def repostar_todos_cards(guild: discord.Guild) -> tuple[list[str], list[str]]:
    """
    Reposta os cards interativos nos canais vinculados.
    Retorna (funções postadas, funções sem canal vinculado).
    """
    postados: list[str] = []
    faltando: list[str] = []

    canais: dict[str, discord.TextChannel | None] = {}
    for chave, cfg in FUNCOES_CANAL.items():
        canal = canal_da_funcao(guild, chave)
        if cfg['categoria']:
            ok = isinstance(canal, discord.CategoryChannel)
        else:
            ok = isinstance(canal, discord.TextChannel)
        canais[chave] = canal if ok else None
        if not ok:
            faltando.append(chave)

    async def repostar_card(chave: str, embed: discord.Embed,
                            view_origem: discord.ui.View | None = None,
                            arquivo_extra=None):
        canal = canais.get(chave)
        if not canal:
            return
        from utils.cards import montar_card, embed_para_md, clonar_interativos
        try:
            # Limpa apenas mensagens do bot/webhooks — o que a staff escreveu fica
            await canal.purge(limit=10, check=lambda m: m.author.bot)
        except discord.errors.Forbidden:
            pass
        nome_persona, tema = PERSONAS[chave]
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
        postados.append(chave)

    # 👋 comece-aqui
    from embeds.boas_vindas_embed import criar_embed_boas_vindas
    await repostar_card(
        'comece_aqui',
        criar_embed_boas_vindas(
            canal_termos_id=settings.CANAL_TERMOS,
            canal_dev_id=settings.CANAL_VERIFICAR_DEV,
            canal_emp_id=settings.CANAL_VERIFICAR_EMPREGADOR,
            canal_ticket_id=settings.CANAL_ABRIR_TICKET,
        ),
    )

    # 📕 regras
    from embeds.regras_embed import criar_embed_regras_serias
    await repostar_card('regras', criar_embed_regras_serias())

    # 📜 termos-de-uso: resumo + PDF + botões de aceite
    from embeds.termos_embed import criar_embed_termos_resumo
    from views.termos_views import TermosAceiteView, TERMOS_PDF
    await repostar_card(
        'termos',
        criar_embed_termos_resumo(),
        view_origem=TermosAceiteView(),
        arquivo_extra=TERMOS_PDF if TERMOS_PDF.exists() else None,
    )

    # 🧑‍💻 verificar-dev
    from embeds.verificacao_embed import criar_embed_verificacao, criar_embed_atualizar_perfil
    from views.iniciar_verificacao import IniciarVerificacaoView
    await repostar_card(
        'verificar_dev', criar_embed_verificacao(), view_origem=IniciarVerificacaoView(),
    )

    # 🏢 verificar-empregador
    from embeds.empregador_embed import criar_embed_verificacao_empregador
    from views.empregador_views import IniciarEmpregadorView
    await repostar_card(
        'verificar_empregador', criar_embed_verificacao_empregador(),
        view_origem=IniciarEmpregadorView(),
    )

    # 🔄 atualizar-perfil
    from views.atualizar_perfil_dev import AtualizarPerfilDevView
    await repostar_card(
        'atualizar_perfil', criar_embed_atualizar_perfil(),
        view_origem=AtualizarPerfilDevView(),
    )

    # 💡 sugerir-tecnologia
    from embeds.tecnologia_embed import criar_embed_sugerir_tecnologia
    from views.tecnologia_views import SugerirTecnologiaView
    await repostar_card(
        'sugerir_tecnologia', criar_embed_sugerir_tecnologia(),
        view_origem=SugerirTecnologiaView(),
    )

    # 🎫 abrir-ticket
    from embeds.ticket_embed import criar_embed_abrir_ticket
    from views.ticket_views import AbrirTicketView
    await repostar_card(
        'abrir_ticket', criar_embed_abrir_ticket(), view_origem=AbrirTicketView(),
    )

    return postados, faltando


def atualizar_settings(canais: dict, cargos: dict):
    """Persiste IDs (canais/cargos) no config/settings.py."""
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
