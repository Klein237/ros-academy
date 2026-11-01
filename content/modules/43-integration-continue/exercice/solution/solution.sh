#!/usr/bin/env bash
# Le workflow corrigé : déclenché aussi par les pull requests, il récupère le code
# et échoue quand un test échoue (colcon test-result).
set -euo pipefail
mkdir -p .github/workflows
cat > .github/workflows/ci.yml <<'YAML'
# Intégration continue du dépôt du robot de livraison.
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  compiler-tester:
    runs-on: ubuntu-24.04
    container: ros:jazzy-ros-base
    defaults:
      run:
        shell: bash
    steps:
      - uses: actions/checkout@v4
      - name: Dépendances
        run: |
          apt-get update
          rosdep update
          rosdep install --from-paths src --ignore-src -y
      - name: Compilation
        run: |
          source /opt/ros/jazzy/setup.bash
          colcon build
      - name: Tests
        run: |
          source /opt/ros/jazzy/setup.bash
          colcon test
          colcon test-result --verbose
YAML
