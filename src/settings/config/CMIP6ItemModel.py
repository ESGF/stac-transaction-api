from pydantic import AnyUrl, ConfigDict
from stac_pydantic import Item, ItemProperties
from typing import List, Optional

import datetime as datetimevalidate


class CMIP6ItemProperties(ItemProperties):
    access: List[str]
    activity_id: List[str]
    cf_standard_name: str
    citation_url: AnyUrl
    data_spec_version: Optional[str] = None
    datetime: Optional[datetimevalidate.datetime] = None
    end_datetime: datetimevalidate.datetime
    experiment_id: str
    experiment_title: str
    frequency: str
    further_info_url: AnyUrl
    grid: str
    grid_label: str
    institution_id: str
    mip_era: str
    model_cohort: str
    nominal_resolution: str
    pid: str
    product: str
    project: str
    realm: List[str]
    retracted: Optional[str] = None
    source_id: str
    source_type: List[str]
    start_datetime: datetimevalidate.datetime
    sub_experiment_id: str
    table_id: str
    title: str
    variable: str
    variable_id: str
    variable_long_name: str
    variable_units: str
    variant_label: str
    version: str

    model_config = ConfigDict(
        protected_namespaces=()
    )


class CMIP6Item(Item):
    properties: CMIP6ItemProperties


# from stac_pydantic.extensions import validate_extensions
# model = CMIP6Item(**stac_item)
# validate_extensions(model, reraise_exception=True)
# print(model)
