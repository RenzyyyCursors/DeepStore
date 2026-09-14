"""
ui.py
-----
DeepStore Windows Password Manager Interface
- Golden Yellow + Slate Graphite aesthetics
- Windows Password & Windows Credential Manager integration
- Responsive animations & Toast notification feedback
- Reorganized card layout: Show/Hide toggle at top, twin Copy buttons at bottom
- Complete in-app Windows Security & Quick Unlock settings, Master Key rotation, Auto-lock & Clipboard security
"""

import time
import secrets
import string
from typing import Optional, Set
import customtkinter as ctk
from tkinter import messagebox

from . import storage
from . import crypto_utils
from . import win_auth

# ---------------- Design System: Colors & Typography ----------------
FONT_FAMILY = "Segoe UI"
MONO_FONT = "Consolas"

# Golden Yellow Accent Palette
ACCENT_COLOR = "#F5C518"       # Vibrant Golden Yellow
ACCENT_HOVER = "#E5B510"       # Darker gold on hover
ACCENT_ACTIVE = "#CCA00E"      # Deep gold
ACCENT_TEXT = "#1C1C1E"        # Crisp dark text on yellow
ACCENT_SUBTLE = ("#FEF3C7", "#3D3519")  # Soft pastel yellow / dark graphite gold tint

# Slate Graphite & Dark/Light Surfaces
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
    """Floating animated toast banner."""
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


