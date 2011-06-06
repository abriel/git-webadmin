#!/bin/bash

PYTHONPATH=.. DJANGO_SETTINGS_MODULE=settings python -c "
from core.models import *
gl = Gitolite_Repository_System()
print gl._parse_config()

gs = Gitosis_Repository_System()
print gs._parse_config()
"
