import sys
import pytest

import mudata as md
import numpy as np
import scanpy as sc

## VIASH START
meta = {
    'executable': './target/docker/qc/calculate_atac_qc_metrics/calculate_atac_qc_metrics',
    'resources_dir': "./resources_test/pbmc_1k_protein_v3/",
    'config': './src/qc/calculate_atac_qc_metrics/config.vsh.yaml',
    'cpus': 2
}
## VIASH END

@pytest.fixture
def synthetic_example():
    atac = sc.AnnData(np.array([
        [0, 0, 0],
        [1, 0, 1],
        [10, 0, 0],
        [100, 0, 1],
        [1000, 0, 0]
    ]))

    return md.MuData({"atac": atac})

@pytest.fixture
def example_mudata(tmp_path, synthetic_example):
    mdata_path = tmp_path / "example.h5mu"
    synthetic_example.write(mdata_path)
    
    return mdata_path

@pytest.fixture
def example_mudata_with_layer(tmp_path, synthetic_example):
    synthetic_example.mod["atac"].layers["atac_counts"] = synthetic_example.mod["atac"].X.copy()
    synthetic_example.mod["atac"].X = np.random.normal(size=synthetic_example.mod["atac"].X.shape)
    mdata_path = tmp_path / "example.h5mu"
    synthetic_example.write(mdata_path)
    
    return mdata_path

@pytest.fixture
def neurips_mudata(tmp_path):
    """From the `NeurIPS Multimodal Single-Cell Integration Challenge
    <https://www.kaggle.com/competitions/open-problems-multimodal/data>`
    
    Link is taken from the Moscot repository: 
    https://github.com/theislab/moscot/blob/cb53435c80fafe58046ead3c42a767fd0b818aaa/src/moscot/datasets.py#L67

    """
    adata = sc.read("../data/neurips_data.h5ad", backup_url="https://figshare.com/ndownloader/files/37993503")

    mdata = md.MuData({"atac": adata})
    mdata_path = tmp_path / "neurips.h5mu"
    mdata.write(mdata_path)

    return mdata_path

@pytest.fixture
def input_mudata(input_path):
    return md.read_h5mu(input_path)

@pytest.mark.parametrize("mudata", ["example_mudata", "neurips_mudata"])
def test_qc_columns_in_tables(run_component, request, mudata, tmp_path):
    input_path = request.getfixturevalue(mudata)
    output_path = tmp_path / "foo.h5mu"

    args = [
        "--input", str(input_path),
        "--output", str(output_path),
        "--modality", "atac",
        "--n_fragments_for_nucleosome_signal", "100"
    ]

    run_component(args)
    assert output_path.is_file()
    data_with_qc = md.read(output_path)

    for qc_metric in ("n_features_per_cell", "total_fragment_counts", "log_total_fragment_counts"):
        assert qc_metric in data_with_qc.mod["atac"].obs
    for qc_metric in ("n_cells_by_counts", "mean_counts", "pct_dropout_by_counts", "total_counts"):
        assert qc_metric in data_with_qc.mod["atac"].var


@pytest.mark.parametrize("mudata", ["example_mudata", "example_mudata_with_layer"])
def test_calculations_correctness(request, run_component, mudata, tmp_path):
    input_path = request.getfixturevalue(mudata)
    output_path = tmp_path / "foo.h5mu"

    args = [
        "--input", str(input_path),
        "--output", str(output_path),
        "--modality", "atac",
        "--n_fragments_for_nucleosome_signal", "100"
    ]

    if mudata == "example_mudata_with_layer":
        args.extend(["--layer", "atac_counts"])

    run_component(args)
    assert output_path.is_file()
    data_with_qc = md.read(output_path)

    assert np.allclose(data_with_qc.mod["atac"].obs["n_features_per_cell"], [0, 2, 1, 2, 1])
    assert np.allclose(data_with_qc.mod["atac"].obs["total_fragment_counts"], [0, 2, 10, 101, 1000])
    assert np.allclose(data_with_qc.mod["atac"].obs["log_total_fragment_counts"], [-np.inf, np.log10(2), np.log10(10), np.log10(101), np.log10(1000)])

    assert np.allclose(data_with_qc.mod["atac"].var["n_cells_by_counts"], [4, 0, 2])
    assert np.allclose(data_with_qc.mod["atac"].var["mean_counts"], [222.2, 0, 0.4])
    assert np.allclose(data_with_qc.mod["atac"].var["pct_dropout_by_counts"], [20, 100, 60])
    assert np.allclose(data_with_qc.mod["atac"].var["total_counts"], [1111, 0, 2])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
