#!/usr/bin/env python
from __future__ import absolute_import, division

from dials.framework import interface

class ScalingModelIface(interface.Interface):
    '''
    The interface definition for a scaling model.
    '''
    scope = "scaling"
    name = 'scaling_model'

    @classmethod
    def factory(cls):
        ''' Get the factory. '''
        pass

    @staticmethod
    def from_dict(d):
        ''' Get from dictionary. '''
        pass

class AimlessScalingModelExt(ScalingModelIface):
  ''' An extension class implementing a scaling model. '''

  name = 'aimless'

  @classmethod
  def factory(cls):
    '''returns the scaling Model Factory'''
    from dials.algorithms.scaling.model.scaling_model_factory import \
      AimlessSMFactory
    return AimlessSMFactory

  @classmethod
  def scaler(cls):
    '''returns the scaler factory'''
    from dials.algorithms.scaling.scaler import AimlessScaler
    return AimlessScaler

  @staticmethod
  def from_dict(d):
    '''creates a scaling model from a dict'''
    from dials.algorithms.scaling.model.model import \
      AimlessScalingModel
    return AimlessScalingModel.from_dict(d)

class KBScalingModelExt(ScalingModelIface):
  ''' An extension class implementing a scaling model. '''

  name = 'KB'

  @classmethod
  def factory(cls):
    '''returns the scaling Model Factory'''
    from dials.algorithms.scaling.model.scaling_model_factory import \
      KBSMFactory
    return KBSMFactory

  @classmethod
  def scaler(cls):
    '''returns the scaler factory'''
    from dials.algorithms.scaling.scaler import KBScaler
    return KBScaler

  @staticmethod
  def from_dict(d):
    '''creates a scaling model from a dict'''
    from dials.algorithms.scaling.model.model import KBScalingModel
    return KBScalingModel.from_dict(d)

class XscaleScalingModelExt(ScalingModelIface):
  ''' An extension class implementing a scaling model. '''

  name = 'xscale'

  @classmethod
  def factory(cls):
    '''returns the scaling Model Factory'''
    from dials.algorithms.scaling.model.scaling_model_factory import \
      XscaleSMFactory
    return XscaleSMFactory

  @classmethod
  def scaler(cls):
    '''returns the scaler factory'''
    from dials.algorithms.scaling.scaler import XscaleScaler
    return XscaleScaler

  @staticmethod
  def from_dict(d):
    '''creates a scaling model from a dict'''
    from dials.algorithms.scaling.model.model import XscaleScalingModel
    return XscaleScalingModel.from_dict(d)
