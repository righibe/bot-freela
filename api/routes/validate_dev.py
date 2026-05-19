"""
Rota POST /validate/dev — Validação completa de desenvolvedores.

Busca dados reais no GitHub, verifica LinkedIn, calcula scores
de compatibilidade e integridade.
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException

from api.models.dev_models import DevValidationRequest, DevValidationResponse
from services.github_service import buscar_perfil_github
from services.linkedin_service import verificar_linkedin
from services.scoring_service import calcular_score
from utils.helpers import (
    extrair_username_github,
    extrair_username_linkedin,
    estimar_senioridade,
    estimar_area,
)

logger = logging.getLogger('bot_freeela.api.validate_dev')
router = APIRouter()

# Experiências que reprovam diretamente
EXPERIENCIAS_INSUFICIENTES = {'6_meses'}


@router.post('/validate/dev', response_model=DevValidationResponse)
async def validate_dev(req: DevValidationRequest) -> DevValidationResponse:
    """
    Valida um desenvolvedor completo.
    Busca GitHub real, verifica LinkedIn, calcula scores.
    """
    response = DevValidationResponse()

    # 1. Verificar experiência mínima (mínimo 1 ano)
    if req.experiencia in EXPERIENCIAS_INSUFICIENTES:
        response.approved = False
        response.rejection_reasons.append(
            'Experiência inferior a 1 ano — verificação não permitida. Mínimo: 1 ano.'
        )
        return response

    # 2. Extrair usernames
    github_username = extrair_username_github(req.github)
    linkedin_username = extrair_username_linkedin(req.linkedin) if req.linkedin else None

    if not github_username:
        response.approved = False
        response.rejection_reasons.append('GitHub URL/username inválido.')
        return response

    # 3. Buscar perfis (em paralelo)
    github_task = buscar_perfil_github(github_username)
    linkedin_task = verificar_linkedin(linkedin_username or '')
    github_profile, linkedin_profile = await asyncio.gather(github_task, linkedin_task)

    # 4. Popular dados do GitHub na resposta
    response.github_valid = github_profile.existe
    response.github_repos = github_profile.repos_publicos
    response.github_recent_repos = github_profile.repos_recentes
    response.github_account_age = github_profile.idade_conta_anos
    response.linkedin_valid = linkedin_profile.existe
    response.detected_languages = github_profile.linguagens_detectadas

    # Verificações de coerência com experiência
    if not github_profile.existe:
        response.rejection_reasons.append('Perfil GitHub não encontrado ou privado.')
    else:
        # Verificar idade da conta GitHub versus experiência declarada
        experiencia_map = {
            '1_ano': 1,
            '2_anos': 2,
            '4_6_anos': 4,
            '6_mais': 6,
        }
        experiencia_anos = experiencia_map.get(req.experiencia)
        if experiencia_anos is not None and github_profile.idade_conta_anos is not None:
            if github_profile.idade_conta_anos + 1 < experiencia_anos:
                response.rejection_reasons.append(
                    f'Conta GitHub com {github_profile.idade_conta_anos} anos não sustenta a experiência declarada ({req.experiencia}).'
                )

        # Verificar repos públicos (esperado ter repos para justificar experiência)
        if github_profile.repos_publicos == 0:
            response.rejection_reasons.append('Nenhum repositório público no GitHub.')
        
        # Verificar se tem linguagens detectadas (deve ter trabalhado em algo)
        if not github_profile.linguagens_detectadas:
            response.rejection_reasons.append('Nenhuma linguagem detectada nos repositórios GitHub.')
        
        # Validar coerência entre repos/atividade e experiência declarada
        # Se tem 4+ anos, espera-se mínimo 3 repos públicos
        if req.experiencia in ('4_6_anos', '6_mais'):
            if github_profile.repos_publicos < 3:
                response.rejection_reasons.append(
                    f'Experiência declarada ({req.experiencia}) com poucos repos públicos ({github_profile.repos_publicos}). '
                    f'Esperado: 3+ repos.'
                )
            # Se tem atividade recente, isso valida a experiência
            if github_profile.repos_recentes > 0:
                response.compatibility = 85  # Alta compatibilidade
        
        # Se declarou linguagens, deve ter pelo menos uma no GitHub
        if req.linguagens:
            confirmadas = [lang for lang in req.linguagens if lang in github_profile.linguagens_detectadas]
            faltando = [lang for lang in req.linguagens if lang not in github_profile.linguagens_detectadas]
            
            if not confirmadas:
                response.rejection_reasons.append(
                    f'Nenhuma das linguagens selecionadas foi encontrada no GitHub: {", ".join(req.linguagens)}.'
                )
            else:
                response.validated_languages = confirmadas
            
            if faltando and len(faltando) > len(confirmadas):
                # Mais linguagens faltando do que encontradas = suspeito
                response.rejection_reasons.append(
                    f'Mais linguagens faltando ({len(faltando)}) do que confirmadas ({len(confirmadas)}).'
                )

    # 5. Calcular score (usa o serviço existente)
    resultado = calcular_score(
        linguagens_selecionadas=req.linguagens,
        experiencia=req.experiencia,
        descricao=req.descricao,
        github_profile=github_profile,
        linkedin_profile=linkedin_profile,
    )

    # 6. Preencher resposta
    # Aprovado se não há motivos de rejeição explícitos
    response.approved = len(response.rejection_reasons) == 0 and github_profile.existe
    response.compatibility = response.compatibility or resultado.compatibilidade
    response.integrity = resultado.integridade
    response.validated_languages = response.validated_languages or resultado.linguagens_confirmadas
    response.estimated_level = resultado.senioridade
    response.area = resultado.area_principal
    response.stack = resultado.stack_principal
    response.compatibility_details = resultado.detalhes_compat
    response.penalties = resultado.penalizacoes
    response.rejection_reasons.extend(resultado.motivos_reprovacao)
    response.needs_review = False  # Não usar review, apenas aprovar/reprovar

    logger.info(
        'Validação dev concluída: github=%s | approved=%s | compat=%d | integ=%d',
        github_username, response.approved, response.compatibility, response.integrity,
    )

    return response
