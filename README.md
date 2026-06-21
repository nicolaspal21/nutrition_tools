# 🍎 Nutrition Tracker - Multi-Agent System

**Built with Google Agent Development Kit (ADK)**

Capstone Project | Agents Intensive (Google & Kaggle)

---

## 📋 Description

A multi-agent system for nutrition tracking, built on the official Google ADK.

### Features:

- 📸 **Photo recognition** → send a photo of your meal → Gemini Vision analyzes it (supports albums!)
- 🎤 **Voice messages** → describe what you ate by voice → Gemini transcribes and calculates
- 📝 **Text input** → "ate soup and bread" → CPFC calculation
- ⚖️ **Weight tracking** → daily weigh-ins with nutrition correlation analysis
- 🏃 **Workout tracking** → log workouts and burned calories
- 📦 **CSV Export** → download your data (meals, weight, workouts) as CSV files
- 📊 **Statistics** → daily/weekly summary with actual vs. target progress
- 🎯 **Goals** → personalized recommendations
- ✏️ **Editing** → modify and delete entries by ID
- ❓ **Questions** → "what did I eat yesterday?", "how much protein this week?"
- 🛡️ **Duplicate protection** → prevents recording the same meal twice
- 💬 **Telegram bot** → convenient interface
- 🧠 **Long-term Memory** → remembers user preferences, allergies, habits
- 🔍 **Google Search** → looks up calorie data for unknown foods
- 📡 **Observability** → logging and OpenTelemetry tracing

---

## 🏗️ Architecture

```
          ┌─────────┐  ┌─────────┐  ┌─────────┐
          │  📸     │  │  🎤     │  │  ✍️     │
          │ Photo   │  │ Voice   │  │ Text    │
          └────┬────┘  └────┬────┘  └────┬────┘
               └───────────┬───────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    ROOT AGENT                           │
│                 (nutrition_tracker)                     │
│                                                         │
│  Coordinates the system, processes multimodal input    │
│  Model: Gemini 3.5 Flash (Vision + Audio + Text)       │
└─────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│ NUTRITION       │ │ NUTRITION   │ │ DATA            │
│ ANALYST         │ │ COACH       │ │ MANAGER         │
│                 │ │             │ │                 │
│ Food analysis   │ │Recommendations│ │ CRUD operations│
│ CPFC calculation│ │ Motivation  │ │ Turso / SQLite  │
└─────────────────┘ └─────────────┘ └─────────────────┘
         │                 │                 │
         └─────────────────┴─────────────────┘
                           │
                    ┌──────┴──────┐
                    │   TOOLS     │
                    │             │
                    │ save_meal   │
                    │ edit_meal   │
                    │ delete_meal │
                    │ save_weight │
                    │ get_meals   │
                    │ ...         │
                    └─────────────┘
```

### Agents (ADK Agent):

| Agent | Role |
|-------|------|
| `root_agent` | Main coordinator, handles all requests |
| `nutrition_analyst` | Analyzes food, calculates CPFC |
| `nutrition_coach` | Provides personalized recommendations |
| `data_manager` | Manages data (Turso/SQLite) |

### Tools:

| Tool | Type | Description |
|------|------|-------------|
| `save_meal` | Custom | Saves a meal (with duplicate protection) |
| `edit_meal` | Custom | Edits entry by ID or the last one |
| `delete_meal` | Custom | Deletes entry by ID or the last one |
| `get_today_meals` | Custom | Gets today's meals |
| `get_meals_by_date` | Custom | Gets meals for any date |
| `get_week_meals` | Custom | Weekly statistics |
| `get_user_goals` | Custom | Gets user's goals |
| `update_user_goals` | Custom | Updates goals |
| `save_weight` | Custom | Records daily weight |
| `get_weight_history` | Custom | Weight history with stats |
| `get_weight_nutrition_analysis` | Custom | Weight-nutrition correlation analysis |
| `delete_weight` | Custom | Deletes weight entry |
| `store_memory` | Custom | Saves user preferences to long-term memory |
| `recall_memories` | Custom | Retrieves user preferences and facts |
| `forget_memory` | Custom | Removes specific memories |
| `analyze_food_description` | Custom | Food description analysis |
| `calculate_daily_totals` | Custom | Daily totals calculation |
| `get_nutrition_advice` | Custom | Generates recommendations |
| `search_nutrition_info` | Custom | Searches for calorie data online (via separate search_agent) |

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/nutrition-tracker.git
cd nutrition-tracker
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# Linux/Mac
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
# Copy the template
copy nutrition_tracker\env.template nutrition_tracker\.env

