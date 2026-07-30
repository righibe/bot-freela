"""
Banco de dados relacional (SQLite) para persistência de dados.
Armazena devs, empregadores, projetos, candidaturas, projetos ativos,
cooldowns e pagamentos.

Por que SQLite:
- ACID: sem risco de corromper dados em escrita concorrente (bot + API rodam
  em threads separadas) — crítico agora que o sistema movimenta dinheiro.
- Transações atômicas para o fluxo de pagamento (cobrança -> repasse).
- Consultas indexadas em vez de varrer arquivos JSON inteiros.
- Arquivo único, zero configuração, sem servidor para gerenciar.

Migração: na primeira execução, dados dos JSONs antigos (data/*.json) são
importados automaticamente e os arquivos renomeados para *.json.migrado.
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger('bot_freeela.core.database')

DATA_DIR = Path(__file__).parent.parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

DB_FILE = DATA_DIR / 'freeela.db'

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
    # Dados de recebimento (PIX) — usados no repasse automático
    pix_key: str = ''
    pix_key_type: str = ''       # CPF, CNPJ, EMAIL, PHONE, RANDOM
    pix_nome: str = ''           # Nome do titular da chave


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
    status: str = 'aberto'       # aberto, pendente, rejeitado, em_negociacao, em_andamento, concluido, cancelado
    data_criacao: str = ''
    message_id: int = 0          # ID da mensagem do embed no canal de listagem
    canal_listagem_id: int = 0   # ID do canal Discord onde o projeto foi publicado
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
    status: str = 'ativo'        # ativo, aguardando_pagamento, concluido, cancelado, disputa
    regras_confirmadas: bool = False


@dataclass
class Pagamento:
    """Cobrança PIX de um projeto + repasse ao dev (via AbacatePay)."""
    id: str = ''
    projeto_ativo_id: str = ''
    dev_id: int = 0
    empregador_id: int = 0
    cobranca_id: str = ''            # ID da cobrança na AbacatePay
    transferencia_id: str = ''       # ID do PIX de repasse na AbacatePay
    valor_total_centavos: int = 0
    taxa_plataforma_centavos: int = 0
    valor_dev_centavos: int = 0
    status: str = 'aguardando'       # aguardando, pago, repassado, erro_repasse, cancelado, expirado
    br_code: str = ''                # PIX copia-e-cola
    pix_key: str = ''                # chave do dev no momento da cobrança
    pix_key_type: str = ''
    canal_id: int = 0                # canal onde a cobrança foi postada
    mensagem_id: int = 0
    dev_mode: bool = False           # cobrança criada em modo de desenvolvimento
    data_criacao: str = ''
    data_pagamento: str = ''
    data_repasse: str = ''


# Campos que são listas serializadas como JSON no banco
_CAMPOS_JSON = {
    'DevVerificado': {'linguagens_confirmadas'},
    'Projeto': {'linguagens_requeridas', 'candidatos'},
}

_CAMPOS_BOOL = {
    'Candidatura': {'dev_aceito', 'empregador_aceito'},
    'ProjetoAtivo': {'regras_confirmadas'},
    'Pagamento': {'dev_mode'},
}


# ══════════════════════════════════════════════════════
#  CONEXÃO
# ══════════════════════════════════════════════════════

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute('PRAGMA journal_mode=WAL')
        _conn.execute('PRAGMA foreign_keys=ON')
        _criar_tabelas(_conn)
        _migrar_jsons_antigos(_conn)
        _seed_tecnologias(_conn)
    return _conn


# Tecnologias iniciais da plataforma. As 11 primeiras herdam os cargos que já
# existem no servidor (settings.CARGOS_LINGUAGEM); as demais ganham cargo
# criado automaticamente pelo setup. Novas tecnologias entram via sugestão.
TECNOLOGIAS_SEED = [
    'Python', 'Java', 'Rust', 'JavaScript', 'TypeScript', 'Golang', 'Kotlin',
    'C/C++', 'C#', 'Swift', 'Ruby',
    'PHP', 'Dart', 'HTML/CSS', 'SQL', 'Bash',
    'React', 'React Native', 'Node.js', 'Angular', 'Vue', 'Django',
    'Flutter', 'Unity',
]


def _seed_tecnologias(conn: sqlite3.Connection) -> None:
    """Popula a tabela de tecnologias na primeira execução."""
    existentes = conn.execute('SELECT COUNT(*) FROM tecnologias').fetchone()[0]
    if existentes > 0:
        return
    try:
        from config.settings import CARGOS_LINGUAGEM
    except Exception:
        CARGOS_LINGUAGEM = {}
    for nome in TECNOLOGIAS_SEED:
        conn.execute(
            'INSERT OR IGNORE INTO tecnologias (nome, cargo_id, status, data_criacao) '
            "VALUES (?, ?, 'ativa', ?)",
            (nome, CARGOS_LINGUAGEM.get(nome, 0), _agora_iso()),
        )
    conn.commit()
    logger.info('Seed de %d tecnologias criado', len(TECNOLOGIAS_SEED))


def _criar_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS devs (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            linguagens_confirmadas TEXT NOT NULL DEFAULT '[]',
            experiencia TEXT DEFAULT '',
            senioridade TEXT DEFAULT '',
            area TEXT DEFAULT '',
            github_url TEXT DEFAULT '',
            linkedin_url TEXT DEFAULT '',
            compatibilidade INTEGER DEFAULT 0,
            integridade INTEGER DEFAULT 0,
            data_verificacao TEXT DEFAULT '',
            projetos_ativos INTEGER DEFAULT 0,
            pix_key TEXT DEFAULT '',
            pix_key_type TEXT DEFAULT '',
            pix_nome TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS empregadores (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            nome TEXT DEFAULT '',
            empresa TEXT DEFAULT '',
            contato TEXT DEFAULT '',
            data_verificacao TEXT DEFAULT '',
            projetos_criados INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS projetos (
            id TEXT PRIMARY KEY,
            empregador_id INTEGER NOT NULL,
            empregador_nome TEXT DEFAULT '',
            titulo TEXT NOT NULL DEFAULT '',
            descricao TEXT DEFAULT '',
            categoria TEXT DEFAULT '',
            linguagens_requeridas TEXT NOT NULL DEFAULT '[]',
            experiencia_minima TEXT DEFAULT '',
            valor REAL DEFAULT 0,
            prazo_estimado TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'aberto',
            data_criacao TEXT DEFAULT '',
            message_id INTEGER DEFAULT 0,
            canal_listagem_id INTEGER DEFAULT 0,
            candidatos TEXT NOT NULL DEFAULT '[]'
        );
        CREATE INDEX IF NOT EXISTS idx_projetos_status ON projetos(status);
        CREATE INDEX IF NOT EXISTS idx_projetos_empregador ON projetos(empregador_id);
        CREATE INDEX IF NOT EXISTS idx_projetos_canal_listagem ON projetos(canal_listagem_id);

        CREATE TABLE IF NOT EXISTS candidaturas (
            id TEXT PRIMARY KEY,
            projeto_id TEXT NOT NULL,
            dev_id INTEGER NOT NULL,
            dev_username TEXT DEFAULT '',
            empregador_id INTEGER DEFAULT 0,
            thread_id INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'negociando',
            dev_aceito INTEGER DEFAULT 0,
            empregador_aceito INTEGER DEFAULT 0,
            valor_negociado REAL DEFAULT 0,
            prazo_negociado TEXT DEFAULT '',
            escopo_negociado TEXT DEFAULT '',
            data_criacao TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_candidaturas_projeto ON candidaturas(projeto_id);
        CREATE INDEX IF NOT EXISTS idx_candidaturas_dev ON candidaturas(dev_id);
        CREATE INDEX IF NOT EXISTS idx_candidaturas_thread ON candidaturas(thread_id);

        CREATE TABLE IF NOT EXISTS projetos_ativos (
            id TEXT PRIMARY KEY,
            projeto_id TEXT NOT NULL,
            candidatura_id TEXT DEFAULT '',
            dev_id INTEGER NOT NULL,
            empregador_id INTEGER NOT NULL,
            categoria_id INTEGER DEFAULT 0,
            canal_texto_id INTEGER DEFAULT 0,
            canal_voz_id INTEGER DEFAULT 0,
            valor REAL DEFAULT 0,
            prazo TEXT DEFAULT '',
            escopo TEXT DEFAULT '',
            data_inicio TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'ativo',
            regras_confirmadas INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_pativos_status ON projetos_ativos(status);
        CREATE INDEX IF NOT EXISTS idx_pativos_dev ON projetos_ativos(dev_id);
        CREATE INDEX IF NOT EXISTS idx_pativos_canal ON projetos_ativos(canal_texto_id);

        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            timestamp REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cooldowns_user ON cooldowns(user_id, tipo);

        -- Registro de aceite dos Termos de Uso (prova do aceite eletrônico:
        -- quem aceitou, qual versão, quando e em qual contexto).
        CREATE TABLE IF NOT EXISTS aceites_termos (
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            versao TEXT NOT NULL,
            contexto TEXT DEFAULT '',
            data_aceite TEXT NOT NULL,
            PRIMARY KEY (user_id, versao)
        );

        -- Registro de tecnologias/áreas (fonte da verdade — cargos do Discord
        -- são criados dinamicamente a partir desta tabela).
        CREATE TABLE IF NOT EXISTS tecnologias (
            nome TEXT PRIMARY KEY,
            cargo_id INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ativa',    -- ativa, sugerida, rejeitada
            sugerida_por INTEGER DEFAULT 0,
            data_criacao TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            tipo TEXT NOT NULL,
            canal_id INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'aberto',
            data_abertura TEXT DEFAULT '',
            data_fechamento TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_tickets_canal ON tickets(canal_id);

        CREATE TABLE IF NOT EXISTS pagamentos (
            id TEXT PRIMARY KEY,
            projeto_ativo_id TEXT NOT NULL,
            dev_id INTEGER NOT NULL,
            empregador_id INTEGER NOT NULL,
            cobranca_id TEXT DEFAULT '',
            transferencia_id TEXT DEFAULT '',
            valor_total_centavos INTEGER NOT NULL DEFAULT 0,
            taxa_plataforma_centavos INTEGER NOT NULL DEFAULT 0,
            valor_dev_centavos INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'aguardando',
            br_code TEXT DEFAULT '',
            pix_key TEXT DEFAULT '',
            pix_key_type TEXT DEFAULT '',
            canal_id INTEGER DEFAULT 0,
            mensagem_id INTEGER DEFAULT 0,
            dev_mode INTEGER DEFAULT 0,
            data_criacao TEXT DEFAULT '',
            data_pagamento TEXT DEFAULT '',
            data_repasse TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_pagamentos_status ON pagamentos(status);
        CREATE INDEX IF NOT EXISTS idx_pagamentos_cobranca ON pagamentos(cobranca_id);
        CREATE INDEX IF NOT EXISTS idx_pagamentos_pativo ON pagamentos(projeto_ativo_id);
    ''')
    conn.commit()


def _migrar_jsons_antigos(conn: sqlite3.Connection) -> None:
    """Importa dados dos JSONs da versão anterior, se existirem."""
    mapa = {
        'devs_verificados.json': ('devs', DevVerificado),
        'empregadores.json': ('empregadores', Empregador),
        'projetos.json': ('projetos', Projeto),
        'candidaturas.json': ('candidaturas', Candidatura),
        'projetos_ativos.json': ('projetos_ativos', ProjetoAtivo),
    }
    for nome_arquivo, (tabela, classe) in mapa.items():
        caminho = DATA_DIR / nome_arquivo
        if not caminho.exists():
            continue
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                registros = json.load(f)
            if not isinstance(registros, list):
                registros = []
            nomes_campos = {f.name for f in fields(classe)}
            importados = 0
            for reg in registros:
                filtrado = {k: v for k, v in reg.items() if k in nomes_campos}
                obj = classe(**filtrado)
                _upsert(conn, tabela, obj)
                importados += 1
            conn.commit()
            caminho.rename(caminho.with_suffix('.json.migrado'))
            logger.info('Migrados %d registros de %s para a tabela %s', importados, nome_arquivo, tabela)
        except Exception as e:
            logger.error('Erro ao migrar %s: %s', nome_arquivo, e)

    # Cooldowns (formato diferente, sem dataclass)
    cd_path = DATA_DIR / 'cooldowns.json'
    if cd_path.exists():
        try:
            with open(cd_path, 'r', encoding='utf-8') as f:
                registros = json.load(f)
            for reg in registros if isinstance(registros, list) else []:
                conn.execute(
                    'INSERT INTO cooldowns (user_id, tipo, timestamp) VALUES (?, ?, ?)',
                    (reg.get('user_id', 0), reg.get('tipo', ''), reg.get('timestamp', 0)),
                )
            conn.commit()
            cd_path.rename(cd_path.with_suffix('.json.migrado'))
            logger.info('Cooldowns migrados para SQLite')
        except Exception as e:
            logger.error('Erro ao migrar cooldowns.json: %s', e)


# ══════════════════════════════════════════════════════
#  SERIALIZAÇÃO dataclass <-> linha SQL
# ══════════════════════════════════════════════════════

def _para_linha(obj) -> dict:
    """Converte dataclass em dict pronto para o SQLite (listas -> JSON, bool -> int)."""
    nome = type(obj).__name__
    dados = asdict(obj)
    for campo in _CAMPOS_JSON.get(nome, ()):
        dados[campo] = json.dumps(dados[campo], ensure_ascii=False)
    for campo in _CAMPOS_BOOL.get(nome, ()):
        dados[campo] = int(bool(dados[campo]))
    return dados


def _de_linha(classe, linha: sqlite3.Row):
    """Converte linha SQL em dataclass (JSON -> listas, int -> bool)."""
    nome = classe.__name__
    dados = dict(linha)
    for campo in _CAMPOS_JSON.get(nome, ()):
        try:
            dados[campo] = json.loads(dados.get(campo) or '[]')
        except (json.JSONDecodeError, TypeError):
            dados[campo] = []
    for campo in _CAMPOS_BOOL.get(nome, ()):
        dados[campo] = bool(dados.get(campo))
    nomes_campos = {f.name for f in fields(classe)}
    return classe(**{k: v for k, v in dados.items() if k in nomes_campos})


def _upsert(conn: sqlite3.Connection, tabela: str, obj) -> None:
    dados = _para_linha(obj)
    colunas = ', '.join(dados.keys())
    marcadores = ', '.join('?' for _ in dados)
    conn.execute(
        f'INSERT OR REPLACE INTO {tabela} ({colunas}) VALUES ({marcadores})',
        list(dados.values()),
    )


def _salvar(tabela: str, obj) -> None:
    conn = _get_conn()
    with _lock:
        _upsert(conn, tabela, obj)
        conn.commit()


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gerar_id(prefixo: str) -> str:
    return f'{prefixo}_{uuid.uuid4().hex[:8]}'


# ══════════════════════════════════════════════════════
#  DEVS VERIFICADOS
# ══════════════════════════════════════════════════════

def salvar_dev(dev: DevVerificado) -> None:
    """Salva ou atualiza um dev verificado (preserva a chave PIX já cadastrada)."""
    existente = buscar_dev(dev.user_id)
    if existente and not dev.pix_key:
        dev.pix_key = existente.pix_key
        dev.pix_key_type = existente.pix_key_type
        dev.pix_nome = existente.pix_nome
    dev.data_verificacao = dev.data_verificacao or _agora_iso()
    _salvar('devs', dev)
    logger.info('Dev salvo: %s (%d)', dev.username, dev.user_id)


def buscar_dev(user_id: int) -> Optional[DevVerificado]:
    """Busca um dev verificado pelo ID."""
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM devs WHERE user_id = ?', (user_id,)).fetchone()
    return _de_linha(DevVerificado, linha) if linha else None


def listar_devs() -> list[DevVerificado]:
    """Lista todos os devs verificados."""
    conn = _get_conn()
    return [_de_linha(DevVerificado, l) for l in conn.execute('SELECT * FROM devs').fetchall()]


def contar_devs() -> int:
    conn = _get_conn()
    return conn.execute('SELECT COUNT(*) FROM devs').fetchone()[0]


def atualizar_projetos_ativos_dev(user_id: int, delta: int) -> None:
    """Incrementa ou decrementa o contador de projetos ativos de um dev."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            'UPDATE devs SET projetos_ativos = MAX(0, projetos_ativos + ?) WHERE user_id = ?',
            (delta, user_id),
        )
        conn.commit()


