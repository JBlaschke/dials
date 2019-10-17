from __future__ import absolute_import, division, print_function

# DIALS_ENABLE_COMMAND_LINE_COMPLETION

import concurrent.futures
import copy
import logging
import sys

import iotbx.phil
from dxtbx.model.experiment_list import ExperimentList
from dxtbx.imageset import ImageSetFactory
from dials.algorithms.indexing import indexer
from dials.algorithms.indexing import DialsIndexError
from dials.array_family import flex
from dials.util.slice import slice_reflections
from dials.util.options import OptionParser
from dials.util.options import flatten_reflections
from dials.util.options import flatten_experiments
from dials.util import log
from dials.util.version import dials_version

logger = logging.getLogger("dials.command_line.index")


help_message = """

This program attempts to perform autoindexing on strong spots output by the
program dials.find_spots. The program is called with a "imported.expt" file
(as generated by dials.import) and a "strong.refl" file (as generated by
dials.find_spots). If one or more lattices are identified given the input
list of strong spots, then the crystal orientation and experimental geometry
are refined to minimise the differences between the observed and predicted
spot centroids. The program will output an "indexed.expt" file which
is similar to the input "imported.expt" file, but with the addition of the
crystal model(s), and an "indexed.refl" file which is similar to the input
"strong.refl" file, but with the addition of miller indices and predicted
spot centroids.

dials.index provides both one-dimensional and three-dimensional fast Fourier
transform (FFT) based methods. These can be chosen by setting the parameters
indexing.method=fft1d or indexing.method=fft3d. By default the program searches
for a primitive lattice, and then proceeds with refinement in space group P1.
If the unit_cell and space_group parameters are set, then the program will
only accept solutions which are consistent with these parameters. Space group
constraints will be enforced in refinement as appropriate.

Examples::

  dials.index imported.expt strong.refl

  dials.index imported.expt strong.refl unit_cell=37,79,79,90,90,90 space_group=P43212

  dials.index imported.expt strong.refl indexing.method=fft1d
"""


phil_scope = iotbx.phil.parse(
    """\
include scope dials.algorithms.indexing.indexer.phil_scope

indexing {

    include scope dials.algorithms.indexing.lattice_search.basis_vector_search_phil_scope

    image_range = None
      .help = "Range in images to slice a sequence. The number of arguments"
              "must be a factor of two. Each pair of arguments gives a range"
              "that follows C conventions (e.g. j0 <= j < j1) when slicing the"
              "reflections by observed centroid."
      .type = ints(size=2)
      .multiple = True

    joint_indexing = True
      .type = bool

}

include scope dials.algorithms.refinement.refiner.phil_scope

output {
  experiments = indexed.expt
    .type = path
  split_experiments = False
    .type = bool
  reflections = indexed.refl
    .type = path
  unindexed_reflections = None
    .type = path
  log = dials.index.log
    .type = str
}
""",
    process_includes=True,
)

# override default refinement parameters
phil_overrides = phil_scope.fetch(
    source=iotbx.phil.parse(
        """\
refinement {
    reflections {
        reflections_per_degree=100
    }
}
"""
    )
)

working_phil = phil_scope.fetch(sources=[phil_overrides])


def _index_experiments(experiments, reflections, params, known_crystal_models=None):
    idxr = indexer.Indexer.from_parameters(
        reflections,
        experiments,
        known_crystal_models=known_crystal_models,
        params=params,
    )
    idxr.index()
    idx_refl = copy.deepcopy(idxr.refined_reflections)
    idx_refl.extend(idxr.unindexed_reflections)
    return idxr.refined_experiments, idx_refl


