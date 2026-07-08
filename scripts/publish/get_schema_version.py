from esgvoc.apps.jsg import json_schema_generator as jsg
import sys
print(jsg.get_schema_version(sys.argv[1]))
