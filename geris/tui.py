# Stdlib
import json
import os
import sys
import time
import traceback

# 3rd party
import openai
from rich.markdown import Markdown
from rich.panel import Panel
from rich.pretty import Pretty
from textual import on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.widgets import Footer, Header, Input
from textual.widgets import Sparkline, Static, RichLog

# Internal
from .gitea import GiteaTools


class Geris(App):

    theme = "catppuccin-mocha"
    BINDINGS = [("ctrl+q", "quit", "Quit")]
    CSS = """
    VerticalScroll       { background: #282a36; color: #f8f8f2; height: 3fr; background: $surface; }
    VerticalScroll:focus { background: #282a36; color: #f8f8f2; height: 3fr; background: $surface; }
    VerticalScroll:blur  { background: #282a36; color: #f8f8f2; height: 3fr; background: $surface; }
    Markdown             { background: #282a36; color: #f8f8f2; text-align: center; background: $surface; }
    Markdown:focus       { background: #282a36; color: #f8f8f2; text-align: center; background: $surface; }
    Markdown:blur        { background: #282a36; color: #f8f8f2; text-align: center; background: $surface; }
    RichLog              { background: #1a1a1a; color: #f8f8f2; height: 1fr; }
    RichLog:focus        { background: #1a1a1a; color: #f8f8f2; height: 1fr; }
    RichLog:blur         { background: #1a1a1a; color: #f8f8f2; height: 1fr; }
    Input                { background: #282a36; color: #f8f8f2; }
    Input:focus          { background: #282a36; color: #f8f8f2; }
    Input:blur           { background: #282a36; color: #f8f8f2; }
    Static.status {
      width: 1fr; color: #f8f8f2; content-align: center middle; border-top: solid #bd93f9; padding-top: 1;
      background: $surface;
    }
    Vertical { width: auto; height: auto; background: $surface; }
    Horizontal { width: 1fr; height: auto; background: $surface; }
    Sparkline { width: 1fr; background: $surface; }
    #spark > .sparkline--max-color { color: $accent; }
    #spark > .sparkline--min-color { color: $accent 30%; }
    """

    def setup_app(self, host, token, model, debug=False) -> None:
        self._tools = GiteaTools(host, token)
        self._llm_model = model
        self._debugFlag = debug
        self._reqCount = 0

    def compose(self) -> ComposeResult:
        self._mdown = Static()
        self._body = VerticalScroll(
            self._mdown, can_focus=False, can_focus_children=False
        )
        self._input = Input(placeholder="> Let's talk about your issues", id="input")
        yield Header(icon="⛓️")
        yield self._body
        if self._debugFlag:
            yield RichLog()
        with Vertical(id="status-container"):
            with Horizontal(id="status-metrics"):
                yield Static(
                    "[green]Open Issues[/green]: 0",
                    classes="status",
                    id="status-issues",
                )
                yield Static(
                    "[yellow]Open Milestones[/yellow]: 0",
                    classes="status",
                    id="status-milestones",
                )
                yield Static(
                    "[cyan]Open PRs[/cyan]: 0", classes="status", id="status-prs"
                )
            yield Sparkline(
                [], summary_function=max, id="status-sparkline", classes="spark"
            )
        yield self._input
        yield Footer()

    def update_status(self) -> None:
        issues_w = self.query_one("#status-issues", Static)
        milestones_w = self.query_one("#status-milestones", Static)
        prs_w = self.query_one("#status-prs", Static)
        data = self._tools.dashboard()
        issues_w.update(f"[green]Open Issues[/green]: {len(data['issues'])}")
        milestones_w.update(
            f"[yellow]Open Milestones[/yellow]: {len(data['milestones'])}"
        )
        prs_w.update(f"[cyan]Open PRs[/cyan]: {len(data['prs'])}")

    def set_heatmap_data(self, year: int) -> None:
        """Sets the data based on the current data."""
        datums = [
            n["contributions"]
            for n in self._tools.get_heatmap_data(self._tools.default_user())
        ]

        for _ in range(365 - len(datums)):
            datums.insert(0, 0)

        self.query_one(Sparkline).data = datums

    def on_mount(self) -> None:
        self.title = "Geris - Gitea Issue Management....hopefully"
        self.set_heatmap_data(2025)
        self.query_one("#input", Input).focus()
        self.update_status()

    @on(Input.Submitted)
    def show_output(self, event: Input.Submitted) -> None:
        self._messages = [
            {
                "role": "system",
                "content": os.getenv(
                    "OPENAI_DEFAULT_PROMPT",
                    """You are a task automation assistant specialized in project repository management. Your primary directives are:
1. Any personal possessive references to 'me' or 'my' by the user will be assumed to mean the 'deafault user'
2. Always assume actions apply to the `default_user` unless otherwise specified, assume the `default_user` as the owner for any repositories if left unspecified.
3. Categorization First. Always prefer labels/tags when available. If labels are missing but logical for the context (e.g., `Priority/High`, `Kind/Bug`), create them proactively. Mandatory label for new issues: `Agent/Review` (verify existence; create if absent).
4. Resource Descriptions. When descriptions are unspecified, use your best judgement based on the title
5. Formatting Rules. Markdown required for all responses. Always prefer to use numbered tables to display data.
6. Issue Creation Protocol. Assign to the default user (retrieved via `default_user` tool unless overridden).
7. Tool Usage. Verify label existence *before* issue creation via `list_labels`.
8. Tool Calls. Use tools only when necessary, and always prefer to use the `default_user` tool for any user-specific actions.
9. Use of unicode symbols or emojis is allowed, but should be used sparingly and only when it adds value to the response.""",
                ),
            },
        ]
        self._messages.append({"role": "user", "content": event.value})
        self._prompt = event.value
        self._chat_flag = False
        self._process_chat()
        self.update_status()

    def _debug(self, msg, pretty=False) -> None:
        if self._debugFlag:
            if pretty:
                self.query_one(RichLog).write(Panel(Pretty(msg)))
            else:
                self.query_one(RichLog).write(msg)
            with open("_process_chat.debug", "a+") as fp:
                fp.write(str(msg) + "\n")

    def _process_chat(self) -> None:
        self._reqCount += 1
        try:
            # Always make the API call with current messages
            response = openai.ChatCompletion.create(
                model=self._llm_model,
                messages=self._messages,
                tools=self._tools.tools(),
                tool_choice="auto",
            )

            # Debug output
            if self._debugFlag:
                with open(f"choices-{self._reqCount:05d}.debug", "w+") as fp:
                    fp.write(json.dumps(response["choices"], indent=2))

            message = response["choices"][0]["message"]

            if "tool_calls" in message:
                # Add the assistant's tool-call message to history ONCE
                if not any(
                    msg.get("tool_calls") == message["tool_calls"]
                    for msg in self._messages
                ):
                    self._messages.append(
                        {k: v for k, v in message.items() if k != "reasoning_content"}
                    )

                # Process ALL tool calls first
                tool_responses = []
                for call in message["tool_calls"]:
                    fn = call["function"]["name"]
                    args = call["function"]["arguments"]

                    self._debug(
                        f"{time.strftime('%H:%M:%S')} :: Tool: {fn} - Args: {args}"
                    )

                    try:
                        result = eval(f"self._tools.{fn}(**{args})")
                        self._debug(result, True)
                    except Exception as e:
                        result = {"error": f"Tool {fn} raised an error: {str(e)}"}
                        self._debug(result, True)

                    tool_responses.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, default=str),
                        }
                    )

                # Add ALL tool responses at once
                self._messages.extend(tool_responses)

                # Debug and recurse
                if self._debugFlag:
                    with open(f"req-{self._reqCount:05d}.json", "w+") as fp:
                        fp.write(json.dumps(self._messages, indent=2))

                self._process_chat()
            else:
                # Final response handling
                if self._debugFlag:
                    with open(f"req-{self._reqCount:05d}.json", "w+") as fp:
                        fp.write(json.dumps(self._messages, indent=2))

                self._mdown.update(
                    Markdown(
                        "\n".join(
                            (
                                "# Prompt",
                                f"- `Input`: **{self._prompt}**",
                                "# Response",
                                message["content"],
                            )
                        )
                    )
                )
        except Exception as e:
            data = [
                "# `ERROR`: **Failed to get assistant response**",
                f"- `Message`: **{str(e)}**",
                f"- `Request Debug File`: **req-{self._reqCount:05d}.json**",
                f"- `Choices Debug File`: **choices-{self._reqCount:05d}.json**",
                "# Message Stack",
            ]
            for n in self._messages:
                data.append("---")
                data.append(f"- `Role`: **{n.get('role', None)}**")
                data.append(f"  - `Content`: {n.get('content', '')}")
                if n.get("tool_call_id", False):
                    data.append(f"  - `ToolCall-ID`: **{n.get('tool_call_id')}**")
                for d in n.get("tool_calls", []):
                    data.append(
                        f"  - `Index`: **{d.get('index', None)}** -- `ID`: **{d.get('id', None)}**"
                    )
                    data.append(f"    - `Type`: **{d.get('type', None)}**")
                    data.append(f"    - `Function`: **{d.get('function', None)}**")
            # [data.append("- " + str(n)) for n in self._messages]
            self._mdown.update(Markdown("\n".join(data)))
            with open("error._process_chat.debug", "a+") as fp:
                for msg in self._messages:
                    fp.write(f"{json.dumps(msg, indent=2)}\n")
                    fp.write(("-" * 80) + "\n" + str(e) + "\n")
                    tb = traceback.extract_tb(sys.exc_info()[2])
                    for frame in tb:
                        fp.write(
                            f"File {frame.filename}, line {frame.lineno}, in {frame.name}\n"
                        )
                    fp.write(f"{type(e).__name__}: {e}")

        self._input.clear()
