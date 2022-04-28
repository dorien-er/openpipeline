nextflow.enable.dsl=2

workflowDir = params.rootDir + "/workflows"
targetDir = params.rootDir + "/target/nextflow"

include { bd_rhapsody_wta } from  targetDir + "/mapping/bd_rhapsody_wta/main.nf" params(params)
include { from_bdrhap_to_h5ad } from  targetDir + "/convert/from_bdrhap_to_h5ad/main.nf" params(params)

include { publish } from targetDir + "/transfer/publish/main.nf" params(params)
include { getChild; overrideOptionValue; has_param; check_required_param } from workflowDir + "/utils/utils.nf" params(params)

workflow {
  if (has_param("help")) {
    log.info """TX Processing - CLI workflow

A workflow for running a BD Rhapsody WTA workflow.
This workflow can be run on a single input or in batch, see below.

Parameters (Single input mode):
  --id       ID of the sample (optional).
  --input    One or more fastq paths, separated with semicolons (required).
             Paths may be globs. Example: path/to/dir/**.fastq
  --reference_genome
             Path to STAR index as a tar.gz file (required).
  --transcriptome_annotation
             Path to GTF annotation file (required).
  --output   Path to an output directory (required).
  
Parameters (Batch mode):
  --csv      A csv file containing columns 'id', 'input' (required).
  --reference_genome
             Path to STAR index as a tar.gz file (required).
  --transcriptome_annotation
             Path to GTF annotation file (required).
  --output   Path to an output directory (required).
"""
    exit 0
  }


  if (has_param("input") == has_param("csv")) {
    exit 1, "ERROR: Please provide either an --input parameter or a --csv parameter"
  }
  
  check_required_param("reference_genome", "STAR index as a tar.gz file")
  check_required_param("transcriptome_annotation", "to GTF annotation file")
  check_required_param("output", "where output files will be published")

  if (has_param("csv")) {
    input_ch = Channel.fromPath(params.csv)
      | splitCsv(header: true, sep: ",")
  } else {
    input_ch = Channel.value( params.subMap(["id", "input"]) )
  }

  def reference_genome = file(params.reference_genome)
  def transcriptome_annotation = file(params.transcriptome_annotation)

  input_ch
    | map { li ->
      // process input
      if (li.containsKey("input") && li.input) {
        input_path = li.input.split(";").collect { path -> 
          file(has_param("csv") ? getChild(params.csv, path) : path)
        }.flatten()
      } else {
        exit 1, has_param("csv") ? 
          "ERROR: The provided csv file should contain an 'input' column" : 
          "ERROR: Please specify an '--input' parameter"
      }

      // process id
      if (li.containsKey("id") && li.id) {
        id_value = li.id
      } else if (!has_param("csv")) {
        id_value = "run"
      } else {
        exit 1, "ERROR: The provided csv file should contain an 'id' column"
      }
      [ id_value, [ input: input_path, reference_genome: reference_genome, transcriptome_annotation: transcriptome_annotation], params ]
    }
    | view { "before run_wf: ${it[0]} - ${it[1]}" }
    | run_wf
    | view { "after run_wf: ${it[0]} - ${it[1]}" }
    | map { overrideOptionValue(it, "publish", "output", "${params.output}/${it[0]}.h5ad") }
    | publish
}

/* BD Rhapsody WTA - common workflow
 * 
 * consumed params:
 *   id:                            a sample id for one or more fastq files
 *   data:
 *     input:                       one or more fastq paths, separated with semicolons, paths may be globs
 *     reference_genome:            a path to STAR index as a tar.gz file
 *     transcriptome_annotation:    a path to GTF annotation file
 *   output                         a publish dir for the output h5ad files
 * output format:               [ id, h5ad, params ]
 *   value id:                      a sample id for one or more fastq files
 *   value h5ad:                    h5ad object of mapped fastq reads
 *   value params:                  the params object, which may already have sample specific overrides
 */
workflow run_wf {
  take:
  input_ch

  main:
  output_ch = input_ch
    // Step 1: group fastq files per lane
    | flatMap { tup ->
      id = tup[0]
      data = tup[1]
      params = tup[2]

      // preproc input
      input = data.remove("input")
      if (input instanceof Path) {
        input = [ input ]
      }

      input_with_new_ids = input.collect { file ->
        new_id = file.name.replaceAll("[^a-zA-Z0-9]R[12]_*\\.fastq\\.gz\$", "")
        [ new_id, file ]
      }
      new_ids = input_with_new_ids.collect{it[0]}.unique()
      new_ids.collect { new_id -> 
        new_input = input_with_new_ids.findAll{it[0] == new_id}.collect{it[1]}
        assert new_input.size() == 2 : "Number of fastqs for id '$new_id' should be two. Found: ${new_input}"

        [ new_id, [ input: new_input ] + data, params + [ tuple_orig_id: id ] ]
      }
    }

    // Step 2: run BD rhapsody WTA
    | view { "running_bd_rhapsody: [${it[0]}, ${it[1]}] (orig_id: ${it[2].tuple_orig_id})" }
    | bd_rhapsody_wta

    // Step 3: group outputs per sample
    | map { id, input, params ->
      def origId = params.tuple_orig_id
      [ origId, input ]
    }
    | groupTuple()

    // Step 4: convert to h5ad
    | map { id, input -> [ id, input, params ]}
    | view { "converting_to_h5ad: [${it[0]}, ${it[1]}]" }
    | from_bdrhap_to_h5ad

  emit:
  output_ch
}


/* BD Rhapsody WTA - Integration testing
 */
workflow test_wf {
  
  output_ch =
    Channel.value(
      [
        "foo",
        [
          input: file(params.rootDir + "/resources_test/bd_rhapsody_wta_test/raw/*.fastq.gz"),
          reference_genome: file(params.rootDir + "/resources_test/bd_rhapsody_wta_test/raw/GRCh38-PhiX-gencodev29-20181205.tar.gz"),
          transcriptome_annotation: file(params.rootDir + "/resources_test/bd_rhapsody_wta_test/raw/gencodev29-20181205.gtf")
        ],
        params
      ]
    )
    | view { "Input: [${it[0]}, ${it[1]}, params]" }
    | run_wf
    | view { output ->
      assert output.size() == 3 : "outputs should contain three elements; [id, file, params]"
      assert output[1].toString().endsWith(".h5ad") : "Output file should be a h5ad file. Found: ${output[1]}"
      "Output: [${output[0]}, ${output[1]}, params]"
    }
    | toList()
    | map { output_list ->
      assert output_list.size() == 1 : "output channel should contain one event"
      assert output_list[0][0] == "foo" : "Output ID should be same as input ID"
    }
    //| check_format(args: {""}) // todo: check whether output h5mu has the right slots defined
}