class WindowsPasswordDialog(ctk.CTkToplevel):
    """Windows Password verification dialog for quick vault unlock."""
    def __init__(self, parent, on_success: callable):
        super().__init__(parent)
        self.title("Windows Security")
        self.geometry("420x280")
        self.resizable(False, False)
        self.configure(fg_color=BG_COLOR)
        self.transient(parent)
        self.grab_set()

        self.on_success = on_success
        username = win_auth.get_current_username()

        # Center dialog relative to parent
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + (parent_w - 420) // 2
        y = parent_y + (parent_h - 280) // 2
        self.geometry(f"+{max(10, x)}+{max(10, y)}")

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        # Header with Windows Shield Icon
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 6))

        ctk.CTkLabel(
            header,
            text="🛡️  Windows Security",
            font=(FONT_FAMILY, 16, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w")

        ctk.CTkLabel(
            card,
            text=f"Enter Windows password for {username} to unlock DeepStore.",
            font=(FONT_FAMILY, 11),
            text_color=TEXT_SECONDARY,
            wraplength=340,
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 12))

        self.pw_entry = ctk.CTkEntry(
            card,
            placeholder_text="Windows Password",
            show="•",
            height=38,
            corner_radius=8,
            border_color=BORDER_COLOR,
            fg_color=BG_COLOR
        )
        self.pw_entry.pack(fill="x", padx=20, pady=(0, 4))
        self.pw_entry.bind("<Return>", lambda e: self._verify())
        self.pw_entry.focus()

        self.error_label = ctk.CTkLabel(
            card,
            text="",
            font=(FONT_FAMILY, 11),
            text_color=DANGER_COLOR
        )
        self.error_label.pack(anchor="w", padx=20, pady=(0, 8))

        btn_bar = ctk.CTkFrame(card, fg_color="transparent")
        btn_bar.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkButton(
            btn_bar,
            text="Cancel",
            width=90,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=self.destroy
        ).pack(side="right", padx=(8, 0))

        self.ok_btn = ctk.CTkButton(
            btn_bar,
            text="Unlock",
            width=100,
            height=34,
            corner_radius=8,
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=self._verify
        )
        self.ok_btn.pack(side="right")

    def _verify(self):
        pw = self.pw_entry.get()
        if not pw:
            self.error_label.configure(text="Please enter your Windows password.")
            return

        self.ok_btn.configure(state="disabled", text="Verifying...")
        self.update()

        valid = win_auth.verify_windows_password(pw)
        if valid:
            self.destroy()
            self.on_success()
        else:
            self.ok_btn.configure(state="normal", text="Unlock")
            self.error_label.configure(text="Incorrect Windows password.")


class SecureVaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DeepStore — Encrypted Windows Vault")
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
    """Refined Windows unlock / vault setup view."""
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
               if self.first_run else "Enter your master passkey or unlock with Windows Password.")
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

        # Windows Auth / Quick Unlock button
        has_win_auth = win_auth.windows_auth_available()
        win_auth_enabled = self.app.meta.get("windows_auth_enabled", False)
        has_key_cached = win_auth.is_key_stored()

        if not self.first_run and has_win_auth and (win_auth_enabled or has_key_cached):
            self.win_btn = ctk.CTkButton(
                wrapper,
                text="🪟  Unlock with Windows Password",
                width=300,
                height=38,
                corner_radius=10,
                font=(FONT_FAMILY, 12),
                fg_color="transparent",
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY,
                hover_color=CARD_HOVER_BG,
                command=self.windows_password_unlock
            )
            self.win_btn.grid(row=btn_row + 2, column=0, columnspan=2, padx=40, pady=(0, 10))

            # Helper to reset passkey cache if user wants
            ctk.CTkButton(
                wrapper,
                text="Clear Windows cached passkey",
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
                self.maybe_offer_windows_auth(key)
                self.app.show_vault()
            except Exception as e:
                self.error_label.configure(text=f"Setup error: {str(e)}", text_color=DANGER_COLOR)
        else:
            try:
                key = storage.unlock_vault(password)
                self.app.key = key
                self.app.data = storage.load_data(key)
                # If Windows Auth is enabled, keep Credential Manager key in sync
                if self.app.meta.get("windows_auth_enabled"):
                    win_auth.store_key(key)
                self.app.show_vault()
            except crypto_utils.WrongPassword:
                self.error_label.configure(text="Incorrect master passkey.", text_color=DANGER_COLOR)
            except Exception as e:
                self.error_label.configure(text=f"Error: {str(e)}", text_color=DANGER_COLOR)

    def maybe_offer_windows_auth(self, key: bytes):
        if not win_auth.windows_auth_available():
            return
        if messagebox.askyesno(
            "Enable Windows Password Unlock?",
            "Would you like to enable quick unlock using your Windows account password?\n\n"
            "Your vault key will be saved securely in Windows Credential Manager.\n"
            "You can enable or disable this in Settings at any time."
        ):
            win_auth.store_key(key)
            self.app.meta["windows_auth_enabled"] = True
            storage.save_meta(self.app.meta)

    def windows_password_unlock(self):
        key = win_auth.retrieve_key()
        if not key:
            self.error_label.configure(
                text="No cached key found in Windows Credential Manager. Use master passkey.",
                text_color=DANGER_COLOR
            )
            return

        def on_verified():
            try:
                self.app.data = storage.load_data(key)
                self.app.key = key
                self.app.show_vault()
            except Exception:
                # Guard: LoginFrame may have been destroyed if show_vault() failed midway
                try:
                    if self.winfo_exists() and hasattr(self, "error_label") and self.error_label.winfo_exists():
                        self.error_label.configure(
                            text="Cached key out of sync. Please unlock with master passkey.",
                            text_color=DANGER_COLOR
                        )
                except Exception:
                    pass

        WindowsPasswordDialog(self.app, on_success=on_verified)

    def clear_cached_passkey(self):
        win_auth.clear_key()
        self.app.meta["windows_auth_enabled"] = False
        storage.save_meta(self.app.meta)
        ToastNotification(self.app, "Cached passkey cleared from Windows Credential Manager.", duration_ms=2000, icon="🛡️")
        self.app.show_login()


class VaultFrame(ctk.CTkFrame):
    """Main Vault Screen with Top Bar, Categories, Search, and 3x3 Card Grid."""
    def __init__(self, master, app: SecureVaultApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.revealed_cards: Set[str] = set()

        # Top Bar
        self.top_bar = ctk.CTkFrame(self, height=64, fg_color=CARD_BG, corner_radius=0)
        self.top_bar.pack(fill="x", side="top")
        self.top_bar.pack_propagate(False)

        # Title / Brand
        brand_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        brand_frame.pack(side="left", padx=24)

        ctk.CTkLabel(
            brand_frame,
            text="DeepStore",
            font=(FONT_FAMILY, 24, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="left")

        vault_badge = ctk.CTkFrame(
            brand_frame,
            fg_color=ACCENT_SUBTLE,
            corner_radius=6
        )
        vault_badge.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(
            vault_badge,
            text="VAULT",
            font=(FONT_FAMILY, 11, "bold"),
            text_color=ACCENT_COLOR
        ).pack(padx=8, pady=2)

        # Action Buttons on Right
        actions_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        actions_frame.pack(side="right", padx=24)

        # 1. New Entry Button (Golden Yellow Accent)
        ctk.CTkButton(
            actions_frame,
            text="+ Add Item",
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            width=100,
            height=34,
            corner_radius=8,
            command=self.open_add_modal
        ).pack(side="left", padx=4)

        # 2. Settings Button
        ctk.CTkButton(
            actions_frame,
            text="⚙️ Preferences",
            font=(FONT_FAMILY, 12),
            fg_color=BG_COLOR,
            hover_color=CARD_HOVER_BG,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            width=115,
            height=34,
            corner_radius=8,
            command=self.open_settings_modal
        ).pack(side="left", padx=4)

        # 3. Lock Button
        ctk.CTkButton(
            actions_frame,
            text="🔒 Lock",
            font=(FONT_FAMILY, 12),
            fg_color="transparent",
            hover_color=CARD_HOVER_BG,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            width=80,
            height=34,
            corner_radius=8,
            command=lambda: self.app.lock("Vault locked.")
        ).pack(side="left", padx=4)

        # Category Bar & Search Bar Frame
        control_bar = ctk.CTkFrame(self, fg_color="transparent", height=48)
        control_bar.pack(fill="x", padx=24, pady=(16, 8))

        # Search Box
        self.search_entry = ctk.CTkEntry(
            control_bar,
            placeholder_text="🔍 Search credentials, websites, emails...",
            width=320,
            height=36,
            corner_radius=8,
            border_color=BORDER_COLOR,
            fg_color=CARD_BG,
            text_color=TEXT_PRIMARY
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # Categories Frame
        self.cats_frame = ctk.CTkFrame(control_bar, fg_color="transparent")
        self.cats_frame.pack(side="left", fill="x", expand=True)

        # Main 3x3 Card Grid Container
        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True, padx=24, pady=4)

        # Pagination & Stats Footer
        self.footer = ctk.CTkFrame(self, height=44, fg_color="transparent")
        self.footer.pack(fill="x", side="bottom", padx=24, pady=(0, 12))

        self.render_categories()
        self.render_grid()

    # ---------- Category Bar Rendering ----------

    def render_categories(self):
        for w in self.cats_frame.winfo_children():
            w.destroy()

        cats = ["All"] + self.app.data.get("categories", storage.DEFAULT_CATEGORIES)
        for cat in cats:
            is_selected = (cat == self.app.current_category)
            fg = ACCENT_COLOR if is_selected else CARD_BG
            tc = ACCENT_TEXT if is_selected else TEXT_PRIMARY
            border = ACCENT_COLOR if is_selected else BORDER_COLOR

            btn = ctk.CTkButton(
                self.cats_frame,
                text=cat,
                font=(FONT_FAMILY, 12, "bold" if is_selected else "normal"),
                fg_color=fg,
                text_color=tc,
                border_width=1,
                border_color=border,
                hover_color=ACCENT_HOVER if is_selected else CARD_HOVER_BG,
                height=32,
                corner_radius=8,
                command=lambda c=cat: self.select_category(c)
            )
            btn.pack(side="left", padx=(0, 6))

        # Category Manage Button
        cat_manage_text = "Done" if self.app.category_edit_mode else "Edit Tags"
        ctk.CTkButton(
            self.cats_frame,
            text=cat_manage_text,
            font=(FONT_FAMILY, 10, "bold"),
            fg_color="transparent",
            text_color=ACCENT_COLOR if self.app.category_edit_mode else TEXT_MUTED,
            hover_color=CARD_HOVER_BG,
            height=30,
            width=65,
            corner_radius=6,
            command=self.toggle_category_edit_mode
        ).pack(side="left", padx=(4, 0))

        if self.app.category_edit_mode:
            ctk.CTkButton(
                self.cats_frame,
                text="+ Add Tag",
                font=(FONT_FAMILY, 11),
                fg_color=BG_COLOR,
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY,
                hover_color=CARD_HOVER_BG,
                height=30,
                width=80,
                corner_radius=6,
                command=self.open_add_category_dialog
            ).pack(side="left", padx=(4, 0))

    def select_category(self, cat: str):
        self.app.current_category = cat
        self.app.page = 0
        self.render_categories()
        self.render_grid()

    def toggle_category_edit_mode(self):
        self.app.category_edit_mode = not self.app.category_edit_mode
        self.render_categories()

    def open_add_category_dialog(self):
        dialog = ctk.CTkInputDialog(text="Enter new category name:", title="Add Category")
        name = dialog.get_input()
        if name:
            if storage.add_category(self.app.data, name):
                self.app.save()
                self.render_categories()
                ToastNotification(self.app, f"Category '{name}' added.", icon="🏷️")
            else:
                messagebox.showerror("Error", "Category already exists or invalid.")

    # ---------- Search & Filtering ----------

    def _on_search(self, event=None):
        self.app.search_query = self.search_entry.get().strip().lower()
        self.app.page = 0
        self.render_grid()

    def get_filtered_entries(self):
        entries = self.app.data.get("entries", [])
        # Filter by category
        if self.app.current_category != "All":
            entries = [e for e in entries if e.get("category") == self.app.current_category]
        # Filter by search
        if self.app.search_query:
            q = self.app.search_query
            entries = [
                e for e in entries
                if q in e.get("service", "").lower()
                or q in e.get("email", "").lower()
                or q in e.get("category", "").lower()
                or q in e.get("notes", "").lower()
            ]
        return entries

    # ---------- 3x3 Card Grid Rendering ----------

    def render_grid(self):
        for w in self.grid_container.winfo_children():
            w.destroy()

        entries = self.get_filtered_entries()
        total_items = len(entries)
        total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
        if self.app.page >= total_pages:
            self.app.page = max(0, total_pages - 1)

        start_idx = self.app.page * PAGE_SIZE
        page_entries = entries[start_idx: start_idx + PAGE_SIZE]

        if not page_entries:
            empty = ctk.CTkFrame(self.grid_container, fg_color="transparent")
            empty.place(relx=0.5, rely=0.5, anchor="center")

            ctk.CTkLabel(
                empty,
                text="📂",
                font=(FONT_FAMILY, 36)
            ).pack(pady=(0, 6))

            ctk.CTkLabel(
                empty,
                text="No credentials found",
                font=(FONT_FAMILY, 15, "bold"),
                text_color=TEXT_PRIMARY
            ).pack()

            ctk.CTkLabel(
                empty,
                text="Click '+ Add Item' above to create your first encrypted credential.",
                font=(FONT_FAMILY, 12),
                text_color=TEXT_SECONDARY
            ).pack(pady=(4, 0))
        else:
            # Configure 3x3 grid columns and rows with equal weight
            for c in range(GRID_COLS):
                self.grid_container.columnconfigure(c, weight=1, uniform="col", pad=12)
            for r in range(GRID_ROWS):
                self.grid_container.rowconfigure(r, weight=1, uniform="row", pad=12)

            for idx, entry in enumerate(page_entries):
                r = idx // GRID_COLS
                c = idx % GRID_COLS
                card = self._build_card(self.grid_container, entry)
                card.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

        self._render_footer(total_items, total_pages)

    def _render_footer(self, total_items: int, total_pages: int):
        for w in self.footer.winfo_children():
            w.destroy()

        # Item count stats
        cat_str = f" in '{self.app.current_category}'" if self.app.current_category != "All" else ""
        stats_text = f"{total_items} item{'s' if total_items != 1 else ''}{cat_str}"
        ctk.CTkLabel(
            self.footer,
            text=stats_text,
            font=(FONT_FAMILY, 11),
            text_color=TEXT_SECONDARY
        ).pack(side="left")

        # Pagination controls
        if total_pages > 1:
            p_frame = ctk.CTkFrame(self.footer, fg_color="transparent")
            p_frame.pack(side="right")

            ctk.CTkButton(
                p_frame,
                text="‹ Previous",
                width=75,
                height=28,
                corner_radius=6,
                font=(FONT_FAMILY, 11),
                fg_color=CARD_BG,
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY if self.app.page > 0 else TEXT_MUTED,
                state="normal" if self.app.page > 0 else "disabled",
                command=self.prev_page
            ).pack(side="left", padx=4)

            ctk.CTkLabel(
                p_frame,
                text=f"Page {self.app.page + 1} of {total_pages}",
                font=(FONT_FAMILY, 11),
                text_color=TEXT_PRIMARY
            ).pack(side="left", padx=8)

            ctk.CTkButton(
                p_frame,
                text="Next ›",
                width=75,
                height=28,
                corner_radius=6,
                font=(FONT_FAMILY, 11),
                fg_color=CARD_BG,
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY if self.app.page < total_pages - 1 else TEXT_MUTED,
                state="normal" if self.app.page < total_pages - 1 else "disabled",
                command=self.next_page
            ).pack(side="left", padx=4)

    def prev_page(self):
        if self.app.page > 0:
            self.app.page -= 1
            self.render_grid()

    def next_page(self):
        entries = self.get_filtered_entries()
        total_pages = max(1, (len(entries) + PAGE_SIZE - 1) // PAGE_SIZE)
        if self.app.page < total_pages - 1:
            self.app.page += 1
            self.render_grid()

    # ---------- Refined Card Layout ----------

    def _build_card(self, parent, entry: dict) -> ctk.CTkFrame:
        """
        Builds a single responsive card:
        - TOP: Service Name + Category Tag + Show/Hide Toggle + 3-dots Menu
        - MIDDLE: Username/Email + Password preview (monospace / dots)
        - BOTTOM: Twin Copy Buttons (Copy User, Copy Pass) neatly close together
        """
        eid = entry.get("id", "")
        revealed = eid in self.revealed_cards

        card = ctk.CTkFrame(
            parent,
            corner_radius=14,
            fg_color=CARD_BG,
            border_width=1,
            border_color=BORDER_COLOR
        )

        # Hover elevation effect
        def _on_enter(e):
            try:
                card.configure(border_color=BORDER_HIGHLIGHT, fg_color=CARD_HOVER_BG)
            except Exception:
                pass

        def _on_leave(e):
            try:
                card.configure(border_color=BORDER_COLOR, fg_color=CARD_BG)
            except Exception:
                pass

        card.bind("<Enter>", _on_enter)
        card.bind("<Leave>", _on_leave)

        # === TOP SECTION ===
        top_bar = ctk.CTkFrame(card, fg_color="transparent")
        top_bar.pack(fill="x", padx=12, pady=(10, 4))

        # Service Name & Category tag
        left_header = ctk.CTkFrame(top_bar, fg_color="transparent")
        left_header.pack(side="left", fill="x", expand=True)

        service_lbl = ctk.CTkLabel(
            left_header,
            text=entry.get("service", "Untitled"),
            font=(FONT_FAMILY, 14, "bold"),
            text_color=TEXT_PRIMARY,
            anchor="w"
        )
        service_lbl.pack(anchor="w")

        cat_badge = ctk.CTkLabel(
            left_header,
            text=entry.get("category", "General"),
            font=(FONT_FAMILY, 10),
            text_color=ACCENT_COLOR,
            anchor="w"
        )
        cat_badge.pack(anchor="w")

        # Top Right: Show/Hide Toggle Eye + Context Action Menu (⋯)
        right_actions = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_actions.pack(side="right")

        eye_btn = ctk.CTkButton(
            right_actions,
            text="🙈" if revealed else "👁️",
            width=28,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=BG_COLOR,
            font=(FONT_FAMILY, 10, "bold"),
            command=lambda: self.toggle_reveal(eid)
        )
        eye_btn.pack(side="left", padx=(0, 2))

        menu_btn = ctk.CTkButton(
            right_actions,
            text="⋯",
            width=28,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=BG_COLOR,
            font=(FONT_FAMILY, 12, "bold"),
            text_color=TEXT_SECONDARY,
            command=lambda: self.open_entry_menu(entry, menu_btn)
        )
        menu_btn.pack(side="left")

        # === MIDDLE SECTION: Credentials ===
        mid = ctk.CTkFrame(card, fg_color="transparent")
        mid.pack(fill="x", padx=12, pady=(4, 8))

        # Email / Username
        email_str = entry.get("email", "") or "—"
        email_lbl = ctk.CTkLabel(
            mid,
            text=email_str,
            font=(FONT_FAMILY, 11),
            text_color=TEXT_SECONDARY,
            anchor="w"
        )
        email_lbl.pack(anchor="w", fill="x")

        # Password Display (Monospace if revealed, Bullet dots if masked)
        raw_pw = entry.get("password", "")
        pw_str = raw_pw if revealed else ("•" * min(14, max(8, len(raw_pw))))
        pw_lbl = ctk.CTkLabel(
            mid,
            text=pw_str,
            font=(MONO_FONT if revealed else FONT_FAMILY, 11),
            text_color=ACCENT_COLOR if revealed else TEXT_MUTED,
            anchor="w"
        )
        pw_lbl.pack(anchor="w", fill="x", pady=(2, 0))

        # === BOTTOM SECTION: Twin Copy Buttons ===
        bot = ctk.CTkFrame(card, fg_color="transparent")
        bot.pack(fill="x", padx=12, pady=(0, 10))

        btn_copy_user = ctk.CTkButton(
            bot,
            text="Copy User",
            height=28,
            corner_radius=6,
            font=(FONT_FAMILY, 10),
            fg_color=BG_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=lambda: self.app.copy_to_clipboard(entry.get("email", ""), label="Username")
        )
        btn_copy_user.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_copy_pass = ctk.CTkButton(
            bot,
            text="Copy Pass",
            height=28,
            corner_radius=6,
            font=(FONT_FAMILY, 10, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=lambda: self.app.copy_to_clipboard(entry.get("password", ""), label="Password")
        )
        btn_copy_pass.pack(side="left", fill="x", expand=True, padx=(4, 0))

        return card

    def toggle_reveal(self, eid: str):
        if eid in self.revealed_cards:
            self.revealed_cards.remove(eid)
        else:
            self.revealed_cards.add(eid)
        self.render_grid()

    # ---------- Context Menu & Modals ----------

    def open_entry_menu(self, entry: dict, anchor_widget):
        """Displays action dialog for an individual entry."""
        menu_win = ctk.CTkToplevel(self)
        menu_win.title("Item Actions")
        menu_win.geometry("260x220")
        menu_win.resizable(False, False)
        menu_win.configure(fg_color=BG_COLOR)
        menu_win.transient(self)
        menu_win.grab_set()

        # Center on screen / near anchor
        x = anchor_widget.winfo_rootx() - 100
        y = anchor_widget.winfo_rooty() + 30
        menu_win.geometry(f"+{max(10, x)}+{max(10, y)}")

        frame = ctk.CTkFrame(menu_win, corner_radius=12, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            frame,
            text=entry.get("service", "Actions"),
            font=(FONT_FAMILY, 13, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(pady=(10, 8), padx=12, anchor="w")

        def _act(func):
            menu_win.destroy()
            func(entry)

        ctk.CTkButton(
            frame,
            text="✏️ Edit Credential",
            font=(FONT_FAMILY, 11),
            fg_color="transparent",
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            anchor="w",
            height=30,
            command=lambda: _act(self.open_edit_modal)
        ).pack(fill="x", padx=8, pady=2)

        ctk.CTkButton(
            frame,
            text="🔍 View Details & Notes",
            font=(FONT_FAMILY, 11),
            fg_color="transparent",
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            anchor="w",
            height=30,
            command=lambda: _act(self.open_details_modal)
        ).pack(fill="x", padx=8, pady=2)

        ctk.CTkButton(
            frame,
            text="🗑️ Delete Credential",
            font=(FONT_FAMILY, 11),
            fg_color="transparent",
            text_color=DANGER_COLOR,
            hover_color=CARD_HOVER_BG,
            anchor="w",
            height=30,
            command=lambda: _act(self.confirm_delete_entry)
        ).pack(fill="x", padx=8, pady=(2, 8))

    # ---------- Add / Edit Entry Modal ----------

    def open_add_modal(self):
        self._open_entry_editor(entry=None, title="Add New Credential")

    def open_edit_modal(self, entry: dict):
        self._open_entry_editor(entry=entry, title="Edit Credential")

    def _open_entry_editor(self, entry: Optional[dict], title: str):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("440x580")
        win.resizable(False, False)
        win.configure(fg_color=BG_COLOR)
        win.transient(self)
        win.grab_set()

        # Center relative to parent
        x = self.winfo_x() + (self.winfo_width() - 440) // 2
        y = self.winfo_y() + (self.winfo_height() - 580) // 2
        win.geometry(f"+{max(10, x)}+{max(10, y)}")

        pad = {"padx": 24, "pady": 4}

        ctk.CTkLabel(
            win,
            text=title,
            font=(FONT_FAMILY, 18, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=24, pady=(20, 10))

        # Category Picker
        ctk.CTkLabel(win, text="Category", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        cats = self.app.data.get("categories", storage.DEFAULT_CATEGORIES)
        current_cat = entry.get("category", cats[0]) if entry else (
            self.app.current_category if self.app.current_category != "All" else cats[0]
        )
        cat_opt = ctk.CTkOptionMenu(
            win,
            values=cats,
            height=34,
            corner_radius=8,
            fg_color=CARD_BG,
            button_color=BORDER_COLOR,
            button_hover_color=ACCENT_COLOR,
            text_color=TEXT_PRIMARY
        )
        cat_opt.set(current_cat)
        cat_opt.pack(fill="x", **pad)

        # Service / Name
        ctk.CTkLabel(win, text="Service / Website", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        srv_entry = ctk.CTkEntry(win, placeholder_text="e.g. GitHub, Google, Slack", height=34, corner_radius=8, border_color=BORDER_COLOR, fg_color=CARD_BG)
        if entry:
            srv_entry.insert(0, entry.get("service", ""))
        srv_entry.pack(fill="x", **pad)

        # Email / Username
        ctk.CTkLabel(win, text="Email / Username", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        email_entry = ctk.CTkEntry(win, placeholder_text="name@example.com or username", height=34, corner_radius=8, border_color=BORDER_COLOR, fg_color=CARD_BG)
        if entry:
            email_entry.insert(0, entry.get("email", ""))
        email_entry.pack(fill="x", **pad)

        # Password + Generator Button
        ctk.CTkLabel(win, text="Password", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        pw_frame = ctk.CTkFrame(win, fg_color="transparent")
        pw_frame.pack(fill="x", **pad)

        pw_entry = ctk.CTkEntry(pw_frame, placeholder_text="Password", height=34, corner_radius=8, border_color=BORDER_COLOR, fg_color=CARD_BG)
        if entry:
            pw_entry.insert(0, entry.get("password", ""))
        pw_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def _generate():
            new_p = gen_password(length=20, use_special=True)
            pw_entry.delete(0, "end")
            pw_entry.insert(0, new_p)
            _check_strength()

        gen_btn = ctk.CTkButton(
            pw_frame,
            text="⚡ Gen",
            width=65,
            height=34,
            corner_radius=8,
            font=(FONT_FAMILY, 11, "bold"),
            fg_color=BG_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            hover_color=CARD_HOVER_BG,
            command=_generate
        )
        gen_btn.pack(side="right")

        strength_lbl = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 10), text_color=TEXT_MUTED)
        strength_lbl.pack(anchor="w", padx=24, pady=(0, 2))

        def _check_strength(e=None):
            p = pw_entry.get()
            score, label = crypto_utils.check_password_strength(p)
            colors = [DANGER_COLOR, "#FF9500", "#FFCC00", "#34C759", SUCCESS_COLOR]
            strength_lbl.configure(text=f"Password Strength: {label}", text_color=colors[min(score, 4)])

        pw_entry.bind("<KeyRelease>", _check_strength)
        _check_strength()

        # Notes
        ctk.CTkLabel(win, text="Notes (Optional)", font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY).pack(anchor="w", **pad)
        notes_box = ctk.CTkTextbox(win, height=65, corner_radius=8, border_width=1, border_color=BORDER_COLOR, fg_color=CARD_BG)
        if entry:
            notes_box.insert("1.0", entry.get("notes", ""))
        notes_box.pack(fill="x", **pad)

        # Save Button
        def _save():
            srv = srv_entry.get().strip()
            em = email_entry.get().strip()
            pw = pw_entry.get()
            cat = cat_opt.get()
            notes = notes_box.get("1.0", "end").strip()

            if not srv:
                messagebox.showerror("Validation Error", "Please provide a Service name.")
                return

            if entry:
                # Update existing
                entry["service"] = srv
                entry["email"] = em
                entry["password"] = pw
                entry["category"] = cat
                entry["notes"] = notes
                entry["updated_at"] = int(time.time())
                ToastNotification(self.app, f"'{srv}' updated.", icon="✏️")
            else:
                # New entry
                new_item = storage.new_entry(cat, srv, em, pw, notes)
                self.app.data.setdefault("entries", []).append(new_item)
                ToastNotification(self.app, f"'{srv}' saved to vault.", icon="✓")

            self.app.save()
            win.destroy()
            self.render_grid()

        save_btn = ctk.CTkButton(
            win,
            text="Save Credential",
            height=38,
            corner_radius=8,
            font=(FONT_FAMILY, 13, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=_save
        )
        save_btn.pack(fill="x", padx=24, pady=(16, 20))

    # ---------- Details Modal ----------

    def open_details_modal(self, entry: dict):
        win = ctk.CTkToplevel(self)
        win.title(entry.get("service", "Credential Details"))
        win.geometry("420x400")
        win.resizable(False, False)
        win.configure(fg_color=BG_COLOR)
        win.transient(self)
        win.grab_set()

        pad = {"padx": 24, "pady": 4}

        ctk.CTkLabel(
            win,
            text=entry.get("service", "Details"),
            font=(FONT_FAMILY, 18, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=24, pady=(20, 4))

        ctk.CTkLabel(
            win,
            text=f"Category: {entry.get('category', 'Uncategorized')}",
            font=(FONT_FAMILY, 11),
            text_color=ACCENT_COLOR
        ).pack(anchor="w", padx=24, pady=(0, 10))

        # Details Card
        card = ctk.CTkFrame(win, corner_radius=12, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        c_pad = {"padx": 16, "pady": 4}

        ctk.CTkLabel(card, text="Username / Email:", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_SECONDARY).pack(anchor="w", **c_pad)
        ctk.CTkLabel(card, text=entry.get("email", "—") or "—", font=(FONT_FAMILY, 12), text_color=TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(0, 6))

        ctk.CTkLabel(card, text="Password:", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_SECONDARY).pack(anchor="w", **c_pad)
        ctk.CTkLabel(card, text=entry.get("password", ""), font=(MONO_FONT, 12), text_color=TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(0, 6))

        ctk.CTkLabel(card, text="Notes:", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_SECONDARY).pack(anchor="w", **c_pad)
        notes_txt = entry.get("notes", "") or "No additional notes."
        ctk.CTkLabel(card, text=notes_txt, font=(FONT_FAMILY, 11), text_color=TEXT_MUTED, wraplength=340, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

    # ---------- Delete Entry ----------

    def confirm_delete_entry(self, entry: dict):
        srv = entry.get("service", "this item")
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete credentials for '{srv}'?"):
            self.app.data["entries"] = [e for e in self.app.data.get("entries", []) if e.get("id") != entry.get("id")]
            self.app.save()
            self.render_grid()
            ToastNotification(self.app, f"'{srv}' deleted.", icon="🗑️")

    # ---------- Settings Modal ----------

    def open_settings_modal(self):
        win = ctk.CTkToplevel(self)
        win.title("DeepStore Preferences & Security")
        win.geometry("540x600")
        win.resizable(False, False)
        win.configure(fg_color=BG_COLOR)
        win.transient(self)
        win.grab_set()

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

        # --- SECTION 1: Windows Authentication & Quick Unlock ---
        sec1 = ctk.CTkFrame(scroll, corner_radius=14, fg_color=CARD_BG, border_width=1, border_color=BORDER_COLOR)
        sec1.pack(fill="x", pady=8, padx=12)

        ctk.CTkLabel(
            sec1,
            text="Windows Authentication & Quick Unlock",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=16, pady=(14, 4))

        username = win_auth.get_current_username()
        has_win_auth = win_auth.windows_auth_available()
        is_cached = win_auth.is_key_stored()

        status_text = f"👤 Windows User: {username}  •  ✓ Active" if has_win_auth else f"👤 Windows User: {username}"
        status_color = SUCCESS_COLOR if has_win_auth else TEXT_MUTED

        ctk.CTkLabel(
            sec1,
            text=status_text,
            font=(FONT_FAMILY, 11),
            text_color=status_color
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Toggle Switch
        win_var = ctk.BooleanVar(value=self.app.meta.get("windows_auth_enabled", False) and is_cached)

        def on_win_toggle():
            val = win_var.get()
            if val:
                if not self.app.key:
                    messagebox.showwarning("Not Unlocked", "Please unlock the vault first before enrolling Windows Quick Unlock.")
                    win_var.set(False)
                    return
                # Enroll / store current key in Windows Credential Manager
                win_auth.store_key(self.app.key)
                self.app.meta["windows_auth_enabled"] = True
                storage.save_meta(self.app.meta)
                ToastNotification(self.app, "Passkey enrolled in Windows Credential Manager.", icon="🔑")
            else:
                win_auth.clear_key()
                self.app.meta["windows_auth_enabled"] = False
                storage.save_meta(self.app.meta)
                ToastNotification(self.app, "Passkey removed from Windows Credential Manager.", icon="🛡️")

        switch = ctk.CTkSwitch(
            sec1,
            text="Enable Windows Password Quick Unlock",
            font=(FONT_FAMILY, 12),
            variable=win_var,
            progress_color=ACCENT_COLOR,
            command=on_win_toggle
        )
        switch.pack(anchor="w", padx=16, pady=(0, 10))

        # Passkey action buttons
        passkey_btns = ctk.CTkFrame(sec1, fg_color="transparent")
        passkey_btns.pack(fill="x", padx=16, pady=(0, 14))

        def resync_passkey():
            if self.app.key:
                win_auth.store_key(self.app.key)
                self.app.meta["windows_auth_enabled"] = True
                storage.save_meta(self.app.meta)
                win_var.set(True)
                ToastNotification(self.app, "Passkey synced to Windows Credential Manager!", icon="✓")

        def clear_passkey():
            win_auth.clear_key()
            self.app.meta["windows_auth_enabled"] = False
            storage.save_meta(self.app.meta)
            win_var.set(False)
            ToastNotification(self.app, "Windows Credential Manager cache cleared.", icon="🗑️")

        ctk.CTkButton(
            passkey_btns,
            text="🔄 Re-sync to Credential Manager",
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
            text="🗑️ Clear Credential Cache",
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

                # Update Windows Credential Manager if active
                if self.app.meta.get("windows_auth_enabled"):
                    win_auth.store_key(new_derived_key)

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

        lock_menu = ctk.CTkOptionMenu(
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
        )
        lock_menu.set(curr_lock_str)
        lock_menu.pack(side="right")

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

        clip_menu = ctk.CTkOptionMenu(
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
        )
        clip_menu.set(curr_clip_str)
        clip_menu.pack(side="right")

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
