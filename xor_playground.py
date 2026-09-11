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
import json
import platform

# Import the license module from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license import generate_license, validate_license, get_expiration_date
from hardware import get_hardware_id

# Default secret key — must match the one in backend/server.py
DEFAULT_SECRET_KEY = 0x504545504552C0DE


class LicenseGeneratorApp:
    """Main GUI application for generating Sedgwick license keys."""

    def __init__(self, root):
        self.root = root
        self.root.title("Sedgwick License Generator")
        self.root.geometry("850x750")
        self.root.minsize(700, 600)
        self.root.configure(bg="#f5f5f5")

        self.secret_key = DEFAULT_SECRET_KEY
        self.generated_licenses = []  # History of generated licenses
        
        # Create log file in the same folder as this tool (portable for thumb drive)
        self.log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                     "license_generator.log")

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
        ttk.Label(main_frame, text="Sedgwick License Generator",
                  style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(main_frame, text="Generate hardware-bound license keys for Sedgwick",
                  style="Subtitle.TLabel").pack(anchor=tk.W, pady=(0, 15))

        # ── Single License Generation ──
        gen_frame = ttk.LabelFrame(main_frame, text="  Generate License  ",
                                   style="Section.TLabelframe", padding=15)
        gen_frame.pack(fill=tk.X, pady=(0, 10))

        # Hardware ID
        hw_frame = ttk.Frame(gen_frame)
        hw_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(hw_frame, text="Hardware ID:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.hw_id_var = tk.StringVar()
        hw_entry = ttk.Entry(hw_frame, textvariable=self.hw_id_var, width=50,
                             font=("Courier", 11))
        hw_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(hw_frame, text="Paste", style="Action.TButton",
                   command=self._paste_hardware_id).pack(side=tk.LEFT, padx=(0, 2))

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

        # Secret Key (collapsible / advanced)
        adv_frame = ttk.Frame(gen_frame)
        adv_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(adv_frame, text="Secret Key:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.secret_var = tk.StringVar(value=f"0x{DEFAULT_SECRET_KEY:016X}")
        secret_entry = ttk.Entry(adv_frame, textvariable=self.secret_var, width=25,
                                 font=("Courier", 11))
        secret_entry.pack(side=tk.LEFT, padx=(5, 10))
        ttk.Label(adv_frame, text="(must match server config)",
                  foreground="#999").pack(side=tk.LEFT)

        # Generate Button
        btn_frame = ttk.Frame(gen_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="⚡ Generate License Key", style="Generate.TButton",
                   command=self._generate_license).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="🖥️ License This Machine", style="Generate.TButton",
                   command=self._license_this_machine).pack(side=tk.LEFT)

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
        columns = ("timestamp", "hardware_id", "expiration", "license_key")
        self.history_tree = ttk.Treeview(hist_frame, columns=columns, show="headings",
                                         height=6)
        self.history_tree.heading("timestamp", text="Generated At")
        self.history_tree.heading("hardware_id", text="Hardware ID (first 16)")
        self.history_tree.heading("expiration", text="Expiration")
        self.history_tree.heading("license_key", text="License Key")

        self.history_tree.column("timestamp", width=150, minwidth=120)
        self.history_tree.column("hardware_id", width=180, minwidth=140)
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

    def _license_this_machine(self):
        """License the current machine with a single click - complete one-step process."""
        try:
            # Get hardware ID
            hw_id = get_hardware_id()
            self.hw_id_var.set(hw_id)
            
            # Set expiration to 1 year from now
            exp_date = datetime.now() + timedelta(days=365)
            exp_date = exp_date.replace(hour=23, minute=59, second=59)
            exp_str = exp_date.strftime("%Y-%m-%d")
            self.exp_var.set(exp_str)
            
            # Parse secret key
            secret = self._parse_secret_key()
            if secret is None:
                return
            
            # Generate license
            try:
                license_key = generate_license(hw_id, exp_date, secret)
            except Exception as e:
                messagebox.showerror("Generation Error", f"Failed to generate license:\n{e}")
                return
            
            # Display the key
            self.result_var.set(license_key)

            # Add to history
            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "hardware_id": hw_id,
                "expiration": exp_str,
                "license_key": license_key,
            }
            self.generated_licenses.append(record)
            self.history_tree.insert("", 0, values=(
                record["timestamp"],
                hw_id[:16] + "…" if len(hw_id) > 16 else hw_id,
                exp_str,
                license_key,
            ))

            # Log to file
            self._log_license(record)

            # Write license.key to Peeper's per-user application data folder.
            try:
                appdata = os.path.expandvars(r"%APPDATA%")
                peeper_dir = os.path.join(appdata, "Peeper")
                os.makedirs(peeper_dir, exist_ok=True)
                key_file = os.path.join(peeper_dir, "license.key")
                with open(key_file, "w") as f:
                    f.write(license_key)
                self.status_var.set(f"✓ Machine licensed! Expires {exp_str}  —  Key installed to AppData")
            except Exception as e:
                self.status_var.set(f"✓ Key generated but could not save to AppData: {e}")
            self.status_label.configure(style="Success.TLabel")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to license this machine:\n{e}")

    def _parse_secret_key(self):
        """Parse the secret key from the UI field."""
        raw = self.secret_var.get().strip()
        try:
            if raw.startswith("0x") or raw.startswith("0X"):
                return int(raw, 16)
            return int(raw)
        except ValueError:
            messagebox.showerror("Invalid Secret Key",
                                 "Secret key must be a valid integer or hex (0x...) value.")
            return None

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

        # Generate
        try:
            license_key = generate_license(hw_id, exp_date, secret)
        except Exception as e:
            messagebox.showerror("Generation Error", f"Failed to generate license:\n{e}")
            return

        self.result_var.set(license_key)
        self.status_var.set(f"Key generated for expiration {exp_str}")
        self.status_label.configure(style="Success.TLabel")

        # Add to history
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hardware_id": hw_id,
            "expiration": exp_str,
            "license_key": license_key,
        }
        self.generated_licenses.append(record)
        self.history_tree.insert("", 0, values=(
            record["timestamp"],
            hw_id[:16] + "…" if len(hw_id) > 16 else hw_id,
            exp_str,
            license_key,
        ))
        
        # Log to file
        self._log_license(record)

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
            initialfile=f"segdwick_licenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "hardware_id",
                                                        "expiration", "license_key"])
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
            initialfile=f"segdwick_licenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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

    def _log_license(self, record):
        """Log license generation to the log file."""
        try:
            # Collect machine information
            machine_info = {
                "hostname": platform.node(),
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            }
            
            # Format log entry
            log_entry = (
                f"\n{'='*80}\n"
                f"Timestamp: {record['timestamp']}\n"
                f"Machine: {machine_info['hostname']} ({machine_info['system']} {machine_info['machine']})\n"
                f"Hardware ID: {record['hardware_id']}\n"
                f"License Key: {record['license_key']}\n"
                f"Expiration: {record['expiration']}\n"
                f"{'='*80}\n"
            )
            
            # Append to log file
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Warning: Failed to write to log file: {e}")


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
