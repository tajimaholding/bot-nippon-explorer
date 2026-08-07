# Commandes et interactions de NEObot

*Dernière mise à jour : LOT QUESTIONNAIRE (état v2.8).*

## Commandes visibles par tous

### /questionnaire
(Re)lance le questionnaire d'accueil, déroulé en messages éphémères sur place (visible uniquement par le membre). Aucun MP, jamais. Les réponses précédentes restent dans le Sheet ; une nouvelle ligne est ajoutée.

### Bouton 🌸 Commencer (salon #bienvenue)
Lance le questionnaire en messages éphémères directement dans le salon — le membre ne quitte pas le serveur, aucun MP nécessaire. Bouton **persistant** : il survit aux redémarrages du bot. En cas d'inactivité (15 min sur une question), le questionnaire s'arrête silencieusement : recliquer pour recommencer.

### Bouton ✋ « Ça m'intéresse » (annonces de voyage)
Bouton persistant à bascule sous chaque annonce : un clic inscrit le membre parmi les intéressés (compteur mis à jour sur l'annonce, ligne ajoutée dans l'onglet **Annonces** du Sheet), un second clic le désinscrit. Sans engagement.

### Boutons 🎴 du menu des centres d'intérêt
Boutons à bascule persistants : un clic donne le rôle d'accès au salon thématique correspondant, un second clic le retire. Confirmation en message éphémère. Configuration : onglet **Intérêts** du Google Sheet (Étiquette / Rôle / Emoji) + `/recharger`.

## Commandes réservées aux administrateurs

### /installer-bouton
Publie dans le salon courant le message d'accueil avec le bouton 🌸 Commencer. À n'exécuter normalement qu'une fois, dans `#bienvenue`.

### /installer-menu-interets
Publie dans le salon courant le menu des centres d'intérêt (embed + boutons, 25 max par message — messages supplémentaires automatiques au-delà). Signale en éphémère les rôles configurés dans le Sheet mais absents du serveur. Pour mettre le menu à jour après modification du Sheet : `/recharger`, supprimer les anciens messages du menu, puis relancer la commande.

### /annonce
Publie une annonce de créneau de voyage dans le salon courant. Paramètres guidés : `titre`, `dates`, `prix`, `places`, `lien` (page de réservation), `description` (facultatif). L'annonce comporte le bouton ✋ Ça m'intéresse. Qui est intéressé par quoi : onglet **Annonces** du Google Sheet.

### /synchro-roles
Synchronise les rôles du serveur avec l'onglet **Rôles** du Google Sheet, en deux temps : un **aperçu** détaillé (créations, modifications champ par champ, rôles hors de portée, rôles du serveur absents du Sheet — jamais touchés, avertissements), puis application uniquement après clic sur **✅ Confirmer** (réservé à l'auteur de la commande, 5 minutes max).

Garde-fous : le bot ne supprime jamais un rôle ; `administrateur`, `gerer-serveur` et `gerer-webhooks` sont refusés (à donner à la main) ; les rôles gérés par Discord (bots, boosts) sont ignorés ; une cellule Permissions vide signifie « ne pas toucher aux permissions de ce rôle » (le mot-clé `aucune` met explicitement zéro permission) ; la ligne `@everyone` est acceptée (permissions uniquement).

**Onglet Rôles — colonnes :**

| Colonne | Contenu |
|---|---|
| Nom | Nom exact du rôle (ou `@everyone`) |
| Couleur | Code hex (`#E91E63`) ou nom : rouge, bleu, vert, jaune, orange, violet, rose, sakura, or, argent, turquoise, corail, marron, gris, noir, blanc. Vide = inchangée |
| Séparé | `oui` = affiché séparément dans la liste des membres |
| Mentionnable | `oui` / `non` |
| Permissions | Mots-clés séparés par `;` (voir ci-dessous), `aucune`, ou vide |

**Vocabulaire des permissions** (accents facultatifs) :

- Courantes : `voir-salons`, `envoyer-messages`, `historique`, `reactions`, `liens`, `fichiers`, `emojis-externes`, `stickers-externes`, `creer-fils`, `ecrire-dans-fils`, `commandes-bots`, `changer-pseudo`, `inviter`
- Vocal : `connecter`, `parler`, `video`, `couper-micro`, `rendre-sourd`, `deplacer-membres`
- Modération : `gerer-messages`, `gerer-fils`, `gerer-pseudos`, `gerer-salons`, `gerer-roles`, `gerer-evenements`, `expulser`, `bannir`, `exclure-temporairement`, `voir-journal-audit`, `mentionner-tout-le-monde`

⚠️ Ces permissions sont les permissions **générales** du rôle. Les accès salon par salon (qui voit quoi) restent gérés par les permissions de catégories dans Discord.