def salvar_pix_dev(user_id: int, pix_key: str, pix_key_type: str, pix_nome: str) -> bool:
    """Cadastra/atualiza a chave PIX de um dev. Retorna False se o dev não existe."""
    conn = _get_conn()
    with _lock:
        cursor = conn.execute(
            'UPDATE devs SET pix_key = ?, pix_key_type = ?, pix_nome = ? WHERE user_id = ?',
            (pix_key.strip(), pix_key_type, pix_nome.strip(), user_id),
        )
        conn.commit()
    if cursor.rowcount > 0:
        logger.info('Chave PIX cadastrada para dev %d (tipo=%s)', user_id, pix_key_type)
        return True
    return False


# ══════════════════════════════════════════════════════
#  EMPREGADORES
# ══════════════════════════════════════════════════════

def salvar_empregador(emp: Empregador) -> None:
    """Salva ou atualiza um empregador."""
    emp.data_verificacao = emp.data_verificacao or _agora_iso()
    _salvar('empregadores', emp)
    logger.info('Empregador salvo: %s (%d)', emp.username, emp.user_id)


def buscar_empregador(user_id: int) -> Optional[Empregador]:
    """Busca um empregador pelo ID."""
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM empregadores WHERE user_id = ?', (user_id,)).fetchone()
    return _de_linha(Empregador, linha) if linha else None


