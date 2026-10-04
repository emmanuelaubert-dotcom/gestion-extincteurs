from datetime import datetime, timedelta
import pandas as pd
import requests
import streamlit as st
from streamlit_qrcode_scanner import qrcode_scanner

# 1. VOS LIENS DE DESIGN (laissez vide "" si besoin)
URL_LOGO = "https://www.centre-formation-securite.fr/wp-content/uploads/2018/11/logo-si2p-fond-clair.png"
URL_FOND = "https://www.centre-formation-securite.fr/wp-content/uploads/triangle-si2p.png"

# METTEZ ICI L'URL DE VOTRE APPLICATION WEB GOOGLE APPS SCRIPT :
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx3fTCNDT5w8mlsxq1JHO_gUUz5ythgeGrzvl7n8rMEeWZdOGU7N7IIHAWQSAaV8h8/exec"

st.set_page_config(
    page_title="Gestion Extincteurs", page_icon="https://img.icons8.com/stickers/1200/fire-extinguisher.jpg", layout="centered"
)

# STYLE GLOBAL (IMAGE DE FOND, TAILLE DES TEXTES, BOUTONS)
st.markdown(
    """
    <style>
    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.9)), url("https://www.centre-formation-securite.fr/wp-content/uploads/triangle-si2p.png");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }
    html, body, [class*="css"] {{ font-size: 18px; }}
    .stButton>button { width: 100%; height: 3.5em; font-size: 20px; font-weight: bold; border-radius: 10px; }
    h1 { font-size: 32px !important; }
    h2 { font-size: 26px !important; }
    h3 { font-size: 22px !important; }

    /* Contour noir autour du champ de saisie de connexion */
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



if URL_LOGO:
  st.sidebar.image(URL_LOGO, use_container_width=True)


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
    response = requests.get(
        APPS_SCRIPT_URL, params={"action": "login", "code": code}
    )
    return response.json()
  except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    return None


def logout_user(code):
  try:
    requests.get(APPS_SCRIPT_URL, params={"action": "logout", "code": code})
  except Exception as e:
    pass


def update_sheet(id_ext, statut, utilisateur, date):
  try:
    params = {
        "action": "update",
        "id": id_ext,
        "statut": statut,
        "utilisateur": utilisateur,
        "date": date,
    }
    requests.get(APPS_SCRIPT_URL, params=params)
  except Exception as e:
    st.error(f"Erreur lors de la mise à jour : {e}")


def update_batch(quantite, utilisateur, date):
  try:
    params = {
        "action": "updateBatch",
        "quantite": quantite,
        "utilisateur": utilisateur,
        "date": date,
    }
    response = requests.get(APPS_SCRIPT_URL, params=params)
    return response.json()
  except Exception as e:
    st.error(f"Erreur lors de la validation du lot : {e}")
    return None


# --- GESTION DES ÉTATS GLOBAUX ---
if "user" not in st.session_state:
  st.session_state.user = None
if "last_activity" not in st.session_state:
  st.session_state.last_activity = datetime.now()

# --- VÉRIFICATION DE L'INACTIVITÉ (5 minutes) ---
INACTIVITY_LIMIT = timedelta(minutes=5)
if st.session_state.user is not None:
  if datetime.now() - st.session_state.last_activity > INACTIVITY_LIMIT:
    code_actuel = str(st.session_state.user.get("Code"))
    logout_user(code_actuel)
    st.session_state.user = None
    st.warning(
        "⏳ Session expirée suite à 5 minutes d'inactivité. Veuillez vous"
        " reconnecter."
    )
    st.rerun()
  else:
    st.session_state.last_activity = datetime.now()


# --- AUTHENTIFICATION ---
if st.session_state.user is None:
  st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQgi9peMxjPgEpbUU1SHhUBqaJa_GjKOId_5oPXARaqJw&s=10")
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
          st.session_state.last_activity = datetime.now()
          st.rerun()
        elif res.get("status") == "already_connected":
          st.error(
              "⚠️ Ce compte est déjà connecté sur un autre appareil ou une autre"
              " fenêtre !"
          )
        else:
          st.error("Code d'accès incorrect.")
      else:
        st.error("Erreur de communication avec le serveur.")

# --- INTERFACE SELON LE RÔLE ---
else:
  user = st.session_state.user
  st.sidebar.write(f"👤 **{user.get('Nom')}**")
  st.sidebar.write(f"🔑 Rôle : *{user.get('Role')}*")

  if st.sidebar.button("Se déconnecter"):
    logout_user(str(user.get("Code")))
    st.session_state.user = None
    st.rerun()

  df_ext, _ = get_data()

  # FORMATEUR
  if str(user.get("Role")).strip().lower() == "formateur":
    st.title("🧯 Formateur")
    st.write(
        "Scannez le QR code de l'extincteur."
    )

    id_scanne = qrcode_scanner(key="scanner_formateur")

    if id_scanne:
      st.info(f"🔍 QR Code détecté : **{id_scanne}**")
      mask = (
          df_ext["ID_Extincteur"].astype(str).str.strip().str.lower()
          == str(id_scanne).strip().lower()
      )

      if mask.any():
        statut_actuel = df_ext.loc[mask, "Statut"].values[0]
        if statut_actuel == "Plein":
          nouveau_statut = "En formation"
        elif statut_actuel == "En formation":
          nouveau_statut = "Vide"
        else:
          nouveau_statut = None

        if nouveau_statut:
          date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          update_sheet(
              id_scanne, nouveau_statut, user.get("Nom"), date_du_jour
          )
          st.success(
              f"✅ Extincteur **{id_scanne}** mis à jour : **{nouveau_statut}**"
          )
          if nouveau_statut == "Vide":
            st.warning("📩 Un e-mail d'alerte a été envoyé au gestionnaire.")
        else:
          st.warning(f"⚠️ Cet extincteur est déjà au statut '{statut_actuel}'.")
      else:
        st.error(f"❌ L'ID '{id_scanne}' est introuvable.")

  # PRESTATAIRE
  elif str(user.get("Role")).strip().lower() == "prestataire":
    st.image("https://thumbs.dreamstime.com/b/extincteur-avec-rendu-d-camion-isol%C3%A9-sur-fond-blanc-272191597.jpg")
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
        date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        res_batch = update_batch(
            quantite_a_prendre, user.get("Nom"), date_du_jour
        )
        if res_batch and res_batch.get("status") == "success":
          st.success(
              f"🚀 Départ validé pour {res_batch.get('count')} extincteur(s)."
              " Un e-mail de suivi a été envoyé au gestionnaire."
          )
          st.rerun()

    else:
      st.write(
          "Scannez individuellement chaque extincteur de retour pour le"
          " basculer en **Plein**."
      )
      id_scanne_retour = qrcode_scanner(key="scanner_prestataire_retour")

      if id_scanne_retour:
        st.info(f"🔍 QR Code détecté : **{id_scanne_retour}**")
        mask = (
            df_ext["ID_Extincteur"].astype(str).str.strip().str.lower()
            == str(id_scanne_retour).strip().lower()
        )

        if mask.any():
          statut_actuel = df_ext.loc[mask, "Statut"].values[0]
          if statut_actuel in ["En rechargement", "Vide"]:
            date_du_jour = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_sheet(
                id_scanne_retour, "Plein", user.get("Nom"), date_du_jour
            )
            st.success(
                f"✅ Extincteur **{id_scanne_retour}** de retour et basculé en"
                " **Plein** !"
            )
          else:
            st.warning(f"⚠️ Cet extincteur est déjà au statut : {statut_actuel}")
        else:
          st.error("❌ ID introuvable.")

 # --- AJOUT DU RAPPEL ET DU BOUTON DE DÉCONNEXION EN BAS DE TOUTES LES PAGES ---
  st.markdown("---")
  st.markdown(
      '<div class="footer-deconnexion">⚠️ Une fois fini de scanner les'
      " extincteurs, pensez à vous déconnecter !</div>",
      unsafe_allow_html=True,
  )

  if st.button("🔒 Se déconnecter maintenant"):
    logout_user(str(user.get("Code")))
    st.session_state.user = None
    st.rerun()
