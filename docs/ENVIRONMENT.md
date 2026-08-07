# Variables d'environnement et configuration

*Dernière mise à jour : LOT 1 (état v2).*

## 1. Variables d'environnement (secrets)

Définies sur **Render** : service `bot-nippon-explorer` → onglet **Environment**. Jamais dans le code, jamais sur GitHub, jamais dans une conversation.

| Variable | Contenu | Où l'obtenir |
|---|---|---|
| `DISCORD_TOKEN` | Jeton secret du bot | Portail développeur Discord → application → Bot → Reset Token |
| `SHEET_ID` | Identifiant du Google Sheet | Dans l'URL du Sheet, entre `/d/` et `/edit` |
| `GOOGLE_CREDENTIALS_JSON` | Contenu intégral du fichier JSON du compte de service | Google Cloud Console → compte de service → Clés |

Équivalent `.env.example` (pour référence — ce projet n'utilise pas de fichier `.env`, Render en tient lieu) :

```env
DISCORD_TOKEN=
SHEET_ID=
GOOGLE_CREDENTIALS_JSON=
```

En cas de fuite d'un secret : régénérer immédiatement le token (Discord) ou la clé (Google Cloud), mettre à jour la variable sur Render, redéployer.

## 2. Configuration applicative (onglet « Config » du Google Sheet)

Non secrète, modifiable à tout moment. Appliquer avec `/recharger`. Toutes les clés sont **facultatives** : une valeur vide désactive la fonction.

| Clé | Valeur attendue | Effet |
|---|---|---|
| `ROLE_ARRIVEE` | Nom de rôle (ex. `Curieux`) | Donné automatiquement à chaque arrivée |
| `ROLE_FINAL` | Nom de rôle (ex. `Visiteur`) | Donné à la fin du questionnaire ; `ROLE_ARRIVEE` est alors retiré |
| `GUIDE_QUESTION` | Texte exact d'une question | Question surveillée pour l'orientation débutants |
| `GUIDE_REPONSES` | Réponses déclencheuses, séparées par `;` | Si choisie(s), le message de fin pointe vers `SALON_GUIDE` |
| `SALON_GUIDE` | ID de salon | Salon guide (#débuter-sur-discord) |
| `SALON_LOGS` | ID de salon | Résumé de chaque questionnaire terminé |
| `SALON_FALLBACK` | ID de salon | Message public de bienvenue à chaque arrivée, mentionnant le nouveau et pointant vers le bouton 🌸 (vide = désactivé) |
| `ACCUEIL_TITRE` | Texte | Titre du message d'accueil publié par /installer-bouton (vide = texte par défaut) |
| `ACCUEIL_TEXTE` | Texte (sauts de ligne acceptés) | Corps du message d'accueil (vide = texte par défaut). Après modification : /recharger puis republier via /installer-bouton |

Obtenir un ID : Paramètres Discord → Avancés → Mode développeur, puis clic droit sur le salon → Copier l'identifiant.

## 3. Réglages côté portail développeur Discord

| Réglage | Valeur requise |
|---|---|
| Privileged Gateway Intents | **SERVER MEMBERS INTENT activé** (sans lui : pas de détection des arrivées, pas de /synchro-veterans) |
| Permissions du rôle NEObot | **Toutes les permissions SAUF Administrateur.** Règle Discord découverte au LOT 4 : pour modifier un rôle, le bot doit posséder toutes les permissions que ce rôle détient — même celles qui ne changent pas. Un jeu minimal provoque des échecs « silencieux » de /synchro-roles |
| Position du rôle NEObot | Au-dessus de tous les rôles qu'il attribue, retire ou modifie |
