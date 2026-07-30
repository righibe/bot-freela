"""
Configurações centrais do sistema Freeela.
Contém IDs de canais, cargos, constantes de validação e mensagens.
"""

import os
import discord
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════
#  CANAIS
# ══════════════════════════════════════════════════════
# O bot NÃO cria nem renomeia canais: a staff monta a estrutura como quiser
# e vincula cada função com /configurar_canal (o comando grava os IDs aqui).
# ID 0 = função ainda sem canal vinculado.
CANAL_COMECE_AQUI = 0
CANAL_TERMOS = 0
CANAL_SUGERIR_TEC = 0
CANAL_VERIFICAR_DEV = 1525187271660277760
CANAL_VERIFICAR_EMPREGADOR = 1503840999615758386          # Atualizar com o ID real
CANAL_ATUALIZAR_PERFIL_DEV = 1525187274331914250                            # Atualizar com o ID real
CATEGORIA_PROJETOS_ID = 1500684318412898427               # Atualizar com o ID real
CATEGORIA_NEGOCIACAO_ID = 1525187265314427081                               # Atualizar com o ID real
CATEGORIA_VERIFICACAO_ID = 1495614476060459038            # Categoria de verificação
CANAL_LOG_DEV = 1497289159344128081                       # Atualizar com o ID real
CANAL_LOG_PROJETOS = 1500684578291978240                  # Atualizar com o ID real
CANAL_REGRAS = 1525186537262809109                        # Canal oficial de regras
CANAL_ABRIR_TICKET = 1525192606072705227                                    # Preenchido pelo setup automático
CATEGORIA_TICKETS_ID = 1525192604898033684                                  # Preenchido pelo setup automático

# ══════════════════════════════════════════════════════
#  CARGOS
# ══════════════════════════════════════════════════════
CARGO_DEV_VERIFICADO = 1500684314999001108
CARGO_EMPREGADOR_VERIFICADO = 1500684315896320012         # Atualizar com o ID real
CARGO_STAFF = 1500684317305868451                         # Atualizar com o ID real
CARGO_TERMOS_ACEITOS = 1525205157867163742                                  # Preenchido pelo setup automático
DEV_ROLE_NAME = 'Desenvolvedor Verificado'

# Função de normalização para melhorar a busca por nome de cargo
def _normalize_role_name(name: str) -> str:
    return ''.join(ch for ch in name.lower() if ch.isalnum() or ch.isspace()).strip()

# Busca o cargo Dev Verificado pelo ID ou pelo nome
def get_cargo_dev_verificado(guild: discord.Guild) -> discord.Role | None:
    """Busca o cargo 'Desenvolvedor Verificado' pelo ID ou pelo nome no servidor."""
    if CARGO_DEV_VERIFICADO:
        cargo = guild.get_role(CARGO_DEV_VERIFICADO)
        if cargo:
            return cargo

    target_name = _normalize_role_name(DEV_ROLE_NAME)
    for role in guild.roles:
        if _normalize_role_name(role.name) == target_name:
            return role

    for role in guild.roles:
        normalized = _normalize_role_name(role.name)
        if target_name in normalized or normalized in target_name:
            return role

    return None

CARGOS_LINGUAGEM = {
    'Java': 1495848927008915801,
    'Python': 1495848994482688121,
    'Rust': 1495849031807799348,
    'JavaScript': 1495849187634577428,
    'Golang': 1495849319910080623,
    'Kotlin': 1495849408762220795,
    'C/C++': 1495849467335938211,
    'Swift': 1495849566140891256,
    'Ruby': 1495849647028179105,
}

CARGOS_EXPERIENCIA = {
    '1_ano': 1501265353068642424,
    '2_anos': 1501265823585665036,
    '4_6_anos': 1501265913117147297,
    '6_mais': 1501266107213021235,
}

# ══════════════════════════════════════════════════════
#  LINGUAGENS
# ══════════════════════════════════════════════════════
LINGUAGENS_OPCOES = [
    'Python', 'Java', 'Rust', 'JavaScript', 'TypeScript',
    'Golang', 'Kotlin', 'C/C++', 'C#', 'Swift', 'Ruby',
]

LINGUAGENS_ALIASES = {
    'python': 'Python', 'java': 'Java', 'rust': 'Rust',
    'javascript': 'JavaScript', 'typescript': 'TypeScript',
    'go': 'Golang', 'golang': 'Golang', 'kotlin': 'Kotlin',
    'c': 'C/C++', 'c++': 'C/C++', 'cpp': 'C/C++',
    'c#': 'C#', 'csharp': 'C#', 'swift': 'Swift', 'ruby': 'Ruby',
}

