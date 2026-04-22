#!/usr/bin/env python3
"""
PDF Attendance Parser — For De Colores Learning Center & Childcare

Copyright (c) 2026 Dominic Finch
Licensed under the MIT License
"""

import customtkinter as ctk  
import threading             
import os                     
import sys                    
import calendar              
import re                     
from tkinter import filedialog, messagebox  
from collections import defaultdict         
try:
    import pdfplumber 
except ImportError:
    # If it's not installed, install it automatically then import it
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber",
                           "--break-system-packages", "-q"])
    import pdfplumber


#  Attendance parsing logic

# Maps month name strings to their number — used when reading month names from the PDF
MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
}
# Function to get all the weekdays in a given month
def weekdays_in_month(year, month, excluded_days=None):
    days = []
    # calendar.monthcalendar() returns a list of weeks; each week is 7 days (Mon–Sun)
    # Days outside the month are represented as 0
    for week in calendar.monthcalendar(year, month):
        for col, day in enumerate(week):
            # day != 0 means to return a real day in month
            # days are sorted by monday=0, tuesday=1, etc. (change if always closed on a certain weekday)
            if day != 0 and col < 5:
                days.append(day)
    result = frozenset(days)  # frozenset = immutable set, good for lookups
    if excluded_days:
        result = result - frozenset(excluded_days)  # Remove holiday/closed days
    return result


def detect_month_year(pdf_path):
    # Regex pattern to find something like "April 2026" in the PDF text
    month_re = re.compile(r'\b(' + '|'.join(MONTHS) + r')\s+(\d{4})\b', re.IGNORECASE)
    # month_re returns April 2026
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:3]:  # Only check the first 3 pages (can be lowered because year always mentioned on first page(change if layout changes))
            text = page.extract_text() or ""  # Extract text; fall back to "" if None
            # If this fails the pdf likely has text that cannot be extracted / scanned pdf.
            m = month_re.search(text)
            if m:
                # returns year then month (look at MONTHS dict to see what number each month corresponds to)
                return int(m.group(2)), MONTHS[m.group(1).lower()]
            # fix error find better parse method to find month
    raise ValueError("Could not detect month/year from PDF.")

def normalise_name(raw):
    raw = raw.strip()
    if "," in raw:
        # Name is in "Last, First" format — title-case each part separately
        last, first = raw.split(",", 1)
        return f"{last.strip().title()}, {first.strip().title()}"
    return raw.title()  # title() capitalises the first letter of each word

def extract_child_name(lines):
    # Find the line containing the centre name — the child's name is near it
    dc_idx = None
    for i, line in enumerate(lines):
        #find line that says "De Colores Learning Center" — the child name is usually on the same line
        if "De Colores Learning Center" in line:
            dc_idx = i
            break
    if dc_idx is None:
        return None

    dc_line = lines[dc_idx]
    # Strip out the centre name and anything after a "Month YYYY" pattern
    after_centre = re.sub(r"De Colores Learning Center.*?Childcare\s*", "", dc_line).strip()
    after_centre = re.sub(r"\b[A-Z][a-z]+ \d{4}.*$", "", after_centre).strip()

    candidates = [after_centre] if after_centre else []

    # Also check the next few lines after the centre name line
    for j in range(dc_idx + 1, min(dc_idx + 4, len(lines))):
        nxt = lines[j].strip()
        # Skip lines that are headers or labels, not actual names
        if nxt and not any(kw in nxt for kw in ("Unit of","Date","Time In","PENALTY","Child's","Sign-In")):
            nxt = re.sub(r"\b[A-Z][a-z]+ \d{4}.*$", "", nxt).strip()
            if nxt:
                candidates.append(nxt)

    for cand in candidates:
        if "," not in cand:
            continue  # A valid "Last, First" name must have a comma
        cand = re.sub(r"De Colores Learning Center.*?Childcare\s*", "", cand).strip()
        cand = re.sub(r"\b[A-Z][a-z]+ \d{4}.*$", "", cand).strip()
        if not cand or "," not in cand:
            continue
        # Try to extract just the child name when multiple names appear on one line
        m = re.match(r'^(.+?,\s+.+?)\s+(?=[A-Za-z][A-Za-z\'\-]*(?:\s+[A-Z][A-Za-z]*)*,)', cand)
        if m:
            child_raw = m.group(1).strip()
            child_raw = re.sub(r'\s+[a-z].*$', '', child_raw).strip()
            if "," in child_raw:
                return normalise_name(child_raw)
        # Simpler fallback: match a plain "Last, First" with nothing after it
        m2 = re.match(r'^([A-Za-z][A-Za-z\'\- ]+,\s+[A-Za-z][A-Za-z \.\']+)\s*$', cand)
        if m2:
            return normalise_name(m2.group(1).strip())
    return None