def index(experiments, reflections, params):
    """
    Index the input experiments and reflections.

    Args:
        experiments: The experiments to index
        reflections (list): A list of reflection tables containing strong spots
        params: An instance of the indexing phil scope

    Returns:
        (tuple): tuple containing:
            experiments: The indexed experiment list
            reflections (dials.array_family.flex.reflection_table):
                The indexed reflections

    """
    if experiments.crystals()[0] is not None:
        known_crystal_models = experiments.crystals()
    else:
        known_crystal_models = None

    if len(reflections) == 0:
        raise ValueError("No reflection lists found in input")
    elif len(reflections) == 1:
        reflections[0]["imageset_id"] = reflections[0]["id"]
    elif len(reflections) > 1:
        assert len(reflections) == len(experiments)
        for i in range(len(reflections)):
            reflections[i]["imageset_id"] = flex.int(len(reflections[i]), i)
            if i > 0:
                reflections[0].extend(reflections[i])
    reflections = reflections[0]

    # If there are scan and goniometer objects present but the oscillation angle is zero
    # then expt.scan and expt.goniometer to None, as the behaviour of some downstream
    # algorithms depend on the presence/absence of these objects
    for expt in experiments:
        if (
            expt.goniometer is not None
            and expt.scan is not None
            and expt.scan.is_still()
        ):
            expt.imageset = ImageSetFactory.imageset_from_anyset(expt.imageset)
            expt.goniometer = None
            expt.scan = None

    if params.indexing.image_range:
        reflections = slice_reflections(reflections, params.indexing.image_range)

    if len(experiments) == 1 or params.indexing.joint_indexing:
        indexed_experiments, indexed_reflections = _index_experiments(
            experiments,
            reflections,
            copy.deepcopy(params),
            known_crystal_models=known_crystal_models,
        )
    else:
        indexed_experiments = ExperimentList()
        indexed_reflections = flex.reflection_table()

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=params.indexing.nproc
        ) as pool:
            futures = []
            for i_expt, expt in enumerate(experiments):
                refl = reflections.select(reflections["imageset_id"] == i_expt)
                refl["imageset_id"] = flex.size_t(len(refl), 0)
                futures.append(
                    pool.submit(
                        _index_experiments,
                        ExperimentList([expt]),
                        refl,
                        copy.deepcopy(params),
                        known_crystal_models=known_crystal_models,
                    )
                )

            for future in concurrent.futures.as_completed(futures):
                try:
                    idx_expts, idx_refl = future.result()
                except Exception as e:
                    print(e)
                else:
                    if idx_expts is None:
                        continue
                    for j_expt, _ in enumerate(idx_expts):
                        sel = idx_refl["id"] == j_expt
                        idx_refl["id"].set_selected(
                            sel, len(indexed_experiments) + j_expt
                        )
                    idx_refl["imageset_id"] = flex.size_t(len(idx_refl), i_expt)
                    indexed_reflections.extend(idx_refl)
                    indexed_experiments.extend(idx_expts)
    return indexed_experiments, indexed_reflections


def run(phil=working_phil, args=None):
    usage = "dials.index [options] models.expt strong.refl"

    parser = OptionParser(
        usage=usage,
        phil=phil,
        read_reflections=True,
        read_experiments=True,
        check_format=False,
        epilog=help_message,
    )

    params, options = parser.parse_args(args=args, show_diff_phil=False)

    # Configure the logging
    log.config(verbosity=options.verbose, logfile=params.output.log)
    logger.info(dials_version())

    # Log the diff phil
    diff_phil = parser.diff_phil.as_str()
    if diff_phil != "":
        logger.info("The following parameters have been modified:\n")
        logger.info(diff_phil)

    experiments = flatten_experiments(params.input.experiments)
    reflections = flatten_reflections(params.input.reflections)

    if len(experiments) == 0:
        parser.print_help()
        return

    try:
        indexed_experiments, indexed_reflections = index(
            experiments, reflections, params
        )
    except (DialsIndexError, ValueError) as e:
        sys.exit(str(e))

    # Save experiments
    if params.output.split_experiments:
        logger.info("Splitting experiments before output")
        indexed_experiments = ExperimentList(
            [copy.deepcopy(re) for re in indexed_experiments]
        )
    logger.info("Saving refined experiments to %s" % params.output.experiments)
    assert indexed_experiments.is_consistent()
    indexed_experiments.as_file(params.output.experiments)

    # Save reflections
    logger.info("Saving refined reflections to %s" % params.output.reflections)
    indexed_reflections.as_msgpack_file(filename=params.output.reflections)


if __name__ == "__main__":
    run()
