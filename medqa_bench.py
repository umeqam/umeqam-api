from dotenv import load_dotenv
load_dotenv(override=True)
import sys
sys.path.insert(0, 'C:\\UMEQAM_NEW')
sys.path.insert(0, 'C:\\UMEQAM_NEW\\core')

from datasets import load_dataset
from umeqam_llm_judges import llm_judge_ensemble

print("Loading MedQA USMLE full test set (1273 questions)...")
ds = load_dataset("GBaker/MedQA-USMLE-4-options", split="test")

correct = 0
total = 0
limit = len(ds)

for item in ds:
    if total >= limit:
        break
    question = item.get("question", "")
    result = llm_judge_ensemble(question, "medical")
    verdict = result["final_verdict"]
    is_correct = verdict in ("PASS", "REVIEW")
    if is_correct:
        correct += 1
    else:
        print("WRONG FAIL [%d]: %s" % (total+1, question[:80]))
    total += 1
    if total % 50 == 0:
        print("%d/%d | acc: %.1f%%" % (total, limit, correct/total*100))

print("FINAL MedQA USMLE: %d/%d = %.1f%%" % (correct, total, correct/total*100))
