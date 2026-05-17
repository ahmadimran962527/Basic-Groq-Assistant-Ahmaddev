import tkinter as tk
from tkinter import font as tkfont
import threading
import sounddevice as sd
import numpy as np
import speech_recognition as sr
import pyttsx3
from groq import Groq

# ---------------- THEME ----------------
BG        = "#0f1117"
SURFACE   = "#1a1d2e"
BUBBLE_U  = "#2563eb"
BUBBLE_AI = "#1e2235"
TEXT_PRI  = "#e8eaf0"
TEXT_SEC  = "#6b7280"
ACCENT    = "#3b82f6"
ACCENT2   = "#06b6d4"
RED       = "#ef4444"
ENTRY_BG  = "#1e2235"
BORDER    = "#2a2d3e"

# ---------------- MODELS ----------------
MODELS = [
    ("Llama 3.3  70B",        "llama-3.3-70b-versatile"),
    ("Llama 3.1  8B  (Fast)", "llama-3.1-8b-instant"),
    ("GPT-OSS  120B",         "openai/gpt-oss-120b"),
    ("GPT-OSS  20B",          "openai/gpt-oss-20b"),
    ("Groq Compound",         "groq/compound"),
    ("Groq Compound Mini",    "groq/compound-mini"),
    ("Qwen 3  32B",           "qwen/qwen3-32b"),
]

client        = None
current_model = None  # set after tk.Tk() is created

# ---------------- TTS ENGINE (global, reusable) ----------------
tts_engine  = None
stop_flag   = threading.Event()   # set this to interrupt speaking

def speak(text):
    global tts_engine
    stop_flag.clear()                        # reset stop flag before speaking

    tts_engine = pyttsx3.init()
    tts_engine.say(text)

    # run in small steps so we can check stop_flag
    tts_engine.startLoop(False)
    while tts_engine.isBusy():
        if stop_flag.is_set():               # user pressed Stop
            tts_engine.stop()
            break
        tts_engine.iterate()
    tts_engine.endLoop()
    tts_engine = None

def stop_speaking():
    """Called when user clicks the Stop button."""
    stop_flag.set()
    if tts_engine:
        try:
            tts_engine.stop()
        except:
            pass
    set_status("⏹  Stopped", RED)
    # re-enable stop btn appearance after a moment
    window.after(800, lambda: set_status("●  Ready", TEXT_SEC))

# ---------------- RECORD AUDIO ----------------
def record_audio(seconds=5, fs=44100):
    set_status("🎤  Listening...", ACCENT2)
    audio = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    audio = np.squeeze(audio)
    set_status("🧠  Recognising...", ACCENT)
    recognizer = sr.Recognizer()
    audio_data = sr.AudioData(audio.tobytes(), fs, 2)
    try:
        return recognizer.recognize_google(audio_data)
    except:
        return None

# ---------------- UI HELPERS ----------------
def set_status(msg, color=TEXT_SEC):
    window.after(0, lambda: status_label.config(text=msg, fg=color))

def add_message(sender, text):
    def _do():
        chat_box.config(state=tk.NORMAL)
        if sender == "you":
            tag   = f"user_{chat_box.index(tk.END)}"
            label = "  You"
            bg    = BUBBLE_U
            align = tk.RIGHT
        else:
            tag   = f"ai_{chat_box.index(tk.END)}"
            label = "  AI"
            bg    = BUBBLE_AI
            align = tk.LEFT

        chat_box.insert(tk.END, f"\n{label}\n", ("sender", sender + "_sender"))
        chat_box.insert(tk.END, f"  {text}  \n\n", (tag, sender + "_bubble"))
        chat_box.tag_config("sender",           font=label_font, foreground=TEXT_SEC)
        chat_box.tag_config("you_sender",       justify=tk.RIGHT)
        chat_box.tag_config("ai_sender",        justify=tk.LEFT)
        chat_box.tag_config(tag,                background=bg,
                                                foreground=TEXT_PRI,
                                                font=body_font,
                                                lmargin1=12, lmargin2=12, rmargin=12,
                                                spacing1=6, spacing3=6)
        chat_box.tag_config(sender + "_bubble", justify=align)
        chat_box.config(state=tk.DISABLED)
        chat_box.see(tk.END)
    window.after(0, _do)

