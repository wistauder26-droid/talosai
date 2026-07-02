# Ein persönliches Morgen-Briefing erstellen (News, Wetter, Termine)

## Schritte
1. `memory_read` auf Nutzer-Fakten: Wohnort, Interessen, Projekte.
2. Delegiere parallel per `delegate`:
   - "Top 5 Nachrichten heute zu [Interessen des Nutzers], mit Quellen-URLs"
   - "Wetter heute in [Wohnort]" (web_search: 'wetter <ort> heute')
3. Falls Kalender-Zugriff (MCP oder `shell` mit `icalBuddy`) vorhanden: heutige Termine holen.
4. Format der Antwort — kurz und scanbar:
   - **☀️ Wetter:** ein Satz
   - **📰 News:** 3–5 Punkte, je ein Satz + Quelle
   - **📅 Heute:** Termine oder "keine Termine gefunden"
   - **💡 Fokus:** 1 Vorschlag basierend auf laufenden Projekten aus dem Memory

## Stolperfallen
- News ohne Quelle sind wertlos — immer URL angeben.
- Nicht mehr als ~15 Zeilen gesamt; das Briefing wird oft vorgelesen (TTS).
