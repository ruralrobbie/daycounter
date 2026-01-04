# DayCounter 🕒

**DayCounter** is a lightweight Linux desktop app that tracks how many days have passed since important moments in your life — relationships, jobs, sobriety, projects, goals, or anything else worth counting.

It counts **upward from a start date/time**, displays everything in a dashboard, and sends desktop notifications when you hit meaningful milestones.

---

## ✨ Features

- 📅 Track **up to 100 events**
- ⏱️ Live **count‑up timer** (days, hours, minutes, seconds)
- 🖥️ Simple **dashboard view** of all events
- 🔔 Desktop notifications for:
  - Every **100 days**
  - Every **1000 days** (yes, 3000+ works!)
  - **Fun numbers** (e.g. `1234`, `3333`, `5555`)
- 🧠 Remembers what it already notified you about (no duplicates)
- 💾 Data saved locally (`~/.config/daycounter_app/data.json`)
- 🐧 Built for **Linux desktop environments**

---

## 🖼️ Example Use Cases

- “Days since I quit smoking”
- “Days since we married”
- “Days since I joined this company”
- “Days since I started this project”
- “Days since last incident” 😅

---

## 🔧 Requirements

- Linux
- Python **3.9+**
- Tkinter
- `notify-send` (libnotify)

### Install dependencies (Debian/Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-tk libnotify-bin
