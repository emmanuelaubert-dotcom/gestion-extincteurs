from datetime import datetime, timedelta
import json
import pandas as pd
import requests
import streamlit as st
from streamlit_qrcode_scanner import qrcode_scanner
from zoneinfo import ZoneInfo

# 1. Définir le fuseau horaire de Paris
fuseau_paris = ZoneInfo("Europe/Paris")

# 2. Récupérer l'heure actuelle à Paris
maintenant_paris = datetime.now(fuseau_paris)
heure_formatee = maintenant_paris.strftime("%d/%m/%Y à %H:%M:%S")

# Masquer la barre d'outils et le badge GitHub
hide_toolbar = """
    <style>
    div[data-testid="stToolbar"] {
        display: none !important;
    }
    </style>
"""
st.markdown(hide_toolbar, unsafe_allow_html=True)

# LIENS DE DESIGN
URL_LOGO = "https://www.centre-formation-securite.fr/wp-content/uploads/2018/11/logo-si2p-fond-clair.png"
URL_FOND = "https://www.centre-formation-securite.fr/wp-content/uploads/triangle-si2p.png"

# URL DE VOTRE APPLICATION WEB GOOGLE APPS SCRIPT
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyfh2erJV6P6l9IuLRwRVORvyx14n2dgUsrTVxyMOWlktKujgrlAS4aH-ySmAxUqUA/exec
"

st.set_page_config(
    page_title="Gestion Extincteurs",
    page_icon="https://img.icons8.com/stickers/1200/fire-extinguisher.jpg",
    layout="centered",
)

