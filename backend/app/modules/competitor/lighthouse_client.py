# # app/modules/competitor/lighthouse_client.py
# import os
# import requests
# # from .lighthouse import fetch_pagespeed_score

# PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
# # Imposta GOOGLE_PSI_KEY nell'ambiente: export GOOGLE_PSI_KEY="la_tua_chiave"

# def fetch_pagespeed_score(url: str, strategy: str = "mobile") -> dict:
#     """
#     Chiama PageSpeed Insights. Ritorna punteggi e dati essenziali.
#     Nota: richiede API key Google.
#     """
#     api_key = os.environ.get("GOOGLE_PSI_KEY")
#     if not api_key:
#         return {"error": "Missing GOOGLE_PSI_KEY env var"}

#     params = {
#         "url": url,
#         "key": api_key,
#         "strategy": strategy
#     }
#     r = requests.get(PAGESPEED_URL, params=params, timeout=20)
#     if r.status_code != 200:
#         return {"error": f"pagespeed request failed ({r.status_code})", "detail": r.text}

#     j = r.json()
#     # Estrai una sintesi: performance score e opportunità principali
#     perf_score = None
#     try:
#         perf_score = int(round(j["lighthouseResult"]["categories"]["performance"]["score"] * 100))
#     except:
#         perf_score = None

#     return {
#         "performance_score": perf_score,
#         "lighthouse_report": j
#     }

# def run_performance_engine(url: str):
#     """
#     Ritorna performance_score e metriche principali in forma semplice.
#     """
#     data = fetch_pagespeed_score(url)

#     if "error" in data:
#         return {
#             "performance_score": None,
#             "metrics": {},
#             "error": data["error"]
#         }

#     report = data["lighthouse_report"]

#     metrics = {}
#     audits = report["lighthouseResult"]["audits"]
#     extract = ["first-contentful-paint", "speed-index", "largest-contentful-paint",
#                "cumulative-layout-shift", "total-blocking-time"]

#     for key in extract:
#         if key in audits:
#             metrics[key] = audits[key].get("displayValue")

#     return {
#         "performance_score": data["performance_score"],
#         "metrics": metrics,
#     }



# app/modules/competitor/lighthouse_client.py

import os
import requests

PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
# Imposta GOOGLE_PSI_KEY nell'ambiente: export GOOGLE_PSI_KEY="la_tua_chiave"


def fetch_pagespeed_score(url: str, strategy: str = "mobile") -> dict:
    """
    Chiama PageSpeed Insights. Ritorna punteggi e dati essenziali.
    Nota: richiede API key Google.
    """
    api_key = os.environ.get("GOOGLE_PSI_KEY")
    if not api_key:
        return {"error": "Missing GOOGLE_PSI_KEY env var"}

    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy
    }

    try:
        r = requests.get(PAGESPEED_URL, params=params, timeout=25)
    except Exception as e:
        return {"error": f"pagespeed request exception: {e}"}

    if r.status_code != 200:
        return {"error": f"pagespeed request failed ({r.status_code})", "detail": r.text}

    j = r.json()
    # Estrai una sintesi: performance score
    perf_score = None
    try:
        perf_score = int(round(j["lighthouseResult"]["categories"]["performance"]["score"] * 100))
    except Exception:
        perf_score = None

    return {
        "performance_score": perf_score,
        "lighthouse_report": j,
    }


def run_performance_engine(url: str, strategy: str = "mobile") -> dict:
    """
    Wrapper più alto livello:
    - performance_score (0–100)
    - core web vitals principali (numericValue + displayValue se disponibili)
    Se l'API fallisce, ritorna valori di default per testing.
    """
    data = fetch_pagespeed_score(url, strategy=strategy)

    if "error" in data:
        # Se la API fallisce, ritorna None (nessun dato disponibile)
        print(f"[WARN] Performance API error: {data['error']}")
        return {
            "performance_score": None,
            "metrics": {},
            "note": "API non disponibile"
        }

    report = data["lighthouse_report"]
    lh = report.get("lighthouseResult", {})
    audits = lh.get("audits", {})

    def _metric(audit_id: str):
        audit = audits.get(audit_id, {})
        return {
            "numeric": audit.get("numericValue"),
            "display": audit.get("displayValue")
        } if audit else None

    metrics = {
        "first_contentful_paint": _metric("first-contentful-paint"),
        "speed_index": _metric("speed-index"),
        "largest_contentful_paint": _metric("largest-contentful-paint"),
        "cumulative_layout_shift": _metric("cumulative-layout-shift"),
        "total_blocking_time": _metric("total-blocking-time"),
        "time_to_first_byte": _metric("server-response-time")
    }

    return {
        "performance_score": data["performance_score"],
        "metrics": metrics,
        "data_full":data,
    }
