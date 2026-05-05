"""
Banco de dados local baseado em JSON para persistência de dados.
Armazena projetos, devs verificados, candidaturas e projetos ativos.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger('bot_freeela.core.database')

DATA_DIR = Path(__file__).parent.parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

PROJETOS_FILE = DATA_DIR / 'projetos.json'
DEVS_FILE = DATA_DIR / 'devs_verificados.json'
EMPREGADORES_FILE = DATA_DIR / 'empregadores.json'
CANDIDATURAS_FILE = DATA_DIR / 'candidaturas.json'
PROJETOS_ATIVOS_FILE = DATA_DIR / 'projetos_ativos.json'
COOLDOWNS_FILE = DATA_DIR / 'cooldowns.json'


# ══════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════

@dataclass
class DevVerificado:
    user_id: int = 0
    username: str = ''
    linguagens_confirmadas: list[str] = field(default_factory=list)
    experiencia: str = ''
    senioridade: str = ''
    area: str = ''
    github_url: str = ''
    linkedin_url: str = ''
    compatibilidade: int = 0
    integridade: int = 0
    data_verificacao: str = ''
    projetos_ativos: int = 0


@dataclass
class Empregador:
    user_id: int = 0
    username: str = ''
    nome: str = ''
    empresa: str = ''
    contato: str = ''
    data_verificacao: str = ''
    projetos_criados: int = 0


@dataclass
class Projeto:
    id: str = ''
    empregador_id: int = 0
    empregador_nome: str = ''
    titulo: str = ''
    descricao: str = ''
    categoria: str = ''
    linguagens_requeridas: list[str] = field(default_factory=list)
    experiencia_minima: str = ''
    valor: float = 0.0
    prazo_estimado: str = ''
    status: str = 'aberto'       # aberto, em_negociacao, em_andamento, concluido, cancelado
    data_criacao: str = ''
    message_id: int = 0          # ID da mensagem do embed no canal de listagem
    candidatos: list[int] = field(default_factory=list)


@dataclass
class Candidatura:
    id: str = ''
    projeto_id: str = ''
    dev_id: int = 0
    dev_username: str = ''
    empregador_id: int = 0
    thread_id: int = 0
    status: str = 'negociando'   # negociando, fechado, cancelado
    dev_aceito: bool = False
    empregador_aceito: bool = False
    valor_negociado: float = 0.0
    prazo_negociado: str = ''
    escopo_negociado: str = ''
    data_criacao: str = ''


@dataclass
class ProjetoAtivo:
    id: str = ''
    projeto_id: str = ''
    candidatura_id: str = ''
    dev_id: int = 0
    empregador_id: int = 0
    categoria_id: int = 0        # ID da categoria Discord criada
    canal_texto_id: int = 0
    canal_voz_id: int = 0
    valor: float = 0.0
    prazo: str = ''
    escopo: str = ''
    data_inicio: str = ''
    status: str = 'ativo'        # ativo, concluido, cancelado, disputa
    regras_confirmadas: bool = False


# ══════════════════════════════════════════════════════
#  FUNÇÕES AUXILIARES I/O
# ══════════════════════════════════════════════════════

def _carregar_json(path: Path) -> list[dict]:
    """Carrega uma lista de dicts de um arquivo JSON."""
    if not path.exists():
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        logger.error('Erro ao carregar %s: %s', path, e)
        return []


def _salvar_json(path: Path, data: list[dict]) -> None:
    """Salva uma lista de dicts em um arquivo JSON."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error('Erro ao salvar %s: %s', path, e)


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gerar_id(prefixo: str) -> str:
    import uuid
    return f'{prefixo}_{uuid.uuid4().hex[:8]}'


# ══════════════════════════════════════════════════════
#  DEVS VERIFICADOS
# ══════════════════════════════════════════════════════

def salvar_dev(dev: DevVerificado) -> None:
    """Salva ou atualiza um dev verificado."""
    dados = _carregar_json(DEVS_FILE)
    dados = [d for d in dados if d.get('user_id') != dev.user_id]
    dev.data_verificacao = dev.data_verificacao or _agora_iso()
    dados.append(asdict(dev))
    _salvar_json(DEVS_FILE, dados)
    logger.info('Dev salvo: %s (%d)', dev.username, dev.user_id)


def buscar_dev(user_id: int) -> Optional[DevVerificado]:
    """Busca um dev verificado pelo ID."""
    dados = _carregar_json(DEVS_FILE)
    for d in dados:
        if d.get('user_id') == user_id:
            return DevVerificado(**d)
    return None


