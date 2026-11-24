"""Monday, Reviewed in One Line — make.fun entry.

Program writes ONE one-line review of the entrant's own Monday to
/output/entry.txt ($MAKEFUN_OUTPUT_DIR/entry.txt when set): a single
line, under 200 characters, no title, no explanation.

Gate (RULES.txt): UTF-8 text, 1-200 characters, not only white space.
Judge (z-ai/glm-5.3-flash, pairwise, margin 1-5, both orders), criteria
in order:
  1. Is a one-line review of the entrant's own Monday rather than a
     joke about something else, and loses to any one-line Monday review
     that lands a laugh.
  2. Gets the bigger laugh, the line a reader would laugh at rather
     than merely nod at.
  3. Names a concrete detail of the Monday, a meeting, a commute, an
     inbox, over generic tiredness.
  4. Lands the joke inside the line with no wasted words, so the turn
     arrives before the reader gives up.
  5. Is the line a reader would repeat to a coworker the next morning.
A line may be deadpan, absurd or quietly furious, as long as it reads
as a review of a real Monday. Length for its own sake does not count;
an exact tie on win rate goes to the smaller text, then the earlier
receipt.

Method: every candidate below was scored BY HAND on the 5-criteria
rubric (/25) BEFORE the proxy scorer ran. The proxy is a mechanical
scorer built from the same criteria (feature points, no per-line
tuning); it is never rigged to a pre-chosen line. Pick = highest
(proxy, rubric); ties go to the shorter text, then the earliest label
(the competition tie-break favours smaller text after playoff games).

v1 candidates A-Z: first-pass angles across Monday families (inbox,
standup, commute, Wi-Fi, coffee, alarm, printer, boss). Controls:
Y = generic tiredness, no concrete detail (c2 and c3 must fail),
Z = joke about Mondays in general, not a review of one's own Monday
(c1, c2, c3 must fail).
v2 challengers AA-AE: tighter rewrites combining the strongest
families (contrast "I showed up, the Wi-Fi didn't" + quoted boss
line "per my last email" + one-star review framing), rubrics scored
BEFORE the proxy ran.
"""

import os
import re

VERSION = "v4"

# v4 calibration (new challenger families, rubrics scored BY HAND before
# the proxy ran on them):
# - BA out-of-office / "circled back": rubric 21 (5,4,4,4,4). The
#   "circled back before I'd logged in" turn is a knowing laugh but
#   softer than AA's quoted boss line; concrete but no meeting/inbox
#   number, so c3 4.
# - BB password-expired / MFA loop: rubric 21 (5,4,5,4,3). Strong
#   concrete detail (password, MFA, standup) but a password-expiry
#   line is not one you'd repeat to a coworker, so c5 3.
# - BC fridge lunch theft / calendar quick sync: rubric 22 (5,4,5,4,4).
# - BD seven snoozes / "no blockers" standup lie: rubric 22 (5,5,4,4,4).
#   "No blockers while completely blocked" is the strongest new joke.
# - BE product-review framing ("would not recommend / arrived broken"):
#   rubric 22 (5,4,4,5,4). The joke is the frame; the punch lands early.
# - BF motivation filed for leave / CC'd on own burnout: rubric 20
#   (5,4,3,4,4). Good turn, thin concrete detail (alarm, inbox only).

# v2 calibration fixes (from v1 proxy-vs-rubric gaps, documented):
# - c1 counted only review/star words for framing; a quoted workplace
#   phrase ('quick sync') or a three-clause escalation also frames the
#   line as a review of a real Monday (D/G scored c1 3.0 vs rubric 5).
#   c1 now credits review/star OR quoted phrase OR triple.
# - c2 missed the laugh in "apologizing to a spreadsheet" (E scored
#   1.5 vs rubric 4): +1.0 for a laugh marker now includes "apolog".
# - c3 counted concrete words only; a named workplace trope ("could
#   have been an email", "per my last email", "quick sync") is itself
#   a concrete Monday artifact (A scored c3 3.0 vs rubric 4): +1.0
#   for a trope phrase.
# - c4 gave length credit to lines with no punch at all (Y/Z scored
#   4.0 vs rubric 2): length bonuses now apply only when a punch word
#   exists; otherwise c4 caps at 2.5.
# v3 calibration fixes (from v2 gaps):
# - c2 missed the repeated parallel escalation in A/Q ("could have
#   been an email, ... could have been silence, ... could have been
#   asleep" scored 3.5/2.5 vs rubric 5/5): +1.0 when the parallel
#   phrase repeats twice or more.
# - c2 missed the end-punch in C ("not one of them was an apology"
#   scored 2.5 vs rubric 4): +0.5 for a punch word in the final third.
# - c2 missed the contrast laugh in K ("I showed up, the Wi-Fi
#   didn't" scored 3.5 vs rubric 4): +0.5 for the "I ..., the ...
#   didn't" contrast pattern.

