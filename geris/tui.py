# Stdlib
import os
import sys
import json
import time
import traceback

# 3rd party
import openai
from rich.panel import Panel
from rich.pretty import Pretty
from rich.markdown import Markdown
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.widgets import Input, Static, RichLog
from textual.containers import VerticalScroll

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
                    "You are a helpful assistant, who manages tasks on project repositories. Respond in markdown formatted text.",
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
            with open("debug._process_chat.dbg", "a+") as fp:
                fp.write(str(msg) + "\n")

    def _process_chat(self) -> None:
        try:
            if not self._chat_flag:
                response = openai.ChatCompletion.create(
                    model=self._llm_model,
                    messages=self._messages,
                    tools=self._tools.tools(),
                    tool_choice="auto",
                )
                self._chat_flag = True
            else:
                response = openai.ChatCompletion.create(
                    model=self._llm_model,
                    messages=self._messages,
                    tools=self._tools.tools(),
                    tool_choice="auto",
                )

            message = response["choices"][0]["message"]

            if "tool_calls" in message:
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
                        break

                    self._messages.append(
                        {k: v for k, v in message.items() if k != "reasoning_content"}
                    )
                    self._messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, default=str),
                        }
                    )
                    self._process_chat()
            else:
                self._mdown.update(
                    Markdown(
                        f"""## Prompt

**Input**: `{self._prompt}`

## Response
                
{message["content"]}"""
                    )
                )
        except Exception as e:
            self._mdown.update(
                Markdown(f"- ERROR: Failed to get assistant response: {str(e)}")
            )
            with open("debug._process_chat.err", "a+") as fp:
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