OPCOES_EXPERIENCIA = [
    ('Até 6 meses', '6_meses'),
    ('1 ano', '1_ano'),
    ('2 anos', '2_anos'),
    ('4 a 6 anos', '4_6_anos'),
    ('6 ou mais anos', '6_mais'),
]

# ══════════════════════════════════════════════════════
#  CATEGORIAS DE PROJETO
# ══════════════════════════════════════════════════════
CATEGORIAS_PROJETO = [
    'Bots', 'SaaS', 'Mobile', 'Web App', 'API / Backend',
    'Automação', 'Data / ML', 'Jogos', 'Desktop', 'Outro',
]

PALAVRAS_CHAVE_CATEGORIA = {
    'Bots': ['bot', 'discord', 'telegram', 'whatsapp', 'chatbot', 'automação de chat', 'slash command'],
    'SaaS': ['saas', 'plataforma', 'dashboard', 'painel', 'assinatura', 'multi-tenant', 'subscription'],
    'Mobile': ['mobile', 'android', 'ios', 'flutter', 'react native', 'app móvel', 'aplicativo'],
    'Web App': ['web', 'site', 'frontend', 'landing page', 'ecommerce', 'loja virtual', 'portal'],
    'API / Backend': ['api', 'backend', 'rest', 'graphql', 'microserviço', 'servidor', 'endpoint'],
    'Automação': ['automação', 'scraping', 'crawler', 'pipeline', 'cron', 'agendamento', 'etl'],
    'Data / ML': ['data', 'machine learning', 'ia', 'inteligência artificial', 'dados', 'modelo', 'treinamento', 'dataset'],
    'Jogos': ['jogo', 'game', 'unity', 'godot', 'pygame', 'unreal'],
    'Desktop': ['desktop', 'electron', 'tauri', 'gui', 'interface gráfica', 'tkinter', 'qt'],
    'Outro': [],
}

STACK_POR_CATEGORIA = {
    'Bots': ['Python', 'JavaScript', 'TypeScript', 'Java', 'Node.js'],
    'SaaS': ['Python', 'JavaScript', 'TypeScript', 'Java', 'C#', 'Ruby', 'Golang', 'Rust'],
    'Mobile': ['Kotlin', 'Swift', 'JavaScript', 'TypeScript', 'React Native', 'Dart'],
    'Web App': ['JavaScript', 'TypeScript', 'React', 'Vue', 'Angular', 'Python', 'Ruby', 'Java', 'C#'],
    'API / Backend': ['Python', 'Java', 'Node.js', 'Golang', 'Rust', 'C#'],
    'Automação': ['Python', 'JavaScript', 'Bash', 'Golang'],
    'Data / ML': ['Python', 'R', 'Julia'],
    'Jogos': ['C#', 'C/C++', 'Python', 'Java'],
    'Desktop': ['Python', 'JavaScript', 'C#', 'Java', 'Rust'],
    'Outro': ['Python', 'JavaScript'],
}

EXPERIENCIA_PROJETO_OPCOES = [
    ('Júnior (até 1 ano)', 'junior'),
    ('Pleno (1-4 anos)', 'pleno'),
    ('Sênior (4+ anos)', 'senior'),
    ('Qualquer nível', 'qualquer'),
]

# ══════════════════════════════════════════════════════
#  SCORES E LIMITES
# ══════════════════════════════════════════════════════
SCORE_COMPATIBILIDADE_MIN = 65
SCORE_INTEGRIDADE_MIN = 70
LINGUAGENS_CONFIRMADAS_MIN = 2

# Tecnologias por dev e regra de match
MAX_TECNOLOGIAS_POR_DEV = 5        # máximo de tecnologias no perfil
MATCH_MIN_TECNOLOGIAS = 2          # mínimo em comum para dar match com um projeto

# Empregador
SCORE_EMPREGADOR_MIN = 60
VALOR_MINIMO_PROJETO = 50.0     # R$
VALOR_MAXIMO_PROJETO = 500000.0  # R$
DESCRICAO_MINIMA_PROJETO = 30   # caracteres

# Proteção
MAX_PROJETOS_ATIVOS_POR_DEV = 3
COOLDOWN_CANDIDATURA_SEGUNDOS = 300     # 5 minutos
COOLDOWN_VERIFICACAO_SEGUNDOS = 3600    # 1 hora
MAX_CANDIDATURAS_DIA = 10
DESCRICAO_MINIMA_INTERESSE = 10