# STYLE GLOBAL
st.markdown(
    """
    <style>
    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.9)), url("https://www.centre-formation-securite.fr/wp-content/uploads/triangle-si2p.png");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }
    html, body, [class*="css"] { font-size: 18px; }
    .stButton>button { width: 100%; height: 3.5em; font-size: 20px; font-weight: bold; border-radius: 10px; }
    h1 { font-size: 32px !important; }
    h2 { font-size: 26px !important; }
    h3 { font-size: 22px !important; }

    .stTextInput input {
        border: 2px solid black !important;
        border-radius: 8px !important;
    }
    
    .footer-deconnexion {
        background-color: #f8d7da;
        color: #721c24;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        margin-top: 30px;
        margin-bottom: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)


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
          f"⏳ Cet extincteur a déjà été modifié il y a moins d'une heure."
          f" Veuillez patienter encore environ {mins} minute(s)."
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


def update_sparklets(qte_pris, qte_depose, utilisateur, date):
  try:
    params = {
        "action": "updateSparklets",
        "qte_pris": qte_pris,
        "qte_depose": qte_depose,
        "utilisateur": utilisateur,
        "date": date,
    }
    response = requests.post(APPS_SCRIPT_URL, data=params)
    return response.json()
  except Exception as e:
    st.error(f"Erreur lors de la mise à jour des sparklets : {e}")
    return None


# --- GESTION DES ÉTATS GLOBAUX ---
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
      if res:
        if res.get("status") == "success":
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
          st.rerun()
        else:
          st.error("Code d'accès incorrect.")
      else:
        st.error("Erreur de communication avec le serveur.")

# --- INTERFACE UTILISATEUR CONNECTÉ ---
else:
  user = st.session_state.user
  if URL_LOGO:
    st.sidebar.image(URL_LOGO, use_container_width=True)
  st.sidebar.write(f"👤 **{user.get('Nom')}**")
  st.sidebar.write(f"🔑 Rôle : *{user.get('Role')}*")

  df_ext, _ = get_data()

  # ==========================================
  # ÉTAPE 1 : GESTION DES SPARKLETS (PAGE UNIQUE)
  # ==========================================
  if st.session_state.etape_utilisateur == "sparklets":
    st.title("💧 Gestion des Sparklets")
    st.write(
        "Veuillez renseigner vos mouvements de sparklets avant de continuer."
    )

    col_sp1, col_sp2 = st.columns(2)

    with col_sp1:
      st.write("**Pris / Emportés**")
      qte_pris = st.number_input(
          "Quantité prise", min_value=0, max_value=50, value=0, key="qte_pris_sp"
      )

    with col_sp2:
      st.write("**Déposés / Restitués**")
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
        update_sparklets(qte_pris, qte_depose, user.get("Nom"), date_du_jour)
        st.session_state.session_actions["sparklets_prises"] += qte_pris
        st.session_state.session_actions["sparklets_deposees"] += qte_depose

      st.session_state.etape_utilisateur = "travail"
      st.rerun()

  # ==========================================
  # ÉTAPE 2 : TRAVAIL (FORMATEUR OU PRESTATAIRE)
  # ==========================================
  elif st.session_state.etape_utilisateur == "travail":

    # --- FORMATEUR ---
    if str(user.get("Role")).strip().lower() == "formateur":
      st.title("🧯 Formateur - Scan des Extincteurs")

      id_scanne = qrcode_scanner(key="scanner_formateur")

      if id_scanne:
        mask = (
            df_ext["ID_QRCode"].astype(str).str.strip().str.lower()
            == str(id_scanne).strip().lower()
        )

        if mask.any():
          nom_extincteur = df_ext.loc[mask, "ID_Extincteur"].values[0]
          st.info(
              f"🔍 Extincteur reconnu : **{nom_extincteur}** (Code:"
              f" {id_scanne})"
          )

          statut_actuel = df_ext.loc[mask, "Statut"].values[0]

          if statut_actuel == "Plein":
            nouveau_statut = "En formation"
          elif statut_actuel == "En formation":
            nouveau_statut = "Vide"
          else:
            nouveau_statut = None

          if nouveau_statut:
            date_du_jour = datetime.now(fuseau_paris).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
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
          else:
            st.warning(f"⚠️ Cet extincteur est déjà au statut '{statut_actuel}'.")
        else:
          st.error(f"❌ Le code scanné '{id_scanne}' est introuvable.")

    # --- PRESTATAIRE ---
    elif str(user.get("Role")).strip().lower() == "prestataire":
      st.image(
          "https://thumbs.dreamstime.com/b/extincteur-avec-rendu-d-camion-isol%C3%A9-sur-fond-blanc-272191597.jpg"
      )
      st.title("🚚 Prestataire")

      choix_action = st.radio(
          "Action :",
          (
              "Récupérer des extincteurs (Lot)",
              "Déposer des extincteurs Plein (Scan individuel)",
          ),
      )

      if "Récupérer" in choix_action:
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
          date_du_jour = datetime.now(fuseau_paris).strftime(
              "%Y-%m-%d %H:%M:%S"
          )
          res_batch = update_batch(
              quantite_a_prendre, user.get("Nom"), date_du_jour
          )
          if res_batch and res_batch.get("status") == "success":
            nb_pris = res_batch.get("count")
            st.session_state.session_actions["En rechargement"] += nb_pris
            st.success(
                f"🚀 Départ validé pour {nb_pris} extincteur(s). Enregistré"
                " pour le bilan."
            )
            st.rerun()

      else:
        st.write(
            "Scannez individuellement chaque extincteur de retour pour le"
            " basculer en **Plein** (peu importe son statut précédent)."
        )
        id_scanne_retour = qrcode_scanner(key="scanner_prestataire_retour")

        if id_scanne_retour:
          mask = (
              df_ext["ID_QRCode"].astype(str).str.strip().str.lower()
              == str(id_scanne_retour).strip().lower()
          )

          if mask.any():
            nom_extincteur = df_ext.loc[mask, "ID_Extincteur"].values[0]
            st.info(
                f"🔍 Extincteur reconnu : **{nom_extincteur}** (Code:"
                f" {id_scanne_retour})"
            )

            statut_actuel = df_ext.loc[mask, "Statut"].values[0]

            if statut_actuel != "Plein":
              date_du_jour = datetime.now(fuseau_paris).strftime(
                  "%Y-%m-%d %H:%M:%S"
              )
              success = update_sheet(
                  str(id_scanne_retour), "Plein", user.get("Nom"), date_du_jour
              )
              if success:
                st.success(
                    f"✅ Extincteur **{nom_extincteur}** (anciennement"
                    f" '{statut_actuel}') de retour et basculé en **Plein** !"
                )
            else:
              st.warning(
                  f"⚠️ Cet extincteur est déjà au statut : **Plein**"
              )
          else:
            st.error("❌ Code QR introuvable.")

    # --- DÉCONNEXION FINALE ---
    st.markdown("---")
    st.markdown(
        '<div class="footer-deconnexion">⚠️ Une fois fini, cliquez ci-dessous pour'
        " envoyer le bilan et vous déconnecter en toute sécurité !</div>",
        unsafe_allow_html=True,
    )

    if st.button(
        "🔒 Se déconnecter et envoyer le bilan", key="btn_deconnexion_bas"
    ):
      code_utilisateur = str(user.get("Code"))
      actions_bilan = st.session_state.get("session_actions", None)

      logout_user(code_utilisateur, actions_bilan)
      st.session_state.clear()
      st.rerun()
