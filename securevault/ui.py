"""
ui.py
-----
DeepStore macOS Password Manager Interface
- macOS Yellow + Graphite aesthetics
- Responsive animations & Toast notification feedback
- Reorganized card layout: Show/Hide toggle at top, twin Copy buttons at bottom
- Complete in-app Passkey & Biometric settings, Master Key rotation, Auto-lock & Clipboard security
"""

import time
import secrets
import string
from typing import Optional, Set
import customtkinter as ctk
from tkinter import messagebox

from . import storage
from . import crypto_utils
from . import biometrics

# ---------------- Design System: Colors & Typography ----------------
FONT_FAMILY = "SF Pro Display"
MONO_FONT = "SF Mono"

# macOS Yellow Accent Palette
ACCENT_COLOR = "#F5C518"       # Vibrant macOS Golden Yellow
ACCENT_HOVER = "#E5B510"       # Darker gold on hover
ACCENT_ACTIVE = "#CCA00E"      # Deep gold
ACCENT_TEXT = "#1C1C1E"        # Crisp dark text on yellow
ACCENT_SUBTLE = ("#FEF3C7", "#3D3519")  # Soft pastel yellow / dark graphite gold tint

# macOS Graphite & Dark/Light Surfaces
BG_COLOR = ("#F2F2F7", "#141416")
CARD_BG = ("#FFFFFF", "#202024")
CARD_HOVER_BG = ("#F8F8FA", "#28282E")
BORDER_COLOR = ("#E5E5EA", "#2E2E36")
BORDER_HIGHLIGHT = ("#D1D1D6", "#454552")
TEXT_PRIMARY = ("#1C1C1E", "#F5F5F7")
TEXT_SECONDARY = ("#8E8E93", "#9E9EA8")
TEXT_MUTED = ("#AEAEB2", "#636366")
DANGER_COLOR = "#FF453A"
DANGER_HOVER = "#D9382F"
SUCCESS_COLOR = "#30D158"

GRID_COLS = 3
GRID_ROWS = 3
PAGE_SIZE = GRID_COLS * GRID_ROWS


