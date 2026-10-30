import speech_recognition as sr
import pyttsx3
import pywhatkit
import pyautogui
import datetime
import time
import os
import ctypes
import shutil
import subprocess
import threading
import queue
import re
import pygetwindow
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

if __package__:
    from .ai_provider import AIProviderError, OpenAIProvider
else:
    from ai_provider import AIProviderError, OpenAIProvider

# ---------- SETUP ----------
recognizer = sr.Recognizer()
recognizer.dynamic_energy_adjustment_ratio = 1.8
recognizer.phrase_threshold = 0.5

reminders = []  # list of (datetime, message)
ai_assistant = None
last_search_query = None
last_search_browser = None
_ui_events = None
_ui_input_handler = None
_command_queue = None
_stop_event = None
_pause_event = None
_microphone_active_event = threading.Event()


def post_ui_event(event, value=None):
    if _ui_events is not None:
        _ui_events.put((event, value))


def request_text_input(prompt):
    if _ui_input_handler is not None:
        return _ui_input_handler(prompt)
    return input(prompt)


def speak(text):
    print(f"Jarvis: {text}")
    post_ui_event("status", ("SPEAKING", "Jarvis is speaking"))
    post_ui_event("assistant", text)
    voice = pyttsx3.init('sapi5')
    voice.setProperty('rate', 170)
    voice.setProperty('volume', 1.0)
    voice.say(text)
    voice.runAndWait()
    voice.stop()


def listen(force=False):
    if _pause_event is not None and _pause_event.is_set() and not force:
        return ""

    if force:
        post_ui_event("status", ("AWAITING_APPROVAL", "Listening for confirm or cancel"))
    else:
        post_ui_event("status", ("LISTENING", "Waiting for your voice"))
    post_ui_event("microphone", "LISTENING")
    print("Listening...")
    _microphone_active_event.set()
    try:
        with sr.Microphone() as source:
            audio = recognizer.listen(source, timeout=1, phrase_time_limit=8)
        command = recognizer.recognize_google(audio)
        print(f"You said: {command}")
        post_ui_event("user", command)
        return command
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        print("Speech not recognized. Please try again.")
        post_ui_event("notice", "Speech was not recognized. Try speaking again.")
        return ""
    except sr.RequestError:
        speak("Sorry, my speech service is down.")
        return ""
    except (OSError, AttributeError) as error:
        print(f"Microphone error: {error}")
        post_ui_event("status", ("ERROR", "Microphone unavailable or permission denied"))
        speak("I can't access the microphone. Check Windows microphone permissions and the selected input device.")
        return ""
    finally:
        _microphone_active_event.clear()
        post_ui_event(
            "microphone",
            "PAUSED" if _pause_event is not None and _pause_event.is_set() else "READY",
        )


def calibrate_microphone():
    post_ui_event("status", ("CALIBRATING", "Stay quiet briefly while I measure room noise"))
    post_ui_event("microphone", "CALIBRATING")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.5)
    except (OSError, AttributeError) as error:
        print(f"Microphone calibration error: {error}")
        post_ui_event("status", ("ERROR", "Microphone unavailable or permission denied"))
        post_ui_event("microphone", "ERROR")
        speak("I can't calibrate the microphone. Check Windows microphone permissions and the selected input device.")
        return False

    print(f"Microphone calibrated. Energy threshold: {recognizer.energy_threshold:.0f}")
    post_ui_event("microphone", "READY")
    post_ui_event("notice", "Microphone calibrated for current room noise.")
    return True


# ---------- COMMAND ACTIONS ----------
def open_app(app_name):
    if app_name == "chrome":
        if open_chrome():
            speak("Opening Chrome.")
        else:
            speak("I couldn't find Chrome installed on this computer.")
        return

    apps = {
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
        "notepad": "notepad",
        "calculator": "calc",
        "youtube": "https://www.youtube.com",
    }
    key = apps.get(app_name)
    if key:
        os.system(f"start {key}")
        speak(f"Opening {app_name}")
    else:
        speak(f"I don't know how to open {app_name} yet.")


