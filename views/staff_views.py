import discord
from discord.ui import View, Button
from config.settings import COR_SUCESSO, COR_ERRO
import logging
import re

logger = logging.getLogger('bot_freeela.views.staff_views')

class StaffReviewView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        btn_aprovar = Button(label='Aprovar Manualmente', style=discord.ButtonStyle.success, custom_id='staff_approve', emoji='✅')
        btn_aprovar.callback = self.aprovar_btn
        self.add_item(btn_aprovar)
        
        btn_rejeitar = Button(label='Rejeitar', style=discord.ButtonStyle.danger, custom_id='staff_reject', emoji='❌')
        btn_rejeitar.callback = self.rejeitar_btn
        self.add_item(btn_rejeitar)

    def _get_cargo_por_id(self, guild: discord.Guild, role_id: int) -> discord.Role | None:
        from config.settings import get_cargo_dev_verificado, CARGO_DEV_VERIFICADO

        # Se é o cargo de dev verificado, usa a busca robusta por nome ou ID
        if role_id == CARGO_DEV_VERIFICADO:
            cargo = get_cargo_dev_verificado(guild)
            if cargo:
                logger.info('Cargo dev verificado encontrado: %s (ID: %s)', cargo.name, cargo.id)
                return cargo
            logger.error('Cargo dev verificado não encontrado no servidor %s', guild.name)
            return None

        if not role_id:
            logger.error('Role ID não fornecido')
            return None

        cargo = guild.get_role(role_id)
        if cargo:
            logger.info('Cargo encontrado por ID: %s (ID: %s)', cargo.name, cargo.id)
            return cargo

        logger.error('Cargo com ID %s não encontrado no servidor %s', role_id, guild.name)
        return None

    def _localizar_categoria(self, guild: discord.Guild, category_id: int, fallback_name: str) -> discord.CategoryChannel | None:
        import unicodedata

        def normalize(text: str) -> str:
            return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()

        categoria = guild.get_channel(category_id)
        if isinstance(categoria, discord.CategoryChannel):
            return categoria
        if isinstance(categoria, discord.TextChannel) and categoria.category:
            return categoria.category
        normalized_fallback = normalize(fallback_name)
        for cat in guild.categories:
            name = normalize(cat.name)
            if name == normalized_fallback or normalized_fallback in name or name in normalized_fallback:
                return cat
        return None

    def _get_user_info_from_embed(self, embed: discord.Embed):
        user_id = None
        projeto_id = None
        tipo = 'dev'
        if 'Empregador' in (embed.title or ''):
            tipo = 'empregador'
            
        for field in embed.fields:
            if 'User ID' in field.name or 'Empregador' in field.name:
                match = re.search(r'`(\d+)`', field.value)
                if match:
                    user_id = int(match.group(1))
            if 'ID do Projeto' in field.name or 'ID:' in field.value:
                match = re.search(r'`(proj[-_][^`]+)`', field.value)
                if match:
                    projeto_id = match.group(1)
        if not projeto_id and embed.description:
            match = re.search(r'`(proj[-_][^`]+)`', embed.description)
            if match:
                projeto_id = match.group(1)
        return user_id, tipo, projeto_id

    async def aprovar_btn(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        embed = interaction.message.embeds[0]
        user_id, tipo, projeto_id = self._get_user_info_from_embed(embed)
        
        if not user_id:
            await interaction.followup.send('Não foi possível encontrar o ID do usuário nesta embed.', ephemeral=True)
            return
            
        user = interaction.guild.get_member(user_id)
        if not user:
            try:
                user = await interaction.guild.fetch_member(user_id)
            except discord.NotFound:
                user = None
            except Exception as e:
                logger.error('Erro ao buscar membro: %s', e)
                user = None

        if not user:
            await interaction.followup.send('Usuário não encontrado no servidor.', ephemeral=True)
            return

        from config.settings import CARGO_DEV_VERIFICADO, CARGO_EMPREGADOR_VERIFICADO
        cargo_id = CARGO_DEV_VERIFICADO if tipo == 'dev' else CARGO_EMPREGADOR_VERIFICADO

        cargo = self._get_cargo_por_id(interaction.guild, cargo_id)

        if not cargo:
            logger.error('Cargo de verificação não encontrado ou não pôde ser criado: %s', cargo_id)
            await interaction.followup.send('Erro: cargo de verificação não encontrado no servidor.', ephemeral=True)
            return

        cargo_assigned = True
        # Verificar se o bot tem permissão para gerenciar roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            cargo_assigned = False
            logger.error('Bot não tem permissão para gerenciar roles no servidor %s', interaction.guild.name)
            await interaction.followup.send(
                '⚠️ Projeto aprovado, mas não tenho permissão para atribuir o cargo de verificado. O projeto continuará sendo publicado.',
                ephemeral=True,
            )
        elif cargo.position >= interaction.guild.me.top_role.position:
            cargo_assigned = False
            logger.error('Cargo %s está acima do cargo mais alto do bot (%s)', cargo.name, interaction.guild.me.top_role.name)
            await interaction.followup.send(
                '⚠️ Projeto aprovado, mas o cargo de verificado está acima do meu cargo mais alto. O projeto continuará sendo publicado.',
                ephemeral=True,
            )
        else:
            try:
                await user.add_roles(cargo, reason=f'Aprovado manualmente por {interaction.user.name}')
                logger.info('Cargo %s atribuído com sucesso ao usuário %s na aprovação manual', cargo.name, user.name)
            except discord.Forbidden:
                cargo_assigned = False
                logger.error('Sem permissão para adicionar cargo %s a %s', cargo_id, user.id)
                await interaction.followup.send(
                    '⚠️ Projeto aprovado, mas não tenho permissão para atribuir o cargo de verificado. O projeto continuará sendo publicado.',
                    ephemeral=True,
                )
            except Exception as e:
                cargo_assigned = False
                logger.error('Erro ao adicionar cargo: %s', e)
                await interaction.followup.send(
                    '⚠️ Projeto aprovado, mas ocorreu um erro ao atribuir o cargo de verificado. O projeto continuará sendo publicado.',
                    ephemeral=True,
                )

        embed.color = COR_SUCESSO
        embed.title = f"✅ APROVADO MANUALMENTE por {interaction.user.name}"
        
        for child in self.children:
            child.disabled = True
        
        await interaction.message.edit(embed=embed, view=self)

        try:
            await user.send(f"🎉 Sua solicitação como **{tipo.upper()}** foi **APROVADA** manualmente pela nossa staff!")
        except Exception:
            pass

        if tipo == 'empregador' and projeto_id:
            from core.database import buscar_projeto, salvar_projeto
            projeto = buscar_projeto(projeto_id)
            if not projeto:
                await interaction.followup.send('⚠️ Projeto não encontrado para publicação. Verifique o ID.', ephemeral=True)
                return

            from config.settings import CATEGORIA_PROJETOS_ID
            categoria_projetos = self._localizar_categoria(
                interaction.guild,
                CATEGORIA_PROJETOS_ID,
                'Projetos Disponíveis'
            )
            if not categoria_projetos:
                await interaction.followup.send(
                    '⚠️ Projeto aprovado, mas a categoria "Projetos Disponíveis" não foi encontrada. Verifique o ID ou o nome da categoria.',
                    ephemeral=True,
                )
                return

            if projeto.status == 'aberto':
                await interaction.followup.send('✅ Projeto já está publicado em Projetos Disponíveis.', ephemeral=True)
                return

            previous_status = projeto.status
            projeto.status = 'aberto'
            salvar_projeto(projeto)

            try:
                from utils.helpers import nome_canal_projeto
                nome_canal = nome_canal_projeto(projeto.categoria, projeto.titulo)
                canal_projeto = await interaction.guild.create_text_channel(nome_canal, category=categoria_projetos)

                from embeds.projeto_embed import criar_embed_projeto_listagem
                from views.projeto_views import ProjetoInteresseView
                from dataclasses import asdict

                embed_listagem = criar_embed_projeto_listagem(asdict(projeto))
                view_int = ProjetoInteresseView(projeto_id=projeto.id)

                from core.tecnologias import mapa_cargos
                cargos_tec = mapa_cargos()
                pings = []
                for lang in projeto.linguagens_requeridas:
                    if lang in cargos_tec:
                        cargo_lang = interaction.guild.get_role(cargos_tec[lang])
                        if cargo_lang:
                            pings.append(cargo_lang.mention)

                content_msg = f"{' '.join(pings)} 🚀 Novo projeto postado: **{', '.join(projeto.linguagens_requeridas)}**!" if pings else ''
                msg = await canal_projeto.send(content=content_msg, embed=embed_listagem, view=view_int)
                projeto.message_id = msg.id
                projeto.canal_listagem_id = canal_projeto.id
                salvar_projeto(projeto)
                
                # Disparar DM para os Devs que têm a stack (Mesclagem)
                from core.database import listar_devs
                devs = listar_devs()
                for dev in devs:
                    dev_langs = set(dev.linguagens_confirmadas or [])
                    proj_langs = set(projeto.linguagens_requeridas)
                    match = dev_langs.intersection(proj_langs)
                    if match:
                        membro_dev = interaction.guild.get_member(dev.user_id)
                        if not membro_dev:
                            try:
                                membro_dev = await interaction.guild.fetch_member(dev.user_id)
                            except Exception:
                                membro_dev = None
                        if membro_dev:
                            try:
                                link_msg = msg.jump_url
                                await membro_dev.send(
                                    f"🚀 **Match de Projeto!**\n\nUm novo projeto que precisa de **{', '.join(match)}** "
                                    f"foi postado!\nCorre no canal {canal_projeto.mention} para clicar em **Tenho Interesse**.\n\n🔗 Link direto: {link_msg}"
                                )
                                logger.info("Notificação DM enviada para o dev %s sobre o projeto %s", membro_dev.name, projeto.id)
                            except Exception:
                                pass

                await interaction.followup.send('✅ Projeto publicado na vitrine!', ephemeral=True)
            except discord.Forbidden as e:
                logger.error('Sem permissão para criar canal ou enviar mensagem: %s', e)
                projeto.status = previous_status
                salvar_projeto(projeto)
                await interaction.followup.send('Erro: não tenho permissão para publicar o projeto na categoria. O status foi revertido.', ephemeral=True)
            except Exception as e:
                logger.error('Erro ao publicar projeto: %s', e)
                projeto.status = previous_status
                salvar_projeto(projeto)
                await interaction.followup.send('Erro ao publicar o projeto em Projetos Disponíveis. O status foi revertido.', ephemeral=True)

    async def rejeitar_btn(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        user_id, tipo, projeto_id = self._get_user_info_from_embed(embed)
        
        embed.color = COR_ERRO
        embed.title = f"❌ REJEITADO por {interaction.user.name}"
        
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=self)
        
        if projeto_id:
            from core.database import buscar_projeto, salvar_projeto
            projeto = buscar_projeto(projeto_id)
            if projeto and projeto.status == 'pendente':
                projeto.status = 'rejeitado'
                salvar_projeto(projeto)
        
        if user_id:
            user = interaction.guild.get_member(user_id)
            if user:
                try:
                    await user.send(f"❌ Sua solicitação como **{tipo.upper()}** foi **REJEITADA** pela nossa staff. Se achar que houve um engano, entre em contato no servidor.")
                except:
                    pass

