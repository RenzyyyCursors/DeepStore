"""
ui.py
-----
customtkinter interface: minimalist, macOS-flavored.

Screens:
  - LoginFrame: first-run master password setup, or unlock (password / Touch ID)
  - VaultFrame: category bar (add/delete categories) + "All" tab +
                4x4 grid of password cards with copy-to-clipboard, +
                dark/light toggle, add/edit/delete entries, search, pagination.
"""

import customtkinter as ctk
from tkinter import messagebox
import secrets
import string

from . import storage
from . import biometrics

FONT_FAMILY = "SF Pro Text"          # falls back gracefully if unavailable
GRID_COLS = 4
GRID_ROWS = 4
PAGE_SIZE = GRID_COLS * GRID_ROWS

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def gen_password(length=20):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SecureVaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SecureVault")
        self.geometry("980x680")
        self.minsize(820, 560)

        self.key = None
        self.data = None
        self.current_category = "All"
        self.page = 0
        self.category_edit_mode = False
        self.search_query = ""

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.show_login()

    # ---------------- navigation ----------------

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_login(self):
        self.clear_container()
        LoginFrame(self.container, self).pack(fill="both", expand=True)

    def show_vault(self):
        self.clear_container()
        self.vault_frame = VaultFrame(self.container, self)
        self.vault_frame.pack(fill="both", expand=True)

    def lock(self):
        self.key = None
        self.data = None
        self.show_login()

    # ---------------- persistence ----------------

    def save(self):
        storage.save_data(self.data, self.key)

    def copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # keep it on the clipboard after the window loses focus


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, app: SecureVaultApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.first_run = not storage.vault_exists()

        wrapper = ctk.CTkFrame(self, corner_radius=20)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        pad = {"padx": 40, "pady": 10}

        title = "Create Your Vault" if self.first_run else "Unlock SecureVault"
        ctk.CTkLabel(wrapper, text="🔒", font=(FONT_FAMILY, 40)).grid(
            row=0, column=0, columnspan=2, pady=(30, 0))
        ctk.CTkLabel(wrapper, text=title, font=(FONT_FAMILY, 22, "bold")).grid(
            row=1, column=0, columnspan=2, pady=(5, 20))

        self.pw_entry = ctk.CTkEntry(wrapper, placeholder_text="Master password",
                                      show="•", width=280)
        self.pw_entry.grid(row=2, column=0, columnspan=2, **pad)
        self.pw_entry.bind("<Return>", lambda e: self.submit())

        if self.first_run:
            self.pw_confirm = ctk.CTkEntry(wrapper, placeholder_text="Confirm password",
                                            show="•", width=280)
            self.pw_confirm.grid(row=3, column=0, columnspan=2, **pad)
            self.pw_confirm.bind("<Return>", lambda e: self.submit())
            btn_row = 4
        else:
            btn_row = 3

        self.error_label = ctk.CTkLabel(wrapper, text="", text_color="#e5484d")
        self.error_label.grid(row=btn_row, column=0, columnspan=2)

        action_text = "Create Vault" if self.first_run else "Unlock"
        ctk.CTkButton(wrapper, text=action_text, width=280, command=self.submit).grid(
            row=btn_row + 1, column=0, columnspan=2, padx=40, pady=(5, 10))

        if not self.first_run and biometrics.touch_id_available() and \
                storage.load_meta().get("touch_id_enabled"):
            ctk.CTkButton(wrapper, text="Unlock with Touch ID", width=280,
                          fg_color="transparent", border_width=1,
                          command=self.touch_id_unlock).grid(
                row=btn_row + 2, column=0, columnspan=2, padx=40, pady=(0, 30))
        else:
            ctk.CTkLabel(wrapper, text="").grid(row=btn_row + 2, column=0, pady=10)

        self.pw_entry.focus()

    def submit(self):
        password = self.pw_entry.get()
        if not password:
            self.error_label.configure(text="Enter a master password.")
            return

        if self.first_run:
            confirm = self.pw_confirm.get()
            if len(password) < 8:
                self.error_label.configure(text="Use at least 8 characters.")
                return
            if password != confirm:
                self.error_label.configure(text="Passwords don't match.")
                return
            key = storage.create_vault(password)
            self.app.key = key
            self.app.data = storage.load_data(key)
            self.maybe_offer_touch_id(key)
            self.app.show_vault()
        else:
            try:
                key = storage.unlock_vault(password)
            except Exception:
                self.error_label.configure(text="Incorrect password.")
                return
            self.app.key = key
            self.app.data = storage.load_data(key)
            self.app.show_vault()

    def maybe_offer_touch_id(self, key):
        if not biometrics.touch_id_available():
            return
        if messagebox.askyesno(
                "Enable Touch ID?",
                "Use Touch ID as a quick way to unlock SecureVault next time?\n\n"
                "Your master password will still work as a fallback."):
            biometrics.store_key(key)
            storage.save_meta({"touch_id_enabled": True})

    def touch_id_unlock(self):
        if not biometrics.authenticate_touch_id():
            self.error_label.configure(text="Touch ID failed. Use your password.")
            return
        key = biometrics.retrieve_key()
        if not key:
            self.error_label.configure(text="Touch ID key not found. Use your password.")
            return
        try:
            self.app.data = storage.load_data(key)
        except Exception:
            self.error_label.configure(text="Could not unlock vault.")
            return
        self.app.key = key
        self.app.show_vault()


