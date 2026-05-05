"""
FastAPI application principal.
Registra rotas de validação de devs e empregadores.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.validate_dev import router as dev_router
from api.routes.validate_employer import router as employer_router

logger = logging.getLogger('bot_freeela.api')

app = FastAPI(
    title='Freeela API',
    description='API de validação para a plataforma Freeela — verificação de devs e empregadores.',
    version='1.0.0',
)

# CORS (para acesso local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Registrar rotas
app.include_router(dev_router, tags=['Dev Validation'])
app.include_router(employer_router, tags=['Employer Validation'])


@app.get('/')
async def root():
    return {
        'status': 'online',
        'service': 'Freeela API',
        'version': '1.0.0',
        'endpoints': [
            'POST /validate/dev',
            'POST /validate/employer',
        ],
    }


@app.get('/health')
async def health():
    return {'status': 'healthy'}