def contar_empregadores() -> int:
    conn = _get_conn()
    return conn.execute('SELECT COUNT(*) FROM empregadores').fetchone()[0]


# ══════════════════════════════════════════════════════
#  PROJETOS
# ══════════════════════════════════════════════════════

def salvar_projeto(projeto: Projeto) -> None:
    """Salva ou atualiza um projeto."""
    projeto.id = projeto.id or _gerar_id('proj')
    projeto.data_criacao = projeto.data_criacao or _agora_iso()
    _salvar('projetos', projeto)
    logger.info('Projeto salvo: %s (%s)', projeto.titulo, projeto.id)


def buscar_projeto(projeto_id: str) -> Optional[Projeto]:
    """Busca um projeto pelo ID."""
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,)).fetchone()
    return _de_linha(Projeto, linha) if linha else None


def listar_projetos(status: str = 'aberto') -> list[Projeto]:
    """Lista projetos por status."""
    conn = _get_conn()
    linhas = conn.execute('SELECT * FROM projetos WHERE status = ?', (status,)).fetchall()
    return [_de_linha(Projeto, l) for l in linhas]


def listar_projetos_por_categoria(categoria: str) -> list[Projeto]:
    """Lista projetos abertos de uma categoria."""
    conn = _get_conn()
    linhas = conn.execute(
        "SELECT * FROM projetos WHERE status = 'aberto' AND categoria = ?", (categoria,)
    ).fetchall()
    return [_de_linha(Projeto, l) for l in linhas]


