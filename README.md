# 🍎 Nutrition Tracker - Multi-Agent System

**Built with Google Agent Development Kit (ADK)**

Capstone Project | Agents Intensive (Google & Kaggle)

---

## 📋 Description

A multi-agent system for nutrition tracking, built on the official Google ADK.

### Features:

- 📝 **Text input** → "ate soup and bread" → CPFC calculation
- ⚖️ **Weight tracking** → daily weigh-ins with nutrition correlation analysis
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
┌─────────────────────────────────────────────────────────┐
│                    ROOT AGENT                           │
│                 (nutrition_tracker)                     │
│                                                         │
│  Coordinates the system, processes requests            │
│  Model: Gemini 2.0 Flash                               │
└─────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│ NUTRITION       │ │ NUTRITION   │ │ DATA            │
│ ANALYST         │ │ COACH       │ │ MANAGER         │
│                 │ │             │ │                 │
│ Food analysis   │ │Recommendations│ │ CRUD operations│
│ CPFC calculation│ │ Motivation  │ │ SQLite / Sheets │
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
| `data_manager` | Manages data (SQLite/Google Sheets) |

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

#### Google Sheets (optional):
1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Sheets API and Google Drive API
3. Create a Service Account and download `credentials.json`
4. Create a Google Spreadsheet
5. Share the spreadsheet with the service account email
6. Add SPREADSHEET_ID to `.env`

> 💡 **Note**: SQLite (`nutrition.db`) is used by default. To switch to Google Sheets, change the imports in `agent.py`.

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
| `/help` | Help |

### Example messages:

**Recording meals:**
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

### SQLite (default):

Database `nutrition_tracker/nutrition.db`:

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
nutrition_tracker/
├── __init__.py           # Module initialization
├── agent.py              # ADK agents (root + sub-agents) + observability
├── telegram_bot.py       # Telegram integration
├── env.template          # Environment variables template
├── nutrition.db          # SQLite database
│
└── tools/                # Tools
    ├── __init__.py
    ├── sqlite_tools.py   # SQLite operations (default)
    ├── sheets_tools.py   # Google Sheets operations
    ├── nutrition_tools.py # Nutrition analysis
    ├── memory_tools.py   # Long-term memory (Memory Bank)
    └── search_tools.py   # Google Search via separate agent

requirements.txt          # Dependencies
README.md                 # Documentation
```

---

## 🔧 Technologies

- **Google ADK** — Agent Development Kit for building agents
- **Gemini 2.0 Flash** — LLM for processing requests
- **SQLite** — Local data storage (default)
- **Google Sheets API** — Cloud storage (optional)
- **python-telegram-bot** — Telegram integration
- **gspread** — Python client for Sheets
- **OpenTelemetry** — Distributed tracing and observability

---

## 🛡️ Features

- **Duplicate protection**: If similar food was recorded in the last 5 minutes — the bot will warn
- **Markdown fallback**: If formatting breaks — message will be sent as plain text
- **Persistence**: Data is stored in SQLite, not lost on restart
- **Editing**: Any entry can be modified by ID
- **Weight-nutrition analysis**: Correlates weight changes with calorie intake
- **Long-term memory**: Remembers allergies, preferences, and habits for personalization
- **Observability**: OpenTelemetry tracing for debugging and monitoring

---

## 📈 Metrics

- **Architecture**: Multi-agent with root + 3 sub-agents + isolated search agent
- **Tools**: 19 custom tools (search uses isolated agent with google_search)
- **Integrations**: Telegram, SQLite, Google Sheets, Google Search
- **Key concepts**: Multi-agent, Custom Tools, Sessions, Long-term Memory, Observability, Built-in Tools
- **Calculation accuracy**: ~90% (depends on description)

---

## 🔮 Possible Improvements

- [ ] Photo food recognition (Gemini Vision)
- [ ] Voice messages (Gemini Audio)
- [ ] Progress charts
- [ ] Recipe recommendations
- [ ] A2A protocol for agent communication
- [ ] CSV data export
- [ ] Weight goal tracking and predictions

---

## 📄 Resources

- [ADK Documentation](https://google.github.io/adk-docs/)
- [ADK Python](https://github.com/google/adk-python)
- [ADK Sample Agents](https://github.com/google/adk-samples)
- [Google AI Studio](https://aistudio.google.com/)

---

## 👨‍💻 Author

Capstone Project for [Agents Intensive Course](https://www.kaggle.com/learn) (Google & Kaggle)
