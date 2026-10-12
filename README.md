# Cryptoast → Nostr auto-poster

Publie automatiquement les nouveaux articles du feed Cryptoast BTC sur Nostr.

## Déploiement (5 minutes)

### 1. Forker ce dépôt

- Clique sur **Fork** en haut de la page (ou crée un nouveau dépôt et pousse-y les fichiers)
- Public ou privé, au choix : ta clé Nostr reste dans les secrets GitHub, jamais dans le code

### 2. Ajouter le secret NOSTR_NSEC

Dans le repo GitHub :
**Settings → Secrets and variables → Actions → New repository secret**

- Name : `NOSTR_NSEC`
- Value : ta clé privée Nostr (format `nsec1...`)

### 3. Activer GitHub Actions

Le workflow tourne automatiquement toutes les **30 minutes**.

Pour tester manuellement :
**Actions → Cryptoast → Nostr → Run workflow**

## Structure

```
├── nostr_poster.py          # script principal
├── requirements.txt         # dépendances Python
├── posted.json              # URLs déjà postées (auto-mis à jour)
└── .github/
    └── workflows/
        └── post.yml         # cron GitHub Actions
```

## Comportement

- Lit le feed `https://cryptoast.fr/btc,bitcoin/feed`
- Publie uniquement les nouveaux articles (non présents dans `posted.json`)
- Format du post :
  ```
  📰 [Titre]

  [Extrait de l'article]

  👉 [Lien]

  #nostrfr
  ```
- Relays : nos.lol, nostr.land, nostr.wine, relay.damus.io
- `posted.json` est committé automatiquement après chaque run

## Modifier la fréquence

Dans `.github/workflows/post.yml`, changer la ligne cron :
- Toutes les 15 min : `"*/15 * * * *"`
- Toutes les heures : `"0 * * * *"`
- Une fois par jour à 8h : `"0 8 * * *"`

## Licence

Code sous licence [MIT](LICENSE) : libre d'utilisation, de modification, de fork et de redistribution, y compris à des fins commerciales, à condition de conserver la mention de copyright.