def listar_devs() -> list[DevVerificado]:
    """Lista todos os devs verificados."""
    dados = _carregar_json(DEVS_FILE)
    return [DevVerificado(**d) for d in dados]


def atualizar_projetos_ativos_dev(user_id: int, delta: int) -> None:
    """Incrementa ou decrementa o contador de projetos ativos de um dev."""
    dados = _carregar_json(DEVS_FILE)
    for d in dados:
        if d.get('user_id') == user_id:
            d['projetos_ativos'] = max(0, d.get('projetos_ativos', 0) + delta)
            break
    _salvar_json(DEVS_FILE, dados)


# ══════════════════════════════════════════════════════
#  EMPREGADORES
# ══════════════════════════════════════════════════════

def salvar_empregador(emp: Empregador) -> None:
    """Salva ou atualiza um empregador."""
    dados = _carregar_json(EMPREGADORES_FILE)
    dados = [d for d in dados if d.get('user_id') != emp.user_id]
    emp.data_verificacao = emp.data_verificacao or _agora_iso()
    dados.append(asdict(emp))
    _salvar_json(EMPREGADORES_FILE, dados)
    logger.info('Empregador salvo: %s (%d)', emp.username, emp.user_id)


def buscar_empregador(user_id: int) -> Optional[Empregador]:
    """Busca um empregador pelo ID."""
    dados = _carregar_json(EMPREGADORES_FILE)
    for d in dados:
        if d.get('user_id') == user_id:
            return Empregador(**d)
    return None


# ══════════════════════════════════════════════════════
#  PROJETOS
# ══════════════════════════════════════════════════════

def salvar_projeto(projeto: Projeto) -> None:
    """Salva ou atualiza um projeto."""
    dados = _carregar_json(PROJETOS_FILE)
    dados = [d for d in dados if d.get('id') != projeto.id]
    projeto.id = projeto.id or _gerar_id('proj')
    projeto.data_criacao = projeto.data_criacao or _agora_iso()
    dados.append(asdict(projeto))
    _salvar_json(PROJETOS_FILE, dados)
    logger.info('Projeto salvo: %s (%s)', projeto.titulo, projeto.id)


def buscar_projeto(projeto_id: str) -> Optional[Projeto]:
    """Busca um projeto pelo ID."""
    dados = _carregar_json(PROJETOS_FILE)
    for d in dados:
        if d.get('id') == projeto_id:
            return Projeto(**d)
    return None


def listar_projetos(status: str = 'aberto') -> list[Projeto]:
    """Lista projetos por status."""
    dados = _carregar_json(PROJETOS_FILE)
    return [Projeto(**d) for d in dados if d.get('status') == status]


def listar_projetos_por_categoria(categoria: str) -> list[Projeto]:
    """Lista projetos abertos de uma categoria."""
    dados = _carregar_json(PROJETOS_FILE)
    return [
        Projeto(**d) for d in dados
        if d.get('status') == 'aberto' and d.get('categoria') == categoria
    ]


def atualizar_status_projeto(projeto_id: str, novo_status: str) -> None:
    """Atualiza o status de um projeto."""
    dados = _carregar_json(PROJETOS_FILE)
    for d in dados:
        if d.get('id') == projeto_id:
            d['status'] = novo_status
            break
    _salvar_json(PROJETOS_FILE, dados)


def adicionar_candidato_projeto(projeto_id: str, dev_id: int) -> None:
    """Adiciona um candidato ao projeto."""
    dados = _carregar_json(PROJETOS_FILE)
    for d in dados:
        if d.get('id') == projeto_id:
            candidatos = d.get('candidatos', [])
            if dev_id not in candidatos:
                candidatos.append(dev_id)
                d['candidatos'] = candidatos
            break
    _salvar_json(PROJETOS_FILE, dados)


# ══════════════════════════════════════════════════════
#  CANDIDATURAS
# ══════════════════════════════════════════════════════

def salvar_candidatura(cand: Candidatura) -> None:
    """Salva ou atualiza uma candidatura."""
    dados = _carregar_json(CANDIDATURAS_FILE)
    dados = [d for d in dados if d.get('id') != cand.id]
    cand.id = cand.id or _gerar_id('cand')
    cand.data_criacao = cand.data_criacao or _agora_iso()
    dados.append(asdict(cand))
    _salvar_json(CANDIDATURAS_FILE, dados)
    logger.info('Candidatura salva: %s', cand.id)


def buscar_candidatura(candidatura_id: str) -> Optional[Candidatura]:
    """Busca uma candidatura pelo ID."""
    dados = _carregar_json(CANDIDATURAS_FILE)
    for d in dados:
        if d.get('id') == candidatura_id:
            return Candidatura(**d)
    return None


