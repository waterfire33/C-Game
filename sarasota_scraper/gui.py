import threading
import queue
import sys
import os
import json
import tempfile
import subprocess
import shutil
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

# Import scraper functions (keeps core logic unchanged)
from scraper import search_sarasota_real_estate, save_to_csv


# ==============================================================================
# Cross-Platform OS Compatibility Helpers (Windows, macOS, Linux)
# ==============================================================================

def get_app_config_dir():
    """Returns a platform-appropriate directory for persistent config/state."""
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        app_dir = os.path.join(base, "SarasotaScraper")
    elif sys.platform == "darwin":
        app_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "sarasota_scraper")
    else:
        base = os.getenv("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        app_dir = os.path.join(base, "sarasota_scraper")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_downloads_dir():
    """Resolves the user's Downloads directory across Windows, macOS, and Linux."""
    if sys.platform == "win32":
        try:
            import winreg
            sub_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                downloads_path, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
                if os.path.isdir(downloads_path):
                    return downloads_path
        except Exception:
            pass
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(downloads, exist_ok=True)
    return downloads


def resource_path(relative_path):
    """Get absolute path to resource, compatible with development and PyInstaller bundles."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


def enumerate_system_printers():
    """Enumerates installed printers across Windows, macOS, and Linux."""
    printers = []
    default_printer = None

    if sys.platform == "win32":
        # 1. Try pywin32 win32print
        try:
            import win32print
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printer_records = win32print.EnumPrinters(flags)
            printers = [p[2] for p in printer_records]
            try:
                default_printer = win32print.GetDefaultPrinter()
            except Exception:
                pass
        except ImportError:
            pass

        # 2. Fallback: PowerShell Get-CimInstance (standard on Windows 10/11)
        if not printers:
            try:
                cmd = ["powershell.exe", "-NoProfile", "-Command", "Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    printers = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            except Exception:
                pass
    else:
        # macOS / Linux CUPS lpstat
        lpstat_bin = shutil.which("lpstat") or "/usr/bin/lpstat"
        try:
            proc = subprocess.run([lpstat_bin, "-p"], capture_output=True, text=True, timeout=5)
            for line in proc.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "printer":
                    printers.append(parts[1])
            # Check default printer
            def_proc = subprocess.run([lpstat_bin, "-d"], capture_output=True, text=True, timeout=5)
            if def_proc.returncode == 0 and "destination:" in def_proc.stdout:
                default_printer = def_proc.stdout.split("destination:")[1].strip()
        except Exception:
            pass

    return printers, default_printer


def print_text_file(filename, printer=None):
    """Prints a text file using the native OS spooler. Returns (success, message)."""
    if sys.platform == "win32":
        try:
            import win32print
            import win32api

            if printer:
                win32api.ShellExecute(0, "printto", filename, f'"{printer}"', ".", 0)
                return True, f"Sent to Windows printer: {printer}"
            else:
                if hasattr(os, "startfile"):
                    os.startfile(filename, "print")
                    return True, "Sent to Windows default printer via startfile"
                else:
                    win32api.ShellExecute(0, "print", filename, None, ".", 0)
                    return True, "Sent to Windows default printer via ShellExecute"
        except ImportError:
            # Fallback if pywin32 is not present
            if hasattr(os, "startfile"):
                try:
                    os.startfile(filename, "print")
                    return True, "Sent to Windows default printer"
                except Exception as e:
                    return False, f"Windows startfile print failed: {e}"
            else:
                try:
                    ps_cmd = f"Start-Process -FilePath '{filename}' -Verb Print -PassThru | Out-Null"
                    if printer:
                        ps_cmd = f"Get-Content '{filename}' | Out-Printer -Name '{printer}'"
                    proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
                    if proc.returncode == 0:
                        return True, f"Sent to printer via PowerShell: {printer or 'default'}"
                    return False, f"PowerShell print error: {proc.stderr}"
                except Exception as e:
                    return False, f"Printing failed: {e}"
    else:
        # macOS / Linux CUPS lpr
        lpr_bin = shutil.which("lpr") or "/usr/bin/lpr"
        cmd = [lpr_bin]
        if printer:
            cmd += ["-P", printer]
        cmd.append(filename)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return True, f"Sent to printer (via lpr): {filename}"
        return False, f"Printing failed: {proc.returncode} {proc.stderr}"


# ==============================================================================
# GUI Components
# ==============================================================================

class QueueWriter:
    """File-like object that puts written text into a queue."""
    def __init__(self, q):
        self.q = q

    def write(self, data):
        if data:
            self.q.put(("LOG", str(data)))

    def flush(self):
        pass


class ScraperGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sarasota Scraper GUI")
        self.geometry("800x600")

        # Responsive font scaling:
        # macOS Retina screens benefit from larger scaling (5x), while Windows/Linux use 1.5x
        default_font = tkfont.nametofont("TkDefaultFont")
        font_multiplier = 5 if sys.platform == "darwin" else 1.5
        scaled_size = max(10, int(default_font.cget("size") * font_multiplier))
        self.font = tkfont.Font(family=default_font.cget("family"), size=scaled_size)
        self.option_add("*Font", self.font)

        self.queue = queue.Queue()
        self.current_results = None

        # Cross-platform configuration directory
        app_support_dir = get_app_config_dir()
        self._config_path = os.path.join(app_support_dir, "printer_config.json")
        self.last_printer = self._load_last_printer()

        self._build_widgets()
        self._poll_queue()

    def _build_widgets(self):
        # Row 1: Street entry + Search
        row1 = ttk.Frame(self)
        row1.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(row1, text="Street name:").pack(side=tk.LEFT)
        self.entry = ttk.Entry(row1)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.entry.bind('<Return>', lambda e: self.start_search())

        self.search_btn = ttk.Button(row1, text="Search", command=self.start_search)
        self.search_btn.pack(side=tk.LEFT, padx=6)

        # Row 2: Action buttons (Save, Clear Screen, Print)
        row2 = ttk.Frame(self)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.save_btn = ttk.Button(row2, text="Save to Downloads", command=self.save_results)
        self.save_btn.pack(side=tk.LEFT, padx=6)
        self.save_btn.state(["disabled"])

        self.clear_btn = ttk.Button(row2, text="Clear Screen", command=self.clear_screen)
        self.clear_btn.pack(side=tk.LEFT, padx=6)

        self.print_btn = ttk.Button(row2, text="Print", command=self.print_results)
        self.print_btn.pack(side=tk.LEFT, padx=6)
        self.print_btn.state(["disabled"])

        # Log Display
        self.log = ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, font=self.font)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def append_log(self, text):
        self.log.configure(state=tk.NORMAL)
        try:
            self.log.insert('1.0', text)
            self.log.yview_moveto(0.0)
        except Exception:
            self.log.insert(tk.END, text)
            self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def start_search(self):
        street = self.entry.get().strip()
        if not street:
            return

        self.search_btn.state(["disabled"])
        self.save_btn.state(["disabled"])
        self.current_results = None

        worker = threading.Thread(target=self._run_search_thread, args=(street,), daemon=True)
        worker.start()

    def _run_search_thread(self, street):
        qwriter = QueueWriter(self.queue)
        old_stdout = sys.stdout
        try:
            sys.stdout = qwriter
            results = search_sarasota_real_estate(street)
        except Exception as e:
            self.queue.put(("LOG", f"\nError during search: {e}\n"))
            results = []
        finally:
            sys.stdout = old_stdout

        self.queue.put(("RESULTS", results))
        self.queue.put(("LOG", "\nSearch complete.\n"))

    def _poll_queue(self):
        try:
            while True:
                typ, payload = self.queue.get_nowait()
                if typ == "LOG":
                    self.append_log(payload)
                elif typ == "RESULTS":
                    self.current_results = payload
                    try:
                        self.search_btn.state(["!disabled"])
                    except Exception:
                        pass

                    if payload:
                        try:
                            self.save_btn.state(["!disabled"])
                            self.print_btn.state(["!disabled"])
                        except Exception:
                            pass
                    else:
                        try:
                            self.save_btn.state(["disabled"])
                            self.print_btn.state(["disabled"])
                        except Exception:
                            pass
                self.queue.task_done()
        except queue.Empty:
            pass

        self.after(100, self._poll_queue)

    def save_results(self):
        if not self.current_results:
            self.append_log("\nNo results to save.\n")
            return

        downloads_dir = get_downloads_dir()
        base_name = self.entry.get().strip().replace(' ', '_').upper() or 'RESULTS'
        name, ext = f"{base_name}_results", '.csv'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(downloads_dir, f"{name}_{ts}{ext}")

        try:
            t = threading.Thread(target=self._save_thread, args=(self.current_results, filename), daemon=True)
            t.start()
            self.append_log(f"\nSaving CSV to: {filename}\n")
        except Exception as e:
            self.append_log(f"\nError saving CSV: {e}\n")

    def _save_thread(self, results, filename):
        try:
            save_to_csv(results, filename)
            self.queue.put(("LOG", f"Saved CSV: {filename}\n"))
        except Exception as e:
            self.queue.put(("LOG", f"Error saving CSV: {e}\n"))

    def clear_screen(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.current_results = None
        try:
            self.save_btn.state(["disabled"])
            self.print_btn.state(["disabled"])
        except Exception:
            pass

    def print_results(self):
        if not self.current_results:
            self.append_log("\nNo results to print.\n")
            return

        printer = self._choose_printer()
        if not printer:
            self.append_log("\nPrint cancelled (no printer selected).\n")
            return

        t = threading.Thread(target=self._print_thread, args=(self.current_results, printer), daemon=True)
        t.start()

    def _choose_printer(self):
        printers, system_default = enumerate_system_printers()

        if not printers:
            # If on Windows and enumeration is unavailable, allow default system printing
            if sys.platform == "win32":
                return "Default"
            self.append_log("\nNo printers found on system.\n")
            return None

        dlg = tk.Toplevel(self)
        dlg.title("Select Printer")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text="Choose printer:").pack(padx=12, pady=(12, 6))

        default = printers[0]
        if hasattr(self, 'last_printer') and self.last_printer in printers:
            default = self.last_printer
        elif system_default and system_default in printers:
            default = system_default

        printer_var = tk.StringVar(value=default)
        cmb = ttk.Combobox(dlg, values=printers, textvariable=printer_var, state="readonly")
        cmb.pack(fill=tk.X, padx=12, pady=(0, 12))

        selected = {"printer": None}

        def on_ok():
            selected["printer"] = printer_var.get()
            try:
                self._save_last_printer(selected["printer"])
            except Exception:
                pass
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(btn_frame, text="Print", command=on_ok).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=8)

        self.wait_window(dlg)
        return selected["printer"]

    def _print_thread(self, results, printer=None):
        filename = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tf:
                filename = tf.name
                tf.write('Sarasota Scraper Results\n')
                tf.write(f'Generated: {datetime.now().isoformat()}\n\n')
                for rec in results:
                    line = ', '.join(f"{k}: {v}" for k, v in rec.items())
                    tf.write(line + "\n")

            printer_target = None if printer == "Default" else printer
            success, msg = print_text_file(filename, printer_target)
            if success:
                self.queue.put(("LOG", f"\n{msg}\n"))
            else:
                self.queue.put(("LOG", f"\nPrinting failed: {msg}\n"))
        except Exception as e:
            self.queue.put(("LOG", f"\nError during printing: {e}\n"))
        finally:
            if filename and os.path.exists(filename):
                try:
                    # Windows print spooler needs a moment before temp file deletion
                    if sys.platform == "win32":
                        import time
                        time.sleep(3)
                    os.remove(filename)
                except Exception:
                    pass

    def _load_last_printer(self):
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_printer')
        except Exception:
            pass
        return None

    def _save_last_printer(self, printer_name):
        try:
            data = {'last_printer': printer_name}
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass


def main():
    app = ScraperGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
