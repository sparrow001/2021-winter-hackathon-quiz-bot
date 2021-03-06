import datetime
import discord
from discord.ext import commands
from .classes import Player
import json


class Answer(discord.ui.Button):
    def __init__(self, _type: int = 0, answer: str = "", **kwargs):
        bkey = {-1: 4, 0: 1, 1: 3}
        kwargs.update(style=discord.ButtonStyle(bkey[_type]), disabled=_type != 0)
        self.answer = answer
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        game = self.view.cog.games.get(interaction.guild_id, None)
        if not game:
            return await interaction.followup.send(
                "why is this button active without an associated game 🤔", ephemeral=True
            )
        user = game.participants.get(interaction.user.id, None)
        if not user:
            user = Player(interaction.user)
            game.participants[interaction.user.id] = user
        self.view.answered[interaction.user.id] = [
            self.label,
            datetime.datetime.now().timestamp(),
        ]
        await interaction.followup.send(f"Answered: {self.answer}", ephemeral=True)


#        await self.view.all_done()


class Leave(discord.ui.Button):
    def __init__(self, cog: commands.Cog, **kwargs):
        kwargs.update(style=discord.ButtonStyle(4), label="Leave")
        super().__init__(**kwargs)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gdat = self.cog.games.get(interaction.guild_id, None)
        if not gdat:
            return
        user = gdat["participants"].get(interaction.user.id, None)
        if not user or not user.active:
            return await interaction.followup.send(
                "You are not in this game.", ephemeral=True
            )
        if hasattr(self.view, "participating"):
            self.view.participating.remove(user.user.id)
        if gdat["active"]:
            user.active = False
            await self.view.all_done()
            await interaction.followup.send(f"{user.user} has left the game.")
        else:
            self.cog.games[interaction.guild.id]["participants"].pop(user.user.id)
            await interaction.followup.send("Joined the game.", ephemeral=True)
        people = (
            lambda u: u.active,
            self.cog.games[interaction.guild.id]["participants"].values(),
        )
        if not any(people):
            await interaction.followup.send("No one is playing... Ending the game.")
            await self.view.all_done()


