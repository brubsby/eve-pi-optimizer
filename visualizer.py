import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import collections

def get_custom_layout(G):
    """
    Calculates a custom layout:
    - Standard layers (0, 1, 4, 5) are evenly spaced centered on Y=0.
    - Layer 3 (Planet|Res) is grouped by Planet, with gaps between planets.
    - Layer 2 (Planets) is positioned to align with the center of their Layer 3 groups.
    """
    pos = {}
    
    # Group nodes by layer
    layers = collections.defaultdict(list)
    for node, data in G.nodes(data=True):
        layers[data.get('layer', 0)].append(node)
        
    x_step = 3.0  # Horizontal separation between layers
    
    # --- 1. Position Layer 3 (Planet|Resource) first to establish anchor points ---
    l3_nodes = layers[3]
    grouped_l3 = collections.defaultdict(list)
    for node in l3_nodes:
        # Node format: "PlanetID|Resource"
        parts = node.split("|")
        planet_id = parts[0]
        grouped_l3[planet_id].append(node)
        
    # Sort resources within groups
    for pid in grouped_l3:
        grouped_l3[pid].sort()
        
    # Sort planets alphabetically
    sorted_planets = sorted(grouped_l3.keys())
    
    # Configuration for L3
    node_spacing = 1.0
    planet_group_spacing = 2.5
    
    # Calculate total height for L3
    l3_y_positions = {}
    current_y = 0
    
    # Store centroids for Layer 2 alignment
    planet_centroids = {}
    
    for pid in sorted_planets:
        group = grouped_l3[pid]
        group_y_start = current_y
        
        for node in group:
            l3_y_positions[node] = current_y
            current_y -= node_spacing
        
        # Calculate centroid for this planet
        group_y_end = current_y + node_spacing # undo last subtract
        centroid = (group_y_start + group_y_end) / 2.0
        planet_centroids[pid] = centroid
        
        # Add gap
        current_y -= planet_group_spacing

    # Center L3 around Y=0
    min_y = min(l3_y_positions.values()) if l3_y_positions else 0
    max_y = max(l3_y_positions.values()) if l3_y_positions else 0
    mid_y = (min_y + max_y) / 2.0
    
    # Apply L3 positions
    for node, y in l3_y_positions.items():
        pos[node] = (3 * x_step, y - mid_y)
        
    # Adjust centroids shift
    for pid in planet_centroids:
        planet_centroids[pid] -= mid_y

    # --- 2. Position Layer 2 (Planets) aligned to centroids ---
    l2_nodes = layers[2]
    for node in l2_nodes:
        if node in planet_centroids:
            y = planet_centroids[node]
        else:
            y = 0 
        pos[node] = (2 * x_step, y)

    # --- 3. Position Other Layers (0, 1, 4, 5) ---
    for layer_idx in [0, 1, 4, 5]:
        nodes = layers[layer_idx]
        nodes.sort()
        
        l3_height = (max_y - min_y) if l3_y_positions else 10
        
        if len(nodes) > 1:
            step = l3_height / (len(nodes) + 1)
            step = max(step, 1.5) # Ensure minimum spacing
            
            # Center around 0
            current_layer_h = (len(nodes) - 1) * step
            start_y = current_layer_h / 2.0
            
            for i, node in enumerate(nodes):
                pos[node] = (layer_idx * x_step, start_y - (i * step))
        else:
            pos[nodes[0]] = (layer_idx * x_step, 0)

    return pos

def visualize_network(G, flow_dict, filename="network_flow.png"):
    """
    Visualizes the solver network using a multipartite layout.
    Highlights edges with active flow.
    """
    print("Generating visualization...")
    
    # Increase height
    plt.figure(figsize=(24, 16))
    
    # Use Custom Layout
    try:
        pos = get_custom_layout(G)
    except Exception as e:
        print(f"Custom layout failed: {e}. Falling back to spring.")
        pos = nx.spring_layout(G)

    # --- Draw Edges ---
    active_edges = []
    inactive_edges = []

    for u, v, data in G.edges(data=True):
        # Check for flow
        flow = 0
        if u in flow_dict and v in flow_dict[u]:
            flow = flow_dict[u][v]
        
        if flow > 0:
            active_edges.append((u, v))
        else:
            inactive_edges.append((u, v))

    # Draw inactive edges (very faint)
    nx.draw_networkx_edges(G, pos, edgelist=inactive_edges, edge_color='#E0E0E0', width=0.5, alpha=0.4, arrows=False)
    
    # Draw active edges
    nx.draw_networkx_edges(G, pos, edgelist=active_edges, edge_color='green', width=1.5, arrows=True, arrowstyle='->', arrowsize=10)

    # --- Draw Nodes ---
    layer_colors = {
        0: '#ff9999', # Source
        1: '#66b3ff', # Characters
        2: '#99ff99', # Planets
        3: '#ffcc99', # Planet|Res
        4: '#c2c2f0', # Resource
        5: '#ff9999'  # Sink
    }
    
    # Prepare node lists and labels
    node_lists = collections.defaultdict(list)
    labels = {}
    
    for node, data in G.nodes(data=True):
        layer = data.get('layer', 0)
        node_lists[layer].append(node)
        
        # Label Logic
        label_text = str(node)
        
        # Layer 4: Resource Node -> "Resource (Req: X)"
        if layer == 4:
            # Find successor (Sink) to get capacity = demand
            # Edge: Resource -> Sink
            successors = list(G.successors(node))
            demand = "?"
            for succ in successors:
                if G.nodes[succ].get('layer') == 5: # Sink
                    edge_data = G.get_edge_data(node, succ)
                    if edge_data:
                        demand = str(edge_data.get('capacity', '?'))
                    break
            labels[node] = f"{label_text} (Req: {demand})"

        # Layer 3: Planet|Resource -> "Resource (Yield)"
        elif layer == 3:
            abundance = "?"
            preds = list(G.predecessors(node))
            if preds:
                p_node = preds[0]
                edge_data = G.get_edge_data(p_node, node)
                if edge_data:
                    weight = edge_data.get('weight', 0)
                    abundance = str(abs(weight))
            
            if "|" in label_text:
                parts = label_text.split('|')
                res_name = parts[1]
                labels[node] = f"{res_name} ({abundance})"
            else:
                labels[node] = f"{label_text} ({abundance})"
            
        # Layer 2: Planet Names -> Strip "J105433 "
        elif layer == 2:
            if "J105433" in label_text:
                labels[node] = label_text.replace("J105433 ", "")
            else:
                labels[node] = label_text
        # Layer 1: Characters
        elif layer == 1:
             labels[node] = label_text
        # Others
        else:
            labels[node] = label_text

    # Draw Nodes per layer
    for layer, nodes in node_lists.items():
        nx.draw_networkx_nodes(G, pos, nodelist=nodes, node_color=layer_colors.get(layer, 'grey'), node_size=300, alpha=1.0)

    # Draw Labels
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7, font_weight='bold')

    plt.title("Mission Solver Network Flow")
    plt.axis('off')
    plt.tight_layout()
    
    plt.savefig(filename)
    plt.close()
    print(f"Visualization saved to {filename}")
