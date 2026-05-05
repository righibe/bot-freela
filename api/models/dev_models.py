"""
Modelos Pydantic para validação de devs na API.
"""

from pydantic import BaseModel, Field
from typing import Optional


class DevValidationRequest(BaseModel):
    """Dados recebidos para validação de um dev."""
    linguagens: list[str] = Field(..., min_length=1, description='Linguagens selecionadas pelo dev')
    experiencia: str = Field(..., description='Código de experiência (1_ano, 2_anos, etc)')
    github: str = Field(..., min_length=1, description='URL ou username do GitHub')
    linkedin: str = Field(default='', description='URL ou username do LinkedIn')
    descricao: str = Field(..., min_length=20, description='Descrição profissional')


class DevValidationResponse(BaseModel):
    """Resultado da validação de um dev."""
    approved: bool = False
    compatibility: int = 0
    integrity: int = 0
    validated_languages: list[str] = []
    detected_languages: list[str] = []
    estimated_level: str = ''
    area: str = ''
    stack: str = ''
    compatibility_details: list[str] = []
    penalties: list[str] = []
    rejection_reasons: list[str] = []
    needs_review: bool = False
    github_valid: bool = False
    github_repos: int = 0
    github_recent_repos: int = 0
    github_account_age: float = 0.0
    linkedin_valid: bool = False
