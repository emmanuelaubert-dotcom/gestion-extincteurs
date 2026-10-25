from datetime import datetime, timedelta
import json
import pandas as pd
import requests
import streamlit as st
from streamlit_qrcode_scanner import qrcode_scanner
from zoneinfo import ZoneInfo

# Configurations
URL_LOGO = "https://www.centre-formation-securite.fr/wp-content/uploads/2018/11/logo-si2p-fond-clair.png"
URL_FOND = "https://www.centre-formation-securite.fr/wp-content/uploads/triangle-si2p.png"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxrTd_cnA9d7NZjjb9ijFMw5t0R_s2XmVqgRqjXY3M8Uzgah8Xy0cb2XXaK19Cfhs0/exec"

# 1. Configuration de la page (unique)
st.set_page_config(
    page_title="Gestion Extincteurs & Sparklets",
    page_icon="🧯",
    layout="wide",
)

# Fuseau horaire
fuseau_paris = ZoneInfo("Europe/Paris")


# --- FONCTIONS UTILITAIRES ---
def get_data():
  try:
    response = requests.get(APPS_SCRIPT_URL + "?action=getData")
    data = response.json()
    df_ext = pd.DataFrame(data["extincteurs"][1:], columns=data["extincteurs"][0])
    df_users = pd.DataFrame(
        data["utilisateurs"][1:], columns=data["utilisateurs"][0]
    )
    return df_ext, df_users
  except Exception as e:
    st.error(f"Erreur de communication avec Google Sheets : {e}")
    return None, None


def attempt_login(code):
  try:
    response = requests.post(APPS_SCRIPT_URL, data={"action": "login", "code": code})
    return response.json()
  except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    return None


def logout_user(code_utilisateur, actions_bilan):
  try:
    if actions_bilan is None:
      actions_bilan = {}

    stats_a_envoyer = {
        "En formation": actions_bilan.get("En formation", 0),
        "Vide": actions_bilan.get("Vide", 0),
        "En rechargement": actions_bilan.get("En rechargement", 0),
        "Pleins": actions_bilan.get("Pleins", 0),
        "sparklets_prises": actions_bilan.get("sparklets_prises", 0),
        "sparklets_deposees": actions_bilan.get("sparklets_deposees", 0),
    }

    stats_json = json.dumps(stats_a_envoyer)
    params = {
        "action": "logout",
        "code": code_utilisateur,
        "actions": stats_json,
    }
    requests.get(APPS_SCRIPT_URL, params=params)
  except Exception as e:
    print(f"Erreur lors de la déconnexion : {e}")


def update_sheet(id_ext, statut, utilisateur, date):
  try:
    params = {
        "action": "update",
        "id": id_ext,
        "statut": statut,
        "utilisateur": utilisateur,
        "date": date,
    }
    response = requests.post(APPS_SCRIPT_URL, data=params)
    res_data = response.json()

    if res_data.get("status") == "too_soon":
      mins = res_data.get("minutes", 60)
      st.warning(
          f"⏳ Cet extincteur a déjà été modifié il y a moins d'une heure. Veuillez patienter encore environ {mins} minute(s)."
      )
      return False

    elif res_data.get("status") == "success":
      if "session_actions" in st.session_state:
        if statut == "En formation":
          st.session_state.session_actions["En formation"] += 1
        elif statut == "Vide":
          st.session_state.session_actions["Vide"] += 1
        elif statut == "Plein":
          st.session_state.session_actions["Pleins"] += 1
      return True
    else:
      st.error("Erreur lors de la mise à jour.")
      return False
  except Exception as e:
    st.error(f"Erreur de communication : {e}")
    return False


def update_batch(quantite, utilisateur, date):
  try:
    params = {
        "action": "updateBatch",
        "quantite": quantite,
        "utilisateur": utilisateur,
        "date": date,
    }
    response = requests.post(APPS_SCRIPT_URL, data=params)
    return response.json()
  except Exception as e:
    st.error(f"Erreur lors de la validation du lot : {e}")
    return None