# Edit .env and add your keys
```

### 5. Get API keys

#### Google API Key (for Gemini):
1. Go to https://aistudio.google.com/apikey
2. Create a new key
3. Add to `.env` as `GOOGLE_API_KEY`

#### Telegram Bot Token:
1. Open @BotFather in Telegram
2. Send `/newbot`
3. Get the token and add to `.env`

#### Database (Turso):
1. Create an account at [Turso](https://turso.tech)
2. Create a database: `turso db create nutrition-tracker`
3. Get the URL: `turso db show nutrition-tracker --url`
4. Create a token: `turso db tokens create nutrition-tracker`
5. Add `TURSO_URL` and `TURSO_TOKEN` to `.env`

> 💡 **Note**: The bot uses Turso (cloud SQLite) via `libsql-client`. `TURSO_URL` and `TURSO_TOKEN` are required — without them the app exits with a configuration error. Data is exported to CSV via the `/export` command.

---

## ▶️ Running

### Option 1: ADK Dev UI (recommended for development)

```bash
# Navigate to the parent folder
cd ..

# Launch ADK web interface
adk web
```

Open http://localhost:8000 and select `nutrition_tracker` from the dropdown.

### Option 2: ADK CLI

```bash
adk run nutrition_tracker
```

### Option 3: Telegram Bot

```bash
python -m nutrition_tracker.telegram_bot
```

---

## 💬 Usage

### Telegram Bot:

| Command | Description |
|---------|-------------|
| `/start` | Get started |
| `/today` | Today's summary |
| `/week` | Weekly statistics |
| `/goals` | Show goals |
| `/undo` | Undo last entry |
| `/sync` | Sync data to Google Sheets (admin only) |
| `/help` | Help |

### Example messages:

**Photo recognition:**
```
📸 [send photo of your meal]
→ 📸 Analyzing photo...
→ Recognized: Chicken with rice
   Chicken breast: 250 kcal | P: 40g | F: 8g | C: 0g
   Rice (150g): 200 kcal | P: 4g | F: 1g | C: 45g
   Total: 450 kcal | P: 44g | F: 9g | C: 45g
   
   Save to diary? 📝
```

**Voice messages:**
```
🎤 [voice: "had chicken with mushrooms and rice"]
→ 🎤 Got it: chicken with mushrooms and rice
   Total: 550 kcal | P: 34g | F: 21g | C: 55g
   
   Save to diary? 📝
```

**Recording meals (text):**
```
Ate 2 eggs and avocado toast
→ ✅ Recorded! #1 🍳 2 eggs and toast — 380 kcal
```

**Statistics with progress:**
```
what did I eat today?
→ 📋 Today:
   #1 🍳 Scrambled eggs — 390 kcal
   #2 🥗 Salad — 150 kcal
   
   📊 Actual / Target:
   🔥 Calories: 540 / 2000 (27%)
   🥩 Protein: 35 / 150g (23%)
   🧈 Fat: 38 / 70g (54%)
   🍞 Carbs: 20 / 200g (10%)
```

**Weight tracking:**
```
weight 74.5
→ ⚖️ Weight recorded: 74.5 kg (-0.3 kg since Nov 25)

weight analysis
→ 📈 2-week trend:
   Start: 76.0 kg → Current: 74.5 kg
   Change: -1.5 kg
   
🔥 Avg calories: 1850 kcal/day (deficit ~150)
💡 Insight: Weight is decreasing in line with calorie deficit!
```

**Editing:**
```
fix #1: 300 kcal
→ ✅ Entry #1 updated
```

**Deleting:**
```
delete #2
→ ✅ Deleted entry #2: Salad
```

**Goals:**
```
I want to lose weight
→ 🎯 Goal set: weight loss
   Calories: 1800, Protein: 135g
```

**Long-term Memory:**
```
I'm vegetarian
→ ✅ Remembered: vegetarian

I'm allergic to nuts
→ ✅ Remembered: nut allergy

what do you know about me?
→ 🧠 About you:
   🍽️ Preferences: vegetarian
   ⚠️ Allergies: nut allergy
