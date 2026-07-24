# 🌸 NEObot — Bot Discord officiel de Nippon Explorer

NEObot accueille les nouveaux membres du serveur Discord Nippon Explorer : questionnaire d'accueil en message privé, attribution automatique des rôles selon les réponses, enregistrement des profils dans un Google Sheet.

**Version actuelle : v2 (socle accueil)** — voir [docs/CHANGELOG.md](docs/CHANGELOG.md).

## Comment le projet fonctionne

Le projet n'est **pas installé sur un ordinateur** : il vit entièrement en ligne.

| Élément | Où | Rôle |
|---|---|---|
| Code (`bot.py`) | Ce dépôt GitHub | Le cerveau du bot |
| Exécution | [Render](https://render.com) (service `bot-nippon-explorer`) | Fait tourner le bot 24h/24 |
| Questionnaire + données | Google Sheet (onglets Questions / Config / Réponses) | Configuration et base de données |
| Secrets | Variables d'environnement sur Render | Jamais dans le code ni sur GitHub |
| Anti-veille | [UptimeRobot](https://uptimerobot.com) | Ping toutes les 5 min (plan gratuit Render) |

## Modifier le bot (workflow standard)

1. **Modifier le questionnaire** : éditer le Google Sheet, puis taper `/recharger` sur Discord. Aucun code.
2. **Modifier le code** : éditer `bot.py` sur GitHub (icône crayon ✏️) → **Commit changes** → Render redéploie automatiquement en 2-3 minutes.
3. **Vérifier** : onglet **Logs** sur Render → le message `🤖 Connecté en tant que NEObot` doit apparaître.
4. **Revenir en arrière** : sur GitHub, fichier → **History** → ouvrir la version précédente → la restaurer par copier-coller.

## Installation depuis zéro

La procédure complète (token Discord, compte de service Google, Render) est décrite dans le guide d'installation fourni séparément. Résumé : créer l'application sur le portail développeur Discord (intent SERVER MEMBERS activé), importer le questionnaire dans Google Sheets, partager le Sheet avec le compte de service, déployer ce dépôt sur Render avec les 3 variables d'environnement documentées dans [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

## Documentation

| Document | Contenu |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Composants, flux, dépendances, données |
| [docs/COMMANDS.md](docs/COMMANDS.md) | Commandes Discord + procédures de test manuel |
| [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) | Variables d'environnement et clés de configuration |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Historique des versions |

## Règles du projet

Développement par lots courts et testables, sauvegarde (commit) avant chaque lot, modification minimale, aucun secret dans le code, documentation tenue à jour. Le mainteneur n'est pas développeur : toute instruction doit être applicable par copier-coller.
