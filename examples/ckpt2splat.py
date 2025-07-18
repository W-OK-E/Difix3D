#!/usr/bin/env python3
"""
Convert checkpoint splat data to PLY format compatible with nerfstudio output.

The attributes need to be in the following format:
- 'means': vertex positions (N, 3)
- 'opacities': opacity values (N, 1) 
- 'quats': rotation quaternions (N, 4)
- 'scales': scale values (N, 3)
- 'sh0': base spherical harmonics (N, 3)
- 'shN': higher-order spherical harmonics (N, 45) - for degree 3 SH
"""

import numpy as np
import struct
import pickle
import torch
from pathlib import Path


def extract_data_from_ckpt(checkpoint_path):
    ckpt = torch.load(checkpoint_path,map_location='cpu')
    splats = ckpt['splats']
    N =splats['means'].shape[0]
    splats['opacities'] = splats['opacities'].reshape(N,1)
    splats['sh0'] = splats['sh0'].reshape(N,3)
    splats['shN'] = splats['shN'].reshape(N,45)
    return splats

def convert_checkpoint_to_ply(checkpoint_data, output_path):
    """
    Convert checkpoint dictionary to PLY format.
    
    Args:
        checkpoint_data: Dictionary containing 'means', 'opacities', 'quats', 'scales', 'sh0', 'shN'
        output_path: Path where to save the PLY file
    """
    
    # Extract data from checkpoint
    means = checkpoint_data['means']  # (N, 3) - x, y, z positions
    opacities = checkpoint_data['opacities']  # (N, 1) - opacity values
    quats = checkpoint_data['quats']  # (N, 4) - rotation quaternions
    scales = checkpoint_data['scales']  # (N, 3) - scale values
    sh0 = checkpoint_data['sh0']  # (N, 3) - base SH coefficients (f_dc_0, f_dc_1, f_dc_2)
    shN = checkpoint_data['shN']  # (N, 45) - higher order SH coefficients (f_rest_0 to f_rest_44)
    
    # Convert to numpy if tensors
    if isinstance(means, torch.Tensor):
        means = means.detach().cpu().numpy()
    if isinstance(opacities, torch.Tensor):
        opacities = opacities.detach().cpu().numpy()
    if isinstance(quats, torch.Tensor):
        quats = quats.detach().cpu().numpy()
    if isinstance(scales, torch.Tensor):
        scales = scales.detach().cpu().numpy()
    if isinstance(sh0, torch.Tensor):
        sh0 = sh0.detach().cpu().numpy()
    if isinstance(shN, torch.Tensor):
        shN = shN.detach().cpu().numpy()
    
    # Ensure correct shapes
    if means.ndim == 1:
        means = means.reshape(-1, 3)
    if opacities.ndim == 1:
        opacities = opacities.reshape(-1, 1)
    if quats.ndim == 1:
        quats = quats.reshape(-1, 4)
    if scales.ndim == 1:
        scales = scales.reshape(-1, 3)
    if sh0.ndim == 1:
        sh0 = sh0.reshape(-1, 3)
    if shN.ndim == 1:
        shN = shN.reshape(-1, 45)
    
    num_vertices = means.shape[0]
    
    # Verify all arrays have the same number of vertices
    assert opacities.shape[0] == num_vertices, f"Opacities shape mismatch: {opacities.shape[0]} vs {num_vertices}"
    assert quats.shape[0] == num_vertices, f"Quats shape mismatch: {quats.shape[0]} vs {num_vertices}"
    assert scales.shape[0] == num_vertices, f"Scales shape mismatch: {scales.shape[0]} vs {num_vertices}"
    assert sh0.shape[0] == num_vertices, f"SH0 shape mismatch: {sh0.shape[0]} vs {num_vertices}"
    assert shN.shape[0] == num_vertices, f"SHN shape mismatch: {shN.shape[0]} vs {num_vertices}"
    
    print(f"Converting {num_vertices} vertices to PLY format...")
    
    # Create PLY header
    header = [
        "ply",
        "format binary_little_endian 1.0",
        "comment Generated by checkpoint converter",
        "comment Vertical Axis: z",
        f"element vertex {num_vertices}",
        "property float x",
        "property float y", 
        "property float z",
        "property float nx",
        "property float ny",
        "property float nz",
        "property float f_dc_0",
        "property float f_dc_1",
        "property float f_dc_2"
    ]
    
    # Add f_rest properties (45 higher-order SH coefficients)
    for i in range(45):
        header.append(f"property float f_rest_{i}")
    
    # Add opacity, scale, and rotation properties
    header.extend([
        "property float opacity",
        "property float scale_0",
        "property float scale_1", 
        "property float scale_2",
        "property float rot_0",
        "property float rot_1",
        "property float rot_2",
        "property float rot_3",
        "end_header"
    ])
    
    # Write PLY file
    with open(output_path, 'wb') as f:
        # Write header
        header_str = '\n'.join(header) + '\n'
        f.write(header_str.encode('ascii'))
        
        # Write binary data
        for i in range(num_vertices):
            # Position (x, y, z)
            f.write(struct.pack('<fff', means[i, 0], means[i, 1], means[i, 2]))
            
            # Normals (nx, ny, nz) - set to zero like in the original
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            
            # Base SH coefficients (f_dc_0, f_dc_1, f_dc_2)
            f.write(struct.pack('<fff', sh0[i, 0], sh0[i, 1], sh0[i, 2]))
            
            # Higher-order SH coefficients (f_rest_0 to f_rest_44)
            for j in range(45):
                f.write(struct.pack('<f', shN[i, j]))
            
            # Opacity
            f.write(struct.pack('<f', opacities[i, 0]))
            
            # Scales (scale_0, scale_1, scale_2)
            f.write(struct.pack('<fff', scales[i, 0], scales[i, 1], scales[i, 2]))
            
            # Rotation quaternion (rot_0, rot_1, rot_2, rot_3)
            f.write(struct.pack('<ffff', quats[i, 0], quats[i, 1], quats[i, 2], quats[i, 3]))
    
    print(f"Successfully converted checkpoint to PLY: {output_path}")
    print(f"File size: {Path(output_path).stat().st_size / (1024*1024):.2f} MB")

