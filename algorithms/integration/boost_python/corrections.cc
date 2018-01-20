/*
 * corrections.cc
 *
 *  Copyright (C) 2013 Diamond Light Source
 *
 *  Author: James Parkhurst
 *
 *  This code is distributed under the BSD license, a copy of which is
 *  included in the root directory of this package.
 */
#include <boost/python.hpp>
#include <boost/python/def.hpp>
#include <dials/algorithms/integration/corrections.h>

using namespace boost::python;

namespace dials { namespace algorithms { namespace boost_python {



  void export_corrections() {

    def("lp_correction", &lp_correction, (
          arg("s0"),
          arg("pn"),
          arg("pf"),
          arg("m2"),
          arg("s1")));

    def("dqe_correction", &dqe_correction, (
          arg("mu"),
          arg("t0"),
          arg("s1"),
          arg("n")));

    class_<Corrections>("Corrections", no_init)
      .def(init< const BeamBase&,
                 const Goniometer&,
                 const Detector& >())
      .def("lp", &Corrections::lp, (
            arg("s1")))
      .def("dqe", &Corrections::dqe, (
            arg("s1"),
            arg("panel")))
      ;

    class_<CorrectionsMulti>("CorrectionsMulti")
      .def("append", &CorrectionsMulti::push_back)
      .def("__len__", &CorrectionsMulti::size)
      .def("lp", &CorrectionsMulti::lp)
      .def("dqe", &CorrectionsMulti::dqe)
      ;
  }

}}} // namespace = dials::algorithms::boost_python
