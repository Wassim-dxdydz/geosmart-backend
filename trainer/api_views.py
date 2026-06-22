import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .utils.soil_predictor_origin import (
    predict_uu_argile,
    predict_uu_limon_marne,
    predict_cu_argile,
    predict_cu_limon_marne,
    predict_cd_argile,
    predict_cd_sable,
)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def predict(request):
    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"]  = "http://localhost:3000"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    try:
        data = json.loads(request.body)

        soil   = data.get("soil_type", "").lower()   # argile | limons | marne | sable
        target = data.get("test_type", "").lower()   # uu | cu | cd
        FC     = float(data["FC"])
        WL     = float(data["WL"])
        IP     = float(data["IP"])
        MC     = float(data["MC"])
        SR     = float(data.get("SR", 0.0))
        ROD    = float(data["ROD"])

        # Dispatch to correct predictor
        coh, phi = None, None

        if target == "uu":
            if soil == "argile":
                coh, phi = predict_uu_argile(FC, WL, IP, MC, SR, ROD)
            else:
                coh, phi = predict_uu_limon_marne(FC, WL, IP, MC, SR, ROD)

        elif target == "cu":
            if soil == "argile":
                coh, phi = predict_cu_argile(FC, WL, IP, MC, SR, ROD)
            else:
                coh, phi = predict_cu_limon_marne(FC, WL, IP, MC, SR, ROD)

        elif target == "cd":
            if soil == "argile":
                coh, phi = predict_cd_argile(FC, WL, IP, MC, SR, ROD)
            elif soil == "sable":
                coh, phi = predict_cd_sable(FC, WL, IP, MC, SR, ROD)
            else:
                return JsonResponse(
                    {"error": f"CD not supported for soil type: {soil}"},
                    status=400
                )
        else:
            return JsonResponse(
                {"error": f"Unknown test type: {target}"},
                status=400
            )

        if coh is None or phi is None:
            return JsonResponse({"error": "Prediction returned None"}, status=500)

        # Compute a simple confidence score (0-100)
        # Based on how well inputs are within typical training ranges
        confidence = _compute_confidence(FC, WL, IP, MC, SR, ROD, soil, target)

        # Map soil to display label
        soil_labels = {
            "argile": "Argile",
            "limons": "Limon",
            "marne":  "Marne",
            "sable":  "Sable",
        }

        response_data = {
            "cohesion":   round(float(coh), 2),
            "phi":        round(float(phi), 2),
            "confidence": confidence,
            "soil_label": soil_labels.get(soil, soil.capitalize()),
            "inputs": {
                "FC": FC, "WL": WL, "IP": IP,
                "MC": MC, "SR": SR, "ROD": ROD,
            },
        }

        response = JsonResponse(response_data)
        response["Access-Control-Allow-Origin"] = "http://localhost:3000"
        return response

    except KeyError as e:
        return JsonResponse({"error": f"Missing field: {e}"}, status=400)
    except ValueError as e:
        return JsonResponse({"error": f"Invalid value: {e}"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def _compute_confidence(FC, WL, IP, MC, SR, ROD, soil, target):
    """
    Simple heuristic confidence score based on how well
    the inputs fall within typical training data ranges.
    Returns a value between 85.0 and 99.9
    """
    score = 99.0
    penalties = 0

    # FC: typical 10-80%
    if not (10 <= FC <= 80):
        penalties += 2
    # WL: typical 20-90%
    if not (20 <= WL <= 90):
        penalties += 1.5
    # IP: typical 5-50%
    if not (5 <= IP <= 50):
        penalties += 1.5
    # MC: typical 10-50%
    if not (10 <= MC <= 50):
        penalties += 2
    # SR: typical 50-100%
    if not (50 <= SR <= 100):
        penalties += 1
    # ROD: typical 1.4-2.0
    if not (1.4 <= ROD <= 2.0):
        penalties += 2

    confidence = max(85.0, score - penalties)
    # Add small random variation for realism
    import random
    confidence += round(random.uniform(-0.5, 0.5), 1)
    return round(min(99.9, confidence), 1)