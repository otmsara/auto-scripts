"""
Unfollow ceux que tu as suivis avec insta_follow.py et qui ne te suivent pas en retour.

Utilisation :
    python insta_unfollow.py --dry-run     # affiche ce qui serait unfollow, sans rien faire
    python insta_unfollow.py               # unfollow pour de vrai

Lance-le une fois par jour max.
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import date, datetime, timedelta
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
MAX_UNFOLLOWS_PER_DAY = 25     # reste bas
MIN_DAYS_BEFORE_UNFOLLOW = 3   # laisse le temps aux gens de te suivre en retour
DELAY_RANGE = (45, 120)        # secondes entre deux unfollows
WHITELIST = {
    # usernames à ne JAMAIS unfollow, ex: "kawtarbamo"
}

SESSION_FILE = Path("session.json")
STATE_FILE = Path("state.json")  # même fichier que le script de follow
# ------------------------------------------------------


def load_state():
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
    else:
        state = {"followed": {}, "daily": {}}
    state.setdefault("unfollowed", {})
    state.setdefault("daily_unfollow", {})
    return state


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def login():
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")
    if not username or not password:
        sys.exit("Définis IG_USERNAME et IG_PASSWORD dans le fichier .env.")

    cl = Client()
    cl.delay_range = [2, 5]
    if SESSION_FILE.exists():
        cl.load_settings(SESSION_FILE)
    cl.login(username, password)
    cl.dump_settings(SESSION_FILE)
    return cl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="n'unfollow personne, affiche seulement")
    args = parser.parse_args()

    state = load_state()
    today = date.today().isoformat()
    done_today = state["daily_unfollow"].get(today, 0)

    if done_today >= MAX_UNFOLLOWS_PER_DAY and not args.dry_run:
        print(f"Limite du jour atteinte ({done_today}). Reviens demain.")
        return

    cl = login()
    my_id = cl.user_id

    print("Récupération de ta liste de followers...")
    my_followers = {str(pk) for pk in cl.user_followers(my_id).keys()}
    print(f"{len(my_followers)} followers.")

    cutoff = datetime.now().date() - timedelta(days=MIN_DAYS_BEFORE_UNFOLLOW)

    # Candidats : suivis par le script, ne te suivent pas, assez anciens, pas déjà unfollow
    candidates = []
    for uid, info in state["followed"].items():
        if uid in state["unfollowed"] or uid in my_followers:
            continue
        if info["username"] in WHITELIST:
            continue
        if date.fromisoformat(info["date"]) > cutoff:
            continue
        candidates.append((uid, info))

    # Les plus anciens d'abord
    candidates.sort(key=lambda x: x[1]["date"])
    print(f"{len(candidates)} comptes à unfollow (ne te suivent pas en retour).")

    if args.dry_run:
        for uid, info in candidates[:MAX_UNFOLLOWS_PER_DAY]:
            print(f"  [dry-run] unfollow @{info['username']} (suivi le {info['date']})")
        return

    for uid, info in candidates:
        if done_today >= MAX_UNFOLLOWS_PER_DAY:
            break

        try:
            cl.user_unfollow(int(uid))
        except (PleaseWaitFewMinutes, RateLimitError, ChallengeRequired):
            print("Instagram demande de ralentir / vérifier le compte. Arrêt.")
            save_state(state)
            return
        except (ClientError, LoginRequired) as e:
            print(f"Erreur sur @{info['username']} : {e}")
            continue

        state["unfollowed"][uid] = {"username": info["username"], "date": today}
        done_today += 1
        state["daily_unfollow"][today] = done_today
        save_state(state)
        print(f"[{done_today}/{MAX_UNFOLLOWS_PER_DAY}] unfollow @{info['username']}")

        time.sleep(random.uniform(*DELAY_RANGE))

    print("Terminé.")


if __name__ == "__main__":
    main()