def buscar_candidatura_por_thread(thread_id: int) -> Optional[Candidatura]:
    """Busca uma candidatura pela thread de negociação."""
    dados = _carregar_json(CANDIDATURAS_FILE)
    for d in dados:
        if d.get('thread_id') == thread_id:
            return Candidatura(**d)
    return None


def atualizar_candidatura(cand: Candidatura) -> None:
    """Atualiza uma candidatura existente."""
    dados = _carregar_json(CANDIDATURAS_FILE)
    for i, d in enumerate(dados):
        if d.get('id') == cand.id:
            dados[i] = asdict(cand)
            break
    _salvar_json(CANDIDATURAS_FILE, dados)


def contar_candidaturas_dev_hoje(dev_id: int) -> int:
    """Conta quantas candidaturas um dev fez hoje."""
    dados = _carregar_json(CANDIDATURAS_FILE)
    hoje = datetime.now(timezone.utc).date().isoformat()
    count = 0
    for d in dados:
        if d.get('dev_id') == dev_id:
            criacao = d.get('data_criacao', '')
            if criacao.startswith(hoje):
                count += 1
    return count


# ══════════════════════════════════════════════════════
#  PROJETOS ATIVOS
# ══════════════════════════════════════════════════════

def salvar_projeto_ativo(pa: ProjetoAtivo) -> None:
    """Salva um projeto ativo."""
    dados = _carregar_json(PROJETOS_ATIVOS_FILE)
    dados = [d for d in dados if d.get('id') != pa.id]
    pa.id = pa.id or _gerar_id('pativo')
    pa.data_inicio = pa.data_inicio or _agora_iso()
    dados.append(asdict(pa))
    _salvar_json(PROJETOS_ATIVOS_FILE, dados)
    logger.info('Projeto ativo salvo: %s', pa.id)


def buscar_projeto_ativo(projeto_ativo_id: str) -> Optional[ProjetoAtivo]:
    """Busca um projeto ativo pelo ID."""
    dados = _carregar_json(PROJETOS_ATIVOS_FILE)
    for d in dados:
        if d.get('id') == projeto_ativo_id:
            return ProjetoAtivo(**d)
    return None


def buscar_projeto_ativo_por_canal(canal_id: int) -> Optional[ProjetoAtivo]:
    """Busca um projeto ativo pelo canal de texto."""
    dados = _carregar_json(PROJETOS_ATIVOS_FILE)
    for d in dados:
        if d.get('canal_texto_id') == canal_id:
            return ProjetoAtivo(**d)
    return None


def listar_projetos_ativos_dev(dev_id: int) -> list[ProjetoAtivo]:
    """Lista projetos ativos de um dev."""
    dados = _carregar_json(PROJETOS_ATIVOS_FILE)
    return [
        ProjetoAtivo(**d) for d in dados
        if d.get('dev_id') == dev_id and d.get('status') == 'ativo'
    ]


def atualizar_projeto_ativo(pa: ProjetoAtivo) -> None:
    """Atualiza um projeto ativo."""
    dados = _carregar_json(PROJETOS_ATIVOS_FILE)
    for i, d in enumerate(dados):
        if d.get('id') == pa.id:
            dados[i] = asdict(pa)
            break
    _salvar_json(PROJETOS_ATIVOS_FILE, dados)


# ══════════════════════════════════════════════════════
#  COOLDOWNS
# ══════════════════════════════════════════════════════

def registrar_cooldown(user_id: int, tipo: str) -> None:
    """Registra um cooldown para um usuário."""
    dados = _carregar_json(COOLDOWNS_FILE)
    dados.append({
        'user_id': user_id,
        'tipo': tipo,
        'timestamp': time.time(),
    })
    _salvar_json(COOLDOWNS_FILE, dados)


def verificar_cooldown(user_id: int, tipo: str, segundos: int) -> float:
    """
    Verifica se o usuário está em cooldown.
    Retorna 0 se não está, ou os segundos restantes.
    """
    dados = _carregar_json(COOLDOWNS_FILE)
    agora = time.time()
    for d in reversed(dados):
        if d.get('user_id') == user_id and d.get('tipo') == tipo:
            diff = agora - d.get('timestamp', 0)
            if diff < segundos:
                return round(segundos - diff)
            return 0
    return 0


def limpar_cooldowns_expirados(segundos_max: int = 86400) -> None:
    """Remove cooldowns com mais de X segundos (padrão: 24h)."""
    dados = _carregar_json(COOLDOWNS_FILE)
    agora = time.time()
    dados = [d for d in dados if agora - d.get('timestamp', 0) < segundos_max]
    _salvar_json(COOLDOWNS_FILE, dados)
