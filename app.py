import tkinter as tk
from tkinter import ttk, messagebox
import requests
import io
import sqlite3
import os
import sys # (v1.0.4): Nötig für den .exe-Build (resource_path)

try:
    from PIL import Image, ImageTk
except ImportError:
    print("Fehler: 'Pillow' ist nicht installiert. Bitte installiere es mit 'pip install Pillow'")
    exit()

# --- 1. Konfiguration & Globale Variablen ---

API_KEY = "HIERHER MIT DEINEM API SCHLÜSSEL"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w300" 
DB_NAME = 'media_tracker.db'

# --- Session-Variablen ---
current_results = []
watched_media_data = []
watchlist_media_data = []
current_selected_media = None
current_user_id = None
current_user_name = None

# --- Globale Widget-Referenzen ---
root = None
label_poster = None
label_info = None
tree_seasons_episodes = None
frame_tree_container = None
listbox_watched = None
listbox_search_results = None
listbox_watchlist = None 
notebook = None
frame_search_list = None
media_type_var = None
entry_search = None
frame_profile_selector = None
episode_cache = {}

button_add_to_watchlist = None
button_mark_watched = None
button_remove_from_watchlist = None
button_remove_from_watched = None
button_find_similar = None


# --- 2. NEUE Hilfsfunktion für .exe-Build (v1.0.4) ---
def resource_path(relative_path):
    """ 
    Holt den absoluten Pfad zu einer Ressource (z.B. Logo).
    Funktioniert sowohl im Entwicklungs-Modus (.py) als auch
    in der gebündelten .exe-Datei (PyInstaller).
    """
    try:
        # PyInstaller erstellt einen temporären Ordner und speichert den Pfad in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Im Entwicklungs-Modus ist der base_path einfach das aktuelle Verzeichnis
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- 3. "Übersetzer"-Funktion (Unverändert) ---
def normalize_media_data(item, media_type):
    if media_type == 'movie':
        return { 'id': item.get('id'), 'title': item.get('title', 'Kein Titel'),
                 'release_date': item.get('release_date', '----'), 'overview': item.get('overview', 'k.A.'),
                 'poster_path': item.get('poster_path'), 'media_type': 'movie' }
    elif media_type == 'tv':
        return { 'id': item.get('id'), 'title': item.get('name', 'Kein Titel'),
                 'release_date': item.get('first_air_date', '----'), 'overview': item.get('overview', 'k.A.'),
                 'poster_path': item.get('poster_path'), 'media_type': 'tv' }
    return None

