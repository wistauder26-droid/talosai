# Gründliche Recherche mit Quellen-Bericht durchführen

## Schritte
1. Frage in 2–4 unabhängige Teilfragen zerlegen.
2. Pro Teilfrage einen Subagenten (`delegate`) mit präzisem Auftrag starten:
   "Recherchiere X. Lies mindestens 2 Quellen mit web_fetch (nicht nur
   Snippets!). Liefere: Kernaussage, Zahlen/Daten, Quellen-URLs."
3. Ergebnisse zusammenführen; Widersprüche zwischen Quellen explizit nennen.
4. Bericht-Format:
   - **Kurzantwort** (2–3 Sätze)
   - **Details** mit Zwischenüberschriften
   - **Quellen** als nummerierte Liste mit URLs
5. Wichtige, wiederverwendbare Erkenntnisse mit `memory_save` sichern.

## Stolperfallen
- Snippets aus web_search reichen NICHT als Beleg — immer web_fetch auf die Quelle.
- Datum der Quelle prüfen; veraltete Infos kennzeichnen.
- Bei Zahlen: immer zwei unabhängige Quellen, sonst als "einzelne Quelle" markieren.
