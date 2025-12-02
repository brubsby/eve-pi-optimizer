import networkx as nx
import visualizer

def solve_mission(characters, resource_targets, planet_data, current_assignments=None, switching_cost=1000000):
    if current_assignments is None:
        current_assignments = {}

    G = nx.DiGraph()
    source, sink = "Source", "Sink"
    
    # Layer 0: Source & Layer 5: Sink (Initial Nodes)
    G.add_node(source, layer=0)
    G.add_node(sink, layer=5)
    
    # --- 1. Graph Construction ---
    
    # Layer 1: Source -> Characters (Capacity = Max Visits)
    for char in characters:
        G.add_node(char['id'], layer=1)
        G.add_edge(source, char['id'], capacity=char['max_visits'], weight=0)
        
        # Get this character's current planets (if any)
        # Structure expected: {'CharName': ['PlanetID1', 'PlanetID2']}
        # or {'CharName': {'PlanetID1': 'Resource'}}
        char_current_planets = current_assignments.get(char['id'], [])
        
        # Layer 2: Characters -> Planets (Capacity = 1)
        for planet in planet_data:
            p_id = planet['id']
            if p_id not in G.nodes:
                G.add_node(p_id, layer=2)
            
            # Skip if planet is banned for this character
            if 'banned' in char and p_id in char['banned']:
                continue
            
            # Determine cost: 0 if already set up, switching_cost if new
            # We use a soft check to handle potential string mismatches if user drops suffixes
            # But exact match is preferred for safety
            edge_weight = 0
            
            # specific check: Is p_id in the user's list for this char?
            # We assume the user provides IDs matching the planet list.
            is_existing = False
            if isinstance(char_current_planets, dict):
                is_existing = p_id in char_current_planets
            elif isinstance(char_current_planets, list):
                is_existing = p_id in char_current_planets
            
            if not is_existing:
                edge_weight = switching_cost

            G.add_edge(char['id'], p_id, capacity=1, weight=edge_weight)

    # Layer 3 & 4: Planets -> Planet|Resource -> Resource Type
    for planet in planet_data:
        p_id = planet['id']
        
        for res, abundance in planet['resources'].items():
            if res in resource_targets:
                # Node for specific resource on specific planet
                # e.g., "Planet1|Iron"
                pr_node = f"{p_id}|{res}"
                G.add_node(pr_node, layer=3)
                
                # Planet -> Planet|Res (Cost = -Abundance)
                # Capacity is set to len(characters) so multiple people can pick same item
                G.add_edge(p_id, pr_node, capacity=len(characters), weight=-abundance)
                
                # Planet|Res -> Global Resource (Aggregation)
                if res not in G.nodes:
                    G.add_node(res, layer=4)
                G.add_edge(pr_node, res, capacity=len(characters), weight=0)

    # Layer 5: Global Resource -> Sink (Capacity = Target Demand)
    for res, target in resource_targets.items():
        # Ensure resource node exists (it might not if no planet has it)
        if res not in G.nodes:
             G.add_node(res, layer=4)
        G.add_edge(res, sink, capacity=target, weight=0)

    # --- 2. Solve (Min Cost Max Flow) ---
    try:
        flow_dict = nx.max_flow_min_cost(G, source, sink)
    except nx.NetworkXUnfeasible:
        print("Error: Constraints are too tight. Cannot meet resource demand.")
        return 0, {}, G, {}

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
        # We attempt to match visitors to their existing resource assignments to minimize churn
        
        assignments = {} # visitor -> item
        unassigned_visitors = list(visitors)
        unassigned_items = list(items_to_collect)
        
        # 1. Greedy Match: Try to give visitors their existing resource if available
        for visitor in list(unassigned_visitors):
            curr_assigns = current_assignments.get(visitor, {})
            preferred_res = None
            if isinstance(curr_assigns, dict):
                preferred_res = curr_assigns.get(p_id)
            
            if preferred_res and preferred_res in unassigned_items:
                assignments[visitor] = preferred_res
                unassigned_visitors.remove(visitor)
                unassigned_items.remove(preferred_res)
        
        # 2. Fill remaining
        for visitor in unassigned_visitors:
            if unassigned_items:
                item = unassigned_items.pop(0)
                assignments[visitor] = item
            else:
                assignments[visitor] = None

        # 3. Generate Orders
        for visitor in visitors:
            item = assignments[visitor]
            if item:
                abundance = planet['resources'][item]
                
                # Status Checks
                curr_assigns = current_assignments.get(visitor, {})
                has_history = bool(curr_assigns)
                is_new_planet = p_id not in curr_assigns
                
                is_head_switch = False
                if not is_new_planet and isinstance(curr_assigns, dict):
                    if curr_assigns.get(p_id) != item:
                        is_head_switch = True
                
                msg = f"{p_id:<25} {item:<20} (Yield: {abundance:<3})"
                
                if is_new_planet:
                    if not has_history:
                        msg += " [NEW PLANET]"
                    else:
                        msg += " [PLANET SWITCH]"
                elif is_head_switch:
                    msg += " [HEAD SWITCH]"
                    
                work_orders[visitor].append(msg)
            else:
                work_orders[visitor].append(f"{p_id:<25} {'No Collection':<20}")

    return total_abundance, work_orders, G, flow_dict

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
    'Toxic Metals': 'Heavy Metals',
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
            "Microorganisms": 62,
            "Noble Metals": 43
        }
    },
    {
        "id": "J105433 II (Storm)",
        "resources": {
            "Aqueous Liquids": 63,
            "Base Metals": 86,
            "Ionic Solutions": 34,
            "Noble Gas": 42,
            "Suspended Plasma": 65
        }
    },
    {
        "id": "J105433 III (Barren)",
        "resources": {
            "Aqueous Liquids": 33,
            "Base Metals": 75,
            "Carbon Compounds": 76,
            "Microorganisms": 62,
            "Noble Metals": 42
        }
    },
    {
        "id": "J105433 IV (Lava)",
        "resources": {
            "Base Metals": 42,
            "Felsic Magma": 36,
            "Heavy Metals": 65,
            "Non-CS Crystals": 47,
            "Suspended Plasma": 48
        }
    },
    {
        "id": "J105433 IX (Gas)",
        "resources": {
            "Aqueous Liquids": 51,
            "Base Metals": 70,
            "Ionic Solutions": 54,
            "Noble Gas": 65,
            "Reactive Gas": 35
        }
    },
    {
        "id": "J105433 V (Temperate)",
        "resources": {
            "Aqueous Liquids": 46,
            "Autotrophs": 64,
            "Carbon Compounds": 82,
            "Complex Organisms": 37,
            "Microorganisms": 60
        }
    },
    {
        "id": "J105433 VI (Gas)",
        "resources": {
            "Aqueous Liquids": 54,
            "Base Metals": 69,
            "Ionic Solutions": 53,
            "Noble Gas": 64,
            "Reactive Gas": 30
        }
    },
    {
        "id": "J105433 VII (Barren)",
        "resources": {
            "Aqueous Liquids": 33,
            "Base Metals": 70,
            "Carbon Compounds": 74,
            "Microorganisms": 60,
            "Noble Metals": 44
        }
    },
    {
        "id": "J105433 VIII (Gas)",
        "resources": {
            "Aqueous Liquids": 53,
            "Base Metals": 71,
            "Ionic Solutions": 54,
            "Noble Gas": 67,
            "Reactive Gas": 30
        }
    },
    {
        "id": "J105433 X (Gas)",
        "resources": {
            "Aqueous Liquids": 52,
            "Base Metals": 71,
            "Ionic Solutions": 56,
            "Noble Gas": 67,
            "Reactive Gas": 23
        }
    }
]

