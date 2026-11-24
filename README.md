# HA-IoSync

Home-Assistant-Integration für **IoSync** – die Brücke zwischen Smart Home und Android / Wear OS. Die IoSync-App überträgt damit eigene Daten an Home Assistant, als Gerät mit echten Entitäten.

Erster Anwendungsfall ist der **Schlaf-/Wachstatus** der Healthy-Uhr-App. Weitere Werte kommen ohne Update dieser Integration dazu: Die App beschreibt ihre Sensoren selbst (Name, Typ, Icon, Geräteklasse, Einheit), unbekannte Sensoren legt die Integration beim ersten Eintreffen an.

## Was ist IoSync?

[IoSync](https://github.com/thestealth131205/IoSync) besteht aus einer Android-App, einem Wear-OS-Watchface und einem [ioBroker-Adapter](https://github.com/thestealth131205/ioBroker.iosync). Die App zeigt und schaltet Datenpunkte aus ioBroker oder Home Assistant, das Watchface bringt sie auf die Uhr.

## Voraussetzungen

- Home Assistant 2025.1 oder neuer
- IoSync-App **ab 5.3.1** mit eingerichtetem Home Assistant (Adresse + Langzeit-Token)

## Installation

**HACS:** HACS → Benutzerdefinierte Repositories → `https://github.com/thestealth131205/HA-IoSync` (Typ: Integration) → „IoSync“ installieren → Home Assistant neu starten.

**Manuell:** `custom_components/iosync` nach `<config>/custom_components/iosync` kopieren und Home Assistant neu starten.

## Einrichtung

1. Einstellungen → Geräte & Dienste → Integration hinzufügen → **IoSync** → Absenden.
2. Fertig – Zugangsdaten braucht die Integration nicht. Die App meldet sich mit ihrem Langzeit-Token.
3. Geräte und Entitäten erscheinen, sobald die App das erste Mal Daten sendet. Beim Schlafstatus z. B. in der App über **Einstellungen → Home Assistant → Schlafstatus von Healthy → Jetzt an Home Assistant senden**.

## Schlafstatus (Healthy)

Gerät **Healthy** mit:

| Entität | Inhalt |
|---|---|
| `binary_sensor.healthy_schlaf` | `on` = schläft, `off` = wach. Attribute: `status`, `geaendert`, `eingeschlafen`, `aufgewacht` |
| `sensor.healthy_eingeschlafen` | Zeitpunkt des letzten Einschlafens |
| `sensor.healthy_aufgewacht` | Zeitpunkt des letzten Aufwachens |

Die Healthy-App meldet Einschlafen und Aufwachen sofort an das Watchface, das den Status ans Handy weitergibt. Der letzte Stand bleibt nach einem Home-Assistant-Neustart erhalten.

### Umstieg von der Mobile-App-Integration

IoSync bis 5.3.0 hat den Schlafstatus über die Mobile-App-Integration gemeldet. Ab 5.3.1 nutzt die App automatisch diese Integration, sobald sie eingerichtet ist, sonst weiterhin den alten Weg.

Damit die Entitäten ihre bisherigen IDs behalten, **vor** dem Einrichten dieser Integration das alte Gerät löschen: Einstellungen → Geräte & Dienste → Mobile App → Gerät **Healthy** → Löschen. Sonst bekommen die neuen Entitäten die Endung `_2`.

### Beispiel-Automation

```yaml
automation:
  - alias: Heizung absenken beim Einschlafen
    triggers:
      - trigger: state
        entity_id: binary_sensor.healthy_schlaf
        to: "on"
    actions:
      - action: climate.set_temperature
        target:
          entity_id: climate.schlafzimmer
        data:
          temperature: 17
```

## Schnittstelle für die App

Beide Endpunkte verlangen den Langzeit-Token (`Authorization: Bearer …`). Ist die Integration nicht eingerichtet, antworten sie mit `404`.

**`GET /api/iosync`** → `{"api_version": 1, "version": "1.0.0"}`

**`POST /api/iosync/update`**

```json
{
  "device": {"id": "uuid", "name": "Healthy", "manufacturer": "letheapp", "model": "Schlafstatus Uhr", "sw_version": "5.3.1"},
  "sensors": [
    {"key": "healthy_sleeping", "type": "binary_sensor", "name": "Schlaf", "state": true,
     "icon": "mdi:sleep", "attributes": {"status": "schläft"}},
    {"key": "healthy_sleep_start", "type": "sensor", "name": "Eingeschlafen",
     "state": "2026-11-23T22:41:00Z", "device_class": "timestamp"}
  ],
  "events": [{"type": "fell_asleep", "data": {}}]
}
```

| Feld | Bedeutung |
|---|---|
| `device.id` | Feste ID des Geräts (`A-Z a-z 0-9 _ -`, max. 64) |
| `sensors[].key` | Feste ID des Sensors innerhalb des Geräts (`a-z 0-9 _`) |
| `sensors[].type` | `sensor` oder `binary_sensor` |
| `sensors[].state` | Wert; `null` = unbekannt. Zeitstempel als ISO 8601 |
| `device_class`, `unit`, `state_class`, `entity_category`, `icon`, `attributes` | optional, wie in Home Assistant |
| `events[]` | löst das Ereignis `iosync_event` aus (`device_id`, `type`, `data`) |

Gelöschte Geräte legt die Integration neu an, sobald die App wieder sendet.

## Lizenz

[GPL-3.0](LICENSE)
