import json
import os
import random
from collections import Counter
from datetime import date
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import db
import images

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = os.environ.get("DISCORD_GUILD_ID") or None

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
MEDAL_DIR = ASSETS / "medals"
TEMPLATE_PATH = ASSETS / "template.png"

MEDALS: list[dict] = json.loads((ROOT / "medals.json").read_text())
MEDAL_BY_ID = {m["id"]: m for m in MEDALS}

MAX_DRAWS = 5

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    db.init()
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()
    print(f"Logged in as {bot.user} ({bot.user.id})")


def medal_path(medal_id: int) -> Path:
    return MEDAL_DIR / MEDAL_BY_ID[medal_id]["image"]


# ---------------------------------------------------------------------------
# /draw
# ---------------------------------------------------------------------------

@bot.tree.command(
    name="draw",
    description="Draw a random Fiesta medal (once per day, up to five total).",
)
async def draw(interaction: discord.Interaction):
    user_id = interaction.user.id
    db.ensure_user(user_id)
    state = db.get_user(user_id)
    today = date.today().isoformat()

    if state["draws_used"] >= MAX_DRAWS:
        await interaction.response.send_message(
            f"You've used all {MAX_DRAWS} of your medal draws. "
            "Trade with other collectors to complete your set!",
            ephemeral=True,
        )
        return

    if state["last_draw_date"] == today:
        await interaction.response.send_message(
            "You've already drawn today. Come back tomorrow!",
            ephemeral=True,
        )
        return

    medal = random.choice(MEDALS)
    db.record_draw(user_id, medal["id"], today)

    remaining = MAX_DRAWS - (state["draws_used"] + 1)
    file = discord.File(medal_path(medal["id"]), filename=medal["image"])
    embed = discord.Embed(
        title=f"You drew: {medal['name']}",
        description=f"{medal['description']}\n\nDraws remaining: **{remaining}**",
        color=discord.Color.gold(),
    )
    embed.set_image(url=f"attachment://{medal['image']}")
    await interaction.response.send_message(embed=embed, file=file)


# ---------------------------------------------------------------------------
# /collection
# ---------------------------------------------------------------------------

@bot.tree.command(
    name="collection",
    description="Show your current Fiesta medal collection.",
)
async def collection(interaction: discord.Interaction):
    inv = db.get_inventory(interaction.user.id)
    if not inv:
        await interaction.response.send_message(
            "You don't have any medals yet — try `/draw`.",
            ephemeral=True,
        )
        return

    paths = [str(medal_path(mid)) for mid in inv]
    buf = images.collage(paths)
    file = discord.File(buf, filename="collection.png")
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s collection",
        color=discord.Color.gold(),
    )
    embed.set_image(url="attachment://collection.png")
    await interaction.response.send_message(embed=embed, file=file)


# ---------------------------------------------------------------------------
# /wear
# ---------------------------------------------------------------------------

@bot.tree.command(
    name="wear",
    description="Show your medals pinned on the shirt or bag template.",
)
async def wear(interaction: discord.Interaction):
    if not TEMPLATE_PATH.exists():
        await interaction.response.send_message(
            "No shirt or bag template has been set up yet. Stay tuned!",
            ephemeral=True,
        )
        return

    inv = db.get_inventory(interaction.user.id)
    if not inv:
        await interaction.response.send_message(
            "You don't have any medals yet — try `/draw`.",
            ephemeral=True,
        )
        return

    paths = [str(medal_path(mid)) for mid in inv]
    buf = images.wear(paths, str(TEMPLATE_PATH))
    file = discord.File(buf, filename="wear.png")
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s look",
        color=discord.Color.gold(),
    )
    embed.set_image(url="attachment://wear.png")
    await interaction.response.send_message(embed=embed, file=file)


# ---------------------------------------------------------------------------
# /trade
# ---------------------------------------------------------------------------

class MedalSelect(discord.ui.Select):
    def __init__(self, owner_id: int, owner_inv: list[int], placeholder: str):
        counts = Counter(owner_inv)
        options = [
            discord.SelectOption(
                label=f"{MEDAL_BY_ID[mid]['name']} (x{c})",
                value=str(mid),
            )
            for mid, c in counts.items()
        ]
        super().__init__(
            placeholder=placeholder,
            options=options,
            min_values=1,
            max_values=1,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This selection isn't yours.", ephemeral=True
            )
            return
        await self.view.on_pick(interaction, int(self.values[0]))


