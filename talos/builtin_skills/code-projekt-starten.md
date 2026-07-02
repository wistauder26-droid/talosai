# Ein neues Code-Projekt sauber aufsetzen und lauffähig übergeben

## Schritte
1. Zielklärung aus der Aufgabe: Sprache, Zweck, wie wird es gestartet?
2. Projekt unter `~/TalosProjekte/<name>/` anlegen (`mkdir -p`).
3. Minimal-Struktur: Hauptdatei, README.md mit Start-Befehl, ggf. requirements.txt/package.json.
4. Code schreiben — klein anfangen, eine Funktion nach der anderen.
5. IMMER selbst testen via `shell` (ausführen, Output prüfen), bevor Erfolg gemeldet wird.
6. Bei Fehlern: Fehlermeldung lesen, fixen, erneut testen — max. 5 Zyklen,
   dann Problem ehrlich beschreiben.
7. Abschluss-Antwort: Was wurde gebaut, wie startet man es (exakter Befehl),
   was wurde getestet.

## Stolperfallen
- Python: venv nutzen (`python3 -m venv .venv && .venv/bin/pip install ...`),
  nie global installieren.
- macOS hat Python 3.9 als System-Python — für Neueres `python3.12` prüfen.
- Nie "sollte funktionieren" sagen — nur was tatsächlich getestet wurde.
