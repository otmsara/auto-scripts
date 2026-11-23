"""
Script de follow ciblé sur Instagram (instagrapi).
Suit des followers d'influenceurs makeup/fashion, avec des limites basses
pour réduire le risque de blocage.

Installation :
    pip install -r requirements.txt
    copy .env.example .env
    # Renseigne IG_USERNAME et IG_PASSWORD dans .env

Utilisation :
    python insta_follow.py

Lance-le une fois par jour max, pas en boucle.
"""

import json
import os
import random
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    ClientError,
    LoginRequired,
    PleaseWaitFewMinutes,
    RateLimitError,
)

load_dotenv(Path(__file__).with_name(".env"))

# ----------------------- CONFIG -----------------------
INFLUENCERS = [
    "bilal.fraiha",
    # ajoute-en d'autres ici, une par ligne
]

MAX_FOLLOWS_PER_DAY = 25          # reste bas, surtout sur un compte récent
FOLLOWERS_TO_FETCH = 100          # followers récupérés par influenceur
DELAY_RANGE = (45, 120)           # secondes entre deux follows
SKIP_PRIVATE = True               # ignorer les comptes privés

SESSION_FILE = Path("session.json")
STATE_FILE = Path("state.json")   # historique pour ne jamais refollow
# ------------------------------------------------------


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"followed": {}, "daily": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def login():
    cl = Client()
    cl.delay_range = [2, 5]  # petits délais aléatoires entre requêtes API
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")
    if not username or not password:
        sys.exit("Définis IG_USERNAME et IG_PASSWORD dans le fichier .env.")

    if SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 0:
        try:
            cl.load_settings(SESSION_FILE)
        except (json.JSONDecodeError, OSError) as e:
            # A truncated or empty session cannot be reused. Login below will
            # create a fresh session file after authentication succeeds.
            print(f"Session invalide ({e}). Nouvelle connexion...")
    cl.login(username, password)
    cl.dump_settings(SESSION_FILE)
    return cl


def main():
    state = load_state()
    today = date.today().isoformat()
    done_today = state["daily"].get(today, 0)

    if done_today >= MAX_FOLLOWS_PER_DAY:
        print(f"Limite du jour atteinte ({done_today}). Reviens demain.")
        return

    cl = login()
    my_id = cl.user_id
    already_following = set(cl.user_following(my_id).keys())
    print(f"Connecté. {done_today}/{MAX_FOLLOWS_PER_DAY} follows déjà faits aujourd'hui.")

    random.shuffle(INFLUENCERS)

    for influencer in INFLUENCERS:
        if done_today >= MAX_FOLLOWS_PER_DAY:
            break

        try:
            infl_id = cl.user_id_from_username(influencer)
            followers = cl.user_followers(infl_id, amount=FOLLOWERS_TO_FETCH)
        except (ClientError, LoginRequired) as e:
            print(f"Impossible de récupérer @{influencer} : {e}")
            continue

        candidates = list(followers.values())
        random.shuffle(candidates)
        print(f"@{influencer} : {len(candidates)} followers récupérés")

        for user in candidates:
            if done_today >= MAX_FOLLOWS_PER_DAY:
                break
            uid = str(user.pk)

            if uid in state["followed"] or uid in already_following:
                continue
            if SKIP_PRIVATE and user.is_private:
                continue

            try:
                cl.user_follow(user.pk)
            except (PleaseWaitFewMinutes, RateLimitError, ChallengeRequired):
                print("Instagram demande de ralentir / vérifier le compte. Arrêt.")
                save_state(state)
                return
            except ClientError as e:
                print(f"Erreur sur @{user.username} : {e}")
                continue

            state["followed"][uid] = {"username": user.username, "date": today}
            done_today += 1
            state["daily"][today] = done_today
            save_state(state)
            print(f"[{done_today}/{MAX_FOLLOWS_PER_DAY}] follow @{user.username}")

            time.sleep(random.uniform(*DELAY_RANGE))

    print("Terminé.")


if __name__ == "__main__":
    main()