def update_sparklets(qte_pris, qte_depose, utilisateur, role, date):
  try:
    params = {
        "action": "updateSparklets",
        "qte_pris": qte_pris,
        "qte_depose": qte_depose,
        "utilisateur": utilisateur,
        "role": role,
        "date": date,
    }
    response = requests.post(APPS_SCRIPT_URL, data=params)
    return response.json()
  except Exception as e:
    st.error(f"Erreur lors de la mise à jour des sparklets : {e}")
    return None


def sauvegarder_contexte_url():
  if st.session_state.get("user"):
    st.query_params["active_code"] = str(st.session_state.user.get("Code"))
    st.query_params["actions_json"] = json.dumps(
        st.session_state.get("session_actions", {})
    )
    st.query_params["etape"] = str(
        st.session_state.get("etape_utilisateur", "sparklets")
    )
    if "choix_action_prestataire" in st.session_state:
      st.query_params["choix_prestataire"] = st.session_state[
          "choix_action_prestataire"
      ]


# --- RESTAURATION AUTOMATIQUE EN CAS DE F5 ---
params = st.query_params
if "active_code" in params and st.session_state.get("user") is None:
  code_en_cours = params["active_code"]
  res = attempt_login(code_en_cours)
  if res and res.get("status") == "success":
    st.session_state.user = res.get("user")

    if "actions_json" in params:
      try:
        st.session_state.session_actions = json.loads(params["actions_json"])
      except:
        pass

    if "etape" in params:
      st.session_state.etape_utilisateur = params["etape"]

    if "choix_prestataire" in params:
      st.session_state["choix_action_prestataire"] = params["choix_prestataire"]


# --- ÉTATS GLOBAUX DE BASE ---
if "user" not in st.session_state:
  st.session_state.user = None
if "last_activity" not in st.session_state:
  st.session_state.last_activity = datetime.now(fuseau_paris)
if "session_actions" not in st.session_state:
  st.session_state.session_actions = {
      "En formation": 0,
      "Vide": 0,
      "En rechargement": 0,
      "Pleins": 0,
      "extincteurs_vides": [],
      "extincteurs_recharges": [],
      "sparklets_prises": 0,
      "sparklets_deposees": 0,
  }
if "etape_utilisateur" not in st.session_state:
  st.session_state.etape_utilisateur = "sparklets"


# =========================================================================
# VÉRIFICATION DE L'INACTIVITÉ (1 HEURE) + ENVOI DU RAPPORT
# =========================================================================
if st.session_state.user is not None:
  if "last_activity" in st.session_state:
    inactivite = (
        datetime.now(fuseau_paris) - st.session_state.last_activity
    ).total_seconds()
    if inactivite > 3600:
      code_user = st.session_state.user.get("Code")
      actions_bilan = st.session_state.get("session_actions", {})
      logout_user(code_user, actions_bilan)

      st.session_state.clear()
      st.query_params.clear()
      st.warning(
          "⏱️ Déconnexion automatique après 1 heure d'inactivité. Votre rapport"
          " a bien été envoyé."
      )
      st.stop()


# =========================================================================
# INTERCEPTION PRIORITAIRE DE LA DÉCONNEXION MANUELLE
# =========================================================================
if st.session_state.get("declencher_deconnexion", False):
  if st.session_state.user:
    code_user = st.session_state.user.get("Code")
    actions_bilan = st.session_state.get("session_actions", {})
    logout_user(code_user, actions_bilan)

  st.session_state.clear()
  st.query_params.clear()
  st.rerun()


# --- FRAGMENTS STREAMLIT POUR ACCÉLÉRER L'EXÉCUTION ---
@st.fragment
def afficher_sparklets(user):
  st.title("💧 Gestion des Sparklets")
  st.write("Veuillez renseigner vos mouvements de sparklets avant de continuer.")

  col_sp1, col_sp2 = st.columns(2)
  with col_sp1:
    st.write("**Prises / Emportées**")
    qte_pris = st.number_input(
        "Quantité prise", min_value=0, max_value=50, value=0, key="qte_pris_sp"
    )

  with col_sp2:
    st.write("**Déposées / Restituées**")
    qte_depose = st.number_input(
        "Quantité déposée",
        min_value=0,
        max_value=50,
        value=0,
        key="qte_depose_sp",
    )

  st.markdown("<br>", unsafe_allow_html=True)

  if st.button("Valider et passer à l'étape suivante ➔"):
    date_du_jour = datetime.now(fuseau_paris).strftime("%Y-%m-%d %H:%M:%S")
    if qte_pris > 0 or qte_depose > 0:
      update_sparklets(
          qte_pris,
          qte_depose,
          user.get("Nom"),
          user.get("Role"),
          date_du_jour,
      )
      st.session_state.session_actions["sparklets_prises"] += qte_pris
      st.session_state.session_actions["sparklets_deposees"] += qte_depose

    st.session_state.etape_utilisateur = "travail"
    sauvegarder_contexte_url()
    st.rerun()


