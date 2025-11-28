"""
Geometry generation for microstrip example.
This module encapsulates the geometric drawing logic for the microstrip example.
It is independent of the pypeec library and provides a structure that can be 
exported to pypeec or other formats (like STL).
"""

class MicrostripGeometry:
    def __init__(
        self,
        length_p1_to_stub=43.0e-6,
        length_stub_to_p2=38.0e-6,
        length_stub_p3=28.0e-6,
        length_p4_to_p5=45.0e-6,
        width_trace=4.0e-6,
        thickness_ground=1.0e-6,
        thickness_substrate=1.0e-6,
        thickness_trace=1.0e-6,
        substrate_margin=10.0e-6,
        gap_bottom_bar=1.0e-6,
        resolution=(1.0e-6, 1.0e-6, 0.5e-6)
    ):
        """
        Initialize the microstrip geometry generator.

        Parameters
        ----------
        length_p1_to_stub : float
            Horizontal distance from terminal P1 to the center of the vertical stub.
        length_stub_to_p2 : float
            Horizontal distance from the stub center to terminal P2.
        length_stub_p3 : float
            Vertical height of the stub.
        length_p4_to_p5 : float
            Horizontal length of the bottom bar trace.
        width_trace : float
            Width of all signal traces.
        thickness_ground : float
            Thickness of the ground plane.
        thickness_substrate : float
            Thickness of the dielectric substrate.
        thickness_trace : float
            Thickness of the signal trace.
        substrate_margin : float
            Margin around the traces for the substrate/ground.
        gap_bottom_bar : float
            Vertical gap between the main trace and the bottom bar.
        resolution : tuple or float
            Voxel grid resolution (dx, dy, dz).
        """
        self.length_p1_to_stub = float(length_p1_to_stub)
        self.length_stub_to_p2 = float(length_stub_to_p2)
        self.length_stub_p3 = float(length_stub_p3)
        self.length_p4_to_p5 = float(length_p4_to_p5)
        self.width_trace = float(width_trace)
        self.thickness_ground = float(thickness_ground)
        self.thickness_substrate = float(thickness_substrate)
        self.thickness_trace = float(thickness_trace)
        self.substrate_margin = float(substrate_margin)
        self.gap_bottom_bar = float(gap_bottom_bar)

        if isinstance(resolution, (float, int)):
            self.dx = self.dy = self.dz = float(resolution)
        else:
            self.dx, self.dy, self.dz = resolution

        # Internal storage for shapes (list of coordinates) and layer mapping
        self.shapes = {}
        self.layer_map = {}
        
        # Computed parameters
        self.n_gnd = 1
        self.n_sub = 1
        self.n_top = 1
        
        self._generate_geometry()

    def _get_rect_coords(self, cx, cy, width, height):
        """Generate coordinates for a rectangle centered at (cx, cy)."""
        hw = width / 2.0
        hh = height / 2.0
        return [
            [cx - hw, cy - hh],
            [cx + hw, cy - hh],
            [cx + hw, cy + hh],
            [cx - hw, cy + hh],
        ]

    def _generate_geometry(self):
        """Calculate the 2D shapes for all domains."""
        # Dimensions
        L1 = self.length_p1_to_stub
        L2 = self.length_stub_to_p2
        L_main = L1 + L2
        L_stub = self.length_stub_p3
        L_bottom = self.length_p4_to_p5
        w = self.width_trace
        gap = self.gap_bottom_bar
        
        # Terminal length (ensure overlap for pypeec ports)
        term_len = 2 * self.dx

        # 1. Main line (P1 to P2)
        coord_main = self._get_rect_coords(L_main / 2.0, 0.0, L_main, w)
        
        # 2. Stub
        coord_stub = self._get_rect_coords(L1, L_stub / 2.0, w, L_stub)
        
        # 3. Ports P1, P2
        coord_p1 = self._get_rect_coords(0.0, 0.0, term_len, w)
        coord_p2 = self._get_rect_coords(L_main, 0.0, term_len, w)
        
        # 4. Bottom bar
        hw = w / 2.0
        bottom_bar_y = -hw - gap - hw
        coord_bottom = self._get_rect_coords(L_bottom / 2.0, bottom_bar_y, L_bottom, w)
        
        # 5. Ports P4, P5
        coord_p4 = self._get_rect_coords(0.0, bottom_bar_y, term_len, w)
        coord_p5 = self._get_rect_coords(L_bottom, bottom_bar_y, term_len, w)
        
        # 6. Substrate/Ground
        margin = self.substrate_margin
        x_min = -margin
        x_max = max(L_main, L_bottom) + margin
        y_min = bottom_bar_y - margin
        y_max = L_stub + margin
        
        coord_rect = [
            [x_min, y_min],
            [x_max, y_min],
            [x_max, y_max],
            [x_min, y_max],
        ]
        
        # Store shapes
        self.shapes = {
            "ground": [coord_rect],
            "substrate": [coord_rect],
            "trace": [coord_main, coord_stub],
            "trace_bottom": [coord_bottom],
            "src": [coord_p1],
            "sink": [coord_p2],
            "src_bottom": [coord_p4],
            "sink_bottom": [coord_p5]
        }
        
        # Layer Calculations
        self.n_gnd = max(1, int(round(self.thickness_ground / self.dz)))
        self.n_sub = max(1, int(round(self.thickness_substrate / self.dz)))
        self.n_top = max(1, int(round(self.thickness_trace / self.dz)))
        
        # Map logical domains to physical layers
        self.layer_map = {
            "ground": "layer_gnd",
            "substrate": "layer_sub",
            "trace": "layer_top",
            "trace_bottom": "layer_top",
            "src": "layer_top",
            "sink": "layer_top",
            "src_bottom": "layer_top",
            "sink_bottom": "layer_top",
        }

    def get_pypeec_data(self):
        """
        Construct the Pypeec geometry dictionary.
        
        Returns
        -------
        dict
            Geometry definition compatible with ``pypeec.run_mesher_data``.
        """
        
        def make_shape(layer, shape_type, **data):
            return {
                "shape_layer": [layer],
                "shape_operation": "add",
                "shape_type": shape_type,
                "shape_data": data,
            }

        layer_stack = [
            {"n_layer": self.n_gnd, "tag_layer": "layer_gnd"},
            {"n_layer": self.n_sub, "tag_layer": "layer_sub"},
            {"n_layer": self.n_top, "tag_layer": "layer_top"},
        ]
        
        geometry_shape = {}
        for domain, coords_list in self.shapes.items():
            layer = self.layer_map[domain]
            shapes = []
            for coords in coords_list:
                # Convert to the format expected by pypeec
                shapes.append(make_shape(layer, "polygon", buffer=0.0, coord_shell=coords, coord_holes=[]))
            geometry_shape[domain] = shapes
            
        return {
            "mesh_type": "shape",
            "data_voxelize": {
                "param": {
                    "dx": self.dx, "dy": self.dy, "dz": self.dz,
                    "cz": 0.0,
                    "simplify": 1.0e-8,
                    "construct": None,
                    "xy_min": None, "xy_max": None
                },
                "layer_stack": layer_stack,
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
                "conflict_rules": [
                    {"domain_resolve": ["trace"], "domain_keep": ["src", "sink"]},
                    {"domain_resolve": ["trace_bottom"], "domain_keep": ["src_bottom", "sink_bottom"]},
                    {"domain_resolve": ["ground"], "domain_keep": ["substrate"]},
                    {"domain_resolve": ["substrate"], "domain_keep": ["trace", "trace_bottom", "src", "sink", "src_bottom", "sink_bottom"]}
                ]
            },
            "data_integrity": {
                "check_integrity": True,
                "domain_connected": {
                    "signal_top": {"domain_group": [["trace"], ["src", "sink"]], "connected": True},
                    "signal_bottom": {"domain_group": [["trace_bottom"], ["src_bottom", "sink_bottom"]], "connected": True},
                    "ground": {"domain_group": [["ground"]], "connected": True}
                },
                "domain_adjacent": {}
            }
        }

    def get_geometry_model(self):
        """
        Return a generic model of the geometry (polygons and layers).
        Useful for extension (e.g. STL conversion).
        """
        return {
            "shapes": self.shapes,
            "layers": {
                "layer_gnd": {"thickness": self.thickness_ground, "n_voxels": self.n_gnd, "z_base": 0.0},
                "layer_sub": {"thickness": self.thickness_substrate, "n_voxels": self.n_sub, "z_base": self.thickness_ground},
                "layer_top": {"thickness": self.thickness_trace, "n_voxels": self.n_top, "z_base": self.thickness_ground + self.thickness_substrate},
            },
            "layer_map": self.layer_map
        }