### /synchro-salons
Applique la grille d'accès de l'onglet **Zones** du Sheet aux **catégories** du serveur, en deux temps : aperçu détaillé par catégorie, puis application après clic sur ✅ Confirmer. Les salons de chaque catégorie sont resynchronisés sur elle, **sauf** ceux listés dans la clé Config `SALONS_EXCEPTIONS` (noms séparés par `;`, sans emoji).

**Onglet Zones — colonnes :** `Catégorie` (nom exact de la catégorie Discord) | `Rôle` (nom exact, ou `@everyone`) | `Accès` parmi :

| Accès | Effet |
|---|---|
| `aucun` | Ne voit pas la catégorie |
| `voir` | Voit + historique, sans écrire ni réagir |
| `voir-sans-historique` | Voit le salon mais pas les anciens messages |
| `voir-reagir` | Voit + historique + réactions, sans écrire |
| `ecrire` | Tout : voir, historique, réagir, écrire (+ fils) |

Garde-fous : aucune création/suppression ; catégories absentes du Sheet et rôles non listés jamais touchés. Après chaque application : **tester avec un compte sans rôle** (il ne doit voir que la Zone 0).

### /synchro-veterans
Donne le rôle `Vétéran` à tout membre possédant un rôle commençant par « Vétéran lvl ». Compte-rendu : nombre d'ajouts et d'échecs.

### /compter-role
Affiche le nombre de membres ayant le rôle choisi (les bots sont exclus du compte et signalés à part). Le rôle se choisit dans un sélecteur avec recherche.

### /compter-invitation
Affiche le nombre d'utilisations d'un lien d'invitation (code ou lien complet accepté). ⚠️ Discord fournit parfois aux bots un compteur en retard : en cas de doute, la valeur de Paramètres du serveur → Invitations fait foi.

### /membre
Fiche d'un membre : compte et ID, date d'arrivée sur le serveur (avec ancienneté), date de création du compte Discord, liste complète des rôles, et statut « règles non acceptées » le cas échéant. Le membre se cherche par @ ou par pseudo affiché dans le sélecteur.

**Attribution des rôles Team par invitation** : elle ne passe plus par NEObot. Attacher directement le rôle au lien d'invitation lors de sa création dans Discord (fonction native). NEObot mesure ensuite via `/compter-role` et `/compter-invitation`.

### /recharger
Recharge questions et configuration depuis le Google Sheet. À exécuter après **chaque** modification du Sheet. Affiche la liste des questions chargées.

### /export
Envoie toutes les réponses en CSV (séparateur `;`, encodage compatible Excel). Réponse éphémère (visible uniquement par l'admin).

## Comportements automatiques

| Événement | Action |
|---|---|
| Arrivée d'un membre | Identification du lien d'invitation utilisé → ligne dans l'onglet **Arrivées**. Si le serveur exige d'accepter les règles (mode Communauté), l'accueil attend l'acceptation ; ensuite : rôle `ROLE_ARRIVEE` (Curieux) + message public facultatif pointant vers le bouton 🌸 (`SALON_FALLBACK`). Aucun MP. Le rôle Team vient du lien d'invitation natif Discord |
| MP fermés à l'arrivée | Message d'orientation dans `SALON_FALLBACK` (si configuré) |
| Fin de questionnaire | Rôles des réponses + `ROLE_FINAL`, retrait `ROLE_ARRIVEE`, enregistrement Sheet, résumé dans `SALON_LOGS` (si configuré). Le message de fin liste les salons de l'onglet **Découverte** (Salon / Description) auxquels le membre a réellement accès, avec liens cliquables |
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

## TEST 7 — Menu des intérêts : bascule

Préconditions : onglet Intérêts rempli, `/recharger` effectué, rôles créés, menu publié via `/installer-menu-interets`, salon thématique visible uniquement par son rôle.

Action : cliquer un bouton (ex. Mangas), vérifier l'apparition du salon ; recliquer le même bouton.

Résultat attendu : message éphémère « ✅ Accès Mangas activé ! » puis salon visible ; au second clic « ➖ Accès Mangas désactivé. » et salon masqué. Aucune erreur dans les logs Render.

## TEST 8 — Menu des intérêts : rôle manquant

Préconditions : ajouter dans l'onglet Intérêts une ligne vers un rôle inexistant, `/recharger`.

Action : exécuter `/installer-menu-interets` dans un salon de test, cliquer le bouton concerné.

Résultat attendu : la commande signale le rôle manquant ; le clic répond « ❌ Le rôle … n'existe pas » sans plantage. Nettoyer : supprimer la ligne, `/recharger`, supprimer le message de test.

## TEST 9 — Menu des intérêts : persistance

Action : sur Render, Manual Deploy → Deploy latest commit ; après redémarrage, cliquer un bouton du menu publié AVANT le redéploiement.

Résultat attendu : le bouton fonctionne toujours (bascule normale).

## TEST 10 — Annonce : publication et bascule

Préconditions : bot en ligne ; salon de test.

Action : `/annonce` avec des valeurs de test (titre « TEST — à supprimer », places 20, un vrai lien) ; cliquer ✋ Ça m'intéresse ; vérifier l'onglet Annonces du Sheet ; recliquer.

Résultat attendu : embed complet publié ; premier clic → « ✅ C'est noté… », compteur passe à (1), ligne ajoutée dans l'onglet Annonces (créé automatiquement au premier clic) ; second clic → « ➖ C'est retiré… », compteur à (0), ligne supprimée. Nettoyer : supprimer le message de test.

## TEST 11 — Annonce : persistance et second compte

Action : publier une annonce de test ; faire cliquer un second compte (ou un ami) ; sur Render, Manual Deploy → Deploy latest commit ; après redémarrage, cliquer avec le premier compte.

Résultat attendu : le compteur cumule correctement les deux membres ; après redéploiement, le bouton fonctionne toujours et le compteur reste juste (les données sont dans le Sheet, pas en mémoire).

## TEST 12 — Synchro rôles : aperçu et création

Préconditions : onglet Rôles rempli avec au moins un rôle inexistant sur le serveur (ex. `test-synchro`, couleur `sakura`, permissions `aucune`).

Action : `/synchro-roles` ; lire l'aperçu SANS confirmer ; vérifier qu'il liste bien la création attendue et les orphelins ; cliquer ❌ Annuler ; relancer ; cliquer ✅ Confirmer.

Résultat attendu : l'annulation ne change rien ; après confirmation, le rôle `test-synchro` existe avec la bonne couleur ; résumé éphémère + trace dans SALON_LOGS. Nettoyer : supprimer le rôle de test à la main et sa ligne du Sheet.

## TEST 13 — Synchro rôles : garde-fous

Action : dans le Sheet, mettre `administrateur` dans les permissions d'un rôle, et une couleur invalide (`bleuu`) sur un autre ; `/synchro-roles`.

Résultat attendu : l'aperçu affiche les avertissements (« refusé », « couleur inconnue ») ; les permissions du rôle fautif ne sont PAS modifiées même après confirmation ; aucun rôle n'est jamais supprimé. Remettre le Sheet en état.

## TEST 14 — Compteurs et fiche membre

Action : `/compter-role` avec le rôle Visiteur ; `/compter-invitation` avec un code actif puis un code bidon ; `/membre` en cherchant un membre par pseudo affiché puis par @.

Résultat attendu : compte correct (bots exclus) ; utilisations affichées pour le code actif, message d'erreur listant les invitations actives pour le code bidon ; fiche complète (date d'arrivée, ancienneté, rôles triés du plus haut au plus bas).