def add_error(text):
    def _do():
        chat_box.config(state=tk.NORMAL)
        chat_box.insert(tk.END, f"\n  ⚠  {text}\n\n", "error")
        chat_box.tag_config("error", foreground=RED, font=label_font, justify=tk.CENTER)
        chat_box.config(state=tk.DISABLED)
        chat_box.see(tk.END)
    window.after(0, _do)

def add_system_note(text):
    def _do():
        chat_box.config(state=tk.NORMAL)
        chat_box.insert(tk.END, f"\n  ⚙  {text}\n\n", "sysnote")
        chat_box.tag_config("sysnote", foreground=ACCENT2, font=label_font, justify=tk.CENTER)
        chat_box.config(state=tk.DISABLED)
        chat_box.see(tk.END)
    window.after(0, _do)

# ---------------- SEND TO AI ----------------
def send_to_ai(user_text):
    add_message("you", user_text)
    set_status("🤖  Thinking...", ACCENT)
    model = current_model.get()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": user_text}]
        )
        reply = response.choices[0].message.content
        add_message("ai", reply)
        # only speak if user hasn't pressed stop
        if not stop_flag.is_set():
            set_status("🔊  Speaking...", ACCENT2)
            window.after(0, lambda: stop_btn.config(state=tk.NORMAL))
            speak(reply)
            window.after(0, lambda: stop_btn.config(state=tk.DISABLED))
    except Exception as e:
        add_error(str(e))
    if not stop_flag.is_set():
        set_status("●  Ready", TEXT_SEC)

# ---------------- VOICE ----------------
def process_voice():
    window.after(0, lambda: mic_btn.config(state=tk.DISABLED))
    user_text = record_audio()
    if not user_text:
        add_error("Could not understand. Try again.")
        set_status("●  Ready", TEXT_SEC)
        window.after(0, lambda: mic_btn.config(state=tk.NORMAL))
        return
    send_to_ai(user_text)
    window.after(0, lambda: mic_btn.config(state=tk.NORMAL))

def start_voice():
    stop_flag.clear()   # clear any previous stop before new request
    threading.Thread(target=process_voice, daemon=True).start()

# ---------------- KEYBOARD ----------------
def process_text(event=None):
    user_text = text_entry.get().strip()
    if not user_text:
        return
    text_entry.delete(0, tk.END)
    stop_flag.clear()   # clear any previous stop before new request
    threading.Thread(target=send_to_ai, args=(user_text,), daemon=True).start()

