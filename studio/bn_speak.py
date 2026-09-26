"""Bangla numbers to spoken words, for voice models that stumble on digits (IndicF5 skips or
mumbles them). Only the text sent to the voice changes; captions keep the digits.

    ৬৯ হাজার ১৪৯ জন      -> ঊনসত্তর হাজার একশো ঊনপঞ্চাশ জন
    ১৯৭১ সালে            -> উনিশশো একাত্তর সালে
    ২০২৩ সাল             -> দুই হাজার তেইশ সাল
    ৩,২১,০০০ / 1,782     -> তিন লাখ একুশ হাজার / এক হাজার সাতশো বিরাশি
    ৮১% / ৪.৫            -> একাশি শতাংশ / চার দশমিক পাঁচ
"""
import re

W = """শূন্য এক দুই তিন চার পাঁচ ছয় সাত আট নয়
দশ এগারো বারো তেরো চৌদ্দ পনেরো ষোলো সতেরো আঠারো উনিশ
বিশ একুশ বাইশ তেইশ চব্বিশ পঁচিশ ছাব্বিশ সাতাশ আটাশ ঊনত্রিশ
ত্রিশ একত্রিশ বত্রিশ তেত্রিশ চৌত্রিশ পঁয়ত্রিশ ছত্রিশ সাঁইত্রিশ আটত্রিশ ঊনচল্লিশ
চল্লিশ একচল্লিশ বিয়াল্লিশ তেতাল্লিশ চুয়াল্লিশ পঁয়তাল্লিশ ছেচল্লিশ সাতচল্লিশ আটচল্লিশ ঊনপঞ্চাশ
পঞ্চাশ একান্ন বাহান্ন তিপ্পান্ন চুয়ান্ন পঞ্চান্ন ছাপ্পান্ন সাতান্ন আটান্ন ঊনষাট
ষাট একষট্টি বাষট্টি তেষট্টি চৌষট্টি পঁয়ষট্টি ছেষট্টি সাতষট্টি আটষট্টি ঊনসত্তর
সত্তর একাত্তর বাহাত্তর তিয়াত্তর চুয়াত্তর পঁচাত্তর ছিয়াত্তর সাতাত্তর আটাত্তর ঊনআশি
আশি একাশি বিরাশি তিরাশি চুরাশি পঁচাশি ছিয়াশি সাতাশি অষ্টাশি ঊননব্বই
নব্বই একানব্বই বিরানব্বই তিরানব্বই চুরানব্বই পঁচানব্বই ছিয়ানব্বই সাতানব্বই আটানব্বই নিরানব্বই""".split()
assert len(W) == 100

_DIG = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
NUM = re.compile(r"(?<![0-9০-৯])([0-9০-৯]{1,3}(?:,[0-9০-৯]{2,3})+|[0-9০-৯]+)(?:\.([0-9০-৯]+))?(\s*%)?")


def words(n):
    if n < 100:
        return W[n]
    parts = []
    for val, name in ((10 ** 7, "কোটি"), (10 ** 5, "লাখ"), (1000, "হাজার")):
        if n >= val:
            q, n = divmod(n, val)
            parts.append(words(q) + " " + name)
    if n >= 100:
        h, n = divmod(n, 100)
        parts.append(W[h] + "শো")
    if n:
        parts.append(W[n])
    return " ".join(parts)


def _say(m):
    whole, frac, pct = m.group(1), m.group(2), m.group(3)
    digits = whole.translate(_DIG).replace(",", "")
    n = int(digits)
    if "," not in whole and len(digits) == 4 and 1100 <= n <= 1999 and not frac:
        s = W[n // 100] + "শো" + (" " + W[n % 100] if n % 100 else "")     # ১৯৭১ -> উনিশশো একাত্তর
    elif len(digits) > 1 and digits.startswith("0"):
        s = " ".join(W[int(d)] for d in digits)                             # ০১৭... read digit by digit
    else:
        s = words(n)
    if frac:
        s += " দশমিক " + " ".join(W[int(d)] for d in frac.translate(_DIG))
    if pct:
        s += " শতাংশ"
    return s


def spoken_bn(text):
    t = re.sub(r"(?<=[0-9০-৯])-(?=[ঀ-৿])", " ", text or "")   # ২০২৪-এ -> ২০২৪ এ
    t = NUM.sub(_say, t)
    t = re.sub(r"\*\*|__|[*#]", "", t)
    return re.sub(r"\s+", " ", t).strip()


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for s in ["স্বাস্থ্য অধিদপ্তরের হিসাবে ২৪ সেপ্টেম্বর পর্যন্ত ভর্তি ৬৯ হাজার ১৪৯ জন। মৃত্যু ২০৯।",
              "১৯৭১ সালে, ২০২৩ সাল, ২০২৪-এ মৃত্যু ৫৭৫, ৮১% রোগী, ৪.৫ শতাংশ, ৩,২১,০০০ জন, 1,782 জন, ১০০ জন, ১০১"]:
        print(spoken_bn(s))
