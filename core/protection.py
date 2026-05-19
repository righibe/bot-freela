"""
Sistema de proteção: anti-spam, cooldowns, limites e validação de comportamento.
"""

import logging
import re
import time
from config.settings import (
    COOLDOWN_CANDIDATURA_SEGUNDOS,
    COOLDOWN_VERIFICACAO_SEGUNDOS,
    MAX_CANDIDATURAS_DIA,
    MAX_PROJETOS_ATIVOS_POR_DEV,
    DESCRICAO_MINIMA_INTERESSE,
    DESCRICAO_MINIMA_PROJETO,
    VALOR_MINIMO_PROJETO,
)
from core.database import (
    verificar_cooldown,
    registrar_cooldown,
    contar_candidaturas_dev_hoje,
    listar_projetos_ativos_dev,
    buscar_dev,
)

logger = logging.getLogger('bot_freeela.core.protection')

# Padrões suspeitos em descrições
PADROES_SUSPEITOS = [
    r'(?:compre|comprar|vend[oa]|vender)',
    r'(?:hack|exploit|crack|keygen|pirat)',
    r'(?:casino|apostar|bet\b)',
    r'(?:xxx|porn|nsfw)',
    r'(?:free\s*money|dinheiro\s*f[aá]cil|renda\s*extra)',
    r'(?:esquema|pirâmide|multinível|mlm\b)',
]

REGEX_SUSPEITO = re.compile('|'.join(PADROES_SUSPEITOS), re.IGNORECASE)


class ProtecaoResultado:
    """Resultado de uma verificação de proteção."""
    def __init__(self):
        self.permitido: bool = True
        self.motivos: list[str] = []

    def bloquear(self, motivo: str) -> None:
        self.permitido = False
        self.motivos.append(motivo)


def verificar_candidatura_permitida(dev_id: int) -> ProtecaoResultado:
    """
    Verifica se um dev pode se candidatar a um projeto.
    Checa cooldown, limite diário e projetos ativos.
    """
    resultado = ProtecaoResultado()

    # 1. Cooldown de candidatura
    cooldown_restante = verificar_cooldown(
        dev_id, 'candidatura', COOLDOWN_CANDIDATURA_SEGUNDOS
    )
    if cooldown_restante > 0:
        minutos = int(cooldown_restante // 60)
        segundos = int(cooldown_restante % 60)
        resultado.bloquear(
            f'Aguarde **{minutos}m {segundos}s** antes de se candidatar novamente.'
        )
        return resultado

    # 2. Limite de candidaturas por dia
    candidaturas_hoje = contar_candidaturas_dev_hoje(dev_id)
    if candidaturas_hoje >= MAX_CANDIDATURAS_DIA:
        resultado.bloquear(
            f'Você atingiu o limite de **{MAX_CANDIDATURAS_DIA} candidaturas** por dia.'
        )
        return resultado

    # 3. Projetos ativos
    ativos = listar_projetos_ativos_dev(dev_id)
    if len(ativos) >= MAX_PROJETOS_ATIVOS_POR_DEV:
        resultado.bloquear(
            f'Você já tem **{len(ativos)}/{MAX_PROJETOS_ATIVOS_POR_DEV}** '
            f'projetos ativos. Finalize um antes de aceitar outro.'
        )
        return resultado

    # 4. Verificar se o dev existe
    dev = buscar_dev(dev_id)
    if not dev:
        resultado.bloquear('Você não é um desenvolvedor verificado.')
        return resultado

    return resultado


def verificar_verificacao_permitida(user_id: int) -> ProtecaoResultado:
    """Verifica se um usuário pode iniciar uma verificação."""
    resultado = ProtecaoResultado()

    cooldown_restante = verificar_cooldown(
        user_id, 'verificacao', COOLDOWN_VERIFICACAO_SEGUNDOS
    )
    if cooldown_restante > 0:
        minutos = int(cooldown_restante // 60)
        resultado.bloquear(
            f'Aguarde **{minutos} minutos** antes de tentar verificar-se novamente.'
        )

    return resultado


def validar_descricao(descricao: str, min_chars: int = DESCRICAO_MINIMA_PROJETO) -> ProtecaoResultado:
    """Valida uma descrição contra spam e conteúdo suspeito."""
    resultado = ProtecaoResultado()

    texto = descricao.strip()

    if len(texto) < min_chars:
        resultado.bloquear(
            f'A descrição deve ter pelo menos **{min_chars} caracteres** '
            f'(atual: {len(texto)}).'
        )

    # Verificar conteúdo suspeito
    match = REGEX_SUSPEITO.search(texto)
    if match:
        resultado.bloquear(
            'A descrição contém conteúdo suspeito ou proibido. '
            'Revise e tente novamente.'
        )
        logger.warning(
            'Conteúdo suspeito detectado na descrição: "%s"', match.group()
        )

    # Verificar se é só repetição de caracteres
    if len(set(texto.replace(' ', ''))) < 5:
        resultado.bloquear(
            'A descrição parece ser spam (muito pouca variação de caracteres).'
        )

    return resultado


def validar_valor_projeto(valor: float) -> ProtecaoResultado:
    """Valida o valor de um projeto."""
    resultado = ProtecaoResultado()

    if valor < VALOR_MINIMO_PROJETO:
        resultado.bloquear(
            f'O valor mínimo para um projeto é **R$ {VALOR_MINIMO_PROJETO:.2f}**.'
        )

    return resultado


def verificar_conteudo_suspeito(texto: str) -> bool:
    """Retorna True se o texto contém padrões suspeitos."""
    return bool(REGEX_SUSPEITO.search(texto))
