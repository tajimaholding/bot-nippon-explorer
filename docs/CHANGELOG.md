# Historique des versions de NEObot

## v2.2 / LOT 3 — Annonces de créneaux de voyage (juillet 2026)

- Nouvelle commande admin `/annonce` : publie un embed (titre, dates, prix, places, lien de réservation, description) dans le salon courant.
- Bouton persistant « ✋ Ça m'intéresse » à bascule avec compteur affiché en direct sur l'annonce.
- Intéressés enregistrés dans le nouvel onglet **Annonces** du Google Sheet (ID annonce, titre, pseudo, ID Discord, date) — créé automatiquement au premier clic.
- Aucun changement au questionnaire, au menu des intérêts ni aux dépendances.

## v2.1 / LOT 2 — Menu des centres d'intérêt (juillet 2026)

- Boutons à bascule persistants : un clic donne le rôle d'accès au salon thématique, un second le retire (réponse éphémère de confirmation).
- Configuration sans code dans le nouvel onglet **Intérêts** du Google Sheet (colonnes Étiquette / Rôle / Emoji), appliquée par `/recharger`.
- Nouvelle commande admin `/installer-menu-interets` : publie le menu dans le salon courant (répartition automatique en messages de 25 boutons maximum, signalement des rôles manquants).
- Aucun changement au questionnaire ni aux dépendances.

## LOT 1 — Socle documentaire (juillet 2026)

Aucune modification de code. Création de README.md, docs/ARCHITECTURE.md, docs/COMMANDS.md, docs/ENVIRONMENT.md, docs/CHANGELOG.md et .gitignore. Adoption officielle du cadre de développement par lots (Python, workflow GitHub web, découpage modulaire différé au lot base de données).

## v2 — Socle accueil (juillet 2026)

- Rôle automatique à l'arrivée (`ROLE_ARRIVEE`, Curieux) ; retiré à la fin du questionnaire au profit de `ROLE_FINAL` (Visiteur).
- Bouton persistant 🌸 Commencer + commande `/installer-bouton` pour le publier dans `#bienvenue`.
- Question « aisance Discord » (via le Sheet) avec orientation des débutants vers `#débuter-sur-discord` (`GUIDE_QUESTION`, `GUIDE_REPONSES`, `SALON_GUIDE`).
- `/synchro-veterans` : rôle parapluie `Vétéran` pour les détenteurs d'un rôle « Vétéran lvl 1-7 ».
- Suppression du mapping `Autre=Visiteur` (remplacé par `ROLE_FINAL` pour tous).
- Préparation de l'ouverture au public : structure de catégories/permissions documentée (Accueil / Voyages / Communauté / Futurs voyageurs / Cercle Vétérans / Teams).

## v1 — Bot d'accueil initial (juillet 2026)

- Questionnaire d'accueil en MP (menus cliquables), 5 questions configurables dans un Google Sheet (onglets Questions/Config/Réponses).
- Attribution de rôles selon la provenance (Team Fildrong, Team Ascuns, Team Iconoclaste, Team ASMR, Team Edwin, Team Acekid, Filleul(e), Visiteur).
- Enregistrement des réponses dans le Sheet ; `/questionnaire`, `/recharger`, `/export`.
- Journalisation optionnelle (`SALON_LOGS`), salon de secours MP fermés (`SALON_FALLBACK`).
- Déploiement : GitHub → Render (plan gratuit) + UptimeRobot ; secrets en variables d'environnement.