# Pre-compiled regex for speed — matches lines starting with a day number and a time
# e.g. "5 08:30 AM" — compiled once here rather than re-compiled on every line
_DATE_RE = re.compile(r'^(\d{1,2})\s+\d{1,2}:\d{2}\s+(?:AM|PM)')

def extract_attended_days(lines, school_days):
    attended = set()
    for line in lines:
        m = _DATE_RE.match(line.strip())
        if m:
            day = int(m.group(1))  # The first capture group is the day number
            if day in school_days:  # Only count it if it's a real school day
                attended.add(day)
    return attended

def parse_pdf(pdf_path, school_days):
    records = {}
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            lines      = text.splitlines()
            child_name = extract_child_name(lines)
            attended   = extract_attended_days(lines, school_days)
            if not child_name:
                continue
            if child_name in records:
                records[child_name] |= attended  # |= merges two sets together
            else:
                records[child_name] = attended
            # yield sends a value back to the caller without ending the function
            # This lets us report progress page-by-page while parsing continues
            yield page_num, total, None
    yield None, None, records  # Final yield sends the completed records dict

def best_absent_days(attended, school_days, n=5):
    """
    Return up to n absent days, prioritising consecutive runs.
    school_days already has holidays removed, so holidays never
    appear in absent or attended — they are invisible to this logic.
    """
    absent = sorted(school_days - attended)  # Days in school but not attended
    if not absent or n <= 0:
        return []
    if len(absent) <= n:
        return absent  # Fewer absences than limit — return them all

    # Build a rank for each school day by its position in the sorted list
    # This lets us check if two absent days are consecutive school days
    # (even if there's a holiday between them in calendar terms)
    school_order = sorted(school_days)
    rank = {d: i for i, d in enumerate(school_order)}  # Dict comprehension: {day: index}

    # Group absent days into consecutive runs based on school-day order
    runs, cur = [], [absent[0]]
    for d in absent[1:]:
        if rank[d] == rank[cur[-1]] + 1:  # Next school day in sequence
            cur.append(d)
        else:
            runs.append(cur); cur = [d]  # Start a new run
    runs.append(cur)

    # Sort runs: longest first, then by earliest start date
    runs.sort(key=lambda r: (-len(r), r[0]))

    # Pick days from the longest runs first, up to the limit n
    chosen, used = [], set()
    for run in runs:
        for d in run:
            if len(chosen) >= n:
                break
            if d not in used:
                chosen.append(d); used.add(d)
        if len(chosen) >= n:
            break
    # Fill any remaining slots with leftover absent days
    for d in absent:
        if len(chosen) >= n:
            break
        if d not in used:
            chosen.append(d); used.add(d)
    return sorted(chosen)

