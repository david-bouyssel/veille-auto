# Le site : `scripts/build.py` et `templates/page.html`

## Génération

```bash
python scripts/build.py          # valide toutes les éditions et génère docs/
python scripts/build.py --check  # valide seulement, n'écrit rien
```

`build.py` :

1. lit `config/sources.json` et la liste des `id` de rubriques ;
2. charge et valide toutes les éditions de `data/editions/`, dans l'ordre des noms de fichier (voir [format-edition.md](format-edition.md)) ;
3. s'arrête avec le code `1` à la première édition invalide, après avoir listé toutes les erreurs ;
4. numérote les éditions valides à partir de 1 ;
5. écrit une page par édition dans `docs/editions/AAAA-MM-JJ.html` ;
6. écrit la dernière édition dans `docs/index.html` ;
7. crée `docs/.nojekyll` pour que GitHub Pages serve les fichiers tels quels ;
8. valide `config/mods.json` et copie `vendor/` dans `docs/vendor/` (lecteur du chiptune du jour).

Le site est regénéré entièrement à chaque build. `docs/` est ignoré par git : ne le commite jamais.

## Sortie

```text
docs/
├── .nojekyll
├── index.html                  dernière édition
├── vendor/chiptune3/           lecteur de modules (copie de vendor/)
└── editions/
    ├── 2026-11-22.html
    └── …
```

## Le gabarit

`templates/page.html` est un fichier unique avec le HTML, le CSS et le JavaScript inline. `build.py` y remplace deux marqueurs :

| Marqueur | Remplacé par |
| --- | --- |
| `__TITRE__` | `Le Petit Compilé · n° N · AAAA-MM-JJ` |
| `__DATA__` | Les données de la page, en JSON, dans `<script type="application/json" id="data">` |

Le JSON est protégé pour l'intégration dans une balise `<script>` : `</` devient `<\/`, et les séparateurs U+2028 et U+2029 sont échappés.

### Données injectées

```json
{
  "config": {
    "timezone": "Europe/Paris",
    "rubriques": [{"id": "secu", "nom": "Sécurité", "couleur": "#e5484d"}]
  },
  "edition": { "date": "…", "numero": 1, "une": {}, "items": [] },
  "mod": {
    "artiste": "…", "titre": "…", "format": "XM", "ko": 114, "licence": "…",
    "fichier": "https://api.modarchive.org/downloads.php?moduleid=…",
    "page": "https://modarchive.org/index.php?request=view_by_moduleid&query=…",
    "selection": {"nom": "Krelez", "url": "https://www.youtube.com/@Krelez"}
  },
  "lecteur": "./vendor/chiptune3/chiptune3.js",
  "archive": [
    {"numero": 1, "date": "…", "href": "editions/….html",
     "items": [{"rubrique": "…", "titre": "…", "url": "…"}]}
  ],
  "nav": {
    "accueil": "../index.html",
    "precedente": "AAAA-MM-JJ.html",
    "suivante": "AAAA-MM-JJ.html"
  }
}
```

- `archive` contient les `archive_editions` éditions précédant celle affichée, de la plus récente à la plus ancienne.
- Les liens sont relatifs. Depuis `index.html`, ils pointent vers `editions/…` ; depuis une page d'édition, vers le même dossier.
- Sur `index.html`, `nav.accueil` et `nav.suivante` valent `null`.
- `mod` vaut `null` si `config/mods.json` est absent ou vide.
- `lecteur` est relatif à la page : `./vendor/…` depuis `index.html`, `../vendor/…` depuis une édition.

### Le chiptune du jour

