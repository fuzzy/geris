# Stdlib
import sys
import json
from typing import List

# 3rd party
import giteapy

# internal
from .utils import tool, func2tool


class GiteaTools:
    """ """

    def __init__(self, host, token):
        _config = giteapy.Configuration()
        _config.host = f"{host}/api/v1"
        _config.api_key["access_token"] = token
        _client = giteapy.ApiClient(_config)

        self._tools = []
        self._funcMap = []
        self._issue = giteapy.IssueApi(_client)
        self._admin = giteapy.AdminApi(_client)
        self._user = giteapy.UserApi(_client)
        self._repo = giteapy.RepositoryApi(_client)

        self._tool_scan()

    def _tool_scan(self):
        for k in dir(self):
            if getattr(getattr(self, k), "_is_tool", False):
                self._tools.append(getattr(self, k))

        for n in self._tools:
            self._funcMap.append(func2tool(n))

    def tools(self) -> List[dict]:
        return self._funcMap

    @tool
    def default_user(self) -> dict:
        """description:Return the current user, their associated repositories and open tickets"""
        return self._user.user_get_current().to_dict().get("login", None)

    @tool
    def dashboard(self) -> dict:
        """description:Return a dashboard with the current user, their repositories and open issues, mildestones and pull requests"""
        retv = self._user.user_get_current().to_dict()
        retv.update(
            {
                "repositories": [
                    n.to_dict() for n in self._user.user_current_list_subscriptions()
                ],
                "prs": [],
                "issues": [],
                "milestones": [],
            }
        )
        for r in retv.get("repositories", []):
            try:
                [
                    retv["issues"].append(n.to_dict())
                    for n in self._issue.issue_list_issues(
                        owner=r.get("owner", {}).get("login", None),
                        repo=r.get("name", None),
                        state="open",
                    )
                ]
                [
                    retv["milestones"].append(n.to_dict())
                    for n in self._issue.issue_get_milestones_list(
                        owner=r.get("owner", {}).get("login", None),
                        repo=r.get("name", None),
                        state="open",
                    )
                ]
                [
                    retv["prs"].append(n.to_dict())
                    for n in self._repo.repo_list_pull_requests(
                        owner=r.get("owner", {}).get("login", None),
                        repo=r.get("name", None),
                        state="open",
                    )
                ]
            except Exception as e:
                with open("default_user.debug", "w+") as fp:
                    fp.write(str(e) + "\n")
                    fp.write("-" * 80 + "\n")
                    fp.write(str(r) + "\n")
        return retv

    def get_heatmap_data(self, owner: str) -> List[dict]:
        return [n.to_dict() for n in self._user.user_get_heatmap_data(username=owner)]

    @tool
    def list_default_user_repos(self) -> List[dict]:
        """description:Return a list of all repos owned by or associated with the default user"""
        return [n.to_dict() for n in self._user.user_current_list_subscriptions()]

    @tool
    def list_default_user_issues(self) -> List[dict]:
        """description:Return a list of all issues assigned to the default user"""
        with open("debug.out", "w+") as fp:
            fp.write("DEBUG")
            fp.write(json.dumps(self.default_user(), indent=2) + "\n")
            for repo in self._user.user_current_list_subscriptions():
                fp.write(("-" * 80) + "\n")
                fp.write(json.dumps(self._issue_issue_list_issues(), indent=2) + "\n")
        return []

    @tool
    def list_users(self) -> List[str]:
        """description:Return a list of all users"""
        return [itm.to_dict() for itm in self._admin.admin_get_all_users()]

    @tool
    def list_orgs(self) -> List[str]:
        """description:Return a list of all orgs"""
        return [itm.to_dict() for itm in self._admin.admin_get_all_orgs()]

    @tool
    def list_repos(self, owner: str) -> List[dict]:
        """description:List repos for an owner
        owner:Owner of the repositories to list
        required:owner"""
        return [itm.to_dict() for itm in self._user.user_list_repos(owner)]

    @tool
    def list_labels(self, owner: str, repo: str) -> List[str]:
        """description:list issue labels for a repository
        owner:Owner of the repository
        repo:Name of the repository
        required:owner,repo"""
        return [
            itm.to_dict()
            for itm in self._issue.issue_list_labels(owner=owner, repo=repo)
        ]

    @tool
    def get_label(self, owner: str, repo: str, id: int) -> dict:
        """description:Get a single label from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the label to get
        required:owner,repo,id"""
        return self._issue.issue_get_label(owner=owner, repo=repo, id=id).to_dict()

    @tool
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

    @tool
    def add_labels(
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

    @tool
    def remove_labels(
        self, owner: str, repo: str, index: int, labels: List[int]
    ) -> dict:
        """description:Remove one or more labels from an issue
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to add label(s) to
        labels:List of label IDs to remove from the issue
        required:owner,repo,index,label"""
        self._issue.issue_remove_label(owner=owner, repo=repo, index=index, id=id)
        return {"result": "success"}

    @tool
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

    @tool
    def delete_label(self, owner: str, repo: str, id: int) -> dict:
        """description:Delete a label from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the label to delete
        required:owner,repo,id"""
        self._issue.issue_delete_label(owner=owner, repo=repo, id=id)
        return {"result": "success"}

    @tool
    def list_milestones(self, owner: str, repo: str, state: str = "open") -> List[str]:
        """description:List milestones for a repository
        owner:Owner of the repository
        repo:Name of the repository
        state:State of the milestones; enum:open,closed,all; default:open
        required:owner,repo"""
        return [
            itm.to_dict()
            for itm in self._issue.issue_get_milestones_list(
                owner=owner, repo=repo, state=state
            )
        ]

    @tool
    def get_milestone(self, owner: str, repo: str, id: int) -> dict:
        """description:Get a single milestone from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the milestone to get
        required:owner,repo,id"""
        return self._issue.issue_get_milestone(owner=owner, repo=repo, id=id).to_dict()

    @tool
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

    @tool
    def delete_milestone(self, owner: str, repo: str, id: int) -> dict:
        """description:Delete a milestone from a repository
        owner:Owner of the repository
        repo:Name of the repository
        id:ID of the milestone to delete
        required:owner,repo,id"""
        self._issue.issue_delete_milestone(owner=owner, repo=repo, id=id)
        return {"result": "success"}

    @tool
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
        return [issue.to_dict() for issue in self._issue.issue_list_issues(**kwargs)]

    @tool
    def get_issue(self, owner: str, repo: str, index: int) -> dict:
        """description:Get a single issue from a repository
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to get
        required:owner,repo,index"""
        return self._issue.issue_get_issue(
            owner=owner, repo=repo, index=index
        ).to_dict()

    @tool
    def edit_issue(
        self,
        owner: str,
        repo: str,
        index: int,
        assignee: str,
        assignees: List[str],
        body: str,
        due_date: str,
        milestone: int,
        state: str,
        title: str,
    ) -> dict:
        """description:Modify an existing issue
        owner:Owner of the repository
        repo:Name of the repository
        index:Index of the issue to close
        assignee:User to assign to the isssue
        assignees:List of users to assign to the issue
        body:The description of the issue
        due_date:A time/date the issue is due on
        milestone:ID of the milestone to attach the issue to
        state:State of the ticket; enum:open,closed;
        title:The title or headline of the issue
        required:owner,repo,index"""
        body = giteapy.EditIssueOption(
            **{
                "assignee": assignee,
                "assignees": assignees,
                "body": body,
                "due_date": due_date,
                "milestone": milestone,
                "state": state,
                "title": title,
            }
        )
        return self._issue.issue_edit_issue(owner, repo, index, body).to_dict()

    @tool
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

    @tool
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

    @tool
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


# create a new high priority issue for a bug on thwap-iac/test-repo titled 'socket interface causing segfault'
