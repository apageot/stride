"""À lancer UNE fois sur ton ordi pour connecter Garmin.

    python3 scripts/connexion_garmin.py

Te demande ton email + mot de passe Garmin (et le code de double authentification si tu l'as),
puis affiche le contenu à coller dans le secret GitHub GARMIN_TOKENS_JSON.
Ton mot de passe n'est stocké nulle part.
"""
from getpass import getpass
from pathlib import Path

from garminconnect import Garmin

store = Path("~/.garminconnect").expanduser()
store.mkdir(parents=True, exist_ok=True)

email = input("Email Garmin : ").strip()
password = getpass("Mot de passe Garmin : ")
g = Garmin(email, password, prompt_mfa=lambda: input("Code reçu par mail/SMS : ").strip())
g.login(str(store))
g.client.dump(str(store))
print(f"\nConnecté en tant que {g.get_full_name()}.\n")
print("Copie TOUT le texte ci-dessous dans le secret GitHub GARMIN_TOKENS_JSON :\n")
print((store / "garmin_tokens.json").read_text())