# --- 4. Datenbank-Funktionen (Unverändert zu v1.0.2) ---
def db_init():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS watched_media (
        watch_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        tmdb_id INTEGER NOT NULL, title TEXT NOT NULL, release_date TEXT,
        overview TEXT, poster_path TEXT, media_type TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        UNIQUE(user_id, tmdb_id, media_type)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS watchlist_media (
        watch_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        tmdb_id INTEGER NOT NULL, title TEXT NOT NULL, release_date TEXT,
        overview TEXT, poster_path TEXT, media_type TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        UNIQUE(user_id, tmdb_id, media_type)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS watched_episodes (
        episode_watch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        show_tmdb_id INTEGER NOT NULL,
        season_number INTEGER NOT NULL,
        episode_number INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        UNIQUE(user_id, show_tmdb_id, season_number, episode_number)
    )''')
    
    try:
        cursor.execute("SELECT user_id, media_type FROM watched_media LIMIT 1")
    except sqlite3.OperationalError:
        print("Führe Altdaten-Migration für watched_media durch...")
        try: cursor.execute("ALTER TABLE watched_media ADD COLUMN media_type TEXT NOT NULL DEFAULT 'movie'")
        except: pass
        try:
            cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (1, 'Default User')")
            cursor.execute("ALTER TABLE watched_media ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
        except: pass
    
    conn.commit()
    conn.close()
    print("Datenbank-Initialisierung abgeschlossen (v1.0).")

def db_get_users():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY username")
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    except Exception as e:
        print(f"Fehler beim Laden der User: {e}"); return []

def db_create_user(username):
    if not username.strip(): return None, "Benutzername darf nicht leer sein."
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username) VALUES (?)", (username.strip(),))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id, "Benutzer erstellt."
    except sqlite3.IntegrityError: return None, "Benutzername existiert bereits."
    except Exception as e: return None, f"Fehler: {e}"

def db_remove_from_watchlist():
    global current_selected_media, current_user_id
    if not current_selected_media:
        label_info.config(text="Kein Medium ausgewählt.")
        return
    if not current_user_id:
        label_info.config(text="Kein Benutzer angemeldet.")
        return
        
    tmdb_id = current_selected_media['id']
    media_type = current_selected_media['media_type']
    
    if not messagebox.askyesno("Löschen", f"Soll '{current_selected_media['title']}' wirklich aus deiner 'Noch Sehen'-Liste entfernt werden?", parent=root):
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM watchlist_media WHERE user_id = ? AND tmdb_id = ? AND media_type = ?",
            (current_user_id, tmdb_id, media_type)
        )
            
        conn.commit()
        conn.close()
        
        label_info.config(text=f"'{current_selected_media['title']}' wurde aus 'Noch Sehen' entfernt.")
        load_watchlist_media() 
        
    except Exception as e:
        label_info.config(text=f"Fehler beim Löschen: {e}")

def db_mark_as_watched():
    global current_selected_media, current_user_id
    if not current_selected_media:
        label_info.config(text="Kein Medium ausgewählt.")
        return
    if not current_user_id:
        label_info.config(text="Kein Benutzer angemeldet.")
        return
    
    try:
        tmdb_id = current_selected_media['id']; title = current_selected_media['title']
        release_date = current_selected_media['release_date']; overview = current_selected_media['overview']
        poster_path = current_selected_media['poster_path']; media_type = current_selected_media['media_type']
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR IGNORE INTO watched_media 
        (user_id, tmdb_id, title, release_date, overview, poster_path, media_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (current_user_id, tmdb_id, title, release_date, overview, poster_path, media_type))
        
        cursor.execute(
            "DELETE FROM watchlist_media WHERE user_id = ? AND tmdb_id = ? AND media_type = ?",
            (current_user_id, tmdb_id, media_type)
        )
            
        conn.commit()
        conn.close()
        
        label_info.config(text=f"'{title}' wurde als 'gesehen' gespeichert!")
        load_watched_media() 
        load_watchlist_media() 

    except Exception as e:
        label_info.config(text=f"Fehler beim Speichern: {e}")

def db_remove_from_watched():
    global current_selected_media, current_user_id
    if not current_selected_media:
        label_info.config(text="Kein Medium ausgewählt.")
        return
    if not current_user_id:
        label_info.config(text="Kein Benutzer angemeldet.")
        return
        
    tmdb_id = current_selected_media['id']
    media_type = current_selected_media['media_type']
    
    if not messagebox.askyesno("Löschen", f"Soll '{current_selected_media['title']}' wirklich aus deiner 'Gesehen'-Liste entfernt werden?\n\n(Alle gesehenen Episoden werden ebenfalls zurückgesetzt!)", parent=root):
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM watched_media WHERE user_id = ? AND tmdb_id = ? AND media_type = ?",
            (current_user_id, tmdb_id, media_type)
        )
        
        if media_type == 'tv':
            cursor.execute(
                "DELETE FROM watched_episodes WHERE user_id = ? AND show_tmdb_id = ?",
                (current_user_id, tmdb_id)
            )
            
        conn.commit()
        conn.close()
        
        label_info.config(text=f"'{current_selected_media['title']}' wurde entfernt.")
        load_watched_media() 
        display_media_details(current_selected_media) 
        
    except Exception as e:
        label_info.config(text=f"Fehler beim Löschen: {e}")

def load_watched_media():
    global watched_media_data, current_user_id, listbox_watched
    if not listbox_watched: return
    listbox_watched.delete(0, tk.END)
    if not current_user_id: return
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watched_media WHERE user_id = ? ORDER BY title", (current_user_id,))
    results = cursor.fetchall()
    watched_media_data = []
    for row in results:
        media_dict = dict(row)
        media_dict['id'] = media_dict['tmdb_id']
        watched_media_data.append(media_dict)
    conn.close()
    
    for media in watched_media_data:
        release_date = media.get('release_date', '----')
        typ_label = "[Serie]" if media.get('media_type') == 'tv' else ""
        listbox_watched.insert(tk.END, f"{media['title']} ({release_date[:4]}) {typ_label}")

def db_add_to_watchlist():
    global current_selected_media, current_user_id
    if not current_selected_media:
        label_info.config(text="Kein Medium ausgewählt.")
        return
    if not current_user_id:
        label_info.config(text="Kein Benutzer angemeldet.")
        return
    try:
        tmdb_id = current_selected_media['id']; title = current_selected_media['title']
        release_date = current_selected_media['release_date']; overview = current_selected_media['overview']
        poster_path = current_selected_media['poster_path']; media_type = current_selected_media['media_type']
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR IGNORE INTO watchlist_media 
        (user_id, tmdb_id, title, release_date, overview, poster_path, media_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (current_user_id, tmdb_id, title, release_date, overview, poster_path, media_type))
        conn.commit()
        conn.close()
        
        label_info.config(text=f"'{title}' wurde zur 'Noch Sehen'-Liste hinzugefügt!")
        load_watchlist_media() 
    except Exception as e:
        label_info.config(text=f"Fehler beim Hinzufügen zur Watchlist: {e}")

def load_watchlist_media():
    global watchlist_media_data, current_user_id, listbox_watchlist
    if not listbox_watchlist: return
    listbox_watchlist.delete(0, tk.END)
    if not current_user_id: return

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watchlist_media WHERE user_id = ? ORDER BY title", (current_user_id,))
    results = cursor.fetchall()
    watchlist_media_data = []
    for row in results:
        media_dict = dict(row)
        media_dict['id'] = media_dict['tmdb_id']
        watchlist_media_data.append(media_dict)
    conn.close()
    
    for media in watchlist_media_data:
        release_date = media.get('release_date', '----')
        typ_label = "[Serie]" if media.get('media_type') == 'tv' else ""
        listbox_watchlist.insert(tk.END, f"{media['title']} ({release_date[:4]}) {typ_label}")

def db_get_watched_episodes_for_show(show_tmdb_id):
    global current_user_id
    if not current_user_id: return {}
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT season_number, episode_number FROM watched_episodes WHERE user_id = ? AND show_tmdb_id = ?",
            (current_user_id, show_tmdb_id)
        )
        watched_data = {}
        for row in cursor.fetchall():
            season_num, ep_num = row
            if season_num not in watched_data:
                watched_data[season_num] = set()
            watched_data[season_num].add(ep_num)
        conn.close()
        return watched_data
    except Exception as e:
        print(f"Fehler beim Laden der Episoden: {e}"); return {}

def db_toggle_episode_watched(show_id, season_num, ep_num, is_watched):
    global current_user_id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if is_watched: 
        cursor.execute(
            "DELETE FROM watched_episodes WHERE user_id = ? AND show_tmdb_id = ? AND season_number = ? AND episode_number = ?",
            (current_user_id, show_id, season_num, ep_num)
        )
        print(f"Episode S{season_num}E{ep_num} von Show {show_id} entfernt.")
    else: 
        cursor.execute(
            "INSERT OR IGNORE INTO watched_episodes (user_id, show_tmdb_id, season_number, episode_number) VALUES (?, ?, ?, ?)",
            (current_user_id, show_id, season_num, ep_num)
        )
        print(f"Episode S{season_num}E{ep_num} von Show {show_id} hinzugefügt.")
    
    conn.commit()
    conn.close()

def db_toggle_season_watched(show_id, season_num, all_episodes, is_fully_watched):
    global current_user_id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if is_fully_watched: 
        print(f"Entferne alle Episoden von S{season_num}...")
        cursor.execute(
            "DELETE FROM watched_episodes WHERE user_id = ? AND show_tmdb_id = ? AND season_number = ?",
            (current_user_id, show_id, season_num)
        )
    else: 
        print(f"Füge alle Episoden von S{season_num} hinzu...")
        ep_data_to_insert = [
            (current_user_id, show_id, ep['season_number'], ep['episode_number'])
            for ep in all_episodes if ep['episode_number'] > 0
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO watched_episodes (user_id, show_tmdb_id, season_number, episode_number) VALUES (?, ?, ?, ?)",
            ep_data_to_insert
        )
    
    conn.commit()
    conn.close()


# --- 5. Profil-Auswahl (Mit Logo-Einbindung) ---
def build_profile_selector(parent_window):
    global frame_profile_selector, all_users, root
    
    parent_window.title("Profil auswählen oder erstellen")
    parent_window.geometry("400x500") 
    
    # NEU (v1.0.4): Lade das Logo für das Login-Fenster
    try:
        logo_path = resource_path("my_logo.ico")
        parent_window.iconbitmap(logo_path)
    except Exception as e:
        print(f"Logo 'my_logo.ico' nicht gefunden oder konnte nicht geladen werden: {e}")
    
    frame_profile_selector = ttk.Frame(parent_window)
    frame_profile_selector.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    def on_profile_select(event=None):
        global current_user_id, current_user_name
        try:
            selected_index = listbox_profiles.curselection()[0]
            selected_user = all_users[selected_index]
            current_user_id = selected_user['user_id']
            current_user_name = selected_user['username']
            start_main_app()
        except IndexError: pass

    def on_profile_create(event=None):
        global current_user_id, current_user_name
        username = entry_new_profile.get()
        user_id, message = db_create_user(username)
        if user_id:
            current_user_id = user_id
            current_user_name = username
            start_main_app()
        else:
            messagebox.showerror("Fehler", message, parent=root)

    def start_main_app():
        global root, frame_profile_selector
        frame_profile_selector.destroy()
        build_main_gui(root) 
        root.title(f"MyMediaTracker v1.0.4 - Angemeldet als: {current_user_name}")
        load_watched_media()
        load_watchlist_media()
        update_button_visibility(0) 

    def populate_profile_list():
        global all_users
        listbox_profiles.delete(0, tk.END)
        all_users = db_get_users()
        for user in all_users:
            listbox_profiles.insert(tk.END, user['username'])

    frame_existing = ttk.LabelFrame(frame_profile_selector, text="Vorhandenes Profil auswählen")
    frame_existing.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    listbox_profiles = tk.Listbox(frame_existing, exportselection=False)
    listbox_profiles.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    listbox_profiles.bind("<Double-Button-1>", on_profile_select)
    button_select = ttk.Button(frame_existing, text="Auswählen", command=on_profile_select)
    button_select.pack(pady=5)
    
    frame_new = ttk.LabelFrame(frame_profile_selector, text="Neues Profil erstellen")
    frame_new.pack(fill=tk.X, padx=10, pady=10)
    entry_new_profile = ttk.Entry(frame_new)
    entry_new_profile.pack(fill=tk.X, padx=5, pady=5)
    entry_new_profile.bind("<Return>", on_profile_create)
    button_create = ttk.Button(frame_new, text="Erstellen & Anmelden", command=on_profile_create)
    button_create.pack(pady=5)
    
    global all_users
    all_users = []
    populate_profile_list()

# --- 6. GUI-Funktionen (Logik) ---
def display_media_details(media_data):
    global current_selected_media, label_poster, label_info, episode_cache
    global frame_tree_container, tree_seasons_episodes
    
    current_selected_media = media_data 
    episode_cache.clear() 
    
    tree_seasons_episodes.delete(*tree_seasons_episodes.get_children())
    frame_tree_container.pack_forget()

    try:
        info_text = f"Titel: {media_data['title']}\n"
        info_text += f"Datum: {media_data.get('release_date', 'Unbekannt')}\n\n"
        overview = media_data.get('overview', 'k.A.')
        label_info.config(text=info_text + overview)
        
        poster_path = media_data.get('poster_path')
        if poster_path:
            poster_url = f"{POSTER_BASE_URL}{poster_path}"
            img_response = requests.get(poster_url)
            img_data = io.BytesIO(img_response.content)
            img = Image.open(img_data)
            photo = ImageTk.PhotoImage(img)
            label_poster.config(image=photo)
            label_poster.image = photo
        else:
            label_poster.config(image=None)
            label_poster.image = None
            
        if media_data.get('media_type') == 'tv':
            frame_tree_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,0))
            show_id = media_data['id']
            watched_ep_data = db_get_watched_episodes_for_show(show_id)
            
            try:
                detail_url = f"https://api.themoviedb.org/3/tv/{show_id}"
                params = {'api_key': API_KEY, 'language': 'de-DE'}
                response = requests.get(detail_url, params=params)
                response.raise_for_status()
                tv_data = response.json()
                
                for season in tv_data.get('seasons', []):
                    season_num = season.get('season_number')
                    if season_num == 0: continue 
                        
                    season_name = season.get('name')
                    ep_count = season.get('episode_count', 0)
                    
                    watched_in_season = watched_ep_data.get(season_num, set())
                    watched_count = len(watched_in_season)
                    
                    status_str = f"{watched_count}/{ep_count}"
                    tag = "ungesehen"
                    if watched_count == ep_count and ep_count > 0:
                        tag = "gesehen" 
                    elif watched_count > 0:
                        tag = "partiell" 
                    
                    season_id_str = f"S{season_num}" 
                    tree_seasons_episodes.insert("", tk.END, iid=season_id_str,
                                        text=f"  {season_name} ({status_str})", 
                                        values=(season_num, ep_count), 
                                        tags=(tag,))
                    
                    tree_seasons_episodes.insert(season_id_str, tk.END, text="Lade Episoden...")

            except requests.exceptions.RequestException as e:
                current_text = label_info.cget("text")
                label_info.config(text=current_text + f"\n\nFehler beim Laden der Staffeln: {e}")
            
    except Exception as e:
        if label_info:
            label_info.config(text=f"Fehler beim Anzeigen der Details:\n{e}")
        else:
            print(f"Fehler beim Anzeigen der Details: {e}")

def populate_search_list(media_list, source_description="Ergebnisse"):
    global current_results, listbox_search_results, notebook, frame_search_list
    listbox_search_results.delete(0, tk.END)
    if media_list:
        current_results = media_list
        for media in current_results:
            release_date = media.get('release_date', '----')
            typ_label = "[Serie]" if media.get('media_type') == 'tv' else ""
            listbox_search_results.insert(tk.END, f"{media['title']} ({release_date[:4]}) {typ_label}")
        
        if len(current_results) > 0:
            listbox_search_results.select_set(0)
            display_media_details(current_results[0])
            
        notebook.select(frame_search_list)
    else:
        label_info.config(text=f"Keine {source_description} gefunden.")
        current_results = []
        
def search_media(event=None):
    global media_type_var, entry_search, label_info, label_poster
    suchbegriff = entry_search.get()
    media_type = media_type_var.get()
    if not suchbegriff: return

    label_info.config(text=f"... Suche {media_type} ...")
    label_poster.config(image=None)
    label_poster.image = None
    tree_seasons_episodes.delete(*tree_seasons_episodes.get_children())
    frame_tree_container.pack_forget()
    
    try:
        search_endpoint = f"https://api.themoviedb.org/3/search/{media_type}"
        params = {'api_key': API_KEY, 'query': suchbegriff, 'language': 'de-DE'}
        response = requests.get(search_endpoint, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [])
        normalized_results = [normalize_media_data(item, media_type) for item in results]
        populate_search_list(normalized_results, source_description=f"Ergebnisse für '{suchbegriff}'")
        
    except requests.exceptions.RequestException as e:
        label_info.config(text=f"Fehler bei der API-Anfrage:\n{e}")
    except Exception as e:
        label_info.config(text=f"Ein Anzeigefehler ist aufgetreten:\n{e}")
        print(f"Ein Anzeigefehler ist aufgetreten: {e}")


def find_similar_media():
    if not current_selected_media:
        label_info.config(text="Bitte zuerst ein Medium auswählen.")
        return
    media_type = current_selected_media.get('media_type')
    tmdb_id = current_selected_media.get('id')
    if not tmdb_id or not media_type:
        label_info.config(text="Konnte Typ oder ID des Mediums nicht finden.")
        return
    label_info.config(text=f"... Suche ähnliche Medien zu '{current_selected_media['title']}' ...")
    
    try:
        similar_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/similar"
        params = {'api_key': API_KEY, 'language': 'de-DE'}
        response = requests.get(similar_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [])
        normalized_results = [normalize_media_data(item, media_type) for item in results]
        populate_search_list(normalized_results, source_description=f"ähnliche Medien")
        
    except requests.exceptions.RequestException as e:
        label_info.config(text=f"Fehler beim Finden ähnlicher Medien:\n{e}")
    except Exception as e:
        label_info.config(text=f"Ein Anzeigefehler ist aufgetreten:\n{e}")
        print(f"Ein Anzeigefehler ist aufgetreten: {e}")

# --- 7. Event-Handler (Überarbeitet für v1.0.4) ---

def update_button_visibility(tab_index):
    """(v1.0.3) Zeigt Buttons basierend auf dem aktiven Tab an."""
    global button_add_to_watchlist, button_mark_watched, button_remove_from_watchlist, button_remove_from_watched
    
    # Verstecke zuerst alle kontextsensitiven Buttons
    button_add_to_watchlist.pack_forget()
    button_mark_watched.pack_forget()
    button_remove_from_watchlist.pack_forget()
    button_remove_from_watched.pack_forget()

    if tab_index == 0: # 0 = Suche
        button_add_to_watchlist.pack(side=tk.LEFT, padx=5)
        button_mark_watched.pack(side=tk.LEFT, padx=5)
    elif tab_index == 1: # 1 = Gesehen
        button_remove_from_watched.pack(side=tk.LEFT, padx=5)
    elif tab_index == 2: # 2 = Noch Sehen
        button_mark_watched.pack(side=tk.LEFT, padx=5) 
        button_remove_from_watchlist.pack(side=tk.LEFT, padx=5)

def on_search_select(event):
    try:
        selected_indices = listbox_search_results.curselection()
        if not selected_indices: return
        selected_index = selected_indices[0]
        selected_media = current_results[selected_index]
        display_media_details(selected_media)
    except Exception as e: print(f"Fehler bei Such-Auswahl: {e}")

def on_watched_select(event):
    try:
        selected_indices = listbox_watched.curselection()
        if not selected_indices: return
        selected_index = selected_indices[0]
        selected_media_data = watched_media_data[selected_index]
        display_media_details(selected_media_data)
    except Exception as e: print(f"Fehler bei Gesehen-Auswahl: {e}")

def on_watchlist_select(event):
    try:
        selected_indices = listbox_watchlist.curselection()
        if not selected_indices: return
        selected_index = selected_indices[0]
        selected_media_data = watchlist_media_data[selected_index]
        display_media_details(selected_media_data)
    except Exception as e: print(f"Fehler bei Watchlist-Auswahl: {e}")

def on_tab_changed(event):
    global notebook
    try:
        selected_tab = notebook.index(notebook.select())
        update_button_visibility(selected_tab)
        
        if selected_tab == 1: 
            load_watched_media()
        elif selected_tab == 2: 
            load_watchlist_media()
    except Exception as e:
        print(f"Fehler bei Tab-Wechsel: {e}")

def fetch_season_data(show_id, season_num):
    global episode_cache, root
    if (show_id in episode_cache and season_num in episode_cache[show_id]):
        print(f"Lade Episoden für S{season_num} aus Cache...")
        return episode_cache[show_id][season_num]
    
    try:
        print(f"API-Aufruf (fetch): Lade Episoden für S{season_num}...")
        ep_url = f"https://api.themoviedb.org/3/tv/{show_id}/season/{season_num}"
        params = {'api_key': API_KEY, 'language': 'de-DE'}
        response = requests.get(ep_url, params=params)
        response.raise_for_status()
        season_data = response.json()
        episodes = season_data.get('episodes', [])
        
        if show_id not in episode_cache: episode_cache[show_id] = {}
        episode_cache[show_id][season_num] = episodes
        return episodes
    except Exception as e:
        messagebox.showerror("API Fehler", f"Konnte Episoden für Staffel {season_num} nicht laden:\n{e}", parent=root)
        return None

def on_tree_open(event):
    global tree_seasons_episodes, current_selected_media, episode_cache
    
    item_id = tree_seasons_episodes.focus() 
    if not item_id.startswith("S"): return 
    
    children = tree_seasons_episodes.get_children(item_id)
    if not children or tree_seasons_episodes.item(children[0], "text") != "Lade Episoden...":
        return 
        
    tree_seasons_episodes.delete(children[0])
    
    show_id = current_selected_media['id']
    season_num = tree_seasons_episodes.item(item_id, "values")[0]
    
    watched_ep_data = db_get_watched_episodes_for_show(show_id)
    watched_in_season = watched_ep_data.get(season_num, set())
    
    all_episodes_in_season = fetch_season_data(show_id, season_num)
    
    if all_episodes_in_season is not None:
        for ep in all_episodes_in_season:
            ep_num = ep.get('episode_number')
            ep_name = ep.get('name', f'Episode {ep_num}')
            if ep_num == 0: continue
            
            is_watched = ep_num in watched_in_season
            tag = "gesehen" if is_watched else "ungesehen"
            ep_id_str = f"S{season_num}E{ep_num}" 
            
            tree_seasons_episodes.insert(item_id, tk.END, iid=ep_id_str,
                                        text=f"E{ep_num}: {ep_name}",
                                        values=(season_num, ep_num), 
                                        tags=(tag,))
    else:
        tree_seasons_episodes.insert(item_id, tk.END, text=f"Episoden konnten nicht geladen werden.")


def on_tree_double_click(event):
    global tree_seasons_episodes, current_selected_media, episode_cache, root
    
    item_id = tree_seasons_episodes.focus() 
    if not item_id: return
    
    # (Stelle sicher, dass ein Medium ausgewählt ist)
    if not current_selected_media: return
    
    show_id = current_selected_media['id']
    
    if "E" in item_id:
        # --- EPISODE GEKLICKT ---
        season_num, ep_num = tree_seasons_episodes.item(item_id, "values")
        is_watched = "gesehen" in tree_seasons_episodes.item(item_id, "tags")
        db_toggle_episode_watched(show_id, season_num, ep_num, is_watched)
        
    else:
        # --- STAFFEL GEKLICKT (v1.0.2) ---
        season_num, ep_count = tree_seasons_episodes.item(item_id, "values")
        
        all_episodes_in_season = fetch_season_data(show_id, season_num)
        
        if all_episodes_in_season is None:
             return
            
        watched_ep_data = db_get_watched_episodes_for_show(show_id)
        watched_in_season = watched_ep_data.get(season_num, set())
        
        valid_ep_count = len([ep for ep in all_episodes_in_season if ep['episode_number'] > 0])
        is_fully_watched = len(watched_in_season) >= valid_ep_count

        db_toggle_season_watched(show_id, season_num, all_episodes_in_season, is_fully_watched)

    # Füge die Serie zur Haupt-Bibliothek hinzu (falls noch nicht geschehen)
    # und entferne sie von der Watchlist
    db_mark_as_watched() 
    # Lade die Listen neu
    load_watched_media()
    load_watchlist_media()
    # Aktualisiere die Detailansicht
    display_media_details(current_selected_media)


# --- 8. GUI-Bau-Funktion (Layout v1.0.4) ---
def build_main_gui(parent_window):
    global media_type_var, entry_search, notebook, frame_search_list
    global listbox_search_results, listbox_watched, listbox_watchlist, label_poster
    global label_info, frame_tree_container, tree_seasons_episodes
    global button_add_to_watchlist, button_mark_watched, button_remove_from_watchlist
    global button_remove_from_watched, button_find_similar

    parent_window.geometry("1100x700") 
    
    # NEU (v1.0.4): Lade das Logo für das Hauptfenster
    try:
        logo_path = resource_path("my_logo.ico")
        parent_window.iconbitmap(logo_path)
    except Exception as e:
        print(f"Logo 'my_logo.ico' nicht gefunden oder konnte nicht geladen werden: {e}")

    media_type_var = tk.StringVar(value="movie")

    frame_search_bar = ttk.Frame(parent_window)
    frame_search_bar.pack(fill=tk.X, padx=10, pady=10)
    frame_search_entry = ttk.Frame(frame_search_bar)
    frame_search_entry.pack(fill=tk.X)
    entry_search = ttk.Entry(frame_search_entry, width=60)
    entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    button_search = ttk.Button(frame_search_entry, text="Suchen", command=search_media)
    button_search.pack(side=tk.LEFT)
    entry_search.bind("<Return>", search_media)
    frame_radio_buttons = ttk.Frame(frame_search_bar)
    frame_radio_buttons.pack(pady=(5,0))
    rb_movie = ttk.Radiobutton(frame_radio_buttons, text="Film", variable=media_type_var, value="movie")
    rb_movie.pack(side=tk.LEFT, padx=5)
    rb_tv = ttk.Radiobutton(frame_radio_buttons, text="Serie", variable=media_type_var, value="tv")
    rb_tv.pack(side=tk.LEFT, padx=5)

    frame_main_content = ttk.Frame(parent_window)
    frame_main_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # --- Spalte 1: Linke Seite (Listen) ---
    frame_left_list = ttk.Frame(frame_main_content, width=350)
    frame_left_list.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
    frame_left_list.pack_propagate(False)
    
    notebook = ttk.Notebook(frame_left_list)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Tab 1: Suche
    frame_search_list = ttk.Frame(notebook)
    notebook.add(frame_search_list, text='Suche')
    list_scrollbar_search = ttk.Scrollbar(frame_search_list, orient=tk.VERTICAL)
    listbox_search_results = tk.Listbox(frame_search_list, yscrollcommand=list_scrollbar_search.set, exportselection=False)
    list_scrollbar_search.config(command=listbox_search_results.yview)
    list_scrollbar_search.pack(side=tk.RIGHT, fill=tk.Y)
    listbox_search_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox_search_results.bind("<<ListboxSelect>>", on_search_select)

    # Tab 2: Gesehen
    frame_watched_list = ttk.Frame(notebook)
    notebook.add(frame_watched_list, text='Gesehen')
    list_scrollbar_watched = ttk.Scrollbar(frame_watched_list, orient=tk.VERTICAL)
    listbox_watched = tk.Listbox(frame_watched_list, yscrollcommand=list_scrollbar_watched.set, exportselection=False)
    list_scrollbar_watched.config(command=listbox_watched.yview)
    list_scrollbar_watched.pack(side=tk.RIGHT, fill=tk.Y)
    listbox_watched.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox_watched.bind("<<ListboxSelect>>", on_watched_select)

    # Tab 3: Noch Sehen
    frame_watchlist = ttk.Frame(notebook)
    notebook.add(frame_watchlist, text='Noch Sehen')
    list_scrollbar_watchlist = ttk.Scrollbar(frame_watchlist, orient=tk.VERTICAL)
    listbox_watchlist = tk.Listbox(frame_watchlist, yscrollcommand=list_scrollbar_watchlist.set, exportselection=False)
    list_scrollbar_watchlist.config(command=listbox_watchlist.yview)
    list_scrollbar_watchlist.pack(side=tk.RIGHT, fill=tk.Y)
    listbox_watchlist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox_watchlist.bind("<<ListboxSelect>>", on_watchlist_select)

    notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

    # --- Spalte 3: Rechte Seite (Poster) ---
    frame_right_poster = ttk.Frame(frame_main_content, width=320) 
    frame_right_poster.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
    frame_right_poster.pack_propagate(False)

    label_poster = ttk.Label(frame_right_poster, relief=tk.SUNKEN)
    label_poster.pack(pady=10, anchor=tk.N)

    # --- Spalte 2: Mitte (Details & Staffeln/Episoden) ---
    frame_middle_details = ttk.Frame(frame_main_content)
    frame_middle_details.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(frame_middle_details, highlightthickness=0)
    scrollbar_middle = ttk.Scrollbar(frame_middle_details, orient="vertical", command=canvas.yview)
    scrollable_frame_middle = ttk.Frame(canvas)
    
    scrollable_frame_middle.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )
    canvas.create_window((0, 0), window=scrollable_frame_middle, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar_middle.set)
    
    scrollbar_middle.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # --- Inhalt für die MITTLERE Spalte (NEUE REIHENFOLGE v1.0.4) ---
    
    # 1. Buttons (Dynamisch)
    frame_buttons = ttk.Frame(scrollable_frame_middle)
    frame_buttons.pack(pady=10)
    
    button_add_to_watchlist = ttk.Button(frame_buttons, text="Zu 'Noch Sehen'", command=db_add_to_watchlist)
    button_mark_watched = ttk.Button(frame_buttons, text="Ganz GESEHEN", command=db_mark_as_watched)
    button_remove_from_watchlist = ttk.Button(frame_buttons, text="Aus 'Noch Sehen' entfernen", command=db_remove_from_watchlist)
    button_remove_from_watched = ttk.Button(frame_buttons, text="Aus 'Gesehen' entfernen", command=db_remove_from_watched)

    # 2. Buttons (Statisch)
    frame_static_buttons = ttk.Frame(scrollable_frame_middle)
    frame_static_buttons.pack(pady=(0,10))
    button_find_similar = ttk.Button(frame_static_buttons, text="Ähnliche finden", command=find_similar_media)
    button_find_similar.pack(side=tk.LEFT, padx=5)
    
    # 3. Beschreibung
    label_info = ttk.Label(scrollable_frame_middle, text="Willkommen! Bitte Film oder Serie suchen.", justify=tk.LEFT, anchor=tk.NW)
    label_info.pack(fill=tk.X, padx=10, pady=5)
    label_info.bind('<Configure>', lambda e: label_info.config(wraplength=e.width - 10))

    # 4. Staffel/Episoden-Liste
    frame_tree_container = ttk.Frame(scrollable_frame_middle)
    
    tree_seasons_episodes = ttk.Treeview(frame_tree_container, columns=("v1", "v2"), show="tree", height=12)
    tree_seasons_episodes.column("#0", width=300, stretch=True)
    tree_seasons_episodes.column("v1", width=0, stretch=False)
    tree_seasons_episodes.column("v2", width=0, stretch=False)
    
    tree_scrollbar = ttk.Scrollbar(frame_tree_container, orient="vertical", command=tree_seasons_episodes.yview)
    tree_seasons_episodes.configure(yscrollcommand=tree_scrollbar.set)
    tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree_seasons_episodes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    tree_seasons_episodes.bind("<<TreeviewOpen>>", on_tree_open)
    tree_seasons_episodes.bind("<Double-Button-1>", on_tree_double_click)
    
    s = ttk.Style()
    s.configure('Treeview')
    tree_seasons_episodes.tag_configure("gesehen", background="#c8e6c9", foreground="black")
    tree_seasons_episodes.tag_configure("partiell", background="#fff9c4", foreground="black")
    tree_seasons_episodes.tag_configure("ungesehen", background="white", foreground="black")
    

# --- 9. Anwendung starten (Stabile Frame-Wechsel-Methode) ---
if __name__ == "__main__":
    db_init() # Zuerst die Datenbank vorbereiten
    
    root = tk.Tk() # Das Hauptfenster erstellen
    
    # Baue den Profil-Auswahl-Screen IN das Hauptfenster
    build_profile_selector(root) 

    root.mainloop() # Starte die Haupt-Schleife