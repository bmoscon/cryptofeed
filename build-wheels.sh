#!/bin/bash
#set -e -x

py_vers=("/opt/python/cp310-cp310/bin" "/opt/python/cp38-cp38/bin" "/opt/python/cp39-cp39/bin")

#for PY in "${py_vers[@]}"; do
#    "${PY}/pip" wheel /io/ -w wheelhouse/
#done

#for whl in wheelhouse/*.whl; do
#    auditwheel repair "$whl" -w /io/wheelhouse/
#done

set -e -u -x

PLAT=manylinux_2_24_x86_64

function repair_wheel {
    wheel="$1"
    if ! auditwheel show "$wheel"; then
        echo "Skipping non-platform wheel $wheel"
    else
        auditwheel repair "$wheel" --plat "$PLAT" -w /io/wheelhouse/
    fi
}


# Install a system package required by our library
#yum install -y gcc g++ buildtools

# Compile wheels
for PYBIN in "${py_vers[@]}"; do
    "${PYBIN}/pip" install cython
    "${PYBIN}/pip" wheel /io/ --no-deps -w wheelhouse/
done

# Bundle external shared libraries into the wheels
for whl in wheelhouse/*.whl; do
    repair_wheel "$whl"
done