class VaultFrame(ctk.CTkFrame):
    def __init__(self, master, app: SecureVaultApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.revealed = set()  # entry ids currently showing plaintext password

        self.build_top_bar()
        self.build_category_bar()
        self.build_toolbar()
        self.build_grid_area()

        self.refresh()

    # ---------- top bar ----------

    def build_top_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(20, 5))

        ctk.CTkLabel(bar, text="SecureVault", font=(FONT_FAMILY, 24, "bold")).pack(side="left")

        ctk.CTkButton(bar, text="Lock", width=70, fg_color="transparent",
                      border_width=1, command=self.app.lock).pack(side="right", padx=(8, 0))

        self.appearance_switch = ctk.CTkSegmentedButton(
            bar, values=["Light", "System", "Dark"], command=self.set_appearance)
        self.appearance_switch.set("System")
        self.appearance_switch.pack(side="right", padx=(8, 0))

    def set_appearance(self, value):
        ctk.set_appearance_mode(value)

    # ---------- category bar ----------

    def build_category_bar(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="x", padx=24, pady=(5, 0))

        self.cat_scroll = ctk.CTkScrollableFrame(wrap, height=50, orientation="horizontal",
                                                  fg_color="transparent")
        self.cat_scroll.pack(side="left", fill="x", expand=True)

        self.edit_btn = ctk.CTkButton(wrap, text="Edit", width=60, fg_color="transparent",
                                       border_width=1, command=self.toggle_edit_mode)
        self.edit_btn.pack(side="right", padx=(8, 0))

    def toggle_edit_mode(self):
        self.app.category_edit_mode = not self.app.category_edit_mode
        self.edit_btn.configure(text="Done" if self.app.category_edit_mode else "Edit")
        self.render_categories()

    def render_categories(self):
        for w in self.cat_scroll.winfo_children():
            w.destroy()

        chips = ["All"] + self.app.data["categories"]
        for name in chips:
            chip_frame = ctk.CTkFrame(self.cat_scroll, fg_color="transparent")
            chip_frame.pack(side="left", padx=4)

            is_selected = (name == self.app.current_category)
            btn = ctk.CTkButton(
                chip_frame, text=name, corner_radius=16, height=32,
                fg_color=("#dbdbdb", "#333333") if not is_selected else ("#3a7ebf", "#1f538d"),
                text_color=("black", "white") if not is_selected else "white",
                command=lambda n=name: self.select_category(n))
            btn.pack(side="left")

            if self.app.category_edit_mode and name not in ("All", "Uncategorized"):
                ctk.CTkButton(chip_frame, text="✕", width=24, height=24, corner_radius=12,
                              fg_color="#e5484d", hover_color="#c53030",
                              command=lambda n=name: self.delete_category(n)).pack(
                    side="left", padx=(2, 0))

        if self.app.category_edit_mode:
            ctk.CTkButton(self.cat_scroll, text="+ New Category", width=120, height=32,
                          fg_color="transparent", border_width=1,
                          command=self.add_category).pack(side="left", padx=4)

    def select_category(self, name):
        self.app.current_category = name
        self.app.page = 0
        self.render_categories()
        self.render_grid()

    def add_category(self):
        dialog = ctk.CTkInputDialog(text="Category name:", title="New Category")
        name = dialog.get_input()
        if name:
            storage.add_category(self.app.data, name)
            self.app.save()
            self.render_categories()

    def delete_category(self, name):
        if messagebox.askyesno("Delete Category",
                                f"Delete '{name}'? Entries move to Uncategorized."):
            storage.delete_category(self.app.data, name)
            if self.app.current_category == name:
                self.app.current_category = "All"
            self.app.save()
            self.render_categories()
            self.render_grid()

    # ---------- toolbar (search + add) ----------

    def build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(12, 5))

        self.search_entry = ctk.CTkEntry(bar, placeholder_text="Search...", width=240)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", self.on_search)

        ctk.CTkButton(bar, text="+ Add Password", command=self.add_entry_dialog).pack(
            side="right")

    def on_search(self, event=None):
        self.app.search_query = self.search_entry.get().strip().lower()
        self.app.page = 0
        self.render_grid()

    # ---------- grid ----------

    def build_grid_area(self):
        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True, padx=24, pady=(5, 5))

        self.pager = ctk.CTkFrame(self, fg_color="transparent")
        self.pager.pack(fill="x", padx=24, pady=(0, 16))

    def get_filtered_entries(self):
        entries = self.app.data["entries"]
        if self.app.current_category != "All":
            entries = [e for e in entries if e["category"] == self.app.current_category]
        if self.app.search_query:
            q = self.app.search_query
            entries = [e for e in entries if q in e["service"].lower() or q in e["email"].lower()]
        return entries

    def render_grid(self):
        for w in self.grid_container.winfo_children():
            w.destroy()
        for w in self.pager.winfo_children():
            w.destroy()

        entries = self.get_filtered_entries()
        start = self.app.page * PAGE_SIZE
        page_entries = entries[start:start + PAGE_SIZE]

        for col in range(GRID_COLS):
            self.grid_container.grid_columnconfigure(col, weight=1, uniform="col")
        for row in range(GRID_ROWS):
            self.grid_container.grid_rowconfigure(row, weight=1, uniform="row")

        if not entries:
            ctk.CTkLabel(self.grid_container, text="No passwords yet — click '+ Add Password'.",
                         text_color="gray").grid(row=0, column=0, columnspan=GRID_COLS, pady=40)
        else:
            for i, entry in enumerate(page_entries):
                r, c = divmod(i, GRID_COLS)
                card = self.build_card(self.grid_container, entry)
                card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

        total_pages = max(1, (len(entries) + PAGE_SIZE - 1) // PAGE_SIZE)
        if total_pages > 1:
            ctk.CTkButton(self.pager, text="◀ Prev", width=80,
                          command=self.prev_page, state=("normal" if self.app.page > 0 else "disabled")
                          ).pack(side="left")
            ctk.CTkLabel(self.pager, text=f"Page {self.app.page + 1} of {total_pages}").pack(
                side="left", padx=12)
            ctk.CTkButton(self.pager, text="Next ▶", width=80,
                          command=self.next_page,
                          state=("normal" if self.app.page < total_pages - 1 else "disabled")
                          ).pack(side="left")

    def prev_page(self):
        self.app.page = max(0, self.app.page - 1)
        self.render_grid()

    def next_page(self):
        self.app.page += 1
        self.render_grid()

    def build_card(self, parent, entry):
        card = ctk.CTkFrame(parent, corner_radius=16, border_width=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(top, text=entry["service"], font=(FONT_FAMILY, 15, "bold"),
                     anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(top, text="⋯", width=24, height=24, fg_color="transparent",
                      command=lambda e=entry: self.entry_menu(e)).pack(side="right")

        # email row
        email_row = ctk.CTkFrame(card, fg_color="transparent")
        email_row.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(email_row, text=entry["email"], font=(FONT_FAMILY, 12),
                     text_color="gray", anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(email_row, text="Copy", width=50, height=22, font=(FONT_FAMILY, 10),
                      command=lambda e=entry: self.app.copy_to_clipboard(e["email"])).pack(side="right")

        # password row
        pw_row = ctk.CTkFrame(card, fg_color="transparent")
        pw_row.pack(fill="x", padx=12, pady=(2, 10))
        revealed = entry["id"] in self.revealed
        pw_display = entry["password"] if revealed else "•" * 10
        pw_label = ctk.CTkLabel(pw_row, text=pw_display, font=(FONT_FAMILY, 12), anchor="w")
        pw_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(pw_row, text=("Hide" if revealed else "Show"), width=45, height=22,
                      font=(FONT_FAMILY, 10),
                      command=lambda e=entry: self.toggle_reveal(e)).pack(side="right", padx=(4, 0))
        ctk.CTkButton(pw_row, text="Copy", width=50, height=22, font=(FONT_FAMILY, 10),
                      command=lambda e=entry: self.app.copy_to_clipboard(e["password"])).pack(
            side="right")

        return card

    def toggle_reveal(self, entry):
        if entry["id"] in self.revealed:
            self.revealed.remove(entry["id"])
        else:
            self.revealed.add(entry["id"])
        self.render_grid()

    def entry_menu(self, entry):
        win = ctk.CTkToplevel(self)
        win.title(entry["service"])
        win.geometry("300x160")
        win.grab_set()
        ctk.CTkButton(win, text="Edit", command=lambda: (win.destroy(), self.edit_entry_dialog(entry))).pack(
            fill="x", padx=20, pady=(20, 8))
        ctk.CTkButton(win, text="Delete", fg_color="#e5484d", hover_color="#c53030",
                      command=lambda: (win.destroy(), self.delete_entry(entry))).pack(
            fill="x", padx=20, pady=8)
        ctk.CTkButton(win, text="Cancel", fg_color="transparent", border_width=1,
                      command=win.destroy).pack(fill="x", padx=20, pady=8)

    def delete_entry(self, entry):
        if messagebox.askyesno("Delete Password", f"Delete the entry for '{entry['service']}'?"):
            self.app.data["entries"] = [e for e in self.app.data["entries"] if e["id"] != entry["id"]]
            self.app.save()
            self.render_grid()

    def add_entry_dialog(self):
        self.entry_form_dialog(title="Add Password")

    def edit_entry_dialog(self, entry):
        self.entry_form_dialog(title="Edit Password", entry=entry)

    def entry_form_dialog(self, title, entry=None):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("380x420")
        win.grab_set()

        pad = {"padx": 24, "pady": 8}

        ctk.CTkLabel(win, text=title, font=(FONT_FAMILY, 18, "bold")).pack(pady=(20, 10))

        ctk.CTkLabel(win, text="Category").pack(anchor="w", **pad)
        cat_var = ctk.StringVar(value=(entry["category"] if entry else self.app.data["categories"][0]))
        cat_menu = ctk.CTkOptionMenu(win, values=self.app.data["categories"], variable=cat_var)
        cat_menu.pack(fill="x", padx=24)

        ctk.CTkLabel(win, text="Service / Website").pack(anchor="w", **pad)
        service_entry = ctk.CTkEntry(win)
        service_entry.pack(fill="x", padx=24)
        if entry:
            service_entry.insert(0, entry["service"])

        ctk.CTkLabel(win, text="Email / Username").pack(anchor="w", **pad)
        email_entry = ctk.CTkEntry(win)
        email_entry.pack(fill="x", padx=24)
        if entry:
            email_entry.insert(0, entry["email"])

        ctk.CTkLabel(win, text="Password").pack(anchor="w", **pad)
        pw_row = ctk.CTkFrame(win, fg_color="transparent")
        pw_row.pack(fill="x", padx=24)
        pw_entry = ctk.CTkEntry(pw_row, show="•")
        pw_entry.pack(side="left", fill="x", expand=True)
        if entry:
            pw_entry.insert(0, entry["password"])

        def generate():
            pw_entry.delete(0, "end")
            pw_entry.insert(0, gen_password())

        ctk.CTkButton(pw_row, text="Generate", width=80, command=generate).pack(side="left", padx=(8, 0))

        def save():
            service = service_entry.get().strip()
            email = email_entry.get().strip()
            password = pw_entry.get()
            category = cat_var.get()
            if not service or not password:
                messagebox.showerror("Missing info", "Service and password are required.")
                return
            if entry:
                entry.update(category=category, service=service, email=email, password=password)
            else:
                self.app.data["entries"].append(
                    storage.new_entry(category, service, email, password))
            self.app.save()
            win.destroy()
            self.render_grid()

        ctk.CTkButton(win, text="Save", command=save).pack(fill="x", padx=24, pady=(20, 10))

    # ---------- refresh everything ----------

    def refresh(self):
        self.render_categories()
        self.render_grid()