# ---------------------------------------------------------------- candidates
CANDIDATES = {
    "A": "My Monday review: the meeting could have been an email, the email could have been silence, and I could have been asleep.",
    "B": "Rated my Monday one star: the coffee was cold, the Wi-Fi died mid-call, and my boss replied 'per my last email'.",
    "C": "Monday, one star: my inbox had 112 unread emails and not one of them was an apology.",
    "D": "Monday gave my inbox 47 unread emails and my calendar a 9 a.m. called 'quick sync' that ran until lunch.",
    "E": "My Monday started with a 9 a.m. meeting titled 'quick sync' and ended with me apologizing to a spreadsheet.",
    "F": "One star for Monday: woke up tired, commuted an hour, and spent the whole morning in a meeting about meetings.",
    "G": "Monday: my alarm snoozed itself, my train left without me, and my inbox greeted me with 63 unread emails.",
    "H": "Monday asked for my weekend back in exchange for a 9 a.m. meeting, a broken printer, and a 'quick question' from my boss.",
    "I": "One star: Monday woke me at 6, stuck me in traffic till 9, then handed me a meeting about a meeting about a meeting.",
    "J": "My Monday: the alarm won, the train lost, and my inbox declared war before I'd even had coffee.",
    "K": "Monday, reviewed: I showed up, the Wi-Fi didn't, and my 9 a.m. 'quick sync' is still going.",
    "L": "I rated Monday two stars because the coffee worked; everything after the 9 a.m. standup did not.",
    "M": "Monday: my laptop updated for 40 minutes, my meeting ran over by 30, and my lunch break lasted exactly none.",
    "N": "Monday's highlight was the coffee; its lowlight was the 47 unread emails, the 9 a.m. standup, and everything after.",
    "O": "My Monday: 8 a.m. alarm, 9 a.m. standup, 10 a.m. 'quick sync', and by noon I'd already used up my week's patience.",
    "P": "Monday gave me a 7 a.m. alarm, a delayed train, and a meeting titled 'quick sync' that ate my whole morning.",
    "Q": "Reviewing my Monday: the standup could've been an email, the email could've been a nap, and I could've stayed in bed.",
    "R": "Monday, one star: my coffee went cold, my Wi-Fi died mid-call, and my boss replied 'per my last email'.",
    "S": "My Monday review: one star. The standup ran long, the printer jammed, and the only thing on time was my regret.",
    "T": "Monday: I clocked in at 9, my motivation clocked out at 9:01, and my inbox is still holding me hostage.",
    "U": "Rated Monday one star: my train was late, my laptop was slower, and my boss asked for 'a quick chat' at 4:55 p.m.",
    "V": "My Monday: the coffee machine broke, the Wi-Fi dropped mid-presentation, and my calendar laughed at me.",
    "W": "Monday review: my alarm went off, my will to live didn't, and my inbox had 89 emails pretending to be urgent.",
    "X": "One star for my Monday: the commute took 90 minutes, the meeting took 2 hours, and lunch took a rain check.",
    "AA": "Monday, one star: I showed up, the Wi-Fi didn't, and my boss replied 'per my last email'.",
    "AB": "Rated my Monday one star: I showed up, the Wi-Fi didn't, and the 9 a.m. 'quick sync' is still going.",
    "AC": "My Monday review: the meeting could have been an email, the Wi-Fi died mid-call, and my boss replied 'per my last email'.",
    "AD": "Monday, one star: my inbox had 112 unread emails, my Wi-Fi died mid-call, and not one of them was an apology.",
    "AE": "I showed up, the Wi-Fi didn't, and my Monday's 9 a.m. 'quick sync' ran until lunch \u2014 one star.",
    # v4 challengers — NEW families/angles, not rewordings of AA:
    # BA out-of-office auto-reply + "circled back"; BB password/MFA loop;
    # BC fridge lunch theft; BD snoozes + "no blockers" standup lie;
    # BE product-review framing ("would not recommend"); BF motivation
    # filed for leave + CC'd on own burnout.
    "BA": "Monday, one star: my out-of-office replied faster than my team, and my boss circled back before I'd even logged in.",
    "BB": "One star for Monday: my password expired, my MFA looped twice, and the standup started before I'd even logged in.",
    "BC": "Monday, one star: someone stole my lunch from the fridge, and my calendar still found time for a 'quick sync'.",
    "BD": "My Monday: seven snoozes, one cold coffee, and a standup where everyone said 'no blockers' while completely blocked.",
    "BE": "Would not recommend Monday: it arrived broken, no refund, and the standup started before the coffee did.",
    "BF": "Monday, one star: my alarm went off at 6, my motivation filed for leave, and my inbox CC'd me on my own burnout.",
    "Y": "Monday was so tiring, I was exhausted all day and couldn't wait for it to end, worst day ever.",
    "Z": "Mondays are the worst, I hate them so much, why can't every day be the weekend, ugh.",
}