@st.fragment
def afficher_formateur(user, df_ext):
  st.title("🧯 Formateur - Scan des Extincteurs")
  id_scanne = qrcode_scanner(key="scanner_formateur")

  if id_scanne:
    mask = (
        df_ext["ID_QRCode"].astype(str).str.strip().str.lower()
        == str(id_scanne).strip().lower()
    )
    if mask.any():
      nom_extincteur = df_ext.loc[mask, "ID_Extincteur"].values[0]
      st.info(f"🔍 Extincteur reconnu : **{nom_extincteur}** (Code: {id_scanne})")
      statut_actuel = df_ext.loc[mask, "Statut"].values[0]

      if statut_actuel == "Plein":
        nouveau_statut = "En formation"
      elif statut_actuel == "En formation":
        nouveau_statut = "Vide"
      else:
        nouveau_statut = None

      if nouveau_statut:
        date_du_jour = datetime.now(fuseau_paris).strftime("%Y-%m-%d %H:%M:%S")
        success = update_sheet(
            str(id_scanne), nouveau_statut, user.get("Nom"), date_du_jour
        )
        if success:
          st.success(
              f"✅ Extincteur **{nom_extincteur}** mis à jour :"
              f" **{nouveau_statut}**"
          )
          if nouveau_statut == "Vide":
            st.session_state.session_actions["extincteurs_vides"].append(
                f"{nom_extincteur} ({id_scanne})"
            )
          sauvegarder_contexte_url()
      else:
        st.warning(f"⚠️ Cet extincteur est déjà au statut '{statut_actuel}'.")
    else:
      st.error(f"❌ Le code scanné '{id_scanne}' est introuvable.")


@st.fragment
def afficher_prestataire(user, df_ext):
  st.title("🚚 Prestataire")

  index_radio = 0
  if (
      "choix_action_prestataire" in st.session_state
      and "Déposer" in str(st.session_state["choix_action_prestataire"])
  ):
    index_radio = 1

  choix_action = st.radio(
      "Action :",
      (
          "Récupérer des extincteurs (Lot)",
          "Déposer des extincteurs Plein (Scan individuel)",
      ),
      index=index_radio,
      key="choix_action_prestataire",
  )

  sauvegarder_contexte_url()

  if "Récupérer" in str(choix_action):
    vides = df_ext[df_ext["Statut"] == "Vide"]
    nb_vides = len(vides)
    st.info(f"📦 Extincteurs actuellement marqués 'Vide' : **{nb_vides}**")
    quantite_a_prendre = st.number_input(
        "Combien d'extincteurs le prestataire emporte-t-il ?",
        min_value=1,
        max_value=100,
        value=max(1, nb_vides),
    )

    if st.button("Valider le départ du lot"):
      date_du_jour = datetime.now(fuseau_paris).strftime("%Y-%m-%d %H:%M:%S")
      res_batch = update_batch(quantite_a_prendre, user.get("Nom"), date_du_jour)
      if res_batch and res_batch.get("status") == "success":
        nb_pris = res_batch.get("count")
        st.session_state.session_actions["En rechargement"] += nb_pris
        st.success(
            f"🚀 Départ validé pour {nb_pris} extincteur(s). Enregistré pour le"
            " bilan."
        )
        sauvegarder_contexte_url()
        st.rerun()

  else:
    st.write(
        "Scannez individuellement chaque extincteur de retour pour le basculer"
        " en **Plein**."
    )
    id_scanne_retour = qrcode_scanner(key="scanner_prestataire_retour")

    if id_scanne_retour:
      mask = (
          df_ext["ID_QRCode"].astype(str).str.strip().str.lower()
          == str(id_scanne_retour).strip().lower()
      )
      if mask.any():
        nom_extincteur = df_ext.loc[mask, "ID_Extincteur"].values[0]
        statut_actuel = df_ext.loc[mask, "Statut"].values[0]
        if statut_actuel != "Plein":
          date_du_jour = datetime.now(fuseau_paris).strftime("%Y-%m-%d %H:%M:%S")
          success = update_sheet(
              str(id_scanne_retour), "Plein", user.get("Nom"), date_du_jour
          )
          if success:
            st.success(
                f"✅ Extincteur **{nom_extincteur}** de retour et basculé en"
                " **Plein** !"
            )
            sauvegarder_contexte_url()
        else:
          st.warning("⚠️ Cet extincteur est déjà au statut : **Plein**")
      else:
        st.error("❌ Code QR introuvable.")


