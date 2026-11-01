#!/usr/bin/env bash
# Rejoue les commandes du cours : les tests du package passent, directement et avec colcon test.
set -e
(cd src/odometrie && python3 -m pytest -q -p no:cacheprovider test)
colcon test --packages-select odometrie --event-handlers console_direct- > /dev/null
colcon test-result --verbose | tail -n 3
colcon test-result > /dev/null      # code non nul si un test a échoué
echo "tests du package odometrie : ok"
