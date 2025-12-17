"""
Generator for Pypeec geometry.yaml files for Microstrip devices.
This script allows defining arbitrary top-layer rectangular patterns and 
automatically generates the corresponding substrate and ground planes.
"""

import yaml
import numpy as np

class SandwichMicrostripGenerator:
    def __init__(self, resolution=1.0e-6, margin=10.0e-6, thickness_ground=1.0e-6, thickness_substrate=10.0e-6, thickness_trace=1.0e-6):
        """
        Initialize the generator.

        Parameters
        ----------
        resolution : float
            Isotropic voxel resolution (dx, dy, dz) in meters.
        margin : float
            Margin to extend the substrate/ground beyond the trace bounding box.
        thickness_ground : float
            Thickness of the ground plane (layer_gnd) in meters.
        thickness_substrate : float
            Thickness of the dielectric substrate (layer_sub) in meters.
        thickness_trace : float
            Thickness of the top trace layer (layer_top) in meters.
        """
        self.res = float(resolution)
        self.margin = float(margin)
        
        # Calculate layer thicknesses in voxels
        self.n_gnd = max(1, int(round(thickness_ground / self.res)))
        self.n_sub = max(1, int(round(thickness_substrate / self.res)))
        self.n_top = max(1, int(round(thickness_trace / self.res)))
        
        # Storage for shapes
        # Structure: {"domain_name": [list of shape dicts]}
        self.shapes = {
            "trace": [],
            "src": [],
            "sink": []
        }
        
        # Bounding box tracking for the top layer pattern
        # [min_x, min_y, max_x, max_y]
        self.bounds = [float('inf'), float('inf'), float('-inf'), float('-inf')]
        self.auto_bounds = True  # Flag to control if we use auto-calculated bounds
        
        # Conflict Rules
        self.conflict_rules = [
            {"domain_resolve": ["trace"], "domain_keep": ["src", "sink"]},
            {"domain_resolve": ["ground"], "domain_keep": ["substrate"]},
            {"domain_resolve": ["substrate"], "domain_keep": ["trace", "src", "sink"]}
        ]
        
        # Integrity Rules
        self.domain_connected = {
            "signal": {"domain_group": [["trace"], ["src", "sink"]], "connected": True},
            "ground": {"domain_group": [["ground"]], "connected": True}
        }

    def set_thickness(self, ground=None, substrate=None, trace=None):
        """Set layer thicknesses in meters."""
        if ground: self.n_gnd = max(1, int(round(ground / self.res)))
        if substrate: self.n_sub = max(1, int(round(substrate / self.res)))
        if trace: self.n_top = max(1, int(round(trace / self.res)))

    def _update_bounds(self, x_min, y_min, x_max, y_max):
        if self.auto_bounds:
            self.bounds[0] = min(self.bounds[0], x_min)
            self.bounds[1] = min(self.bounds[1], y_min)
            self.bounds[2] = max(self.bounds[2], x_max)
            self.bounds[3] = max(self.bounds[3], y_max)

    def _make_rect_shape(self, cx, cy, w, h, layer):
        """Create a Pypeec polygon shape definition for a rectangle."""
        hw = w / 2.0
        hh = h / 2.0
        
        # Calculate corners
        x1, y1 = cx - hw, cy - hh
        x2, y2 = cx + hw, cy - hh
        x3, y3 = cx + hw, cy + hh
        x4, y4 = cx - hw, cy + hh
        
        # Update bounds for auto-sizing substrate
        self._update_bounds(x1, y1, x3, y3)
        
        return {
            "shape_layer": [layer],
            "shape_operation": "add",
            "shape_type": "polygon",
            "shape_data": {
                "buffer": 0.0,
                "coord_shell": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
                "coord_holes": []
            }
        }

    def add_rect(self, x, y, w, h, domain="trace", layer="layer_top"):
        """
        Add a rectangle to a specific domain group.
        
        In Pypeec, 'geometry_shape' keys represent logical domains (groups).
        All shapes added to the same 'domain' key will be considered part 
        of the same group (e.g. connected component).
        
        Parameters
        ----------
        x, y : float
            Center coordinates of the rectangle.
        w, h : float
            Width and Height of the rectangle.
        domain : str
            The logical domain name (group) this shape belongs to.
            Examples: 'trace', 'src', 'sink', 'coupling_cap'.
            Shapes with the same domain name are grouped together.
        layer : str
            The layer to place the rectangle on. 
            Options: 'layer_top', 'layer_sub', 'layer_gnd'.
        """
        shape = self._make_rect_shape(x, y, w, h, layer)
        
        if domain not in self.shapes:
            self.shapes[domain] = []
        self.shapes[domain].append(shape)

    def set_manual_bounds(self, x_min, y_min, x_max, y_max):
        """
        Manually set the bounding box for substrate/ground generation.
        If this is called, the auto-calculation from added shapes is ignored.
        
        Parameters
        ----------
        x_min, y_min, x_max, y_max : float
            Coordinates of the bounding box.
        """
        self.bounds = [x_min, y_min, x_max, y_max]
        self.auto_bounds = False

    def generate_yaml_data(self):
        """Construct the dictionary for geometry.yaml."""
        
        # 1. Calculate Substrate/Ground Plate Dimensions
        if self.auto_bounds and self.bounds[0] == float('inf'):
            # No shapes added and no manual bounds, default to a small square
            bx_min, by_min, bx_max, by_max = 0, 0, 10*self.res, 10*self.res
        else:
            bx_min, by_min, bx_max, by_max = self.bounds

        # Apply margin
        gx_min = bx_min - self.margin
        gy_min = by_min - self.margin
        gx_max = bx_max + self.margin
        gy_max = by_max + self.margin
        
        ground_coords = [[gx_min, gy_min], [gx_max, gy_min], [gx_max, gy_max], [gx_min, gy_max]]
        
        # 2. Create Ground and Substrate Shapes
        # Ground
        ground_shape = {
            "shape_layer": ["layer_gnd"],
            "shape_operation": "add",
            "shape_type": "polygon",
            "shape_data": {
                "buffer": 0.0,
                "coord_shell": ground_coords,
                "coord_holes": []
            }
        }
        
        # Substrate
        substrate_shape = {
            "shape_layer": ["layer_sub"],
            "shape_operation": "add",
            "shape_type": "polygon",
            "shape_data": {
                "buffer": 0.0,
                "coord_shell": ground_coords,
                "coord_holes": []
            }
        }
        
        # 3. Assemble Geometry Shapes
        geometry_shape = {
            "ground": [ground_shape],
            "substrate": [substrate_shape]
        }
        # Add user-defined top layer shapes
        for domain, shape_list in self.shapes.items():
            if shape_list: # Only add if not empty
                geometry_shape[domain] = shape_list

        # 4. Build Final Structure
        data = {
            "mesh_type": "shape",
            "data_voxelize": {
                "param": {
                    "dx": self.res, "dy": self.res, "dz": self.res,
                    "cz": 0.0,
                    "simplify": 1.0e-8,
                    "construct": None,
                    "xy_min": None, "xy_max": None
                },
                "layer_stack": [
                    {"n_layer": self.n_gnd, "tag_layer": "layer_gnd"},
                    {"n_layer": self.n_sub, "tag_layer": "layer_sub"},
                    {"n_layer": self.n_top, "tag_layer": "layer_top"},
                ],
                "geometry_shape": geometry_shape
            },
            "data_point": {
                "check_cloud": False,
                "filter_cloud": False,
                "pts_cloud": []
            },
            "data_resampling": {
                "use_reduce": False,
                "use_resample": False,
                "resampling_factor": [1, 1, 1]
            },
            "data_conflict": {
                "resolve_rules": True,
                "resolve_random": False,
                "conflict_rules": self.conflict_rules
            },
            "data_integrity": {
                "check_integrity": True,
                "domain_connected": self.domain_connected,
                "domain_adjacent": {}
            }
        }
        return data

    def write_file(self, filename):
        """Generate data and write to a YAML file."""
        data = self.generate_yaml_data()
        
        # Use sort_keys=False to maintain logical order if using Python 3.7+
        with open(filename, 'w') as f:
            yaml.dump(data, f, default_flow_style=None, sort_keys=False)
        print(f"Geometry saved to {filename}")

