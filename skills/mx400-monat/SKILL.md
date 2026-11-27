---
name: mx400-monat
description: Holt die Monatswerte der Wärmepumpe (Buderus MX400) per mx400-MCP und trägt sie in den Reiter "WP Gateway" von AufDemSchnee.xlsx ein. Use when the user wants a month of heat pump data added or refreshed in the Excel ("trag den Dezember ein", "WP Monat nachtragen"), or invokes /mx400-monat.
---

# MX400-Monat ins Excel

Ziel: ein abgeschlossener Monat steht als vollständige Zeile im Reiter **WP Gateway**, alle Formeln, Summen und Diagramme umfassen ihn. Sprache: Deutsch.

- Mappe: `/Users/lukasmussle/Library/CloudStorage/GoogleDrive-lukasmuessle@googlemail.com/My Drive/Alex_Lukas/AufDemSchnee/AufDemSchnee.xlsx`
- Schreiben **nur per AppleScript ins laufende Excel** (`timeout 60 osascript ...`). openpyxl & Co. zerstören beim Speichern Diagramme und bedingte Formatierung der anderen Reiter.

## 1. Monat festlegen

Ohne Angabe: der letzte abgeschlossene Monat. Ein laufender Monat ist unvollständig: nur auf ausdrücklichen Wunsch, und dann im Abschlussbericht als Teilmonat nennen.

## 2. Werte holen

Mit `mcp__mx400__read`, jeweils `?sampleRate=P1M&startDate=YYYY-MM-01&endDate=YYYY-MM-<letzter Tag>`:

| Pfad | Spalte im Sheet | Umrechnung |
|---|---|---|
| `/recordings/system/sensors/temperatures/outdoor_t1` | Ø Außentemp (°C) | `y / c`, 1 Nachkommastelle |
| `/recordings/heatSources/emon/total/compressor` | Kompressor (kWh) | `y` |
| `/recordings/heatSources/emon/total/eheater` | Heizstab (kWh) | `y` |
| `/recordings/heatSources/emon/total/outputProduced` | Wärme erzeugt (kWh) | `y` |
| `/recordings/heatSources/emon/total/numberOfStarts` | Kompressorstarts | `y` |
| `/recordings/heatSources/emon/total/workingTime` | Laufzeit Kompressor (h) | `y / 3600` |

Vollständigkeit: bei frischen Monaten ist `c` die Stundenzahl; `c` = Tage × 24 (±1 wegen Zeitumstellung) heißt vollständig. Ältere Monate sind verdichtet (`c = 1`), die gelten als vollständig.

Zählerwerte vor dem 23.07.2026 sind kumuliert statt Delta, siehe Memory `recordings-counter-quirk`. Neue Monate betrifft das nicht.

## 3. Sheet lesen

Im Reiter **WP Gateway** die Kopfzeile suchen (Zelle in Spalte A = `Monat`) und jede Spalte über ihren **Kopftext** zuordnen, nie über feste Buchstaben: der Nutzer baut den Reiter um. Die sechs Spalten aus der Tabelle oben sind Eingaben, alle anderen sind Formeln. Datenzeilen haben in Spalte A ein Datum (Monatserster als Seriennummer, Format `mmm yyyy`), darunter folgt die Summenzeile (Spalte A beginnt mit `Summe`).

Diagramm-Eigenschaften (`chart objects`) per AppleScript abzufragen hängt Excel auf: Finger weg, die Diagramme folgen den Bereichen von selbst.

## 4. Eintragen

**Monat existiert schon** (z.B. vorher als Teilmonat eingetragen): nur die sechs Eingabezellen überschreiben.

**Neuer Monat**, so dass alle Bereiche (Summen, Kennzahlen, Diagramme) automatisch mitwachsen:
1. Zeile **über der letzten Datenzeile** einfügen (`insert into range ... shift shift down`). Bereiche wie `C13:C24` dehnen sich nur bei Einfügen innerhalb aus, nicht direkt darunter.
2. Die nun letzte Datenzeile komplett (Spalte A bis letzte Spalte) in die leere Zeile darüber kopieren (`copy range` ... `destination`), Formate und relative Formeln wandern mit.
3. In der letzten Datenzeile Datum (Seriennummer = Tage seit 1899-12-30) und die sechs Eingabewerte setzen.
4. Summenzeile rollierend auf **12 Monate** halten: in jeder Formel der Summenzeile (SUM, AVERAGE, SUMIFS, ...) die Startzeile um 1 erhöhen, damit sie die letzten 12 Datenzeilen umfasst. Beschriftung `Summe <Mon YY> – <Mon YY>` und die Überschrift `Kennzahlen ...` darüber auf denselben Zeitraum ziehen.

## 5. Prüfen und berichten

Neue Zeile und Summenzeile per `string value` zurücklesen. Fertig ist es, wenn jede Formelzelle eine Zahl oder bewusst leer zeigt (kein `#REF!`, `#VALUE!`, `#N/A`), die Summenzeile genau 12 Monate umfasst und `###` per Spaltenbreite behoben ist.

Nicht speichern, der Nutzer prüft und speichert selbst. Bericht: eingetragene Werte, COP und Starts/Tag des Monats im Vergleich zum Vorjahresmonat (falls vorhanden). Ist die Spalte WP-Zähler leer, fehlt die Ablesung im Reiter **WP Strom**: daran erinnern, die füllt sich danach von selbst.
