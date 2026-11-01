"""Writes the fixture the portfolio Lab's post checker is tested against: published and queued posts plus test drafts that break
each rule, with what writing_problems returns for each (in order).

Usage: python -m scripts.export_lab_posts <output.json>
"""
import json
import os
import sys

from app.services.post_rules import writing_problems

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILLER = ("In today's fast-paced landscape, I leveraged a robust pipeline to unlock seamless insights.\n\n"
          "This approach ensures teams can navigate their data journey.\n\nThoughts?")
TELLS = ("It's not just a dashboard, but a way of thinking.\n\nHere's the thing: the best part? Let that sink in.\n\n"
         "Like this post if you agree and follow me for more.\n\nAgree?")
STRUCTURE = ("Accuracy went from 71% to 94%.\n\nTo test the model I split the data.\n\nShort one.\n\n"
             "I built the loader. I built the loader twice.\n\nI built the checks.\n\nI built the report and the report page.\n\n"
             "The pipeline ran 3 times, 3 times, 3 times \u2014 then \u2014 stopped. #data #python #sql\n\n"
             "What do you think?")


def main(out_path: str) -> None:
    queue = json.load(open(os.path.join(BASE, "data", "approved_queue.json"), encoding="utf-8"))
    history = json.load(open(os.path.join(BASE, "data", "post_history.json"), encoding="utf-8"))
    drafts = [{"text": p["text"]} for p in history + queue]
    drafts[-1]["sample"] = "A queued post (passes)"
    drafts += [{"text": FILLER, "sample": "Filler words and a vague close"}, {"text": TELLS, "sample": "AI tells and engagement bait"},
               {"text": STRUCTURE, "sample": "Flow, repetition and openers"},
               {"text": "\U0001F680 Shipped it! \U0001D5D5\U0001D5FC\U0001D5F9\U0001D5F1 text."}, {"text": "   "}]
    for d in drafts:
        d["python"] = writing_problems(d["text"])
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"source": "curiosync app/services/post_rules.py writing_problems", "drafts": drafts}, f, ensure_ascii=False, indent=1)
    print(f"{len(drafts)} drafts written to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1])