## TEST 15 — Rôle Team par lien natif

Préconditions : un lien d'invitation créé dans Discord avec un rôle Team attaché (fonction native).

Action : faire rejoindre un compte de test via ce lien.

Résultat attendu : le rôle Team est attribué par Discord ; l'accueil NEObot (Curieux + questionnaire) se déroule normalement ; `/membre` sur ce compte montre bien le rôle Team ; une ligne apparaît dans l'onglet **Arrivées** avec le bon code et son étiquette (ou « non référencée » si le code n'est pas dans l'onglet Invitations).

## TEST 16 — Synchro salons : aperçu, application, sécurité

Préconditions : onglet Zones rempli ; `SALONS_EXCEPTIONS` renseigné dans Config ; `/recharger`.

Action : `/synchro-salons` ; lire l'aperçu SANS confirmer (vérifier catégories, exceptions intactes, avertissements) ; ❌ Annuler ; relancer ; ✅ Confirmer ; puis vérifier avec un compte sans rôle qu'il ne voit que la Zone 0, et avec un compte Visiteur qu'il peut écrire dans #général mais pas voir la Zone 7.

Résultat attendu : annulation sans effet ; après confirmation, la grille est appliquée, les salons d'exception (🔒, présentations…) gardent leurs réglages propres ; trace dans SALON_LOGS.

## TEST 17 — Questionnaire éphémère en salon

Action : avec un compte de test, cliquer 🌸 Commencer dans #bienvenue ; répondre aux questions (elles apparaissent sur place, « Toi seul peux voir ») ; vérifier depuis un autre compte que rien n'est visible dans le salon ; à la fin, vérifier rôles (Visiteur, retrait Curieux), ligne dans Réponses, résumé dans SALON_LOGS. Tester aussi /questionnaire sur le serveur (même flux) et le double-clic sur le bouton pendant un questionnaire en cours (message « déjà en cours »).

Résultat attendu : questionnaire complet sans MP, salon propre pour les autres, finalisation identique au flux MP.

## TEST 18 — Non-régression générale après redéploiement

Action : sur Render, Manual Deploy → Deploy latest commit ; attendre la fin ; cliquer le bouton 🌸 Commencer d'un message publié AVANT le redéploiement.

Résultat attendu : logs `🤖 Connecté...` et `✅ ... questions chargées` ; le bouton répond toujours (persistance) ; `/questionnaire` fonctionne.
