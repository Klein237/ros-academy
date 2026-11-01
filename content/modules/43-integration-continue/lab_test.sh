#!/usr/bin/env bash
# Rejoue le cours : ci.sh réussit sur le package, et échoue dès qu'un test échoue.
set -e
bash ci.sh > /tmp/ci-sain.txt 2>&1 || { tail -n 30 /tmp/ci-sain.txt; exit 1; }
printf 'def test_casse():\n    assert False\n' > src/odometrie/test/test_casse.py
if bash ci.sh > /tmp/ci-casse.txt 2>&1; then
  echo "ci.sh réussit alors qu'un test échoue"; exit 1
fi
rm src/odometrie/test/test_casse.py
echo "ci.sh : vert sur le package, rouge quand un test échoue : ok"
