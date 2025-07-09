#!/usr/bin/env python3

# stdlib
import os
import json
import time
import inspect
import argparse
import configparser
from typing import List, get_type_hints
from typing import get_origin, get_args

# 3rd party
import openai
import giteapy
from rich.panel import Panel
from rich.pretty import Pretty
from rich.markdown import Markdown
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.widgets import Input, Static, RichLog
from textual.containers import VerticalScroll


config = configparser.ConfigParser()
debugFlag = False
giteaHost = None
giteaKey = None


def func2tool(p):
    retv = {
        "type": "function",
        "function": {
            "parameters": {"type": "object", "properties": {}, "required": []}
        },
    }
    data = [
        [tuple(tkn.split(":")) for tkn in ln.split("; ")]
        for ln in p.__doc__.split("\n")
    ]
    sig = inspect.signature(p)

    # type helper
    def typeof(n):
        if n is str or n == "str":
            return {"type": "string"}
        elif n is int or n == "int":
            return {"type": "integer"}
        elif n is float or n == "float":
            return {"type": "number"}
        elif n is bool or n == "bool":
            return {"type": "boolean"}
        elif get_origin(n) is list:
            _retv = {"type": "array", "items": typeof(get_args(n)[0])}
            return _retv
        else:
            return {"type": "unknown"}

    # parse function name and arg types out of inspect data
    retv["function"]["name"] = p.__name__
    for k, v in sig.parameters.items():
        val = typeof(v.annotation)
        retv["function"]["parameters"]["properties"][k] = val

    # now parse the docstring to fill in extra details
    for datum in data:
        key = datum[0][0]
        keys = retv["function"]["parameters"]["properties"].keys()
        for item in datum:
            if item[0] == "description" and key not in keys:
                retv["function"][item[0]] = item[1]
            elif item[0] == "required" and key not in keys:
                retv["function"]["parameters"]["required"] = item[1].split(",")
            elif item[0] in keys:
                retv["function"]["parameters"]["properties"][item[0]]["description"] = (
                    item[1]
                )
            elif item[0] == "enum" and key in keys:
                retv["function"]["parameters"]["properties"][key][item[0]] = item[
                    1
                ].split(",")
            elif item[0] == "default" and key in keys:
                retv["function"]["parameters"]["properties"][key][item[0]] = item[1]

    return retv


