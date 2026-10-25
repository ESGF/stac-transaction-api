import json
import unittest

from models import ESGFItem

MINIMAL_ITEM = {
    "type": "Feature",
    "stac_version": "1.1.0",
    "stac_extensions": [],
    "id": "some.id.here",
    "base_id": "MIP-DRS7.CMIP7.CMIP.EC-Earth-Consortium.EC-Earth3-ESM-1-1.esm-hist.r1i1p1f1",
    "version": "20260428",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    },
    "bbox": [0, 0, 1, 1],
    "collection": "CMIP7",
    "links": [],
    "properties": {
        "datetime": None,
        "start_datetime": "1850-01-01T00:00:00Z",
        "end_datetime": "1850-02-01T00:00:00Z",
    },
    "assets": {},
}


class TestESGFItem(unittest.TestCase):
    def test_base_id_and_version_survive_round_trip(self):
        """stac_pydantic.item.Item silently drops unrecognized top-level
        fields (pydantic v2 default extra="ignore"), so a client-submitted
        base_id/version never reaches JSON Schema validation even when
        the CMIP6/CMIP7 extension schema requires them at the item root.
        ESGFItem must preserve them.
        """
        item = ESGFItem(**MINIMAL_ITEM)
        dumped = json.loads(item.model_dump_json())

        self.assertEqual(dumped.get("base_id"), MINIMAL_ITEM["base_id"])
        self.assertEqual(dumped.get("version"), MINIMAL_ITEM["version"])

    def test_still_validates_known_required_fields(self):
        """ESGFItem must keep Item's existing validation -- allowing
        extra fields should not weaken required/typed fields."""
        bad_item = dict(MINIMAL_ITEM)
        del bad_item["id"]

        with self.assertRaises(Exception):
            ESGFItem(**bad_item)


if __name__ == "__main__":
    unittest.main()
