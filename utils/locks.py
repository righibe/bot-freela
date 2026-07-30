"""
Guarda de idempotência para cliques em botões.

Evita que um duplo-clique (ou uma reentrega de interação pelo Discord) crie
recursos duplicados — como threads/tópicos ou canais de negociação.

Como o loop de eventos do discord.py é single-thread, a checagem e a reserva
da chave dentro de ``__enter__`` acontecem sem nenhum ``await`` entre elas,
portanto são atômicas: dois cliques em sequência não conseguem reservar a
mesma chave ao mesmo tempo.
"""

from contextlib import contextmanager

# Chaves atualmente em processamento (ex.: ('empregador', user_id)).
_em_andamento: set = set()


@contextmanager
def guarda_acao(chave):
    """
    Reserva ``chave`` enquanto uma ação está em andamento.

    Uso::

        with guarda_acao(('empregador', user.id)) as livre:
            if not livre:
                return  # já existe uma ação em andamento para esta chave
            ...  # toda a lógica com await fica aqui dentro

    Retorna ``True`` (via ``as livre``) se a chave estava livre e foi
    reservada; ``False`` se já havia uma ação em andamento para ela.
    A chave é sempre liberada ao sair do bloco ``with``.
    """
    livre = chave not in _em_andamento
    if livre:
        _em_andamento.add(chave)
    try:
        yield livre
    finally:
        if livre:
            _em_andamento.discard(chave)