class GiteaTools:
    """ """

    def __init__(self, host, token):
        _config = giteapy.Configuration()
        _config.host = f"{host}/api/v1"
        _config.api_key["access_token"] = token
        _client = giteapy.ApiClient(_config)

        self._funcMap = []

        self._issue = giteapy.IssueApi(_client)
        self._admin = giteapy.AdminApi(_client)
        self._user = giteapy.UserApi(_client)
        self._repo = giteapy.RepositoryApi(_client)

        self._tools = (
            # user and org
            self.default_user,
            self.list_users,
            self.list_orgs,
            # labels
            self.list_labels,
            self.get_label,
            self.get_labels,
            self.add_label,
            self.remove_label,
            self.create_label,
            self.delete_label,
            # milestones
            self.list_milestones,
            self.get_milestone,
            self.create_milestone,
            self.delete_milestone,
            # issues
            self.list_issues,
            self.get_issue,
            self.close_issue,
            self.close_issues,
            self.create_issue,
            # comments
            # self.list_comments, # TODO
            # self.create_comment, # TODO
        )

        for n in self._tools:
            self._funcMap.append(func2tool(n))

    def tools(self) -> List[dict]:
        return self._funcMap

    def default_user(self) -> dict:
        """description:Return the current user"""
        retv = self._user.user_get_current()
        return retv.to_dict()

    def list_users(self) -> List[str]:
        """description:Return a list of all users"""
        return [itm.to_dict() for itm in self._admin.admin_get_all_users()]

    def list_orgs(self) -> List[str]:
        """description:Return a list of all orgs"""
        return [itm.to_dict() for itm in self._admin.admin_get_all_orgs()]

    def list_labels(self, owner: str, repo: str) -> List[str]:
        """description:list issue labels for a repository
        owner:Owner of the repository
        repo:Name of the repository
        required:owner,repo"""
        data = self._issue.issue_list_labels(owner=owner, repo=repo)
        return [json.dumps(itm.to_dict(), default=str) for itm in data]

    def get_label(self, owner: str, repo: str, id: int) -> dict:
        """description:Get a single label from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the label to get
        required:owner,repo,id"""
        return self._issue.issue_get_label(owner=owner, repo=repo, id=id).to_dict()

    def get_labels(self, owner: str, repo: str, index: int) -> List[dict]:
        """description:Get all labels on an issue
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to get the labels from
        required:owner,repo,index"""
        return [
            itm.to_dict()
            for itm in self._issue.issue_get_labels(owner=owner, repo=repo, index=index)
        ]

    def add_label(
        self, owner: str, repo: str, index: int, labels: List[int]
    ) -> List[dict]:
        """description:Add one or more labels to an issue
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to add label(s) to
        labels:List of label IDs to add to the issue
        required:owner,repo,index,labels"""
        bodyKwargs = giteapy.IssueLabelsOption(**{"labels": labels})
        return [
            itm.to_dict()
            for itm in self._issue.issue_add_label(
                owner=owner, repo=repo, index=index, body=bodyKwargs
            )
        ]

    def remove_label(self, owner: str, repo: str, index: int, id: int) -> dict:
        """description:Remove a label from an issue
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to add label(s) to
        id:ID of the label to remove from the issue
        required:owner,repo,index,label"""
        self._issue.issue_remove_label(owner=owner, repo=repo, index=index, id=id)
        return {"result": "success"}

    def create_label(
        self,
        owner: str,
        repo: str,
        color: str = None,
        name: str = None,
        descr: str = None,
    ) -> dict:
        """desscription:Create a label on a repository
        required:owner,repo,color,name"""
        body = giteapy.CreateLabelOption(
            **{
                k: v
                for k, v in {"color": color, "name": name, "description": descr}.items()
                if v is not None
            }
        )
        return self._issue.issue_create_label(
            owner=owner, repo=repo, body=body
        ).to_dict()

    def delete_label(self, owner: str, repo: str, id: int) -> None:
        """description:Delete a label from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the label to delete
        required:owner,repo,id"""
        return self._issue.issue_delete_label(owner=owner, repo=repo, id=id)

    def list_milestones(self, owner: str, repo: str, state: str = "open") -> List[str]:
        """description:List milestones for a repository
        owner:Owner of the repository
        repo:Name of the repository
        state:State of the milestones; enum:open,closed,all; default:open
        required:owner,repo"""
        return [
            json.dumps(itm.to_dict())
            for itm in self._issue.issue_get_milestones_list(
                owner=owner, repo=repo, state=state
            )
        ]

    def get_milestone(self, owner: str, repo: str, id: int) -> dict:
        """description:Get a single milestone from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the milestone to get
        required:owner,repo,id"""
        return self._issue.issue_get_milestone(owner=owner, repo=repo, id=id).to_dict()

    def create_milestone(
        self, owner: str, repo: str, descr: str, due_on: str, title: str
    ) -> dict:
        """description:Create a milestone on a repository
        owner:Owner of the repository
        repo:Name of the repository
        descr:The description of the milestone
        due_on:Time and date in datetime object format
        title:Title of the milestone
        required:owner,repo,title"""
        body = giteapy.CreateMilestoneOption(
            description=descr, due_on=due_on, title=title
        )
        return self._issue.issue_create_milestone(
            owner=owner, repo=repo, body=body
        ).to_dict()

    def delete_milestone(self, owner: str, repo: str, id: int) -> dict:
        """description:Delete a milestone from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the milestone to delete
        required:owner,repo,id"""
        self._issue.issue_delete_milestone(owner=owner, repo=repo, id=id)
        return {"result": "success"}

    def list_issues(
        self,
        owner: str,
        repo: str,
        labels: str = None,
        page: int = 0,
        q: str = None,
        state: str = "open",
    ) -> List[dict]:
        """description:list open and/or closed issues on a repository
        owner:Owner of the repository
        repo:Name of the repository
        state:State of the issue to create; enum:open,closed,all; default:open
        labels:comma separated list of labels to filter by
        page:page number of requested issues; default:0;
        q:search string
        required:owner,repo"""
        kwargs = {
            k: v
            for k, v in {
                "owner": owner,
                "repo": repo,
                "labels": labels,
                "page": page,
                "q": q,
                "state": state,
            }.items()
            if v is not None
        }
        return [
            json.loads(json.dumps(issue.to_dict(), default=str))
            for issue in self._issue.issue_list_issues(**kwargs)
        ]

    def get_issue(self, owner: str, repo: str, index: int) -> dict:
        """description:Get a single issue from a repository
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to get
        required:owner,repo,index"""
        return self._issue.issue_get_issue(
            owner=owner, repo=repo, index=index
        ).to_dict()

    def close_issue(self, owner: str, repo: str, index: int) -> dict:
        """description:Close a given issue
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to close
        required:owner,repo,index"""
        body = giteapy.EditIssueOption(state="closed")
        return self._issue.issue_edit_issue(
            owner=owner, repo=repo, index=index, body=body
        ).to_dict()

    def close_issues(self, owner: str, repo: str, indexes: List[int]) -> List[dict]:
        """description:Close multiple issues
        owner:Owner of the repository
        repo:Name of the repository
        indexes:Index of the issue to close
        required:owner,repo,indexes"""
        retv = []
        for n in indexes:
            retv.append(self.close_issue(owner, repo, n))
        return retv

    def create_issue(
        self,
        owner: str,
        repo: str,
        assignee: str = None,
        assignees: list[str] = None,
        body: str = None,
        closed: bool = False,
        due_date: str = None,
        labels: list[int] = None,
        milestone: int = None,
        title: str = None,
    ) -> dict:
        """description:Create an issue on a repository
        owner:Owner of the repository
        repo:Name of the repository
        assignee:Name of the assigned user
        assignees:Any additional assigned users
        body:Description of the issue and success criteria
        closed:The default of False, will mark the issue as open; default:False;
        due_date:A datetime formatted string
        labels:A list of all labels to apply to this issue
        milestone:Milestone this issue belongs to
        title:The title, a one-line description of the issue
        required:owner,repo,title"""
        bodyKwargs = {
            k: v
            for k, v in {
                "assignee": assignee,
                "assignees": assignees,
                "body": body,
                "closed": closed,
                "due_date": due_date,
                "labels": labels,
                "milestone": milestone,
                "title": title,
            }.items()
            if v is not None
        }

        body = giteapy.CreateIssueOption(**bodyKwargs)
        return self._issue.issue_create_issue(
            owner=owner, repo=repo, body=body
        ).to_dict()


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
    RichLog                  { background: #1a1a1a; color: #f8f8f2; height: 2fr; }
    RichLog:focus            { background: #1a1a1a; color: #f8f8f2; height: 2fr; }
    RichLog:blur             { background: #1a1a1a; color: #f8f8f2; height: 2fr; }
    Input                { background: #282a36; color: #f8f8f2; }
    Input:focus          { background: #282a36; color: #f8f8f2; }
    Input:blur           { background: #282a36; color: #f8f8f2; }
    """

    def setup_app(self, host, token, model) -> None:
        self._tools = GiteaTools(host, token)
        self._llm_model = model

    def compose(self) -> ComposeResult:
        self._mdown = Static()
        self._body = VerticalScroll(
            self._mdown, can_focus=False, can_focus_children=False
        )
        self._input = Input(placeholder="> Let's talk about your issues", id="input")
        yield Header()
        yield self._body
        if debugFlag:
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
        if debugFlag:
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

        self._input.clear()


# Main logic
def main():
    global debugFlag, config

    if __name__ == "__main__":
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
            default="~/.gerisrc",
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
        )
        app.run()


if __name__ == "__main__":
    main()
