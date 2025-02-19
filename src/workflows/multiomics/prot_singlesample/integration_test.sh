#!/bin/bash

# get the root of the directory
REPO_ROOT=$(git rev-parse --show-toplevel)

# ensure that the command below is run from the root of the repository
cd "$REPO_ROOT"

export NXF_VER=21.10.6

viash ns build -q prot_singlesample

nextflow run . \
  -main-script src/workflows/multiomics/prot_singlesample/test.nf \
  -profile docker,no_publish \
  -resume \
  -entry test_wf \
  -with-trace work/trace.txt