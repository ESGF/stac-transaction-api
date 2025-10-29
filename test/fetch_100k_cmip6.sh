#!/bin/bash


download() {
    activity=$1
    institution=$2
    for i in ${institution}; do
        python fetch_esgf_cmip6.py --activity-id ${activity} --institution-id ${i}
    done
}

activity_id='AerChemMIP'
institution_id='NOAA-GFDL NCAR BCC DKRZ NIMS-KMA NERC UCSB'
download ${activity_id} "${institution_id}"

activity_id='C4MIP'
institution_id='MIROC CSIRO CNRM-CERFACS NCC MRI NASA-GISS'
download ${activity_id} "${institution_id}"

activity_id='CFMIP'
institution_id='IPSL MRI MOHC NASA-GISS CNRM-CERFACS NCAR'
download ${activity_id} "${institution_id}"

activity_id='DAMIP'
institution_id='NCAR CNRM-CERFACS'
download ${activity_id} "${institution_id}"

activity_id='CDRMIP'
institution_id='MOHC MIROC'
download ${activity_id} "${institution_id}"

activity_id='CMIP'
institution_id='CAS NOAA-GFDL BCC'
download ${activity_id} "${institution_id}"

activity_id='FAFMIP'
institution_id='MRI MIROC NCAR'
download ${activity_id} "${institution_id}"
