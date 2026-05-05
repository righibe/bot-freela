"""
Rota POST /validate/employer — Validação de empregadores e projetos.

Analisa coerência entre descrição, categoria, valor e complexidade.
Usa palavras-chave internas por categoria para detecção.
"""

import logging
import re
from fastapi import APIRouter

from api.models.employer_models import EmployerValidationRequest, EmployerValidationResponse
from config.settings import (
    PALAVRAS_CHAVE_CATEGORIA,
    CATEGORIAS_PROJETO,
    VALOR_MINIMO_PROJETO,
    VALOR_MAXIMO_PROJETO,
    DESCRICAO_MINIMA_PROJETO,
    SCORE_EMPREGADOR_MIN,
)
from core.protection import validar_descricao, validar_valor_projeto, verificar_conteudo_suspeito

logger = logging.getLogger('bot_freeela.api.validate_employer')
router = APIRouter()

# Faixas de valor por complexidade estimada
COMPLEXIDADE_FAIXAS = {
    'baixa': (50, 500),
    'média': (300, 5000),
    'alta': (2000, 50000),
    'muito_alta': (10000, 500000),
}

# Indicadores de complexidade na descrição
INDICADORES_COMPLEXIDADE = {
    'muito_alta': [
        'machine learning', 'inteligência artificial', 'blockchain',
        'arquitetura distribuída', 'microserviços', 'kubernetes',
        'infraestrutura', 'escalável', 'multi-tenant', 'tempo real',
    ],
    'alta': [
        'dashboard', 'painel administrativo', 'e-commerce', 'plataforma',
        'integração', 'api complexa', 'autenticação avançada', 'sistema completo',
        'deploy', 'ci/cd', 'websocket',
    ],
    'média': [
        'crud', 'api rest', 'bot', 'landing page', 'formulário',
        'automação', 'scraping', 'frontend', 'backend simples',
    ],
    'baixa': [
        'simples', 'básico', 'correção', 'ajuste', 'melhoria',
        'pequeno', 'script', 'fix',
    ],
}


def _detectar_categoria(descricao: str, titulo: str, tipo_declarado: str) -> tuple[str, bool]:
    """
    Detecta a categoria real do projeto baseado na descrição e título.
    Retorna (categoria_detectada, coerente_com_declarada).
    """
    texto = f'{titulo} {descricao}'.lower()
    scores: dict[str, int] = {}

    for categoria, palavras in PALAVRAS_CHAVE_CATEGORIA.items():
        score = 0
        for palavra in palavras:
            if palavra.lower() in texto:
                score += 1
        if score > 0:
            scores[categoria] = score

    if not scores:
        return tipo_declarado if tipo_declarado in CATEGORIAS_PROJETO else 'Outro', True

    categoria_detectada = max(scores, key=scores.get)
    coerente = (
        tipo_declarado == categoria_detectada
        or tipo_declarado in scores
        or tipo_declarado == 'Outro'
    )

    return categoria_detectada, coerente


def _estimar_complexidade(descricao: str) -> str:
    """Estima a complexidade do projeto baseado na descrição."""
    texto = descricao.lower()

    for nivel in ['muito_alta', 'alta', 'média', 'baixa']:
        indicadores = INDICADORES_COMPLEXIDADE[nivel]
        matches = sum(1 for ind in indicadores if ind in texto)
        if matches >= 2:
            return nivel

    # Heurísticas adicionais
    palavras = len(descricao.split())
    if palavras > 100:
        return 'alta'
    elif palavras > 50:
        return 'média'
    return 'baixa'


def _verificar_valor_vs_complexidade(valor: float, complexidade: str) -> tuple[bool, str]:
    """Verifica se o valor é coerente com a complexidade estimada."""
    faixa = COMPLEXIDADE_FAIXAS.get(complexidade, (50, 500000))
    min_val, max_val = faixa

    if valor < min_val * 0.5:
        return False, (
            f'O valor R$ {valor:.2f} parece muito baixo para um projeto de '
            f'complexidade {complexidade} (faixa esperada: R$ {min_val:.0f} — R$ {max_val:.0f}).'
        )
    elif valor > max_val * 2:
        return False, (
            f'O valor R$ {valor:.2f} parece muito alto para um projeto de '
            f'complexidade {complexidade} (faixa esperada: R$ {min_val:.0f} — R$ {max_val:.0f}).'
        )

    return True, ''


