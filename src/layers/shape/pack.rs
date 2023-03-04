use std::{collections::HashMap, rc::Rc};

use halo2_proofs::{circuit::Layouter, halo2curves::FieldExt, plonk::Error};
use ndarray::{concatenate, Axis};

use crate::{
  gadgets::gadget::{GadgetConfig, GadgetType},
  layers::layer::{AssignedTensor, CellRc, GadgetConsumer},
};

use super::super::layer::{Layer, LayerConfig};

pub struct PackChip {}

impl<F: FieldExt> Layer<F> for PackChip {
  fn forward(
    &self,
    _layouter: impl Layouter<F>,
    tensors: &Vec<AssignedTensor<F>>,
    _constants: &HashMap<i64, CellRc<F>>,
    _gadget_config: Rc<GadgetConfig>,
    layer_config: &LayerConfig,
  ) -> Result<Vec<AssignedTensor<F>>, Error> {
    let axis = layer_config.layer_params[0] as usize;
    if axis != 0 {
      panic!("Pack only supports axis=0");
    }

    let expanded = tensors
      .into_iter()
      .map(|x| x.clone().insert_axis(Axis(axis)))
      .collect::<Vec<_>>();
    let views = expanded.iter().map(|x| x.view()).collect::<Vec<_>>();

    let out = concatenate(Axis(axis), views.as_slice()).unwrap();

    Ok(vec![out])
  }
}

impl GadgetConsumer for PackChip {
  fn used_gadgets(&self) -> Vec<GadgetType> {
    vec![]
  }
}