# 4. Define Current Assignments (Optional)
# Map Character ID -> List of Planet IDs (or Dict of PlanetID: Resource)
# Use this to minimize switching costs.
current_assignments = {
    'Tyler Typical': {
        "J105433 II (Storm)": "Aqueous Liquids",
        "J105433 III (Barren)": "Microorganisms",
        "J105433 IV (Lava)": "Non-CS Crystals",
        "J105433 V (Temperate)": "Complex Organisms",
        "J105433 VIII (Gas)": "Aqueous Liquids"
    },
    'Typer Typical': {
        "J105433 II (Storm)": "Base Metals",
        "J105433 IV (Lava)": "Heavy Metals",
        "J105433 V (Temperate)": "Carbon Compounds",
        "J105433 VI (Gas)": "Aqueous Liquids",
        "J105433 X (Gas)": "Ionic Solutions"
    },
    'Tyler Atypical': {
        "J105433 II (Storm)": "Base Metals",
        "J105433 IV (Lava)": "Heavy Metals",
        "J105433 VI (Gas)": "Aqueous Liquids",
        "J105433 VIII (Gas)": "Aqueous Liquids",
        "J105433 X (Gas)": "Ionic Solutions"
    },
    'Dunstin Checksin': {
        "J105433 II (Storm)": "Base Metals",
        "J105433 III (Barren)": "Microorganisms",
        "J105433 IV (Lava)": "Heavy Metals",
        "J105433 V (Temperate)": "Carbon Compounds",
        "J105433 VIII (Gas)": "Noble Gas"
    },
    'Xauthuul': {
        "J105433 II (Storm)": "Base Metals",
        "J105433 III (Barren)": "Microorganisms",
        "J105433 IV (Lava)": "Heavy Metals",
        "J105433 V (Temperate)": "Complex Organisms",
        "J105433 X (Gas)": "Ionic Solutions"
    },
    'Haulen Datore': {
        "J105433 IV (Lava)": "Non-CS Crystals"
    }
}

# Cost to switch to a new planet (vs staying on existing one).
# Set high to prioritize stability, or low to prioritize pure yield.
SWITCHING_COST = 20 

total_yield, orders, G, flow_dict = solve_mission(chars, targets, planets, current_assignments, SWITCHING_COST)

# --- Visualize ---
visualizer.visualize_network(G, flow_dict, filename="solution_network.png")

print(f"Total System Abundance: {total_yield}\n")
print("--- MISSION ASSIGNMENTS ---")
for char_id, tasks in orders.items():
    print(f"\n{char_id}:")
    if not tasks:
        print("  (No tasks assigned)")
    for t in tasks:
        print(f"  - {t}")
