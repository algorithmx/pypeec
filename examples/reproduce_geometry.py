from microstrip_yaml_generator import SandwichMicrostripGenerator

if __name__ == "__main__":
    # Initialize with margin=0 because we will manually set the bounds to match exactly
    gen = SandwichMicrostripGenerator(resolution=0.5e-6, margin=0.0)
    
    # Set layer thicknesses to match the target (n=2 for all)
    # The generator stores these as n_gnd, n_sub, n_top
    gen.n_gnd = 2
    gen.n_sub = 2
    gen.n_top = 2
    
    # --- Define Shapes ---
    
    # 1. Trace (T-shape)
    # Horizontal main line: 0 to 81um, width 4um centered at y=0
    # Center x = 40.5um, y = 0
    gen.add_rect(x=40.5e-6, y=0.0, w=81.0e-6, h=4.0e-6, domain="trace")
    
    # Vertical stub: x=41 to 45um, y=0 to 28um
    # Center x = 43.0um, y = 14.0um, w=4um, h=28um
    gen.add_rect(x=43.0e-6, y=14.0e-6, w=4.0e-6, h=28.0e-6, domain="trace")
    
    # 2. Trace Bottom
    # Horizontal line: 0 to 45um, y centered at -5um, width 4um
    # Center x = 22.5um, y = -5.0um
    gen.add_rect(x=22.5e-6, y=-5.0e-6, w=45.0e-6, h=4.0e-6, domain="trace_bottom")
    
    # 3. Ports
    # Src: x=-0.5 to 0.5 (width 1um), y=-2 to 2
    gen.add_rect(x=0.0, y=0.0, w=1.0e-6, h=4.0e-6, domain="src")
    
    # Sink: x=80.5 to 81.5 (width 1um), y=-2 to 2
    gen.add_rect(x=81.0e-6, y=0.0, w=1.0e-6, h=4.0e-6, domain="sink")
    
    # Src Bottom: x=-0.5 to 0.5, y=-7 to -3
    gen.add_rect(x=0.0, y=-5.0e-6, w=1.0e-6, h=4.0e-6, domain="src_bottom")
    
    # Sink Bottom: x=44.5 to 45.5, y=-7 to -3
    gen.add_rect(x=45.0e-6, y=-5.0e-6, w=1.0e-6, h=4.0e-6, domain="sink_bottom")
    
    # --- Force Substrate/Ground Bounds ---
    # To match 'examples/microstrip/geometry.yaml' exactly:
    # coord_shell: [[-10.0e-6, -15.0e-6], [91.0e-6, -15.0e-6], [91.0e-6, 38.0e-6], [-10.0e-6, 38.0e-6]]
    # This corresponds to [min_x, min_y, max_x, max_y]
    gen.bounds = [-10.0e-6, -15.0e-6, 91.0e-6, 38.0e-6]
    
    # --- Custom Conflict Rules for Bottom Trace ---
    gen.conflict_rules = [
        {"domain_resolve": ["trace"], "domain_keep": ["src", "sink"]},
        {"domain_resolve": ["trace_bottom"], "domain_keep": ["src_bottom", "sink_bottom"]},
        {"domain_resolve": ["ground"], "domain_keep": ["substrate"]},
        {"domain_resolve": ["substrate"], "domain_keep": ["trace", "trace_bottom", "src", "sink", "src_bottom", "sink_bottom"]}
    ]
    
    # --- Custom Integrity Rules ---
    gen.domain_connected = {
        "signal_top": {"domain_group": [["trace"], ["src", "sink"]], "connected": True},
        "signal_bottom": {"domain_group": [["trace_bottom"], ["src_bottom", "sink_bottom"]], "connected": True},
        "ground": {"domain_group": [["ground"]], "connected": True}
    }
    
    # Generate file
    gen.write_file("examples/microstrip/geometry.yaml")