def build_report(records, school_days, month_name, year):
    # For each child, get their top absent days
    child_absences = {n: best_absent_days(d, school_days) for n, d in records.items()}

    # Group children who share the exact same absent days
    # defaultdict(list) auto-creates an empty list for any new key
    groups = defaultdict(list)
    for name, days in child_absences.items():
        groups[tuple(days)].append(name)  # tuple() makes the list hashable (usable as a dict key)
    groups = dict(groups)  # Convert back to a regular dict

    shared     = {k: v for k, v in groups.items() if len(v) > 1}  # Dict comprehension: groups with 2+ children
    singletons = {k: v for k, v in groups.items() if len(v) == 1}

    BAR = "─" * 54
    lines = [
        f"Attendance Absence Report — {month_name} {year}",
        f"School days: {sorted(school_days)}",
        f"Max 5 absent days shown per child (consecutive runs prioritised)",
        "",
    ]
    sec = 1
    # Print shared groups first (children who missed the same days)
    for days, names in sorted(shared.items(), key=lambda x: x[0] or ()):
        day_str = ", ".join(map(str, days)) if days else "(no absences)"
        lines += [BAR, f"Section {sec}  —  Missed: {day_str}  ({len(names)} kids)", BAR]
        for name in sorted(names):
            lines.append(f"  {name}")
            lines.append(f"  {day_str}")
        lines.append("")
        sec += 1
    if singletons:
        lines += [BAR, f"Section {sec}  —  Individual absences", BAR]
        for days, names in sorted(singletons.items(), key=lambda x: (x[0] if x[0] else (999,))):
            day_str = ", ".join(map(str, days)) if days else "(no absences)"
            lines.append(f"  {names[0]}")
            lines.append(f"  {day_str}")
        lines.append("")

    stats = {
        "total":   len(records),
        "absent":  sum(1 for d in child_absences.values() if d),       # Count children with any absences
        "perfect": sum(1 for d in child_absences.values() if not d),   # Count children with zero absences
        "groups":  sum(1 for v in groups.values() if len(v) > 1),
        "month":   f"{month_name} {year}",
    }
    return "\n".join(lines), stats  # Join all lines into one big string

# ─────────────────────────────────────────────────────────────────────────────
#  UI colors
# ─────────────────────────────────────────────────────────────────────────────

# Hex color constants used throughout the UI — defined once so they're easy to change


#Colors used for text and UI elements, change if you want a different color scheme
MYBLUE   = "#4F8EF7"
MYPURPLE  = "#A78BFA"
BG_DARK  = "#0F1117"
BG_CARD  = "#1A1D2E"
BG_SIDE  = "#13151F"
TEXT     = "#E8EAF0"
SUBTEXT  = "#8B8FA8"
MYGREEN  = "#34D399"
MYYELLOW  = "#FBBF24"
MYRED   = "#F87171"
MYBLACK   = "#2A2D3E"


class StatCard(ctk.CTkFrame):
    # A reusable UI card widget that shows a label and a large number
    def __init__(self, parent, label, value, color=MYBLUE, **kwargs):
        # **kwargs passes any extra keyword arguments up to the parent class
        super().__init__(parent, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=MYBLACK, **kwargs)
        ctk.CTkLabel(self, text=label, font=("Courier New", 11),
                     text_color=SUBTEXT).pack(pady=(14, 2))
        self.val_label = ctk.CTkLabel(self, text=str(value),
                                      font=("Courier New", 28, "bold"),
                                      text_color=color)
        self.val_label.pack(pady=(0, 14))

    def update_value(self, value):
        # Update just the number displayed, without rebuilding the whole widget
        self.val_label.configure(text=str(value))




