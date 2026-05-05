"""
Cliente HTTP para comunicação com a API FastAPI.
Usado pelo bot para validar devs e empregadores.
"""

import logging
import aiohttp
from typing import Optional
from config.settings import API_BASE_URL

logger = logging.getLogger('bot_freeela.services.api_client')


async def validar_dev_via_api(
    linguagens: list[str],
    experiencia: str,
    github: str,
    linkedin: str,
    descricao: str,
) -> Optional[dict]:
    """
    Envia dados do dev para a API de validação.
    Retorna o dict de resposta ou None em caso de erro.
    """
    payload = {
        'linguagens': linguagens,
        'experiencia': experiencia,
        'github': github,
        'linkedin': linkedin,
        'descricao': descricao,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{API_BASE_URL}/validate/dev',
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info('API /validate/dev retornou: approved=%s', data.get('approved'))
                    return data
                else:
                    body = await resp.text()
                    logger.error('API /validate/dev retornou status %d: %s', resp.status, body)
                    return None
    except aiohttp.ClientError as e:
        logger.error('Erro de conexão com a API /validate/dev: %s', e)
        return None
    except Exception as e:
        logger.exception('Erro inesperado ao chamar API /validate/dev: %s', e)
        return None


async def validar_empregador_via_api(
    nome: str,
    empresa: str,
    tipo_projeto: str,
    titulo: str,
    descricao: str,
    linguagens: list[str],
    experiencia_exigida: str,
    valor: float,
    prazo: str = '',
    contato: str = '',
) -> Optional[dict]:
    """
    Envia dados do empregador para a API de validação.
    Retorna o dict de resposta ou None em caso de erro.
    """
    payload = {
        'nome': nome,
        'empresa': empresa,
        'tipo_projeto': tipo_projeto,
        'titulo': titulo,
        'descricao': descricao,
        'linguagens': linguagens,
        'experiencia_exigida': experiencia_exigida,
        'valor': valor,
        'prazo': prazo,
        'contato': contato,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{API_BASE_URL}/validate/employer',
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info('API /validate/employer retornou: approved=%s', data.get('approved'))
                    return data
                else:
                    body = await resp.text()
                    logger.error('API /validate/employer retornou status %d: %s', resp.status, body)
                    return None
    except aiohttp.ClientError as e:
        logger.error('Erro de conexão com a API /validate/employer: %s', e)
        return None
    except Exception as e:
        logger.exception('Erro inesperado ao chamar API /validate/employer: %s', e)
        return None
