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
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, RichLog, Static

# Internal
from .gitea import GiteaTools


class AiChatApp(App):

    theme = "dracula"
    BINDINGS = [("ctrl+q", "quit", "Quit")]
    CSS = """
    VerticalScroll       { background: #282a36; color: #f8f8f2; height: 4fr; }
    VerticalScroll:focus { background: #282a36; color: #f8f8f2; height: 4fr; }
    VerticalScroll:blur  { background: #282a36; color: #f8f8f2; height: 4fr; }
    Markdown             { background: #282a36; color: #f8f8f2; text-align: center; }
    Markdown:focus       { background: #282a36; color: #f8f8f2; text-align: center; }
    Markdown:blur        { background: #282a36; color: #f8f8f2; text-align: center; }
    RichLog              { background: #1a1a1a; color: #f8f8f2; height: 2fr; }
    RichLog:focus        { background: #1a1a1a; color: #f8f8f2; height: 2fr; }
    RichLog:blur         { background: #1a1a1a; color: #f8f8f2; height: 2fr; }
    Input                { background: #282a36; color: #f8f8f2; }
    Input:focus          { background: #282a36; color: #f8f8f2; }
    Input:blur           { background: #282a36; color: #f8f8f2; }
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
        yield Header()
        yield self._body
        if self._debugFlag:
            yield RichLog()
        yield self._input
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Geris - Gitea Issue Management....hopefully"
        self.query_one("#input", Input).focus()

    @on(Input.Submitted)
    def show_output(self, event: Input.Submitted) -> None:
        self._messages = [
            {
                "role": "system",
                "content": os.getenv(
                    "OPENAI_DEFAULT_PROMPT",
                    """You are a task automation assistant specialized in project repository management. Your primary directives are:
1. Categorization First. Always prefer labels/tags when available. If labels are missing but logical for the context (e.g., `Priority/High`, `Kind/Bug`), create them proactively. Mandatory label for new issues: `Agent/Review` (verify existence; create if absent).
2. Resource Descriptions. When descriptions are unspecified, use your best judgement based on the title
3. Formatting Rules. Markdown required for all responses. For lists >3 items, always use numbered tables.
4. Issue Creation Protocol. Assign to the default user (retrieved via `default_user` tool unless overridden).
5. Tool Usage. Verify label existence *before* issue creation via `list_labels`.""",
                    # "You are a helpful assistant, who manages tasks on project repositories. You are hyper-aware of categorization, and prefer to use labels anytime they are available. If not asked to put a description in place on a resource, use your besst judgement. Respond in markdown formatted text, and prefer verbose tables with row number when listing similar content. For any issues you create, apply the labels 'Agent' and 'Review', creating them on the repo before-hand if they do not exist. When creating new issues, unless otherwise explicitly stated, assign to the default user. You have a tool to retrieve the default user",
                ),
            },
        ]
        self._messages.append({"role": "user", "content": event.value})
        self._prompt = event.value
        self._chat_flag = False
        self._process_chat()

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
