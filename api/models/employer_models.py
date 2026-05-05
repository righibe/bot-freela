"""
Modelos Pydantic para validação de empregadores na API.
"""

from pydantic import BaseModel, Field
from typing import Optional


class EmployerValidationRequest(BaseModel):
    """Dados recebidos para validação de um empregador/projeto."""
    nome: str = Field(..., min_length=2, description='Nome do empregador')
    empresa: str = Field(default='', description='Nome da empresa (opcional)')
    tipo_projeto: str = Field(..., description='Categoria do projeto')
    titulo: str = Field(..., min_length=5, description='Título do projeto')
    descricao: str = Field(..., min_length=30, description='Descrição detalhada do projeto')
    linguagens: list[str] = Field(..., min_length=1, description='Stack tecnológica requerida')
    experiencia_exigida: str = Field(..., description='Nível de experiência exigido')
    valor: float = Field(..., gt=0, description='Valor oferecido em R$')
    prazo: str = Field(default='', description='Prazo estimado do projeto')
    contato: str = Field(default='', description='Meio de contato adicional')


class EmployerValidationResponse(BaseModel):
    """Resultado da validação de um empregador/projeto."""
    approved: bool = False
    score: int = 0
    categoria_detectada: str = ''
    categoria_coerente: bool = False
    valor_coerente: bool = False
    descricao_coerente: bool = False
    complexidade_estimada: str = ''
    problemas: list[str] = []
    sugestoes: list[str] = []
    detalhes: list[str] = []
