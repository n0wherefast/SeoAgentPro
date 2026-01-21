# app/modules/competitor/radar.py

def radar_payload(my_scores: dict, comp_scores: dict) -> dict:
    """
    Restituisce un dict pronto per un radar chart library:
      labels: dimensioni (human-readable)
      datasets: [{label, data}]
    """
    # Mapping per labels leggibili
    label_map = {
        "authority": "Authority",
        "content": "Content",
        "performance": "Performance",
        "technical": "Technical",
        "keyword_coverage": "Keywords"
    }
    
    keys = ["authority", "content", "performance", "technical", "keyword_coverage"]
    labels = [label_map[k] for k in keys]
    
    # Gestisci None values → 0
    my_data = [my_scores.get(k) or 0 for k in keys]
    comp_data = [comp_scores.get(k) or 0 for k in keys]

    return {
        "labels": labels,
        "datasets": [
            {"label": "Your Site", "data": my_data},
            {"label": "Competitor", "data": comp_data}
        ]
    }
