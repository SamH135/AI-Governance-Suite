"""Manual bake-off: NLI grounding scorers on a labeled legal/medical claim set.

Runs each candidate checkpoint through the production path
(probes.grounding.NLIGroundingScorer) on labeled (claim, evidence) pairs and
reports accuracy, per-category breakdown, mean entailment by true label, and
per-pair latency. Not a pytest test — run directly:

    py tests/manual/grounding_bakeoff.py [model_id ...]

Downloads ~2-3GB of checkpoints on first run (HF cache). Labels:
    1 = supported (entailed by the doc), 0 = unsupported (fabricated/contradicted/
    not-in-doc — including claims that are true in the world but absent here).
"""
import json
import sys
import time
from pathlib import Path

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from services.compliance.framework.probes.grounding import NLIGroundingScorer

DOC_DEPO = (
    "Deposition of John Miller, March 3, 2024, page 42 line 10-18. "
    "Q: Did you inspect the brake line? A: Yes, on February 28. I found no "
    "visible wear or corrosion. Q: How often are maintenance logs updated? "
    "A: Weekly, every Monday morning."
)
DOC_MED = (
    "Emergency Department Note, St. David's Medical Center. Patient presented "
    "2023-06-14 with left wrist pain after a fall. X-ray showed distal radius "
    "fracture. A short arm cast was applied on 2023-06-14. Orthopedic "
    "follow-up scheduled for 2023-06-28. Discharged with ibuprofen 600mg as "
    "needed."
)
DOC_TIMELINE = (
    "Case file excerpt: Incident reported to insurer 2024-01-08. First demand "
    "letter sent 2024-02-01. Plaintiff filed suit 2024-03-15 in Travis County "
    "District Court. Defense counsel entered appearance 2024-04-02. Discovery "
    "deadline set for 2024-09-30."
)

# (doc, claim, label, category)
PAIRS = [
    # --- paraphrase / restatement (the easy positives) ---
    (DOC_DEPO, "The deponent inspected the brake line on February 28.", 1, "paraphrase"),
    (DOC_DEPO, "Maintenance logs were updated weekly.", 1, "paraphrase"),
    (DOC_DEPO, "John Miller found no brake wear during the inspection.", 1, "paraphrase"),
    (DOC_MED, "The patient fractured their distal radius.", 1, "paraphrase"),
    (DOC_MED, "A cast was applied on June 14, 2023.", 1, "paraphrase"),
    (DOC_MED, "The patient was discharged with a 600mg ibuprofen prescription.", 1, "paraphrase"),
    (DOC_TIMELINE, "Suit was filed in Travis County District Court.", 1, "paraphrase"),
    (DOC_TIMELINE, "The discovery deadline was set for September 30, 2024.", 1, "paraphrase"),
    # --- multi-hop / inference (hard positives) ---
    (DOC_DEPO, "The brake line showed no signs of deterioration when checked.", 1, "multi_hop"),
    (DOC_MED, "The wrist fracture was on the patient's left side.", 1, "multi_hop"),
    (DOC_MED, "The orthopedic follow-up was scheduled roughly two weeks after the ER visit.", 1, "multi_hop"),
    (DOC_TIMELINE, "The insurer was notified before the first demand letter was sent.", 1, "multi_hop"),
    (DOC_TIMELINE, "Defense counsel entered an appearance about three weeks after suit was filed.", 1, "multi_hop"),
    # --- contradiction using the doc's own vocabulary (hard negatives) ---
    (DOC_DEPO, "The deponent found severe brake corrosion during the inspection.", 0, "contradiction"),
    (DOC_MED, "The patient presented with right wrist pain.", 0, "contradiction"),
    (DOC_TIMELINE, "Defense counsel entered an appearance before suit was filed.", 0, "contradiction"),
    # --- numeric/date swaps (NLI's known weak spot) ---
    (DOC_DEPO, "The brake inspection happened on March 3, 2024.", 0, "date_swap"),
    (DOC_MED, "The injury was treated on June 28, 2023.", 0, "date_swap"),
    (DOC_MED, "The patient was prescribed 800mg ibuprofen.", 0, "date_swap"),
    (DOC_TIMELINE, "Plaintiff filed suit on March 15, 2023.", 0, "date_swap"),
    # --- fabrication / not-in-doc (easy negatives) ---
    (DOC_DEPO, "The deponent admitted liability for the crash.", 0, "fabrication"),
    (DOC_DEPO, "The deponent is a certified mechanic.", 0, "fabrication"),
    (DOC_MED, "The patient underwent wrist surgery.", 0, "fabrication"),
    (DOC_MED, "The patient has a documented history of diabetes.", 0, "fabrication"),
    (DOC_TIMELINE, "The case settled out of court for $50,000.", 0, "fabrication"),
    # --- world-true but absent from the record (the subtle one) ---
    (DOC_DEPO, "Brake line corrosion can cause brake failure.", 0, "world_knowledge"),
    (DOC_MED, "Distal radius fractures are common after falls.", 0, "world_knowledge"),
]

MODELS = [
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",          # ~350MB, default
    "cross-encoder/nli-deberta-v3-base",                   # ~400MB, classic NLI
    "ynie/roberta-large-snli_mnli_fever_anli_R1_R2_R3-nli",  # ~500MB, strong baseline
    "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli",  # ~870MB
    "lytang/MiniCheck-DeBERTa-v3-Large",                   # ~870MB, purpose-built, binary 0/1
    "lytang/MiniCheck-RoBERTa-Large",                    # ~440MB, purpose-built, binary 0/1
]

THRESHOLD = 0.5


def main():
    models = sys.argv[1:] or MODELS
    summary = {}
    for model_id in models:
        print(f"\n=== {model_id} ===", flush=True)
        try:
            scorer = NLIGroundingScorer(model_id=model_id)
        except Exception as e:  # noqa: BLE001 - report and continue the bake-off
            print(f"  load failed: {e}")
            summary[model_id] = {"error": str(e)}
            continue
        rows, correct, lat = [], 0, 0.0
        for doc, claim, label, cat in PAIRS:
            t0 = time.perf_counter()
            try:
                p = scorer.score(claim, doc)
            except Exception as e:  # noqa: BLE001
                print(f"  scorer incompatible: {e}")
                rows = None
                break
            lat += time.perf_counter() - t0
            pred = 1 if p >= THRESHOLD else 0
            correct += int(pred == label)
            rows.append({"claim": claim, "label": label, "cat": cat,
                         "p": round(p, 4), "pred": pred})
        if rows is None:
            summary[model_id] = {"error": "incompatible labels"}
            continue
        cats = {}
        for r in rows:
            c = cats.setdefault(r["cat"], [0, 0])
            c[1] += 1
            c[0] += int(r["pred"] == r["label"])
        pos = [r["p"] for r in rows if r["label"] == 1]
        neg = [r["p"] for r in rows if r["label"] == 0]
        summary[model_id] = {
            "accuracy": round(correct / len(rows), 3),
            "per_category": {k: f"{v[0]}/{v[1]}" for k, v in cats.items()},
            "mean_p_supported": round(sum(pos) / len(pos), 3),
            "mean_p_unsupported": round(sum(neg) / len(neg), 3),
            "ms_per_pair": round(1000 * lat / len(rows), 1),
            "pairs": rows,
        }
        print(json.dumps(summary[model_id], indent=2), flush=True)

    out = Path(__file__).parent / "grounding_bakeoff_results.json"
    out.write_text(json.dumps({"n_pairs": len(PAIRS), "threshold": THRESHOLD,
                               "models": summary}, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
