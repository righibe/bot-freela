"""
Motor de matching entre devs e projetos.
Verifica compatibilidade de linguagens, experiência e disponibilidade.
"""

import logging
from core.database import (
    DevVerificado, Projeto, buscar_dev, listar_projetos_ativos_dev
)
from config.settings import MAX_PROJETOS_ATIVOS_POR_DEV

logger = logging.getLogger('bot_freeela.core.matching')

# Mapeamento de senioridade para nível numérico
NIVEL_EXPERIENCIA = {
    'junior': 1,
    'pleno': 2,
    'senior': 3,
    'qualquer': 0,
}

EXPERIENCIA_DEV_NIVEL = {
    '6_meses': 0,
    '1_ano': 1,
    '2_anos': 2,
    '4_6_anos': 3,
    '6_mais': 3,
}


def verificar_compatibilidade_dev_projeto(dev: DevVerificado, projeto: Projeto) -> dict:
    """
    Verifica se um dev é compatível com um projeto.

    Retorna:
        {
            'compativel': bool,
            'linguagens_match': list[str],
            'linguagens_faltando': list[str],
            'experiencia_ok': bool,
            'disponibilidade_ok': bool,
            'motivos_rejeicao': list[str],
            'score_match': int,
        }
    """
    resultado = {
        'compativel': False,
        'linguagens_match': [],
        'linguagens_faltando': [],
        'experiencia_ok': False,
        'disponibilidade_ok': False,
        'motivos_rejeicao': [],
        'score_match': 0,
    }

    # 1. Verificar linguagens — dev precisa ter pelo menos 2 linguagens do projeto
    langs_dev = set(dev.linguagens_confirmadas)
    langs_projeto = set(projeto.linguagens_requeridas)

    match = langs_dev & langs_projeto
    faltando = langs_projeto - langs_dev

    resultado['linguagens_match'] = sorted(match)
    resultado['linguagens_faltando'] = sorted(faltando)

    if len(match) < 2:
        resultado['motivos_rejeicao'].append(
            f'Você tem apenas {len(match)} linguagem(s) compatível(is) '
            f'com o projeto (mínimo: 2). '
            f'Requeridas: {", ".join(langs_projeto)}'
        )
    else:
        resultado['score_match'] += 40

    # 2. Verificar experiência
    nivel_dev = EXPERIENCIA_DEV_NIVEL.get(dev.experiencia, 0)
    nivel_requerido = NIVEL_EXPERIENCIA.get(projeto.experiencia_minima, 0)

    if nivel_requerido > 0 and nivel_dev < nivel_requerido:
        resultado['motivos_rejeicao'].append(
            f'Seu nível de experiência ({dev.senioridade}) '
            f'não atende ao mínimo exigido ({projeto.experiencia_minima}).'
        )
    else:
        resultado['experiencia_ok'] = True
        resultado['score_match'] += 30

    # 3. Verificar disponibilidade (limite de projetos ativos)
    projetos_ativos = listar_projetos_ativos_dev(dev.user_id)
    if len(projetos_ativos) >= MAX_PROJETOS_ATIVOS_POR_DEV:
        resultado['motivos_rejeicao'].append(
            f'Você atingiu o limite de {MAX_PROJETOS_ATIVOS_POR_DEV} projetos ativos.'
        )
    else:
        resultado['disponibilidade_ok'] = True
        resultado['score_match'] += 20

    # 4. Bonus por score de compatibilidade alto
    if dev.compatibilidade >= 80:
        resultado['score_match'] += 10

    resultado['score_match'] = min(resultado['score_match'], 100)
    resultado['compativel'] = len(resultado['motivos_rejeicao']) == 0

    return resultado


def rankear_devs_para_projeto(projeto: Projeto, devs: list[DevVerificado]) -> list[dict]:
    """
    Rankeia devs compatíveis para um projeto.

    Retorna lista ordenada por score_match (maior primeiro).
    """
    resultados = []
    for dev in devs:
        compat = verificar_compatibilidade_dev_projeto(dev, projeto)
        if compat['compativel']:
            resultados.append({
                'dev': dev,
                'match': compat,
            })

    resultados.sort(key=lambda x: x['match']['score_match'], reverse=True)
    return resultados
