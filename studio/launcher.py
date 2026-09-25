"""GeoExplainer.exe - starts the local studio server (if not running) and opens the browser."""
import ctypes, os, subprocess, sys, time, urllib.request, webbrowser

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
# exe lives in geo-explainer/, launcher.py in geo-explainer/studio/
ROOT = HERE if os.path.exists(os.path.join(HERE, "studio", "server.py")) else os.path.dirname(HERE)
PY = os.path.join(os.path.dirname(ROOT), "envs", "tts", "Scripts", "pythonw.exe")
SERVER = os.path.join(ROOT, "studio", "server.py")
URL = "http://localhost:7870"


def up():
    try:
        urllib.request.urlopen(URL + "/api/settings", timeout=2)
        return True
    except Exception:
        return False


def msg(text):
    ctypes.windll.user32.MessageBoxW(0, text, "Geo Explainer Studio", 0x10)


def main():
    if not up():
        if not os.path.exists(PY):
            msg(f"Python not found:\n{PY}\n\nKeep GeoExplainer.exe inside the geo-explainer folder.")
            return
        os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
        log = open(os.path.join(ROOT, "logs", "server.log"), "ab", buffering=0)
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        subprocess.Popen([PY, SERVER], cwd=os.path.join(ROOT, "studio"), creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True)
        for _ in range(40):
            time.sleep(0.5)
            if up():
                break
        else:
            msg("The studio did not start. See geo-explainer\\logs\\server.log")
            return
    webbrowser.open(URL)


if __name__ == "__main__":
    main()
