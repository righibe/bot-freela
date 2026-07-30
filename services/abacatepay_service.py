"""
Cliente da API AbacatePay (https://docs.abacatepay.com).

Responsável por:
- Criar cobranças PIX (QR Code) para o empregador pagar o projeto.
- Checar o status da cobrança (polling).
- Simular pagamento em modo de desenvolvimento.
- Enviar PIX de repasse para a chave do desenvolvedor (split 85/15).

Endpoints usados (API v2 — chaves novas do painel só funcionam na v2):
- POST /v2/transparents/create            -> cria QR Code PIX (checkout transparente)
- GET  /v2/transparents/check?id=         -> status: PENDING/PAID/EXPIRED/CANCELLED
- POST /v2/transparents/simulate-payment  -> paga a cobrança (apenas dev mode)
- POST /v2/pix/send                       -> envia PIX para chave de terceiros (repasse)
"""

import base64
import logging
from typing import Optional

import aiohttp

from config.settings import ABACATEPAY_API_KEY

logger = logging.getLogger('bot_freeela.services.abacatepay')

BASE_V2 = 'https://api.abacatepay.com/v2'


def pagamentos_configurados() -> bool:
    """True se a chave da API AbacatePay está configurada no .env."""
    return bool(ABACATEPAY_API_KEY)


def _headers() -> dict:
    return {
        'Authorization': f'Bearer {ABACATEPAY_API_KEY}',
        'Content-Type': 'application/json',
    }


async def _request(metodo: str, url: str, **kwargs) -> Optional[dict]:
    """Faz uma requisição à AbacatePay e retorna o campo 'data' da resposta."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                metodo, url,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
                **kwargs,
            ) as resp:
                corpo = await resp.json(content_type=None)
                if resp.status == 200 and isinstance(corpo, dict) and not corpo.get('error'):
                    return corpo.get('data')
                logger.error(
                    'AbacatePay %s %s retornou %d: %s',
                    metodo, url, resp.status, corpo,
                )
                return None
    except aiohttp.ClientError as e:
        logger.error('Erro de conexão com AbacatePay (%s): %s', url, e)
        return None
    except Exception as e:
        logger.exception('Erro inesperado ao chamar AbacatePay (%s): %s', url, e)
        return None


async def criar_cobranca_pix(
    valor_centavos: int,
    descricao: str,
    external_id: str,
    expiracao_segundos: int = 3600,
) -> Optional[dict]:
    """
    Cria uma cobrança PIX (QR Code).

    Retorna dict com: id, brCode (copia-e-cola), brCodeBase64 (imagem do QR),
    status, devMode, expiresAt — ou None em caso de erro.
    """
    payload = {
        'method': 'PIX',
        'data': {
            'amount': int(valor_centavos),
            'expiresIn': expiracao_segundos,
            'description': descricao[:500],
            'externalId': external_id,
        },
    }
    data = await _request('POST', f'{BASE_V2}/transparents/create', json=payload)
    if data:
        logger.info(
            'Cobrança PIX criada: %s | %d centavos | devMode=%s',
            data.get('id'), valor_centavos, data.get('devMode'),
        )
    return data


async def checar_status_cobranca(cobranca_id: str) -> Optional[str]:
    """Retorna o status da cobrança: PENDING, PAID, EXPIRED, CANCELLED, REFUNDED."""
    data = await _request(
        'GET', f'{BASE_V2}/transparents/check', params={'id': cobranca_id}
    )
    return data.get('status') if data else None


async def simular_pagamento(cobranca_id: str) -> bool:
    """Simula o pagamento de uma cobrança (apenas em modo de desenvolvimento)."""
    data = await _request(
        'POST',
        f'{BASE_V2}/transparents/simulate-payment',
        params={'id': cobranca_id},
        json={'metadata': {}},
    )
    return data is not None


async def enviar_pix(
    chave: str,
    tipo_chave: str,
    valor_centavos: int,
    external_id: str,
    descricao: str = '',
) -> Optional[dict]:
    """
    Envia um PIX para uma chave de terceiros (repasse ao desenvolvedor).

    tipo_chave: CPF, CNPJ, PHONE, EMAIL, RANDOM ou BR_CODE.
    Retorna o dict da transação (id, status, amount, ...) ou None.
    """
    payload = {
        'amount': int(valor_centavos),
        'externalId': external_id,
        'description': (descricao or 'Repasse Freeela')[:100],
        'pix': {
            'key': chave,
            'type': tipo_chave,
        },
    }
    data = await _request('POST', f'{BASE_V2}/pix/send', json=payload)
    if data:
        logger.info(
            'PIX de repasse enviado: %s | %d centavos | chave=%s (%s)',
            data.get('id'), valor_centavos, chave[:4] + '***', tipo_chave,
        )
    return data


def decodificar_qrcode_base64(br_code_base64: str) -> Optional[bytes]:
    """Converte o brCodeBase64 (data URI) da AbacatePay em bytes PNG."""
    try:
        if ',' in br_code_base64:
            br_code_base64 = br_code_base64.split(',', 1)[1]
        return base64.b64decode(br_code_base64)
    except Exception as e:
        logger.error('Erro ao decodificar QR Code base64: %s', e)
        return None


def calcular_split(valor_total_centavos: int, taxa_percent: float) -> tuple[int, int]:
    """
    Calcula a divisão do pagamento.
    Retorna (taxa_plataforma_centavos, valor_dev_centavos).
    """
    taxa = round(valor_total_centavos * taxa_percent / 100)
    return taxa, valor_total_centavos - taxa
