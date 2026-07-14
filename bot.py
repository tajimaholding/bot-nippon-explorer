# -*- coding: utf-8 -*-
"""
Bot d'accueil (onboarding) — Nippon Explorer
--------------------------------------------
Ce que fait ce bot :
  1. Quand un nouveau membre rejoint le serveur, il lui envoie un
     questionnaire en message privé (menus cliquables).
  2. Selon la réponse à la question "Qui vous a parlé de Nippon Explorer ?",
     il attribue automatiquement le bon rôle (Team Fildrong, Filleul(e), etc.).
  3. Toutes les réponses sont enregistrées dans un Google Sheet.
  4. Les questions se modifient DANS le Google Sheet (onglet "Questions"),
     puis on tape /recharger sur Discord. Aucune modification de code.

Commandes disponibles sur Discord :
  /questionnaire  -> (re)faire le questionnaire (utile pour tester ou si MP fermés)
  /recharger      -> recharger les questions depuis le Google Sheet (admin)
  /export         -> recevoir toutes les réponses en fichier CSV (admin)

Variables d'environnement à définir chez l'hébergeur (voir GUIDE) :
  DISCORD_TOKEN            -> le jeton secret du bot Discord
  SHEET_ID                 -> l'identifiant du Google Sheet
  GOOGLE_CREDENTIALS_JSON  -> le contenu du fichier JSON du compte de service Google
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
#    (Render + UptimeRobot le "pingent" pour garder le bot éveillé)
# ============================================================

def demarrer_serveur_web():
    port = int(os.environ.get("PORT", 10000))

    class Poignee(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Le bot est en ligne.".encode("utf-8"))

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass  # silence

    serveur = http.server.ThreadingHTTPServer(("0.0.0.0", port), Poignee)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()


# ============================================================
# 2. Connexion Google Sheets
# ============================================================

PORTEES_GOOGLE = ["https://www.googleapis.com/auth/spreadsheets"]

QUESTIONS = []   # liste de dicts : {"texte", "options", "multiple", "roles"}
CONFIG = {}      # options facultatives lues dans l'onglet "Config"


def ouvrir_classeur():
    infos = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(infos, scopes=PORTEES_GOOGLE)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ["SHEET_ID"])


def charger_donnees():
    """Lit les onglets Questions / Config et prépare l'onglet Réponses."""
    global QUESTIONS, CONFIG
    classeur = ouvrir_classeur()

    # --- Onglet "Questions" ---
    lignes = classeur.worksheet("Questions").get_all_records()
    questions = []
    for ligne in lignes:
        texte = str(ligne.get("Question", "")).strip()
        options = [o.strip() for o in str(ligne.get("Options", "")).split(";") if o.strip()]
        if not texte or not options:
            continue  # ligne vide ou incomplète : ignorée
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
            "options": options[:25],   # Discord limite à 25 choix par menu
            "multiple": multiple,
            "roles": roles,
        })

    # --- Onglet "Config" (facultatif) ---
    config = {}
    try:
        for ligne in classeur.worksheet("Config").get_all_values():
            if len(ligne) >= 2 and ligne[0].strip():
                config[ligne[0].strip().upper()] = ligne[1].strip()
    except gspread.WorksheetNotFound:
        pass

    # --- Onglet "Réponses" : créé si absent, en-têtes mis à jour ---
    try:
        feuille_r = classeur.worksheet("Réponses")
    except gspread.WorksheetNotFound:
        feuille_r = classeur.add_worksheet(title="Réponses", rows=2000, cols=30)
    entetes = ["Date", "Pseudo", "ID Discord"] + [q["texte"] for q in questions]
    feuille_r.update(range_name="A1", values=[entetes])

    QUESTIONS = questions
    CONFIG = config


def enregistrer_reponses(utilisateur, reponses):
    """Ajoute une ligne dans l'onglet Réponses."""
    classeur = ouvrir_classeur()
    feuille = classeur.worksheet("Réponses")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    ligne = [date, str(utilisateur), str(utilisateur.id)] + [", ".join(r) for r in reponses]
    feuille.append_row(ligne, value_input_option="USER_ENTERED")


def lire_toutes_les_reponses():
    classeur = ouvrir_classeur()
    return classeur.worksheet("Réponses").get_all_values()


# ============================================================
# 3. Le questionnaire (menus cliquables en message privé)
# ============================================================

COULEUR = 0xD90F2C  # rouge Japon
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


sessions_en_cours = set()  # évite de lancer 2 questionnaires en même temps pour la même personne


