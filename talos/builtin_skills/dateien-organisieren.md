# Dateien und Ordner sicher aufräumen/organisieren

## Schritte
1. ERST ANALYSIEREN: `ls -la` / `du -sh` auf den Zielordner; Bild vom Ist-Zustand machen.
2. Plan vorschlagen (welche Datei wohin) und auf Bestätigung des Nutzers warten,
   wenn mehr als ~10 Dateien betroffen sind.
3. Verschieben statt löschen: `mkdir -p` Zielordner, dann `mv`.
   Löschen nur auf ausdrücklichen Wunsch — und dann in den Papierkorb:
   `mv <datei> ~/.Trash/` statt `rm`.
4. Abschluss: Vorher/Nachher-Zusammenfassung (Anzahl Dateien, neue Struktur).

## Stolperfallen
- NIE `rm -rf` auf Nutzerdaten. Papierkorb ist reversibel, rm nicht.
- Versteckte Dateien (.DS_Store etc.) in Ruhe lassen.
- Bei Namenskonflikten nummerieren statt überschreiben.
- Programme/Apps (.app) nicht verschieben.
