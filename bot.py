# -*- coding: utf-8 -*-
"""
NEObot v2.4 — Bot d'accueil de Nippon Explorer
--------------------------------------------
Correctif v2.4.1 (LOT 5) — compatibilité mode Communauté :
  • L'accueil (rôles + questionnaire) attend désormais que le membre ait
    accepté les règles du serveur (état « en attente » de Discord).
  • La détection d'invitation réessaie après 2,5 s si le compteur Discord
    est en retard sur l'événement d'arrivée.

Nouveauté v2.4 (LOT 5) :
  • Suivi des invitations par influenceur : onglet « Invitations » du Sheet
    (Code / Étiquette / Rôle), détection automatique de l'invitation utilisée
    à chaque arrivée, attribution du rôle Team correspondant, historique dans
    l'onglet « Arrivées », tableau de bord /invitations.

Nouveauté v2.3 (LOT 4) :
  • Gestion des rôles pilotée par le Google Sheet : onglet « Rôles »
    (Nom / Couleur / Séparé / Mentionnable / Permissions en mots-clés
    français), commande admin /synchro-roles avec APERÇU obligatoire puis
    bouton de confirmation. Le bot ne supprime jamais de rôle et refuse
    le mot-clé « administrateur ».

Nouveauté v2.2 (LOT 3) :
  • Annonces de créneaux de voyage : commande admin /annonce (titre, dates,
    prix, places, lien) avec bouton persistant « ✋ Ça m'intéresse » à bascule,
    compteur affiché sur l'annonce, intéressés enregistrés dans l'onglet
    « Annonces » du Google Sheet.

Nouveauté v2.1 (LOT 2) :
  • Menu des centres d'intérêt : boutons à bascule qui donnent/retirent des
    rôles d'accès aux salons thématiques. Configuration dans l'onglet
    « Intérêts » du Google Sheet ; publication via /installer-menu-interets.

Nouveautés de la v2 (« socle accueil ») :
  • Rôle automatique à l'arrivée (Curieux) — clé Config : ROLE_ARRIVEE
  • Le questionnaire retire ce rôle et donne le rôle final (Visiteur) — clé : ROLE_FINAL
  • Bouton permanent « 🌸 Commencer » dans le salon d'accueil — commande : /installer-bouton
  • Nouvelle question « aisance Discord » : les débutants sont orientés vers
    le salon guide — clés Config : GUIDE_QUESTION, GUIDE_REPONSES, SALON_GUIDE
  • /synchro-veterans : donne le rôle « Vétéran » à tous ceux qui ont un rôle « Vétéran lvl … »

Commandes disponibles sur Discord :
  /questionnaire       -> (re)faire le questionnaire
  /installer-bouton    -> publier le message d'accueil avec le bouton Commencer (admin)
  /installer-menu-interets -> publier le menu des centres d'intérêt (admin)
  /annonce             -> publier une annonce de créneau de voyage (admin)
  /synchro-roles       -> synchroniser les rôles du serveur avec l'onglet Rôles (admin)
  /invitations         -> tableau de bord des invitations par influenceur (admin)
  /synchro-veterans    -> donner le rôle Vétéran aux détenteurs d'un rôle « Vétéran lvl » (admin)
  /recharger           -> recharger les questions depuis Google Sheets (admin)
  /export              -> recevoir toutes les réponses en fichier CSV (admin)

Variables d'environnement (inchangées) :
  DISCORD_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_JSON
"""

import asyncio
import csv
import io
import json
import os
import threading
import http.server
import unicodedata
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# 1. Petit serveur web : nécessaire pour l'hébergement gratuit
# ============================================================

def demarrer_serveur_web():
    port = int(os.environ.get("PORT", 10000))

    class Poignee(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("NEObot est en ligne.".encode("utf-8"))

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    serveur = http.server.ThreadingHTTPServer(("0.0.0.0", port), Poignee)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()


# ============================================================
# 2. Connexion Google Sheets
# ============================================================

PORTEES_GOOGLE = ["https://www.googleapis.com/auth/spreadsheets"]

QUESTIONS = []
CONFIG = {}
INTERETS = []  # boutons du menu des centres d'intérêt : {"etiquette", "role", "emoji"}
ROLES_CONFIG = []  # onglet « Rôles » : description des rôles à synchroniser
INVITATIONS = {}   # onglet « Invitations » : code -> {"etiquette", "role"}
CACHE_INVITATIONS = {}  # serveur_id -> {code: nombre d'utilisations} (perdu au redémarrage : resynchronisé)


def ouvrir_classeur():
    infos = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(infos, scopes=PORTEES_GOOGLE)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ["SHEET_ID"])


def normaliser_code_invitation(texte):
    """Accepte un code brut (abc123) ou un lien complet (https://discord.gg/abc123)."""
    brut = str(texte).strip().rstrip("/")
    if not brut:
        return ""
    return brut.split("/")[-1]