def contar_projetos_por_status() -> dict[str, int]:
    """Retorna {status: quantidade} de todos os projetos."""
    conn = _get_conn()
    linhas = conn.execute('SELECT status, COUNT(*) AS n FROM projetos GROUP BY status').fetchall()
    return {l['status']: l['n'] for l in linhas}


def atualizar_status_projeto(projeto_id: str, novo_status: str) -> None:
    """Atualiza o status de um projeto."""
    conn = _get_conn()
    with _lock:
        conn.execute('UPDATE projetos SET status = ? WHERE id = ?', (novo_status, projeto_id))
        conn.commit()


def adicionar_candidato_projeto(projeto_id: str, dev_id: int) -> None:
    """Adiciona um candidato ao projeto."""
    projeto = buscar_projeto(projeto_id)
    if not projeto:
        return
    if dev_id not in projeto.candidatos:
        projeto.candidatos.append(dev_id)
        _salvar('projetos', projeto)


def remover_candidato_projeto(projeto_id: str, dev_id: int) -> None:
    """Remove um candidato do projeto (libera o dev para se candidatar de novo)."""
    projeto = buscar_projeto(projeto_id)
    if projeto and dev_id in projeto.candidatos:
        projeto.candidatos.remove(dev_id)
        _salvar('projetos', projeto)


