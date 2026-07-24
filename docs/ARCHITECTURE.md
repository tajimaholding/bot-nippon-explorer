# Architecture de NEObot

*Document de référence — à mettre à jour à chaque lot qui modifie la structure.*
*Dernière mise à jour : LOT 3 (état v2.2).*

## 1. Vue d'ensemble

```text
Membre Discord                    Administrateur
      │                                 │
      ▼                                 ▼
┌─────────────────────────────────────────────┐
│              Serveur Discord                │
│  (rôles, salons, boutons, commandes /)      │
└──────────────────┬──────────────────────────┘
                   │ API Discord (discord.py)
                   ▼
┌─────────────────────────────────────────────┐
│   NEObot — bot.py, hébergé sur Render       │
│   + mini serveur web (anti-veille)          │
└──────────────────┬──────────────────────────┘
                   │ API Google Sheets (gspread)
                   ▼
┌─────────────────────────────────────────────┐
│   Google Sheet                              │
│   Questions │ Config │ Réponses             │
└─────────────────────────────────────────────┘
```

## 2. Choix d'architecture assumé : fichier unique

Le code tient dans un seul fichier `bot.py` (~556 lignes), découpé en 7 sections numérotées. Ce choix est **volontaire** à ce stade : le mainteneur met à jour le bot par copier-coller intégral dans GitHub, et un fichier unique rend cette opération sûre et simple. Le passage à une arborescence modulaire (`src/commands/`, `src/services/`, etc.) est planifié pour le lot qui introduira la base de données, où il deviendra nécessaire.

## 3. Rôle de chaque section de bot.py

| Section | Responsabilité | Équivalent modulaire futur |
|---|---|---|
| 1. Serveur web | Répondre aux pings d'UptimeRobot (anti-veille Render) | `src/utils/keepalive` |
| 2. Google Sheets | Lecture Questions/Config, écriture Réponses. Seule section qui touche aux données | `src/repositories/` |
| 3. Outils rôles | `trouver_role`, `obtenir_membre` (fonctions génériques) | `src/utils/` |
| 4. Questionnaire | Logique métier : déroulé des questions en MP, attribution des rôles, journalisation | `src/services/onboarding` |
| 5. Bouton Commencer | Vue persistante du salon d'accueil | `src/events/` |
| 5bis. Menu intérêts | Boutons à bascule persistants donnant/retirant les rôles d'accès thématiques | `src/commands/roles/` |
| 5ter. Annonces | Bouton « Ça m'intéresse » persistant, compteur, écriture onglet Annonces | `src/commands/travel/` |
| 6. Bot + commandes | Réception des commandes/événements Discord, appels aux sections 2-4, réponses | `src/commands/` + `src/events/` |
| 7. Démarrage | Lancement serveur web + bot | point d'entrée |

La séparation des responsabilités du cahier des charges (commands → services → repositories) est donc déjà respectée *logiquement*, à défaut de l'être *physiquement* en dossiers.

## 4. Flux principaux

**Onboarding (flux central) :**
`on_member_join` → ajout rôle `ROLE_ARRIVEE` (Curieux) → `derouler_questionnaire` (MP, menus cliquables, 15 min max/question) → `attribuer_roles` (rôles des réponses + `ROLE_FINAL`, retrait de `ROLE_ARRIVEE`) → `enregistrer_reponses` (ligne dans l'onglet Réponses) → message de fin (+ lien salon guide si débutant Discord) → `journaliser` (salon `SALON_LOGS` si défini).

**Voies de rattrapage :** bouton 🌸 Commencer (`#bienvenue`) et `/questionnaire` mènent au même `derouler_questionnaire`. MP fermés → message dans `SALON_FALLBACK`.

**Configuration :** modification du Google Sheet → `/recharger` → `charger_donnees()` recharge tout en mémoire (variables globales `QUESTIONS` et `CONFIG`).

**Export :** `/export` → lecture de l'onglet Réponses → fichier CSV (UTF-8-sig, séparateur `;`) envoyé en réponse éphémère.

## 5. Données manipulées

| Donnée | Stockage | Persistance |
|---|---|---|
| Questions, options, mapping rôles | Sheet « Questions » | ✅ persistant |
| Réglages (ROLE_FINAL, SALON_LOGS…) | Sheet « Config » | ✅ persistant |
| Boutons d'intérêt (étiquette, rôle, emoji) | Sheet « Intérêts » | ✅ persistant |
| Intéressés par annonce (ID annonce, titre, pseudo, ID, date) | Sheet « Annonces » | ✅ persistant |
| Profils : date, pseudo, ID Discord, réponses | Sheet « Réponses » | ✅ persistant |
| Sessions de questionnaire en cours | Mémoire (`sessions_en_cours`) | ❌ perdu au redémarrage (acceptable : le membre reclique sur Commencer) |

Aucune donnée critique n'est conservée uniquement en mémoire.

## 6. Dépendances

| Bibliothèque | Rôle | Justification |
|---|---|---|
| `discord.py` ≥ 2.4 | Client Discord (commandes /, boutons, menus, événements) | Bibliothèque Python de référence |
| `gspread` ≥ 6.0 | Lecture/écriture Google Sheets | Standard de fait pour Sheets en Python |
| `google-auth` ≥ 2.0 | Authentification du compte de service Google | Requis par gspread |

## 7. Connexions externes et pannes

| Connexion | Si elle tombe |
|---|---|
| API Discord | Le bot est hors ligne ; discord.py se reconnecte automatiquement |
| API Google Sheets | Le questionnaire continue (questions en mémoire) ; l'enregistrement échoue et l'erreur est tracée dans les logs Render (`[ERREUR Google Sheets]`) sans faire tomber le bot |
| Render (veille) | UptimeRobot pinge toutes les 5 min ; en cas de veille, réveil au prochain ping |

Limite connue : pendant une veille ou un redéploiement Render, un `on_member_join` peut être manqué → le membre garde le bouton Commencer comme rattrapage.

## 8. Sécurité

Secrets exclusivement dans les variables d'environnement Render (`DISCORD_TOKEN`, `SHEET_ID`, `GOOGLE_CREDENTIALS_JSON`) — voir docs/ENVIRONMENT.md. Le Google Sheet n'est partagé qu'avec le compte de service. Les commandes d'administration sont restreintes par `default_permissions(administrator=True)`. Aucun secret n'apparaît dans les logs ni dans les messages d'erreur envoyés aux membres.

## 9. Évolution prévue

LOT 2 (fait, v2.1) : salon de redirection par boutons. LOT 3 (fait, v2.2) : `/annonce` avec mesure de la demande. LOT 2bis/3bis (proposés) : pré-attribution des accès selon le questionnaire ; clôture automatique des annonces complètes. LOT 4 : base de données Postgres + découpage en modules + premiers tests automatiques — ce lot mettra à jour le présent document.
