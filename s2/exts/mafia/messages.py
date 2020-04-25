"""Mafia text."""

LOBBY_CREATED = (
    "{creator} started a game of Mafia. Join by reacting with {join_emoji}!"
    "\n\n**Make sure you're not in 100 servers!** Mafia games take place in "
    "a separate server."
)
LOBBY_CANCELLED = "{mention}: Cancelled game."
LOBBY_CANT_FORCE_START = (
    "{mention}: Can't force start\N{EM DASH}at least 3 players are needed."
)
LOBBY_STARTING = "Game is starting! Good luck."
LOBBY_INVITE = (
    "{mentions}: The game is starting!\n\n"
    "**Join here:** {invite}\n"
    "(Anyone can join! You'll be a spectator if you didn't join the lobby earlier.)"
)

MAFIA_GREET_FLAVOR = [
    "Greetings, mafia!",
    "Say hello, mafia!",
    "Say hi, mafia!",
]

MAFIA_GREET = (
    "@everyone: {flavor} In this channel, you can secretly talk to your evil partner."
)

MAFIA_PICK = [
    "Okay, **{victim}** will be killed tonight.",
    "Got it. **{victim}** will be murdered tonight.",
    "Picked **{victim}** to be tonight's victim.",
]

MAFIA_FAILURE = [
    "Someone prevented **{victim}**'s death!",
    "**{victim}** managed to survive your attack!",
    "**{victim}** was healed!",
]

MAFIA_SUCCESS = [
    "**{victim}** was killed!",
    "**{victim}** is now dead.",
    "**{victim}**, rest in peace.",
    "**{victim}**, R.I.P.",
]

INVESTIGATOR_PICK = [
    "Okay, visiting **{player}** tonight.",
    "OK, you'll visit **{player}'s house** tonight.",
    "Okay, paying a visit to **{player}**.",
]

DOCTOR_PICK = [
    "Okay, healing **{player}** tonight.",
    "OK, going to heal **{player}** tonight.",
]

DOCTOR_RESULT = {
    "healed": [
        "You have saved {target}'s life!",
        "You just saved {target}'s life!",
        "You saved {target}'s life!",
        "You prevented {target}'s death!",
        "{target} was saved!",
    ],
    "noop": [
        "{target} wasn't attacked, so nothing happened.",
        "Nothing happened! {target} wasn't attacked.",
        "Nobody attacked {target}, so nothing happened.",
    ],
}

INVESTIGATOR_RESULT_SUSPICIOUS = [
    "You find that your target has a knife collection.",
    "You find that the suspect is making a lot of noise.",
    "You find that the suspect's garage is leaking red fluid.",
    "You find that your target has a shed full of weapons.",
]

INVESTIGATOR_RESULT_CLEAN = [
    "You find nothing out of the ordinary with your target.",
    "You find nothing suspicious with your target.",
    "You find nothing strange with the suspect.",
]

ROLE_GREETINGS = {
    "Innocent": "**You are Innocent!** Your goal is to survive and hang the mafia.",
    "Investigator": (
        "Hello there, **Investigator!** You will be able to visit "
        "someone's house every night and determine their suspiciousness. "
        "This is vital to defeating the mafia and helping your fellow townies survive!"
    ),
    "Doctor": (
        "Hello, **Doctor!** At night, you'll be able to heal someone and "
        "prevent their death if they're attacked."
    ),
}

ACTION_PROMPTS = {
    "Mafia": (
        "It's time to kill!\n\n"
        "\N{HOCHO} Discuss someone to kill, then **type `!kill <username>` in chat** "
        "when you have decided on someone to stab. You have 30 seconds!\n\n"
        "Alternatively, you can do nothing to stay low. "
        "Once you choose someone to kill, you can't go back to killing nobody!\n\n"
        "{victims}"
    ),
    "Investigator": (
        "Pick someone to visit and investigate tonight by "
        "**typing `!visit <username>` in chat**. You have 30 seconds!\n\n"
        "{players}"
    ),
    "Doctor": (
        "Pick someone to heal tonight by **typing `!heal <username>` in chat**. "
        "If they aren't attacked, then nothing will happen. "
        "You have 30 seconds!\n\n{players}"
    ),
}

GAME_START = [
    "{mentions}: The main game will take place here. Have fun!",
    "{mentions}: Hello there! Here's where the main game will take place. Have fun!",
    "{mentions}: Hello everybody! The game will take place here. Have fun!",
]

TUTORIAL = (
    "**Welcome to the game, everybody!**\n\n"
    "There are {mafia_n} mafia hiding within a town of innocents. "
    "**If you are an innocent,** your goal is to lynch the mafia. "
    "**If you are a mafia,** your goal is to work with your partner to wipe "
    "out the innocents before they find out about you!"
)

DISCUSSION_TIME_ANNOUNCEMENT = [
    "It is now discussion time! Decide on someone to hang.",
    "Time to discuss! Decide on a town member to hang.",
    "Let's discuss! Will someone die today?",
]

VOTING_TIME_ANNOUNCEMENT = (
    "Alive town members can now vote who to hang. "
    "To vote, type `!vote <username>` in chat. "
    "You all have 90 seconds, and {votes} votes are needed to hang someone.\n\n"
    "**Alive Players:**\n\n{players}"
)

VOTING_TIME_REMAINING = [
    "**{seconds} seconds** remaining to vote!",
    "**{seconds} seconds** are left to vote!",
    "Just **{seconds} seconds** are left to vote!",
    "Just **{seconds} seconds** remaining to vote!",
]

ALREADY_VOTED_FOR = "{mention} You've already voted for {target}."
VOTED_FOR = "**{voter}** has voted for **{target}** to be hanged."
VOTES_ENTRY = "{mention}: {votes}"

FOUND_DEAD = [
    "**{victim}** was unfortunately found dead in their home last night.",
    "**{victim}** was found dead in their home last night.",
    "**{victim}** was found deceased in their home last night.",
]

GAME_THROWN = (
    "{mentions}: Unfortunately, {thrower} left the server. The game is unable "
    "to proceed."
)

THEY_ROLE = "They were **{role}**."
WAS_ROLE = "**{died}** was **{role}**."

NIGHT_EMOJI = "\N{NIGHT WITH STARS}"
DAY_EMOJI = "\N{BLACK SUN WITH RAYS}"
DAY = "Day"
NIGHT = "Night"
DAY_ANNOUNCEMENT = "{emoji} **{time_of_day} {day}** {emoji}"

NIGHT_ANNOUNCEMENT = [
    "Night time! Sleep tight, and don't let the bed bugs bite!",
    "Night time! Sleep tight, everybody!",
    "It's night! Let's all get some rest.",
]

MAFIA_WIN = "\N{HOCHO} **Mafia win!**"
TOWNIES_WIN = "\N{DIZZY SYMBOL} **Townies win!**"
CURRENTLY_ALIVE_MAFIA = "**Alive Mafia:**\n\n{users}"
CURRENTLY_ALIVE_TOWNIES = "**Alive Townies:**\n\n{users}"
THANK_YOU = "@everyone: Thanks for playing!"

GOODBYE = (
    "\N{ALARM CLOCK} Game over! This server will self-destruct in {seconds} seconds."
)

FILLING_PROGRESS = (
    "\N{SLEEPING SYMBOL} **Waiting for everyone to join...**\n\n"
    "Players who still need to join:\n\n{waiting_on}"
)

SOMETHING_BROKE = "@everyone: Looks like something broke (`{error!r}`)... tell slice!"
