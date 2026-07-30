"""
Fluxo completo de atualização de perfil do dev verificado (3 etapas):

1. Modal — GitHub, LinkedIn e descrição (pré-preenchidos com o perfil atual)
2. Seleção de tecnologias (paginada, pré-marcada com as atuais)
3. Seleção de experiência → revalidação na API → cargos e banco atualizados

Tudo acontece em mensagens ephemeral — nada de threads ou canais extras.
"""

import logging

import discord
from discord.ui import Modal, TextInput, View, Select, Button

from config.settings import (
    COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, COR_ALERTA,
    CARGOS_EXPERIENCIA, OPCOES_EXPERIENCIA, MAX_TECNOLOGIAS_POR_DEV,
)
from services.api_client import validar_dev_via_api
from core.database import DevVerificado, salvar_dev, buscar_dev
from core.tecnologias import nomes_ativas, sincronizar_cargos_membro
from utils.helpers import estimar_senioridade, estimar_area, experiencia_label

logger = logging.getLogger('bot_freeela.modals.atualizar_perfil_dev')

# Experiência mínima de 1 ano — quem já é verificado não pode "voltar" para menos
OPCOES_EXPERIENCIA_UPDATE = [(l, v) for l, v in OPCOES_EXPERIENCIA if v != '6_meses']