def buscar_projeto_por_canal_listagem(canal_id: int) -> Optional[Projeto]:
    """Busca um projeto pelo canal de vitrine onde ele foi publicado."""
    if not canal_id:
        return None
    conn = _get_conn()
    linha = conn.execute(
        'SELECT * FROM projetos WHERE canal_listagem_id = ?', (canal_id,)
    ).fetchone()
    return _de_linha(Projeto, linha) if linha else None


def listar_projetos_empregador(empregador_id: int, status: Optional[str] = None) -> list[Projeto]:
    """Lista projetos de um empregador, opcionalmente filtrados por status."""
    conn = _get_conn()
    if status:
        linhas = conn.execute(
            'SELECT * FROM projetos WHERE empregador_id = ? AND status = ?',
            (empregador_id, status),
        ).fetchall()
    else:
        linhas = conn.execute(
            'SELECT * FROM projetos WHERE empregador_id = ?', (empregador_id,)
        ).fetchall()
    return [_de_linha(Projeto, l) for l in linhas]


# ══════════════════════════════════════════════════════
#  CANDIDATURAS
# ══════════════════════════════════════════════════════

def salvar_candidatura(cand: Candidatura) -> None:
    """Salva ou atualiza uma candidatura."""
    cand.id = cand.id or _gerar_id('cand')
    cand.data_criacao = cand.data_criacao or _agora_iso()
    _salvar('candidaturas', cand)
    logger.info('Candidatura salva: %s', cand.id)


def buscar_candidatura(candidatura_id: str) -> Optional[Candidatura]:
    """Busca uma candidatura pelo ID."""
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM candidaturas WHERE id = ?', (candidatura_id,)).fetchone()
    return _de_linha(Candidatura, linha) if linha else None


def buscar_candidatura_por_thread(thread_id: int) -> Optional[Candidatura]:
    """Busca uma candidatura pela thread/canal de negociação."""
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM candidaturas WHERE thread_id = ?', (thread_id,)).fetchone()
    return _de_linha(Candidatura, linha) if linha else None


def atualizar_candidatura(cand: Candidatura) -> None:
    """Atualiza uma candidatura existente."""
    _salvar('candidaturas', cand)


def listar_candidaturas_projeto(projeto_id: str) -> list[Candidatura]:
    """Lista todas as candidaturas de um projeto."""
    conn = _get_conn()
    linhas = conn.execute('SELECT * FROM candidaturas WHERE projeto_id = ?', (projeto_id,)).fetchall()
    return [_de_linha(Candidatura, l) for l in linhas]


def listar_candidaturas_por_status(status: str) -> list[Candidatura]:
    """Lista candidaturas por status (ex.: 'negociando')."""
    conn = _get_conn()
    linhas = conn.execute('SELECT * FROM candidaturas WHERE status = ?', (status,)).fetchall()
    return [_de_linha(Candidatura, l) for l in linhas]


def contar_candidaturas() -> tuple[int, int]:
    """Retorna (negociando, total)."""
    conn = _get_conn()
    total = conn.execute('SELECT COUNT(*) FROM candidaturas').fetchone()[0]
    ativas = conn.execute("SELECT COUNT(*) FROM candidaturas WHERE status = 'negociando'").fetchone()[0]
    return ativas, total


def listar_candidaturas_dev_por_status(dev_id: int, status: str = 'negociando') -> list[Candidatura]:
    """Lista candidaturas de um dev com determinado status."""
    conn = _get_conn()
    linhas = conn.execute(
        'SELECT * FROM candidaturas WHERE dev_id = ? AND status = ?', (dev_id, status)
    ).fetchall()
    return [_de_linha(Candidatura, l) for l in linhas]


def contar_candidaturas_dev_hoje(dev_id: int) -> int:
    """Conta quantas candidaturas um dev fez hoje (UTC)."""
    conn = _get_conn()
    hoje = datetime.now(timezone.utc).date().isoformat()
    return conn.execute(
        'SELECT COUNT(*) FROM candidaturas WHERE dev_id = ? AND data_criacao LIKE ?',
        (dev_id, f'{hoje}%'),
    ).fetchone()[0]


# ══════════════════════════════════════════════════════
#  PROJETOS ATIVOS
# ══════════════════════════════════════════════════════

def salvar_projeto_ativo(pa: ProjetoAtivo) -> None:
    """Salva um projeto ativo."""
    pa.id = pa.id or _gerar_id('pativo')
    pa.data_inicio = pa.data_inicio or _agora_iso()
    _salvar('projetos_ativos', pa)
    logger.info('Projeto ativo salvo: %s', pa.id)


def buscar_projeto_ativo(projeto_ativo_id: str) -> Optional[ProjetoAtivo]:
    """Busca um projeto ativo pelo ID."""
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM projetos_ativos WHERE id = ?', (projeto_ativo_id,)).fetchone()
    return _de_linha(ProjetoAtivo, linha) if linha else None