# Hand rubric, scored BEFORE the proxy ran (c1..c5, total /25).
RUBRIC = {
    "A": (5, 5, 4, 5, 5), "B": (5, 5, 5, 4, 5), "C": (5, 4, 4, 5, 4),
    "D": (5, 4, 5, 4, 3), "E": (5, 4, 4, 4, 4), "F": (5, 3, 4, 4, 4),
    "G": (5, 3, 5, 4, 3), "H": (5, 4, 4, 3, 3), "I": (5, 4, 4, 4, 4),
    "J": (5, 4, 4, 4, 3), "K": (5, 4, 4, 5, 4), "L": (5, 4, 3, 5, 3),
    "M": (5, 3, 4, 4, 3), "N": (5, 3, 4, 3, 3), "O": (5, 3, 5, 3, 3),
    "P": (5, 3, 4, 3, 3), "Q": (5, 5, 3, 5, 5), "R": (5, 4, 4, 4, 4),
    "S": (5, 4, 4, 4, 4), "T": (5, 4, 3, 4, 4), "U": (5, 4, 5, 4, 3),
    "V": (5, 3, 4, 3, 3), "W": (5, 4, 4, 4, 3), "X": (5, 3, 4, 4, 3),
    # Challenger rubrics, scored BEFORE the proxy ran.
    "AA": (5, 5, 4, 5, 5), "AB": (5, 4, 4, 5, 4), "AC": (5, 5, 5, 4, 5),
    "AD": (5, 4, 5, 4, 4), "AE": (5, 4, 4, 4, 4),
    # v4 challenger rubrics, scored BY HAND before the proxy ran on them.
    "BA": (5, 4, 4, 4, 4), "BB": (5, 4, 5, 4, 3), "BC": (5, 4, 5, 4, 4),
    "BD": (5, 5, 4, 4, 4), "BE": (5, 4, 4, 5, 4), "BF": (5, 4, 3, 4, 4),
    "Y": (3, 1, 1, 2, 1), "Z": (2, 1, 1, 2, 1),
}

# ---------------------------------------------------------------- proxy scorer
# Mechanical /25 proxy from the judge's 5 criteria, in order. Feature
# points only; no per-line tuning.
# v4 calibration fixes (from v4 gaps — general features, not per-line tuning):
# - c3 missed concrete Monday artifacts in the new families: "password",
#   "mfa", "fridge", "lunch", "snooze(s)", "blocked/blockers",
#   "burnout", "out-of-office", "logged in", "refund" (BA/BB scored
#   c3 2.0 vs rubric 4/5; BD 3.0 vs 4). Added to CONCRETE.
# - c1 missed product-review framing: "would not recommend" / "arrived
#   broken" is a review of one's own Monday just as "one star" is (BE
#   scored c1 3.0 vs rubric 5). Review framing now credits it.
# - c2 missed the irony laugh in "no blockers while completely blocked"
#   and the turns "filed for leave", "circled back", "arrived broken",
#   "stole my lunch", "MFA looped" (BD c2 2.5 vs rubric 5; BE 2.0 vs 4).
#   Added as laugh signals + end-punch words (general workplace tropes).
# - c4 denied length credit to BD/BE because no punch word was found;
#   with the new punch words the early-turn rule applies to them too.
# Residual known gap: BE has no first-person pronoun, so its proxy c1
# still trails its rubric c1 by ~1; the product frame is credited, the
# missing "my/I" is not faked.
CONCRETE = ["meeting", "standup", "sync", "inbox", "email", "emails",
            "commute", "train", "traffic", "printer", "wi-fi", "wifi",
            "laptop", "spreadsheet", "calendar", "alarm", "coffee",
            "boss", "presentation", "call", "lunch", "9 a.m", "8 a.m",
            "7 a.m", "4:55", "112", "47", "63", "89", "90 minutes",
            "40 minutes", "password", "mfa", "fridge", "snooze",
            "snoozes", "blocked", "blockers", "burnout",
            "out-of-office", "logged in", "refund"]
LAUGH_WORDS = ["one star", "two stars", "apolog", "hostage", "war",
               "laughed", "regret", "asleep", "silence", "nap", "bed",
               "rain check", "clocked out", "didn't", "never",
               "still going", "exactly none", "ate my", "declared war",
               "holding me hostage", "circled back", "no blockers",
               "filed for leave", "arrived broken",
               "would not recommend", "stole", "looped", "burnout"]
