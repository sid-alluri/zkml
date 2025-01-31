# Oggn
import onnx
import numpy as np
import msgpack
from onnx import numpy_helper
import argparse


# Helper Functions
def get_shape(container, node_id):
  dim = container.__getitem__(node_id).type.tensor_type.shape.dim
  dim_list = list()
  for i in range(len(dim)):
    dim_list.append(int(dim.pop(0).dim_value))
  return dim_list

def get_output_dim(node_id, graph):
  model_output = graph.output
  model_valueinfo = graph.value_info
  if node_id == len(graph.node) - 1:
    output_dim = get_shape(model_output, 0)
  else:
    output_dim = get_shape(model_valueinfo, node_id)
  buf = output_dim[1]
  output_dim.remove(output_dim[1])
  output_dim.append(buf)
  return output_dim

def get_input_dim(layers):
  return layers[-1]['out_shapes'][0]

def create_wbdim_map(graph):
  wbdim_map = {}
  for init in graph.initializer:
    n = init.name
    dim = init.dims
    l = [int(_) for _ in init.dims]
    if len(l)>1: ##Check here while adding more OPS
      buf = l[1]
      l.remove(l[1])
      l.append(buf)
    wbdim_map[n] = l
  return wbdim_map

class Converter():
  def __init__( self, model_path, scale_factor, k, num_cols, num_randoms, use_selectors, commit, expose_output):
    self.model = onnx.load(model_path)
    self.scale_factor = scale_factor
    self.k = k
    self.num_cols = num_cols
    self.num_randoms = num_randoms
    self.use_selectors = use_selectors
    self.commit = commit
    self.expose_output = expose_output

  def to_dict(self):
    model_graph = self.model.graph
    model_input = model_graph.input
    model_nodes = model_graph.node
    model_init = self.model.graph.initializer
   
    layers = list()
    tensors = list()
    commit_before = list()
    commit_after = list()
    wbdim_map = create_wbdim_map(model_graph)

    node_id = 0
    init_id = 0
    wb_ids = []
    fullc_wb_ids = []

    for node in model_nodes:
      if node.op_type == "Conv":
        layer_type = "Conv2D"
        inp_idxes = []
        inp_idxes.append(init_id)
        for i in range(init_id+1,init_id+len(node.input)):
          inp_idxes.append(i)
          wb_ids.append(i)
        out_idxes = [init_id+len(node.input)]
        init_id = out_idxes[0] 
        inputs_dim = []
        for input in node.input:
          if input in wbdim_map.keys():
            inputs_dim.append(wbdim_map[input])
          elif input not in wbdim_map.keys() and node_id == 0:
            inp_dim = get_shape(model_input, 0)
            inputs_dim.append(inp_dim)
          elif input not in wbdim_map.keys() and node_id != 0:
            inp_dim = get_input_dim(layers)
            inputs_dim.append(inp_dim)
        output_dim = get_output_dim(node_id, model_graph)
        node_attr = node.attribute
        kernel = [np.int64(_).item() for _ in node_attr.pop(0).ints]
        stride = [np.int64(_).item() for _ in node_attr.pop(0).ints]
        padding = str(node_attr.pop(0).s)
        if padding == b'SAME_UPPER':
          padding_code = 1
        else:
          padding_code = 0 
        params = [0, padding_code, 1, stride[0], stride[1]] # 1 == ReLU 
      elif node.op_type == "MaxPool":
        layer_type = "MaxPool2D"
        inp_idxes = []
        inp_idxes.append(init_id)
        for i in range(init_id+1,init_id+len(node.input)):
          inp_idxes.append(i)
          wb_ids.append(i)
        out_idxes = [init_id+len(node.input)]
        init_id = out_idxes[0] 
        inputs_dim = []
        for input in node.input:
          if input in wbdim_map.keys():
            inputs_dim.append(wbdim_map[input])
          elif input not in wbdim_map.keys() and node_id == 0:
            inp_dim = get_shape(model_input, 0)
            inputs_dim.append(inp_dim)
          elif input not in wbdim_map.keys() and node_id != 0:
            inp_dim = get_input_dim(layers)
            inputs_dim.append(inp_dim)
        output_dim = get_output_dim(node_id, model_graph)
        node_attr = node.attribute
        kernel = [np.int64(_).item() for _ in node_attr.pop(0).ints]
        stride = [np.int64(_).item() for _ in node_attr.pop(0).ints]
        params = [kernel[0], kernel[1], stride[0], stride[1]]

      elif node.op_type == "Relu":
        layer_type = "ReLU"
        inp_idxes = []
        inp_idxes.append(init_id)
        for i in range(init_id+1,init_id+len(node.input)):
          inp_idxes.append(i)
          wb_ids.append(i)
        out_idxes = [init_id+len(node.input)]
        init_id = out_idxes[0]         
        inputs_dim = []
        for input in node.input:
          if input in wbdim_map.keys():
                inputs_dim.append(wbdim_map[input])
          elif input not in wbdim_map.keys() and node_id == 0:
                inp_dim = get_shape(model_input, 0)
                inputs_dim.append(inp_dim)
          elif input not in wbdim_map.keys() and node_id != 0:
                inp_dim = get_input_dim(layers)
                inputs_dim.append(inp_dim)

        output_dim = get_output_dim(node_id, model_graph)
        params = []
        
      elif node.op_type == "Reshape":
        layer_type = "Reshape"
        inputs_dim = []
        inp_idxes = []
        inp_idxes.append(init_id)
        for i in range(init_id+1,init_id+len(node.input)):
          inp_idxes.append(i)
          # wb_ids.append(i) // No wb for reshape
        out_idxes = [init_id+len(node.input)]
        init_id = out_idxes[0] 
    
        for input in node.input:
          if input in wbdim_map.keys():
            inputs_dim.append(wbdim_map[input])
          elif input not in wbdim_map.keys() and node_id == 0:
            inp_dim = get_shape(model_input, 0)
            inputs_dim.append(inp_dim)
          elif input not in wbdim_map.keys() and node_id != 0:
            inp_dim = get_input_dim(layers)
            inputs_dim.append(inp_dim)
        output_dim = get_output_dim(node_id, model_graph)
        params = []

      elif node.op_type == "Gemm":
        layer_type = "FullyConnected"
        inputs_dim = []
        inp_idxes = []
        inp_idxes.append(init_id)
        for i in range(init_id+1,init_id+len(node.input)):
          inp_idxes.append(i)
          wb_ids.append(i)
          fullc_wb_ids.append(i)
        out_idxes = [init_id+len(node.input)]
        init_id = out_idxes[0] 

        for input in node.input:
          if input in wbdim_map.keys():
            inputs_dim.append(wbdim_map[input][::-1])  #Specific to FullyConnected, to match with rest of zkml
          elif input not in wbdim_map.keys() and node_id == 0:
            inp_dim = get_shape(model_input, 0)
            inputs_dim.append(inp_dim)
          elif input not in wbdim_map.keys() and node_id != 0:
            inp_dim = get_input_dim(layers)
            inputs_dim.append(inp_dim)
      
        output_dim = get_output_dim(node_id, model_graph)
        params = [0]
      else:
        node_id += 1
        continue
      layer = {
        "layer_type": layer_type,
        "params": params,
        "inp_shapes": inputs_dim,
        "inp_idxes": inp_idxes, 
        "out_idxes": out_idxes, 
        "out_shapes": [output_dim],
        "mask": []
      }
      layers.append(layer)
      node_id += 1

    # Converting W&B
    init_ct = 0
    for init in model_init:
      if init.data_type == 1: # Tried avoiding unwanted init with init_id, but not working, used data_type instead
        shape = [np.int64(dim).item() for dim in init.dims]
        if len(shape)>1 :
          buf = shape[1]
          shape.remove(shape[1])
          shape.append(buf) 
        if wb_ids[init_ct] in fullc_wb_ids: ## Not good
          shape = shape[::-1]
        for i in range(1,len(fullc_wb_ids),2):
          if wb_ids[init_ct] == fullc_wb_ids[i]:
            shape = [shape[0]]
        raw_data = numpy_helper.to_array(init).ravel().tolist()  ## Orientation of ravel ?
        data = []
        for i in raw_data:
          if isinstance(i, float):
            buf = np.int64(np.round(i * self.scale_factor)).item()
            data.append(buf)
          elif isinstance(i, int):
            buf = np.int64(i).item()
        tensor = {"idx": wb_ids[init_ct] , 
                "shape": shape, 
                "data": data
                }
        tensors.append(tensor)
        init_ct+=1    
    final_dict = {
      'global_sf': self.scale_factor,
      'k': self.k,
      'num_cols': self.num_cols,
      'inp_idxes': [0], 
      'out_idxes': [init_id], 
      'layers': layers,  
      'tensors': tensors,
      'use_selectors': self.use_selectors,
      'commit_before': commit_before,
      'commit_after': commit_after,
      'num_random': self.num_randoms,
    }
    return final_dict

  def to_msgpack(self):
    final_dict = self.to_dict()
    model_packed = msgpack.packb(final_dict, use_bin_type=True)
    final_dict['tensors']=[]
    config_packed = msgpack.packb(final_dict, use_bin_type=True)
    return model_packed, config_packed
  
