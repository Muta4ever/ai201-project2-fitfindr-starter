# Triggered Failure Modes — Test Evidence

These are the three deliberately-triggered failure modes from Milestone 5, with
the exact commands and the actual agent output. Use one of these in the demo video.

---

## 1. `search_listings` returns zero results

**Command:**
```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```
**Output:**
```
[]
```
Returns an empty list — no exception.

**Full agent on the same impossible query:**
```bash
python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
s = run_agent('designer ballgown size XXS under \$5', get_example_wardrobe())
print('error:', s['error'])
print('fit_card:', s['fit_card'])
"
```
**Output:**
```
error: No listings matched 'designer ballgown' in size XXS under $5. Try broader keywords, removing the size filter, or raising your max price.
fit_card: None
```
The agent stops early, sets a specific error, and never calls `suggest_outfit`/`create_fit_card`.

---

## 2. `suggest_outfit` with an empty wardrobe

**Command:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```
**Output (example run):**
```
This adorable Y2K Baby Tee is perfect for creating a sweet and playful look. Pair it with
a flowy skirt in a neutral shade like beige or denim for a whimsical, cottagecore-inspired
outfit. You could also team it with high-waisted jeans and sneakers for a casual, everyday
vibe... add some delicate accessories like a dainty necklace...
```
Returns useful **general** styling advice (no references to owned pieces that don't exist),
not an exception or an empty string.

---

## 3. `create_fit_card` with an empty outfit string

**Command:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```
**Output:**
```
Can't write a fit card without an outfit suggestion — try styling the item first.
```
Returns a descriptive error string — not a Python exception.