def load_checkpoint(checkpoint_path):
    """
    Load checkpoint from file. Supports both pickle and torch formats.
    """
    checkpoint_path = Path(checkpoint_path)
    
    if checkpoint_path.suffix == '.pkl':
        with open(checkpoint_path, 'rb') as f:
            return pickle.load(f)
    elif checkpoint_path.suffix in ['.pt', '.pth']:
        return torch.load(checkpoint_path, map_location='cpu')
    else:
        # Try to load as pickle first, then torch
        try:
            with open(checkpoint_path, 'rb') as f:
                return pickle.load(f)
        except:
            return torch.load(checkpoint_path, map_location='cpu')

def main():
    """
    Example usage
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert checkpoint to PLY format')
    parser.add_argument('--checkpoint_path', help='Path to checkpoint file')
    parser.add_argument('--output_path', help='Output PLY file path')
    parser.add_argument('--show-stats', action='store_true', help='Show statistics of the data')
    
    args = parser.parse_args()
    # print(f"Available keys in checkpoint: {list(checkpoint.keys())}")
    splat_data =  extract_data_from_ckpt(args.checkpoint_path)
    # Verify required keys are present
    required_keys = ['means', 'opacities', 'quats', 'scales', 'sh0', 'shN']
    missing_keys = [key for key in required_keys if key not in splat_data]
    if missing_keys:
        print(f"Warning: Missing required keys: {missing_keys}")
        return
    
    # Show statistics if requested
    # if args.show_stats:
    #     print("\nData statistics:")
    #     for key in required_keys:
    #         data = checkpoint[key]
    #         if isinstance(data, torch.Tensor):
    #             data = data.detach().cpu().numpy()
    #         print(f"{key}: shape={data.shape}, min={data.min():.6f}, max={data.max():.6f}, mean={data.mean():.6f}")
    
    # Convert to PLY
    convert_checkpoint_to_ply(splat_data, args.output_path)


main()