def buscar_projeto_ativo_por_canal(canal_id: int) -> Optional[ProjetoAtivo]:
    """Busca um projeto ativo pelo canal de texto."""
    conn = _get_conn()
    linha = conn.execute(
        'SELECT * FROM projetos_ativos WHERE canal_texto_id = ?', (canal_id,)
    ).fetchone()
    return _de_linha(ProjetoAtivo, linha) if linha else None


def buscar_projeto_ativo_por_candidatura(candidatura_id: str) -> Optional[ProjetoAtivo]:
    """Busca um projeto ativo pela candidatura que o originou."""
    conn = _get_conn()
    linha = conn.execute(
        'SELECT * FROM projetos_ativos WHERE candidatura_id = ?', (candidatura_id,)
    ).fetchone()
    return _de_linha(ProjetoAtivo, linha) if linha else None


def listar_projetos_ativos_dev(dev_id: int) -> list[ProjetoAtivo]:
    """Lista projetos ativos de um dev (inclui os aguardando pagamento)."""
    conn = _get_conn()
    linhas = conn.execute(
        "SELECT * FROM projetos_ativos WHERE dev_id = ? AND status IN ('ativo', 'aguardando_pagamento')",
        (dev_id,),
    ).fetchall()
    return [_de_linha(ProjetoAtivo, l) for l in linhas]


def listar_projetos_ativos_por_status(status: str) -> list[ProjetoAtivo]:
    """Lista projetos ativos por status."""
    conn = _get_conn()
    linhas = conn.execute('SELECT * FROM projetos_ativos WHERE status = ?', (status,)).fetchall()
    return [_de_linha(ProjetoAtivo, l) for l in linhas]


def buscar_projeto_ativo_por_ambiente(canal_id: int) -> Optional[ProjetoAtivo]:
    """Busca um projeto ativo por qualquer canal do ambiente (texto, voz ou categoria)."""
    if not canal_id:
        return None
    conn = _get_conn()
    linha = conn.execute(
        'SELECT * FROM projetos_ativos '
        'WHERE canal_texto_id = ? OR canal_voz_id = ? OR categoria_id = ?',
        (canal_id, canal_id, canal_id),
    ).fetchone()
    return _de_linha(ProjetoAtivo, linha) if linha else None


def listar_projetos_ativos_empregador(empregador_id: int) -> list[ProjetoAtivo]:
    """Lista projetos em execução (ou aguardando pagamento) de um empregador."""
    conn = _get_conn()
    linhas = conn.execute(
        "SELECT * FROM projetos_ativos WHERE empregador_id = ? "
        "AND status IN ('ativo', 'aguardando_pagamento')",
        (empregador_id,),
    ).fetchall()
    return [_de_linha(ProjetoAtivo, l) for l in linhas]


def recalcular_projetos_ativos_devs() -> int:
    """
    Recalcula o contador projetos_ativos de todos os devs a partir da tabela
    projetos_ativos (fonte da verdade). Corrige contadores que ficaram
    inconsistentes após exclusões manuais. Retorna quantos devs foram corrigidos.
    """
    conn = _get_conn()
    with _lock:
        cursor = conn.execute('''
            UPDATE devs SET projetos_ativos = (
                SELECT COUNT(*) FROM projetos_ativos pa
                WHERE pa.dev_id = devs.user_id
                  AND pa.status IN ('ativo', 'aguardando_pagamento')
            )
            WHERE projetos_ativos != (
                SELECT COUNT(*) FROM projetos_ativos pa
                WHERE pa.dev_id = devs.user_id
                  AND pa.status IN ('ativo', 'aguardando_pagamento')
            )
        ''')
        conn.commit()
    if cursor.rowcount:
        logger.info('Contador de projetos ativos corrigido para %d devs', cursor.rowcount)
    return cursor.rowcount


def contar_projetos_ativos(status: str = 'ativo') -> int:
    conn = _get_conn()
    return conn.execute(
        'SELECT COUNT(*) FROM projetos_ativos WHERE status = ?', (status,)
    ).fetchone()[0]


def atualizar_projeto_ativo(pa: ProjetoAtivo) -> None:
    """Atualiza um projeto ativo."""
    _salvar('projetos_ativos', pa)


# ══════════════════════════════════════════════════════
#  PAGAMENTOS
# ══════════════════════════════════════════════════════

def salvar_pagamento(pg: Pagamento) -> None:
    """Salva ou atualiza um pagamento."""
    pg.id = pg.id or _gerar_id('pgto')
    pg.data_criacao = pg.data_criacao or _agora_iso()
    _salvar('pagamentos', pg)
    logger.info('Pagamento salvo: %s (status=%s)', pg.id, pg.status)


def buscar_pagamento(pagamento_id: str) -> Optional[Pagamento]:
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM pagamentos WHERE id = ?', (pagamento_id,)).fetchone()
    return _de_linha(Pagamento, linha) if linha else None


def buscar_pagamento_por_cobranca(cobranca_id: str) -> Optional[Pagamento]:
    """Busca um pagamento pelo ID da cobrança na AbacatePay (usado pelo webhook)."""
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM pagamentos WHERE cobranca_id = ?', (cobranca_id,)).fetchone()
    return _de_linha(Pagamento, linha) if linha else None


