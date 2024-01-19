import sys
import os
import pytest
import mudata as md
import numpy as np

## VIASH START
meta = {
    'resources_dir': './resources_test/',
    'executable': './target/docker/query/cellxgene_census',
    'config': '/home/di/code/openpipeline/src/query/cellxgene_census/config.vsh.yaml'
}
## VIASH END

def test_cellxgene_extract_metadata_expression(run_component, tmp_path):
    output_file = tmp_path / "output.h5mu"

    run_component([
        "--obs_value_filter", "is_primary_data == True and cell_type_ontology_term_id in ['CL:0000136', 'CL:1000311', 'CL:0002616'] and suspension_type == 'cell'",
        "--species", "homo_sapiens",
        "--output", output_file,
    ])

    # check whether file exists
    assert os.path.exists(output_file), "Output file does not exist"

    mdata = md.read(output_file)
    print(f"Output: {mdata}")

    assert 'rna' in mdata.mod, "Output should contain 'rna' modality."
    var, obs = mdata.mod['rna'].var, mdata.mod['rna'].obs
    assert not obs.empty, ".obs should not be empty"
    assert "is_primary_data" in obs.columns
    assert np.all(obs["is_primary_data"] == True)
    assert "cell_type_ontology_term_id" in obs.columns
    assert "disease" in obs.columns
    assert "soma_joinid" in var.columns
    assert "feature_id" in var.columns
    assert mdata.mod['rna'].n_obs

if __name__ == '__main__':
    sys.exit(pytest.main([__file__]))
