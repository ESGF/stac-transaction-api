"""
Models relating to Authorisation for the ESGF Next Gen Core Architecture.
"""

import re
from typing import Literal
from urllib.parse import urlparse

from esgf_playground_utils.models.item import CMIP6Item
from esgf_playground_utils.models.kafka import RequesterData
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic_core import ValidationError
from stac_fastapi.extensions.core.transaction.request import PartialItem, PatchOperation

import settings.transaction as settings

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

    nodes: dict[str, Node] = {}

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

    def authorize(self, assets: dict, role: Role):
        """Check for appropriate authorisation.

        Args:
            assets (CMIP6Item): item to be authorised
            role (Role): required role for auhroisation

        Raises:
            HTTPException: Raised if either node or role permission is missing
        """
        for asset in assets.values():
            asset_url = urlparse(asset.href)
            node_permission = self.nodes.get(asset_url.hostname, None)

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

    projects: dict[str, Project] = {}

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

    def authorize(self, project: str, role: Role):
        """Check for appropriate authorisation.

        Args:
            item (Item): item to be authorised
            role (Role): required role for auhroisation

        Raises:
            HTTPException: Raised if either node or role permission is missing
        """
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

    requester_data: RequesterData
    nodes: Nodes = Nodes()
    projects: Projects = Projects()

    def authorize(self, collection_id: str, item: CMIP6Item | PartialItem, role: Role):
        """Check for appropriate authorisation.

        Args:
            collection_id: collection id of request
            item (Item): item to be authorised
            role (Role): required role for auhroisation

        Raises:
            HTTPException: Raised if either node or role permission is missing
        """
        self.projects.authorize(collection_id, role)
        self.nodes.authorize(item.assets, role)

    def add(self, entitlements: list[str]):
        """add entitlements to Authorizer.

        Args:
            entitlements (list[str]): list of entitlements to be added
        """
        for entitlement in entitlements:
            if match := re.search(settings.stac_api.get("regex"), entitlement):

                try:
                    if match.group("type") == "project":
                        self.projects.add(
                            Project(
                                id=match.group("id"),
                                roles=[match.group("role")],
                            )
                        )

                    elif match.group("type") == "node":
                        self.nodes.add(
                            Node(
                                id=match.group("id"),
                                roles=[match.group("role")],
                            )
                        )

                except ValidationError:
                    settings.logger.info("Entitlement skipped: %s", entitlement)
