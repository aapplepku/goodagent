# Amazon Berkeley Objects demo catalog

This demo bundle contains 48 English-language product listings selected
deterministically from the [Amazon Berkeley Objects (ABO) dataset](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html).
The product titles, descriptions, brands, categories, identifiers, and image
references come from ABO.

ABO is licensed under the Creative Commons Attribution 4.0 International
license. Credit for the source data and images belongs to Amazon.com. Credit
for constructing the source dataset and archives belongs to Matthieu
Guillaumin, Thomas Dideriksen, Kenan Deng, Himanshu Arora, Jasmine Collins,
and Jitendra Malik. See `LICENSE-CC-BY-4.0.txt`.

## Demo-only fields

ABO does not provide current prices, inventory, popularity, ratings, or shopper
engagement. Those fields in `catalog.csv` are deterministic synthetic values.
Every row is marked with `data_provenance` so the sample cannot be mistaken for
live Amazon commerce data.

`engagement.csv` is entirely synthetic. It contains pseudonymous identifiers
and generated search, view, add-to-cart, and purchase events linked to the 48
sample product IDs. It contains no Amazon customer data, reviews, emails,
addresses, names, or other direct identifiers.

The catalog uses local `/abo-images/...` paths so the demo does not depend on
third-party image delivery at runtime. `image-sources.csv` records the official
ABO URL, local path, SHA-256 digest, and CC BY 4.0 license for every mirrored
thumbnail.

## Rebuild

Download `abo-listings.tar` and `images/metadata/images.csv.gz` from the ABO
site, extract the listings archive, then run:

```bash
python scripts/build_abo_demo_dataset.py \
  --listings-dir /path/to/abo/listings/metadata \
  --image-metadata /path/to/images.csv.gz \
  --output-dir examples/datasets/amazon-berkeley-objects \
  --public-dir apps/web/public \
  --shopper-public-dir apps/shopper/public
```

The script always selects the same source records and generates the same demo
fields and pseudonymous events.
