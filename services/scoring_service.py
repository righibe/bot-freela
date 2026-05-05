import logging
from dataclasses import dataclass, field
from services.github_service import GitHubProfile
from services.linkedin_service import LinkedInProfile
logger = logging.getLogger('bot_freeela.services.scoring')

@dataclass
class ResultadoScore:
    compatibilidade: int = 0
    integridade: int = 100
    detalhes_compat: list[str] = field(default_factory=list)
    penalizacoes: list[str] = field(default_factory=list)
    linguagens_selecionadas: list[str] = field(default_factory=list)
    linguagens_detectadas: list[str] = field(default_factory=list)
    linguagens_confirmadas: list[str] = field(default_factory=list)
    aprovado: bool = False
    requires_review: bool = False
    score_final: int = 0
    motivos_reprovacao: list[str] = field(default_factory=list)
    stack_principal: str = ''
    area_principal: str = ''
    senioridade: str = ''
#TODO: transformar em uma API
def calcular_score(linguagens_selecionadas: list[str], experiencia: str, descricao: str, github_profile: GitHubProfile, linkedin_profile: LinkedInProfile) -> ResultadoScore:
    resultado = ResultadoScore()
    resultado.linguagens_selecionadas = linguagens_selecionadas
    resultado.linguagens_detectadas = github_profile.linguagens_detectadas
    compat = 0
    integ = 100
    if github_profile.existe:
        compat += 15
        resultado.detalhes_compat.append('✅ GitHub válido (+15)')
    else:
        resultado.detalhes_compat.append('❌ GitHub inválido ou não encontrado (+0)')
    if github_profile.repos_publicos >= 5:
        compat += 15
        resultado.detalhes_compat.append(f'✅ {github_profile.repos_publicos} repos públicos (+15)')
    elif github_profile.repos_publicos >= 2:
        compat += 8
        resultado.detalhes_compat.append(f'⚠️ {github_profile.repos_publicos} repos públicos (+8)')
    else:
        resultado.detalhes_compat.append(f'❌ Apenas {github_profile.repos_publicos} repos públicos (+0)')
    confirmadas = [lang for lang in linguagens_selecionadas if lang in github_profile.linguagens_detectadas]
    resultado.linguagens_confirmadas = confirmadas
    if len(confirmadas) >= 3:
        compat += 20
        resultado.detalhes_compat.append(f'✅ {len(confirmadas)} linguagens confirmadas (+20)')
    elif len(confirmadas) >= 2:
        compat += 20
        resultado.detalhes_compat.append(f'✅ {len(confirmadas)} linguagens confirmadas (+20)')
    elif len(confirmadas) == 1:
        compat += 8
        resultado.detalhes_compat.append(f'⚠️ Apenas 1 linguagem confirmada (+8)')
    else:
        resultado.detalhes_compat.append('❌ Nenhuma linguagem confirmada no GitHub (+0)')
    descricao_lower = descricao.lower()
    langs_na_desc = [lang for lang in linguagens_selecionadas if lang.lower() in descricao_lower]
    if len(langs_na_desc) >= 1:
        compat += 10
        resultado.detalhes_compat.append(f'✅ Linguagens mencionadas na descrição (+10)')
    else:
        resultado.detalhes_compat.append('⚠️ Nenhuma linguagem mencionada na descrição (+0)')
    if linkedin_profile.existe:
        compat += 10
        resultado.detalhes_compat.append('✅ LinkedIn válido (+10)')
    else:
        resultado.detalhes_compat.append('❌ LinkedIn inválido (+0)')
    if github_profile.repos_recentes >= 3:
        compat += 10
        resultado.detalhes_compat.append(f'✅ {github_profile.repos_recentes} repos com atividade recente (+10)')
    elif github_profile.repos_recentes >= 1:
        compat += 5
        resultado.detalhes_compat.append(f'⚠️ {github_profile.repos_recentes} repos com atividade recente (+5)')
    else:
        resultado.detalhes_compat.append('❌ Sem atividade recente no GitHub (+0)')
    exp_pontos = {'1_ano': 10, '2_anos': 15, '4_6_anos': 20, '6_mais': 20}
    exp_pts = exp_pontos.get(experiencia, 0)
    if exp_pts > 0:
        compat += exp_pts
        resultado.detalhes_compat.append(f'✅ Experiência declarada coerente (+{exp_pts})')
    else:
        resultado.detalhes_compat.append('❌ Experiência insuficiente (+0)')
    compat = min(compat, 100)
    resultado.compatibilidade = compat
    if github_profile.existe:
        nao_confirmadas = [lang for lang in linguagens_selecionadas if lang not in github_profile.linguagens_detectadas]
        for lang in nao_confirmadas:
            penalidade = 15
            integ -= penalidade
            resultado.penalizacoes.append(f"⚠️ '{lang}' não encontrada no GitHub (-{penalidade})")
    if len(confirmadas) < 2:
        penalidade = 25
        integ -= penalidade
        resultado.penalizacoes.append(f'🔴 Menos de 2 linguagens confirmadas (-{penalidade})')
    if experiencia in ('4_6_anos', '6_mais'):
        if github_profile.existe and github_profile.repos_publicos < 5:
            penalidade = 25
            integ -= penalidade
            resultado.penalizacoes.append(f'🔴 Experiência alta mas poucos repos ({github_profile.repos_publicos}) (-{penalidade})')
    if experiencia in ('4_6_anos', '6_mais'):
        if github_profile.existe and github_profile.idade_conta_anos < 2:
            penalidade = 25
            integ -= penalidade
            resultado.penalizacoes.append(f'🔴 Conta GitHub com {github_profile.idade_conta_anos} anos vs experiência de {experiencia} (-{penalidade})')
    if not linkedin_profile.existe:
        penalidade = 15
        integ -= penalidade
        resultado.penalizacoes.append(f'⚠️ LinkedIn não encontrado ou inacessível (-{penalidade})')
    if len(descricao.strip()) < 30:
        penalidade = 10
        integ -= penalidade
        resultado.penalizacoes.append(f'⚠️ Descrição muito curta ({len(descricao.strip())} chars) (-{penalidade})')
    integ = max(integ, 0)
    resultado.integridade = integ
    from config.settings import SCORE_COMPATIBILIDADE_MIN, SCORE_INTEGRIDADE_MIN, LINGUAGENS_CONFIRMADAS_MIN
    if resultado.compatibilidade < SCORE_COMPATIBILIDADE_MIN:
        resultado.motivos_reprovacao.append(f'Compatibilidade ({resultado.compatibilidade}%) abaixo do mínimo ({SCORE_COMPATIBILIDADE_MIN}%)')
    if resultado.integridade < SCORE_INTEGRIDADE_MIN:
        resultado.motivos_reprovacao.append(f'Integridade ({resultado.integridade}%) abaixo do mínimo ({SCORE_INTEGRIDADE_MIN}%)')
    if len(confirmadas) < LINGUAGENS_CONFIRMADAS_MIN:
        resultado.motivos_reprovacao.append(f'Apenas {len(confirmadas)} linguagem(ns) confirmada(s) (mínimo: {LINGUAGENS_CONFIRMADAS_MIN})')
    resultado.aprovado = len(resultado.motivos_reprovacao) == 0
    from utils.helpers import estimar_senioridade, estimar_area
    resultado.stack_principal = ' + '.join(confirmadas[:3]) if confirmadas else 'N/A'
    resultado.area_principal = estimar_area(confirmadas)
    resultado.senioridade = estimar_senioridade(experiencia, resultado.compatibilidade)
    logger.info('Score calculado para GitHub=%s | compat=%d | integ=%d | aprovado=%s', github_profile.username, resultado.compatibilidade, resultado.integridade, resultado.aprovado)
    return resultado