# --- STYLE CSS ---
hide_toolbar = """
    <style>
    div[data-testid="stToolbar"] { display: none !important; }
    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.9)), url("https://www.centre-formation-securite.fr/wp-content/uploads/triangle-si2p.png");
        background-size: cover; background-position: center; background-repeat: no-repeat;
    }
    html, body, [class*="css"] { font-size: 18px; }
    .stButton>button { width: 100%; height: 3.5em; font-size: 20px; font-weight: bold; border-radius: 10px; }
    h1 { font-size: 32px !important; }
    h2 { font-size: 26px !important; }
    h3 { font-size: 22px !important; }
    .stTextInput input { border: 2px solid black !important; border-radius: 8px !important; }
    .footer-deconnexion {
        background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 8px;
        text-align: center; font-weight: bold; margin-top: 30px; margin-bottom: 15px;
    }
    </style>
"""
st.markdown(hide_toolbar, unsafe_allow_html=True)


# --- AUTHENTIFICATION ---
if st.session_state.user is None:
  st.image(
      "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQgi9peMxjPgEpbUU1SHhUBqaJa_GjKOId_5oPXARaqJw&s=10"
  )
  st.title("🧯 Connexion")
  code_saisi = st.text_input("Code d'accès", type="password")

  if st.button("Se connecter"):
    if not code_saisi:
      st.error("Veuillez saisir un code.")
    else:
      res = attempt_login(code_saisi)
      if res and res.get("status") == "success":
        st.session_state.user = res.get("user")
        st.session_state.last_activity = datetime.now(fuseau_paris)
        st.session_state.session_actions = {
            "En formation": 0,
            "Vide": 0,
            "En rechargement": 0,
            "Pleins": 0,
            "extincteurs_vides": [],
            "extincteurs_recharges": [],
            "sparklets_prises": 0,
            "sparklets_deposees": 0,
        }
        st.session_state.etape_utilisateur = "sparklets"
        sauvegarder_contexte_url()
        st.rerun()
      else:
        st.error("Code d'accès incorrect ou erreur serveur.")

# --- INTERFACE UTILISATEUR CONNECTÉ ---
else:
  st.session_state.last_activity = datetime.now(fuseau_paris)

  user = st.session_state.user
  if URL_LOGO:
    st.sidebar.image(URL_LOGO, use_container_width=True)
  st.sidebar.write(f"👤 **{user.get('Nom')}**")
  st.sidebar.write(f"🔑 Rôle : *{user.get('Role')}*")

  df_ext, _ = get_data()

  # Exécution via les fragments pour accélérer les interactions et les scans
  if st.session_state.etape_utilisateur == "sparklets":
    afficher_sparklets(user)
  elif st.session_state.etape_utilisateur == "travail":
    role = str(user.get("Role")).strip().lower()
    if role == "formateur":
      afficher_formateur(user, df_ext)
    elif role == "prestataire":
      afficher_prestataire(user, df_ext)

  # DÉCONNEXION FINALE (Visible pour tout le monde en bas de page)
  st.markdown("---")
  st.markdown(
      '<div class="footer-deconnexion">⚠️ Une fois fini, cliquez ci-dessous pour'
      " vous déconnecter en toute sécurité !</div>",
      unsafe_allow_html=True,
  )

  if st.button("🔒 Se déconnecter ", key="btn_deconnexion_bas"):
    st.session_state["declencher_deconnexion"] = True
    st.rerun()
