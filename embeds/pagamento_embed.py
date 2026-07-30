"""
Embeds do fluxo de pagamento (AbacatePay).
"""

import discord
from config.settings import (
    COR_SUCESSO, COR_ALERTA, COR_ERRO, COR_EXECUCAO, COR_PRINCIPAL,
    TAXA_PLATAFORMA_PERCENT,
)
from utils.helpers import formatar_data, formatar_brl_centavos


def criar_embed_cobranca(
    titulo_projeto: str,
    valor_total_centavos: int,
    dev_mention: str,
    empregador_mention: str,
    br_code: str,
    expiracao_minutos: int,
    dev_mode: bool = False,
) -> discord.Embed:
    """Embed com o QR Code PIX para o empregador pagar o projeto."""
    taxa = round(valor_total_centavos * TAXA_PLATAFORMA_PERCENT / 100)
    valor_dev = valor_total_centavos - taxa

    embed = discord.Embed(
        title='💳  Pagamento do Projeto',
        description=(
            f'{empregador_mention}, escaneie o **QR Code** abaixo ou use o '
            f'**PIX copia-e-cola** para pagar o projeto **{titulo_projeto}**.\n\n'
            f'Assim que o pagamento for confirmado, o repasse ao desenvolvedor '
            f'é feito **automaticamente** e o projeto será concluído. ✨'
        ),
        color=COR_PRINCIPAL,
    )
    embed.add_field(
        name='💰  Valor Total',
        value=f'**{formatar_brl_centavos(valor_total_centavos)}**',
        inline=True,
    )
    embed.add_field(
        name=f'👨‍💻  Dev recebe ({100 - TAXA_PLATAFORMA_PERCENT:.0f}%)',
        value=formatar_brl_centavos(valor_dev),
        inline=True,
    )
    embed.add_field(
        name=f'🏦  Taxa Freeela ({TAXA_PLATAFORMA_PERCENT:.0f}%)',
        value=formatar_brl_centavos(taxa),
        inline=True,
    )
    embed.add_field(
        name='📋  PIX Copia-e-Cola',
        value=f'```{br_code[:1000]}```',
        inline=False,
    )
    embed.add_field(
        name='⏰  Validade',
        value=f'Este QR Code expira em **{expiracao_minutos} minutos**.',
        inline=False,
    )
    if dev_mode:
        embed.add_field(
            name='🧪  Modo de Desenvolvimento',
            value='Cobrança de teste — use o botão **Simular Pagamento** para testar o fluxo.',
            inline=False,
        )
    embed.set_image(url='attachment://qrcode_pix.png')
    embed.set_footer(text='Freeela • Pagamento seguro via AbacatePay')
    return embed


def criar_embed_pagamento_confirmado(
    titulo_projeto: str,
    valor_total_centavos: int,
    taxa_centavos: int,
    valor_dev_centavos: int,
    dev_mention: str,
    repasse_ok: bool,
) -> discord.Embed:
    """Embed enviado quando o pagamento é confirmado e o repasse processado."""
    embed = discord.Embed(
        title='✅  Pagamento Confirmado!',
        description=(
            f'O pagamento do projeto **{titulo_projeto}** foi confirmado! 🎉\n\n'
            + (
                f'💸 O repasse de **{formatar_brl_centavos(valor_dev_centavos)}** '
                f'já foi enviado via PIX para {dev_mention}.'
                if repasse_ok else
                f'⚠️ O repasse ao desenvolvedor está **em processamento**. '
                f'A staff foi notificada e o valor será enviado em breve.'
            )
        ),
        color=COR_SUCESSO,
    )
    embed.add_field(
        name='💰  Valor Pago',
        value=formatar_brl_centavos(valor_total_centavos),
        inline=True,
    )
    embed.add_field(
        name='👨‍💻  Repasse ao Dev',
        value=formatar_brl_centavos(valor_dev_centavos),
        inline=True,
    )
    embed.add_field(
        name='🏦  Taxa Freeela',
        value=formatar_brl_centavos(taxa_centavos),
        inline=True,
    )
    embed.set_footer(text=f'Confirmado em {formatar_data()} • Freeela + AbacatePay')
    return embed


def criar_embed_solicitar_pix(dev_mention: str) -> discord.Embed:
    """Embed pedindo ao dev que cadastre a chave PIX antes do pagamento."""
    embed = discord.Embed(
        title='💳  Chave PIX Necessária',
        description=(
            f'{dev_mention}, para receber o pagamento deste projeto você precisa '
            f'**cadastrar sua chave PIX**.\n\n'
            f'Clique no botão abaixo e informe sua chave — o repasse de '
            f'**{100 - TAXA_PLATAFORMA_PERCENT:.0f}%** do valor será enviado '
            f'automaticamente para ela assim que o empregador pagar. 🔐'
        ),
        color=COR_ALERTA,
    )
    embed.set_footer(text='Seus dados ficam armazenados com segurança e são usados apenas para o repasse.')
    return embed


def criar_embed_pix_cadastrado(tipo_label: str, chave_mascarada: str) -> discord.Embed:
    """Confirmação de cadastro da chave PIX."""
    embed = discord.Embed(
        title='✅  Chave PIX Cadastrada!',
        description=(
            'Sua chave foi salva com sucesso. Os pagamentos dos seus projetos '
            'serão enviados automaticamente para ela. 💸'
        ),
        color=COR_SUCESSO,
    )
    embed.add_field(name='🔑  Tipo', value=tipo_label, inline=True)
    embed.add_field(name='🔒  Chave', value=f'`{chave_mascarada}`', inline=True)
    embed.set_footer(text='Você pode atualizar sua chave a qualquer momento com /configurar_pagamento')
    return embed


def criar_embed_erro_repasse(
    pagamento_id: str,
    dev_mention: str,
    valor_dev_centavos: int,
) -> discord.Embed:
    """Alerta para a staff quando o repasse automático falha."""
    embed = discord.Embed(
        title='🚨  Falha no Repasse Automático',
        description=(
            f'O pagamento foi recebido, mas o repasse de '
            f'**{formatar_brl_centavos(valor_dev_centavos)}** para {dev_mention} '
            f'**falhou**.\n\n'
            f'Verifique o saldo/chave na AbacatePay e processe manualmente.\n'
            f'ID do pagamento: `{pagamento_id}`'
        ),
        color=COR_ERRO,
    )
    return embed


def criar_embed_cobranca_cancelada(titulo_projeto: str) -> discord.Embed:
    embed = discord.Embed(
        title='❌  Cobrança Cancelada',
        description=(
            f'A cobrança do projeto **{titulo_projeto}** foi cancelada.\n'
            f'Use **Concluir & Pagar** novamente para gerar um novo QR Code.'
        ),
        color=COR_ERRO,
    )
    return embed


def criar_embed_cobranca_expirada(titulo_projeto: str) -> discord.Embed:
    embed = discord.Embed(
        title='⏰  Cobrança Expirada',
        description=(
            f'O QR Code do projeto **{titulo_projeto}** expirou sem pagamento.\n'
            f'Use **Concluir & Pagar** novamente para gerar um novo QR Code.'
        ),
        color=COR_ALERTA,
    )
    return embed
