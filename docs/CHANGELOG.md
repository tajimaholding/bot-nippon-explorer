# Historique des versions de NEObot

## v2.8.1 / LOT QUESTIONNAIRE — Suppression du flux MP (août 2026)

- Le questionnaire en messages privés est **entièrement supprimé** : l'onboarding se fait exclusivement dans le serveur (bouton 🌸 ou `/questionnaire`, messages éphémères).
- À l'arrivée : rôle Curieux + message public facultatif de bienvenue mentionnant le nouveau et pointant vers le bouton (clé `SALON_FALLBACK`, sémantique mise à jour).
- Le bloc « On t'accompagne » se désactive en vidant `SALON_GUIDE` dans Config (l'onglet Découverte le remplace avantageusement).

## v2.8 / LOT QUESTIONNAIRE — Questionnaire en salon (août 2026)

- Le bouton 🌸 Commencer et `/questionnaire` (utilisé sur le serveur) déroulent le questionnaire **en messages éphémères dans le salon** : visible uniquement par le membre, sans MP, sans quitter le serveur — idéal débutants et MP fermés.
- Le MP automatique à l'arrivée est conservé (flux historique), avec le bouton comme rattrapage universel.
- Refactorisation : fin de questionnaire commune aux deux flux (rôles, enregistrement, journal, redirection guide).
- Le message de fin liste les **salons désormais accessibles** avec liens cliquables et descriptions — nouvel onglet **Découverte** (Salon / Description), filtré automatiquement selon les accès réels du membre.

## v2.7 / LOT SALONS — Grille d'accès pilotée par le Sheet (juillet 2026)

- Nouvel onglet **Zones** : Catégorie / Rôle (ou `@everyone`) / Accès (`aucun`, `voir`, `voir-sans-historique`, `voir-reagir`, `ecrire`).
- Nouvelle commande admin `/synchro-salons` : aperçu par catégorie (réglages à poser, salons à resynchroniser, exceptions intactes, avertissements, catégories non gérées) → confirmation → application au niveau **catégories** + resynchronisation de leurs salons.
- Clé Config `SALONS_EXCEPTIONS` : liste de noms de salons (séparés par `;`, sans emoji, accents facultatifs) jamais touchés — salons d'intérêt 🔒, exceptions de la Zone 0, etc.
- Garde-fous : aucune création ni suppression ; catégories absentes du Sheet jamais touchées ; réglages des rôles non listés conservés ; rappel du test « compte sans rôle » après chaque application.
- 5 nouveaux tests automatiques (construction du plan, exceptions, resynchronisation, avertissements).

## v2.6 / LOT 5ter — Journal des arrivées (juillet 2026)

- Cause racine des compteurs à zéro identifiée : le rôle NEObot n'avait pas **« Gérer le serveur »** — sans elle, Discord renvoie la liste des invitations mais avec des compteurs vides, sans erreur. Permission ajoutée, compteurs fiables.
- Retour de l'identification du lien utilisé à chaque arrivée (tâche de fond, lectures à 0/2,5/10 s), **journalisation seule** : ligne dans l'onglet **Arrivées** (date, pseudo, ID, code, étiquette). Aucune attribution de rôle par ce canal — les rôles Team restent attachés aux liens natifs Discord.
- Onglet **Invitations** simplifié à deux colonnes : Code / Étiquette. Tout lien classique collé ici est suivi avec un libellé lisible (influenceur, événement promo…) ; un lien non listé est journalisé avec son code brut.

## v2.5 / LOT 5 révisé — Compteurs et fiche membre (juillet 2026)

- **Abandon de la détection d'invitation par comparaison de compteurs** : les tests ont montré que Discord fournit au bot des compteurs durablement faux sur ce serveur (8 utilisations côté interface, 0 côté API pendant plus d'une heure). L'attribution des rôles Team se fait désormais par les **liens d'invitation natifs de Discord** (rôle attaché au lien à sa création) — plus simple et fiable.
- Retirés : onglets Invitations/Arrivées, `/invitations`, cache des compteurs, tâches de détection. Conservé : l'accueil attend l'acceptation des règles (mode Communauté).
- Nouvelles commandes admin : `/compter-role` (membres ayant un rôle donné, bots exclus), `/compter-invitation` (utilisations d'un lien, avec avertissement de fiabilité), `/membre` (fiche : date d'arrivée, ancienneté, rôles, statut règles — recherche par @ ou pseudo).

## v2.4.1 / LOT 5 correctif — Compatibilité mode Communauté (juillet 2026)

- L'accueil (rôle d'invitation, Curieux, questionnaire) attend désormais que le membre ait **accepté les règles** du serveur : Discord bloque rôles et MP tant qu'il est « en attente ». Reprise automatique dès l'acceptation.
- La détection d'invitation **réessaie après 2,5 s** si le compteur Discord est en retard sur l'événement d'arrivée (cause des « indéterminé » observés en test).
- Découverte documentée : le profil membre Discord (« Méthode d'adhésion ») affiche le premier lien jamais utilisé par le compte, même après expulsion/retour — ne pas s'y fier, l'onglet Arrivées fait foi.
- 3 nouveaux tests automatiques (compteur en retard, aucune variation, détection immédiate).

## v2.4 / LOT 5 — Suivi des invitations par influenceur (juillet 2026)

- Nouvel onglet **Invitations** du Sheet : Code (ou lien complet) / Étiquette (influenceur) / Rôle à attribuer.
- À chaque arrivée : détection de l'invitation utilisée (comparaison des compteurs avant/après), attribution automatique du rôle Team, enregistrement dans le nouvel onglet **Arrivées** (date, pseudo, ID, code, influenceur, rôle) — auto-créé.
- Cas ambigus (deux arrivées simultanées, redémarrage) enregistrés comme « indéterminé » plutôt que mal attribués ; resynchronisation des compteurs à chaque reconnexion et sur création/suppression d'invitation.
- Nouvelle commande admin `/invitations` : utilisations par influenceur en direct + invitations non suivies.
- 9 nouveaux tests automatiques (normalisation des codes, détection avant/après, ambiguïtés, invitation épuisée).
- Prérequis : permission « Gérer le serveur » (couverte par le réglage « tout sauf Administrateur » du LOT 4).

## v2.3 / LOT 4 — Gestion des rôles pilotée par le Sheet (juillet 2026)

- Nouvel onglet **Rôles** du Google Sheet : Nom / Couleur (hex ou nom français) / Séparé / Mentionnable / Permissions (mots-clés français).
- Nouvelle commande admin `/synchro-roles` : aperçu complet (créations, modifications détaillées, rôles hors de portée, orphelins, avertissements) puis application seulement après clic sur « Confirmer ».
- Garde-fous : aucune suppression de rôle, jamais ; mots-clés `administrateur`, `gerer-serveur`, `gerer-webhooks` refusés ; rôles gérés par Discord ignorés ; cellule Permissions vide = permissions non touchées ; ligne `@everyone` acceptée (permissions uniquement).
- Audit de chaque synchronisation dans `SALON_LOGS` ; premiers tests automatiques du projet (8 cas sur les analyseurs).
- Prérequis documenté suite aux tests : le rôle NEObot doit avoir toutes les permissions sauf Administrateur (Discord exige que l'éditeur d'un rôle possède toutes les permissions de ce rôle, même inchangées).

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
