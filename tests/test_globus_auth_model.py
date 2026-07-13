import pytest
from esgf_core_utils.models.exceptions import AuthorizationException, MissingPermissionException
from esgf_core_utils.models.kafka.events import RequesterData
from stac_fastapi.extensions.transaction.request import PartialItem

from authorizer.globus_auth_model import GlobusAuth, Node, Nodes, Project, Projects

REGEX = (
    r"(?P<type>[^:]*)\:(?P<id>[^:]*)(\:institution\:(?P<institution>[^:]*))?"
    r"\:role=(?P<role>[^:]*)\:group\:(?P<group_id>[^:]*)"
)
GROUP_ID = "e3329078-b8f6-11f0-9fdd-0e7d9e9fc9e3"
NODE = "aims3.llnl.gov"


@pytest.fixture
def requester_data():
    return RequesterData(
        client_id="test-client",
        sub="test-sub",
        iss="https://auth.globus.org",
    )


@pytest.fixture
def item_with_asset():
    return PartialItem.model_validate({
        "assets": {
            "data": {
                "href": f"https://{NODE}/path/to/file.nc",
                "alternate:name": NODE,
            }
        }
    })


class TestNodes:
    def test_add_new_node(self):
        nodes = Nodes()
        nodes.add(Node(id=NODE, roles={"CREATE"}))
        assert NODE in nodes.nodes
        assert "CREATE" in nodes.nodes[NODE].roles

    def test_add_existing_node_merges_roles(self):
        nodes = Nodes()
        nodes.add(Node(id=NODE, roles={"CREATE"}))
        nodes.add(Node(id=NODE, roles={"UPDATE"}))
        assert nodes.nodes[NODE].roles == {"CREATE", "UPDATE"}

    def test_authorize_href_by_hostname(self):
        nodes = Nodes()
        nodes.add(Node(id=NODE, roles={"CREATE"}))
        nodes.authorize_href(f"https://{NODE}/path", "CREATE")

    def test_authorize_href_wildcard_fallback(self):
        nodes = Nodes()
        nodes.add(Node(id="*", roles={"CREATE"}))
        nodes.authorize_href("https://any-node.example.com/path", "CREATE")

    def test_authorize_href_no_matching_node_raises(self):
        nodes = Nodes()
        with pytest.raises(MissingPermissionException):
            nodes.authorize_href(f"https://{NODE}/path", "CREATE")

    def test_authorize_href_wrong_role_raises(self):
        nodes = Nodes()
        nodes.add(Node(id=NODE, roles={"CREATE"}))
        with pytest.raises(MissingPermissionException):
            nodes.authorize_href(f"https://{NODE}/path", "DELETE")

    def test_authorize_assets(self):
        nodes = Nodes()
        nodes.add(Node(id=NODE, roles={"CREATE"}))
        assets = {"data": {"href": f"https://{NODE}/file.nc", "alternate:name": NODE}}
        nodes.authorize(assets, "CREATE")

    def test_authorize_assets_no_permission_raises(self):
        nodes = Nodes()
        assets = {"data": {"href": f"https://{NODE}/file.nc", "alternate:name": NODE}}
        with pytest.raises(MissingPermissionException):
            nodes.authorize(assets, "CREATE")

    def test_authorize_nested_alternate_assets(self):
        nodes = Nodes()
        nodes.add(Node(id=NODE, roles={"CREATE"}))
        nodes.add(Node(id="eagle.alcf.anl.gov", roles={"CREATE"}))
        assets = {
            "data": {
                "href": f"https://{NODE}/file.nc",
                "alternate:name": NODE,
                "alternate": {
                    "replica": {
                        "href": "https://eagle.alcf.anl.gov/file.nc",
                        "alternate:name": "eagle.alcf.anl.gov",
                    }
                },
            }
        }
        nodes.authorize(assets, "CREATE")