def charger_donnees():
    """Lit les onglets Questions / Config et prépare l'onglet Réponses."""
    global QUESTIONS, CONFIG, INTERETS, ROLES_CONFIG, INVITATIONS
    classeur = ouvrir_classeur()

    lignes = classeur.worksheet("Questions").get_all_records()
    questions = []
    for ligne in lignes:
        texte = str(ligne.get("Question", "")).strip()
        options = [o.strip() for o in str(ligne.get("Options", "")).split(";") if o.strip()]
        if not texte or not options:
            continue
        multiple = str(ligne.get("Multiple", "")).strip().lower() in ("oui", "yes", "x", "1", "true", "vrai")
        roles = {}
        brut = str(ligne.get("Rôles", "") or ligne.get("Roles", "")).strip()
        if brut:
            for paire in brut.split(";"):
                if "=" in paire:
                    option, role = paire.split("=", 1)
                    roles[option.strip()] = role.strip()
        questions.append({
            "texte": texte[:256],
            "options": options[:25],
            "multiple": multiple,
            "roles": roles,
        })

    config = {}
    try:
        for ligne in classeur.worksheet("Config").get_all_values():
            if len(ligne) >= 2 and ligne[0].strip():
                config[ligne[0].strip().upper()] = ligne[1].strip()
    except gspread.WorksheetNotFound:
        pass

    # --- Onglet "Intérêts" (facultatif) : boutons d'accès aux salons ---
    interets = []
    try:
        for ligne in classeur.worksheet("Intérêts").get_all_records():
            etiquette = str(ligne.get("Étiquette", "") or ligne.get("Etiquette", "")).strip()
            role = str(ligne.get("Rôle", "") or ligne.get("Role", "")).strip()
            emoji = str(ligne.get("Emoji", "")).strip()
            if etiquette and role:
                interets.append({"etiquette": etiquette[:80], "role": role, "emoji": emoji})
    except gspread.WorksheetNotFound:
        pass

    try:
        feuille_r = classeur.worksheet("Réponses")
    except gspread.WorksheetNotFound:
        feuille_r = classeur.add_worksheet(title="Réponses", rows=2000, cols=30)
    entetes = ["Date", "Pseudo", "ID Discord"] + [q["texte"] for q in questions]
    feuille_r.update(range_name="A1", values=[entetes])

    # --- Onglet "Rôles" (facultatif) : rôles à synchroniser ---
    roles_config = []
    try:
        for ligne in classeur.worksheet("Rôles").get_all_records():
            nom = str(ligne.get("Nom", "")).strip()
            if not nom:
                continue
            roles_config.append({
                "nom": nom,
                "couleur": str(ligne.get("Couleur", "")),
                "separe": str(ligne.get("Séparé", "") or ligne.get("Separe", "")),
                "mentionnable": str(ligne.get("Mentionnable", "")),
                "permissions": str(ligne.get("Permissions", "")),
            })
    except gspread.WorksheetNotFound:
        pass

    # --- Onglet "Invitations" (facultatif) : suivi par influenceur ---
    invitations = {}
    try:
        for ligne in classeur.worksheet("Invitations").get_all_records():
            code = normaliser_code_invitation(str(ligne.get("Code", "")))
            etiquette = str(ligne.get("Étiquette", "") or ligne.get("Etiquette", "")).strip()
            role = str(ligne.get("Rôle", "") or ligne.get("Role", "")).strip()
            if code and role:
                invitations[code] = {"etiquette": etiquette or code, "role": role}
    except gspread.WorksheetNotFound:
        pass

    QUESTIONS = questions
    CONFIG = config
    INTERETS = interets
    ROLES_CONFIG = roles_config
    INVITATIONS = invitations


def enregistrer_reponses(utilisateur, reponses):
    classeur = ouvrir_classeur()
    feuille = classeur.worksheet("Réponses")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    ligne = [date, str(utilisateur), str(utilisateur.id)] + [", ".join(r) for r in reponses]
    feuille.append_row(ligne, value_input_option="USER_ENTERED")


def lire_toutes_les_reponses():
    classeur = ouvrir_classeur()
    return classeur.worksheet("Réponses").get_all_values()


def enregistrer_arrivee(membre, code, etiquette, role_attribue):
    """Ajoute une ligne dans l'onglet Arrivées (créé au besoin)."""
    classeur = ouvrir_classeur()
    try:
        feuille = classeur.worksheet("Arrivées")
    except gspread.WorksheetNotFound:
        feuille = classeur.add_worksheet(title="Arrivées", rows=2000, cols=8)
        feuille.update(
            range_name="A1",
            values=[["Date", "Pseudo", "ID Discord", "Code invitation", "Influenceur", "Rôle attribué"]],
        )
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    feuille.append_row(
        [date, str(membre), str(membre.id), code, etiquette, role_attribue],
        value_input_option="USER_ENTERED",
    )


def basculer_interet_annonce(annonce_id, titre, utilisateur):
    """Inscrit ou désinscrit un intéressé dans l'onglet Annonces.
    Retourne (ajouté: bool, nouveau_compte: int)."""
    classeur = ouvrir_classeur()
    try:
        feuille = classeur.worksheet("Annonces")
    except gspread.WorksheetNotFound:
        feuille = classeur.add_worksheet(title="Annonces", rows=2000, cols=6)
        feuille.update(
            range_name="A1",
            values=[["ID annonce", "Titre", "Pseudo", "ID Discord", "Date"]],
        )
    valeurs = feuille.get_all_values()
    compte_actuel = sum(
        1 for ligne in valeurs[1:] if len(ligne) >= 1 and ligne[0] == str(annonce_id)
    )
    for indice, ligne in enumerate(valeurs[1:], start=2):
        if (
            len(ligne) >= 4
            and ligne[0] == str(annonce_id)
            and ligne[3] == str(utilisateur.id)
        ):
            feuille.delete_rows(indice)
            return False, max(compte_actuel - 1, 0)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    feuille.append_row(
        [str(annonce_id), titre, str(utilisateur), str(utilisateur.id), date],
        value_input_option="USER_ENTERED",
    )
    return True, compte_actuel + 1


# ============================================================
# 3. Outils rôles
# ============================================================

def trouver_role(serveur: discord.Guild, nom: str):
    nom = (nom or "").strip()
    if not nom:
        return None
    return discord.utils.find(lambda r: r.name.lower() == nom.lower(), serveur.roles)


async def obtenir_membre(serveur: discord.Guild, utilisateur):
    membre = serveur.get_member(utilisateur.id)
    if membre is None:
        try:
            membre = await serveur.fetch_member(utilisateur.id)
        except discord.NotFound:
            return None
    return membre


# ============================================================
# 4. Le questionnaire (menus cliquables en message privé)
# ============================================================

COULEUR = 0xD90F2C
DUREE_MAX_PAR_QUESTION = 900  # 15 minutes