# ══════════════════════════════════════════════════════
#  CORES
# ══════════════════════════════════════════════════════
COR_PRINCIPAL = 5793266
COR_CARD_ACCENT = 0x5682F7   # azul da identidade — faixa lateral dos cards V2
COR_SUCESSO = 5763719
COR_ALERTA = 16705372
COR_ERRO = 15548997
COR_DIAGNOSTICO = 2829617
COR_REVIEW = 15418782
COR_PROJETO = 3447003
COR_MATCHING = 16750899
COR_EXECUCAO = 1752220

# ══════════════════════════════════════════════════════
#  MENSAGENS
# ══════════════════════════════════════════════════════
MSG_REPROVADO_EXPERIENCIA = 'A verificação dev é destinada para membros com pelo menos **1 ano de experiência prática** em programação.'
MSG_VERIFICACAO_INICIADA = 'Sua verificação foi iniciada! Siga as etapas abaixo para completar o processo.'
MSG_PROCESSANDO = '⏳ Estamos analisando seus dados… Isso pode levar alguns segundos.'
MSG_APROVADO = '🎉 **Parabéns!** Você foi aprovado como **Desenvolvedor Verificado**!\nSeus cargos foram atribuídos automaticamente.'
MSG_REVIEW = '📋 Sua verificação foi encaminhada para **revisão manual** pela staff.\nVocê será notificado quando houver uma resposta.'
MSG_ERRO_API = '❌ Ocorreu um erro ao se comunicar com nossos servidores. Tente novamente mais tarde.'
MSG_REPROVADO_AUTO = 'Infelizmente seu perfil não atingiu os requisitos mínimos neste momento.'
MSG_APROVADO_AUTO = '🎉 Parabéns! Sua verificação foi aprovada automaticamente!'

# API
API_BASE_URL = 'http://127.0.0.1:8000'
API_HOST = '127.0.0.1'
API_PORT = 8000

# ══════════════════════════════════════════════════════
#  PAGAMENTOS (AbacatePay)
# ══════════════════════════════════════════════════════
# Chave da API AbacatePay (https://app.abacatepay.com -> Integrações -> API Keys).
# Chaves de desenvolvimento permitem simular pagamentos sem dinheiro real.
ABACATEPAY_API_KEY = os.getenv('ABACATEPAY_API_KEY', '')

# Secret configurado no webhook do painel da AbacatePay (opcional — o bot também
# confirma pagamentos por polling, então o webhook é um acelerador, não requisito).
ABACATEPAY_WEBHOOK_SECRET = os.getenv('ABACATEPAY_WEBHOOK_SECRET', '')

# Percentual retido pela plataforma em cada projeto concluído.
TAXA_PLATAFORMA_PERCENT = float(os.getenv('TAXA_PLATAFORMA_PERCENT', '15'))

# Tempo de validade do QR Code PIX gerado para o empregador (segundos).
PIX_EXPIRACAO_SEGUNDOS = int(os.getenv('PIX_EXPIRACAO_SEGUNDOS', '3600'))

# Intervalo do polling de status da cobrança (segundos).
PIX_POLL_INTERVALO_SEGUNDOS = 20

# ══════════════════════════════════════════════════════
#  TERMOS DE USO
# ══════════════════════════════════════════════════════
# Ao alterar o conteúdo de TERMOS_DE_USO.md, incremente a versão —
# todos os usuários precisarão aceitar novamente.
TERMOS_VERSAO = '1.0'
TERMOS_DATA_VIGENCIA = '10 de julho de 2026'

TIPOS_CHAVE_PIX = [
    ('CPF', 'CPF', '🪪'),
    ('CNPJ', 'CNPJ', '🏢'),
    ('E-mail', 'EMAIL', '📧'),
    ('Telefone', 'PHONE', '📱'),
    ('Chave aleatória', 'RANDOM', '🎲'),
]

# ══════════════════════════════════════════════════════
#  TICKETS
# ══════════════════════════════════════════════════════
# (rótulo, slug, emoji, descrição curta)
TIPOS_TICKET = [
    ('Problema com Pagamento', 'pagamento', '💰', 'Cobrança, repasse ou PIX que não chegou'),
    ('Disputa de Projeto', 'disputa', '⚖️', 'Conflito entre dev e contratante'),
    ('Denúncia', 'denuncia', '🚨', 'Denunciar usuário, golpe ou pagamento por fora'),
    ('Bug / Erro do Bot', 'bug', '🐛', 'Algo não funcionou como deveria'),
    ('Dúvida / Outros', 'duvida', '❓', 'Qualquer outro assunto'),
]