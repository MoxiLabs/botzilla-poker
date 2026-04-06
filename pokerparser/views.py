import discord
from .core import t

class TournamentView(discord.ui.View):
    """View with Link and Copy Password buttons for a tournament"""
    
    def __init__(self, url: str, password: str, timeout: float = None):
        super().__init__(timeout=timeout)
        self.password = password
        
        # 1. Link Button (External URL)
        if url:
             self.add_item(discord.ui.Button(
                 label=t("btn_link"),
                 style=discord.ButtonStyle.link,
                 url=url
             ))
             
        # 2. Copy Password Button (Ephemeral response)
        if password and password.lower() != "not required":
            copy_btn = discord.ui.Button(
                label=t("btn_copy_pw"),
                style=discord.ButtonStyle.secondary,
                custom_id="copy_pwd"
            )
            copy_btn.callback = self.copy_callback
            self.add_item(copy_btn)

    async def copy_callback(self, interaction: discord.Interaction):
        """Sends the password in an ephemeral message for easy copying"""
        await interaction.response.send_message(
            content=t("password_copied", password=self.password),
            ephemeral=True
        )
