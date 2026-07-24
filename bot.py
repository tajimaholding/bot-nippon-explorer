# -*- coding: utf-8 -*-
"""
NEObot v2.1 — Bot d'accueil de Nippon Explorer
--------------------------------------------
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


def ouvrir_classeur():
    infos = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(infos, scopes=PORTEES_GOOGLE)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ["SHEET_ID"])


def charger_donnees():
    """Lit les onglets Questions / Config et prépare l'onglet Réponses."""
    global QUESTIONS, CONFIG, INTERETS
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

    QUESTIONS = questions
    CONFIG = config
    INTERETS = interets


def enregistrer_reponses(utilisateur, reponses):
    classeur = ouvrir_classeur()
    feuille = classeur.worksheet("Réponses")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    ligne = [date, str(utilisateur), str(utilisateur.id)] + [", ".join(r) for r in reponses]
    feuille.append_row(ligne, value_input_option="USER_ENTERED")


def lire_toutes_les_reponses():
    classeur = ouvrir_classeur()
    return classeur.worksheet("Réponses").get_all_values()


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
        self.add_dynamic_items(BoutonInteret)  # réactive les boutons d'intérêt
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
    print(f"🤖 Connecté en tant que {bot.user}")


@bot.event
async def on_member_join(membre: discord.Member):
    if membre.bot:
        return

    # 1) Rôle d'arrivée immédiat (Curieux) : accès lecture seule aux zones publiques
    role_arrivee = trouver_role(membre.guild, CONFIG.get("ROLE_ARRIVEE", ""))
    if role_arrivee:
        try:
            await membre.add_roles(role_arrivee, reason="Arrivée sur le serveur")
        except discord.Forbidden:
            print(f"⚠️ Impossible de donner {role_arrivee.name} (rôle du bot trop bas ?)")

    # 2) Questionnaire en MP
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
        f"🎴 Boutons d'intérêt configurés : {len(INTERETS)}",
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
