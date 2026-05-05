"""
Views para o sistema de empregadores.
Botão para iniciar verificação e seleção de categoria.
"""

import logging
import discord
from discord.ui import View, Button, Select
from config.settings import CATEGORIAS_PROJETO, COR_PRINCIPAL
from modals.empregador_modal import EmpregadorModal

logger = logging.getLogger('bot_freeela.views.empregador')


class IniciarEmpregadorView(View):
    """View com botão para iniciar a verificação de empregador."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='📋  Criar Projeto',
        style=discord.ButtonStyle.success,
        custom_id='btn_iniciar_empregador',
        row=0,
    )
    async def btn_iniciar(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        channel = interaction.channel
        user = interaction.user

        if not guild or not channel:
            await interaction.response.send_message(
                '❌ Erro interno. Tente novamente.',
                ephemeral=True,
            )
            return

        # Verificar se já tem thread ativa
        for thread in channel.threads:
            if thread.name == f'projeto-{user.name}' and not thread.archived:
                await interaction.response.send_message(
                    f'⚠️ Você já possui uma verificação em andamento: {thread.mention}',
                    ephemeral=True,
                )
                return

        try:
            # Criar thread privada
            thread = await channel.create_thread(
                name=f'projeto-{user.name}',
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,  # 24 horas
                reason=f'Cadastro de projeto por {user.name}',
            )
            await thread.add_user(user)

            embed = discord.Embed(
                title='🏢  Cadastro de Projeto',
                description=(
                    f'Olá {user.mention}!\n\n'
                    f'Para cadastrar seu projeto, selecione primeiro a **categoria** abaixo.\n'
                    f'Em seguida, preencha o formulário completo.'
                ),
                color=COR_PRINCIPAL,
            )
            embed.set_footer(text='Esta thread é privada.')

            view = SelecaoCategoriaView(user_id=user.id, thread=thread)
            await thread.send(embed=embed, view=view)

            await interaction.response.send_message(
                f'✅ Seu cadastro foi iniciado! Acesse: {thread.mention}',
                ephemeral=True,
            )
            logger.info('Thread de empregador criada para %s', user.name)

        except discord.Forbidden:
            await interaction.response.send_message(
                '❌ Sem permissão para criar threads.',
                ephemeral=True,
            )
        except Exception as e:
            await interaction.response.send_message(
                '❌ Erro ao iniciar o cadastro.',
                ephemeral=True,
            )
            logger.exception('Erro ao criar thread de empregador: %s', e)


class SelecaoCategoriaView(View):
    """View para selecionar a categoria do projeto."""

    def __init__(self, user_id: int, thread: discord.Thread):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.thread = thread

        emojis = {
            'Bots': '🤖', 'SaaS': '☁️', 'Mobile': '📱',
            'Web App': '🌐', 'API / Backend': '⚙️', 'Automação': '🔄',
            'Data / ML': '📊', 'Jogos': '🎮', 'Desktop': '🖥️', 'Outro': '📦',
        }

        opcoes = [
            discord.SelectOption(
                label=cat,
                value=cat,
                emoji=emojis.get(cat, '📦'),
            )
            for cat in CATEGORIAS_PROJETO
        ]

        select = Select(
            placeholder='Selecione a categoria do projeto...',
            min_values=1,
            max_values=1,
            options=opcoes,
            custom_id='select_categoria_projeto',
        )
        select.callback = self.callback_categoria
        self.add_item(select)

    async def callback_categoria(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                '❌ Apenas o empregador pode interagir.',
                ephemeral=True,
            )
            return

        categoria = interaction.data['values'][0]
        modal = EmpregadorModal(
            user_id=self.user_id,
            thread=self.thread,
            categoria=categoria,
        )
        await interaction.response.send_modal(modal)
        logger.info('Categoria selecionada por %s: %s', interaction.user.name, categoria)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