def buscar_pagamento_pendente_projeto(projeto_ativo_id: str) -> Optional[Pagamento]:
    """Busca cobrança em aberto de um projeto ativo (evita cobrança duplicada)."""
    conn = _get_conn()
    linha = conn.execute(
        "SELECT * FROM pagamentos WHERE projeto_ativo_id = ? AND status = 'aguardando'",
        (projeto_ativo_id,),
    ).fetchone()
    return _de_linha(Pagamento, linha) if linha else None


def listar_pagamentos_por_status(status: str) -> list[Pagamento]:
    conn = _get_conn()
    linhas = conn.execute('SELECT * FROM pagamentos WHERE status = ?', (status,)).fetchall()
    return [_de_linha(Pagamento, l) for l in linhas]


def marcar_pagamento_pago(cobranca_id: str) -> Optional[Pagamento]:
    """
    Marca um pagamento como pago (chamado pelo webhook ou pelo polling).
    Atômico: só transiciona se ainda estiver 'aguardando' — evita repasse duplo.
    Retorna o Pagamento atualizado, ou None se não encontrado/já processado.
    """
    conn = _get_conn()
    with _lock:
        cursor = conn.execute(
            "UPDATE pagamentos SET status = 'pago', data_pagamento = ? "
            "WHERE cobranca_id = ? AND status = 'aguardando'",
            (_agora_iso(), cobranca_id),
        )
        conn.commit()
    if cursor.rowcount == 0:
        return None
    return buscar_pagamento_por_cobranca(cobranca_id)


def marcar_pagamento_em_repasse(pagamento_id: str) -> bool:
    """
    Reivindica um pagamento para processar o repasse (transição atômica
    'aguardando'/'pago' -> 'repassando'). Retorna True apenas para o primeiro
    chamador — garante que o dev nunca recebe o PIX duas vezes, mesmo com
    webhook e polling rodando ao mesmo tempo.
    """
    conn = _get_conn()
    with _lock:
        cursor = conn.execute(
            "UPDATE pagamentos SET status = 'repassando', "
            "data_pagamento = CASE WHEN data_pagamento = '' THEN ? ELSE data_pagamento END "
            "WHERE id = ? AND status IN ('aguardando', 'pago')",
            (_agora_iso(), pagamento_id),
        )
        conn.commit()
    return cursor.rowcount > 0


