#!/usr/bin/env python3

# stdlib
import argparse
import configparser
import os
import sys

# 3rd party
import openai

# Internal
from .tui import AiChatApp

config = configparser.ConfigParser()
debugFlag = False
giteaHost = None
giteaKey = None


# Main logic
def main():
    global debugFlag, config

    parser = argparse.ArgumentParser(
        prog="geris",
        description="Gitea issue management with a sprinkling of Eris.",
        epilog="Fnord!",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="Specify the config file to use.",
        default=f"{os.getenv('HOME')}/.gerisrc",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show debugging window and log tool usage",
    )
    parser.add_argument(
        "-g",
        "--gitea-profile",
        type=str,
        help="Specify the gitea profile to use.",
        default="default",
    )
    parser.add_argument(
        "-o",
        "--openai-profile",
        type=str,
        help="Specify the openai profile to use.",
        default="default",
    )

    args = parser.parse_args()
    if not os.path.isfile(args.config):
        print(f"\033[1;31mERROR\033[0m: {args.config} does not exist.")
        sys.exit(1)
    config.read(args.config)

    if args.debug:
        debugFlag = True

    openaiConfig = config[f"openai:{args.openai_profile}"]
    openai.api_base = openaiConfig.get("uri", "UNSET")
    openai.api_key = openaiConfig.get("token", "UNSET")

    app = AiChatApp()
    app.setup_app(
        config[f"gitea:{args.gitea_profile}"].get("uri", "UNSET"),
        config[f"gitea:{args.gitea_profile}"].get("token", "UNSET"),
        config[f"openai:{args.openai_profile}"].get("model", "UNSET"),
        args.debug,
    )
    app.run()


if __name__ == "__main__":
    main()
