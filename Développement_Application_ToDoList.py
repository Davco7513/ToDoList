import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
import jwt
from datetime import datetime, timedelta
import hashlib

# Configuration JWT
SECRET_KEY = "violon999PMS"  # À changer en production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Initialisation des fichiers JSON pour stocker les utilisateurs et les tâches
USER_FILE = "users.json"
TASK_FILE = "tasks.json"

# Création des fichiers s'ils n'existent pas
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(TASK_FILE):
    with open(TASK_FILE, "w") as f:
        json.dump([], f)


# --- Gestion des utilisateurs avec JWT ---

def load_users():
    """Charge les utilisateurs depuis le fichier JSON."""
    with open(USER_FILE, "r") as f:
        return json.load(f)


def save_users(users):
    """Enregistre les utilisateurs dans le fichier JSON."""
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)


def hash_password(password):
    """Hash le mot de passe avec SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Crée un token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """Vérifie la validité d'un token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def register_user(first_name, last_name, email, password):
    """Inscrit un nouvel utilisateur si l'email n'est pas déjà utilisé."""
    users = load_users()
    if email in users:
        return False

    # Hashage du mot de passe avant stockage
    hashed_password = hash_password(password)

    users[email] = {
        "first_name": first_name,
        "last_name": last_name,
        "password": hashed_password  # On stocke le hash, pas le mot de passe en clair
    }
    save_users(users)
    return True


def authenticate_user(email, password):
    """Vérifie si les identifiants sont corrects et retourne un token JWT."""
    users = load_users()
    if email not in users:
        return None

    # Vérification du mot de passe hashé
    hashed_password = hash_password(password)
    if users[email]["password"] == hashed_password:
        # Création du token JWT
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": email},
            expires_delta=access_token_expires
        )
        return access_token
    return None


def is_valid_email(email):
    """Vérifie si l'email contient un @."""
    return "@" in email


# --- Gestion des tâches (inchangée) ---

def load_tasks():
    """Charge la liste des tâches depuis le fichier JSON."""
    with open(TASK_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_tasks(tasks):
    """Enregistre la liste des tâches dans le fichier JSON."""
    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=4)


def add_task(email, title, description, status="En cours"):
    """Ajoute une nouvelle tâche avec vérification globale du nom."""
    tasks = load_tasks()

    # Si tasks est une liste (ancien format), la convertir en dictionnaire
    if isinstance(tasks, list):
        tasks = {"default_user": tasks}  # Conversion vers le nouveau format
        save_tasks(tasks)  # Sauvegarder immédiatement le nouveau format

    # Vérifier si une tâche avec le même titre existe déjà
    for user_tasks in tasks.values():
        for task in user_tasks:
            if task["title"].lower() == title.lower():
                return False

    # Si le titre est unique, ajouter la tâche
    if email not in tasks:
        tasks[email] = []

    tasks[email].append({"title": title, "description": description, "status": status})
    save_tasks(tasks)
    return True


def get_tasks(email, status_filter=None):
    """Retourne les tâches d'un utilisateur, filtrées par statut si demandé."""
    tasks = load_tasks()

    # Gestion de la compatibilité avec l'ancien format
    if isinstance(tasks, list):
        if status_filter and status_filter != "Tout":
            return [t for t in tasks if t["status"] == status_filter]
        return tasks

    user_tasks = tasks.get(email, [])
    if status_filter and status_filter != "Tout":
        return [t for t in user_tasks if t["status"] == status_filter]
    return user_tasks


def delete_task(email, index):
    """Supprime une tâche d'un utilisateur spécifique."""
    tasks = load_tasks()

    # Gestion de la compatibilité avec l'ancien format
    if isinstance(tasks, list):
        if 0 <= index < len(tasks):
            del tasks[index]
            save_tasks(tasks)
        return

    if email in tasks and 0 <= index < len(tasks[email]):
        del tasks[email][index]
        save_tasks(tasks)


def update_task(email, index, title, description, status):
    """Met à jour une tâche d'un utilisateur spécifique."""
    tasks = load_tasks()

    # Gestion de la compatibilité avec l'ancien format
    if isinstance(tasks, list):
        if 0 <= index < len(tasks):
            # Vérification du nom unique
            for i, task in enumerate(tasks):
                if task["title"].lower() == title.lower() and i != index:
                    return False
            tasks[index] = {"title": title, "description": description, "status": status}
            save_tasks(tasks)
            return True
        return False

    if email in tasks and 0 <= index < len(tasks[email]):
        # Vérification du nom unique
        for user_email, user_tasks in tasks.items():
            for i, task in enumerate(user_tasks):
                if task["title"].lower() == title.lower() and not (user_email == email and i == index):
                    return False
        tasks[email][index] = {"title": title, "description": description, "status": status}
        save_tasks(tasks)
        return True
    return False