# ================================================================
#  MODEL PICKER POPUP
# ================================================================
def open_model_picker():
    popup = tk.Toplevel(window)
    popup.title("")
    popup.configure(bg=SURFACE)
    popup.resizable(False, False)
    popup.grab_set()

    row_h = 44
    popup.geometry(f"260x{len(MODELS) * row_h + 50}+{window.winfo_x() + 10}+{window.winfo_y() + 60}")

    tk.Label(popup, text="Select Model", font=btn_font,
             bg=SURFACE, fg=TEXT_PRI, pady=10).pack(fill=tk.X, padx=16)
    tk.Frame(popup, bg=BORDER, height=1).pack(fill=tk.X)

    for display_name, api_name in MODELS:
        is_active = (api_name == current_model.get())
        row_bg  = ACCENT if is_active else SURFACE
        row_fg  = "white" if is_active else TEXT_PRI
        tick    = "✓  " if is_active else "    "

        row = tk.Frame(popup, bg=row_bg, cursor="hand2")
        row.pack(fill=tk.X)

        lbl = tk.Label(row, text=tick + display_name,
                       font=label_font,
                       bg=row_bg, fg=row_fg,
                       anchor=tk.W, padx=14, pady=11)
        lbl.pack(fill=tk.X)
        tk.Frame(popup, bg=BORDER, height=1).pack(fill=tk.X)

        def make_select(api=api_name, dname=display_name):
            def _select(e=None):
                current_model.set(api)
                model_btn.config(text=f"⚙  {dname}  ▾")
                popup.destroy()
                add_system_note(f"Switched to  {dname}")
            return _select

        fn = make_select()
        row.bind("<Button-1>", fn)
        lbl.bind("<Button-1>", fn)

        if not is_active:
            def _enter(e, r=row, l=lbl):
                r.config(bg=BORDER); l.config(bg=BORDER)
            def _leave(e, r=row, l=lbl):
                r.config(bg=SURFACE); l.config(bg=SURFACE)
            row.bind("<Enter>", _enter); row.bind("<Leave>", _leave)
            lbl.bind("<Enter>", _enter); lbl.bind("<Leave>", _leave)

# ================================================================
#  API KEY SCREEN
# ================================================================
def validate_api_key():
    global client
    key = key_entry.get().strip()
    if not key:
        show_key_error("⚠  Please enter your API key.")
        return

    key_status.config(text="⏳  Checking your key...", fg=ACCENT)
    connect_btn.config(state=tk.DISABLED)
    window.update_idletasks()

    def _check():
        global client
        try:
            test_client = Groq(api_key=key)
            test_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            client = test_client
            window.after(0, launch_main_ui)
        except Exception as e:
            err = str(e)
            if "401" in err or "invalid_api_key" in err.lower() or "authentication" in err.lower():
                msg = "❌  Invalid API key — please check and try again."
            elif "connection" in err.lower() or "network" in err.lower():
                msg = "❌  No internet connection."
            else:
                msg = f"❌  {err[:100]}"
            window.after(0, lambda: show_key_error(msg))
            window.after(0, lambda: connect_btn.config(state=tk.NORMAL))

    threading.Thread(target=_check, daemon=True).start()

def show_key_error(msg):
    key_status.config(text=msg, fg=RED)
    key_frame.config(highlightbackground=RED)

def build_key_screen():
    global key_entry, key_status, connect_btn, key_frame

    for w in window.winfo_children():
        w.destroy()

    header = tk.Frame(window, bg=SURFACE, pady=14)
    header.pack(fill=tk.X)
    tk.Label(header, text="⬡  Ahmad's Assistant", font=title_font,
             bg=SURFACE, fg=TEXT_PRI).pack(side=tk.LEFT, padx=20)
    tk.Frame(window, bg=ACCENT, height=2).pack(fill=tk.X)

    card = tk.Frame(window, bg=BG)
    card.pack(fill=tk.BOTH, expand=True)

    inner = tk.Frame(card, bg=SURFACE, padx=40, pady=40)
    inner.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    tk.Label(inner, text="🔑", font=tkfont.Font(size=38),
             bg=SURFACE, fg=ACCENT).pack(pady=(0, 10))
    tk.Label(inner, text="Enter your Groq API Key", font=title_font,
             bg=SURFACE, fg=TEXT_PRI).pack()
    tk.Label(inner, text="Get your free key at  console.groq.com",
             font=label_font, bg=SURFACE, fg=TEXT_SEC).pack(pady=(4, 22))

    key_frame = tk.Frame(inner, bg=ENTRY_BG,
                         highlightbackground=BORDER, highlightthickness=1)
    key_frame.pack(fill=tk.X, pady=(0, 6))

    key_entry = tk.Entry(key_frame, font=entry_font, bg=ENTRY_BG, fg=TEXT_PRI,
                         insertbackground=ACCENT, relief=tk.FLAT, bd=10,
                         show="•", width=36)
    key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    key_entry.bind("<Return>", lambda e: validate_api_key())
    key_entry.bind("<FocusIn>",  lambda e: key_frame.config(highlightbackground=ACCENT))
    key_entry.bind("<FocusOut>", lambda e: key_frame.config(highlightbackground=BORDER))

    show_var = tk.BooleanVar(value=False)
    def toggle_show():
        key_entry.config(show="" if show_var.get() else "•")
    tk.Checkbutton(inner, text="Show key", variable=show_var, command=toggle_show,
                   bg=SURFACE, fg=TEXT_SEC, activebackground=SURFACE,
                   activeforeground=TEXT_PRI, selectcolor=ENTRY_BG,
                   font=label_font, bd=0, cursor="hand2").pack(anchor=tk.W, pady=(2, 14))

    key_status = tk.Label(inner, text="", font=label_font, bg=SURFACE, fg=RED,
                          wraplength=320, justify=tk.CENTER)
    key_status.pack(pady=(0, 14))

    connect_btn = tk.Button(inner, text="Connect  ➤", font=btn_font,
                            bg=ACCENT, fg="white",
                            activebackground=ACCENT2, activeforeground="white",
                            relief=tk.FLAT, bd=0, padx=26, pady=10,
                            cursor="hand2", command=validate_api_key)
    connect_btn.pack()
    key_entry.focus_set()

