MyMediaTracker v1.0.4

Eine Desktop-Anwendung zur Verfolgung von Filmen und Serien, die mit Python, Tkinter und der TMDb-API erstellt wurde.

(Hinweis: Ersetze screenshot.png durch den Namen eines Screenshots, den du mit ins Repository hochlädst, oder lösche diese Zeile.)

Über das Projekt

MyMediaTracker ist eine benutzerfreundliche Desktop-Anwendung für Windows, mit der du deine gesehenen Filme und Serien verfolgen kannst. Dank der Profilverwaltung kann die Anwendung von mehreren Personen im Haushalt genutzt werden, wobei jeder seine eigenen Listen pflegt.

Sie nutzt die TMDb-API, um detaillierte Informationen, Poster und sogar Episodenlisten für Serien abzurufen. Der gesamte Fortschritt wird lokal in einer SQLite-Datenbank gespeichert.

Funktionen

    Multi-Profil-Verwaltung: Erstelle mehrere Benutzerprofile. Jedes Profil hat seine eigenen, separaten Listen.

    Film- & Seriensuche: Durchsuche die gesamte The Movie Database (TMDb) nach Filmen oder Serien.

    Drei-Listen-System: Verwalte deine Medien in drei separaten Tabs:

        Suche: Zeigt Suchergebnisse an.

        Gesehen (Bibliothek): Eine Liste aller Medien, die du (auch teilweise) gesehen hast.

        Noch Sehen (Watchlist): Eine Liste von Medien, die du in Zukunft sehen möchtest.

    Detailliertes Episoden-Tracking:

        Markiere ganze Staffeln oder einzelne Episoden als gesehen (per Doppelklick).

        Eine hierarchische Baumansicht (Treeview) lädt Episoden dynamisch nach, wenn eine Staffel aufgeklappt wird.

        Der Status (komplett, partiell oder ungesehen) wird visuell im Staffel-Namen angezeigt.

    Kontextsensitive Steuerung: Die Benutzeroberfläche zeigt nur die Aktionen an, die im aktuellen Tab (Suche, Gesehen, Noch Sehen) sinnvoll sind.

    Entdecken: Finde ähnliche Filme oder Serien basierend auf deiner aktuellen Auswahl.

    Lokale Speicherung: Alle Profildaten und Listen werden in einer lokalen media_tracker.db (SQLite) Datei gespeichert.

    Kompiliert: Kann mittels PyInstaller zu einer einzigen .exe-Datei für Windows gebündelt werden.

Verwendete Technologien

    Python 3: Kernsprache

    Tkinter (ttk): Für die grafische Benutzeroberfläche (GUI)

    SQLite3: Für die lokale Datenbank (Profile, Listen, Episodenstatus)

    Requests: Für alle API-Anfragen an TMDb

    Pillow (PIL): Zum Laden und Anzeigen von Posterbildern

    PyInstaller: Zum Erstellen einer eigenständigen .exe-Datei für Windows

Installation & Einrichtung

Es gibt zwei Möglichkeiten, die Anwendung zu nutzen:

1. Als .exe (Windows) verwenden

    Lade die app.exe aus dem Releases-Tab dieses Repos herunter (oder aus dem dist-Ordner, falls du selbst buildest).

    Lege die app.exe in einen eigenen Ordner (z.B. auf deinem Desktop).

    Lege die my_logo.ico-Datei (aus diesem Repo) in denselben Ordner.

    Starte die app.exe. Beim ersten Start wird im selben Ordner automatisch die Datenbankdatei media_tracker.db erstellt.

2. Als Python-Skript ausführen (für Entwickler)

    Klone dieses Repository:
    Bash

git clone https://github.com/DEIN-USERNAME/DEIN-REPO-NAME.git
cd DEIN-REPO-NAME

Installiere die notwendigen Python-Bibliotheken:
Bash

pip install requests pillow

WICHTIG: API-Schlüssel eintragen Diese Anwendung benötigt einen API-Schlüssel von The Movie Database (TMDb).

    Erstelle ein kostenloses Konto auf themoviedb.org.

    Gehe in deine Account-Einstellungen zum API-Bereich und beantrage einen "v3"-Schlüssel.

    Öffne die app.py-Datei in einem Texteditor.

    Finde die Zeile (ca. Zeile 19):
    Python

    API_KEY = "DEIN_API_SCHLÜSSEL_HIER" 

    Ersetze "DEIN_API_SCHLÜSSEL_HIER" durch deinen persönlichen TMDb-API-Schlüssel.

(Achtung: Veröffentliche deinen privaten Schlüssel niemals öffentlich! Wenn du dieses Repository forkst, füge deine app.py zu deiner .gitignore-Datei hinzu, nachdem du deinen Schlüssel eingetragen hast.)

Starte die Anwendung:
Bash

    python app.py

Build-Anleitung (Erstellung der .exe)

Um die .exe-Datei selbst zu erstellen, wird PyInstaller benötigt:

    Installiere PyInstaller:
    Bash

pip install pyinstaller

Stelle sicher, dass deine Logo-Datei my_logo.ico im selben Ordner wie app.py liegt.

Führe den Build-Befehl in deiner Konsole aus (alles in einer Zeile):
Bash

    python -m PyInstaller --onefile --windowed --icon=my_logo.ico --add-data "my_logo.ico;." --hidden-import=requests --hidden-import=PIL app.py

    Die fertige app.exe befindet sich im neu erstellten dist-Ordner.

Lizenz

Dieses Projekt steht unter der MIT-Lizenz.