class InitiatorSelectView(discord.ui.View):
    def __init__(self, initiator_id: int, initiator_inv: list[int], target: discord.Member):
        super().__init__(timeout=300)
        self.initiator_id = initiator_id
        self.target = target
        self.add_item(MedalSelect(initiator_id, initiator_inv, "Choose a medal to offer..."))

    async def on_pick(self, interaction: discord.Interaction, medal_id: int):
        target_inv = db.get_inventory(self.target.id)
        if not target_inv:
            await interaction.response.edit_message(
                content=f"{self.target.display_name} has no medals to trade.",
                view=None,
            )
            return

        for child in self.children:
            child.disabled = True
        offered = MEDAL_BY_ID[medal_id]
        await interaction.response.edit_message(
            content=f"You offered **{offered['name']}**. Waiting for {self.target.display_name}...",
            view=self,
        )
        await interaction.followup.send(
            content=(
                f"{self.target.mention}, {interaction.user.display_name} wants to trade "
                f"their **{offered['name']}**. Pick one of your medals to offer in return:"
            ),
            view=TargetSelectView(
                target_id=self.target.id,
                target_inv=target_inv,
                initiator=interaction.user,
                initiator_medal=medal_id,
            ),
        )


class TargetSelectView(discord.ui.View):
    def __init__(
        self,
        target_id: int,
        target_inv: list[int],
        initiator: discord.abc.User,
        initiator_medal: int,
    ):
        super().__init__(timeout=600)
        self.target_id = target_id
        self.initiator = initiator
        self.initiator_medal = initiator_medal
        self.add_item(MedalSelect(target_id, target_inv, "Choose a medal to offer in return..."))

    async def on_pick(self, interaction: discord.Interaction, target_medal: int):
        for child in self.children:
            child.disabled = True

        i_medal = MEDAL_BY_ID[self.initiator_medal]
        t_medal = MEDAL_BY_ID[target_medal]

        await interaction.response.edit_message(
            content=f"{interaction.user.display_name} offered **{t_medal['name']}** in return.",
            view=self,
        )
        await interaction.followup.send(
            content=(
                f"{self.initiator.mention}, do you confirm exchanging your "
                f"**{i_medal['name']}** for {interaction.user.display_name}'s **{t_medal['name']}**?"
            ),
            view=ConfirmView(
                initiator_id=self.initiator.id,
                target_id=self.target_id,
                initiator_medal=self.initiator_medal,
                target_medal=target_medal,
            ),
        )


class ConfirmView(discord.ui.View):
    def __init__(
        self,
        initiator_id: int,
        target_id: int,
        initiator_medal: int,
        target_medal: int,
    ):
        super().__init__(timeout=600)
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.initiator_medal = initiator_medal
        self.target_medal = target_medal

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.initiator_id:
            await interaction.response.send_message(
                "Only the trade initiator can confirm.", ephemeral=True
            )
            return

        if not db.has_medal(self.initiator_id, self.initiator_medal):
            await interaction.response.edit_message(
                content="Trade cancelled: you no longer have that medal.", view=None
            )
            return
        if not db.has_medal(self.target_id, self.target_medal):
            await interaction.response.edit_message(
                content="Trade cancelled: the other player no longer has that medal.",
                view=None,
            )
            return

        db.swap_medals(
            self.initiator_id,
            self.initiator_medal,
            self.target_id,
            self.target_medal,
        )
        i_medal = MEDAL_BY_ID[self.initiator_medal]
        t_medal = MEDAL_BY_ID[self.target_medal]
        await interaction.response.edit_message(
            content=(
                f"Trade complete: <@{self.initiator_id}>'s **{i_medal['name']}** "
                f"for <@{self.target_id}>'s **{t_medal['name']}**."
            ),
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.initiator_id:
            await interaction.response.send_message(
                "Only the trade initiator can cancel.", ephemeral=True
            )
            return
        await interaction.response.edit_message(content="Trade cancelled.", view=None)


@bot.tree.command(
    name="trade",
    description="Propose a medal trade with another collector.",
)
@app_commands.describe(target="The collector you want to trade with")
async def trade(interaction: discord.Interaction, target: discord.Member):
    if target.bot:
        await interaction.response.send_message(
            "Bots can't trade medals.", ephemeral=True
        )
        return
    if target.id == interaction.user.id:
        await interaction.response.send_message(
            "You can't trade with yourself.", ephemeral=True
        )
        return

    inv = db.get_inventory(interaction.user.id)
    if not inv:
        await interaction.response.send_message(
            "You don't have any medals to trade yet.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        content=f"Pick a medal to offer to {target.display_name}:",
        view=InitiatorSelectView(interaction.user.id, inv, target),
        ephemeral=True,
    )


if __name__ == "__main__":
    bot.run(TOKEN)
