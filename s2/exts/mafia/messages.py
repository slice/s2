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
    "Hello, mafia!",
    "Hello there, mafia!",
    "Greetings, mafia!",
]

MAFIA_GREET = "@everyone: {flavor} Plan out who to kill each night in this channel."

MAFIA_FAILURE = [
    "Someone prevented **{target}**'s death!",
    "**{target}** managed to survive your attack!",
    "**{target}** was healed!",
]

MAFIA_SUCCESS = [
    "**{target}** was killed!",
    "**{target}** is now dead.",
    "**{target}**, rest in peace.",
    "**{target}**, R.I.P.",
]

DOCTOR_YOU_WERE_SAVED = [
    "Your life was saved by a doctor!",
    "A doctor saved your life!",
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
    "You find that your target has a collection of voodoo dolls.",
    "You find strange liquids oozing from your suspect's dumpster.",
]

INVESTIGATOR_RESULT_CLEAN = [
    "You find nothing out of the ordinary with your target.",
    "You find nothing suspicious with your target.",
    "You find nothing strange with the suspect.",
    "You don't find anything strange with the suspect.",
    "You don't find anything suspicious with the suspect.",
    "You don't find anything out of the ordinary with the suspect.",
]

ROLE_GREETINGS = {
    "Innocent": "**You are Innocent!** Your goal is to survive and lynch the mafia.",
    "Investigator": (
        "Hello there, **Investigator!** You will be able to visit "
        "someone's house every night and determine their suspiciousness. "
        "This is vital to defeating the mafia and helping your fellow townies survive!"
    ),
    "Doctor": (
        "Hello, **Doctor!** At night, you'll be able to heal someone and "
        "prevent their death if they're attacked."
    ),
    "Medium": (
        "Hello, **Medium!** At night, you'll be able to talk to the dead! "
        "However, keep in mind that you can only do this **once per game.** "
        "Be smart!"
    ),
}

PICK_RESPONSE = {
    "Mafia": [
        "Okay, **{target}** will be killed tonight.",
        "Got it. **{target}** will be murdered tonight.",
        "Picked **{target}** to be tonight's victim.",
    ],
    "Investigator": [
        "Okay, visiting **{target}** tonight.",
        "OK, you'll visit **{target}'s house** tonight.",
        "Okay, paying a visit to **{target}**.",
    ],
    "Doctor": [
        "Okay, healing **{target}** tonight.",
        "OK, going to heal **{target}** tonight.",
    ],
}

PICK_PROMPT = {
    "Mafia": (
        "It's time to kill!\n\n"
        "\N{HOCHO} Discuss someone to kill, then **type `!kill <username>` in chat** "
        "when you have decided on someone to stab. You have 30 seconds!\n\n"
        "Alternatively, you can do nothing to stay low. "
        "Once you choose someone to kill, you can't go back to killing nobody!\n\n"
        "{targets}"
    ),
    "Investigator": (
        "Pick someone to visit and investigate tonight by "
        "**typing `!visit <username>` in chat**. You have 30 seconds!\n\n"
        "{targets}"
    ),
    "Doctor": (
        "Pick someone to heal tonight by **typing `!heal <username>` in chat**. "
        "If they aren't attacked, then nothing will happen. "
        "You have 30 seconds!\n\n{targets}"
    ),
    "Medium": (
        "If you wish to speak to the dead now, type `!seance`. "
        "You can only seance once a game, so make it count."
    ),
}

MEDIUM_SEANCE_ANNOUNCEMENT = [
    "A medium, {medium}, has opened a channel of communication!",
    "Medium {medium} has arrived!",
]
MEDIUM_SEANCE = "Beginning the seance..."
MEDIUM_ALREADY_SEANCED = "You have already used your seance."

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
    "It is now discussion time! Decide on someone to accuse.",
    "Time to discuss! Who did it?",
    "Time to discuss! Decide on a town member to accuse.",
    "Let's discuss! Will someone die today?",
]

VOTING_TIME_ANNOUNCEMENT = (
    "Town members can now vote who to put on trial. "
    "To vote, type `!vote <username>` in chat. "
    "You all have 90 seconds, and {votes} are needed to accuse someone.\n\n"
    "**Players:**\n\n{players}"
)
VOTING_TIME_STALEMATE = "A suspect couldn't be determined!"
VOTING_TIME_TOO_MANY_TRIALS = "We have run out time today."
PUT_ON_TRIAL = (
    "{player}, you have been put on trial for acts of treason. What is your defense?"
)
JUDGEMENT_PROMPT = (
    "Do you think {player} is guilty or innocent? "
    "**DM me or type in your player channel** what you think "
    "(either `!innocent` or `!guilty`). "
    "You don't have to vote if you don't want to."
)
JUDGEMENT_VOTE_PUBLIC = "**{player}** has voted."
JUDGEMENT_VOTE_PUBLIC_CHANGE = "**{player}** has changed their vote."
JUDGEMENT_VOTE = [
    "Voted **{judgement}**.",
    "Voted **{judgement}**. Were you right?",
    "Voted **{judgement}**. But was it the right choice?",
    "OK, voted **{judgement}**. But was it the right choice?",
]
JUDGEMENT_INNOCENT = "The town has determined **{player}** to be innocent."
JUDGEMENT_TIE = "The town couldn't reach a verdict on **{player}**'s innocence."

LYNCH_LAST_WORDS_PROMPT = (
    "\N{SKULL} {player.mention}, you have been convicted. Do you have any last words?"
)
REST_IN_PEACE = "\N{SKULL} Rest in peace, {player}. You will be missed. \N{SKULL}"

VOTING_TIME_REMAINING = [
    "**{seconds} seconds** remaining to vote!",
    "**{seconds} seconds** are left to vote!",
    "Just **{seconds} seconds** are left to vote!",
    "Just **{seconds} seconds** remaining to vote!",
]

ALREADY_VOTED_FOR = "{mention}: You've already voted for {target}."
VOTED_FOR = "**{voter}** has voted for **{target}** to be put on trial."
VOTES_ENTRY = "{votes} {mention}"

FOUND_DEAD = [
    "**{victim}** was unfortunately found dead in their home last night.",
    "**{victim}** was found dead in their home last night.",
    "**{victim}** was found deceased in their home last night.",
]

GAME_THROWN = (
    "@everyone: Unfortunately, {thrower} left the server. The game is unable "
    "to proceed!"
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
CURRENTLY_ALIVE_MAFIA = "**Alive Mafia:** {players}"
CURRENTLY_ALIVE_TOWNIES = "**Alive Townies:** {players}"
PLAYER_ROLE_LISTING = "**Players:**\n\n{players}"

THANK_YOU = "@everyone: Thanks for playing!"
GAME_OVER = "\N{ALARM CLOCK} **Game over!** This server will self-destruct in {seconds} seconds."
GAME_OVER_INVITE = "Game over!\n\nPlayers:\n\n{players}"

FILLING_PROGRESS = (
    "\N{SLEEPING SYMBOL} **Waiting for everyone to join...**\n\n"
    "Players who still need to join:\n\n{waiting_on}"
)

SOMETHING_BROKE = "@everyone: Looks like something broke (`{error!r}`)... tell slice!"