# Example Usage
if __name__ == "__main__":
    gen = SandwichMicrostripGenerator(
        resolution=0.5e-6, 
        margin=15.0e-6,
        thickness_ground=1.0e-6,
        thickness_substrate=5.0e-6,
        thickness_trace=1.0e-6
    )
    
    # Define dimensions
    w = 4.0e-6
    
    # Example 1: A single connected trace made of two segments
    # Both segments are assigned to the 'trace' domain, so they will be grouped together.
    gen.add_rect(x=10e-6, y=0, w=20e-6, h=w, domain="trace")
    gen.add_rect(x=30e-6, y=2e-6, w=20e-6, h=w, domain="trace") # Slightly offset, still 'trace'
    
    # Example 2: A separate isolated island (e.g. for coupling)
    # This is assigned to a DIFFERENT domain name 'island', so it forms a separate group.
    gen.add_rect(x=30e-6, y=-10e-6, w=10e-6, h=w, domain="island")

    # Add Ports (terminals)
    # These are distinct logical domains from the trace itself
    gen.add_rect(x=0, y=0, w=2e-6, h=w, domain="src")
    gen.add_rect(x=40e-6, y=2e-6, w=2e-6, h=w, domain="sink")
    
    # Generate file
    gen.write_file("generated_geometry.yaml")