# ================================================================
#  MAIN CHAT UI
# ================================================================
def launch_main_ui():
    global chat_box, status_label, text_entry, mic_btn, model_btn, stop_btn

    for w in window.winfo_children():
        w.destroy()

    # ── Header ──────────────────────────────────────────
    header = tk.Frame(window, bg=SURFACE, pady=10)
    header.pack(fill=tk.X)

    tk.Label(header, text="⬡  Ahmad's Assistant", font=title_font,
             bg=SURFACE, fg=TEXT_PRI).pack(side=tk.LEFT, padx=20)

    status_label = tk.Label(header, text="●  Ready", font=label_font,
                             bg=SURFACE, fg=TEXT_SEC)
    status_label.pack(side=tk.RIGHT, padx=16)

    initial_label = next(n for n, a in MODELS if a == current_model.get())
    model_btn = tk.Button(
        header,
        text=f"⚙  {initial_label}  ▾",
        font=label_font,
        bg=ENTRY_BG, fg=ACCENT2,
        activebackground=BORDER, activeforeground=ACCENT2,
        relief=tk.FLAT, bd=0, padx=10, pady=6,
        cursor="hand2", command=open_model_picker,
    )
    model_btn.pack(side=tk.RIGHT, padx=(0, 6))

    tk.Frame(window, bg=ACCENT, height=2).pack(fill=tk.X)

    # ── Chat area ────────────────────────────────────────
    chat_frame = tk.Frame(window, bg=BG)
    chat_frame.pack(fill=tk.BOTH, expand=True)

    scrollbar = tk.Scrollbar(chat_frame, bg=SURFACE, troughcolor=BG,
                              activebackground=ACCENT, bd=0, width=6)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    chat_box = tk.Text(chat_frame, wrap=tk.WORD, bg=BG, fg=TEXT_PRI,
                       relief=tk.FLAT, bd=0, padx=18, pady=18,
                       spacing1=2, spacing3=2,
                       yscrollcommand=scrollbar.set,
                       state=tk.DISABLED, cursor="arrow",
                       selectbackground=ACCENT)
    chat_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=chat_box.yview)

    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, "\n  👋  Hello! Type or speak — I'm ready.\n\n", "welcome")
    chat_box.tag_config("welcome", foreground=TEXT_SEC, font=label_font, justify=tk.CENTER)
    chat_box.config(state=tk.DISABLED)

    # ── Separator ────────────────────────────────────────
    tk.Frame(window, bg=BORDER, height=1).pack(fill=tk.X)

    # ── Input bar ────────────────────────────────────────
    input_outer = tk.Frame(window, bg=SURFACE, pady=14)
    input_outer.pack(fill=tk.X)

    input_inner = tk.Frame(input_outer, bg=ENTRY_BG,
                            highlightbackground=BORDER, highlightthickness=1)
    input_inner.pack(fill=tk.X, padx=16)

    text_entry = tk.Entry(input_inner, font=entry_font, bg=ENTRY_BG, fg=TEXT_PRI,
                          insertbackground=ACCENT, relief=tk.FLAT, bd=10)
    text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    text_entry.bind("<Return>", process_text)
    text_entry.bind("<FocusIn>",  lambda e: input_inner.config(highlightbackground=ACCENT))
    text_entry.bind("<FocusOut>", lambda e: input_inner.config(highlightbackground=BORDER))

    tk.Button(input_inner, text="➤", font=btn_font,
              bg=ACCENT, fg="white",
              activebackground=ACCENT2, activeforeground="white",
              relief=tk.FLAT, bd=0, padx=14, pady=8,
              cursor="hand2", command=process_text).pack(side=tk.LEFT)

    # ⏹ Stop speaking button
    stop_btn = tk.Button(input_inner, text="⏹", font=tkfont.Font(size=14),
                         bg=ENTRY_BG, fg=RED,
                         activebackground=BORDER, activeforeground=RED,
                         relief=tk.FLAT, bd=0, padx=10, pady=8,
                         cursor="hand2", command=stop_speaking,
                         state=tk.DISABLED)   # disabled until AI speaks
    stop_btn.pack(side=tk.LEFT, padx=(2, 2))

    mic_btn = tk.Button(input_inner, text="🎤", font=tkfont.Font(size=14),
                        bg=ENTRY_BG, fg=ACCENT2,
                        activebackground=BORDER, activeforeground=ACCENT2,
                        relief=tk.FLAT, bd=0, padx=12, pady=8,
                        cursor="hand2", command=start_voice)
    mic_btn.pack(side=tk.LEFT, padx=(2, 6))

    # ── Footer ────────────────────────────────────────────
    footer = tk.Frame(window, bg=SURFACE, pady=8)
    footer.pack(fill=tk.X)

    tk.Button(footer, text="✕  Quit", font=label_font,
              bg=SURFACE, fg=RED,
              activebackground=RED, activeforeground="white",
              relief=tk.FLAT, bd=0, padx=14, pady=4,
              cursor="hand2", command=window.destroy).pack(side=tk.RIGHT, padx=16)

    tk.Label(footer, text="✦  Ahmad's Assistant", font=label_font,
             bg=SURFACE, fg=TEXT_SEC).pack(side=tk.LEFT, padx=16)

    text_entry.focus_set()

# ================================================================
#  BOOTSTRAP
# ================================================================
window = tk.Tk()
window.title("Ahmad's Assistant")
window.geometry("600x720")
window.resizable(True, True)
window.configure(bg=BG)

try:
    title_font = tkfont.Font(family="SF Pro Display", size=15, weight="bold")
    body_font  = tkfont.Font(family="SF Pro Text",    size=11)
    label_font = tkfont.Font(family="SF Pro Text",    size=9)
    entry_font = tkfont.Font(family="SF Pro Text",    size=12)
    btn_font   = tkfont.Font(family="SF Pro Text",    size=12, weight="bold")
except:
    title_font = tkfont.Font(family="Segoe UI", size=15, weight="bold")
    body_font  = tkfont.Font(family="Segoe UI", size=11)
    label_font = tkfont.Font(family="Segoe UI", size=9)
    entry_font = tkfont.Font(family="Segoe UI", size=12)
    btn_font   = tkfont.Font(family="Segoe UI", size=12, weight="bold")

current_model = tk.StringVar()
current_model.set(MODELS[0][1])

model_btn = None
stop_btn  = None

build_key_screen()
window.mainloop()