# UI 
class App(ctk.CTk):
    # The main application window — inherits from ctk.CTk (the root window class)
    def __init__(self):
        super().__init__()  # Initialise the parent CTk window
        self.title("PDF Attendance Parser")
        self.geometry("1000x660")
        self.minsize(900, 580)
        self.configure(fg_color=BG_DARK)

        # Instance variables — underscore prefix is a convention meaning "internal use"
        self._pdf_path   = None   # Path to the selected PDF file
        self._report_txt = None   # The generated report text
        self._parsing    = False  # Flag to prevent double-parsing

        self._build_sidebar()
        self._build_main()

    #Sidebar
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=220, fg_color=BG_SIDE,
                          corner_radius=0, border_width=0)
        # grid() places the widget in a row/column layout; sticky="nsew" stretches it to fill the cell
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)  # Prevent the frame from shrinking to fit its contents
        sb.grid_rowconfigure(8, weight=1)  # Row 8 gets all spare vertical space (pushes nav up)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)  # The main content column expands to fill the window

        ctk.CTkLabel(sb, text="📋", font=("Courier New", 36)).grid(
            row=0, column=0, padx=24, pady=(32, 4))
        ctk.CTkLabel(sb, text="PDF Attendance\nParser",
                     font=("Courier New", 14, "bold"),
                     text_color=TEXT, justify="center").grid(
            row=1, column=0, padx=24, pady=(0, 32))

        ctk.CTkFrame(sb, height=1, fg_color=MYBLACK).grid(
            row=2, column=0, sticky="ew", padx=16)  # Thin horizontal divider line



        self._nav_btns = []
        nav = [
            ("  🏠  Dashboard", "dashboard"),
            ("  📄  Results",   "results"),
            ("  ⚙️  Settings",  "settings"),
        ]
        for i, (label, name) in enumerate(nav):
            btn = ctk.CTkButton(sb, text=label, anchor="w",
                                font=("Courier New", 13),
                                fg_color="transparent", text_color=SUBTEXT,
                                hover_color=MYBLACK, corner_radius=8, height=42,
                                # lambda n=name captures the current value of name in the loop
                                # Without n=name, all buttons would use the last value of name
                                command=lambda n=name: self._show_page(n))
            btn.grid(row=3 + i, column=0, padx=12, pady=3, sticky="ew")
            self._nav_btns.append((name, btn))

    # ── Main container ────────────────────────────────────────────────────────

    def _build_main(self):
        self._pages = {}
        container = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        container.grid(row=0, column=1, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Build all three pages and store them — only one is shown at a time
        self._pages["dashboard"] = self._build_dashboard(container)
        self._pages["results"]   = self._build_results(container)
        self._pages["settings"]  = self._build_settings(container)

        self._show_page("dashboard")

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _build_dashboard(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=BG_DARK, corner_radius=0)
        frame.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 0))
        ctk.CTkLabel(hdr, text="Dashboard",
                     font=("Courier New", 22, "bold"),
                     text_color=TEXT).pack(side="left")

        drop = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=16,
                            border_width=2, border_color=MYBLACK)
        drop.grid(row=1, column=0, sticky="ew", padx=32, pady=20)
        drop.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(drop, text="Select Attendance PDF",
                     font=("Courier New", 15, "bold"),
                     text_color=TEXT).grid(row=0, column=0, pady=(24, 4))
        ctk.CTkLabel(drop,
                     text="Supports monthly De Colores Learning Center & Childcare sign-in/sign-out sheets",
                     font=("Courier New", 11), text_color=SUBTEXT).grid(row=1, column=0, pady=(0, 16))

        btn_row = ctk.CTkFrame(drop, fg_color="transparent")
        btn_row.grid(row=2, column=0, pady=(0, 24))

        ctk.CTkButton(btn_row, text="📂  Open PDF",
                      font=("Courier New", 13, "bold"),
                      fg_color=MYBLUE, hover_color="#3A72D8",
                      corner_radius=10, height=42, width=160,
                      command=self._select_file).pack(side="left", padx=8)

        self._parse_btn = ctk.CTkButton(btn_row, text="⚡  Parse",
                                        font=("Courier New", 13, "bold"),
                                        fg_color=BG_CARD,
                                        border_width=1, border_color=MYBLUE,
                                        text_color=MYBLUE, hover_color=MYBLACK,
                                        corner_radius=10, height=42, width=160,
                                        state="disabled",  # Greyed out until a file is selected
                                        command=self._start_parse)
        self._parse_btn.pack(side="left", padx=8)

        self._save_btn = ctk.CTkButton(btn_row, text="💾  Save Report",
                                        font=("Courier New", 13, "bold"),
                                        fg_color=BG_CARD,
                                        border_width=1, border_color=MYBLUE,
                                        text_color=MYBLUE, hover_color=MYBLACK,
                                        corner_radius=10, height=42, width=160,
                                        state="disabled",  # Greyed out until a report is generated
                                        command=self._save_report)
        self._save_btn.pack(side="left", padx=8)

        self._file_label = ctk.CTkLabel(drop, text="No file selected",
                                         font=("Courier New", 11), text_color=SUBTEXT)
        self._file_label.grid(row=3, column=0, pady=(0, 8))

        #Progress bar is still broken but core functionality works (EDIT LATER)
        self._progress = ctk.CTkProgressBar(drop, width=400, height=6,
                                             fg_color=MYBLACK, progress_color=MYBLUE,
                                             corner_radius=3)
        self._progress.set(0)
        self._progress_label = ctk.CTkLabel(drop, text="",
                                             font=("Courier New", 10), text_color=SUBTEXT)
        # Note: progress bar and label are not grid()'d here — they appear only when parsing starts

        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.grid(row=2, column=0, sticky="ew", padx=32, pady=(0, 20))
        for i in range(4):
            # weight=1 means all columns share space equally; minsize stops them squishing too narrow
            cards_frame.grid_columnconfigure(i, weight=1, minsize=120)

        self._stat_total   = StatCard(cards_frame, "TOTAL CHILDREN",     "—", MYBLUE)
        self._stat_absent  = StatCard(cards_frame, "WITH ABSENCES",      "—", MYYELLOW)
        self._stat_perfect = StatCard(cards_frame, "PERFECT ATTENDANCE", "—", MYGREEN)
        self._stat_groups  = StatCard(cards_frame, "SHARED GROUPS",      "—", MYPURPLE)

        for col, card in enumerate([self._stat_total, self._stat_absent,
                                     self._stat_perfect, self._stat_groups]):
            card.grid(row=0, column=col, padx=6, sticky="ew")

        log_hdr = ctk.CTkFrame(frame, fg_color="transparent")
        log_hdr.grid(row=3, column=0, sticky="ew", padx=32, pady=(4, 6))
        ctk.CTkLabel(log_hdr, text="Status Log",
                     font=("Courier New", 13, "bold"), text_color=TEXT).pack(side="left")

        self._log = ctk.CTkTextbox(frame, height=120, fg_color=BG_CARD,
                                    text_color=SUBTEXT, font=("Courier New", 11),
                                    corner_radius=12, border_width=1, border_color=MYBLACK)
        self._log.grid(row=4, column=0, sticky="ew", padx=32, pady=(0, 28))
        self._log.configure(state="disabled")  # Read-only — users can't type in the log
        self._log_write("Ready. Open a PDF file to get started.")

        return frame

    # ── Results ───────────────────────────────────────────────────────────────

    def _build_results(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=BG_DARK, corner_radius=0)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)  # Row 1 (the textbox) expands vertically

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 12))
        ctk.CTkLabel(hdr, text="Results",
                     font=("Courier New", 22, "bold"), text_color=TEXT).pack(side="left")
        self._period_label = ctk.CTkLabel(hdr, text="",
                                           font=("Courier New", 13), text_color=SUBTEXT)
        self._period_label.pack(side="left", padx=16)

        self._results_box = ctk.CTkTextbox(frame, fg_color=BG_CARD, text_color=TEXT,
                                            font=("Courier New", 12), corner_radius=12,
                                            border_width=1, border_color=MYBLACK, wrap="none")
        self._results_box.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 28))
        self._results_box.insert("1.0", "Parse a PDF to see results here.")  # "1.0" = line 1, char 0
        self._results_box.configure(state="disabled")

        return frame

    # ── Settings ──────────────────────────────────────────────────────────────

    def _build_settings(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=BG_DARK, corner_radius=0)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Settings",
                     font=("Courier New", 22, "bold"), text_color=TEXT).grid(
            row=0, column=0, sticky="w", padx=32, pady=(28, 20))

        card = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=16,
                            border_width=1, border_color=MYBLACK)
        card.grid(row=1, column=0, sticky="ew", padx=32)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🗓  Closed / Holiday Days",
                     font=("Courier New", 14, "bold"), text_color=TEXT).grid(
            row=0, column=0, sticky="w", padx=24, pady=(22, 4))

        ctk.CTkLabel(card,
                     text="Enter the day numbers the daycare is closed (comma-separated).\n"
                          "These days are removed from the school calendar entirely — "
                          "they won't appear as absences for anyone.",
                     font=("Courier New", 11), text_color=SUBTEXT,
                     wraplength=580, justify="left").grid(
            row=1, column=0, sticky="w", padx=24, pady=(0, 14))

        self._holiday_entry = ctk.CTkEntry(
            card,
            placeholder_text="e.g.  24, 25",
            font=("Courier New", 13),
            fg_color=BG_DARK, border_color=MYBLACK,
            text_color=TEXT, height=40)
        self._holiday_entry.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 8))
        # Trigger feedback update on every keystroke so the user sees live validation
        self._holiday_entry.bind("<KeyRelease>", self._on_holiday_key)

        self._holiday_feedback = ctk.CTkLabel(
            card, text="No days entered — all weekdays will count as school days.",
            font=("Courier New", 11), text_color=SUBTEXT)
        self._holiday_feedback.grid(row=3, column=0, sticky="w", padx=24, pady=(0, 22))

        return frame

    # ── Settings helpers ──────────────────────────────────────────────────────

    def _on_holiday_key(self, _event=None):
        # _event is passed by tkinter but we don't use it — underscore signals it's intentionally ignored
        days, err = self._parse_holiday_entry()
        if err:
            self._holiday_feedback.configure(text=f"⚠  {err}", text_color=MYRED)
        elif days:
            self._holiday_feedback.configure(
                text=f"✓  {len(days)} day(s) excluded: {', '.join(map(str, days))}",
                text_color=MYGREEN)
        else:
            self._holiday_feedback.configure(
                text="No days entered — all weekdays will count as school days.",
                text_color=SUBTEXT)

    def _parse_holiday_entry(self):
        """Return (sorted list of valid day ints, error_string_or_None).
        Supports individual days (24) and ranges (4-8), comma-separated."""
        raw = self._holiday_entry.get().strip()
        if not raw:
            return [], None
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]  # List comprehension: split and clean each part
        days, seen = [], set()
        for p in parts:
            if not p:
                continue
            if "-" in p:
                # Handle a range like "4-8" — split into start and end
                bounds = p.split("-", 1)
                if not all(b.strip().isdigit() for b in bounds):  # all() checks every item is True
                    return [], f"'{p}' is not a valid range."
                # FIX: renamed from min/max to range_start/range_end
                # Using min and max as variable names overwrites Python's built-in functions
                # of the same name, which could cause subtle bugs elsewhere in the code
                range_start, range_end = int(bounds[0].strip()), int(bounds[1].strip())
                if range_start > range_end:
                    return [], f"Range '{p}' start must be ≤ end."
                if not (1 <= range_start <= 31 and 1 <= range_end <= 31):
                    return [], f"Range '{p}' must be within 1–31."
                for d in range(range_start, range_end + 1):
                    if d not in seen:
                        days.append(d)
                        seen.add(d)
            else:
                if not p.isdigit():
                    return [], f"'{p}' is not a valid day number."
                d = int(p)
                if not (1 <= d <= 31):
                    return [], f"Day {d} is out of range (1–31)."
                if d not in seen:  # Avoid adding the same day twice
                    days.append(d)
                    seen.add(d)
        return sorted(days), None

    # ── Page switching ────────────────────────────────────────────────────────

    def _show_page(self, name):
        # Highlight the active nav button and dim the others
        for n, btn in self._nav_btns:
            btn.configure(text_color=TEXT if n == name else SUBTEXT,
                          fg_color=MYBLACK if n == name else "transparent")
        # Show only the selected page; hide all others by removing them from the grid
        for n, pg in self._pages.items():
            if n == name:
                pg.grid(row=0, column=0, sticky="nsew")
            else:
                pg.grid_forget()  # Removes widget from layout without destroying it

    # ── File / parse actions ──────────────────────────────────────────────────

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Open Attendance PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All files", "*.*")]
        )
        if path:
            self._pdf_path = path
            short = os.path.basename(path)  # Just the filename, not the full path
            self._file_label.configure(text=f"📄  {short}", text_color=TEXT)
            self._parse_btn.configure(state="normal")   # Enable the Parse button
            self._save_btn.configure(state="disabled")  # Reset Save until new report is ready
            self._report_txt = None
            self._log_write(f"File selected: {short}")
            # Reset stat cards to dashes
            for card in (self._stat_total, self._stat_absent,
                         self._stat_perfect, self._stat_groups):
                card.update_value("—")


    def _start_parse(self):
        if not self._pdf_path or self._parsing:
            return  # Guard: do nothing if no file selected or already parsing

        excluded, err = self._parse_holiday_entry()
        if err:
            messagebox.showerror("Invalid holiday days",
                                 f"Fix the holiday entry in Settings first:\n\n{err}")
            return

        self._parsing = True
        #ensure buttons are disabled found crashes happen when clicking parse multiple times
        self._parse_btn.configure(state="disabled", text="⏳  Parsing…")
        self._save_btn.configure(state="disabled")
        self._log_write(f"Parsing {os.path.basename(self._pdf_path)}…")
        if excluded:
            self._log_write(f"Excluding closed/holiday days: {excluded}")

        # Show the progress bar now that parsing is starting
        self._progress.grid(row=4, column=0, pady=(4, 4))
        self._progress_label.grid(row=5, column=0, pady=(0, 8))
        self._progress.set(0)
        # Run the parser in a background thread so the UI stays responsive
        threading.Thread(target=self._parse_worker, args=(excluded,), daemon=True).start()

    def _parse_worker(self, excluded_days):
        # This runs on a background thread — never touch UI widgets directly here
        # Use self.after(0, callable) to safely schedule any UI updates on the main thread
        try:
            year, month = detect_month_year(self._pdf_path)
            school_days = weekdays_in_month(year, month, excluded_days)
            month_name  = calendar.month_name[month]

            # FIX: _log_write touches a UI widget, so it must be called via self.after()
            # Calling it directly from a background thread could cause a crash or silent corruption
            self.after(0, lambda: self._log_write(f"Detected period: {month_name} {year}"))
            self.after(0, lambda: self._log_write(f"School days ({len(school_days)}): {sorted(school_days)}"))

            records = {}
            for page_num, total, result in parse_pdf(self._pdf_path, school_days):
                if result is not None:
                    records = result  # Final yield from parse_pdf — contains all records
                else:
                    pct = page_num / total
                    # Schedule progress bar update on the main thread
                    self.after(0, lambda p=pct, n=page_num, t=total: (
                        self._progress.set(p),
                        self._progress_label.configure(text=f"Page {n} / {t}")
                    ))

            report_txt, stats = build_report(records, school_days, month_name, year)
            self._report_txt = report_txt

            def _done():
                # All UI updates happen here, safely on the main thread
                self._progress.set(1)
                self._progress_label.configure(text="Complete ✓")
                self._stat_total.update_value(stats["total"])
                self._stat_absent.update_value(stats["absent"])
                self._stat_perfect.update_value(stats["perfect"])
                self._stat_groups.update_value(stats["groups"])
                self._log_write(
                    f"Done! {stats['total']} children | "
                    f"{stats['absent']} with absences | "
                    f"{stats['groups']} shared groups"
                )
                self._parse_btn.configure(state="normal", text="⚡  Parse")
                self._save_btn.configure(state="normal")
                self._parsing = False

                # FIX: hide the progress bar and its label after parsing completes
                # Previously they remained visible permanently after the first parse
                self._progress.grid_remove()        # grid_remove() hides the widget but remembers
                self._progress_label.grid_remove()  # its grid settings, so grid() will restore it

                self._results_box.configure(state="normal")   # Temporarily enable to insert text
                self._results_box.delete("1.0", "end")        # Clear previous results
                self._results_box.insert("1.0", report_txt)
                self._results_box.configure(state="disabled") # Lock it again so users can't edit it
                self._period_label.configure(text=stats["month"])

            self.after(0, _done)  # Schedule _done to run on the main thread

        except Exception as e:
            def _err(msg=str(e)):
                self._log_write(f"ERROR: {msg}")
                self._parse_btn.configure(state="normal", text="⚡  Parse")
                # FIX: also hide the progress bar on error so it doesn't get stuck showing
                self._progress.grid_remove()
                self._progress_label.grid_remove()
                self._parsing = False
            self.after(0, _err)

    def _save_report(self):
        if not self._report_txt:
            return
        path = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All files", "*.*")],
            initialfile="attendance_absences.txt"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._report_txt)
            self._log_write(f"Saved → {os.path.basename(path)}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_write(self, msg):
        self._log.configure(state="normal")   # Temporarily unlock so we can insert text
        self._log.insert("end", f"› {msg}\n") # "end" means append to the bottom
        self._log.see("end")                  # Auto-scroll to show the latest message
        self._log.configure(state="disabled") # Lock it again so users can't edit it


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # This block only runs when you execute this file directly
    # It won't run if this file is imported as a module by another script
    app = App()
    app.mainloop()  # Starts the UI event loop — the app runs until the window is closed