def find_chrome_executable():
    candidates = [
        shutil.which("chrome.exe"),
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def open_chrome(url=None, restore_session=False):
    executable = find_chrome_executable()
    if executable is None:
        return False

    arguments = [executable]
    if restore_session:
        arguments.append("--restore-last-session")
    if url:
        arguments.append(url)
    try:
        subprocess.Popen(arguments)
    except OSError:
        return False
    return True


def open_browser_url(url, browser_name=None):
    if browser_name == "chrome":
        if open_chrome(url=url):
            return True, True
        return webbrowser.open(url, new=2), False

    if browser_name:
        try:
            browser = webbrowser.get(browser_name)
        except webbrowser.Error:
            return webbrowser.open(url, new=2), False
        return browser.open(url, new=2), True

    return webbrowser.open(url, new=2), True


def open_website(address):
    address = address.strip().rstrip(".,!?")
    aliases = {
        "google": "https://www.google.com",
        "google.com": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "youtube.com": "https://www.youtube.com",
        "chatgpt": "https://chatgpt.com",
        "chat gpt": "https://chatgpt.com",
        "chatgpt.com": "https://chatgpt.com",
        "netflix": "https://www.netflix.com",
        "reddit": "https://www.reddit.com",
        "gmail": "https://mail.google.com",
    }
    url = aliases.get(address.lower(), address)
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        parsed_url = urlsplit(url)
        valid_url = (
            parsed_url.scheme in {"http", "https"}
            and parsed_url.hostname
            and parsed_url.username is None
            and parsed_url.password is None
            and not any(character.isspace() for character in parsed_url.netloc)
        )
    except ValueError:
        valid_url = False

    if not valid_url:
        speak("Please say a valid website address, like example.com.")
        return

    opened, _ = open_browser_url(url)
    if opened:
        speak(f"Opening {parsed_url.hostname}.")
    else:
        speak("I couldn't open the website in your default browser.")


def close_app(app_name):
    title_suffixes = {
        "chrome": ("- google chrome",),
        "edge": ("- microsoft edge",),
        "firefox": ("- firefox",),
        "browser": ("- google chrome", "- microsoft edge", "- firefox"),
        "word": ("- word",),
        "excel": ("- excel",),
        "powerpoint": ("- powerpoint",),
        "notepad": ("- notepad",),
        "calculator": ("calculator",),
    }
    suffixes = title_suffixes.get(app_name)
    if suffixes is None:
        speak("I can close Chrome, Edge, Firefox, Word, Excel, PowerPoint, Notepad, or Calculator.")
        return

    matching_windows = [
        window
        for window in pygetwindow.getAllWindows()
        if window.title and window.title.lower().endswith(suffixes)
    ]
    if not matching_windows:
        speak(f"I couldn't find an open {app_name} window.")
        return

    for window in matching_windows:
        window.close()
    speak(f"Closing {app_name}. Save prompts may appear for unsaved work.")


def search_browser(query, browser_name=None):
    global last_search_query, last_search_browser

    query = query.strip()
    if not query:
        speak("What would you like me to search for?")
        return

    last_search_query = query
    last_search_browser = browser_name
    speak(f"Searching Google for {query}")
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    opened, preferred_browser_found = open_browser_url(url, browser_name)
    if not opened:
        speak("I couldn't open the search in a browser.")
    elif browser_name and not preferred_browser_found:
        speak(f"{browser_name.title()} wasn't available, so I used your default browser.")


def open_first_search_result():
    if not last_search_query:
        speak("Search for something first, then ask me to open the first link.")
        return

    url = f"https://www.google.com/search?btnI=1&q={quote_plus(last_search_query)}"
    opened, preferred_browser_found = open_browser_url(url, last_search_browser)
    if not opened:
        speak("I couldn't open the search result in a browser.")
        return
    if last_search_browser and not preferred_browser_found:
        speak(f"{last_search_browser.title()} wasn't available, so I used your default browser.")
    speak(f"Opening Google's top result for {last_search_query}.")


def lock_computer():
    if os.name != "nt":
        speak("Locking the computer is only supported on Windows.")
        return
    if ctypes.windll.user32.LockWorkStation():
        speak("Locking the computer.")
    else:
        speak("Windows couldn't lock the computer.")


def request_power_action(action):
    actions = {
        "shutdown": ("/s", "Shut down"),
        "restart": ("/r", "Restart"),
    }
    switch, label = actions[action]
    speak(
        f"This will {label.lower()} the computer and close open apps. "
        "Say confirm to proceed or cancel to abort."
    )
    was_paused = _pause_event.is_set() if _pause_event is not None else False
    if _pause_event is not None:
        _pause_event.set()
    while _microphone_active_event.is_set() and (_stop_event is None or not _stop_event.is_set()):
        time.sleep(0.05)
    try:
        confirmation = re.sub(r"[^\w\s]", "", listen(force=True).casefold()).strip()
    finally:
        if _pause_event is not None and not was_paused:
            _pause_event.clear()
    if confirmation != "confirm":
        speak(f"{label} cancelled.")
        return

    try:
        subprocess.Popen([
            "shutdown.exe", switch, "/t", "60", "/c",
            f"{label} requested by Jarvis. Use 'cancel shutdown' within 60 seconds to abort.",
        ])
    except OSError:
        speak(f"Windows could not schedule the {label.lower()}.")
        return
    speak(f"{label} scheduled for 60 seconds from now. Say cancel shutdown to abort.")


def cancel_power_action():
    try:
        subprocess.run(["shutdown.exe", "/a"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        speak("There is no pending shutdown or restart to cancel.")
    else:
        speak("Pending shutdown or restart cancelled.")


def request_install(query):
    query = query.strip()
    if not query:
        speak("Tell me what software you want to install.")
        return

    search_browser(f"{query} official download", browser_name="chrome")

    winget = shutil.which("winget.exe") or shutil.which("winget")
    if winget is None:
        speak("Windows Package Manager is not available on this computer.")
        return

    speak(f"Searching the Windows package catalog for {query}.")
    try:
        search_result = subprocess.run(
            [winget, "search", "--query", query, "--source", "winget", "--count", "10", "--accept-source-agreements"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Package search failed: {type(error).__name__}")
        speak("I couldn't search the Windows package catalog.")
        return

    if search_result.returncode != 0 or not search_result.stdout.strip():
        print(search_result.stderr.strip() or search_result.stdout.strip())
        speak("I couldn't find package results. Check the terminal output.")
        return

    print("\nWinget search results (review the name and ID):")
    print(search_result.stdout)
    package_id = request_text_input("Type the exact package ID to inspect it, or press Enter to cancel:").strip()
    if not package_id:
        speak("Installation cancelled.")
        return
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", package_id):
        speak("That package ID has an invalid format. Installation cancelled.")
        return

    try:
        package_details = subprocess.run(
            [winget, "show", "--id", package_id, "--exact", "--source", "winget", "--accept-source-agreements"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Package details lookup failed: {type(error).__name__}")
        speak("I couldn't verify that package. Installation cancelled.")
        return

    if package_details.returncode != 0 or not package_details.stdout.strip():
        print(package_details.stderr.strip() or package_details.stdout.strip())
        speak("I couldn't verify that exact package ID. Installation cancelled.")
        return

    print("\nReview the exact package details, publisher, license, and installer source before proceeding:")
    print(package_details.stdout)
    confirmation = request_text_input(f"Type INSTALL {package_id} exactly to install, or press Enter to cancel:").strip()
    if confirmation.casefold() != f"install {package_id}".casefold():
        speak("Installation cancelled.")
        return

    speak(f"Starting the Winget installer for {package_id}. Review any license and Windows permission prompts.")
    post_ui_event("status", ("EXECUTING", f"Installing package {package_id}"))
    try:
        install_result = subprocess.run(
            [winget, "install", "--id", package_id, "--exact", "--source", "winget"],
            timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Installation did not complete: {type(error).__name__}")
        speak("The installation did not complete. Check the terminal and Windows prompts.")
        return

    if install_result.returncode != 0:
        speak("Winget reported that installation failed or was cancelled. Check the terminal output.")
        return

    try:
        verification = subprocess.run(
            [winget, "list", "--id", package_id, "--exact", "--source", "winget", "--accept-source-agreements"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        speak(f"Winget reported success for {package_id}, but I couldn't verify the installed package.")
        return

    if verification.returncode == 0 and re.search(
        rf"(?<![\w.+-]){re.escape(package_id)}(?![\w.+-])",
        verification.stdout,
        re.IGNORECASE,
    ):
        speak(f"Verified that {package_id} is installed.")
    else:
        speak(f"Winget finished for {package_id}, but I couldn't verify it in the installed package list.")


def play_song(song_name):
    speak(f"Playing {song_name} on YouTube")
    pywhatkit.playonyt(song_name)


def set_reminder(hour, minute, message):
    now = datetime.datetime.now()
    reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if reminder_time < now:
        reminder_time += datetime.timedelta(days=1)
    reminders.append((reminder_time, message))
    speak(f"Reminder set for {reminder_time.strftime('%I:%M %p')}")


def respond_to_ai(command):
    if ai_assistant is None:
        speak("AI chat is not configured. Set OPENAI_API_KEY in this terminal to enable it.")
        return

    try:
        answer = ai_assistant.respond(command)
    except AIProviderError as error:
        print(f"AI chat error: {error}")
        speak("I couldn't reach the AI service. Check the internet connection, API key, and account access.")
    else:
        speak(answer)


def reminder_checker(stop_event=None):
    while stop_event is None or not stop_event.is_set():
        now = datetime.datetime.now()
        for r in reminders[:]:
            reminder_time, message = r
            if now >= reminder_time:
                speak(f"Reminder: {message}")
                reminders.remove(r)
        if stop_event is not None:
            stop_event.wait(20)
        else:
            time.sleep(20)


# ---------- COMMAND PARSER ----------
def process_command(command):
    normalized_command = command.lower()
    search_prefixes = (
        "open chrome search for ",
        "open chrome search ",
        "open browser search for ",
        "open browser search ",
        "search on google for ",
        "search google for ",
        "search on google ",
        "search for ",
        "search ",
        "google ",
    )

    if normalized_command.startswith("type "):
        text = command[5:].strip()
        if text:
            speak("Typing now.")
            pyautogui.write(text, interval=0.03)
        else:
            speak("What should I type?")

    elif normalized_command.startswith("close "):
        close_app(normalized_command[6:].strip())

    elif normalized_command.startswith("install "):
        request_install(command[8:].strip())

    elif normalized_command in {"lock pc", "lock computer", "lock my computer", "lock laptop", "lock my laptop"}:
        lock_computer()

    elif normalized_command in {"unlock", "unlock pc", "unlock computer", "unlock laptop", "unlock my computer", "unlock my laptop"}:
        speak("I can't unlock Windows or handle your sign-in credentials. Please unlock it at the Windows sign-in screen.")

    elif normalized_command in {"shut down", "shutdown", "shut down computer", "shutdown computer", "shut down my computer", "shutdown my computer", "shut down laptop", "shut down my laptop"}:
        request_power_action("shutdown")

    elif normalized_command in {"restart", "restart computer", "restart my computer", "restart laptop", "restart my laptop"}:
        request_power_action("restart")

    elif normalized_command in {"cancel shutdown", "cancel restart", "cancel shutdown or restart"}:
        cancel_power_action()

    elif normalized_command in {"open previous tab", "open previous chrome tab", "restore chrome session", "restore previous chrome session"}:
        if open_chrome(restore_session=True):
            speak("Opening Chrome and asking it to restore the previous session.")
        else:
            speak("I couldn't find Chrome installed on this computer.")

    elif normalized_command in {"open first link", "open the first link", "open first result", "open the first result"}:
        open_first_search_result()

    elif normalized_command.startswith(search_prefixes):
        prefix = next(prefix for prefix in search_prefixes if normalized_command.startswith(prefix))
        browser_name = "chrome" if prefix.startswith("open chrome ") else None
        search_browser(command[len(prefix):], browser_name=browser_name)

    elif normalized_command.startswith("open "):
        app_name = normalized_command[5:].strip()
        if app_name in {"word", "excel", "powerpoint", "notepad", "chrome", "calculator", "youtube"}:
            open_app(app_name)
        elif app_name.startswith("website "):
            open_website(command[12:].strip())
        elif app_name in {"google", "google.com", "chatgpt", "chat gpt", "netflix", "reddit", "gmail"} or "." in app_name or app_name.startswith(("http://", "https://")):
            open_website(command[5:].strip())
        else:
            respond_to_ai(command)

    elif normalized_command.startswith("play "):
        song = command[len("play "):].strip()
        play_song(song)

    elif "remind me" in normalized_command or "wake me" in normalized_command or "set alarm" in normalized_command:
        speak("At what time? Please say the hour and minute, like 7 30.")
        time_text = listen()
        numbers = [int(s) for s in time_text.split() if s.isdigit()]
        if len(numbers) >= 2:
            set_reminder(numbers[0], numbers[1], "Wake up!" if "wake" in normalized_command else "Reminder")
        else:
            speak("Sorry, I didn't catch the time clearly.")

    elif normalized_command in {"stop", "exit", "quit"}:
        speak("Goodbye, Ryan!")
        if _stop_event is not None:
            _stop_event.set()

    else:
        respond_to_ai(command)


# ---------- BACKGROUND WORKERS ----------
def microphone_worker(commands, stop_event, pause_event):
    if not calibrate_microphone():
        return

    while not stop_event.is_set():
        if pause_event.wait(0.1):
            continue
        command = listen()
        if command and not stop_event.is_set():
            commands.put(command)


def command_worker(commands, stop_event, pause_event):
    while not stop_event.is_set():
        try:
            command = commands.get(timeout=0.2)
        except queue.Empty:
            continue

        post_ui_event("status", ("PROCESSING", "Working on your request"))
        try:
            process_command(command)
        except Exception as error:
            print(f"Command error: {type(error).__name__}: {error}")
            post_ui_event("status", ("ERROR", "The command could not be completed"))
            speak("I couldn't complete that command. Check the terminal for details.")
        finally:
            commands.task_done()

        if not stop_event.is_set() and not pause_event.is_set():
            post_ui_event("status", ("LISTENING", "Waiting for your voice or a typed command"))


# ---------- MAIN LOOP ----------
def main():
    global ai_assistant, _ui_events, _ui_input_handler, _command_queue
    global _stop_event, _pause_event, _microphone_active_event

    if __package__:
        from .command_center import JarvisWindow
    else:
        from command_center import JarvisWindow

    _ui_events = queue.Queue()
    _command_queue = queue.Queue()
    _stop_event = threading.Event()
    _pause_event = threading.Event()
    _microphone_active_event = threading.Event()
    window = JarvisWindow(_ui_events, _command_queue, _stop_event, _pause_event)
    _ui_input_handler = window.ask_input

    if os.getenv("OPENAI_API_KEY"):
        try:
            ai_assistant = OpenAIProvider()
        except AIProviderError as error:
            print(f"AI setup error: {error}")
        else:
            print(f"AI chat enabled with model {ai_assistant.model}.")
    else:
        print("AI chat disabled: OPENAI_API_KEY is not set in this terminal.")
    post_ui_event("ai_state", ai_assistant is not None)

    post_ui_event("notice", "Voice assistant ready. Speech recognition uses Google's online service.")

    def announce_and_start_workers():
        if _stop_event.is_set():
            return
        try:
            speak("Jarvis is online.")
        except Exception as error:
            print(f"Startup speech error: {type(error).__name__}: {error}")
            post_ui_event("status", ("ERROR", "Voice output could not start"))
        threading.Thread(
            target=microphone_worker,
            args=(_command_queue, _stop_event, _pause_event),
            daemon=True,
        ).start()
        threading.Thread(
            target=command_worker,
            args=(_command_queue, _stop_event, _pause_event),
            daemon=True,
        ).start()
        threading.Thread(target=reminder_checker, args=(_stop_event,), daemon=True).start()

    window.root.after(
        300,
        lambda: threading.Thread(target=announce_and_start_workers, daemon=True).start(),
    )

    try:
        window.run()
    finally:
        _stop_event.set()
        _pause_event.clear()


if __name__ == "__main__":
    main()
    