async def derouler_questionnaire(utilisateur: discord.User, serveur: discord.Guild):
    """Envoie les questions une par une en MP, attribue les rôles, enregistre tout."""
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
        await mp.send(embed=bienvenue)  # si les MP sont fermés -> discord.Forbidden

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

            if vue.valeurs is None:  # temps écoulé
                await mp.send(
                    "⏳ Le temps est écoulé. Tape **/questionnaire** sur le serveur "
                    "pour recommencer quand tu veux !"
                )
                return

            reponses.append(vue.valeurs)
            embed.add_field(name="Ta réponse ✅", value=", ".join(vue.valeurs), inline=False)
            await message.edit(embed=embed, view=None)

        # --- Attribution des rôles ---
        roles_donnes, roles_introuvables = await attribuer_roles(utilisateur, serveur, reponses)

        # --- Enregistrement dans Google Sheets ---
        try:
            await asyncio.to_thread(enregistrer_reponses, utilisateur, reponses)
        except Exception as erreur:
            print(f"[ERREUR Google Sheets] {erreur}")

        # --- Message de fin ---
        merci = discord.Embed(
            title="🎌 Merci, et bienvenue chez Nippon Explorer !",
            description="Ton profil est enregistré. Bonne exploration !",
            color=COULEUR,
        )
        if roles_donnes:
            merci.add_field(name="Rôles attribués", value=", ".join(roles_donnes), inline=False)
        await mp.send(embed=merci)

        # --- Journal pour les admins (facultatif) ---
        await journaliser(serveur, utilisateur, reponses, roles_donnes, roles_introuvables)
    finally:
        sessions_en_cours.discard(utilisateur.id)


async def attribuer_roles(utilisateur, serveur, reponses):
    """Attribue les rôles correspondant aux réponses + le rôle final éventuel."""
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
    membre = serveur.get_member(utilisateur.id)
    if membre is None:
        try:
            membre = await serveur.fetch_member(utilisateur.id)
        except discord.NotFound:
            return donnes, noms_voulus

    for nom in noms_voulus:
        role = discord.utils.find(lambda r: r.name.lower() == nom.lower(), serveur.roles)
        if role is None:
            introuvables.append(nom)
            continue
        try:
            await membre.add_roles(role, reason="Questionnaire d'accueil")
            donnes.append(role.name)
        except discord.Forbidden:
            introuvables.append(f"{nom} (le rôle du bot est trop bas dans la liste)")
    return donnes, introuvables


async def journaliser(serveur, utilisateur, reponses, roles_donnes, roles_introuvables):
    """Envoie un résumé dans le salon indiqué par SALON_LOGS (Config), si défini."""
    salon_id = CONFIG.get("SALON_LOGS", "").strip()
    if not salon_id.isdigit():
        return
    salon = serveur.get_channel(int(salon_id))
    if salon is None:
        return
    resume = discord.Embed(
        title=f"📋 Questionnaire terminé : {utilisateur}",
        color=COULEUR,
    )
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
# 4. Le bot Discord et ses commandes
# ============================================================

intents = discord.Intents.default()
intents.members = True  # nécessaire pour détecter les arrivées (à activer aussi sur le site Discord Dev !)


class BotAccueil(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.donnees_chargees = False

    async def setup_hook(self):
        await self.tree.sync()  # publie les commandes /


bot = BotAccueil()


@bot.event
async def on_ready():
    if not bot.donnees_chargees:
        try:
            await asyncio.to_thread(charger_donnees)
            bot.donnees_chargees = True
            print(f"✅ {len(QUESTIONS)} questions chargées depuis Google Sheets.")
        except Exception as erreur:
            print(f"❌ Impossible de lire le Google Sheet : {erreur}")
        # rend les commandes / disponibles immédiatement sur chaque serveur
        for serveur in bot.guilds:
            bot.tree.copy_global_to(guild=serveur)
            await bot.tree.sync(guild=serveur)
    print(f"🤖 Connecté en tant que {bot.user}")


@bot.event
async def on_member_join(membre: discord.Member):
    if membre.bot:
        return
    try:
        await derouler_questionnaire(membre, membre.guild)
    except discord.Forbidden:
        # MP fermés -> on prévient dans le salon de secours s'il est défini
        salon_id = CONFIG.get("SALON_FALLBACK", "").strip()
        if salon_id.isdigit():
            salon = membre.guild.get_channel(int(salon_id))
            if salon:
                try:
                    await salon.send(
                        f"👋 Bienvenue {membre.mention} ! Je n'ai pas pu t'envoyer de message privé. "
                        "Active tes MP (Paramètres du serveur > Confidentialité) puis tape **/questionnaire** ici."
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
    await interaction.followup.send(f"✅ **{len(QUESTIONS)} questions chargées :**\n{liste}", ephemeral=True)


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
        io.BytesIO(tampon.getvalue().encode("utf-8-sig")),  # utf-8-sig : accents corrects dans Excel
        filename="reponses_nippon_explorer.csv",
    )
    await interaction.followup.send(f"📊 {max(len(lignes) - 1, 0)} réponse(s) exportée(s).", file=fichier, ephemeral=True)


# ============================================================
# 5. Démarrage
# ============================================================

if __name__ == "__main__":
    demarrer_serveur_web()
    bot.run(os.environ["DISCORD_TOKEN"])