class AtualizarPerfilDevModal(Modal, title='Atualizar Perfil — Etapa 1 de 3'):
    """Etapa 1: links e descrição, pré-preenchidos com o perfil atual."""

    def __init__(self, dev: DevVerificado):
        super().__init__()
        self.dev = dev

        self.github = TextInput(
            label='URL do GitHub',
            style=discord.TextStyle.short,
            placeholder='https://github.com/seu-usuario',
            default=dev.github_url or None,
            required=True,
        )
        self.linkedin = TextInput(
            label='URL do LinkedIn (opcional)',
            style=discord.TextStyle.short,
            placeholder='https://linkedin.com/in/seu-usuario',
            default=dev.linkedin_url or None,
            required=False,
        )
        self.descricao = TextInput(
            label='Breve Descrição Profissional',
            style=discord.TextStyle.paragraph,
            placeholder='Sou desenvolvedor com foco em...',
            required=True,
            min_length=20,
            max_length=1000,
        )
        self.add_item(self.github)
        self.add_item(self.linkedin)
        self.add_item(self.descricao)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='🛠️  Etapa 2 de 3 — Suas Tecnologias',
            description=(
                f'Selecione **todas** as tecnologias do seu perfil '
                f'(máx. {MAX_TECNOLOGIAS_POR_DEV}) — a lista substitui a atual.\n\n'
                f'**Atuais:** '
                + (', '.join(f'`{l}`' for l in self.dev.linguagens_confirmadas) or 'nenhuma')
            ),
            color=COR_PRINCIPAL,
        )
        view = SelecaoTecnologiasPerfilView(
            dev=self.dev,
            github=self.github.value.strip(),
            linkedin=(self.linkedin.value or '').strip(),
            descricao=self.descricao.value.strip(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception('Erro na modal de atualização de perfil: %s', error)
        try:
            await interaction.response.send_message(
                '❌ Ocorreu um erro ao processar o formulário.', ephemeral=True,
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                '❌ Ocorreu um erro ao processar o formulário.', ephemeral=True,
            )


class SelecaoTecnologiasPerfilView(View):
    """Etapa 2: selects paginados de tecnologias, pré-marcados com as atuais."""

    def __init__(self, dev: DevVerificado, github: str, linkedin: str, descricao: str):
        super().__init__(timeout=600)
        self.dev = dev
        self.github = github
        self.linkedin = linkedin
        self.descricao = descricao
        self.selecoes_por_pagina: dict[int, list[str]] = {}

        from views.selecao_linguagens import _emoji_tecnologia

        atuais = set(dev.linguagens_confirmadas or [])
        tecnologias = nomes_ativas()
        paginas = [tecnologias[i:i + 25] for i in range(0, len(tecnologias), 25)][:4]

        for indice, pagina in enumerate(paginas):
            # Pré-seleção: quem não mexer no select mantém o que já tinha
            self.selecoes_por_pagina[indice] = [n for n in pagina if n in atuais]
            opcoes = [
                discord.SelectOption(
                    label=nome, value=nome,
                    emoji=_emoji_tecnologia(nome),
                    default=nome in atuais,
                )
                for nome in pagina
            ]
            select = Select(
                placeholder=(
                    f'Tecnologias ({pagina[0][0]}–{pagina[-1][0]})...'
                    if len(paginas) > 1 else
                    f'Selecione até {MAX_TECNOLOGIAS_POR_DEV} tecnologias...'
                ),
                min_values=0,
                max_values=min(MAX_TECNOLOGIAS_POR_DEV, len(opcoes)),
                options=opcoes,
                row=indice,
            )
            select.callback = self._fazer_callback(indice)
            self.add_item(select)

        btn = Button(
            label=f'✅  Confirmar Tecnologias (máx. {MAX_TECNOLOGIAS_POR_DEV})',
            style=discord.ButtonStyle.success,
            row=4,
        )
        btn.callback = self.callback_confirmar
        self.add_item(btn)

    def _fazer_callback(self, indice: int):
        async def callback(interaction: discord.Interaction):
            self.selecoes_por_pagina[indice] = list(interaction.data['values'])
            await interaction.response.defer()
        return callback

    def _selecionadas(self) -> list[str]:
        todas = []
        for pagina in sorted(self.selecoes_por_pagina):
            for nome in self.selecoes_por_pagina[pagina]:
                if nome not in todas:
                    todas.append(nome)
        return todas

    async def callback_confirmar(self, interaction: discord.Interaction):
        selecionadas = self._selecionadas()
        if not selecionadas:
            await interaction.response.send_message(
                '⚠️ Selecione pelo menos **1 tecnologia** antes de confirmar.',
                ephemeral=True,
            )
            return
        if len(selecionadas) > MAX_TECNOLOGIAS_POR_DEV:
            await interaction.response.send_message(
                f'⚠️ Você selecionou **{len(selecionadas)}** tecnologias — o máximo é '
                f'**{MAX_TECNOLOGIAS_POR_DEV}**. Ajuste e confirme de novo.',
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title='📈  Etapa 3 de 3 — Experiência',
            description=(
                'Tecnologias: ' + ', '.join(f'**{l}**' for l in selecionadas) +
                '\n\nAgora selecione seu tempo de experiência para o bot revalidar seu perfil.'
            ),
            color=COR_PRINCIPAL,
        )
        view = SelecaoExperienciaPerfilView(
            dev=self.dev,
            github=self.github,
            linkedin=self.linkedin,
            descricao=self.descricao,
            linguagens=selecionadas,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class SelecaoExperienciaPerfilView(View):
    """Etapa 3: experiência → validação na API → atualização de cargos e banco."""

    def __init__(self, dev: DevVerificado, github: str, linkedin: str,
                 descricao: str, linguagens: list[str]):
        super().__init__(timeout=300)
        self.dev = dev
        self.github = github
        self.linkedin = linkedin
        self.descricao = descricao
        self.linguagens = linguagens

        from views.selecao_experiencia import _emoji_experiencia
        opcoes = [
            discord.SelectOption(
                label=label, value=valor,
                emoji=_emoji_experiencia(valor),
                default=valor == dev.experiencia,
            )
            for label, valor in OPCOES_EXPERIENCIA_UPDATE
        ]
        select = Select(
            placeholder='Selecione seu tempo de experiência...',
            min_values=1, max_values=1, options=opcoes,
        )
        select.callback = self.callback_experiencia
        self.add_item(select)

    async def callback_experiencia(self, interaction: discord.Interaction):
        experiencia = interaction.data['values'][0]

        embed_proc = discord.Embed(
            title='⏳  Validando seu perfil...',
            description='Estamos conferindo seu GitHub e revalidando seus dados. Aguarde alguns segundos.',
            color=COR_ALERTA,
        )
        await interaction.response.edit_message(embed=embed_proc, view=None)

        logger.info(
            'Atualização de perfil: %s (%d) | langs=%s | exp=%s',
            interaction.user.name, interaction.user.id, self.linguagens, experiencia,
        )

        # Atalho de teste — mesmo comportamento da verificação
        if self.github.upper() == 'TESTE':
            resultado_api = {
                'approved': True, 'needs_review': False,
                'compatibility': 100, 'integrity': 100,
                'validated_languages': self.linguagens,
                'rejection_reasons': [],
            }
        else:
            resultado_api = await validar_dev_via_api(
                github=self.github,
                linkedin=self.linkedin,
                descricao=self.descricao,
                linguagens=self.linguagens,
                experiencia=experiencia,
            )

        if not resultado_api:
            await interaction.edit_original_response(embed=discord.Embed(
                title='❌  Erro de Comunicação',
                description='Não foi possível falar com a API de validação. Tente novamente em instantes.',
                color=COR_ERRO,
            ))
            return

        if not resultado_api.get('approved', False):
            if resultado_api.get('needs_review', False):
                await interaction.edit_original_response(embed=discord.Embed(
                    title='📋  Atualização em Revisão',
                    description=(
                        'Sua atualização precisa de **revisão manual da staff**. '
                        'Seu perfil atual continua valendo até a análise.'
                    ),
                    color=COR_ALERTA,
                ))
                logger.info('Atualização de %d enviada para revisão', interaction.user.id)
                return
            motivos = resultado_api.get('rejection_reasons', [])
            await interaction.edit_original_response(embed=discord.Embed(
                title='❌  Atualização Rejeitada',
                description=(
                    'Seu perfil atual foi mantido. Motivos:\n\n'
                    + '\n'.join(f'• {m}' for m in motivos or ['Perfil não atingiu os requisitos.'])
                ),
                color=COR_ERRO,
            ))
            logger.warning('Atualização de %d rejeitada: %s', interaction.user.id, motivos)
            return

        # Aprovado — aplicar cargos e salvar
        try:
            await self._aplicar_atualizacao(interaction, experiencia, resultado_api)
        except Exception as e:
            logger.exception('Erro ao aplicar atualização de perfil: %s', e)
            await interaction.edit_original_response(embed=discord.Embed(
                title='⚠️  Erro ao Atualizar Cargos',
                description='Seus dados foram validados, mas houve um erro ao atualizar os cargos. Contate a staff.',
                color=COR_ALERTA,
            ))

    async def _aplicar_atualizacao(
        self,
        interaction: discord.Interaction,
        experiencia: str,
        resultado_api: dict,
    ):
        user = interaction.user
        guild = interaction.guild

        # Cargo de experiência: remove os antigos e aplica o novo
        for exp_key, cargo_id in CARGOS_EXPERIENCIA.items():
            cargo = guild.get_role(cargo_id)
            if not cargo:
                continue
            try:
                if exp_key == experiencia and cargo not in user.roles:
                    await user.add_roles(cargo, reason='Atualização de perfil')
                elif exp_key != experiencia and cargo in user.roles:
                    await user.remove_roles(cargo, reason='Atualização de perfil')
            except discord.Forbidden:
                logger.error('Sem permissão para ajustar cargo de experiência de %s', user.name)

        # Cargos de tecnologia: sincroniza com a nova lista (remove os que saíram)
        await sincronizar_cargos_membro(user, self.linguagens, remover_antigos=True)

        # Banco: atualiza o perfil preservando PIX (salvar_dev cuida disso)
        dev = buscar_dev(user.id) or self.dev
        dev.user_id = user.id
        dev.username = user.name
        dev.linguagens_confirmadas = self.linguagens
        dev.experiencia = experiencia
        dev.github_url = self.github
        dev.linkedin_url = self.linkedin
        dev.compatibilidade = resultado_api.get('compatibility', dev.compatibilidade)
        dev.integridade = resultado_api.get('integrity', dev.integridade)
        dev.senioridade = estimar_senioridade(experiencia, dev.compatibilidade)
        dev.area = estimar_area(self.linguagens)
        salvar_dev(dev)

        confirmadas = resultado_api.get('validated_languages', []) or []
        embed = discord.Embed(
            title='✅  Perfil Atualizado com Sucesso!',
            description='Seus dados foram revalidados e seus cargos, sincronizados.',
            color=COR_SUCESSO,
        )
        embed.add_field(
            name='🛠️  Tecnologias',
            value=', '.join(f'`{l}`' for l in self.linguagens),
            inline=False,
        )
        if confirmadas:
            embed.add_field(
                name='🔎  Confirmadas no GitHub',
                value=', '.join(f'`{l}`' for l in confirmadas),
                inline=False,
            )
        embed.add_field(name='📈  Experiência', value=experiencia_label(experiencia), inline=True)
        embed.add_field(name='📂  Área', value=dev.area, inline=True)
        embed.set_footer(text='Sua chave PIX cadastrada não foi alterada 💳')
        await interaction.edit_original_response(embed=embed)
        logger.info('Perfil de %s (%d) atualizado com sucesso', user.name, user.id)
