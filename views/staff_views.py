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

    def _get_user_info_from_embed(self, embed: discord.Embed):
        user_id = None
        projeto_id = None
        tipo = 'dev'
        if 'Empregador' in embed.title:
            tipo = 'empregador'
            
        for field in embed.fields:
            if 'User ID' in field.name or 'Empregador' in field.name:
                match = re.search(r'`(\d+)`', field.value)
                if match:
                    user_id = int(match.group(1))
            if 'ID do Projeto' in field.name or 'ID:' in field.value:
                match = re.search(r'`(proj-[^`]+)`', field.value)
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
            await interaction.followup.send('Usuário não encontrado no servidor.', ephemeral=True)
            return

        from config.settings import CARGO_DEV_VERIFICADO, CARGO_EMPREGADOR_VERIFICADO
        cargo_id = CARGO_DEV_VERIFICADO if tipo == 'dev' else CARGO_EMPREGADOR_VERIFICADO
        cargo = interaction.guild.get_role(cargo_id)
        
        if cargo:
            try:
                await user.add_roles(cargo, reason=f'Aprovado manualmente por {interaction.user.name}')
                
                embed.color = COR_SUCESSO
                embed.title = f"✅ APROVADO MANUALMENTE por {interaction.user.name}"
                
                for child in self.children:
                    child.disabled = True
                
                await interaction.message.edit(embed=embed, view=self)
                
                try:
                    await user.send(f"🎉 Sua solicitação como **{tipo.upper()}** foi **APROVADA** manualmente pela nossa staff!")
                except:
                    pass
                    
                # Publicar o projeto pendente se existir
                if tipo == 'empregador' and projeto_id:
                    from core.database import buscar_projeto, salvar_projeto
                    projeto = buscar_projeto(projeto_id)
                    if projeto and projeto.status == 'pendente':
                        projeto.status = 'aberto'
                        salvar_projeto(projeto)
                        
                        from config.settings import CATEGORIA_PROJETOS_ID, CARGOS_LINGUAGEM
                        categoria_projetos = interaction.guild.get_channel(CATEGORIA_PROJETOS_ID)
                        if categoria_projetos and isinstance(categoria_projetos, discord.CategoryChannel):
                            import re
                            nome_canal = f"{projeto.categoria[:10].lower()}-{projeto.titulo[:15].lower().replace(' ', '-')}"
                            nome_canal = re.sub(r'[^a-z0-9\-]', '', nome_canal)
                            canal_projeto = await interaction.guild.create_text_channel(nome_canal, category=categoria_projetos)
                            
                            from embeds.projeto_embed import criar_embed_projeto_listagem
                            from views.projeto_views import ProjetoInteresseView
                            from dataclasses import asdict
                            
                            embed_listagem = criar_embed_projeto_listagem(asdict(projeto))
                            view_int = ProjetoInteresseView(projeto_id=projeto.id)
                            
                            pings = []
                            for lang in projeto.linguagens_requeridas:
                                if lang in CARGOS_LINGUAGEM:
                                    cargo_lang = interaction.guild.get_role(CARGOS_LINGUAGEM[lang])
                                    if cargo_lang:
                                        pings.append(cargo_lang.mention)
                                        
                            content_msg = f"{' '.join(pings)} 🚀 Novo projeto postado: **{', '.join(projeto.linguagens_requeridas)}**!" if pings else ""
                            msg = await canal_projeto.send(content=content_msg, embed=embed_listagem, view=view_int)
                            projeto.message_id = msg.id
                            salvar_projeto(projeto)
                            await interaction.followup.send('✅ Projeto publicado na vitrine!', ephemeral=True)
                
            except Exception as e:
                logger.error('Erro ao aprovar manualmente: %s', e)
                await interaction.followup.send('Erro ao dar o cargo ou publicar projeto.', ephemeral=True)

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

