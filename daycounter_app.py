#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "DayCounter"
MAX_ENTRIES = 100

# Default “fun numbers”
DEFAULT_FUN_NUMBERS = [
    111, 222, 333, 444, 555, 666, 777, 888, 999,
    1010, 1111, 1234, 1313, 1414, 1515,
    2020, 2222, 2345, 2468,
    3000, 3333, 3456, 4321, 4444,
    5000, 5555, 6000, 6666, 7000, 7777,
    8000, 8888, 9000, 9999,
]

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "daycounter_app")
DATA_FILE = os.path.join(CONFIG_DIR, "data.json")


def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def notify(title: str, body: str):
    """
    Desktop notification using notify-send (libnotify-bin).
    Falls back to stderr if unavailable.
    """
    try:
        subprocess.run(["notify-send", title, body], check=False)
    except Exception:
        print(f"[NOTIFY] {title}: {body}", file=sys.stderr)


def format_date_user(dt: datetime) -> str:
    """
    Display in user's requested format:
    - If year differs from current year: 12OCT2022
    - Else: 12OCT
    """
    now = datetime.now().astimezone()
    mon = dt.strftime("%b").upper()
    day = dt.strftime("%d")
    if dt.year != now.year:
        return f"{day}{mon}{dt.year}"
    return f"{day}{mon}"


def format_elapsed(delta: timedelta) -> str:
    """
    Pretty elapsed time: D days, HH:MM:SS
    """
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    days = total_seconds // 86400
    rem = total_seconds % 86400
    hours = rem // 3600
    rem %= 3600
    minutes = rem // 60
    seconds = rem % 60
    return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_datetime(text: str) -> datetime:
    """
    Flexible parser:
    Accepts:
      - YYYY-MM-DD HH:MM
      - YYYY-MM-DD HH:MM:SS
      - YYYY-MM-DDTHH:MM
      - YYYY-MM-DD (assumes 00:00)
    Interprets as local time.
    """
    s = text.strip()

    # If only date provided, append midnight
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        s = s + " 00:00"

    # Allow 'T'
    s = s.replace("T", " ")

    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    for f in fmts:
        try:
            naive = datetime.strptime(s, f)
            # local timezone
            return naive.astimezone()
        except ValueError:
            continue
    raise ValueError("Use YYYY-MM-DD HH:MM (or YYYY-MM-DDTHH:MM).")


@dataclass
class Entry:
    id: str
    title: str
    start_iso: str  # stored as ISO with tz
    enabled: bool = True


@dataclass
class Settings:
    fun_numbers: list
    notify_100: bool = True
    notify_1000: bool = True
    notify_fun: bool = True


