"""
Models relating to Authorisation for the ESGF Next Gen Core Architecture.
"""

from typing import Literal

from esgf_playground_utils.models.kafka import RequesterData
from fastapi import HTTPException
from pydantic import BaseModel
from stac_pydantic.item import Item

Role = Literal[
    "CREATE",
    "UPDATE",
    "DELETE",
    "REPLICATE",
    "REVOKE",
]


class Node(BaseModel):
    """
    Model describing Node auth info of a ESGF publisher.
    """

    id: str
    roles: set[Role]


class Project(BaseModel):
    """
    Model describing Project auth info of a ESGF publisher.
    """

    id: str
    roles: set[Role]


class Nodes(BaseModel):
    """
    Model describing Project auth info of a ESGF publisher.
    """

    nodes: dict[str, Node]

    def add(self, node: Node | dict):
        """
        Add a new project or update roles if project already exists.

        Args:
            node (Node | dict): node to be added
        """
        if isinstance(node, dict):
            node = Node(**node)

        if existing_node := self.nodes.get(node.id):
            existing_node.roles.update(node.roles)

        else:
            self.nodes[node.id] = node

    def authorize(self, item: Item, role: Role):
        """Check for appropriate authorisation.

        Args:
            assets (Item): item to be authorised
            role (Role): required role for auhroisation

        Raises:
            HTTPException: Raised if either node or role permission is missing
        """
        for asset in item.assets:
            node_permission = self.nodes.get(asset.href, None)
            if not node_permission:
                raise HTTPException(
                    status_code=401,
                    detail=f"Node permission missing for {asset.href}",
                )

            if role not in node_permission.roles:
                raise HTTPException(
                    status_code=401,
                    detail=f"Node role ({role}) permission missing for {asset.href}",
                )


class Projects(BaseModel):
    """
    Model describing Project auth info of a ESGF publisher.
    """

    projects: dict[str, Project]

    def add(self, project: Project | dict):
        """
        Add a new project or update roles if project already exists.

        Args:
            project (Project | dict): project to be added
        """
        if isinstance(project, dict):
            project = Project(**project)

        if existing_project := self.projects.get(project.id):
            existing_project.roles.update(project.roles)

        else:
            self.projects[project.id] = project

    def authorize(self, item: Item, role: Role):
        """Check for appropriate authorisation.

        Args:
            item (Item): item to be authorised
            role (Role): required role for auhroisation

        Raises:
            HTTPException: Raised if either node or role permission is missing
        """
        project = item.properties["project"]
        project_permission = self.projects.get(project, None)

        if not project_permission:
            raise HTTPException(
                status_code=401,
                detail=f"Project permission missing for {project}",
            )

        if role not in project_permission.roles:
            raise HTTPException(
                status_code=401,
                detail=f"Project role ({role}) permission missing for {project}",
            )


class Authorizer(BaseModel):
    """
    Model describing Authentication information of a ESGF publisher.
    """

    client_id: str
    requester_data: RequesterData
    nodes: Nodes
    projects: Projects

    def authorize(self, item: Item, role: Role):
        """Check for appropriate authorisation.

        Args:
            item (Item): item to be authorised
            role (Role): required role for auhroisation

        Raises:
            HTTPException: Raised if either node or role permission is missing
        """
        self.projects.authorize(item, role)
        self.nodes.authorize(item, role)
