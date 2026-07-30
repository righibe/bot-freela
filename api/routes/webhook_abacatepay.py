"""
Webhook da AbacatePay — confirma pagamentos em tempo real.

A AbacatePay chama esta rota quando uma cobrança é paga. A rota apenas marca
o pagamento como 'pago' no banco; o bot (polling) detecta a mudança e executa
o repasse + conclusão do projeto no loop do Discord.

Segurança:
- Valida o `webhookSecret` da query string contra ABACATEPAY_WEBHOOK_SECRET.
- Valida a assinatura HMAC-SHA256 do corpo (header X-Webhook-Signature).

O webhook é um acelerador: mesmo sem ele (bot rodando localmente sem URL
pública), o polling confirma o pagamento em até ~20 segundos.
"""

import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, Request, HTTPException

from config.settings import ABACATEPAY_WEBHOOK_SECRET

logger = logging.getLogger('bot_freeela.api.webhook_abacatepay')

router = APIRouter()

# Chave pública da AbacatePay para verificação HMAC dos webhooks
# (https://docs.abacatepay.com -> Webhooks -> Verificação e Segurança)
ABACATEPAY_PUBLIC_KEY = (
    't9dXRhHHo3yDEj5pVDYz0frf7q6bMKyMRmxxCPIPp3RCplBfXRxqlC6ZpiWmOqj4'
    'L63qEaeUOtrCI8P0VMUgo6iIga2ri9ogaHFs0WIIywSMg0q7RmBfybe1E5XJcfC4'
    'IW3alNqym0tXoAKkzvfEjZxV6bE0oG2zJrNNYmUCKZyV0KZ3JS8Votf9EAWWYdiD'
    'kMkpbMdPggfh1EqHlVkMiTady6jOR3hyzGEHrIz2Ret0xHKMbiqkr9HS1JhNHDX9'
)


def _assinatura_valida(corpo: bytes, assinatura: str) -> bool:
    esperada = hmac.new(
        ABACATEPAY_PUBLIC_KEY.encode('utf-8'), corpo, hashlib.sha256
    ).digest()
    esperada_b64 = base64.b64encode(esperada).decode('utf-8')
    return hmac.compare_digest(esperada_b64, assinatura)


def _extrair_ids_cobranca(payload: dict) -> list[str]:
    """
    Extrai possíveis IDs de cobrança do payload, cobrindo os formatos
    v1 (billing.paid / pixQrCode) e v2 (transparent.completed).
    """
    data = payload.get('data') or {}
    candidatos = []
    for caminho in (
        ('pixQrCode', 'id'),
        ('transparent', 'id'),
        ('billing', 'id'),
        ('payment', 'id'),
        ('id',),
    ):
        atual = data
        for chave in caminho:
            atual = atual.get(chave) if isinstance(atual, dict) else None
            if atual is None:
                break
        if isinstance(atual, str) and atual:
            candidatos.append(atual)
    return candidatos


@router.post('/webhooks/abacatepay')
async def webhook_abacatepay(request: Request):
    # 1. Validar secret da URL
    secret = request.query_params.get('webhookSecret', '')
    if not ABACATEPAY_WEBHOOK_SECRET or not hmac.compare_digest(secret, ABACATEPAY_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail='Unauthorized')

    corpo = await request.body()

    # 2. Validar assinatura HMAC (quando presente)
    assinatura = request.headers.get('X-Webhook-Signature', '')
    if assinatura and not _assinatura_valida(corpo, assinatura):
        logger.warning('Webhook AbacatePay com assinatura HMAC inválida — descartado')
        raise HTTPException(status_code=401, detail='Invalid signature')

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid JSON')

    evento = payload.get('event', '')
    logger.info('Webhook AbacatePay recebido: %s', evento)

    eventos_pagamento = {'billing.paid', 'transparent.completed', 'checkout.completed'}
    if evento not in eventos_pagamento:
        return {'received': True, 'processed': False}

    from core.database import marcar_pagamento_pago
    for cobranca_id in _extrair_ids_cobranca(payload):
        pagamento = marcar_pagamento_pago(cobranca_id)
        if pagamento:
            logger.info(
                'Pagamento %s marcado como PAGO via webhook (cobrança %s)',
                pagamento.id, cobranca_id,
            )
            return {'received': True, 'processed': True}

    logger.warning('Webhook de pagamento sem cobrança correspondente: %s', evento)
    return {'received': True, 'processed': False}