class SelecteurQuestion(discord.ui.Select):
    def __init__(self, question, proprietaire_id):
        self.proprietaire_id = proprietaire_id
        options = [discord.SelectOption(label=o[:100]) for o in question["options"]]
        maxi = len(options) if question["multiple"] else 1
        super().__init__(
            placeholder="Clique ici pour répondre…",
            min_values=1,
            max_values=maxi,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.proprietaire_id:
            await interaction.response.send_message("Ce questionnaire ne t'est pas destiné.", ephemeral=True)
            return
        self.view.valeurs = list(self.values)
        await interaction.response.defer()
        self.view.stop()


class VueQuestion(discord.ui.View):
    def __init__(self, question, proprietaire_id):
        super().__init__(timeout=DUREE_MAX_PAR_QUESTION)
        self.valeurs = None
        self.add_item(SelecteurQuestion(question, proprietaire_id))


sessions_en_cours = set()


def doit_voir_le_guide(reponses):
    """Vrai si la réponse à la question « aisance Discord » est un déclencheur (Config)."""
    q_cible = CONFIG.get("GUIDE_QUESTION", "").strip().lower()
    declencheurs = [d.strip().lower() for d in CONFIG.get("GUIDE_REPONSES", "").split(";") if d.strip()]
    if not q_cible or not declencheurs:
        return False
    for question, valeurs in zip(QUESTIONS, reponses):
        if question["texte"].strip().lower() == q_cible:
            return any(v.lower() in declencheurs for v in valeurs)
    return False


async def derouler_questionnaire(utilisateur: discord.User, serveur: discord.Guild):
    if utilisateur.id in sessions_en_cours:
        return
    if not QUESTIONS:
        return
    sessions_en_cours.add(utilisateur.id)
    try:
        mp = await utilisateur.create_dm()

        bienvenue = discord.Embed(
            title=f"🌸 Bienvenue sur {serveur.name} !",
            description=(
                "Pour t'accueillir au mieux, réponds à ces quelques questions.\n"
                "Il suffit de **cliquer** dans les menus ci-dessous. C'est parti !"
            ),
            color=COULEUR,
        )
        await mp.send(embed=bienvenue)

        reponses = []
        total = len(QUESTIONS)
        for numero, question in enumerate(QUESTIONS, start=1):
            embed = discord.Embed(
                title=f"Question {numero}/{total}",
                description=f"**{question['texte']}**",
                color=COULEUR,
            )
            if question["multiple"]:
                embed.set_footer(text="Plusieurs réponses possibles ✔")
            vue = VueQuestion(question, utilisateur.id)
            message = await mp.send(embed=embed, view=vue)
            await vue.wait()

            if vue.valeurs is None:
                await mp.send(
                    "⏳ Le temps est écoulé. Reclique sur le bouton **Commencer** du salon d'accueil, "
                    "ou tape **/questionnaire** sur le serveur pour recommencer quand tu veux !"
                )
                return

            reponses.append(vue.valeurs)
            embed.add_field(name="Ta réponse ✅", value=", ".join(vue.valeurs), inline=False)
            await message.edit(embed=embed, view=None)

        roles_donnes, roles_introuvables = await attribuer_roles(utilisateur, serveur, reponses)

        try:
            await asyncio.to_thread(enregistrer_reponses, utilisateur, reponses)
        except Exception as erreur:
            print(f"[ERREUR Google Sheets] {erreur}")

        merci = discord.Embed(
            title="🎌 Merci, et bienvenue chez Nippon Explorer !",
            description="Ton profil est enregistré : le serveur t'est maintenant ouvert. Bonne exploration !",
            color=COULEUR,
        )
        if roles_donnes:
            merci.add_field(name="Rôles attribués", value=", ".join(roles_donnes), inline=False)
        salon_guide = CONFIG.get("SALON_GUIDE", "").strip()
        if doit_voir_le_guide(reponses) and salon_guide.isdigit():
            merci.add_field(
                name="👋 On t'accompagne !",
                value=(
                    f"Tu débutes sur Discord ? Pas de panique : passe d'abord par <#{salon_guide}>, "
                    "on t'y explique le fonctionnement du serveur en quelques minutes."
                ),
                inline=False,
            )
        await mp.send(embed=merci)

        await journaliser(serveur, utilisateur, reponses, roles_donnes, roles_introuvables)
    finally:
        sessions_en_cours.discard(utilisateur.id)


async def attribuer_roles(utilisateur, serveur, reponses):
    """Donne les rôles liés aux réponses + ROLE_FINAL, puis retire ROLE_ARRIVEE."""
    noms_voulus = []
    for question, valeurs in zip(QUESTIONS, reponses):
        for valeur in valeurs:
            nom_role = question["roles"].get(valeur)
            if nom_role:
                noms_voulus.append(nom_role)
    role_final = CONFIG.get("ROLE_FINAL", "").strip()
    if role_final:
        noms_voulus.append(role_final)

    donnes, introuvables = [], []
    membre = await obtenir_membre(serveur, utilisateur)
    if membre is None:
        return donnes, noms_voulus

    for nom in noms_voulus:
        role = trouver_role(serveur, nom)
        if role is None:
            introuvables.append(nom)
            continue
        try:
            await membre.add_roles(role, reason="Questionnaire d'accueil")
            donnes.append(role.name)
        except discord.Forbidden:
            introuvables.append(f"{nom} (le rôle du bot est trop bas dans la liste)")

    # Le membre n'est plus un simple « Curieux »
    role_arrivee = trouver_role(serveur, CONFIG.get("ROLE_ARRIVEE", ""))
    if role_arrivee and role_arrivee in membre.roles:
        try:
            await membre.remove_roles(role_arrivee, reason="Questionnaire d'accueil terminé")
        except discord.Forbidden:
            introuvables.append(f"{role_arrivee.name} (impossible à retirer : rôle du bot trop bas)")

    return donnes, introuvables


async def journaliser(serveur, utilisateur, reponses, roles_donnes, roles_introuvables):
    salon_id = CONFIG.get("SALON_LOGS", "").strip()
    if not salon_id.isdigit():
        return
    salon = serveur.get_channel(int(salon_id))
    if salon is None:
        return
    resume = discord.Embed(title=f"📋 Questionnaire terminé : {utilisateur}", color=COULEUR)
    for question, valeurs in zip(QUESTIONS, reponses):
        resume.add_field(name=question["texte"][:250], value=", ".join(valeurs)[:1000] or "—", inline=False)
    if roles_donnes:
        resume.add_field(name="Rôles attribués", value=", ".join(roles_donnes), inline=False)
    if roles_introuvables:
        resume.add_field(
            name="⚠️ Rôles introuvables (à créer ou corriger)",
            value=", ".join(roles_introuvables),
            inline=False,
        )
    try:
        await salon.send(embed=resume)
    except discord.Forbidden:
        pass


# ============================================================
# 5. Bouton permanent « Commencer » (salon d'accueil)
# ============================================================

class VueBoutonCommencer(discord.ui.View):
    """Vue persistante : le bouton survit aux redémarrages du bot."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🌸 Commencer",
        style=discord.ButtonStyle.success,
        custom_id="neobot:commencer",
    )
    async def commencer(self, interaction: discord.Interaction, bouton: discord.ui.Button):
        serveur = interaction.guild or (bot.guilds[0] if bot.guilds else None)
        if serveur is None:
            await interaction.response.send_message("Erreur : serveur introuvable.", ephemeral=True)
            return
        await interaction.response.send_message("📬 Regarde tes messages privés !", ephemeral=True)
        try:
            await derouler_questionnaire(interaction.user, serveur)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'arrive pas à t'écrire en privé. Active tes messages privés "
                "(Paramètres de confidentialité du serveur > Messages privés), puis reclique sur le bouton.",
                ephemeral=True,
            )


# ============================================================
# 5bis. Menu des centres d'intérêt (boutons à bascule persistants)
# ============================================================

class BoutonInteret(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"neobot:interet:(?P<nom>.+)",
):
    """Bouton persistant : un clic donne le rôle d'accès, un second le retire."""

    def __init__(self, etiquette: str, nom_role: str, emoji: str = ""):
        self.nom_role = nom_role
        super().__init__(
            discord.ui.Button(
                label=etiquette[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"neobot:interet:{nom_role}"[:100],
                emoji=emoji or None,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        # Reconstruit le bouton après un redémarrage du bot
        return cls(item.label or match["nom"], match["nom"])

    async def callback(self, interaction: discord.Interaction):
        serveur = interaction.guild
        if serveur is None:
            await interaction.response.send_message("Ce bouton s'utilise sur le serveur.", ephemeral=True)
            return
        role = trouver_role(serveur, self.nom_role)
        if role is None:
            await interaction.response.send_message(
                f"❌ Le rôle « {self.nom_role} » n'existe pas (ou plus). Signale-le à un administrateur.",
                ephemeral=True,
            )
            return
        membre = interaction.user
        try:
            if role in membre.roles:
                await membre.remove_roles(role, reason="Menu des centres d'intérêt")
                await interaction.response.send_message(f"➖ Accès **{role.name}** désactivé.", ephemeral=True)
            else:
                await membre.add_roles(role, reason="Menu des centres d'intérêt")
                await interaction.response.send_message(f"✅ Accès **{role.name}** activé !", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Je n'ai pas le droit de gérer ce rôle (rôle du bot trop bas). Signale-le à un administrateur.",
                ephemeral=True,
            )


def construire_menus_interets():
    """Répartit les boutons en messages de 25 maximum (limite Discord)."""
    vues = []
    for depart in range(0, len(INTERETS), 25):
        vue = discord.ui.View(timeout=None)
        for interet in INTERETS[depart:depart + 25]:
            try:
                vue.add_item(BoutonInteret(interet["etiquette"], interet["role"], interet["emoji"]))
            except Exception as erreur:
                print(f"[Menu intérêts] Bouton ignoré ({interet['etiquette']}) : {erreur}")
        vues.append(vue)
    return vues


# ============================================================
# 5ter. Annonces de voyage (bouton « Ça m'intéresse » persistant)
# ============================================================

class BoutonAnnonce(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"neobot:annonce:(?P<ident>\d+)",
):
    """Bouton persistant : inscrit/désinscrit l'intéressé et met à jour le compteur."""

    def __init__(self, ident, compte: int = 0):
        self.ident = int(ident)
        super().__init__(
            discord.ui.Button(
                label=f"✋ Ça m'intéresse ({compte})",
                style=discord.ButtonStyle.primary,
                custom_id=f"neobot:annonce:{ident}",
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["ident"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        titre = ""
        if interaction.message and interaction.message.embeds:
            titre = interaction.message.embeds[0].title or ""
        try:
            ajoute, compte = await asyncio.to_thread(
                basculer_interet_annonce, self.ident, titre, interaction.user
            )
        except Exception as erreur:
            print(f"[ERREUR Annonces] {erreur}")
            await interaction.followup.send(
                "❌ Petit souci technique, réessaie dans une minute.", ephemeral=True
            )
            return
        vue = discord.ui.View(timeout=None)
        vue.add_item(BoutonAnnonce(self.ident, compte))
        try:
            await interaction.message.edit(view=vue)
        except discord.HTTPException:
            pass
        if ajoute:
            await interaction.followup.send(
                "✅ C'est noté, tu es compté(e) parmi les intéressés ! "
                "Clique à nouveau si tu changes d'avis.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "➖ C'est retiré. Tu peux te réinscrire à tout moment.", ephemeral=True
            )


# ============================================================
# 5quater. Synchronisation des rôles depuis l'onglet « Rôles »
# ============================================================

# Mots-clés français -> permissions Discord. Volontairement SANS
# « administrateur », « gerer-serveur » ni « gerer-webhooks » : ces pouvoirs
# se donnent à la main, jamais depuis un tableur.
PERMS_FR = {
    "voir-salons": "view_channel",
    "envoyer-messages": "send_messages",
    "historique": "read_message_history",
    "reactions": "add_reactions",
    "liens": "embed_links",
    "fichiers": "attach_files",
    "emojis-externes": "use_external_emojis",
    "stickers-externes": "use_external_stickers",
    "creer-fils": "create_public_threads",
    "ecrire-dans-fils": "send_messages_in_threads",
    "commandes-bots": "use_application_commands",
    "changer-pseudo": "change_nickname",
    "inviter": "create_instant_invite",
    "connecter": "connect",
    "parler": "speak",
    "video": "stream",
    "mentionner-tout-le-monde": "mention_everyone",
    "gerer-messages": "manage_messages",
    "gerer-fils": "manage_threads",
    "gerer-pseudos": "manage_nicknames",
    "gerer-salons": "manage_channels",
    "gerer-roles": "manage_roles",
    "gerer-evenements": "manage_events",
    "expulser": "kick_members",
    "bannir": "ban_members",
    "exclure-temporairement": "moderate_members",
    "voir-journal-audit": "view_audit_log",
    "couper-micro": "mute_members",
    "rendre-sourd": "deafen_members",
    "deplacer-membres": "move_members",
}

PERMS_REFUSEES = {"administrateur", "gerer-serveur", "gerer-webhooks"}

COULEURS_FR = {
    "rouge": 0xD32F2F, "bleu": 0x1E88E5, "vert": 0x43A047, "jaune": 0xFDD835,
    "orange": 0xFB8C00, "violet": 0x8E24AA, "rose": 0xEC407A, "sakura": 0xFFB7C5,
    "or": 0xC9A227, "argent": 0xB0BEC5, "turquoise": 0x00ACC1, "corail": 0xFF7043,
    "marron": 0x795548, "gris": 0x9E9E9E, "noir": 0x111111, "blanc": 0xFFFFFF,
}


def normaliser_mot(texte):
    """minuscules, sans accents, sans espaces superflus."""
    texte = unicodedata.normalize("NFD", str(texte).strip().lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def parser_couleur(texte):
    brut = str(texte).strip()
    if not brut:
        return None, None
    cle = normaliser_mot(brut)
    if cle in COULEURS_FR:
        return discord.Colour(COULEURS_FR[cle]), None
    h = brut.lstrip("#")
    if len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h):
        return discord.Colour(int(h, 16)), None
    return None, f"couleur inconnue « {brut} »"


def parser_oui_non(texte):
    cle = normaliser_mot(texte)
    if not cle:
        return None
    if cle in ("oui", "yes", "1", "true", "vrai", "x"):
        return True
    if cle in ("non", "no", "0", "false", "faux"):
        return False
    return None


def parser_permissions(cellule):
    """Cellule vide -> None (ne pas toucher). « aucune » -> zéro permission.
    Retourne (Permissions ou None, liste de problèmes)."""
    brut = str(cellule).strip()
    if not brut:
        return None, []
    if normaliser_mot(brut) == "aucune":
        return discord.Permissions.none(), []
    problemes = []
    perms = discord.Permissions.none()
    for mot in brut.split(";"):
        cle = normaliser_mot(mot)
        if not cle:
            continue
        if cle in PERMS_REFUSEES:
            problemes.append(f"« {mot.strip()} » refusé (à donner à la main)")
            continue
        attribut = PERMS_FR.get(cle)
        if attribut is None:
            problemes.append(f"mot-clé inconnu « {mot.strip()} »")
            continue
        setattr(perms, attribut, True)
    return perms, problemes


def construire_plan_roles(serveur):
    """Compare l'onglet Rôles au serveur. Ne prévoit JAMAIS de suppression."""
    plan, avertissements, orphelins, hors_portee = [], [], [], []
    noms_sheet = set()
    limite = serveur.me.top_role
    for cfg in ROLES_CONFIG:
        nom = cfg["nom"]
        couleur, erreur_couleur = parser_couleur(cfg["couleur"])
        if erreur_couleur:
            avertissements.append(f"{nom} : {erreur_couleur} (couleur ignorée)")
        separe = parser_oui_non(cfg["separe"])
        mentionnable = parser_oui_non(cfg["mentionnable"])
        perms, problemes = parser_permissions(cfg["permissions"])
        if problemes:
            avertissements.append(f"{nom} : " + " ; ".join(problemes) + " → permissions non touchées")
            perms = None

        if normaliser_mot(nom) in ("everyone", "@everyone"):
            if perms is not None and serveur.default_role.permissions.value != perms.value:
                plan.append({"type": "everyone", "nom": "@everyone", "perms": perms})
            continue

        noms_sheet.add(nom.lower())
        role = trouver_role(serveur, nom)
        if role is None:
            plan.append({
                "type": "creer", "nom": nom, "couleur": couleur,
                "separe": bool(separe), "mentionnable": bool(mentionnable),
                "perms": perms if perms is not None else discord.Permissions.none(),
            })
            continue
        if role.managed:
            avertissements.append(f"{nom} : rôle géré par Discord, ignoré")
            continue
        if role >= limite:
            hors_portee.append(nom)
            continue
        params, changements = {}, []
        if couleur is not None and role.colour.value != couleur.value:
            params["colour"] = couleur
            changements.append("couleur")
        if separe is not None and role.hoist != separe:
            params["hoist"] = separe
            changements.append("affichage séparé")
        if mentionnable is not None and role.mentionable != mentionnable:
            params["mentionable"] = mentionnable
            changements.append("mentionnable")
        if perms is not None and role.permissions.value != perms.value:
            params["permissions"] = perms
            changements.append("permissions")
        if params:
            plan.append({
                "type": "modifier", "nom": role.name, "role": role,
                "params": params, "changements": changements,
            })

    for role in serveur.roles:
        if role.is_default() or role.managed:
            continue
        if role.name.lower() not in noms_sheet:
            orphelins.append(role.name)
    return plan, avertissements, orphelins, hors_portee


def resumer_liste(elements, maxi=950):
    texte = ", ".join(elements)
    return texte[:maxi] + ("…" if len(texte) > maxi else "")


class VueConfirmationRoles(discord.ui.View):
    """Aperçu -> confirmation explicite avant toute modification de rôle."""

    def __init__(self, plan, serveur, auteur_id):
        super().__init__(timeout=300)
        self.plan = plan
        self.serveur = serveur
        self.auteur_id = auteur_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.auteur_id:
            await interaction.response.send_message(
                "Seule la personne ayant lancé /synchro-roles peut confirmer.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ Confirmer et appliquer", style=discord.ButtonStyle.success)
    async def confirmer(self, interaction: discord.Interaction, bouton: discord.ui.Button):
        for enfant in self.children:
            enfant.disabled = True
        await interaction.response.edit_message(view=self)
        faits, echecs = [], []
        for action in self.plan:
            try:
                if action["type"] == "creer":
                    await self.serveur.create_role(
                        name=action["nom"],
                        colour=action["couleur"] or discord.Colour.default(),
                        hoist=action["separe"],
                        mentionable=action["mentionnable"],
                        permissions=action["perms"],
                        reason="Synchro rôles (Google Sheet)",
                    )
                    faits.append(f"➕ {action['nom']}")
                elif action["type"] == "modifier":
                    await action["role"].edit(**action["params"], reason="Synchro rôles (Google Sheet)")
                    faits.append(f"✏️ {action['nom']} ({', '.join(action['changements'])})")
                else:  # @everyone
                    await self.serveur.default_role.edit(
                        permissions=action["perms"], reason="Synchro rôles (Google Sheet)"
                    )
                    faits.append("✏️ @everyone (permissions)")
            except discord.Forbidden:
                echecs.append(action["nom"])
            except discord.HTTPException as erreur:
                echecs.append(f"{action['nom']} (erreur {getattr(erreur, 'status', '?')})")
        resume = f"🧩 Synchronisation terminée : {len(faits)} action(s) appliquée(s)."
        if faits:
            resume += "\n" + resumer_liste(faits, 1200)
        if echecs:
            resume += f"\n⚠️ Échecs : {resumer_liste(echecs, 400)}"
        await interaction.followup.send(resume[:1900], ephemeral=True)
        await journaliser_synchro_roles(self.serveur, interaction.user, faits, echecs)
        self.stop()

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def annuler(self, interaction: discord.Interaction, bouton: discord.ui.Button):
        for enfant in self.children:
            enfant.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Synchronisation annulée, rien n'a été modifié.", ephemeral=True)
        self.stop()


async def journaliser_synchro_roles(serveur, auteur, faits, echecs):
    salon_id = CONFIG.get("SALON_LOGS", "").strip()
    if not salon_id.isdigit():
        return
    salon = serveur.get_channel(int(salon_id))
    if salon is None:
        return
    audit = discord.Embed(title="🧩 Synchronisation des rôles", color=COULEUR)
    audit.add_field(name="Par", value=str(auteur), inline=False)
    audit.add_field(name="Actions", value=resumer_liste(faits) or "aucune", inline=False)
    if echecs:
        audit.add_field(name="Échecs", value=resumer_liste(echecs), inline=False)
    try:
        await salon.send(embed=audit)
    except discord.Forbidden:
        pass


# ============================================================
# 5quinquies. Suivi des invitations par influenceur
# ============================================================

async def synchroniser_cache_invitations(serveur):
    """Mémorise le compteur d'utilisations de chaque invitation du serveur."""
    try:
        invitations = await serveur.invites()
    except discord.Forbidden:
        print("⚠️ Permission « Gérer le serveur » requise pour lire les invitations.")
        return
    CACHE_INVITATIONS[serveur.id] = {inv.code: inv.uses or 0 for inv in invitations}


async def detecter_invitation(serveur):
    """Compare les compteurs avant/après une arrivée.
    Retourne le code utilisé, ou None si indéterminé (0 ou plusieurs candidats).
    Le compteur Discord pouvant être en retard de quelques instants sur
    l'événement d'arrivée, on réessaie une fois après 2,5 secondes."""
    avant = CACHE_INVITATIONS.get(serveur.id, {})
    apres = avant
    for tentative in (1, 2):
        try:
            actuelles = await serveur.invites()
        except discord.Forbidden:
            return None
        apres = {inv.code: inv.uses or 0 for inv in actuelles}
        candidats = [code for code, uses in apres.items() if uses > avant.get(code, 0)]
        # Une invitation à nombre d'usages limité disparaît quand elle s'épuise :
        candidats += [code for code in avant if code not in apres]
        if candidats:
            CACHE_INVITATIONS[serveur.id] = apres
            return candidats[0] if len(candidats) == 1 else None
        if tentative == 1:
            await asyncio.sleep(2.5)
    CACHE_INVITATIONS[serveur.id] = apres
    return None


# ============================================================
# 6. Le bot Discord et ses commandes
# ============================================================

intents = discord.Intents.default()
intents.members = True


class NEObot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.donnees_chargees = False

    async def setup_hook(self):
        self.add_view(VueBoutonCommencer())  # réactive le bouton après chaque redémarrage
        self.add_dynamic_items(BoutonInteret, BoutonAnnonce)  # réactive les boutons persistants
        await self.tree.sync()


bot = NEObot()


@bot.event
async def on_ready():
    if not bot.donnees_chargees:
        try:
            await asyncio.to_thread(charger_donnees)
            bot.donnees_chargees = True
            print(f"✅ {len(QUESTIONS)} questions chargées depuis Google Sheets.")
        except Exception as erreur:
            print(f"❌ Impossible de lire le Google Sheet : {erreur}")
        for serveur in bot.guilds:
            bot.tree.copy_global_to(guild=serveur)
            await bot.tree.sync(guild=serveur)
    # (Re)synchronise les compteurs d'invitations à chaque (re)connexion
    for serveur in bot.guilds:
        await synchroniser_cache_invitations(serveur)
    print(f"🤖 Connecté en tant que {bot.user}")


@bot.event
async def on_invite_create(invitation: discord.Invite):
    if invitation.guild:
        CACHE_INVITATIONS.setdefault(invitation.guild.id, {})[invitation.code] = invitation.uses or 0


@bot.event
async def on_invite_delete(invitation: discord.Invite):
    if invitation.guild:
        CACHE_INVITATIONS.get(invitation.guild.id, {}).pop(invitation.code, None)


EN_ATTENTE_REGLES = {}  # id membre -> rôle d'invitation à donner une fois les règles acceptées


async def accueillir_membre(membre: discord.Member, nom_role_invitation: str):
    """Étapes d'accueil : rôle d'invitation, rôle Curieux, questionnaire en MP.
    Appelé directement, ou après acceptation des règles (mode Communauté)."""
    # 1) Rôle lié à l'invitation utilisée
    if nom_role_invitation:
        role = trouver_role(membre.guild, nom_role_invitation)
        if role:
            try:
                await membre.add_roles(role, reason="Invitation suivie (onglet Invitations)")
            except discord.Forbidden:
                print(f"⚠️ Impossible de donner {role.name} (rôle du bot trop bas ?)")

    # 2) Rôle d'arrivée immédiat (Curieux) : accès lecture seule aux zones publiques
    role_arrivee = trouver_role(membre.guild, CONFIG.get("ROLE_ARRIVEE", ""))
    if role_arrivee:
        try:
            await membre.add_roles(role_arrivee, reason="Arrivée sur le serveur")
        except discord.Forbidden:
            print(f"⚠️ Impossible de donner {role_arrivee.name} (rôle du bot trop bas ?)")

    # 3) Questionnaire en MP
    try:
        await derouler_questionnaire(membre, membre.guild)
    except discord.Forbidden:
        salon_id = CONFIG.get("SALON_FALLBACK", "").strip()
        if salon_id.isdigit():
            salon = membre.guild.get_channel(int(salon_id))
            if salon:
                try:
                    await salon.send(
                        f"👋 Bienvenue {membre.mention} ! Je n'ai pas pu t'envoyer de message privé. "
                        "Active tes MP (Paramètres du serveur > Confidentialité) puis clique sur le bouton "
                        "**🌸 Commencer** du salon d'accueil."
                    )
                except discord.Forbidden:
                    pass


@bot.event
async def on_member_join(membre: discord.Member):
    if membre.bot:
        return

    # 0) Par quelle invitation ce membre arrive-t-il ?
    code = await detecter_invitation(membre.guild)
    infos_invitation = INVITATIONS.get(code) if code else None
    if infos_invitation:
        etiquette = infos_invitation["etiquette"]
        nom_role_invitation = infos_invitation["role"]
    elif code:
        etiquette = "invitation non référencée"
        nom_role_invitation = ""
    else:
        etiquette = "indéterminé"
        nom_role_invitation = ""
    try:
        await asyncio.to_thread(
            enregistrer_arrivee,
            membre,
            code or "indéterminé",
            etiquette,
            nom_role_invitation,
        )
    except Exception as erreur:
        print(f"[ERREUR Arrivées] {erreur}")

    # Mode Communauté : tant que le membre n'a pas accepté les règles, Discord
    # bloque rôles et MP. On mémorise et on reprend dans on_member_update.
    if membre.pending:
        EN_ATTENTE_REGLES[membre.id] = nom_role_invitation
        return

    await accueillir_membre(membre, nom_role_invitation)


@bot.event
async def on_member_update(avant: discord.Member, apres: discord.Member):
    # Le membre vient d'accepter les règles du serveur -> lancer l'accueil
    if avant.pending and not apres.pending:
        nom_role = EN_ATTENTE_REGLES.pop(apres.id, "")
        await accueillir_membre(apres, nom_role)


@bot.tree.command(name="questionnaire", description="(Re)faire le questionnaire d'accueil")
async def commande_questionnaire(interaction: discord.Interaction):
    serveur = interaction.guild or (bot.guilds[0] if bot.guilds else None)
    if serveur is None:
        await interaction.response.send_message("Je ne suis sur aucun serveur pour le moment.", ephemeral=True)
        return
    await interaction.response.send_message("📬 Regarde tes messages privés !", ephemeral=True)
    try:
        await derouler_questionnaire(interaction.user, serveur)
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Impossible de t'écrire en privé. Active tes MP : "
            "clic droit sur le serveur > Paramètres de confidentialité > Messages privés.",
            ephemeral=True,
        )


@bot.tree.command(
    name="installer-bouton",
    description="Publier ici le message d'accueil avec le bouton Commencer (admin)",
)
@app_commands.default_permissions(administrator=True)
async def commande_installer_bouton(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌸 Bienvenue chez Nippon Explorer !",
        description=(
            "Ici, la communauté conçoit et vit des **voyages de groupe au Japon**.\n\n"
            "**Comment ça marche ?**\n"
            "1️⃣ Clique sur le bouton **Commencer** ci-dessous.\n"
            "2️⃣ Réponds au petit questionnaire que je t'envoie en message privé (2 minutes, des clics, pas de texte à taper).\n"
            "3️⃣ Le serveur s'ouvre à toi : salons de discussion, annonces de voyages, et plus encore.\n\n"
            "💬 *Si tu ne reçois pas de message privé, active tes MP : clic droit sur l'icône du serveur → "
            "Paramètres de confidentialité → Messages privés, puis reclique sur le bouton.*"
        ),
        color=COULEUR,
    )
    await interaction.channel.send(embed=embed, view=VueBoutonCommencer())
    await interaction.response.send_message("✅ Message d'accueil publié dans ce salon.", ephemeral=True)


@bot.tree.command(
    name="installer-menu-interets",
    description="Publier ici le menu des centres d'intérêt (admin)",
)
@app_commands.default_permissions(administrator=True)
async def commande_installer_menu_interets(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not INTERETS:
        await interaction.followup.send(
            "❌ Aucun bouton configuré. Remplis l'onglet **Intérêts** du Google Sheet "
            "(colonnes : Étiquette / Rôle / Emoji), puis tape **/recharger**.",
            ephemeral=True,
        )
        return
    serveur = interaction.guild
    manquants = [i["role"] for i in INTERETS if serveur and trouver_role(serveur, i["role"]) is None]
    embed = discord.Embed(
        title="🎴 Choisis tes centres d'intérêt",
        description=(
            "Clique sur les boutons ci-dessous pour **ouvrir les salons** qui t'intéressent.\n"
            "Un clic active l'accès, un second clic le retire. Tu peux changer d'avis à tout moment !"
        ),
        color=COULEUR,
    )
    vues = construire_menus_interets()
    await interaction.channel.send(embed=embed, view=vues[0])
    for vue in vues[1:]:
        await interaction.channel.send(view=vue)
    confirmation = f"✅ Menu publié : {len(INTERETS)} bouton(s) sur {len(vues)} message(s)."
    if manquants:
        confirmation += "\n⚠️ Rôles à créer (boutons inopérants d'ici là) : " + ", ".join(manquants)
    await interaction.followup.send(confirmation, ephemeral=True)


@bot.tree.command(
    name="annonce",
    description="Publier ici une annonce de créneau de voyage (admin)",
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    titre="Titre du voyage (ex. Japon d'automne — Tokyo & Kyoto)",
    dates="Dates du créneau (ex. 12 au 26 octobre 2026)",
    prix="Prix par personne (ex. 3 200 €)",
    places="Nombre de places disponibles",
    lien="Lien vers la page de réservation",
    description="Texte libre de présentation (facultatif)",
)
async def commande_annonce(
    interaction: discord.Interaction,
    titre: str,
    dates: str,
    prix: str,
    places: int,
    lien: str,
    description: str = "",
):
    # Répondre à Discord AVANT de publier : la limite des 3 secondes est
    # facilement dépassée quand l'hébergeur gratuit est lent à réagir.
    await interaction.response.defer(ephemeral=True)
    ident = int(datetime.now(timezone.utc).timestamp())
    embed = discord.Embed(
        title=f"🗾 {titre}"[:256],
        description=description[:2000] or None,
        color=COULEUR,
    )
    embed.add_field(name="📅 Dates", value=dates[:1024], inline=True)
    embed.add_field(name="💶 Prix", value=prix[:1024], inline=True)
    embed.add_field(name="🎫 Places", value=str(places), inline=True)
    embed.add_field(name="🔗 Réservation", value=lien[:1024], inline=False)
    embed.set_footer(text="Clique sur « Ça m'intéresse » pour être compté — sans engagement.")
    vue = discord.ui.View(timeout=None)
    vue.add_item(BoutonAnnonce(ident, 0))
    try:
        await interaction.channel.send(embed=embed, view=vue)
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Je n'ai pas la permission d'écrire dans ce salon. "
            "Vérifie mes permissions ici (Envoyer des messages, Intégrer des liens) puis réessaie.",
            ephemeral=True,
        )
        return
    await interaction.followup.send("✅ Annonce publiée dans ce salon.", ephemeral=True)


@bot.tree.command(
    name="synchro-roles",
    description="Synchroniser les rôles du serveur avec l'onglet Rôles du Sheet (admin)",
)
@app_commands.default_permissions(administrator=True)
async def commande_synchro_roles(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    serveur = interaction.guild
    if serveur is None:
        await interaction.followup.send("Cette commande s'utilise sur le serveur.", ephemeral=True)
        return
    try:
        await asyncio.to_thread(charger_donnees)  # relit le Sheet pour partir de la version à jour
    except Exception as erreur:
        await interaction.followup.send(f"❌ Erreur de lecture du Google Sheet : {erreur}", ephemeral=True)
        return
    if not ROLES_CONFIG:
        await interaction.followup.send(
            "❌ Onglet **Rôles** vide ou absent. Colonnes attendues : "
            "Nom / Couleur / Séparé / Mentionnable / Permissions.",
            ephemeral=True,
        )
        return
    plan, avertissements, orphelins, hors_portee = construire_plan_roles(serveur)

    apercu = discord.Embed(
        title="🧩 Synchronisation des rôles — APERÇU",
        description="Rien n'est encore appliqué. Vérifie puis confirme.",
        color=COULEUR,
    )
    creations = [a["nom"] for a in plan if a["type"] == "creer"]
    modifications = [f"{a['nom']} ({', '.join(a['changements'])})" for a in plan if a["type"] == "modifier"]
    everyone = [a for a in plan if a["type"] == "everyone"]
    if creations:
        apercu.add_field(name=f"➕ À créer ({len(creations)})", value=resumer_liste(creations), inline=False)
    if modifications:
        apercu.add_field(name=f"✏️ À modifier ({len(modifications)})", value=resumer_liste(modifications), inline=False)
    if everyone:
        apercu.add_field(name="✏️ @everyone", value="permissions générales mises à jour", inline=False)
    if hors_portee:
        apercu.add_field(
            name="🚫 Hors de portée (au-dessus du rôle NEObot)",
            value=resumer_liste(hors_portee), inline=False,
        )
    if avertissements:
        apercu.add_field(name="⚠️ Avertissements", value=resumer_liste(avertissements), inline=False)
    if orphelins:
        apercu.add_field(
            name="👻 Sur le serveur mais absents du Sheet (jamais touchés)",
            value=resumer_liste(orphelins), inline=False,
        )
    if not plan:
        apercu.description = "✅ Tout est déjà conforme au Sheet, rien à appliquer."
        await interaction.followup.send(embed=apercu, ephemeral=True)
        return
    await interaction.followup.send(
        embed=apercu,
        view=VueConfirmationRoles(plan, serveur, interaction.user.id),
        ephemeral=True,
    )


@bot.tree.command(
    name="invitations",
    description="Tableau de bord des invitations par influenceur (admin)",
)
@app_commands.default_permissions(administrator=True)
async def commande_invitations(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    serveur = interaction.guild
    if serveur is None:
        await interaction.followup.send("Cette commande s'utilise sur le serveur.", ephemeral=True)
        return
    try:
        actuelles = await serveur.invites()
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Il me faut la permission **Gérer le serveur** pour lire les invitations.",
            ephemeral=True,
        )
        return
    par_code = {inv.code: inv for inv in actuelles}
    embed = discord.Embed(title="📨 Invitations par influenceur", color=COULEUR)
    if INVITATIONS:
        lignes = []
        for code, infos in INVITATIONS.items():
            inv = par_code.get(code)
            uses = str(inv.uses or 0) if inv else "⚠️ introuvable (supprimée ?)"
            lignes.append(f"**{infos['etiquette']}** — `{code}` : {uses} utilisation(s) → rôle « {infos['role']} »")
        embed.add_field(name="Suivies (onglet Invitations)", value="\n".join(lignes)[:1024], inline=False)
    else:
        embed.add_field(
            name="Aucune invitation suivie",
            value="Remplis l'onglet **Invitations** du Sheet (Code / Étiquette / Rôle) puis /recharger.",
            inline=False,
        )
    non_suivies = [inv for inv in actuelles if inv.code not in INVITATIONS]
    if non_suivies:
        lignes = [
            f"`{inv.code}` : {inv.uses or 0} utilisation(s) (créée par {inv.inviter or '?'})"
            for inv in non_suivies
        ]
        embed.add_field(name="Non suivies", value="\n".join(lignes)[:1024], inline=False)
    embed.set_footer(text="Historique détaillé : onglet « Arrivées » du Google Sheet.")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(
    name="synchro-veterans",
    description="Donner le rôle « Vétéran » à tous les détenteurs d'un rôle « Vétéran lvl … » (admin)",
)
@app_commands.default_permissions(administrator=True)
async def commande_synchro_veterans(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    serveur = interaction.guild
    if serveur is None:
        await interaction.followup.send("Cette commande s'utilise sur le serveur.", ephemeral=True)
        return
    parapluie = trouver_role(serveur, "Vétéran")
    if parapluie is None:
        await interaction.followup.send("❌ Crée d'abord un rôle nommé exactement **Vétéran**.", ephemeral=True)
        return
    ajouts, erreurs = 0, 0
    async for membre in serveur.fetch_members(limit=None):
        est_veteran = any(r.name.lower().startswith("vétéran lvl") for r in membre.roles)
        if est_veteran and parapluie not in membre.roles:
            try:
                await membre.add_roles(parapluie, reason="Synchronisation Vétéran")
                ajouts += 1
            except discord.Forbidden:
                erreurs += 1
    message = f"✅ Rôle **Vétéran** donné à {ajouts} membre(s)."
    if erreurs:
        message += f"\n⚠️ {erreurs} échec(s) : vérifie que le rôle du bot est au-dessus de « Vétéran »."
    await interaction.followup.send(message, ephemeral=True)


@bot.tree.command(name="recharger", description="Recharger les questions depuis Google Sheets (admin)")
@app_commands.default_permissions(administrator=True)
async def commande_recharger(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        await asyncio.to_thread(charger_donnees)
    except Exception as erreur:
        await interaction.followup.send(f"❌ Erreur de lecture du Google Sheet : {erreur}", ephemeral=True)
        return
    liste = "\n".join(f"{n}. {q['texte']} ({len(q['options'])} choix)" for n, q in enumerate(QUESTIONS, 1))
    await interaction.followup.send(
        f"✅ **{len(QUESTIONS)} questions chargées :**\n{liste}\n"
        f"🎴 Boutons d'intérêt configurés : {len(INTERETS)}\n"
        f"🧩 Rôles décrits dans l'onglet Rôles : {len(ROLES_CONFIG)}\n"
        f"📨 Invitations suivies : {len(INVITATIONS)}",
        ephemeral=True,
    )


@bot.tree.command(name="export", description="Exporter toutes les réponses en fichier CSV (admin)")
@app_commands.default_permissions(administrator=True)
async def commande_export(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        lignes = await asyncio.to_thread(lire_toutes_les_reponses)
    except Exception as erreur:
        await interaction.followup.send(f"❌ Erreur de lecture du Google Sheet : {erreur}", ephemeral=True)
        return
    tampon = io.StringIO()
    csv.writer(tampon, delimiter=";").writerows(lignes)
    fichier = discord.File(
        io.BytesIO(tampon.getvalue().encode("utf-8-sig")),
        filename="reponses_nippon_explorer.csv",
    )
    await interaction.followup.send(f"📊 {max(len(lignes) - 1, 0)} réponse(s) exportée(s).", file=fichier, ephemeral=True)


# ============================================================
# 7. Démarrage
# ============================================================

if __name__ == "__main__":
    demarrer_serveur_web()
    bot.run(os.environ["DISCORD_TOKEN"])
