import os
import threading
import time
from typing import List

from dotenv import load_dotenv
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from cloudflare_client import CloudflareClient, CloudflareAPIError


MAX_BATCH = 10


def load_credentials():
    load_dotenv()
    token = os.getenv("CLOUDFLARE_API_TOKEN")
    email = os.getenv("CLOUDFLARE_EMAIL")
    api_key = os.getenv("CLOUDFLARE_API_KEY")
    if not token and not (email and api_key):
        return None, None, None
    return token, email, api_key


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Cloudflare Bulk Domain Deleter")
        self.root.geometry("900x650")

        self.token, self.email, self.api_key = load_credentials()
        self.client = None
        try:
            if self.token or (self.email and self.api_key):
                self.client = CloudflareClient(
                    api_token=self.token, email=self.email, api_key=self.api_key
                )
        except Exception as e:
            self.client = None

        self._build_ui()

        if self.client is None:
            messagebox.showwarning(
                "Secrets missing",
                "Cloudflare credentials are not set.\n\nPlease create a .env file from .env.example and provide either:\n- CLOUDFLARE_API_TOKEN (recommended), or\n- CLOUDFLARE_EMAIL + CLOUDFLARE_API_KEY (legacy)\n\nThen restart the app.",
            )

    def _build_ui(self) -> None:
        # Frame for input
        input_frame = ttk.LabelFrame(self.root, text="Domains Input")
        input_frame.pack(fill=tk.X, padx=12, pady=10)

        lbl = ttk.Label(
            input_frame,
            text=f"Enter up to {MAX_BATCH} domains to delete (one per line):",
        )
        lbl.pack(anchor=tk.W, padx=10, pady=(8, 4))

        self.domains_text = tk.Text(input_frame, height=8, font=("Consolas", 11))
        self.domains_text.pack(fill=tk.X, padx=10, pady=(0, 8))

        controls = ttk.Frame(input_frame)
        controls.pack(fill=tk.X, padx=10, pady=(0, 8))

        self.delete_btn = ttk.Button(controls, text="DELETE", command=self.on_delete)
        self.delete_btn.pack(side=tk.LEFT)

        self.count_label = ttk.Label(controls, text="0 domains queued")
        self.count_label.pack(side=tk.LEFT, padx=12)

        self.domains_text.bind("<KeyRelease>", self._on_domains_change)

        # Progress
        progress_frame = ttk.LabelFrame(self.root, text="Progress")
        progress_frame.pack(fill=tk.X, padx=12, pady=10)

        self.progress = ttk.Progressbar(
            progress_frame, orient=tk.HORIZONTAL, length=400, mode="determinate"
        )
        self.progress.pack(fill=tk.X, padx=10, pady=8)

        self.progress_label = ttk.Label(progress_frame, text="Waiting to start...")
        self.progress_label.pack(anchor=tk.W, padx=10, pady=(0, 8))

        # Logs
        log_frame = ttk.LabelFrame(self.root, text="Logs")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.log = ScrolledText(log_frame, height=18, state=tk.DISABLED, font=("Consolas", 10))
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    def _on_domains_change(self, event=None):
        domains = self._parse_domains(self.domains_text.get("1.0", tk.END))
        self.count_label.configure(text=f"{len(domains)} domains queued")

    @staticmethod
    def _parse_domains(text: str) -> List[str]:
        items = [line.strip() for line in text.splitlines()]
        items = [x for x in items if x]
        # Remove duplicates, preserve order
        seen = set()
        out: List[str] = []
        for x in items:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def on_delete(self):
        domains = self._parse_domains(self.domains_text.get("1.0", tk.END))
        if not domains:
            messagebox.showinfo("No domains", "Please enter at least one domain.")
            return
        if len(domains) > MAX_BATCH:
            messagebox.showwarning(
                "Too many domains",
                f"You entered {len(domains)} domains. Please limit to {MAX_BATCH} at a time.",
            )
            return
        if self.client is None:
            messagebox.showerror(
                "Missing credentials",
                "Cloudflare credentials are missing. Create your .env first.",
            )
            return

        confirm = messagebox.askyesno(
            "Confirm deletion",
            f"You are about to DELETE {len(domains)} domain(s). This is irreversible.\n\nProceed?",
        )
        if not confirm:
            return

        # Disable inputs during processing
        self.delete_btn.configure(state=tk.DISABLED)
        self.domains_text.configure(state=tk.DISABLED)

        self.progress.configure(value=0, maximum=len(domains))
        self.progress_label.configure(text="Starting...")
        self._clear_log()
        self._log("Starting bulk deletion...")

        t = threading.Thread(target=self._delete_worker, args=(domains,), daemon=True)
        t.start()

    def _delete_worker(self, domains: List[str]):
        start = time.time()
        completed = 0
        for idx, domain in enumerate(domains, start=1):
            t0 = time.time()
            self._log(f"[{idx}/{len(domains)}] Looking up zone for '{domain}'...")
            try:
                zone = self.client.get_zone_by_name(domain)
                if not zone:
                    self._log(f"  - Not found. Skipping.")
                    # Progress will be updated in finally
                    continue
                zone_id = zone.get("id")
                self._log(f"  - Found zone id: {zone_id}. Deleting...")
                ok, msg = self.client.delete_zone(zone_id)
                if ok:
                    self._log("  - Deleted successfully.")
                else:
                    self._log(f"  - Failed to delete: {msg}")
            except CloudflareAPIError as e:
                self._log(f"  - API error: {e}")
            except Exception as e:
                self._log(f"  - Unexpected error: {e}")
            finally:
                completed += 1
                self._update_progress(completed, len(domains), start)
                # Small pacing delay to be gentle on rate limits
                elapsed = time.time() - t0
                if elapsed < 1.0:
                    time.sleep(1.0 - elapsed)

        self._log("All done.")
        self.root.after(0, lambda: self.progress_label.configure(text="Completed"))
        self.root.after(0, lambda: self.delete_btn.configure(state=tk.NORMAL))
        self.root.after(0, lambda: self.domains_text.configure(state=tk.NORMAL))

    def _clear_log(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.root.after(0, self._append_log, f"[{timestamp}] {message}\n")

    def _append_log(self, text: str):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _update_progress(self, completed: int, total: int, start_time: float):
        self.root.after(0, self.progress.configure, {"value": completed})
        # ETA
        if completed > 0:
            elapsed = time.time() - start_time
            per_item = elapsed / completed
            remaining = max(total - completed, 0)
            eta = int(per_item * remaining)
            eta_str = time.strftime("%M:%S", time.gmtime(eta))
            status = f"{completed}/{total} completed. ETA: {eta_str}"
        else:
            status = f"0/{total} completed."
        self.root.after(0, lambda: self.progress_label.configure(text=status))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