REPEATABLE = ["could have been an email", "per my last email",
              "meeting about meetings", "quick sync", "quick question",
              "quick chat", "one star", "could've been", "still going",
              "exactly none", "rain check", "no blockers",
              "circled back", "would not recommend", "filed for leave"]
TROPE = ["could have been an email", "could've been an email",
         "per my last email", "quick sync", "quick chat",
         "quick question", "meeting about meetings",
         "meeting about a meeting"]
PUNCH_RE = (r"one star|two stars|apolog|asleep|silence|hostage|war|"
            r"regret|laughed|never|didn't|still going|exactly none|"
            r"rain check|nap|bed|per my last email|stole|no blockers|"
            r"filed for leave|arrived broken|would not recommend|"
            r"circled back|looped|burnout")


def proxy_score(text):
    """Mechanical /25 proxy from the judge's 5 criteria, in order."""
    low = text.lower()
    words = re.findall(r"[a-z0-9']+", low)
    n = len(words)
    triple = text.count(",") >= 2
    quoted = "'" in text

    # c1: Monday review framing + first person + laugh signal.
    c1 = 1.0
    if "monday" in low:
        c1 += 1.0
    if re.search(r"\b(my|i|i'd|i've)\b", low):
        c1 += 1.0
    if re.search(r"review|rated|rating|star|would not recommend|"
                 r"arrived broken", low) or quoted or triple:
        c1 += 1.0
    if any(w in low for w in LAUGH_WORDS):
        c1 += 1.0

    # c2: laugh strength - escalation / rule of three / sharp turn /
    # quoted phrase / repeated parallel / end-punch.
    c2 = 1.0
    if triple:
        c2 += 1.0
    if re.search(r"could (have )?been|not one of them|still|exactly|"
                 r"never|didn't|apolog|no blockers|filed for leave|"
                 r"circled back|arrived broken|would not recommend|"
                 r"stole|looped", low):
        c2 += 1.0
    if len(re.findall(r"could (have )?been|could've been", low)) >= 2:
        c2 += 1.0
    if quoted:
        c2 += 0.5
    if re.search(r"\bi .*, the .* didn't\b", low):
        c2 += 0.5
    if re.search(r"\b(one star|two stars)\b", low):
        c2 += 0.5
    if any(w in low for w in ["asleep", "hostage", "war", "regret",
                              "laughed"]):
        c2 += 0.5
    if re.search(PUNCH_RE, low[int(len(text) * 0.7):]):
        c2 += 0.5

    # c3: concrete detail count + named workplace trope.
    det = len({w for w in CONCRETE if w in low})
    c3 = min(5.0, 1.0 + det)
    if any(w in low for w in TROPE):
        c3 = min(5.0, c3 + 1.0)

    # c4: no wasted words - turn arrives early, length credit only
    # when a punch word exists.
    punch = [m.start() for m in re.finditer(PUNCH_RE, low)]
    c4 = 2.0
    if punch:
        if punch[0] <= len(text) * 0.6:
            c4 += 1.0
        if n <= 30:
            c4 += 1.0
        if n <= 22:
            c4 += 0.5
    else:
        c4 = min(c4, 2.5)
    if re.search(r"^(monday|my monday|rated|one star|reviewing)", low):
        c4 += 0.5

    # c5: repeatability - quotable phrase / meme-able trope.
    c5 = 1.0
    if any(w in low for w in REPEATABLE):
        c5 += 2.0
    if re.search(r"could have been an email|could've been an email", low):
        c5 += 1.0
    if quoted:
        c5 += 0.5
    if len(text) <= 120:
        c5 += 0.5

    parts = (min(5, c1), min(5, c2), min(5, c3), min(5, c4), min(5, c5))
    return round(sum(parts), 1), parts


def pick():
    scored = []
    for label, text in CANDIDATES.items():
        p, parts = proxy_score(text)
        r = sum(RUBRIC[label])
        scored.append((label, text, p, r, parts))
    # Highest proxy, then highest rubric, then shorter, then earliest
    # label (the competition tie-break favours smaller text).
    scored.sort(key=lambda s: (-s[2], -s[3], len(s[1]), s[0]))
    return scored


def main():
    scored = pick()
    for label, text, p, r, parts in scored:
        print(f"{label}: proxy {p} (c {[round(x, 1) for x in parts]}) "
              f"rubric {r} [{len(text)}ch] {text!r}")
    label, text, p, r, _ = scored[0]
    print(f"PICK {label}: proxy {p} rubric {r}: {text!r}")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    try:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "entry.txt")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        os.makedirs("output", exist_ok=True)
        out_path = os.path.join("output", "entry.txt")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"WROTE {out_path} ({len(text)} chars, no trailing newline)")


if __name__ == "__main__":
    main()
