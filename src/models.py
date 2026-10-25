"""ESGF-specific STAC Item model.

`stac_pydantic.item.Item` does not declare the ESGF/CMIP `base_id` and
`version` top-level Item fields (siblings of `id`/`collection`), and it
does not set `extra="allow"` at that level (only the nested
`ItemProperties` does). Pydantic v2's default is `extra="ignore"`, so
FastAPI silently drops any such field when it parses a request body into
a plain `Item` -- a client-submitted `base_id`/`version` never survives to
reach JSON Schema validation, even though the CMIP6/CMIP7 STAC extension
schemas require both at the item root (see the `cmip7` schema for
`>=v2.0.1` on the `gh-pages` branch, `oneOf[0].required`).

`ESGFItem` keeps `Item`'s existing validation behaviour but preserves any
extension-defined top-level field the client sends, so it reaches the
JSON Schema validator that actually enforces it.
"""

from pydantic import ConfigDict
from stac_pydantic.item import Item


class ESGFItem(Item):
    model_config = ConfigDict(extra="allow")