class Store:
    def __init__(self):
        ensure_dirs()
        self.entries: list[Entry] = []
        self.settings = Settings(fun_numbers=DEFAULT_FUN_NUMBERS.copy())
        # For each entry, track which milestones were already notified
        # map: entry_id -> set(int)
        self.notified: dict[str, set[int]] = {}

    def load(self):
        if not os.path.exists(DATA_FILE):
            self.save()
            return
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.entries = [Entry(**e) for e in data.get("entries", [])]
        s = data.get("settings", {})
        self.settings = Settings(
            fun_numbers=s.get("fun_numbers", DEFAULT_FUN_NUMBERS.copy()),
            notify_100=s.get("notify_100", True),
            notify_1000=s.get("notify_1000", True),
            notify_fun=s.get("notify_fun", True),
        )
        notified_raw = data.get("notified", {})
        self.notified = {k: set(v) for k, v in notified_raw.items()}

    def save(self):
        ensure_dirs()
        data = {
            "entries": [asdict(e) for e in self.entries],
            "settings": asdict(self.settings),
            "notified": {k: sorted(list(v)) for k, v in self.notified.items()},
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_entry(self, title: str, start_dt: datetime):
        if len(self.entries) >= MAX_ENTRIES:
            raise ValueError(f"Max {MAX_ENTRIES} entries.")
        eid = f"e{int(time.time()*1000)}"
        e = Entry(id=eid, title=title.strip(), start_iso=start_dt.isoformat(), enabled=True)
        self.entries.append(e)
        self.notified.setdefault(eid, set())
        self.save()

    def delete_entry(self, entry_id: str):
        self.entries = [e for e in self.entries if e.id != entry_id]
        if entry_id in self.notified:
            del self.notified[entry_id]
        self.save()

    def update_entry(self, entry: Entry):
        for i, e in enumerate(self.entries):
            if e.id == entry.id:
                self.entries[i] = entry
                break
        self.save()


class App(tk.Tk):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.title(f"{APP_NAME}")
        self.geometry("1000x600")

        # UI
        self._build_ui()

        # Start loop
        self._refresh_table()
        self.after(1000, self._tick)

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Title").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.title_var, width=35).grid(row=0, column=1, padx=8, sticky="w")

        ttk.Label(top, text="Start (YYYY-MM-DD HH:MM)").grid(row=0, column=2, sticky="w")
        self.dt_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.dt_var, width=22).grid(row=0, column=3, padx=8, sticky="w")

        ttk.Button(top, text="Add", command=self._on_add).grid(row=0, column=4, padx=8)

        ttk.Button(top, text="Settings", command=self._open_settings).grid(row=0, column=5, padx=4)
        ttk.Button(top, text="Delete Selected", command=self._on_delete).grid(row=0, column=6, padx=4)

        # Table
        mid = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid.pack(fill="both", expand=True)

        cols = ("title", "start", "elapsed", "days", "next")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=20)
        self.tree.heading("title", text="Title")
        self.tree.heading("start", text="Start")
        self.tree.heading("elapsed", text="Elapsed")
        self.tree.heading("days", text="Days")
        self.tree.heading("next", text="Next Milestone")

        self.tree.column("title", width=320, anchor="w")
        self.tree.column("start", width=140, anchor="w")
        self.tree.column("elapsed", width=140, anchor="w")
        self.tree.column("days", width=80, anchor="e")
        self.tree.column("next", width=240, anchor="w")

        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        mid.grid_rowconfigure(0, weight=1)
        mid.grid_columnconfigure(0, weight=1)

        # Status bar
        self.status = tk.StringVar(value=f"Loaded {len(self.store.entries)} entries. Data: {DATA_FILE}")
        ttk.Label(self, textvariable=self.status, padding=6).pack(fill="x")

    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("Settings")
        win.geometry("520x420")
        win.transient(self)
        win.grab_set()

        s = self.store.settings

        notify_100_var = tk.BooleanVar(value=s.notify_100)
        notify_1000_var = tk.BooleanVar(value=s.notify_1000)
        notify_fun_var = tk.BooleanVar(value=s.notify_fun)

        ttk.Checkbutton(win, text="Notify every 100 days", variable=notify_100_var).pack(anchor="w", padx=12, pady=(12, 0))
        ttk.Checkbutton(win, text="Notify every 1000 days", variable=notify_1000_var).pack(anchor="w", padx=12)
        ttk.Checkbutton(win, text="Notify fun numbers", variable=notify_fun_var).pack(anchor="w", padx=12, pady=(0, 8))

        ttk.Label(win, text="Fun numbers (comma or space separated):").pack(anchor="w", padx=12, pady=(8, 0))
        fun_txt = tk.Text(win, height=12, width=60)
        fun_txt.pack(padx=12, pady=8, fill="both", expand=True)
        fun_txt.insert("1.0", ", ".join(str(x) for x in s.fun_numbers))

        def on_save():
            raw = fun_txt.get("1.0", "end").strip()
            nums = set()
            for token in re.split(r"[,\s]+", raw):
                token = token.strip()
                if not token:
                    continue
                if not re.fullmatch(r"\d+", token):
                    messagebox.showerror("Invalid fun number", f"Not an integer: {token}")
                    return
                nums.add(int(token))
            if any(n <= 0 for n in nums):
                messagebox.showerror("Invalid fun number", "All fun numbers must be positive.")
                return

            self.store.settings.notify_100 = bool(notify_100_var.get())
            self.store.settings.notify_1000 = bool(notify_1000_var.get())
            self.store.settings.notify_fun = bool(notify_fun_var.get())
            self.store.settings.fun_numbers = sorted(nums)
            self.store.save()
            self.status.set("Settings saved.")
            win.destroy()

        ttk.Button(win, text="Save", command=on_save).pack(pady=(0, 12))

    def _on_add(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("Missing title", "Enter a title.")
            return
        try:
            start_dt = parse_datetime(self.dt_var.get())
        except ValueError as e:
            messagebox.showerror("Invalid date/time", str(e))
            return

        try:
            self.store.add_entry(title, start_dt)
        except ValueError as e:
            messagebox.showerror("Cannot add", str(e))
            return

        self.title_var.set("")
        self.dt_var.set("")
        self.status.set(f"Added: {title}")
        self._refresh_table()

    def _on_delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Delete", "Select a row to delete.")
            return
        item_id = sel[0]
        entry_id = self.tree.item(item_id, "tags")[0]
        # confirm
        if not messagebox.askyesno("Delete", "Delete selected entry?"):
            return
        self.store.delete_entry(entry_id)
        self.status.set("Deleted entry.")
        self._refresh_table()

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        now = datetime.now().astimezone()

        # Sort by start time ascending
        def start_dt(entry: Entry):
            return datetime.fromisoformat(entry.start_iso)

        for e in sorted(self.store.entries, key=start_dt):
            sd = datetime.fromisoformat(e.start_iso)
            delta = now - sd
            days = int(delta.total_seconds() // 86400)
            elapsed = format_elapsed(delta)
            start_disp = f"{format_date_user(sd)} {sd.strftime('%H:%M')}"
            next_m = self._next_milestone(days)
            self.tree.insert(
                "",
                "end",
                values=(e.title, start_disp, elapsed, f"{max(days,0)}", next_m),
                tags=(e.id,)
            )

        self.status.set(f"Loaded {len(self.store.entries)} entries. Data: {DATA_FILE}")

    def _next_milestone(self, days: int) -> str:
        if days < 0:
            return "Not started yet"
        targets = set()
        s = self.store.settings
        if s.notify_100:
            # next multiple of 100
            n = ((days // 100) + 1) * 100
            targets.add(n)
        if s.notify_1000:
            n = ((days // 1000) + 1) * 1000
            targets.add(n)
        if s.notify_fun and s.fun_numbers:
            # smallest fun number > days
            for fn in s.fun_numbers:
                if fn > days:
                    targets.add(fn)
                    break
        if not targets:
            return "—"
        nxt = min(targets)
        return f"{nxt} days"

    def _tick(self):
        """
        Called every second.
        """
        now = datetime.now().astimezone()
        s = self.store.settings

        # update rows + fire notifications
        for row in self.tree.get_children():
            tags = self.tree.item(row, "tags")
            if not tags:
                continue
            entry_id = tags[0]
            entry = next((x for x in self.store.entries if x.id == entry_id), None)
            if not entry:
                continue

            sd = datetime.fromisoformat(entry.start_iso)
            delta = now - sd
            days = int(delta.total_seconds() // 86400)

            # Update table values
            values = list(self.tree.item(row, "values"))
            # elapsed idx 2, days idx 3, next idx 4
            values[2] = format_elapsed(delta)
            values[3] = f"{max(days,0)}"
            values[4] = self._next_milestone(days)
            self.tree.item(row, values=values)

            # Notify on milestones
            if days >= 0:
                self._check_notify(entry, days)

        # Persist notified state occasionally (cheap write throttle)
        # (writes only if something changed; we track via flag)
        self.after(1000, self._tick)

    def _check_notify(self, entry: Entry, days: int):
        s = self.store.settings
        fired = []

        def mark(m: int):
            self.store.notified.setdefault(entry.id, set()).add(m)
            fired.append(m)

        already = self.store.notified.setdefault(entry.id, set())

        # every 100 days
        if s.notify_100 and days % 100 == 0 and days != 0 and days not in already:
            mark(days)

        # every 1000 days
        if s.notify_1000 and days % 1000 == 0 and days != 0 and days not in already:
            mark(days)

        # fun numbers
        if s.notify_fun and days in set(s.fun_numbers) and days not in already:
            mark(days)

        if fired:
            fired_sorted = sorted(fired)
            # single notification per tick per entry
            title = f"{APP_NAME}: {entry.title}"
            body = f"Reached {fired_sorted[-1]} days since {format_date_user(datetime.fromisoformat(entry.start_iso))}."
            notify(title, body)
            self.store.save()


def main():
    store = Store()
    store.load()
    app = App(store)
    app.mainloop()


if __name__ == "__main__":
    main()
