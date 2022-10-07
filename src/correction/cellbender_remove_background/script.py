import mudata as mu
# import scanpy as sc
import logging
import tempfile
# import pathlib
import subprocess
import os
import sys
import numpy as np

logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
logFormatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
console_handler.setFormatter(logFormatter)
logger.addHandler(console_handler)

## VIASH START
par = {
    # inputs
    "input": "input.h5mu",
    "modality": "rna",
    # outputs
    "output": "output.h5mu",
    "layer_output": "corrected",
    "obs_latent_rt_efficiency": "latent_rt_efficiency",
    "obs_latent_cell_probability": "latent_cell_probability",
    "obs_latent_scale": "latent_scale",
    "var_ambient_expression": "ambient_expression",
    # "obsm_latent_gene_encoding": "latent_gene_encoding",
    # args
    "total_droplets_included": 50000,
    "epochs": 150,
    "fpr": 0.01,
    "exclude_antibody_capture": False,
    "learning_rate": 0.001,
    "layer_corrected": "corrected",
    "cuda": False
}
meta = { 
  'temp_dir': os.getenv("VIASH_TEMP"), 
  'resources_dir': 'src/correction/cellbender_remove_background'
}
## VIASH END

sys.path.append(meta['resources_dir'])
from helper import anndata_from_h5

logger.info("Reading input mudata")
mdata = mu.read_h5mu(par["input"])

mod = par["modality"]
logger.info("Performing log transformation on modality %s", mod)
data = mdata.mod[mod]

# with pathlib.Path(meta["temp_dir"]) / "cellbender" as temp_dir:
#   os.mkdir(temp_dir)
with tempfile.TemporaryDirectory(prefix="cellbender-", dir=meta["temp_dir"]) as temp_dir:
  # construct paths within tempdir
  input_file = os.path.join(temp_dir, "input.h5ad")
  output_file = os.path.join(temp_dir, "output.h5")

  logger.info("Creating AnnData input file for CellBender: '%s'", input_file)
  data.write_h5ad(input_file)

  logger.info("Constructing CellBender command")
  cmd_pars = [
    "cellbender", "remove-background",
    "--input", input_file,
    "--output", output_file
  ]

  extra_args = [
    ("--expected-cells", "expected_cells", True),
    ("--total-droplets-included", "total_droplets_included", True),
    ("--model", "model", True),
    ("--epochs", "epochs", True),
    ("--cuda", "cuda", False),
    ("--low-count-threshold", "low_count_threshold", True),
    ("--z-dim", "z_dim", True),
    ("--z-layers", "z_layers", True),
    ("--training-fraction", "training_fraction", True),
    ("--exclude-antibody-capture", "exclude_antibody_capture", False),
    ("--learning-rate", "learning_rate", True),
    ("--empty-drop-training-fraction", "empty_drop_training_fraction", True),
  ]
  for (flag, name, is_kwarg) in extra_args:
    if par[name]:
      values = par[name] if isinstance(par[name], list) else [par[name]]
      cmd_pars += [flag] + [str(val) for val in values] if is_kwarg else [flag]

  logger.info("Running CellBender")
  out = subprocess.check_output(cmd_pars).decode("utf-8")
  
  logger.info("Reading CellBender 10xh5 output file: '%s'", output_file)
  # have to use custom read_10x_h5 function for now
  # will be fixed when https://github.com/scverse/scanpy/pull/2344 is merged
  # adata_out = sc.read_10x_h5(output_file, gex_only=False)
  adata_out = anndata_from_h5(output_file, analyzed_barcodes_only=False)

  logger.info("Copying X output to MuData")
  data.layers[par["layer_output"]] = adata_out.X

  logger.info("Copying .obs output to MuData")
  obs_store = { 
    "obs_latent_rt_efficiency": "latent_RT_efficiency", 
    "obs_latent_cell_probability": "latent_cell_probability", 
    "obs_latent_scale": "latent_scale"
  }
  for to_name, from_name in obs_store.items():
    if par[to_name]:
      if from_name in adata_out.obs:
        data.obs[par[to_name]] = adata_out.obs[from_name]
      # when using unfiltered data, the values will be in uns instead of obs
      elif from_name in adata_out.uns and 'barcode_indices_for_latents' in adata_out.uns:
        vec = np.zeros(data.n_obs)
        vec[adata_out.uns['barcode_indices_for_latents']] = adata_out.uns[from_name]
        data.obs[par[to_name]] = vec
  
  logger.info("Copying .var output to MuData")
  var_store = { "var_ambient_expression": "ambient_expression" }
  for to_name, from_name in var_store.items():
    if par[to_name]:
      data.var[par[to_name]] = adata_out.var[from_name]

  # logger.info("Copying .obsm output to MuData")
  # obsm_store = { "obsm_latent_gene_encoding": "latent_gene_encoding" }
  # for to_name, from_name in obsm_store.items():
  #   if par[to_name]:
  #     data.obsm[par[to_name]] = adata_out.obsm[from_name]


logger.info("Writing to file %s", par["output"])
mdata.write(filename=par["output"])