```

---

## 📊 Data Structure

### Turso / SQLite:

Tables (in Turso cloud DB; schema is identical for a local SQLite file):

**Table `meals`:**
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Unique entry ID |
| user_id | TEXT | Telegram user ID |
| date | TEXT | Date (YYYY-MM-DD) |
| time | TEXT | Time (HH:MM) |
| meal_type | TEXT | breakfast/lunch/dinner/snack |
| description | TEXT | Food description |
| calories | REAL | Calories |
| protein | REAL | Protein (g) |
| fat | REAL | Fat (g) |
| carbs | REAL | Carbohydrates (g) |

**Table `users`:**
| Field | Type | Description |
|-------|------|-------------|
| user_id | TEXT | Telegram user ID |
| goal_type | TEXT | weight_loss/muscle_gain/maintenance |
| daily_calories | INTEGER | Calorie goal |
| daily_protein | INTEGER | Protein goal |
| daily_fat | INTEGER | Fat goal |
| daily_carbs | INTEGER | Carbs goal |

**Table `weight_log`:**
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Unique entry ID |
| user_id | TEXT | Telegram user ID |
| date | TEXT | Date (YYYY-MM-DD) |
| time | TEXT | Time (HH:MM) |
| weight | REAL | Weight in kg |
| note | TEXT | Optional note |

**Table `memory_bank` (Long-term Memory):**
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Unique entry ID |
| user_id | TEXT | Telegram user ID |
| memory_type | TEXT | preference/allergy/habit/fact |
| content | TEXT | Memory content |
| metadata | TEXT | JSON with additional data |
| created_at | TIMESTAMP | When memory was created |

---

## 📁 Project Structure

```
.
├── Dockerfile            # Docker image for Cloud Run
├── deploy.sh             # Deployment script
├── requirements.txt      # Dependencies
├── README.md             # Documentation
│
└── nutrition_tracker/
    ├── __init__.py           # Module initialization
    ├── agent.py              # ADK agents (root + sub-agents) + observability
    ├── telegram_bot.py       # Telegram integration (polling mode)
    ├── webhook_server.py     # Webhook server for Cloud Run
    ├── env.template          # Environment variables template
    ├── .env                  # Environment variables (create from template)
    ├── nutrition.db          # SQLite database (auto-created, local only)
    │
    └── tools/                # Tools
        ├── __init__.py
        ├── database.py       # Database abstraction (SQLite/Turso)
        ├── sqlite_tools.py   # SQLite/Turso CRUD operations + CSV export
        ├── nutrition_tools.py # Nutrition analysis
        ├── memory_tools.py   # Long-term memory (Memory Bank)
        └── search_tools.py   # Google Search via separate agent
```

---

## 🔧 Technologies

- **Google ADK** — Agent Development Kit for building agents
- **Gemini 3.5 Flash** — LLM for processing requests
- **SQLite / Turso** — Local SQLite or cloud Turso database
- **CSV Export** — download meals/weight/workouts as CSV files
- **python-telegram-bot** — Telegram integration
- **aiohttp** — Async HTTP server for webhooks
- **OpenTelemetry** — Distributed tracing and observability

---

## ☁️ Cloud Deployment

### Google Cloud Run

The bot can be deployed to Cloud Run with Turso as the cloud database.

#### Prerequisites:
1. Google Cloud account with Cloud Run enabled
2. [Turso](https://turso.tech) account for cloud SQLite database
3. Docker installed locally

#### Environment Variables for Cloud:
```env
TURSO_URL=libsql://your-db.turso.io
TURSO_TOKEN=your-token
WEBHOOK_URL=https://your-cloud-run-url.run.app
```

#### Deploy:
```bash
./deploy.sh
```

The Dockerfile uses `webhook_server.py` which handles Telegram webhooks instead of polling.

---

## 🛡️ Features

- **Multimodal input**: Photos (Gemini Vision), voice (Gemini Audio), and text
- **Album support**: Send multiple photos of the same dish — they'll be analyzed together
- **Smart duplicate protection**: Blocks only exact duplicates within 2 minutes (same description + meal type)
- **Markdown fallback**: If formatting breaks — message will be sent as plain text
- **Persistence**: Data is stored in Turso (cloud SQLite), not lost on restart
- **Editing**: Any entry can be modified by ID
- **Weight tracking**: One entry per day (re-entering overwrites), history with dates
- **Weight-nutrition analysis**: Correlates weight changes with calorie intake
- **Long-term memory**: Remembers allergies, preferences, and habits for personalization
- **Observability**: OpenTelemetry tracing for debugging and monitoring

---

## 📄 Resources

- [ADK Documentation](https://google.github.io/adk-docs/)
- [ADK Python](https://github.com/google/adk-python)
- [ADK Sample Agents](https://github.com/google/adk-samples)
- [Google AI Studio](https://aistudio.google.com/)

---

## 👨‍💻 Author

Capstone Project for [Agents Intensive Course](https://www.kaggle.com/learn) (Google & Kaggle)
