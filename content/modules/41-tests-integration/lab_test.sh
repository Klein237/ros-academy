#!/usr/bin/env bash
# Rejoue les commandes du cours : le test d'intégration passe avec launch_test, puis avec colcon test.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
launch_test src/limiteur/test/test_limiteur_launch.py > /tmp/launch_test.txt 2>&1 || { tail -n 40 /tmp/launch_test.txt; exit 1; }
colcon test --packages-select limiteur --event-handlers console_direct- > /dev/null
colcon test-result --verbose | tail -n 3
colcon test-result | grep -Eq "^Summary: [1-9][0-9]* tests?,"   # colcon test a bien trouvé le test launch (« 1 test » au singulier)
colcon test-result > /dev/null      # code non nul si un test a échoué
echo "test d'intégration du limiteur : ok"
