# VISTA — Plugin QGIS per ispezione stradale

Plugin QGIS per l'ispezione stradale: assegnazione progressive ettometriche, popolamento codici difetti (Capitolo/Sottocapitolo/Descrizione) e generazione di report Word con foto.

Compatibile con QGIS 3.x (Qt5) e QGIS 4.x (Qt6).

## Installazione da QGIS

1. Apri QGIS → **Plugin → Gestisci e installa plugin → Impostazioni**
2. Nella sezione **Repository dei plugin** clicca **Aggiungi**
3. Inserisci:
   - **Nome:** VISTA Repository
   - **URL:** `https://raw.githubusercontent.com/eugenio3006/vista-qgis-plugin/main/plugins.xml`
4. Clicca OK, poi vai nella scheda **Tutti**, cerca "VISTA" e clicca **Installa**

Gli aggiornamenti futuri compariranno automaticamente nel gestore plugin di QGIS.

## Per lo sviluppatore: pubblicare una nuova versione

1. Aggiorna il campo `version=` in `vista_v2/metadata.txt` (es. `2.1.0`)
2. Committa e pusha su `main`
3. Crea e pusha il tag corrispondente:

   ```bash
   git tag v2.1.0
   git push origin v2.1.0
   ```

La GitHub Action farà il resto: crea lo zip, pubblica la release e aggiorna `plugins.xml` con la nuova versione e il nuovo link di download.

> **Nota:** il tag deve corrispondere alla versione in `metadata.txt` (tag `v2.1.0` ↔ `version=2.1.0`), altrimenti la Action si ferma con un errore.

## Struttura del repository

```
vista-qgis-plugin/
├── vista_v2/                    # codice sorgente del plugin
│   ├── metadata.txt
│   ├── __init__.py
│   └── ...
├── plugins.xml                  # catalogo letto da QGIS (aggiornato dalla Action)
└── .github/workflows/release.yml
```

## Autore

Eugenio Liccardi
