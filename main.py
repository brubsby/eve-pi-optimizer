import networkx as nx

def solve_mission(characters, resource_targets, planet_data):
    G = nx.DiGraph()
    source, sink = "Source", "Sink"
    
    # --- 1. Graph Construction ---
    
    # Layer 1: Source -> Characters (Capacity = Max Visits)
    for char in characters:
        G.add_edge(source, char['id'], capacity=char['max_visits'], weight=0)
        
        # Layer 2: Characters -> Planets (Capacity = 1)
        for planet in planet_data:
            # Skip if planet is banned for this character
            if 'banned' in char and planet['id'] in char['banned']:
                continue
            
            G.add_edge(char['id'], planet['id'], capacity=1, weight=0)

    # Layer 3 & 4: Planets -> Planet|Resource -> Resource Type
    for planet in planet_data:
        p_id = planet['id']
        
        for res, abundance in planet['resources'].items():
            if res in resource_targets:
                # Node for specific resource on specific planet
                # e.g., "Planet1|Iron"
                pr_node = f"{p_id}|{res}"
                
                # Planet -> Planet|Res (Cost = -Abundance)
                # Capacity is set to len(characters) so multiple people can pick same item
                G.add_edge(p_id, pr_node, capacity=len(characters), weight=-abundance)
                
                # Planet|Res -> Global Resource (Aggregation)
                G.add_edge(pr_node, res, capacity=len(characters), weight=0)

    # Layer 5: Global Resource -> Sink (Capacity = Target Demand)
    for res, target in resource_targets.items():
        G.add_edge(res, sink, capacity=target, weight=0)

    # --- 2. Solve (Min Cost Max Flow) ---
    try:
        flow_dict = nx.max_flow_min_cost(G, source, sink)
    except nx.NetworkXUnfeasible:
        print("Error: Constraints are too tight. Cannot meet resource demand.")
        return 0, {}

    # --- 3. Post-Processing (Generate Work Orders) ---
    
    # Initialize empty work orders
    work_orders = {char['id']: [] for char in characters}
    total_abundance = 0

    for planet in planet_data:
        p_id = planet['id']
        
        # A. Who is at this planet? 
        # Check flow from all characters to this planet node
        visitors = []
        for char in characters:
            c_id = char['id']
            # Check if flow exists and is > 0
            if c_id in flow_dict and p_id in flow_dict[c_id]:
                if flow_dict[c_id][p_id] > 0:
                    visitors.append(c_id)
        
        # B. What resources are being taken from this planet?
        # Check flow from Planet to Planet|Resource nodes
        items_to_collect = []
        if p_id in flow_dict:
            for neighbor, flow_amt in flow_dict[p_id].items():
                if flow_amt > 0 and "|" in neighbor: # Identify Planet|Res nodes
                    res_name = neighbor.split("|")[1]
                    # If flow is 2, we add it twice: ['Iron', 'Iron']
                    for _ in range(int(flow_amt)):
                        items_to_collect.append(res_name)
                        # Add to total score calculation
                        total_abundance += planet['resources'][res_name]

        # C. Assign items to visitors
        # Since cost is property of the planet, not the person, any visitor 
        # can take any of the assigned items.
        for i, visitor in enumerate(visitors):
            if i < len(items_to_collect):
                item = items_to_collect[i]
                abundance = planet['resources'][item]
                work_orders[visitor].append(f"Visit {p_id} -> Collect {item} (Yield: {abundance})")
            else:
                # Edge case: Character visited but didn't pick anything 
                # (This happens if optimization routed them there just to pass through, 
                # though in this specific graph structure that's rare/impossible)
                work_orders[visitor].append(f"Visit {p_id} -> No Collection")

    return total_abundance, work_orders

# --- Example Usage ---

# 1. Define Characters
chars = [
    {'id': 'Typer Typical', 'max_visits': 5, 'banned': []}, 
    {'id': 'Tyler Atypical', 'max_visits': 5, 'banned': []}, 
]