def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--model', type=str, required=True)
  parser.add_argument('--model_output', type=str, required=True)
  parser.add_argument('--config_output', type=str, required=True)
  parser.add_argument('--scale_factor', type=int, default=2**8)
  parser.add_argument('--k', type=int, default=19)
  parser.add_argument('--eta', type=float, default=0.001)
  parser.add_argument('--num_cols', type=int, default=6)
  parser.add_argument('--use_selectors', action=argparse.BooleanOptionalAction, required=False, default=True)
  parser.add_argument('--commit', action=argparse.BooleanOptionalAction, required=False, default=False)
  parser.add_argument('--expose_output', action=argparse.BooleanOptionalAction, required=False, default=True)
  parser.add_argument('--num_randoms', type=int, default=20001)
  args = parser.parse_args()

  converter = Converter(
    args.model,
    args.scale_factor,
    args.k,
    args.num_cols,
    args.num_randoms,
    args.use_selectors,
    args.commit,
    args.expose_output,
  )

  model_packed, config_packed = converter.to_msgpack()

  if model_packed is None:
    raise Exception('Failed to convert model')

  with open(args.model_output, 'wb') as f:
    f.write(model_packed)
  with open(args.config_output, 'wb') as f:
    f.write(config_packed)

if __name__ == '__main__':
  main()

