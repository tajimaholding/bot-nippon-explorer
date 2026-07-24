# Commandes et interactions de NEObot

*Dernière mise à jour : LOT 1 (état v2).*

## Commandes visibles par tous

### /questionnaire
(Re)lance le questionnaire d'accueil en message privé. Utilisable par tout membre, à tout moment (les réponses précédentes restent dans le Sheet ; une nouvelle ligne est ajoutée).

### Bouton 🌸 Commencer (salon #bienvenue)
Même effet que `/questionnaire`. Bouton **persistant** : il survit aux redémarrages du bot.

## Commandes réservées aux administrateurs

### /installer-bouton
Publie dans le salon courant le message d'accueil avec le bouton 🌸 Commencer. À n'exécuter normalement qu'une fois, dans `#bienvenue`.

### /synchro-veterans
Donne le rôle `Vétéran` à tout membre possédant un rôle commençant par « Vétéran lvl ». Compte-rendu : nombre d'ajouts et d'échecs.

### /recharger
Recharge questions et configuration depuis le Google Sheet. À exécuter après **chaque** modification du Sheet. Affiche la liste des questions chargées.

### /export
Envoie toutes les réponses en CSV (séparateur `;`, encodage compatible Excel). Réponse éphémère (visible uniquement par l'admin).

## Comportements automatiques

| Événement | Action |
|---|---|
| Arrivée d'un membre | Rôle `ROLE_ARRIVEE` (Curieux) + questionnaire en MP |
| MP fermés à l'arrivée | Message d'orientation dans `SALON_FALLBACK` (si configuré) |
| Fin de questionnaire | Rôles des réponses + `ROLE_FINAL`, retrait `ROLE_ARRIVEE`, enregistrement Sheet, résumé dans `SALON_LOGS` (si configuré) |
| Réponse « Je débute sur Discord » | Le message de fin pointe vers le salon `SALON_GUIDE` |

---

# Procédures de test manuel

## TEST 1 — Parcours d'accueil complet

Préconditions : bot en ligne ; rôles `Curieux`, `Visiteur` et rôles Teams existants ; rôle NEObot au-dessus d'eux ; compte de test avec MP ouverts.

Action : rejoindre le serveur avec le compte de test (ou se donner `Curieux` puis cliquer 🌸 Commencer) ; répondre aux 6 questions, dont « Je débute sur Discord » à la question 1 et « Fildrong » à la question provenance.

Résultat attendu : questionnaire fluide en MP ; message de fin mentionnant `Team Fildrong` et `Visiteur`, avec le lien vers le salon guide ; `Curieux` retiré ; nouvelle ligne dans l'onglet Réponses ; résumé dans `SALON_LOGS` si configuré ; aucune erreur dans les logs Render.

## TEST 2 — MP fermés

Préconditions : compte de test avec MP désactivés pour le serveur ; `SALON_FALLBACK` configuré.

Action : rejoindre le serveur (ou cliquer le bouton).

Résultat attendu : pas de plantage ; message d'orientation dans le salon de secours (arrivée) ou message éphémère expliquant comment ouvrir ses MP (bouton).

## TEST 3 — Rôle introuvable

Préconditions : dans le Sheet, mapper temporairement une réponse vers un rôle inexistant (ex. `Test=RoleFantome`), puis `/recharger`.

Action : faire le questionnaire en choisissant cette réponse.

Résultat attendu : le questionnaire se termine normalement ; le rôle manquant est listé dans « Rôles introuvables » du résumé `SALON_LOGS` ; les autres rôles sont bien attribués. Remettre le Sheet en état puis `/recharger`.

## TEST 4 — Rôle du bot trop bas

Préconditions : déplacer temporairement le rôle NEObot sous `Visiteur`.

Action : faire le questionnaire.

Résultat attendu : pas de plantage ; échec signalé dans le résumé (« rôle du bot trop bas dans la liste »). Replacer le rôle NEObot en haut ensuite.

## TEST 5 — /synchro-veterans

Préconditions : rôle `Vétéran` créé ; au moins un membre avec un rôle « Vétéran lvl N » sans le rôle `Vétéran` ; rôle NEObot au-dessus de `Vétéran`.

Action : exécuter `/synchro-veterans`.

Résultat attendu : compte-rendu « Rôle Vétéran donné à N membre(s) » ; les membres concernés ont le rôle ; une seconde exécution donne 0 ajout (pas de doublon).

## TEST 6 — /recharger et /export

Action : modifier le libellé d'une option dans le Sheet → `/recharger` → vérifier la liste affichée → `/export` → ouvrir le CSV.

Résultat attendu : modification visible dans la liste ; CSV lisible dans Excel avec accents corrects et toutes les lignes de l'onglet Réponses. Remettre le libellé d'origine puis `/recharger`.

## TEST 7 — Non-régression après redéploiement

Action : sur Render, Manual Deploy → Deploy latest commit ; attendre la fin ; cliquer le bouton 🌸 Commencer d'un message publié AVANT le redéploiement.

Résultat attendu : logs `🤖 Connecté...` et `✅ ... questions chargées` ; le bouton répond toujours (persistance) ; `/questionnaire` fonctionne.
