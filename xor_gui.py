#!/usr/bin/env python3
"""
Sedgwick License Generator Tool
================================
A GUI tool for generating and managing license keys for Sedgwick.

Generates hardware-bound, time-limited license keys that can be
distributed to customers for activation within the application.

Usage:
    python3 license_generator.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
from datetime import datetime, timedelta
import csv
import hashlib
import json

# Import the license module from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xor_core import xor_encode as generate_license, xor_validate as validate_license, get_ttl_date as get_expiration_date

OLD_SECRET_KEY = 0x1234567890ABCDEF
SPECTATOR_SECRET_PHRASE = "nlc-spectator-license-secret-v2"
SPECTATOR_SECRET_KEY = int.from_bytes(hashlib.sha256(SPECTATOR_SECRET_PHRASE.encode("utf-8")).digest()[:8], "big")

PRODUCTS = {
    "Sedgwick (old key)": {
        "product": "Sedgwick",
        "secret": OLD_SECRET_KEY,
        "hint": "Existing tool / old secret key",
    },
    "NLC Spectator (new key)": {
        "product": "NLC Spectator",
        "secret": SPECTATOR_SECRET_KEY,
        "hint": "Spectator secret phrase includes 'spectator'",
    },
}


class LicenseGeneratorApp:
    """Main GUI application for generating licenses for supported tools."""

    def __init__(self, root):
        self.root = root
        self.root.title("NLC License Generator")
        self.root.geometry("820x720")
        self.root.minsize(700, 600)
        self.root.configure(bg="#f5f5f5")

        self.generated_licenses = []  # History of generated licenses

        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Custom styles
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"),
                        background="#f5f5f5", foreground="#333")
        style.configure("Subtitle.TLabel", font=("Helvetica", 10),
                        background="#f5f5f5", foreground="#666")
        style.configure("Section.TLabelframe.Label", font=("Helvetica", 12, "bold"))
        style.configure("TLabelframe", background="#f5f5f5")
        style.configure("TLabel", background="#f5f5f5")
        style.configure("TFrame", background="#f5f5f5")
        style.configure("Generate.TButton", font=("Helvetica", 12, "bold"),
                        padding=(20, 10))
        style.configure("Action.TButton", font=("Helvetica", 10), padding=(10, 5))
        style.configure("Success.TLabel", foreground="#155724", background="#d4edda",
                        font=("Helvetica", 11, "bold"), padding=5)
        style.configure("Error.TLabel", foreground="#721c24", background="#f8d7da",
                        font=("Helvetica", 11), padding=5)

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── Header ──
        ttk.Label(main_frame, text="NLC License Generator",
                  style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(main_frame, text="Generate hardware-bound license keys for supported tools",
                  style="Subtitle.TLabel").pack(anchor=tk.W, pady=(0, 15))

        # ── Single License Generation ──
        gen_frame = ttk.LabelFrame(main_frame, text="  Generate License  ",
                                   style="Section.TLabelframe", padding=15)
        gen_frame.pack(fill=tk.X, pady=(0, 10))

        # Product / secret selection
        product_frame = ttk.Frame(gen_frame)
        product_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(product_frame, text="Tool:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.product_var = tk.StringVar(value="NLC Spectator (new key)")
        product_select = ttk.Combobox(
            product_frame,
            textvariable=self.product_var,
            values=list(PRODUCTS.keys()),
            state="readonly",
            width=28,
        )
        product_select.pack(side=tk.LEFT, padx=(5, 10))
        product_select.bind("<<ComboboxSelected>>", lambda _event: self._on_product_change())
        self.product_hint_var = tk.StringVar()
        ttk.Label(product_frame, textvariable=self.product_hint_var, foreground="#666").pack(side=tk.LEFT)

        # Hardware ID
        hw_frame = ttk.Frame(gen_frame)
        hw_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(hw_frame, text="Hardware ID:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.hw_id_var = tk.StringVar()
        hw_entry = ttk.Entry(hw_frame, textvariable=self.hw_id_var, width=70,
                             font=("Courier", 11))
        hw_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(hw_frame, text="Paste", style="Action.TButton",
                   command=self._paste_hardware_id).pack(side=tk.LEFT)

        # Expiration Date
        exp_frame = ttk.Frame(gen_frame)
        exp_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(exp_frame, text="Expiration:", width=15, anchor=tk.W).pack(side=tk.LEFT)

        self.exp_var = tk.StringVar()
        exp_entry = ttk.Entry(exp_frame, textvariable=self.exp_var, width=15,
                              font=("Courier", 11))
        exp_entry.pack(side=tk.LEFT, padx=(5, 10))

        # Quick-set duration buttons
        ttk.Label(exp_frame, text="Quick set:").pack(side=tk.LEFT, padx=(10, 5))
        for label, days in [("30 days", 30), ("90 days", 90), ("1 year", 365),
                            ("2 years", 730), ("5 years", 1825)]:
            ttk.Button(exp_frame, text=label,
                       command=lambda d=days: self._set_expiration_days(d)).pack(
                side=tk.LEFT, padx=2)

        # Set default expiration to 1 year from now
        self._set_expiration_days(365)

        # Selected Secret Key (read-only)
        adv_frame = ttk.Frame(gen_frame)
        adv_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(adv_frame, text="Secret Key:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.secret_var = tk.StringVar()
        secret_entry = ttk.Entry(adv_frame, textvariable=self.secret_var, width=25,
                     font=("Courier", 11), state="readonly")
        secret_entry.pack(side=tk.LEFT, padx=(5, 10))
        ttk.Label(adv_frame, text="selected by tool above",
                  foreground="#999").pack(side=tk.LEFT)
        self._on_product_change()

        # Generate Button
        btn_frame = ttk.Frame(gen_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="⚡ Generate License Key", style="Generate.TButton",
                   command=self._generate_license).pack(side=tk.LEFT)

        # ── Result Area ──
        result_frame = ttk.LabelFrame(main_frame, text="  Generated Key  ",
                                      style="Section.TLabelframe", padding=15)
        result_frame.pack(fill=tk.X, pady=(0, 10))

        self.result_var = tk.StringVar(value="—")
        result_entry = ttk.Entry(result_frame, textvariable=self.result_var,
                                 font=("Courier", 16, "bold"), justify=tk.CENTER,
                                 state="readonly")
        result_entry.pack(fill=tk.X, pady=(0, 8))

        res_btn_frame = ttk.Frame(result_frame)
        res_btn_frame.pack()
        ttk.Button(res_btn_frame, text="📋 Copy to Clipboard", style="Action.TButton",
                   command=self._copy_to_clipboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(res_btn_frame, text="✅ Verify Key", style="Action.TButton",
                   command=self._verify_license).pack(side=tk.LEFT, padx=5)

        # Status message
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(result_frame, textvariable=self.status_var,
                                      anchor=tk.CENTER)
        self.status_label.pack(fill=tk.X, pady=(8, 0))

        # ── License History ──
        hist_frame = ttk.LabelFrame(main_frame, text="  License History  ",
                                    style="Section.TLabelframe", padding=10)
        hist_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Treeview for history
        columns = ("timestamp", "product", "hardware_id", "expiration", "license_key")
        self.history_tree = ttk.Treeview(hist_frame, columns=columns, show="headings",
                                         height=6)
        self.history_tree.heading("timestamp", text="Generated At")
        self.history_tree.heading("product", text="Tool")
        self.history_tree.heading("hardware_id", text="Hardware ID (first 16)")
        self.history_tree.heading("expiration", text="Expiration")
        self.history_tree.heading("license_key", text="License Key")

        self.history_tree.column("timestamp", width=145, minwidth=120)
        self.history_tree.column("product", width=120, minwidth=100)
        self.history_tree.column("hardware_id", width=160, minwidth=140)
        self.history_tree.column("expiration", width=100, minwidth=80)
        self.history_tree.column("license_key", width=200, minwidth=160)

        scrollbar = ttk.Scrollbar(hist_frame, orient=tk.VERTICAL,
                                  command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # History action buttons
        hist_btn_frame = ttk.Frame(main_frame)
        hist_btn_frame.pack(fill=tk.X)
        ttk.Button(hist_btn_frame, text="Export History (CSV)", style="Action.TButton",
                   command=self._export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(hist_btn_frame, text="Export History (JSON)", style="Action.TButton",
                   command=self._export_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(hist_btn_frame, text="Clear History", style="Action.TButton",
                   command=self._clear_history).pack(side=tk.RIGHT, padx=5)

        # ── Keyboard shortcuts ──
        self.root.bind("<Command-g>", lambda e: self._generate_license())
        self.root.bind("<Command-c>", lambda e: self._copy_to_clipboard())
        self.root.bind("<Command-v>", lambda e: self._paste_hardware_id())

    # ── Actions ────────────────────────────────────────────────────

    def _set_expiration_days(self, days):
        """Set expiration date to N days from today."""
        exp = datetime.now() + timedelta(days=days)
        self.exp_var.set(exp.strftime("%Y-%m-%d"))

    def _paste_hardware_id(self):
        """Paste clipboard content into the hardware ID field."""
        try:
            clipboard = self.root.clipboard_get().strip()
            self.hw_id_var.set(clipboard)
        except tk.TclError:
            pass

    def _selected_config(self):
        return PRODUCTS.get(self.product_var.get(), PRODUCTS["NLC Spectator (new key)"])

    def _on_product_change(self):
        config = self._selected_config()
        self.secret_var.set(f"0x{config['secret']:016X}")
        self.product_hint_var.set(config["hint"])

    def _parse_secret_key(self):
        """Return the secret key selected by the tool dropdown."""
        return self._selected_config()["secret"]

    def _generate_license(self):
        """Generate a license key from the current inputs."""
        hw_id = self.hw_id_var.get().strip()
        if not hw_id:
            messagebox.showwarning("Missing Hardware ID",
                                   "Please enter the customer's Hardware ID.")
            return

        exp_str = self.exp_var.get().strip()
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
            exp_date = exp_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 "Expiration date must be in YYYY-MM-DD format.")
            return

        if exp_date < datetime.now():
            if not messagebox.askyesno("Past Expiration",
                                       "The expiration date is in the past.\n"
                                       "Generate anyway?"):
                return

        secret = self._parse_secret_key()
        if secret is None:
            return
        config = self._selected_config()
        product_name = config["product"]

        # Generate
        try:
            license_key = generate_license(hw_id, exp_date, secret)
        except Exception as e:
            messagebox.showerror("Generation Error", f"Failed to generate license:\n{e}")
            return

        self.result_var.set(license_key)
        self.status_var.set(f"{product_name} key generated for expiration {exp_str}")
        self.status_label.configure(style="Success.TLabel")

        # Add to history
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "product": product_name,
            "hardware_id": hw_id,
            "expiration": exp_str,
            "license_key": license_key,
            "secret_key": f"0x{secret:016X}",
        }
        self.generated_licenses.append(record)
        self.history_tree.insert("", 0, values=(
            record["timestamp"],
            record["product"],
            hw_id[:16] + "…" if len(hw_id) > 16 else hw_id,
            exp_str,
            license_key,
        ))

    def _copy_to_clipboard(self):
        """Copy the generated license key to the clipboard."""
        key = self.result_var.get()
        if not key or key == "—":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(key)
        self.status_var.set("Copied to clipboard!")
        self.status_label.configure(style="Success.TLabel")

    def _verify_license(self):
        """Verify the generated key against the current inputs."""
        key = self.result_var.get()
        if not key or key == "—":
            messagebox.showinfo("No Key", "Generate a key first.")
            return

        hw_id = self.hw_id_var.get().strip()
        if not hw_id:
            messagebox.showwarning("Missing Hardware ID",
                                   "Enter a Hardware ID to verify against.")
            return

        secret = self._parse_secret_key()
        if secret is None:
            return

        is_valid = validate_license(key, hw_id, secret)
        if is_valid:
            exp = get_expiration_date(key, secret)
            self.status_var.set(f"✅ VALID — Expires {exp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.status_label.configure(style="Success.TLabel")
        else:
            self.status_var.set("❌ INVALID — Key does not match hardware ID or is expired")
            self.status_label.configure(style="Error.TLabel")

    # ── Export / History ───────────────────────────────────────────

    def _export_csv(self):
        """Export license history to CSV."""
        if not self.generated_licenses:
            messagebox.showinfo("Empty History", "No licenses to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Export Licenses as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"nlc_licenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "product", "hardware_id",
                                                        "expiration", "license_key", "secret_key"])
                writer.writeheader()
                writer.writerows(self.generated_licenses)
            self.status_var.set(f"Exported {len(self.generated_licenses)} licenses to CSV")
            self.status_label.configure(style="Success.TLabel")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV:\n{e}")

    def _export_json(self):
        """Export license history to JSON."""
        if not self.generated_licenses:
            messagebox.showinfo("Empty History", "No licenses to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Export Licenses as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"nlc_licenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        if not path:
            return

        try:
            with open(path, "w") as f:
                json.dump(self.generated_licenses, f, indent=2)
            self.status_var.set(f"Exported {len(self.generated_licenses)} licenses to JSON")
            self.status_label.configure(style="Success.TLabel")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export JSON:\n{e}")

    def _clear_history(self):
        """Clear the license generation history."""
        if not self.generated_licenses:
            return
        if messagebox.askyesno("Clear History",
                               "Clear all license generation history?"):
            self.generated_licenses.clear()
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            self.status_var.set("History cleared")
            self.status_label.configure(style="Success.TLabel")


def main():
    root = tk.Tk()

    # macOS-specific styling
    if sys.platform == "darwin":
        try:
            root.tk.call("::tk::unsupported::MacWindowStyle", "style",
                         root._w, "document", "closeBox collapseBox")
        except tk.TclError:
            pass

    app = LicenseGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
