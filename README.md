# Geris


**Geris** is a terminal-based application for managing Gitea repositories using the Gitea API and OpenAI's function-calling capabilities. It provides a conversational interface via a Textual UI, enabling users to query and manipulate repository issues, labels, milestones, and user data.

[![asciicast](https://asciinema.org/a/fPIIqQeAOqT0Rz2gOUMHupZMP.svg)](https://asciinema.org/a/fPIIqQeAOqT0Rz2gOUMHupZMP)

## Features

- Conversational UI for managing Gitea repositories
- OpenAI function calling integration for tool automation
- Textual UI with keyboard navigation and live feedback
- Support for user, organization, issue, label, and milestone operations
- Structured docstring parsing for function-to-tool conversion

## Requirements

- Python 3.9+
- Gitea instance with API access
- OpenAI API credentials with model access (e.g., GPT-4)
- Config file with valid API tokens (see below)

## Installation

To install from github:

```bash
python3 -m venv ~/.localpy && \
  source ~/.localpy/bin/activate && \
  pip3 install git+https://github.com/fuzzy/geris
```

To install locally:

```bash
git clone https://github.com/yourname/geris.git
cd geris
python3 -m venv ~/.localpy && \
  source ~/.localpy/bin/activate && \
  pip3 install -e .
```

This will install the geris CLI command.

## Configuration

Geris expects a configuration file (default: ~/.gerisrc) with OpenAI and Gitea profiles. Example structure:

```
[openai:default]
uri = https://api.openai.com/v1
token = YOUR_OPENAI_API_KEY
model = gpt-4

[gitea:default]
uri = https://gitea.example.com
token = YOUR_GITEA_TOKEN
```

## Usage

```
geris -c ~/.gerisrc

Command-Line Arguments
Flag	Description
-c, --config	Path to config file
-d, --debug	Enable debugging logs and UI panel
-g, --gitea-profile	Gitea profile section in config
-o, --openai-profile	OpenAI profile section in config
```

Development

Geris is structured around the GiteaTools class, which defines callable tools with structured docstrings. These are parsed by func2tool() to generate OpenAI-compatible tool definitions.

The UI is built using Textual and includes interactive panels for conversation input, response display, and optional debugging output.
License

This project is licensed under the MIT License.