def gen_password(length: int = 20, use_special: bool = True) -> str:
    """Generate high-entropy password."""
    chars = string.ascii_letters + string.digits
    if use_special:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    # Ensure at least 1 uppercase, 1 lowercase, 1 digit, 1 special
    pwd = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*()-_=+") if use_special else secrets.choice(chars)
    ]
    pwd += [secrets.choice(chars) for _ in range(max(4, length) - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


class ToastNotification(ctk.CTkFrame):
    """Floating animated macOS-style toast banner."""
    def __init__(self, master, message: str, duration_ms: int = 3000, icon: str = "✓"):
        super().__init__(
            master,
            corner_radius=20,
            fg_color=("#1C1C1E", "#F5F5F7"),
            border_width=1,
            border_color=("#3A3A3C", "#E5E5EA")
        )
        self.master = master
        self.duration_ms = duration_ms

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(padx=16, pady=8)

        text_color = ("#F5F5F7", "#1C1C1E")
        ctk.CTkLabel(
            content,
            text=f"{icon}  {message}",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=text_color
        ).pack(side="left")

        # Placement near bottom center
        self.place(relx=0.5, rely=0.92, anchor="center")
        self.lift()

        # Fade out and destroy
        self.after(self.duration_ms, self.dismiss)

    def dismiss(self):
        try:
            self.destroy()
        except Exception:
            pass


class SecureVaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DeepStore — Encrypted Vault")
        self.geometry("1020x720")
        self.minsize(860, 600)
        self.configure(fg_color=BG_COLOR)

        self.key: Optional[bytes] = None
        self.data: Optional[dict] = None
        self.meta: dict = storage.load_meta()
        self.current_category = "All"
        self.page = 0
        self.category_edit_mode = False
        self.search_query = ""

        # Auto-lock & clipboard safety
        self.last_activity = time.time()
        self.clipboard_clear_job = None
        self.last_copied_val: Optional[str] = None
        self.auto_lock_job = None

        # Apply saved theme
        saved_theme = self.meta.get("theme", "System")
        ctk.set_appearance_mode(saved_theme)

        # Main container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Activity listeners for auto-lock
        self.bind_all("<Any-KeyPress>", self._on_user_activity)
        self.bind_all("<Motion>", self._on_user_activity)
        self.bind_all("<Button-1>", self._on_user_activity)

        self._start_auto_lock_checker()
        self.show_login()

    def _on_user_activity(self, event=None):
        self.last_activity = time.time()

    def _start_auto_lock_checker(self):
        self._check_auto_lock()

    def _check_auto_lock(self):
        if self.key is not None:
            timeout_min = self.meta.get("auto_lock_minutes", 5)
            if timeout_min > 0:
                elapsed = time.time() - self.last_activity
                if elapsed >= (timeout_min * 60):
                    self.lock("Auto-locked due to inactivity.")
                    return
        self.auto_lock_job = self.after(5000, self._check_auto_lock)

    # ---------------- Navigation ----------------

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_login(self, notice: str = ""):
        self.clear_container()
        login = LoginFrame(self.container, self, initial_notice=notice)
        login.pack(fill="both", expand=True)

    def show_vault(self):
        self.clear_container()
        self.vault_frame = VaultFrame(self.container, self)
        self.vault_frame.pack(fill="both", expand=True)

    def lock(self, reason: str = ""):
        # Zero out sensitive data from memory
        self.key = None
        self.data = None
        self.clear_clipboard_safely()
        self.show_login(notice=reason)

    # ---------------- Persistence & Security ----------------

    def save(self):
        if self.key and self.data:
            storage.save_data(self.data, self.key)

    def copy_to_clipboard(self, text: str, label: str = "Item"):
        """Copies to clipboard with auto-clear security timer and toast feedback."""
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.last_copied_val = text

        # Cancel any previous clear timer
        if self.clipboard_clear_job:
            self.after_cancel(self.clipboard_clear_job)
            self.clipboard_clear_job = None

        clear_seconds = self.meta.get("clipboard_clear_seconds", 30)
        if clear_seconds > 0:
            self.clipboard_clear_job = self.after(clear_seconds * 1000, self._auto_clear_clipboard)
            ToastNotification(
                self,
                f"{label} copied! (Clearing in {clear_seconds}s)",
                duration_ms=2500,
                icon="📋"
            )
        else:
            ToastNotification(self, f"{label} copied to clipboard!", duration_ms=2000, icon="📋")

    def _auto_clear_clipboard(self):
        try:
            current = self.clipboard_get()
            if current == self.last_copied_val:
                self.clipboard_clear()
                self.last_copied_val = None
                ToastNotification(self, "Clipboard cleared for security.", duration_ms=2000, icon="🛡️")
        except Exception:
            pass

    def clear_clipboard_safely(self):
        if self.last_copied_val:
            try:
                self.clipboard_clear()
            except Exception:
                pass
            self.last_copied_val = None


class LoginFrame(ctk.CTkFrame):
    """Refined macOS unlock / vault setup view."""
    def __init__(self, master, app: SecureVaultApp, initial_notice: str = ""):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.first_run = not storage.vault_exists()

        wrapper = ctk.CTkFrame(
            self,
            corner_radius=24,
            fg_color=CARD_BG,
            border_width=1,
            border_color=BORDER_COLOR
        )
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        pad = {"padx": 40, "pady": 8}

        # Clean Header
        title = "Create Master Passkey" if self.first_run else "Unlock DeepStore"
        ctk.CTkLabel(
            wrapper,
            text=title,
            font=(FONT_FAMILY, 24, "bold"),
            text_color=TEXT_PRIMARY
        ).grid(row=0, column=0, columnspan=2, pady=(36, 4))

        sub = ("Initialize your encrypted vault with a secure passkey."
               if self.first_run else "Enter your master passkey or use Touch ID.")
        ctk.CTkLabel(
            wrapper,
            text=sub,
            font=(FONT_FAMILY, 12),
            text_color=TEXT_SECONDARY
        ).grid(row=1, column=0, columnspan=2, pady=(0, 20), padx=30)

        # Inputs
        self.pw_entry = ctk.CTkEntry(
            wrapper,
            placeholder_text="Master passkey",
            show="•",
            width=300,
            height=40,
            corner_radius=10,
            border_color=BORDER_COLOR,
            fg_color=BG_COLOR
        )
        self.pw_entry.grid(row=2, column=0, columnspan=2, **pad)
        self.pw_entry.bind("<Return>", lambda e: self.submit())

        btn_row = 3
        if self.first_run:
            self.pw_entry.bind("<KeyRelease>", self._on_password_type)
            self.strength_label = ctk.CTkLabel(
                wrapper,
                text="Strength: Empty",
                font=(FONT_FAMILY, 11),
                text_color=TEXT_MUTED
            )
            self.strength_label.grid(row=3, column=0, columnspan=2, pady=(0, 4))

            self.pw_confirm = ctk.CTkEntry(
                wrapper,
                placeholder_text="Confirm master passkey",
                show="•",
                width=300,
                height=40,
                corner_radius=10,
                border_color=BORDER_COLOR,
                fg_color=BG_COLOR
            )
            self.pw_confirm.grid(row=4, column=0, columnspan=2, **pad)
            self.pw_confirm.bind("<Return>", lambda e: self.submit())
            btn_row = 5

        self.error_label = ctk.CTkLabel(
            wrapper,
            text=initial_notice,
            font=(FONT_FAMILY, 12),
            text_color=DANGER_COLOR if "lock" not in initial_notice.lower() else ACCENT_COLOR
        )
        self.error_label.grid(row=btn_row, column=0, columnspan=2, pady=4)

        action_text = "Create Vault" if self.first_run else "Unlock"
        self.submit_btn = ctk.CTkButton(
            wrapper,
            text=action_text,
            width=300,
            height=40,
            corner_radius=10,
            font=(FONT_FAMILY, 13, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=self.submit
        )
        self.submit_btn.grid(row=btn_row + 1, column=0, columnspan=2, padx=40, pady=(6, 12))

        # Touch ID / Biometrics button
        has_touch_id = biometrics.touch_id_available()
        touch_id_enabled = self.app.meta.get("touch_id_enabled", False)
        has_key_cached = biometrics.is_key_stored()

        if not self.first_run and has_touch_id and (touch_id_enabled or has_key_cached):
            self.touch_btn = ctk.CTkButton(
                wrapper,
                text="Touch ID Unlock",
                width=300,
                height=38,
                corner_radius=10,
                font=(FONT_FAMILY, 12),
                fg_color="transparent",
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY,
                hover_color=CARD_HOVER_BG,
                command=self.touch_id_unlock
            )
            self.touch_btn.grid(row=btn_row + 2, column=0, columnspan=2, padx=40, pady=(0, 10))

            # Helper to reset passkey cache if user is stuck
            ctk.CTkButton(
                wrapper,
                text="Clear cached passkey",
                font=(FONT_FAMILY, 11),
                text_color=TEXT_MUTED,
                fg_color="transparent",
                hover_color=CARD_HOVER_BG,
                command=self.clear_cached_passkey
            ).grid(row=btn_row + 3, column=0, columnspan=2, pady=(0, 20))
        else:
            ctk.CTkLabel(wrapper, text="").grid(row=btn_row + 2, column=0, pady=10)

        self.pw_entry.focus()

    def _on_password_type(self, event=None):
        if self.first_run and hasattr(self, "strength_label"):
            pw = self.pw_entry.get()
            score, label = crypto_utils.check_password_strength(pw)
            colors = [DANGER_COLOR, "#FF9500", "#FFCC00", "#34C759", SUCCESS_COLOR]
            self.strength_label.configure(
                text=f"Strength: {label}",
                text_color=colors[min(score, 4)]
            )

    def submit(self):
        password = self.pw_entry.get()
        if not password:
            self.error_label.configure(text="Please enter your master passkey.", text_color=DANGER_COLOR)
            return

        if self.first_run:
            confirm = self.pw_confirm.get()
            if len(password) < 8:
                self.error_label.configure(text="Passkey must be at least 8 characters.", text_color=DANGER_COLOR)
                return
            if password != confirm:
                self.error_label.configure(text="Passkeys do not match.", text_color=DANGER_COLOR)
                return
            try:
                key = storage.create_vault(password)
                self.app.key = key
                self.app.data = storage.load_data(key)
                self.maybe_offer_touch_id(key)
                self.app.show_vault()
            except Exception as e:
                self.error_label.configure(text=f"Setup error: {str(e)}", text_color=DANGER_COLOR)
        else:
            try:
                key = storage.unlock_vault(password)
                self.app.key = key
                self.app.data = storage.load_data(key)
                # If Touch ID is enabled, keep Keychain key in sync
                if self.app.meta.get("touch_id_enabled"):
                    biometrics.store_key(key)
                self.app.show_vault()
            except crypto_utils.WrongPassword:
                self.error_label.configure(text="Incorrect passkey.", text_color=DANGER_COLOR)
            except Exception as e:
                self.error_label.configure(text=f"Error: {str(e)}", text_color=DANGER_COLOR)

    def maybe_offer_touch_id(self, key: bytes):
        if not biometrics.touch_id_available():
            return
        if messagebox.askyesno(
            "Enable Touch ID / Passkey?",
            "Would you like to enable Touch ID to quickly unlock DeepStore?\n\n"
            "You can always change this in Settings at any time."
        ):
            biometrics.store_key(key)
            self.app.meta["touch_id_enabled"] = True
            storage.save_meta(self.app.meta)

    def touch_id_unlock(self):
        if hasattr(self, "touch_btn"):
            self.touch_btn.configure(state="disabled", text="Verifying Touch ID...")
        try:
            success = biometrics.authenticate_touch_id("Unlock DeepStore Vault", update_pump=self.app.update)
            if not success:
                self.error_label.configure(text="Touch ID cancelled or unverified. Use passkey.", text_color=DANGER_COLOR)
                return
            key = biometrics.retrieve_key()
            if not key:
                self.error_label.configure(text="No cached passkey found in Keychain. Use passkey.", text_color=DANGER_COLOR)
                return
            try:
                self.app.data = storage.load_data(key)
                self.app.key = key
                self.app.show_vault()
            except Exception:
                self.error_label.configure(
                    text="Cached passkey out of sync. Please unlock with master passkey.",
                    text_color=DANGER_COLOR
                )
        finally:
            if hasattr(self, "touch_btn") and self.touch_btn.winfo_exists():
                self.touch_btn.configure(state="normal", text="Touch ID Unlock")

    def clear_cached_passkey(self):
        biometrics.clear_key()
        self.app.meta["touch_id_enabled"] = False
        storage.save_meta(self.app.meta)
        ToastNotification(self.app, "Cached passkey cleared from Keychain.", duration_ms=2000)
        self.app.show_login()


class VaultFrame(ctk.CTkFrame):
    """Main Vault Screen with Top Bar, Categories, Search, and 3x3 Card Grid."""
    def __init__(self, master, app: SecureVaultApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.revealed: Set[str] = set()

        self.build_top_bar()
        self.build_category_bar()
        self.build_grid_area()

        self.refresh()

    # ---------- Top Bar ----------

    def build_top_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=28, pady=(20, 8))

        # Brand Title + Item Count Badge
        brand_frame = ctk.CTkFrame(bar, fg_color="transparent")
        brand_frame.pack(side="left")

        ctk.CTkLabel(
            brand_frame,
            text="DeepStore",
            font=(FONT_FAMILY, 24, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="left")

        self.count_badge = ctk.CTkLabel(
            brand_frame,
            text="0 items",
            font=(FONT_FAMILY, 11),
            text_color=TEXT_SECONDARY,
            fg_color=CARD_BG,
            corner_radius=10,
            padx=8,
            pady=2
        )
        self.count_badge.pack(side="left", padx=(10, 0))

        # Right Action Controls
        right_box = ctk.CTkFrame(bar, fg_color="transparent")
        right_box.pack(side="right")

        # Search box
        self.search_entry = ctk.CTkEntry(
            right_box,
            placeholder_text="Search vault...",
            width=180,
            height=32,
            corner_radius=8,
            border_color=BORDER_COLOR,
            fg_color=CARD_BG
        )
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.on_search)

        # Add item button (Yellow accent)
        ctk.CTkButton(
            right_box,
            text="+ Add Password",
            height=32,
            corner_radius=8,
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=self.add_entry_dialog
        ).pack(side="left", padx=(0, 10))

        # Settings Dialog Button
        ctk.CTkButton(
            right_box,
            text="⚙️ Settings",
            width=85,
            height=32,
            corner_radius=8,
            font=(FONT_FAMILY, 12),
            fg_color=CARD_BG,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=self.open_settings_dialog
        ).pack(side="left", padx=(0, 8))

        # Lock Button
        ctk.CTkButton(
            right_box,
            text="🔒 Lock",
            width=65,
            height=32,
            corner_radius=8,
            font=(FONT_FAMILY, 12),
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=self.app.lock
        ).pack(side="left")

    def on_search(self, event=None):
        self.app.search_query = self.search_entry.get().strip().lower()
        self.app.page = 0
        self.render_grid()

    # ---------- Category Bar ----------

    def build_category_bar(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="x", padx=28, pady=(4, 6))

        self.cat_scroll = ctk.CTkScrollableFrame(
            wrap,
            height=46,
            orientation="horizontal",
            fg_color="transparent"
        )
        self.cat_scroll.pack(side="left", fill="x", expand=True)

        self.edit_btn = ctk.CTkButton(
            wrap,
            text="Edit",
            width=50,
            height=28,
            corner_radius=6,
            font=(FONT_FAMILY, 11),
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_SECONDARY,
            hover_color=CARD_HOVER_BG,
            command=self.toggle_edit_mode
        )
        self.edit_btn.pack(side="right", padx=(8, 0))

    def toggle_edit_mode(self):
        self.app.category_edit_mode = not self.app.category_edit_mode
        self.edit_btn.configure(
            text="Done" if self.app.category_edit_mode else "Edit",
            fg_color=ACCENT_COLOR if self.app.category_edit_mode else "transparent",
            text_color=ACCENT_TEXT if self.app.category_edit_mode else TEXT_SECONDARY
        )
        self.render_categories()

    def render_categories(self):
        for w in self.cat_scroll.winfo_children():
            w.destroy()

        chips = ["All"] + self.app.data["categories"]
        for name in chips:
            chip_frame = ctk.CTkFrame(self.cat_scroll, fg_color="transparent")
            chip_frame.pack(side="left", padx=3)

            is_selected = (name == self.app.current_category)
            btn = ctk.CTkButton(
                chip_frame,
                text=name,
                corner_radius=14,
                height=28,
                font=(FONT_FAMILY, 12, "bold" if is_selected else "normal"),
                fg_color=ACCENT_COLOR if is_selected else CARD_BG,
                hover_color=ACCENT_HOVER if is_selected else CARD_HOVER_BG,
                text_color=ACCENT_TEXT if is_selected else TEXT_PRIMARY,
                border_width=0 if is_selected else 1,
                border_color=BORDER_COLOR,
                command=lambda n=name: self.select_category(n)
            )
            btn.pack(side="left")

            if self.app.category_edit_mode and name not in ("All", "Uncategorized"):
                ctk.CTkButton(
                    chip_frame,
                    text="✕",
                    width=20,
                    height=20,
                    corner_radius=10,
                    font=(FONT_FAMILY, 10, "bold"),
                    fg_color=DANGER_COLOR,
                    hover_color=DANGER_HOVER,
                    text_color="#FFFFFF",
                    command=lambda n=name: self.delete_category(n)
                ).pack(side="left", padx=(2, 0))

        if self.app.category_edit_mode:
            ctk.CTkButton(
                self.cat_scroll,
                text="+ New",
                width=70,
                height=28,
                corner_radius=14,
                font=(FONT_FAMILY, 11),
                fg_color="transparent",
                border_width=1,
                border_color=ACCENT_COLOR,
                text_color=ACCENT_COLOR,
                hover_color=CARD_HOVER_BG,
                command=self.add_category
            ).pack(side="left", padx=4)

    def select_category(self, name: str):
        self.app.current_category = name
        self.app.page = 0
        self.render_categories()
        self.render_grid()

    def add_category(self):
        dialog = ctk.CTkInputDialog(text="Enter category name:", title="New Category")
        name = dialog.get_input()
        if name and name.strip():
            if storage.add_category(self.app.data, name.strip()):
                self.app.save()
                self.render_categories()
            else:
                messagebox.showinfo("Category Exists", "A category with this name already exists.")

    def delete_category(self, name: str):
        if messagebox.askyesno("Delete Category", f"Delete '{name}'? Existing entries will move to 'Uncategorized'."):
            storage.delete_category(self.app.data, name)
            if self.app.current_category == name:
                self.app.current_category = "All"
            self.app.save()
            self.render_categories()
            self.render_grid()

    # ---------- Grid Area ----------

    def build_grid_area(self):
        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True, padx=28, pady=(4, 4))

        self.pager = ctk.CTkFrame(self, fg_color="transparent")
        self.pager.pack(fill="x", padx=28, pady=(0, 16))

    def get_filtered_entries(self):
        entries = self.app.data["entries"]
        if self.app.current_category != "All":
            entries = [e for e in entries if e.get("category") == self.app.current_category]
        if self.app.search_query:
            q = self.app.search_query
            entries = [
                e for e in entries
                if q in e.get("service", "").lower() or q in e.get("email", "").lower()
            ]
        return entries

    def render_grid(self):
        for w in self.grid_container.winfo_children():
            w.destroy()
        for w in self.pager.winfo_children():
            w.destroy()

        entries = self.get_filtered_entries()
        total_items = len(self.app.data.get("entries", []))
        self.count_badge.configure(text=f"{total_items} items")

        start = self.app.page * PAGE_SIZE
        page_entries = entries[start:start + PAGE_SIZE]

        for col in range(GRID_COLS):
            self.grid_container.grid_columnconfigure(col, weight=1, uniform="col")
        for row in range(GRID_ROWS):
            self.grid_container.grid_rowconfigure(row, weight=1, uniform="row")

        if not entries:
            empty_box = ctk.CTkFrame(self.grid_container, fg_color=CARD_BG, corner_radius=16, border_width=1, border_color=BORDER_COLOR)
            empty_box.grid(row=1, column=1, padx=20, pady=40, sticky="nsew")
            ctk.CTkLabel(
                empty_box,
                text="🔑",
                font=(FONT_FAMILY, 36)
            ).pack(pady=(24, 6))
            ctk.CTkLabel(
                empty_box,
                text="No passwords found",
                font=(FONT_FAMILY, 15, "bold"),
                text_color=TEXT_PRIMARY
            ).pack(pady=(0, 4))
            ctk.CTkLabel(
                empty_box,
                text="Click '+ Add Password' above to create one.",
                font=(FONT_FAMILY, 12),
                text_color=TEXT_SECONDARY
            ).pack(pady=(0, 24))
        else:
            for i, entry in enumerate(page_entries):
                r, c = divmod(i, GRID_COLS)
                card = self.build_card(self.grid_container, entry)
                card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

        total_pages = max(1, (len(entries) + PAGE_SIZE - 1) // PAGE_SIZE)
        if total_pages > 1:
            ctk.CTkButton(
                self.pager,
                text="◀ Prev",
                width=75,
                height=28,
                corner_radius=6,
                font=(FONT_FAMILY, 11),
                fg_color=CARD_BG,
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY,
                hover_color=CARD_HOVER_BG,
                command=self.prev_page,
                state=("normal" if self.app.page > 0 else "disabled")
            ).pack(side="left")

            ctk.CTkLabel(
                self.pager,
                text=f"Page {self.app.page + 1} of {total_pages} ({len(entries)} matching)",
                font=(FONT_FAMILY, 11),
                text_color=TEXT_SECONDARY
            ).pack(side="left", padx=12)

            ctk.CTkButton(
                self.pager,
                text="Next ▶",
                width=75,
                height=28,
                corner_radius=6,
                font=(FONT_FAMILY, 11),
                fg_color=CARD_BG,
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY,
                hover_color=CARD_HOVER_BG,
                command=self.next_page,
                state=("normal" if self.app.page < total_pages - 1 else "disabled")
            ).pack(side="left")

    def prev_page(self):
        self.app.page = max(0, self.app.page - 1)
        self.render_grid()

    def next_page(self):
        self.app.page += 1
        self.render_grid()

    # ---------- Card Cell (Show at top, Twin Copy at bottom) ----------

    def build_card(self, parent, entry: dict):
        card = ctk.CTkFrame(
            parent,
            corner_radius=16,
            fg_color=CARD_BG,
            border_width=1,
            border_color=BORDER_COLOR
        )

        # 1. TOP ROW: Service Name + SHOW/HIDE Button + More Options Menu
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(12, 6))

        # Title & Category Tag
        title_box = ctk.CTkFrame(top_row, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        service_text = entry.get("service", "Untitled")
        ctk.CTkLabel(
            title_box,
            text=service_text,
            font=(FONT_FAMILY, 14, "bold"),
            text_color=TEXT_PRIMARY,
            anchor="w"
        ).pack(side="top", anchor="w")

        cat_badge = ctk.CTkLabel(
            title_box,
            text=entry.get("category", "General"),
            font=(FONT_FAMILY, 10),
            text_color=ACCENT_COLOR,
            anchor="w"
        )
        cat_badge.pack(side="top", anchor="w")

        # Top Controls: Show/Hide Button at Top + Action Menu
        top_actions = ctk.CTkFrame(top_row, fg_color="transparent")
        top_actions.pack(side="right")

        revealed = entry["id"] in self.revealed
        show_btn = ctk.CTkButton(
            top_actions,
            text="Hide" if revealed else "Show",
            width=48,
            height=24,
            corner_radius=6,
            font=(FONT_FAMILY, 10, "bold"),
            fg_color=ACCENT_COLOR if revealed else "transparent",
            border_width=1,
            border_color=ACCENT_COLOR,
            text_color=ACCENT_TEXT if revealed else TEXT_PRIMARY,
            hover_color=ACCENT_HOVER,
            command=lambda e=entry: self.toggle_reveal(e)
        )
        show_btn.pack(side="left", padx=(0, 4))

        menu_btn = ctk.CTkButton(
            top_actions,
            text="⋯",
            width=26,
            height=24,
            corner_radius=6,
            font=(FONT_FAMILY, 12, "bold"),
            fg_color="transparent",
            text_color=TEXT_SECONDARY,
            hover_color=CARD_HOVER_BG,
            command=lambda e=entry: self.entry_menu(e)
        )
        menu_btn.pack(side="left")

        # 2. MIDDLE ROWS: Username / Email & Password Display
        content_box = ctk.CTkFrame(card, fg_color="transparent")
        content_box.pack(fill="x", padx=14, pady=(2, 8))

        # Username / Email
        email_val = entry.get("email", "—")
        email_label = ctk.CTkLabel(
            content_box,
            text=f"👤 {email_val}",
            font=(FONT_FAMILY, 11),
            text_color=TEXT_SECONDARY,
            anchor="w"
        )
        email_label.pack(fill="x", pady=(0, 3))

        # Password (Masked or Plaintext)
        pw_raw = entry.get("password", "")
        pw_display = pw_raw if revealed else "••••••••••••"
        pw_label = ctk.CTkLabel(
            content_box,
            text=f"🔑 {pw_display}",
            font=(MONO_FONT if revealed else FONT_FAMILY, 11),
            text_color=TEXT_PRIMARY if revealed else TEXT_MUTED,
            anchor="w"
        )
        pw_label.pack(fill="x")

        # 3. BOTTOM ROW: TWO COPY BUTTONS CLOSE TO EACH OTHER
        bottom_row = ctk.CTkFrame(card, fg_color="transparent")
        bottom_row.pack(fill="x", padx=14, pady=(0, 12))

        # Twin Copy Buttons Grouped Side-by-Side Close Together
        copy_group = ctk.CTkFrame(bottom_row, fg_color="transparent")
        copy_group.pack(fill="x", expand=True)

        copy_email_btn = ctk.CTkButton(
            copy_group,
            text="📋 Copy User",
            height=26,
            corner_radius=6,
            font=(FONT_FAMILY, 10),
            fg_color=BG_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=lambda e=entry: self.app.copy_to_clipboard(e.get("email", ""), "Username")
        )
        copy_email_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        copy_pw_btn = ctk.CTkButton(
            copy_group,
            text="🔑 Copy Pass",
            height=26,
            corner_radius=6,
            font=(FONT_FAMILY, 10, "bold"),
            fg_color=ACCENT_SUBTLE,
            border_width=1,
            border_color=ACCENT_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=ACCENT_COLOR,
            command=lambda e=entry: self.app.copy_to_clipboard(e.get("password", ""), "Password")
        )
        copy_pw_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Responsive card hover effect
        def on_enter(e):
            try:
                card.configure(border_color=ACCENT_COLOR)
            except Exception:
                pass

        def on_leave(e):
            try:
                card.configure(border_color=BORDER_COLOR)
            except Exception:
                pass

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        return card

    def toggle_reveal(self, entry: dict):
        if entry["id"] in self.revealed:
            self.revealed.remove(entry["id"])
        else:
            self.revealed.add(entry["id"])
        self.render_grid()

    def entry_menu(self, entry: dict):
        win = ctk.CTkToplevel(self)
        win.title(entry.get("service", "Item"))
        win.geometry("320x180")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(
            win,
            text=entry.get("service", "Options"),
            font=(FONT_FAMILY, 15, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(pady=(16, 10))

        ctk.CTkButton(
            win,
            text="✏️ Edit Password",
            height=32,
            corner_radius=8,
            font=(FONT_FAMILY, 12),
            fg_color=BG_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=lambda: (win.destroy(), self.edit_entry_dialog(entry))
        ).pack(fill="x", padx=24, pady=4)

        ctk.CTkButton(
            win,
            text="🗑️ Delete Entry",
            height=32,
            corner_radius=8,
            font=(FONT_FAMILY, 12),
            fg_color=DANGER_COLOR,
            hover_color=DANGER_HOVER,
            text_color="#FFFFFF",
            command=lambda: (win.destroy(), self.delete_entry(entry))
        ).pack(fill="x", padx=24, pady=4)

    def delete_entry(self, entry: dict):
        if messagebox.askyesno("Delete Password", f"Are you sure you want to delete '{entry.get('service')}'?"):
            self.app.data["entries"] = [e for e in self.app.data["entries"] if e["id"] != entry["id"]]
            self.app.save()
            ToastNotification(self.app, f"Deleted '{entry.get('service')}'", duration_ms=2000, icon="🗑️")
            self.render_grid()

    # ---------- Form Dialog (Add / Edit) ----------

    def add_entry_dialog(self):
        self.entry_form_dialog(title="Add New Password")

    def edit_entry_dialog(self, entry: dict):
        self.entry_form_dialog(title="Edit Password", entry=entry)

    def entry_form_dialog(self, title: str, entry: Optional[dict] = None):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("420x480")
        win.resizable(False, False)
        win.grab_set()

        pad = {"padx": 28, "pady": 4}

        ctk.CTkLabel(
            win,
            text=title,
            font=(FONT_FAMILY, 18, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(pady=(20, 10))

        # Category
        ctk.CTkLabel(win, text="Category", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        cat_var = ctk.StringVar(value=(entry["category"] if entry else self.app.data["categories"][0]))
        cat_menu = ctk.CTkOptionMenu(
            win,
            values=self.app.data["categories"],
            variable=cat_var,
            corner_radius=8,
            fg_color=BG_COLOR,
            button_color=BORDER_COLOR,
            button_hover_color=ACCENT_COLOR,
            text_color=TEXT_PRIMARY
        )
        cat_menu.pack(fill="x", padx=28, pady=(0, 6))

        # Service
        ctk.CTkLabel(win, text="Service / Website", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        service_entry = ctk.CTkEntry(win, placeholder_text="e.g. GitHub, Google, Amazon", corner_radius=8, height=36)
        service_entry.pack(fill="x", padx=28, pady=(0, 6))
        if entry:
            service_entry.insert(0, entry.get("service", ""))

        # Email / Username
        ctk.CTkLabel(win, text="Email / Username", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        email_entry = ctk.CTkEntry(win, placeholder_text="e.g. user@example.com", corner_radius=8, height=36)
        email_entry.pack(fill="x", padx=28, pady=(0, 6))
        if entry:
            email_entry.insert(0, entry.get("email", ""))

        # Password + Generate
        ctk.CTkLabel(win, text="Password", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        pw_row = ctk.CTkFrame(win, fg_color="transparent")
        pw_row.pack(fill="x", padx=28, pady=(0, 12))

        pw_entry = ctk.CTkEntry(pw_row, show="•", corner_radius=8, height=36)
        pw_entry.pack(side="left", fill="x", expand=True)
        if entry:
            pw_entry.insert(0, entry.get("password", ""))

        def toggle_form_pw():
            if pw_entry.cget("show") == "":
                pw_entry.configure(show="•")
                eye_btn.configure(text="👁")
            else:
                pw_entry.configure(show="")
                eye_btn.configure(text="🙈")

        eye_btn = ctk.CTkButton(
            pw_row,
            text="👁",
            width=36,
            height=36,
            corner_radius=8,
            fg_color=BG_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=toggle_form_pw
        )
        eye_btn.pack(side="left", padx=(6, 0))

        def generate():
            pwd = gen_password(length=20)
            pw_entry.delete(0, "end")
            pw_entry.insert(0, pwd)
            pw_entry.configure(show="")
            eye_btn.configure(text="🙈")

        ctk.CTkButton(
            pw_row,
            text="🎲 Generate",
            width=90,
            height=36,
            corner_radius=8,
            font=(FONT_FAMILY, 11, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=generate
        ).pack(side="left", padx=(6, 0))

        def save():
            service = service_entry.get().strip()
            email = email_entry.get().strip()
            password = pw_entry.get()
            category = cat_var.get()

            if not service or not password:
                messagebox.showerror("Missing Information", "Service and Password are required fields.")
                return

            if entry:
                entry.update(category=category, service=service, email=email, password=password)
                ToastNotification(self.app, f"Updated '{service}'", duration_ms=2000, icon="✓")
            else:
                self.app.data["entries"].append(storage.new_entry(category, service, email, password))
                ToastNotification(self.app, f"Added '{service}'", duration_ms=2000, icon="✓")

            self.app.save()
            win.destroy()
            self.render_grid()

        ctk.CTkButton(
            win,
            text="Save Password",
            height=40,
            corner_radius=10,
            font=(FONT_FAMILY, 13, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=save
        ).pack(fill="x", padx=28, pady=(10, 20))

    # ---------- In-App Passkey & Settings Modal ----------

    def open_settings_dialog(self):
        win = ctk.CTkToplevel(self)
        win.title("DeepStore Settings")
        win.geometry("540x600")
        win.resizable(False, False)
        win.grab_set()

        pad = {"padx": 24, "pady": 6}

        # Header
        header = ctk.CTkFrame(win, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))
        ctk.CTkLabel(
            header,
            text="⚙️ Preferences & Security",
            font=(FONT_FAMILY, 18, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="left")

        # Scrollable Settings Container
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 16))

        # --- SECTION 1: Passkey & Touch ID Management ---
        sec1 = ctk.CTkFrame(scroll, corner_radius=14, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR)
        sec1.pack(fill="x", pady=8, padx=12)

        ctk.CTkLabel(
            sec1,
            text="Touch ID & Passkey Cache",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=16, pady=(14, 4))

        has_touch_id = biometrics.touch_id_available()
        is_cached = biometrics.is_key_stored()
        status_text = "✓ Touch ID hardware supported" if has_touch_id else "⚠️ Touch ID not available on this device"
        status_color = SUCCESS_COLOR if has_touch_id else TEXT_MUTED

        ctk.CTkLabel(
            sec1,
            text=status_text,
            font=(FONT_FAMILY, 11),
            text_color=status_color
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Toggle Switch
        touch_var = ctk.BooleanVar(value=self.app.meta.get("touch_id_enabled", False) and is_cached)

        def on_touch_toggle():
            val = touch_var.get()
            if val:
                if not has_touch_id:
                    messagebox.showwarning("Unavailable", "Touch ID hardware is not active on this Mac.")
                    touch_var.set(False)
                    return
                # Enroll / store current key
                biometrics.store_key(self.app.key)
                self.app.meta["touch_id_enabled"] = True
                storage.save_meta(self.app.meta)
                ToastNotification(self.app, "Passkey enrolled in Keychain.", icon="🔑")
            else:
                biometrics.clear_key()
                self.app.meta["touch_id_enabled"] = False
                storage.save_meta(self.app.meta)
                ToastNotification(self.app, "Passkey cleared from Keychain.", icon="🛡️")

        switch = ctk.CTkSwitch(
            sec1,
            text="Enable Touch ID / Biometric Passkey Unlock",
            font=(FONT_FAMILY, 12),
            variable=touch_var,
            progress_color=ACCENT_COLOR,
            command=on_touch_toggle
        )
        switch.pack(anchor="w", padx=16, pady=(0, 10))

        # Passkey action buttons
        passkey_btns = ctk.CTkFrame(sec1, fg_color="transparent")
        passkey_btns.pack(fill="x", padx=16, pady=(0, 14))

        def resync_passkey():
            if self.app.key:
                biometrics.store_key(self.app.key)
                self.app.meta["touch_id_enabled"] = True
                storage.save_meta(self.app.meta)
                touch_var.set(True)
                ToastNotification(self.app, "Passkey synced to Keychain!", icon="✓")

        def clear_passkey():
            biometrics.clear_key()
            self.app.meta["touch_id_enabled"] = False
            storage.save_meta(self.app.meta)
            touch_var.set(False)
            ToastNotification(self.app, "Keychain passkey cache cleared.", icon="🗑️")

        ctk.CTkButton(
            passkey_btns,
            text="🔄 Re-sync Passkey",
            height=28,
            corner_radius=6,
            font=(FONT_FAMILY, 11),
            fg_color=BG_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=resync_passkey
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            passkey_btns,
            text="🗑️ Clear Passkey Cache",
            height=28,
            corner_radius=6,
            font=(FONT_FAMILY, 11),
            fg_color=BG_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=clear_passkey
        ).pack(side="left")

        # --- SECTION 2: Rotate / Change Master Passkey ---
        sec2 = ctk.CTkFrame(scroll, corner_radius=14, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR)
        sec2.pack(fill="x", pady=8, padx=12)

        ctk.CTkLabel(
            sec2,
            text="Change Master Passkey",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            sec2,
            text="Re-encrypts the entire vault database with a fresh random salt.",
            font=(FONT_FAMILY, 11),
            text_color=TEXT_SECONDARY
        ).pack(anchor="w", padx=16, pady=(0, 10))

        curr_pw = ctk.CTkEntry(sec2, placeholder_text="Current passkey", show="•", height=34, corner_radius=6)
        curr_pw.pack(fill="x", padx=16, pady=(0, 6))

        new_pw = ctk.CTkEntry(sec2, placeholder_text="New passkey (min 8 chars)", show="•", height=34, corner_radius=6)
        new_pw.pack(fill="x", padx=16, pady=(0, 6))

        confirm_pw = ctk.CTkEntry(sec2, placeholder_text="Confirm new passkey", show="•", height=34, corner_radius=6)
        confirm_pw.pack(fill="x", padx=16, pady=(0, 10))

        def update_master_key():
            cur = curr_pw.get()
            np = new_pw.get()
            cp = confirm_pw.get()

            if not cur or not np:
                messagebox.showerror("Error", "Please fill all password fields.")
                return
            if len(np) < 8:
                messagebox.showerror("Error", "New passkey must be at least 8 characters.")
                return
            if np != cp:
                messagebox.showerror("Error", "New passkeys do not match.")
                return

            try:
                # Verify current passkey first
                storage.unlock_vault(cur)
                # Re-encrypt vault with new passkey
                new_derived_key = storage.change_master_password(self.app.key, np)
                self.app.key = new_derived_key

                # Update Keychain if Touch ID is active
                if self.app.meta.get("touch_id_enabled"):
                    biometrics.store_key(new_derived_key)

                curr_pw.delete(0, "end")
                new_pw.delete(0, "end")
                confirm_pw.delete(0, "end")
                ToastNotification(self.app, "Master passkey updated successfully!", duration_ms=2500, icon="🔐")
                messagebox.showinfo("Success", "Master passkey has been updated and vault safely re-encrypted.")
            except crypto_utils.WrongPassword:
                messagebox.showerror("Error", "Current master passkey is incorrect.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update passkey: {str(e)}")

        ctk.CTkButton(
            sec2,
            text="Update & Re-encrypt Vault",
            height=32,
            corner_radius=8,
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=update_master_key
        ).pack(anchor="w", padx=16, pady=(0, 14))

        # --- SECTION 3: Auto-Lock & Clipboard Timers ---
        sec3 = ctk.CTkFrame(scroll, corner_radius=14, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR)
        sec3.pack(fill="x", pady=8, padx=12)

        ctk.CTkLabel(
            sec3,
            text="Security & Auto-Lock",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=16, pady=(14, 8))

        # Inactivity auto lock
        lock_row = ctk.CTkFrame(sec3, fg_color="transparent")
        lock_row.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(lock_row, text="Auto-lock after inactivity:", font=(FONT_FAMILY, 12), text_color=TEXT_PRIMARY).pack(side="left")
        lock_opts = {"Never": 0, "1 min": 1, "5 mins": 5, "15 mins": 15, "30 mins": 30}
        curr_lock = self.app.meta.get("auto_lock_minutes", 5)
        curr_lock_str = next((k for k, v in lock_opts.items() if v == curr_lock), "5 mins")

        def on_lock_change(val):
            self.app.meta["auto_lock_minutes"] = lock_opts[val]
            storage.save_meta(self.app.meta)

        ctk.CTkOptionMenu(
            lock_row,
            values=list(lock_opts.keys()),
            width=110,
            height=28,
            corner_radius=6,
            fg_color=BG_COLOR,
            button_color=BORDER_COLOR,
            button_hover_color=ACCENT_COLOR,
            text_color=TEXT_PRIMARY,
            command=on_lock_change
        ).set(curr_lock_str)
        lock_row.winfo_children()[-1].pack(side="right")

        # Clipboard auto clear
        clip_row = ctk.CTkFrame(sec3, fg_color="transparent")
        clip_row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(clip_row, text="Auto-clear clipboard after:", font=(FONT_FAMILY, 12), text_color=TEXT_PRIMARY).pack(side="left")
        clip_opts = {"15 seconds": 15, "30 seconds": 30, "60 seconds": 60, "Never": 0}
        curr_clip = self.app.meta.get("clipboard_clear_seconds", 30)
        curr_clip_str = next((k for k, v in clip_opts.items() if v == curr_clip), "30 seconds")

        def on_clip_change(val):
            self.app.meta["clipboard_clear_seconds"] = clip_opts[val]
            storage.save_meta(self.app.meta)

        ctk.CTkOptionMenu(
            clip_row,
            values=list(clip_opts.keys()),
            width=110,
            height=28,
            corner_radius=6,
            fg_color=BG_COLOR,
            button_color=BORDER_COLOR,
            button_hover_color=ACCENT_COLOR,
            text_color=TEXT_PRIMARY,
            command=on_clip_change
        ).set(curr_clip_str)
        clip_row.winfo_children()[-1].pack(side="right")

        # Theme Appearance
        theme_row = ctk.CTkFrame(sec3, fg_color="transparent")
        theme_row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(theme_row, text="Appearance Theme:", font=(FONT_FAMILY, 12), text_color=TEXT_PRIMARY).pack(side="left")

        def on_theme_change(val):
            ctk.set_appearance_mode(val)
            self.app.meta["theme"] = val
            storage.save_meta(self.app.meta)

        theme_seg = ctk.CTkSegmentedButton(
            theme_row,
            values=["Light", "System", "Dark"],
            selected_color=ACCENT_COLOR,
            selected_hover_color=ACCENT_HOVER,
            command=on_theme_change
        )
        theme_seg.set(self.app.meta.get("theme", "System"))
        theme_seg.pack(side="right")

    # ---------- Refresh Everything ----------

    def refresh(self):
        self.render_categories()
        self.render_grid()
