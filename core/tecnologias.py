"""
Serviço de tecnologias — a ponte entre o banco (fonte da verdade) e os
cargos do Discord.

- Cada tecnologia ativa tem (ou ganha) um cargo próprio no servidor.
- Cargos são criados sob demanda e o ID é persistido no banco.
- A sincronização aplica/remove os cargos de tecnologia de um membro
  conforme o que está salvo no perfil dele.
"""

import logging

import discord

from config.settings import LINGUAGENS_ALIASES, MAX_TECNOLOGIAS_POR_DEV
from core.database import (
    Tecnologia, listar_tecnologias, buscar_tecnologia, salvar_tecnologia,
    atualizar_cargo_tecnologia, atualizar_status_tecnologia,
)

logger = logging.getLogger('bot_freeela.core.tecnologias')

COR_CARGO_TECNOLOGIA = discord.Color.from_str('#5793e6')


def nomes_ativas() -> list[str]:
    """Nomes de todas as tecnologias ativas, em ordem alfabética."""
    return [t.nome for t in listar_tecnologias('ativa')]


def mapa_cargos() -> dict[str, int]:
    """{nome da tecnologia: cargo_id} das tecnologias ativas com cargo."""
    return {t.nome: t.cargo_id for t in listar_tecnologias('ativa') if t.cargo_id}


def normalizar_nome(texto: str) -> str | None:
    """
    Resolve um texto digitado para o nome canônico de uma tecnologia ativa.
    Aceita aliases comuns ('js' -> JavaScript não; 'golang'/'go' -> Golang).
    Retorna None se não existir.
    """
    texto = texto.strip()
    if not texto:
        return None
    tec = buscar_tecnologia(texto)
    if tec and tec.status == 'ativa':
        return tec.nome
    alias = LINGUAGENS_ALIASES.get(texto.lower())
    if alias:
        tec = buscar_tecnologia(alias)
        if tec and tec.status == 'ativa':
            return tec.nome
    return None


async def garantir_cargo(guild: discord.Guild, nome: str) -> discord.Role | None:
    """
    Retorna o cargo Discord de uma tecnologia, criando-o se necessário
    (e persistindo o ID no banco).
    """
    tec = buscar_tecnologia(nome)
    if not tec:
        return None

    if tec.cargo_id:
        cargo = guild.get_role(tec.cargo_id)
        if cargo:
            return cargo

    # Procurar por nome antes de criar (evita duplicar cargos existentes)
    cargo = discord.utils.get(guild.roles, name=tec.nome)
    if not cargo:
        try:
            cargo = await guild.create_role(
                name=tec.nome,
                color=COR_CARGO_TECNOLOGIA,
                reason=f'Cargo automático da tecnologia {tec.nome}',
            )
            logger.info('Cargo criado para tecnologia %s (ID: %d)', tec.nome, cargo.id)
        except discord.Forbidden:
            logger.error('Sem permissão para criar cargo da tecnologia %s', tec.nome)
            return None
    atualizar_cargo_tecnologia(tec.nome, cargo.id)
    return cargo


async def garantir_cargos_ativos(guild: discord.Guild) -> int:
    """Garante que toda tecnologia ativa tem cargo. Retorna quantos foram criados."""
    criados = 0
    for tec in listar_tecnologias('ativa'):
        tinha = bool(tec.cargo_id and guild.get_role(tec.cargo_id))
        cargo = await garantir_cargo(guild, tec.nome)
        if cargo and not tinha:
            criados += 1
    return criados


async def sincronizar_cargos_membro(
    member: discord.Member,
    tecnologias_do_dev: list[str],
    remover_antigos: bool = True,
) -> None:
    """
    Aplica no membro os cargos das tecnologias do perfil dele e,
    opcionalmente, remove cargos de tecnologia que não estão mais no perfil.
    """
    guild = member.guild
    mapa = mapa_cargos()

    desejados = set()
    for nome in tecnologias_do_dev:
        cargo = await garantir_cargo(guild, nome)
        if cargo:
            desejados.add(cargo.id)

    todos_cargos_tec = set(mapa.values()) | desejados

    adicionar = [
        guild.get_role(cid) for cid in desejados
        if cid not in {r.id for r in member.roles} and guild.get_role(cid)
    ]
    remover = []
    if remover_antigos:
        remover = [
            r for r in member.roles
            if r.id in todos_cargos_tec and r.id not in desejados
        ]

    try:
        if adicionar:
            await member.add_roles(*adicionar, reason='Sincronização de tecnologias do perfil')
        if remover:
            await member.remove_roles(*remover, reason='Sincronização de tecnologias do perfil')
    except discord.Forbidden:
        logger.error('Sem permissão para sincronizar cargos de %s', member.name)


def validar_lista_tecnologias(texto: str) -> tuple[list[str], list[str]]:
    """
    Interpreta uma lista digitada ('python, react, node.js') e valida contra
    o banco. Retorna (nomes_canonicos_validos, entradas_invalidas).
    Respeita o limite de MAX_TECNOLOGIAS_POR_DEV.
    """
    validas: list[str] = []
    invalidas: list[str] = []
    for parte in texto.split(','):
        parte = parte.strip()
        if not parte:
            continue
        nome = normalizar_nome(parte)
        if nome and nome not in validas:
            validas.append(nome)
        elif not nome:
            invalidas.append(parte)
    return validas[:MAX_TECNOLOGIAS_POR_DEV], invalidas


def sugerir_tecnologia(nome: str, user_id: int) -> tuple[bool, str]:
    """
    Registra uma sugestão de tecnologia.
    Retorna (ok, mensagem para o usuário).
    """
    nome = ' '.join(nome.split())[:40]
    if len(nome) < 2:
        return False, '❌ Nome muito curto.'
    existente = buscar_tecnologia(nome)
    if existente:
        if existente.status == 'ativa':
            return False, f'⚠️ **{existente.nome}** já existe na plataforma!'
        if existente.status == 'sugerida':
            return False, f'⏳ **{existente.nome}** já foi sugerida e está em análise pela staff.'
        return False, f'❌ **{existente.nome}** já foi analisada e recusada pela staff.'
    salvar_tecnologia(Tecnologia(nome=nome, status='sugerida', sugerida_por=user_id))
    return True, (
        f'💡 Sugestão de **{nome}** enviada para a staff! '
        f'Você será avisado por DM quando ela for analisada.'
    )


async def aprovar_sugestao(guild: discord.Guild, nome: str) -> discord.Role | None:
    """Ativa uma tecnologia sugerida e cria o cargo."""
    atualizar_status_tecnologia(nome, 'ativa')
    return await garantir_cargo(guild, nome)


def rejeitar_sugestao(nome: str) -> None:
    atualizar_status_tecnologia(nome, 'rejeitada')