def _verificar_linguagens_vs_categoria(linguagens: list[str], categoria: str) -> tuple[bool, str]:
    """Verifica se as linguagens fazem sentido para a categoria."""
    # Combinações comuns
    combos_esperadas = {
        'Mobile': {'Kotlin', 'Swift', 'JavaScript', 'TypeScript', 'Java'},
        'Web App': {'JavaScript', 'TypeScript', 'Python', 'Ruby', 'Java'},
        'API / Backend': {'Python', 'Java', 'Golang', 'Rust', 'Ruby', 'C#', 'Kotlin', 'TypeScript', 'JavaScript'},
        'Bots': {'Python', 'JavaScript', 'TypeScript', 'Java'},
        'Data / ML': {'Python', 'Rust'},
        'Jogos': {'C/C++', 'C#', 'Python', 'Rust', 'Java'},
        'Desktop': {'C/C++', 'C#', 'Python', 'Java', 'Rust'},
    }

    esperadas = combos_esperadas.get(categoria)
    if not esperadas:
        return True, ''

    langs_set = set(linguagens)
    match = langs_set & esperadas

    if len(match) == 0 and len(linguagens) > 0:
        return False, (
            f'As linguagens declaradas ({", ".join(linguagens)}) não são '
            f'comuns para projetos da categoria "{categoria}".'
        )

    return True, ''


@router.post('/validate/employer', response_model=EmployerValidationResponse)
async def validate_employer(req: EmployerValidationRequest) -> EmployerValidationResponse:
    """
    Valida um empregador e seu projeto.
    Analisa coerência entre descrição, categoria, valor e complexidade.
    """
    response = EmployerValidationResponse()
    score = 100  # Começa com 100 e vai penalizando
    detalhes = []
    problemas = []
    sugestoes = []

    # 1. Validar descrição (anti-spam + tamanho)
    desc_check = validar_descricao(req.descricao, DESCRICAO_MINIMA_PROJETO)
    if not desc_check.permitido:
        problemas.extend(desc_check.motivos)
        score -= 30

    # 2. Validar valor
    valor_check = validar_valor_projeto(req.valor)
    if not valor_check.permitido:
        problemas.extend(valor_check.motivos)
        score -= 20
    response.valor_coerente = valor_check.permitido

    # 3. Detectar categoria
    categoria_detectada, categoria_coerente = _detectar_categoria(
        req.descricao, req.titulo, req.tipo_projeto
    )
    response.categoria_detectada = categoria_detectada
    response.categoria_coerente = categoria_coerente

    if categoria_coerente:
        detalhes.append(f'✅ Categoria "{req.tipo_projeto}" coerente com a descrição.')
        score += 0  # Não penaliza
    else:
        detalhes.append(
            f'⚠️ Categoria declarada "{req.tipo_projeto}" difere da detectada '
            f'"{categoria_detectada}". Pode indicar erro ou incoerência.'
        )
        score -= 10
        sugestoes.append(
            f'Considere alterar a categoria para "{categoria_detectada}".'
        )

    # 4. Estimar complexidade
    complexidade = _estimar_complexidade(req.descricao)
    response.complexidade_estimada = complexidade
    detalhes.append(f'📊 Complexidade estimada: {complexidade}')

    # 5. Verificar valor vs complexidade
    valor_ok, valor_msg = _verificar_valor_vs_complexidade(req.valor, complexidade)
    if not valor_ok:
        problemas.append(valor_msg)
        score -= 15
        response.valor_coerente = False
    else:
        detalhes.append(f'✅ Valor R$ {req.valor:.2f} coerente com a complexidade.')
        response.valor_coerente = True

    # 6. Verificar linguagens vs categoria
    langs_ok, langs_msg = _verificar_linguagens_vs_categoria(
        req.linguagens, req.tipo_projeto
    )
    if not langs_ok:
        sugestoes.append(langs_msg)
        score -= 5

    # 7. Verificar descrição suficiente
    palavras = len(req.descricao.split())
    if palavras >= 30:
        response.descricao_coerente = True
        detalhes.append(f'✅ Descrição detalhada ({palavras} palavras).')
    elif palavras >= 15:
        response.descricao_coerente = True
        detalhes.append(f'⚠️ Descrição razoável ({palavras} palavras). Considere detalhar mais.')
        score -= 5
    else:
        response.descricao_coerente = False
        problemas.append(f'Descrição muito curta ({palavras} palavras). Detalhe mais o projeto.')
        score -= 15

    # 8. Verificar conteúdo suspeito no título
    if verificar_conteudo_suspeito(req.titulo):
        problemas.append('Título contém conteúdo suspeito ou proibido.')
        score -= 30

    # 9. Verificar nome do empregador
    if len(req.nome.strip()) < 2:
        problemas.append('Nome do empregador muito curto.')
        score -= 10

    # Calcular score final
    score = max(0, min(100, score))
    response.score = score
    response.approved = score >= SCORE_EMPREGADOR_MIN and len(problemas) == 0
    response.problemas = problemas
    response.sugestoes = sugestoes
    response.detalhes = detalhes

    logger.info(
        'Validação empregador concluída: nome=%s | approved=%s | score=%d | problemas=%d',
        req.nome, response.approved, response.score, len(problemas),
    )

    return response
