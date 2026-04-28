# fiesta-medals-bot

A Discord bot inspired by San Antonio's Fiesta medal culture. Players draw a
random medal once a day (up to five total), build a collection, and trade
duplicates with other server members to complete the set.

## Commands

| Command       | Description                                                          |
|---------------|----------------------------------------------------------------------|
| `/draw`       | Draw a random medal. Once per day, lifetime cap of five draws.       |
| `/collection` | Show your medals as a horizontal collage.                            |
| `/trade`      | Pick a medal to offer, propose a trade with another member, confirm. |
| `/wear`       | Show your medals pinned on the shirt or bag template (if provided).  |

The trade flow is interactive: the initiator picks an offered medal from a
private select menu; the target picks one of their medals to offer in return;
the initiator confirms or cancels.

## Setup

### 1. Create the Discord application

1. Go to <https://discord.com/developers/applications> and create a new app.
2. Add a Bot user; copy the bot token.
3. Under **OAuth2 > URL Generator**, select scopes `bot` and
   `applications.commands`. Bot permissions: **Send Messages**,
   **Embed Links**, **Attach Files**, **Read Message History**.
4. Use the generated URL to invite the bot to your server.

### 2. Install and configure

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env, set DISCORD_TOKEN
# optional: set DISCORD_GUILD_ID for instant slash-command sync during dev
```

### 3. Drop in the medal images

Place five PNGs in `assets/medals/`, named to match `medals.json`:

```
assets/medals/medal_1.png
assets/medals/medal_2.png
assets/medals/medal_3.png
assets/medals/medal_4.png
assets/medals/medal_5.png
```

All five should be the same size. You can edit names and descriptions in
`medals.json`.

For an end-to-end smoke test before the real assets land, generate
placeholders:

```bash
python scripts/make_placeholders.py
```

### 4. (Optional) Shirt or bag template

If the creative team delivers a shirt or bag image, save it as
`assets/template.png`. The `/wear` command will overlay medals across the
middle of the canvas. Adjust positioning in `images.py:wear()` once you have
the real template — `target_w` controls medal size, `y` controls vertical
placement.

If `assets/template.png` is absent, `/wear` returns a "stay tuned" reply.

### 5. Run

```bash
python bot.py
```

## Data

Per-user state lives in `data/fiesta.db` (SQLite). Two tables:

- `users` — `user_id`, `draws_used`, `last_draw_date`
- `inventory` — one row per owned medal (duplicates allowed)

Delete the file to reset all collections during testing.

## Project layout

```
bot.py                 slash commands and trade UI
db.py                  SQLite layer
images.py              collage and wear renderers (Pillow)
medals.json            medal metadata
assets/medals/         medal PNGs (creative team)
assets/template.png    optional shirt or bag template
scripts/make_placeholders.py   generates test medal art
```