# 2. Define Demand (P1 naming convention)
P1_targets = {
    'Bacteria': 1,
    'Proteins': 1,
    'Toxic Metals': 2,
    'Reactive Metals': 1,
    'Electrolytes': 1,
    'Water': 2,
    'Biofuels': 1,
    'Chiral Structures': 1,  
}

# 3. Translation Map (P1 Result -> P0 Resource)
# Based on the table: Resource | P1 Result
translation_map = {
    'Bacteria': 'Microorganisms',
    'Biofuels': 'Carbon Compounds',
    'Biomass': 'Planktic Colonies',
    'Chiral Structures': 'Non-CS Crystals',
    'Electrolytes': 'Ionic Solutions',
    'Industrial Fibers': 'Autotrophs',
    'Oxidizing Compound': 'Reactive Gas',
    'Oxygen': 'Noble Gas',
    'Plasmoids': 'Suspended Plasma',
    'Precious Metals': 'Noble Metals',
    'Proteins': 'Complex Organisms',
    'Reactive Metals': 'Base Metals',
    'Silicon': 'Felsic Magma',
    'Toxic Metals': 'Heavy Metals', # Note: Ensure 'Heavy Metals' exists in your planet data
    'Water': 'Aqueous Liquids'
}

# 4. Convert P1_targets to targets (P0 format)
targets = {}

print("--- Translating Targets ---")
for p1_name, amount in P1_targets.items():
    if p1_name in translation_map:
        p0_name = translation_map[p1_name]
        targets[p0_name] = amount
        print(f"Mapped '{p1_name}' -> '{p0_name}' (Qty: {amount})")
    else:
        print(f"WARNING: No mapping found for '{p1_name}'")

# 3. Define Universe
planets = [
    {
        'id': 'J105433 I (Barren)',
        'resources': {
            'Microorganisms': 100,
            'Carbon Compounds': 100,
            'Noble Metals': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 II (Storm)',
        'resources': {
            'Ionic Solutions': 100,
            'Noble Gas': 100,
            'Suspended Plasma': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 III (Barren)',
        'resources': {
            'Microorganisms': 100,
            'Carbon Compounds': 100,
            'Noble Metals': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 IV (Lava)',
        'resources': {
            'Non-CS Crystals': 100,
            'Suspended Plasma': 100,
            'Heavy Metals': 100,
            'Base Metals': 100,
            'Felsic Magma': 100
        }
    },
    {
        'id': 'J105433 V (Temperate)',
        'resources': {
            'Microorganisms': 100,
            'Carbon Compounds': 100,
            'Autotrophs': 100,
            'Complex Organisms': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 VI (Gas)',
        'resources': {
            'Ionic Solutions': 100,
            'Reactive Gas': 100,
            'Noble Gas': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 VII (Barren)',
        'resources': {
            'Microorganisms': 100,
            'Carbon Compounds': 100,
            'Noble Metals': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 VIII (Gas)',
        'resources': {
            'Ionic Solutions': 100,
            'Reactive Gas': 100,
            'Noble Gas': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 IX (Gas)',
        'resources': {
            'Ionic Solutions': 100,
            'Reactive Gas': 100,
            'Noble Gas': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    },
    {
        'id': 'J105433 X (Gas)',
        'resources': {
            'Ionic Solutions': 100,
            'Reactive Gas': 100,
            'Noble Gas': 100,
            'Base Metals': 100,
            'Aqueous Liquids': 100
        }
    }
]


total_yield, orders = solve_mission(chars, targets, planets)

print(f"Total System Abundance: {total_yield}\n")
print("--- MISSION ASSIGNMENTS ---")
for char_id, tasks in orders.items():
    print(f"\n{char_id}:")
    if not tasks:
        print("  (No tasks assigned)")
    for t in tasks:
        print(f"  - {t}")