`config/mods.json` liste des modules (MOD, XM, IT, S3M) de [The Mod Archive](https://modarchive.org/). Les morceaux viennent des « Random chiptune mix » de la chaîne YouTube Krelez ; chacun a été retrouvé et vérifié sur Mod Archive (artiste, format, licence).

| Champ | Contenu |
| --- | --- |
| `id` | Identifiant Mod Archive (`moduleid`) |
| `artiste`, `titre` | Affichés dans la page |
| `format` | `MOD`, `XM`, `IT` ou `S3M` |
| `ko` | Taille du fichier en Ko, affichée avant le chargement |
| `licence` | Licence indiquée sur Mod Archive |
| `mix` | Numéro du mix Krelez où le morceau apparaît, clé de l'objet `mixes` (facultatif, non affiché : sert à retrouver la provenance) |

`mixes` associe un numéro de mix à l'identifiant de la vidéo YouTube.

`selection` (facultatif) crédite l'origine de la sélection : `{"nom": "Krelez", "url": "https://www.youtube.com/@Krelez"}`. La page affiche « Sélection : Krelez » à côté de la source.

Le choix est déterministe : l'édition du jour `d` reçoit `mods[d.toordinal() % len(mods)]`. La liste défile donc dans son ordre, un morceau par jour, puis recommence. Ajouter ou retirer un morceau décale l'attribution des éditions suivantes et des pages déjà générées, ce qui est sans conséquence.

Pour ajouter un morceau : trouve-le sur Mod Archive, note son `id` (dans l'URL `view_by_moduleid&query=…`), son format, sa taille et sa licence, puis lance `python scripts/build.py --check`.

Rien n'est téléchargé au build ni stocké dans le dépôt : la page lit le fichier directement depuis `api.modarchive.org`, qui autorise les requêtes d'autres origines (CORS).

### Fonctionnement de la page

Le script de la page lit `#data` et construit tout le contenu côté navigateur :

- **Bandeau** « Le Petit Compilé », date et numéro de l'édition.
- **À la une** : grand article, couleur de sa rubrique.
- **Rubriques** dans l'ordre de `config/sources.json`, seulement celles qui ont des articles.
- **Sommaire** : filtres par rubrique avec le nombre d'articles, recherche plein texte dans l'édition, case « Masquer les articles lus ».
- **Articles lus** : bouton par article, et marquage automatique au clic sur le lien.
- **Lien HN** : points et commentaires si `hn` est renseigné.
- **Navigation** entre éditions et **archives** des éditions précédentes.
- **Thème** clair ou sombre : suit le système, ou le choix du lecteur.
- **Le chiptune du jour**, sous le titre, sur trois lignes : le libellé ; le bouton « Écouter », l'artiste, le titre, le format, la taille et, pendant la lecture, le temps écoulé et la durée ; le volume (icône de haut-parleur et curseur) la source, un lien vers la fiche Mod Archive avec la licence en infobulle, et la sélection, un lien vers la chaîne YouTube Krelez. Rien n'est chargé avant le clic sur « Écouter » : le lecteur `chiptune3` (libopenmpt en WebAssembly, dans un AudioWorklet) est alors importé, puis le module est téléchargé et joué en boucle. Le bouton bascule ensuite entre pause et lecture. Un curseur règle le volume. En cas d'échec, le bandeau affiche la cause (« Lecteur introuvable », « Téléchargement impossible », « Navigateur non compatible »…) et la console donne le détail.

### Stockage local

La page garde les préférences du lecteur dans `localStorage`, toujours dans un `try/catch` : elle fonctionne aussi sans stockage.

| Clé | Contenu |
| --- | --- |
| `va-theme` | `light` ou `dark` |
| `va-read` | URL des articles lus (1 500 au plus, les plus anciennes sont retirées) |
| `va-filter` | Filtre de rubrique sélectionné |
| `va-hide` | `1` si les articles lus sont masqués |
| `va-mod-vol` | Volume du chiptune du jour, de `0` à `1` |

### Sécurité du rendu

Tout texte issu des éditions passe par `esc()` avant insertion dans le HTML. Les liens passent par `safeUrl()`, qui remplace toute URL non `http(s)` par `#`. Garde ces deux fonctions pour tout nouveau contenu dynamique.

### Dépendances externes

Les polices Google Fonts (Newsreader et Instrument Sans) sont chargées depuis l'extérieur. Sans elles, la page retombe sur les polices système.

Le chiptune du jour télécharge son module depuis `api.modarchive.org`, seulement au clic sur « Écouter ».

Le lecteur `chiptune3` 0.8.10 (MIT, avec libopenmpt sous licence BSD) est copié dans `vendor/chiptune3/`, sans CDN. Pour le mettre à jour, remplace les fichiers `chiptune3.js`, `chiptune3.worklet.js`, `libopenmpt.worklet.js` et `LICENSE` par ceux du paquet npm `chiptune3`.

## Numéro de version

Le bas de page affiche `v0.0.N` en petit gras. `build.py` calcule `N` avec `git rev-list --count HEAD` moins `BASE_COMMITS` : chaque commit l'incrémente, et le commit qui a introduit ce numéro est la version 0.0.1. `N` n'a pas de plafond (0.0.9 puis 0.0.10). Les deux premiers chiffres (`VERSION_MAJEUR`, `VERSION_MINEUR`) ne changent qu'à la demande de l'auteur ; on remet alors `BASE_COMMITS` au nombre de commits courant pour repartir de 0. Ce numéro est indépendant des tags posés à la main. Le job `build` de `publish.yml` récupère l'historique complet (`fetch-depth: 0`), sinon le compte serait faux. Sans git, la page affiche `v0.0.0`.

## Prévisualiser en local

```bash
python scripts/build.py
python -m http.server 8000 --directory docs
```

Ouvre ensuite `http://localhost:8000/`. Tu peux aussi ouvrir `docs/index.html` directement dans le navigateur : la page s'affiche sans serveur, mais le chiptune du jour ne se lance pas en `file://`, car le navigateur refuse alors de charger le module JavaScript du lecteur.