def marcar_pagamento_repassado(pagamento_id: str, transferencia_id: str) -> None:
    """Marca o repasse ao dev como concluído."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            "UPDATE pagamentos SET status = 'repassado', transferencia_id = ?, data_repasse = ? "
            "WHERE id = ?",
            (transferencia_id, _agora_iso(), pagamento_id),
        )
        conn.commit()


def atualizar_status_pagamento(pagamento_id: str, novo_status: str) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute('UPDATE pagamentos SET status = ? WHERE id = ?', (novo_status, pagamento_id))
        conn.commit()


def somar_receita_plataforma() -> int:
    """Soma (em centavos) das taxas de plataforma de pagamentos concluídos."""
    conn = _get_conn()
    resultado = conn.execute(
        "SELECT COALESCE(SUM(taxa_plataforma_centavos), 0) FROM pagamentos "
        "WHERE status IN ('pago', 'repassado')"
    ).fetchone()
    return resultado[0]


# ══════════════════════════════════════════════════════
#  TECNOLOGIAS
# ══════════════════════════════════════════════════════

@dataclass
class Tecnologia:
    nome: str = ''
    cargo_id: int = 0
    status: str = 'ativa'        # ativa, sugerida, rejeitada
    sugerida_por: int = 0
    data_criacao: str = ''


def listar_tecnologias(status: str = 'ativa') -> list[Tecnologia]:
    conn = _get_conn()
    linhas = conn.execute(
        'SELECT * FROM tecnologias WHERE status = ? ORDER BY nome', (status,)
    ).fetchall()
    return [_de_linha(Tecnologia, l) for l in linhas]


def buscar_tecnologia(nome: str) -> Optional[Tecnologia]:
    """Busca uma tecnologia pelo nome (case-insensitive)."""
    conn = _get_conn()
    linha = conn.execute(
        'SELECT * FROM tecnologias WHERE LOWER(nome) = LOWER(?)', (nome.strip(),)
    ).fetchone()
    return _de_linha(Tecnologia, linha) if linha else None


def salvar_tecnologia(tec: Tecnologia) -> None:
    tec.data_criacao = tec.data_criacao or _agora_iso()
    _salvar('tecnologias', tec)
    logger.info('Tecnologia salva: %s (status=%s)', tec.nome, tec.status)


def atualizar_cargo_tecnologia(nome: str, cargo_id: int) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute('UPDATE tecnologias SET cargo_id = ? WHERE nome = ?', (cargo_id, nome))
        conn.commit()


def atualizar_status_tecnologia(nome: str, status: str) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute('UPDATE tecnologias SET status = ? WHERE nome = ?', (status, nome))
        conn.commit()


# ══════════════════════════════════════════════════════
#  TICKETS
# ══════════════════════════════════════════════════════

@dataclass
class Ticket:
    id: str = ''
    user_id: int = 0
    username: str = ''
    tipo: str = ''
    canal_id: int = 0
    status: str = 'aberto'       # aberto, fechado
    data_abertura: str = ''
    data_fechamento: str = ''


def salvar_ticket(ticket: Ticket) -> None:
    ticket.id = ticket.id or _gerar_id('tkt')
    ticket.data_abertura = ticket.data_abertura or _agora_iso()
    _salvar('tickets', ticket)
    logger.info('Ticket salvo: %s (%s) de %s', ticket.id, ticket.tipo, ticket.username)


def buscar_ticket_por_canal(canal_id: int) -> Optional[Ticket]:
    conn = _get_conn()
    linha = conn.execute('SELECT * FROM tickets WHERE canal_id = ?', (canal_id,)).fetchone()
    return _de_linha(Ticket, linha) if linha else None


def buscar_ticket_aberto_usuario(user_id: int) -> Optional[Ticket]:
    """Retorna o ticket aberto de um usuário, se houver (limite: 1 por vez)."""
    conn = _get_conn()
    linha = conn.execute(
        "SELECT * FROM tickets WHERE user_id = ? AND status = 'aberto'", (user_id,)
    ).fetchone()
    return _de_linha(Ticket, linha) if linha else None


def fechar_ticket(canal_id: int) -> Optional[Ticket]:
    """Marca o ticket do canal como fechado. Retorna o ticket ou None."""
    ticket = buscar_ticket_por_canal(canal_id)
    if not ticket or ticket.status == 'fechado':
        return None
    conn = _get_conn()
    with _lock:
        conn.execute(
            "UPDATE tickets SET status = 'fechado', data_fechamento = ? WHERE canal_id = ?",
            (_agora_iso(), canal_id),
        )
        conn.commit()
    return ticket


def contar_tickets(status: str = 'aberto') -> int:
    conn = _get_conn()
    return conn.execute('SELECT COUNT(*) FROM tickets WHERE status = ?', (status,)).fetchone()[0]


def listar_tickets_por_status(status: str = 'aberto') -> list[Ticket]:
    conn = _get_conn()
    linhas = conn.execute('SELECT * FROM tickets WHERE status = ?', (status,)).fetchall()
    return [_de_linha(Ticket, l) for l in linhas]


# ══════════════════════════════════════════════════════
#  TERMOS DE USO (aceite eletrônico)
# ══════════════════════════════════════════════════════

def registrar_aceite_termos(user_id: int, username: str, versao: str, contexto: str = '') -> None:
    """
    Registra o aceite dos Termos de Uso por um usuário.
    O registro (usuário + versão + data UTC + contexto) é a evidência do
    aceite eletrônico — nunca deletar esta tabela.
    """
    conn = _get_conn()
    with _lock:
        conn.execute(
            'INSERT OR IGNORE INTO aceites_termos (user_id, username, versao, contexto, data_aceite) '
            'VALUES (?, ?, ?, ?, ?)',
            (user_id, username, versao, contexto, _agora_iso()),
        )
        conn.commit()
    logger.info('Aceite dos Termos v%s registrado: %s (%d) [%s]', versao, username, user_id, contexto)


def usuario_aceitou_termos(user_id: int, versao: str) -> bool:
    """Verifica se o usuário aceitou a versão vigente dos Termos de Uso."""
    conn = _get_conn()
    linha = conn.execute(
        'SELECT 1 FROM aceites_termos WHERE user_id = ? AND versao = ?',
        (user_id, versao),
    ).fetchone()
    return linha is not None


def contar_aceites_termos(versao: str) -> int:
    conn = _get_conn()
    return conn.execute(
        'SELECT COUNT(*) FROM aceites_termos WHERE versao = ?', (versao,)
    ).fetchone()[0]


# ══════════════════════════════════════════════════════
#  COOLDOWNS
# ══════════════════════════════════════════════════════

def registrar_cooldown(user_id: int, tipo: str) -> None:
    """Registra um cooldown para um usuário."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            'INSERT INTO cooldowns (user_id, tipo, timestamp) VALUES (?, ?, ?)',
            (user_id, tipo, time.time()),
        )
        conn.commit()


def verificar_cooldown(user_id: int, tipo: str, segundos: int) -> float:
    """
    Verifica se o usuário está em cooldown.
    Retorna 0 se não está, ou os segundos restantes.
    """
    conn = _get_conn()
    linha = conn.execute(
        'SELECT MAX(timestamp) FROM cooldowns WHERE user_id = ? AND tipo = ?',
        (user_id, tipo),
    ).fetchone()
    if not linha or linha[0] is None:
        return 0
    diff = time.time() - linha[0]
    if diff < segundos:
        return round(segundos - diff)
    return 0


def limpar_cooldowns_expirados(segundos_max: int = 86400) -> None:
    """Remove cooldowns com mais de X segundos (padrão: 24h)."""
    conn = _get_conn()
    with _lock:
        conn.execute('DELETE FROM cooldowns WHERE timestamp < ?', (time.time() - segundos_max,))
        conn.commit()
