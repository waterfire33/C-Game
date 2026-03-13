import threading
import queue
import sys
import os
import json
import tempfile
import subprocess
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

# Import scraper functions (keeps core logic unchanged)
from scraper import search_sarasota_real_estate, save_to_csv


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

        # Create a scaled font (5x) based on the default GUI font
        default_font = tkfont.nametofont("TkDefaultFont")
        scaled_size = max(1, int(default_font.cget("size") * 5))
        self.font = tkfont.Font(family=default_font.cget("family"), size=scaled_size)
        # Apply as the default font for widgets
        self.option_add("*Font", self.font)

        self.queue = queue.Queue()
        self.current_results = None
        # Config path for persisting last-used printer (per-user, macOS Application Support)
        app_support_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "sarasota_scraper")
        try:
            os.makedirs(app_support_dir, exist_ok=True)
        except Exception:
            pass
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
        # Bind Return key to start search
        self.entry.bind('<Return>', lambda e: self.start_search())

        self.search_btn = ttk.Button(row1, text="Search", command=self.start_search)
        self.search_btn.pack(side=tk.LEFT, padx=6)

        # Row 2: Action buttons (Save, Clear Screen, Print)
        row2 = ttk.Frame(self)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))

        # Save button: explicitly label to indicate it saves to Downloads
        self.save_btn = ttk.Button(row2, text="Save to Downloads", command=self.save_results)
        self.save_btn.pack(side=tk.LEFT, padx=6)
        self.save_btn.state(["disabled"])

        # Clear screen button on its own row so it's always visible
        self.clear_btn = ttk.Button(row2, text="Clear Screen", command=self.clear_screen)
        self.clear_btn.pack(side=tk.LEFT, padx=6)

        # Print button
        self.print_btn = ttk.Button(row2, text="Print", command=self.print_results)
        self.print_btn.pack(side=tk.LEFT, padx=6)
        self.print_btn.state(["disabled"])

        # ScrolledText is a tk widget; set font explicitly to ensure scaling
        self.log = ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, font=self.font)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

    def append_log(self, text):
        self.log.configure(state=tk.NORMAL)
        # Insert new logs at the top so newest entries are first
        try:
            self.log.insert('1.0', text)
            # Keep view pinned to top so new entries are visible
            self.log.yview_moveto(0.0)
        except Exception:
            # Fallback to append
            self.log.insert(tk.END, text)
            self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def start_search(self):
        street = self.entry.get().strip()
        if not street:
            return

        # Disable buttons while running
        self.search_btn.state(["disabled"])
        self.save_btn.state(["disabled"])
        self.current_results = None

        worker = threading.Thread(target=self._run_search_thread, args=(street,), daemon=True)
        worker.start()

    def _run_search_thread(self, street):
        # Redirect stdout for the duration so print() inside scraper goes to the GUI
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

        # Send results object to the main thread
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
                    # Re-enable the Search button so user can run another query
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

        # Re-schedule
        self.after(100, self._poll_queue)

    def save_results(self):
        if not self.current_results:
            self.append_log("\nNo results to save.\n")
            return
        # Auto-save directly to the user's Downloads folder on macOS
        downloads_dir = os.path.expanduser("~/Downloads")
        try:
            os.makedirs(downloads_dir, exist_ok=True)
        except Exception:
            pass

        base_name = self.entry.get().strip().replace(' ', '_').upper() or 'RESULTS'
        name, ext = f"{base_name}_results", '.csv'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(downloads_dir, f"{name}_{ts}{ext}")

        try:
            # Run save in a thread to avoid blocking briefly
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
        # Clear the log text and reset in-memory results
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.current_results = None
        try:
            self.save_btn.state(["disabled"])
        except Exception:
            pass
        try:
            self.print_btn.state(["disabled"])
        except Exception:
            pass

    def print_results(self):
        if not self.current_results:
            self.append_log("\nNo results to print.\n")
            return

        # Ask user to choose a printer first (runs on main thread)
        printer = self._choose_printer()
        if not printer:
            self.append_log("\nPrint cancelled (no printer selected).\n")
            return

        # Start print in background to avoid blocking UI
        t = threading.Thread(target=self._print_thread, args=(self.current_results, printer), daemon=True)
        t.start()

    def _choose_printer(self):
        # Try to enumerate printers using lpstat
        try:
            proc = subprocess.run(["/usr/bin/lpstat", "-p"], capture_output=True, text=True)
            out = proc.stdout
            printers = []
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == 'printer':
                    printers.append(parts[1])
        except Exception:
            printers = []

        if not printers:
            # No printers found
            self.append_log("\nNo printers found on system (lpstat returned none).\n")
            return None
        # Dialog to choose printer
        dlg = tk.Toplevel(self)
        dlg.title("Select Printer")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text="Choose printer:").pack(padx=12, pady=(12,6))
        # Use persisted last_printer if available and present in the current list
        default = printers[0]
        if hasattr(self, 'last_printer') and self.last_printer in printers:
            default = self.last_printer
        printer_var = tk.StringVar(value=default)
        cmb = ttk.Combobox(dlg, values=printers, textvariable=printer_var, state="readonly")
        cmb.pack(fill=tk.X, padx=12, pady=(0,12))

        selected = {"printer": None}

        def on_ok():
            selected["printer"] = printer_var.get()
            # Persist the choice
            try:
                self._save_last_printer(selected["printer"])
            except Exception:
                pass
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0,12))
        ttk.Button(btn_frame, text="Print", command=on_ok).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=8)

        self.wait_window(dlg)
        return selected["printer"]

    def _print_thread(self, results, printer=None):
        try:
            # Create a temporary text file with a readable representation of the results
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tf:
                filename = tf.name
                tf.write('Sarasota Scraper Results\n')
                tf.write(f'Generated: {datetime.now().isoformat()}\n\n')
                for rec in results:
                    # Write each dict on its own line in a readable format
                    line = ', '.join(f"{k}: {v}" for k, v in rec.items())
                    tf.write(line + "\n")

            # Call macOS printing utility `lpr`
            cmd = ["/usr/bin/lpr"]
            if printer:
                cmd += ["-P", printer]
            cmd.append(filename)
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                self.queue.put(("LOG", f"\nSent to printer (via lpr): {filename}\n"))
            else:
                self.queue.put(("LOG", f"\nPrinting failed: {proc.returncode} {proc.stderr}\n"))
        except Exception as e:
            self.queue.put(("LOG", f"\nError during printing: {e}\n"))
        finally:
            # Attempt to remove the temp file
            try:
                if os.path.exists(filename):
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