class JoinStartLeave(discord.ui.View):
    def __init__(self, cog: commands.Cog, totalq: int, **kwargs):
        self.totalq = totalq
        self.cog = cog
        kwargs.setdefault("timeout", 300)
        super().__init__(**kwargs)
        self.add_item(Leave(self.cog))

    @discord.ui.button(label="Join", style=discord.ButtonStyle(3))
    async def join_game(self, btn: discord.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.cog.games[interaction.guild.id]["participants"].get(
            interaction.user.id, None
        ):
            return await interaction.followup.send(
                "You are already in this game.", ephemeral=True
            )
        self.cog.games[interaction.guild_id]["participants"][
            interaction.user.id
        ] = Player(interaction.user)
        await interaction.followup.send("Joined the game.", ephemeral=True)

    @discord.ui.button(label="Start", style=discord.ButtonStyle(1))
    async def start_game(self, btn: discord.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.cog.games[interaction.guild_id]["start_by"] != interaction.user.id:
            return await interaction.followup.send(
                "Only the person who ran the command to start this quiz can begin it early.",
                ephemeral=True,
            )
        if len(self.cog.games[interaction.guild_id]["participants"]) < 1:
            return await interaction.followup.send(
                "There are no players in this game!", ephemeral=True
            )
        self.cog.games[interaction.guild_id]["active"] = True
        await interaction.followup.send("Starting quiz!", ephemeral=True)
        self.stop()
        self.cog.bot.dispatch("quiz_start", interaction.guild_id, interaction.user.id)


class Answers(discord.ui.View):
    def __init__(
        self, cog: commands.Cog, guild: discord.Guild, answers: int, qnum: int, **kwargs
    ):
        self.qnum: int = qnum
        self.answered = {}
        self.participating = [
            u.user.id for u in cog.games[guild.id].participants.values()
        ]
        self.cog = cog
        self.guild = guild
        kwargs.setdefault("timeout", 15)
        super().__init__(**kwargs)
        for i, l in enumerate("ABCD"[: len(answers)]):
            self.add_item(Answer(0, answers[i], label=l))

    #        self.add_item(Leave(cog))

    #    async def all_done(self):
    #        if set(self.answered) == set(self.participating):
    #            await self.end()

    async def on_timeout(self):
        await self.end()

    async def end(self):
        self.stop()
        self.cog.bot.dispatch("next_question", self.guild.id, self.qnum, self.answered)
        return self.answered


class ShowAnswers(discord.ui.View):
    def __init__(self, answers: list, ind_correct: int, **kwargs):
        super().__init__(**kwargs)
        for i, l in enumerate("ABCD"[: len(answers)]):
            self.add_item(Answer(1 if i == ind_correct else -1, label=l))


class Version(discord.ui.View):
    def __init__(self, version: str, **kwargs):
        super().__init__(**kwargs)
        self.version = version

    @discord.ui.button(label="Yes", style=discord.ButtonStyle(3))
    async def yes(self, btn: discord.Button, interaction: discord.Interaction):
        with open("/home/clari/Repositories/Winter-Hackathon/data.json", "r+") as f:
            d = json.loads(f.read())
            d["version"] = self.version
            f.seek(0)
            f.write(json.dumps(d, indent=4))
            f.truncate()
        self.stop()
        return await interaction.followup.send_message(f"Version set to {self.version}")

    @discord.ui.button(label="No", style=discord.ButtonStyle(4))
    async def no(self, btn: discord.Button, interaction: discord.Interaction):
        self.stop()
        return await interaction.followup.send_message("Version not set.")


class AcceptSuggestion(discord.ui.View):
    def __init__(
        self,
        suggestor_id: int,
        question: str,
        correct: str,
        wrong_one: str,
        wrong_two="null",
        wrong_three="null",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.question = question
        self.correct = correct
        self.wrong_one = wrong_one
        self.wrong_two = wrong_two
        self.wrong_three = wrong_three
        self.suggestor_id = suggestor_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle(3))
    async def yes(self, btn: discord.Button, interaction: discord.Interaction):
        if interaction.user.id != 642416218967375882:
            return await interaction.followup.send_message("no ty :)", ephemeral=True)
        if isinstance(self.wrong_two, int):
            self.wrong_two = str(self.wrong_two)
        if isinstance(self.wrong_three, int):
            self.wrong_three = str(self.wrong_three)
        async with self.bot.db.cursor() as c:
            await c.execute(
                "INSERT INTO questions(question, correct, wrong_one, wrong_two, wrong_three) VALUES (?, ?, ?, ?, ?)",
                (
                    self.question,
                    self.correct,
                    self.wrong_one,
                    self.wrong_two,
                    self.wrong_three,
                ),
            )
        await self.bot.db.commit()
        await interaction.followup.send_message(
            embed=self.bot.Embed(
                title="Question Added",
                description=f"Added `{self.question}` to the list of questions.",
            )
            .add_field(name="Correct Answer", value=f"• {self.correct}")
            .add_field(
                name="Wrong Answers",
                value=f"• {self.wrong_one}\n• {self.wrong_two}\n• {self.wrong_three}",
            ),
            ephemeral=True,
        )
        em = self.bot.Embed(
            title="Suggestion Accepted",
            description=f"A developer has accepted your suggestion for {self.bot.mention}.",
        )
        em.add_field(name="Question", value=f"{self.question}")
        em.add_field(name="Correct Answer", value=f"{self.correct}")
        em.add_field(
            name="Wrong Answers",
            value=f"{self.wrong_one}\n{self.wrong_two}\n{self.wrong_three}",
        )
        try:
            await self.bot.get_user(self.suggestor_id).send(embed=em)
        except:
            pass
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle(4))
    async def no(self, btn: discord.Button, interaction: discord.Interaction):
        await interaction.followup.send_message("Suggestion not accepted.")
        embed = self.bot.Embed(
            title="Suggestion not accepted",
            description=f"Your Suggestion for {self.bot.user.mention} was not accepted.",
        )
        embed.add_field(name="Suggested Question", value=f"{self.question}")
        embed.add_field(name="Correct Answer", value=f"{self.correct}")
        embed.add_field(
            name="Wrong Answers",
            value=f"{self.wrong_one}\n{self.wrong_two}\n{self.wrong_three}",
        )
        try:
            await self.bot.get_user(self.suggestor_id).send(embed=embed)
        except:
            pass
        self.stop()