# --- Interface utilisateur avec Tkinter ---

class TaskApp:
    def __init__(self, root):
        """Initialise l'application avec l'écran de connexion."""
        self.root = root
        self.current_user = None
        self.access_token = None  # Stockage du token JWT
        self.root.title("Gestionnaire de tâches")
        self.filter_var = tk.StringVar(value="Tout")

        # --- Interface de connexion ---
        self.login_frame = tk.Frame(root)
        tk.Label(self.login_frame, text="Email:").grid(row=0, column=0)
        self.email_entry = tk.Entry(self.login_frame)
        self.email_entry.grid(row=0, column=1)

        tk.Label(self.login_frame, text="Mot de passe:").grid(row=1, column=0)
        self.password_entry = tk.Entry(self.login_frame, show="*")
        self.password_entry.grid(row=1, column=1)

        self.login_btn = tk.Button(self.login_frame, text="Se connecter", command=self.login)
        self.login_btn.grid(row=2, column=0, columnspan=2)

        self.register_btn = tk.Button(self.login_frame, text="S'inscrire", command=self.show_register_form)
        self.register_btn.grid(row=3, column=0, columnspan=2)

        self.login_frame.pack()

    def show_register_form(self):
        """Affiche le formulaire d'inscription."""
        self.login_frame.pack_forget()

        self.register_frame = tk.Frame(self.root)

        tk.Label(self.register_frame, text="Prénom:").grid(row=0, column=0)
        self.first_name_entry = tk.Entry(self.register_frame)
        self.first_name_entry.grid(row=0, column=1)

        tk.Label(self.register_frame, text="Nom:").grid(row=1, column=0)
        self.last_name_entry = tk.Entry(self.register_frame)
        self.last_name_entry.grid(row=1, column=1)

        tk.Label(self.register_frame, text="Email:").grid(row=2, column=0)
        self.register_email_entry = tk.Entry(self.register_frame)
        self.register_email_entry.grid(row=2, column=1)

        tk.Label(self.register_frame, text="Mot de passe:").grid(row=3, column=0)
        self.register_password_entry = tk.Entry(self.register_frame, show="*")
        self.register_password_entry.grid(row=3, column=1)

        self.submit_btn = tk.Button(self.register_frame, text="S'inscrire", command=self.register)
        self.submit_btn.grid(row=4, column=0, pady=10)

        self.back_btn = tk.Button(self.register_frame, text="Retour", command=self.back_to_login)
        self.back_btn.grid(row=4, column=1, pady=10)

        self.register_frame.pack()

    def back_to_login(self):
        """Retourne à l'écran de connexion."""
        self.register_frame.pack_forget()
        self.login_frame.pack()

    def login(self):
        """Vérifie l'authentification et charge l'interface principale en cas de succès."""
        email = self.email_entry.get()
        password = self.password_entry.get()

        if not is_valid_email(email):
            messagebox.showerror("Erreur", "L'adresse email doit contenir un @")
            return

        token = authenticate_user(email, password)
        if token:
            self.access_token = token
            payload = verify_token(token)
            if payload:
                self.current_user = payload.get("sub")  # email de l'utilisateur
                self.login_frame.destroy()
                self.show_main_app()
            else:
                messagebox.showerror("Erreur", "Session expirée, veuillez vous reconnecter")
        else:
            messagebox.showerror("Erreur", "Identifiants incorrects")

    def register(self):
        """Inscrit un nouvel utilisateur."""
        first_name = self.first_name_entry.get()
        last_name = self.last_name_entry.get()
        email = self.register_email_entry.get()
        password = self.register_password_entry.get()

        if not all([first_name, last_name, email, password]):
            messagebox.showerror("Erreur", "Veuillez remplir tous les champs")
            return

        if not is_valid_email(email):
            messagebox.showerror("Erreur", "L'adresse email doit contenir un @")
            return

        if register_user(first_name, last_name, email, password):
            messagebox.showinfo("Succès", "Inscription réussie")
            self.register_frame.pack_forget()
            self.login_frame.pack()
            # Pré-remplir l'email dans le champ de connexion
            self.email_entry.delete(0, tk.END)
            self.email_entry.insert(0, email)
        else:
            messagebox.showerror("Erreur", "Email déjà utilisé")

    def check_auth(self):
        """Vérifie si l'utilisateur est toujours authentifié."""
        if not self.access_token:
            return False

        payload = verify_token(self.access_token)
        if not payload:
            messagebox.showerror("Session expirée", "Votre session a expiré, veuillez vous reconnecter")
            self.main_frame.destroy()
            self.__init__(self.root)
            return False
        return True

    def show_main_app(self):
        """Affiche l'interface principale de gestion des tâches."""
        if not self.check_auth():
            return

        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack()

        # --- Formulaire de gestion des tâches ---
        tk.Label(self.main_frame, text="Titre:").grid(row=0, column=0)
        self.title_entry = tk.Entry(self.main_frame)
        self.title_entry.grid(row=0, column=1)

        tk.Label(self.main_frame, text="Description:").grid(row=1, column=0)
        self.desc_entry = tk.Entry(self.main_frame)
        self.desc_entry.grid(row=1, column=1)

        tk.Label(self.main_frame, text="Statut:").grid(row=2, column=0)
        self.status_var = tk.StringVar(value="En cours")
        self.status_menu = ttk.Combobox(self.main_frame, textvariable=self.status_var, values=["En cours", "Terminé"],
                                        state="readonly")
        self.status_menu.grid(row=2, column=1)

        self.add_btn = tk.Button(self.main_frame, text="Ajouter", command=self.add_task)
        self.add_btn.grid(row=3, column=0)

        self.update_btn = tk.Button(self.main_frame, text="Modifier", command=self.update_selected_task)
        self.update_btn.grid(row=3, column=1)

        self.delete_btn = tk.Button(self.main_frame, text="Supprimer", command=self.delete_selected_task)
        self.delete_btn.grid(row=3, column=2)

        # --- Liste des tâches ---
        self.task_list = ttk.Treeview(self.main_frame, columns=("Title", "Description", "Status"), show='headings')
        self.task_list.heading("Title", text="Titre")
        self.task_list.heading("Description", text="Description")
        self.task_list.heading("Status", text="Statut")
        self.task_list.grid(row=4, column=0, columnspan=3)

        self.task_list.bind("<ButtonRelease-1>", self.select_task)

        # --- Filtre des tâches ---
        self.filter_menu = ttk.Combobox(self.main_frame, textvariable=self.filter_var,
                                        values=["Tout", "En cours", "Terminé"], state="readonly")
        self.filter_menu.grid(row=5, column=0)
        self.filter_menu.bind("<<ComboboxSelected>>", lambda e: self.refresh_tasks())

        self.refresh_tasks()

    def add_task(self):
        """Ajoute une tâche avec vérification globale du nom."""
        if not self.check_auth():
            return

        title = self.title_entry.get()
        description = self.desc_entry.get()
        status = self.status_var.get()

        if title and description:
            if add_task(self.current_user, title, description, status):
                self.refresh_tasks()
                messagebox.showinfo("Succès", "Tâche ajoutée")
            else:
                messagebox.showerror("Erreur", "Ce nom de tâche est déjà utilisé par un autre utilisateur")
        else:
            messagebox.showerror("Erreur", "Veuillez remplir tous les champs")

    def update_selected_task(self):
        """Met à jour une tâche sélectionnée."""
        if not self.check_auth():
            return

        selected_item = self.task_list.selection()
        if selected_item:
            index = int(self.task_list.index(selected_item[0]))
            if update_task(self.current_user, index,
                           self.title_entry.get(),
                           self.desc_entry.get(),
                           self.status_var.get()):
                self.refresh_tasks()
                messagebox.showinfo("Succès", "Tâche modifiée")
            else:
                messagebox.showerror("Erreur", "Ce nom de tâche est déjà utilisé")

    def delete_selected_task(self):
        """Supprime une tâche sélectionnée."""
        if not self.check_auth():
            return

        selected_item = self.task_list.selection()
        if selected_item:
            index = int(self.task_list.index(selected_item[0]))
            delete_task(self.current_user, index)
            self.refresh_tasks()
            messagebox.showinfo("Succès", "Tâche supprimée")

    def select_task(self, event):
        """Remplit les champs avec la tâche sélectionnée."""
        selected_item = self.task_list.selection()
        if selected_item:
            values = self.task_list.item(selected_item[0], "values")
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, values[0])
            self.desc_entry.delete(0, tk.END)
            self.desc_entry.insert(0, values[1])
            self.status_var.set(values[2])

    def refresh_tasks(self):
        """Actualise l'affichage des tâches."""
        if not self.check_auth():
            return

        for row in self.task_list.get_children():
            self.task_list.delete(row)
        for i, t in enumerate(get_tasks(self.current_user, self.filter_var.get())):
            self.task_list.insert("", "end", iid=str(i), values=(t["title"], t["description"], t["status"]))


if __name__ == "__main__":
    root = tk.Tk()
    app = TaskApp(root)
    root.mainloop()