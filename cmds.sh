_inst_clean() {
  local current="$1"
  for dep in $(sed -nE 's/    (.*)>=.*/\1/p' "../$current/setup.cfg"); do
    if [[ -d "../$dep" ]]; then
      _inst_clean "$dep"
    fi
  done
  rm -rf ../$current/src/*.egg-info
}

_inst_local() {
  local current="$1"
  local extras="$2"
  pushd "../$current"
  for dep in $(sed -nE 's/    (.*)>=.*/\1/p' setup.cfg); do
    if [[ \
        -d "../$dep" && ! -f $(python3 -c \
        'import sysconfig; print(sysconfig.get_paths()["purelib"])')/$dep.egg-link \
    ]]; then
      _inst_local "$dep"
    fi
  done
  python3 -m pip install -e ."$extras"
  popd
}

activate() {
  # Activate virtual environment. Use "deactivate" (part of venv) to undo this.
  source venv/bin/activate
}

py_inst() {(
  # Install the project in this directory in a Python 3 virtual environment.
  rm -rf venv
  python3 -m venv venv || (rm -rf venv && exit 1)
  py_update || (rm -rf venv && exit 1)
)}

py_test() {(
  # Run Python tests in the "test" dir relative to where this command is run.
  if [[ -z venv ]]; then
    py_inst || exit 1
  fi
  activate && python3 -m pytest test/ "$@"
)}

py_update() {(
  # Update by reinstalling dependencies.
  activate
  local package_name=$(basename $(pwd))
  if grep -q '^test =$' setup.cfg; then
    local extras="[test]"
  else
    local extras=""
  fi
  _inst_local "$package_name" "$extras"
  _inst_clean "$package_name"
)}

unsource() {
  # Unset all functions defined by this file.
  unset _inst_clean
  unset _inst_local
  unset activate
  unset py_inst
  unset py_tests
  unset py_update
  unset unsource
}
