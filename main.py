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
    {'id': 'Tyler Typical', 'max_visits': 5, 'banned': []}, 
    {'id': 'Typer Typical', 'max_visits': 5, 'banned': []}, 
    {'id': 'Tyler Atypical', 'max_visits': 5, 'banned': []}, 
    {'id': 'Dunstin Checksin', 'max_visits': 5, 'banned': []}, 
    {'id': 'Xauthuul', 'max_visits': 5, 'banned': []}, 
    {'id': 'Haulen Datore', 'max_visits': 1, 'banned': ['J105433 I', 'J105433 III', 'J105433 VII', 'J105433 V']}, 


]

# 2. Define Demand (P1 naming convention)
P1_targets = {
    'Bacteria': 3,
    'Proteins': 2,
    'Toxic Metals': 4,
    'Reactive Metals': 4,
    'Electrolytes': 3,
    'Water': 5,
    'Biofuels': 2,
    'Chiral Structures': 2,
    'Oxygen': 1,
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
        "id": "J105433 I (Barren)",
        "resources": {
            "Aqueous Liquids": 36,
            "Base Metals": 71,
            "Carbon Compounds": 73,
            "Microorganisms": 61,
            "Noble Metals": 43
        }
    },
    {
        "id": "J105433 II (Storm)",
        "resources": {
            "Aqueous Liquids": 62,
            "Base Metals": 85,
            "Ionic Solutions": 34,
            "Noble Gas": 42,
            "Suspended Plasma": 64
        }
    },
    {
        "id": "J105433 III (Barren)",
        "resources": {
            "Aqueous Liquids": 33,
            "Base Metals": 75,
            "Carbon Compounds": 75,
            "Microorganisms": 61,
            "Noble Metals": 43
        }
    },
    {
        "id": "J105433 IV (Lava)",
        "resources": {
            "Base Metals": 43,
            "Felsic Magma": 37,
            "Heavy Metals": 65,
            "Non-CS Crystals": 47,
            "Suspended Plasma": 48
        }
    },
    {
        "id": "J105433 IX (Gas)",
        "resources": {
            "Aqueous Liquids": 50,
            "Base Metals": 70,
            "Ionic Solutions": 54,
            "Noble Gas": 65,
            "Reactive Gas": 35
        }
    },
    {
        "id": "J105433 V (Temperate)",
        "resources": {
            "Aqueous Liquids": 47,
            "Autotrophs": 63,
            "Carbon Compounds": 82,
            "Complex Organisms": 37,
            "Microorganisms": 60
        }
    },
    {
        "id": "J105433 VI (Gas)",
        "resources": {
            "Aqueous Liquids": 53,
            "Base Metals": 69,
            "Ionic Solutions": 53,
            "Noble Gas": 64,
            "Reactive Gas": 31
        }
    },
    {
        "id": "J105433 VII (Barren)",
        "resources": {
            "Aqueous Liquids": 34,
            "Base Metals": 70,
            "Carbon Compounds": 74,
            "Microorganisms": 59,
            "Noble Metals": 44
        }
    },
    {
        "id": "J105433 VIII (Gas)",
        "resources": {
            "Aqueous Liquids": 52,
            "Base Metals": 71,
            "Ionic Solutions": 53,
            "Noble Gas": 67,
            "Reactive Gas": 31
        }
    },
    {
        "id": "J105433 X (Gas)",
        "resources": {
            "Aqueous Liquids": 52,
            "Base Metals": 71,
            "Ionic Solutions": 56,
            "Noble Gas": 66,
            "Reactive Gas": 23
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