class TestProjects:
    def test_add_new_project(self):
        projects = Projects()
        projects.add(Project(id="CMIP6", roles={"CREATE"}))
        assert "CMIP6" in projects.projects
        assert "CREATE" in projects.projects["CMIP6"].roles

    def test_add_existing_project_merges_roles(self):
        projects = Projects()
        projects.add(Project(id="CMIP6", roles={"CREATE"}))
        projects.add(Project(id="CMIP6", roles={"UPDATE"}))
        assert projects.projects["CMIP6"].roles == {"CREATE", "UPDATE"}

    def test_authorize_by_project_id(self):
        projects = Projects()
        projects.add(Project(id="CMIP6", roles={"CREATE"}))
        projects.authorize("CMIP6", "CREATE")

    def test_authorize_wildcard_fallback(self):
        projects = Projects()
        projects.add(Project(id="*", roles={"CREATE"}))
        projects.authorize("CMIP6", "CREATE")

    def test_authorize_no_matching_project_raises(self):
        projects = Projects()
        with pytest.raises(MissingPermissionException):
            projects.authorize("CMIP6", "CREATE")

    def test_authorize_wrong_role_raises(self):
        projects = Projects()
        projects.add(Project(id="CMIP6", roles={"CREATE"}))
        with pytest.raises(MissingPermissionException):
            projects.authorize("CMIP6", "DELETE")

    def test_specific_project_takes_precedence_over_wildcard(self):
        projects = Projects()
        projects.add(Project(id="*", roles={"CREATE"}))
        projects.add(Project(id="CMIP6", roles={"DELETE"}))
        with pytest.raises(MissingPermissionException):
            projects.authorize("CMIP6", "CREATE")


class TestGlobusAuthAdd:
    def test_add_project_entitlement(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([f"project:CMIP6:role=CREATE:group:{GROUP_ID}"])
        assert "CMIP6" in auth.projects.projects
        assert "CREATE" in auth.projects.projects["CMIP6"].roles

    def test_add_node_entitlement(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([f"node:{NODE}:role=CREATE:group:{GROUP_ID}"])
        assert NODE in auth.nodes.nodes
        assert "CREATE" in auth.nodes.nodes[NODE].roles

    def test_invalid_entitlement_skipped(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add(["not-a-valid-entitlement"])
        assert auth.projects.projects == {}
        assert auth.nodes.nodes == {}

    def test_invalid_role_skipped(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([f"project:CMIP6:role=SUPERADMIN:group:{GROUP_ID}"])
        assert auth.projects.projects == {}

    def test_multiple_entitlements_accumulate_roles(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([
            f"project:CMIP6:role=CREATE:group:{GROUP_ID}",
            f"project:CMIP6:role=UPDATE:group:{GROUP_ID}",
        ])
        assert auth.projects.projects["CMIP6"].roles == {"CREATE", "UPDATE"}

    def test_wildcard_entitlement(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([f"project:*:role=CREATE:group:{GROUP_ID}"])
        assert "*" in auth.projects.projects

    def test_mixed_project_and_node_entitlements(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([
            f"project:CMIP6:role=CREATE:group:{GROUP_ID}",
            f"node:{NODE}:role=CREATE:group:{GROUP_ID}",
        ])
        assert "CMIP6" in auth.projects.projects
        assert NODE in auth.nodes.nodes


class TestGlobusAuthAuthorize:
    def test_authorize_success(self, requester_data, item_with_asset):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([
            f"project:CMIP6:role=CREATE:group:{GROUP_ID}",
            f"node:{NODE}:role=CREATE:group:{GROUP_ID}",
        ])
        auth.authorize("CMIP6", item_with_asset, "CREATE", "req-1", "evt-1")

    def test_authorize_missing_project_raises(self, requester_data, item_with_asset):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([f"node:{NODE}:role=CREATE:group:{GROUP_ID}"])
        with pytest.raises(AuthorizationException):
            auth.authorize("CMIP6", item_with_asset, "CREATE", "req-1", "evt-1")

    def test_authorize_missing_node_raises(self, requester_data, item_with_asset):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([f"project:CMIP6:role=CREATE:group:{GROUP_ID}"])
        with pytest.raises(AuthorizationException):
            auth.authorize("CMIP6", item_with_asset, "CREATE", "req-1", "evt-1")

    def test_authorize_wrong_role_raises(self, requester_data, item_with_asset):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([
            f"project:CMIP6:role=CREATE:group:{GROUP_ID}",
            f"node:{NODE}:role=CREATE:group:{GROUP_ID}",
        ])
        with pytest.raises(AuthorizationException):
            auth.authorize("CMIP6", item_with_asset, "DELETE", "req-1", "evt-1")

    def test_authorize_item_with_no_assets(self, requester_data):
        auth = GlobusAuth(requester_data=requester_data, regex=REGEX)
        auth.add([f"project:CMIP6:role=CREATE:group:{GROUP_ID}"])
        item = PartialItem.model_validate({})
        auth.authorize("CMIP6", item, "CREATE", "req-1", "evt-1")
