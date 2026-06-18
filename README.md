# WhatsApp Chat Analyser

> An interactive **Streamlit** dashboard that turns an exported WhatsApp chat into visual analytics: activity timelines, busiest users, word clouds, emoji breakdowns and more.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?logo=streamlit&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-data-150458?logo=pandas&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Upload a `.txt` export of any WhatsApp conversation (group or 1:1) and the app parses it into a tidy DataFrame, then renders a full analytics report. You can scope every view to the whole chat or to a single participant.

## Features

- 📊 **Top-line stats**: total messages, words, media and links shared
- 📅 **Timelines**: monthly and daily message volume
- 🗓️ **Activity maps**: busiest day, busiest month, and a day×hour heatmap
- 👥 **Most active users** (group chats) with contribution percentages
- ☁️ **Word cloud** + most-common-words (with Hinglish stop-word filtering)
- 😀 **Emoji analysis**: frequency table and pie chart
- 🔍 **Per-user filtering**: analyse "Overall" or any single participant

---

## How It Works

```mermaid
flowchart LR
    A["Exported chat .txt"] --> B["preprocessor.preprocess()<br>regex split into messages + timestamps"]
    B --> C["pandas DataFrame<br>(user, message, date parts, period)"]
    C --> D["helper.py analytics<br>stats / timelines / heatmap / emoji / wordcloud"]
    D --> E["app.py<br>Streamlit charts (matplotlib + seaborn)"]
```

---

## Tech Stack

| Purpose | Library |
|---------|---------|
| UI | Streamlit |
| Data wrangling | pandas, `re` |
| Charts | matplotlib, seaborn |
| Text/NLP | wordcloud, urlextract, emoji, regex |

---

## Getting Started

```bash
pip install -r requirements.txt
streamlit run app.py
```
Then in the sidebar, upload an exported chat (WhatsApp → a chat → ⋮ → *More* → *Export chat* → *Without media*) and click **Show Analysis**.

---

## Project Structure

```
app.py             Streamlit UI and chart layout
preprocessor.py    Regex parser: raw export -> structured DataFrame
helper.py          All analytics (stats, timelines, activity, wordcloud, emoji)
stop_hinglish.txt  Stop-word list for Hinglish text
```

---

## Notes

- The current date parser expects the `M/D/YY, h:mm AM/PM -` export format; other locales/formats may need the regex in `preprocessor.py` adjusted.

---

## Author

**Muhammad Wajih Hyder** — BS Computer Science, FAST‑NUCES (2026)
[GitHub @wajihhyder](https://github.com/wajihhyder) · wajihhyder22@gmail.com
